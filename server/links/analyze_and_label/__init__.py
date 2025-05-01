from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
import logging
import json
from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)  # for exponential backoff
from lib.metrics import init_metrics, stats_gauge, stats_count
import time
from lib.links.filters import is_included, randomly_execute_with_sampling

init_metrics()

logger = init_logger(__name__)

default_options = {
    "prompt": "Analyze this transcript and provide a list of relevant labels for categorization. Return your response as a JSON object with a single key 'labels' containing an array of strings.",
    "analysis_type": "labeled_analysis",
    "model": "gpt-4-turbo",
    "sampling_rate": 1,
    "temperature": 0.2,
    "source": {
        "analysis_type": "transcript",
        "text_location": "body.paragraphs.transcript",
    },
    "response_format": {"type": "json_object"}
}


def get_analysis_for_type(vcon, index, analysis_type):
    for a in vcon.analysis:
        if a["dialog"] == index and a["type"] == analysis_type:
            return a
    return None


@retry(
    wait=wait_exponential(multiplier=2, min=1, max=65),
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def generate_analysis_with_labels(transcript, prompt, model, temperature, client, response_format) -> dict:
    messages = [
        {"role": "system", "content": "You are a helpful assistant that analyzes text and provides relevant labels."},
        {"role": "user", "content": prompt + "\n\n" + transcript},
    ]

    response = client.chat.completions.create(
        model=model, 
        messages=messages, 
        temperature=temperature,
        response_format=response_format
    )
    
    return response.choices[0].message.content


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

    client = OpenAI(api_key=opts["OPENAI_API_KEY"], timeout=120.0, max_retries=0)
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

        logger.info(
            "Analysing dialog %s with options: %s",
            index,
            {k: v for k, v in opts.items() if k != "OPENAI_API_KEY"},
        )
        start = time.time()
        try:
            # Get the structured analysis with labels
            analysis_json_str = generate_analysis_with_labels(
                transcript=source_text,
                prompt=opts["prompt"],
                model=opts["model"],
                temperature=opts["temperature"],
                client=client,
                response_format=opts.get("response_format", {"type": "json_object"})
            )
            
            # Parse the response to get labels
            try:
                analysis_data = json.loads(analysis_json_str)
                labels = analysis_data.get("labels", [])
                
                # Add the structured analysis to the vCon
                vendor_schema = {}
                vendor_schema["model"] = opts["model"]
                vendor_schema["prompt"] = opts["prompt"]
                vCon.add_analysis(
                    type=opts["analysis_type"],
                    dialog=index,
                    vendor="openai",
                    body=analysis_json_str,
                    encoding="json",
                    extra={
                        "vendor_schema": vendor_schema,
                    },
                )
                
                # Apply each label as a tag
                for label in labels:
                    vCon.add_tag(tag_name=label, tag_value=label)
                    logger.info(f"Applied label as tag: {label}")
                
                stats_gauge(
                    "conserver.link.openai.labels_added",
                    len(labels),
                    tags=[f"analysis_type:{opts['analysis_type']}"],
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response for vCon {vcon_uuid}: {e}")
                stats_count(
                    "conserver.link.openai.json_parse_failures",
                    tags=[f"analysis_type:{opts['analysis_type']}"],
                )
                # Add the raw text anyway as the analysis
                vCon.add_analysis(
                    type=opts["analysis_type"],
                    dialog=index,
                    vendor="openai",
                    body=analysis_json_str,
                    encoding="none",
                    extra={
                        "vendor_schema": {
                            "model": opts["model"],
                            "prompt": opts["prompt"],
                            "parse_error": str(e)
                        },
                    },
                )
                
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

    vcon_redis.store_vcon(vCon)
    logger.info(f"Finished analyze_and_label - {module_name}:{link_name} plugin for: {vcon_uuid}")

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
