from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.metrics import record_histogram, increment_counter
from lib.links.filters import is_included, randomly_execute_with_sampling
from lib.llm_client import create_llm_client, get_vendor_from_response
import time
import json
import copy

logger = init_logger(__name__)

default_options = {
    "prompt": "Analyze this vCon and return a JSON object with your analysis.",
    "analysis_type": "json_analysis",
    "model": "gpt-3.5-turbo-16k",
    "sampling_rate": 1,
    "temperature": 0,
    "system_prompt": "You are a helpful assistant that analyzes conversation data and returns structured JSON output.",
    "remove_body_properties": True,
    "response_format": {"type": "json_object"},
}


def get_analysis_for_type(vcon, analysis_type):
    for a in vcon.analysis:
        if a["type"] == analysis_type:
            return a
    return None


def generate_analysis(vcon_data, client, vcon_uuid, opts):
    """Generate analysis using the LLM client.

    Returns:
        Tuple of (analysis_result, response) where response contains provider info
    """
    prompt = opts.get("prompt", "")
    system_prompt = opts.get("system_prompt", "You are a helpful assistant.")

    # Convert vcon_data to a JSON string
    vcon_data_json = json.dumps(vcon_data)

    # Do not modify vCon data. If the system prompt text appears in the vCon itself,
    # it should be preserved for analysis.

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt + "\n\n" + vcon_data_json},
    ]

    response = client.complete_with_tracking(
        messages=messages,
        vcon_uuid=vcon_uuid,
        tracking_opts=opts,
        sub_type="ANALYZE_VCON",
        response_format=opts.get("response_format", {"type": "json_object"}),
    )

    return response.content, response


def is_valid_json(json_string):
    try:
        json.loads(json_string)
        return True
    except json.JSONDecodeError:
        return False


def prepare_vcon_for_analysis(vcon, remove_body_properties=True):
    """Create a copy of vCon with optional removal of body properties to save space"""
    vcon_copy = copy.deepcopy(vcon.to_dict())

    if remove_body_properties:
        if 'dialog' in vcon_copy:
            for dialog in vcon_copy['dialog']:
                if 'body' in dialog:
                    dialog.pop('body', None)

    return vcon_copy


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}: {link_name} plugin for: {vcon_uuid}")
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    if not is_included(opts, vCon):
        logger.info(f"Skipping {link_name} vCon {vcon_uuid} due to filters")
        return vcon_uuid

    if not randomly_execute_with_sampling(opts):
        logger.info(f"Skipping {link_name} vCon {vcon_uuid} due to sampling")
        return vcon_uuid

    # Check if analysis already exists
    analysis = get_analysis_for_type(vCon, opts["analysis_type"])
    if analysis:
        logger.info(
            "vCon %s already has a %s analysis",
            vCon.uuid,
            opts["analysis_type"],
        )
        return vcon_uuid

    # Create LLM client (supports OpenAI, Anthropic, and LiteLLM providers)
    client = create_llm_client(opts)
    logger.info(f"Using {client.provider_name} provider for model {opts.get('model', 'default')}")

    # Prepare vCon data for analysis (removing body properties if specified)
    vcon_data = prepare_vcon_for_analysis(vCon, opts["remove_body_properties"])

    # Filter out sensitive keys from logging
    filtered_opts = {
        k: v for k, v in opts.items()
        if k not in (
            "OPENAI_API_KEY", "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT", "ANTHROPIC_API_KEY",
            "ai_usage_api_token"
        )
    }
    logger.info(
        "Analyzing entire vCon with options: %s",
        filtered_opts,
    )

    start = time.time()
    try:
        analysis_result, response = generate_analysis(
            vcon_data=vcon_data,
            client=client,
            vcon_uuid=vcon_uuid,
            opts=opts,
        )

        # Validate JSON response
        if not is_valid_json(analysis_result):
            logger.error(
                "Invalid JSON response from LLM for vCon %s",
                vcon_uuid,
            )
            increment_counter(
                "conserver.link.llm.invalid_json",
                attributes={"analysis_type": opts['analysis_type'], "provider": client.provider_name},
            )
            raise ValueError("Invalid JSON response from LLM")

    except Exception as e:
        logger.error(
            "Failed to generate analysis for vCon %s after multiple retries: %s",
            vcon_uuid,
            e,
        )
        increment_counter(
            "conserver.link.llm.analysis_failures",
            attributes={"analysis_type": opts['analysis_type'], "provider": client.provider_name},
        )
        raise e

    record_histogram(
        "conserver.link.llm.analysis_time",
        time.time() - start,
        attributes={"analysis_type": opts['analysis_type'], "provider": client.provider_name},
    )

    vendor_schema = {}
    vendor_schema["model"] = response.model
    vendor_schema["prompt"] = opts["prompt"]
    vendor_schema["system_prompt"] = opts["system_prompt"]
    vendor_schema["provider"] = response.provider

    # Add analysis to vCon with no dialog index (applies to entire vCon)
    vCon.add_analysis(
        type=opts["analysis_type"],
        vendor=get_vendor_from_response(response),
        body=json.loads(analysis_result),  # Pass the parsed JSON
        dialog=0,  # Use dialog=0 to indicate it applies to the first/main dialog
        extra={
            "vendor_schema": vendor_schema,
        },
    )

    vcon_redis.store_vcon(vCon)
    logger.info(f"Finished analyze - {module_name}:{link_name} plugin for: {vcon_uuid}")

    return vcon_uuid


def navigate_dict(dictionary, path):
    keys = path.split(".")
    current = dictionary
    for key in keys:
        if key in current:
            current = current[key]
        else:
            return None
    return current
