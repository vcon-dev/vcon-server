from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.metrics import record_histogram, increment_counter
from lib.links.filters import is_included, randomly_execute_with_sampling
from lib.llm_client import create_llm_client, get_vendor_from_response
import time

logger = init_logger(__name__)

default_options = {
    "prompt": "",
    "analysis_type": "summary",
    "model": "gpt-3.5-turbo-16k",
    "sampling_rate": 1,
    "temperature": 0,
    "system_prompt": "You are a helpful assistant.",
    "source": {
        "analysis_type": "transcript",
        "text_location": "body.paragraphs.transcript",
    },
}


def get_analysis_for_type(vcon, index, analysis_type):
    for a in vcon.analysis:
        if a["dialog"] == index and a["type"] == analysis_type:
            return a
    return None


def generate_analysis(
    transcript, client, vcon_uuid, opts
):
    """Generate analysis using the LLM client.

    Returns:
        Tuple of (analysis_text, response) where response contains provider info
    """
    prompt = opts.get("prompt", "")
    system_prompt = opts.get("system_prompt", "You are a helpful assistant.")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt + "\n\n" + transcript},
    ]

    response = client.complete_with_tracking(
        messages=messages,
        vcon_uuid=vcon_uuid,
        tracking_opts=opts,
        sub_type="ANALYZE",
    )
    return response.content, response


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

    # Create LLM client (supports OpenAI, Anthropic, and LiteLLM providers)
    client = create_llm_client(opts)
    logger.info(f"Using {client.provider_name} provider for model {opts.get('model', 'default')}")

    source_type = navigate_dict(opts, "source.analysis_type")
    text_location = navigate_dict(opts, "source.text_location")

    for index, dialog in enumerate(vCon.dialog):
        source = get_analysis_for_type(vCon, index, source_type)
        if not source:
            logger.warning("No %s found for vCon: %s", source_type, vCon.uuid)
            continue
        source_text = navigate_dict(source, text_location)
        if not source_text:
            logger.warning("No source_text found at %s for vCon: %s", text_location, vCon.uuid)
            continue
        analysis = get_analysis_for_type(vCon, index, opts["analysis_type"])

        # See if it already has the analysis
        if analysis:
            logger.info(
                "Dialog %s already has a %s in vCon: %s",
                index,
                opts["analysis_type"],
                vCon.uuid,
            )
            continue

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
            "Analysing dialog %s with options: %s",
            index,
            filtered_opts,
        )
        start = time.time()
        try:
            analysis_text, response = generate_analysis(
                transcript=source_text,
                client=client,
                vcon_uuid=vcon_uuid,
                opts=opts,
            )
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
        vendor_schema["provider"] = response.provider
        vCon.add_analysis(
            type=opts["analysis_type"],
            dialog=index,
            vendor=get_vendor_from_response(response),
            body=analysis_text,
            encoding="none",
            extra={
                "vendor_schema": vendor_schema,
            },
        )
    vcon_redis.store_vcon(vCon)
    logger.info(f"Finished analyze - {module_name}:{link_name} plugin for: {vcon_uuid}")

    return vcon_uuid


def navigate_dict(dictionary, path):
    if dictionary is None:
        return None
    keys = path.split(".")
    current = dictionary
    for key in keys:
        if key in current:
            current = current[key]
        else:
            return None
    return current
