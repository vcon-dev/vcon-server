from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
import logging
from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)  # for exponential backoff
from lib.metrics import init_metrics, stats_gauge, stats_count
import time
import json
import copy
from lib.links.filters import is_included, randomly_execute_with_sampling

init_metrics()

logger = init_logger(__name__)

default_options = {
    "prompt": "Analyze this vCon and return a JSON object with your analysis.",
    "analysis_type": "json_analysis",
    "model": "gpt-3.5-turbo-16k",
    "sampling_rate": 1,
    "temperature": 0,
    "system_prompt": "You are a helpful assistant that analyzes conversation data and returns structured JSON output.",
    "remove_body_properties": True,
}


def get_analysis_for_type(vcon, analysis_type):
    for a in vcon.analysis:
        if a["type"] == analysis_type:
            return a
    return None


@retry(
    wait=wait_exponential(multiplier=2, min=1, max=65),
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def generate_analysis(vcon_data, prompt, system_prompt, model, temperature, client) -> str:
    # Convert vcon_data to a JSON string
    vcon_data_json = json.dumps(vcon_data)

    # Check and replace the system_prompt in the JSON string
    if system_prompt in vcon_data_json:
        vcon_data_json = vcon_data_json.replace(system_prompt, "")
        # Log that the system_prompt was found and replaced
        logger.info(f"Replaced system_prompt in vcon_data for vcon_uuid: {vcon_uuid}")


    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt + "\n\n" + json.dumps(vcon_data)},
    ]

    

    response = client.chat.completions.create(
        model=model, 
        messages=messages, 
        temperature=temperature,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content


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

    client = OpenAI(api_key=opts["OPENAI_API_KEY"], timeout=120.0, max_retries=0)
    
    # Prepare vCon data for analysis (removing body properties if specified)
    vcon_data = prepare_vcon_for_analysis(vCon, opts["remove_body_properties"])
    
    logger.info(
        "Analyzing entire vCon with options: %s",
        {k: v for k, v in opts.items() if k != "OPENAI_API_KEY"},
    )
    
    start = time.time()
    try:
        analysis_result = generate_analysis(
            vcon_data=vcon_data,
            prompt=opts["prompt"],
            system_prompt=opts["system_prompt"],
            model=opts["model"],
            temperature=opts["temperature"],
            client=client,
        )
        
        # Validate JSON response
        if not is_valid_json(analysis_result):
            logger.error(
                "Invalid JSON response from OpenAI for vCon %s",
                vcon_uuid,
            )
            stats_count(
                "conserver.link.openai.invalid_json",
                tags=[f"analysis_type:{opts['analysis_type']}"],
            )
            raise ValueError("Invalid JSON response from OpenAI")
            
    except Exception as e:
        logger.error(
            "Failed to generate analysis for vCon %s after multiple retries: %s",
            vcon_uuid,
            e,
        )
        stats_count(
            "conserver.link.openai.analysis_failures",
            tags=[f"analysis_type:{opts['analysis_type']}"],
        )
        raise e

    stats_gauge(
        "conserver.link.openai.analysis_time",
        time.time() - start,
        tags=[f"analysis_type:{opts['analysis_type']}"],
    )

    vendor_schema = {}
    vendor_schema["model"] = opts["model"]
    vendor_schema["prompt"] = opts["prompt"]
    vendor_schema["system_prompt"] = opts["system_prompt"]
    
    # Add analysis to vCon with no dialog index (applies to entire vCon)
    vCon.add_analysis(
        type=opts["analysis_type"],
        vendor="openai",
        body=json.loads(analysis_result),  # Pass the raw JSON string instead of parsing it
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
