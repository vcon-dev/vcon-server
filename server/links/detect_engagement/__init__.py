from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
import logging
from openai import OpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)
from lib.metrics import record_histogram, increment_counter
import time
from lib.links.filters import is_included, randomly_execute_with_sampling
import os
logger = init_logger(__name__)

default_options = {
    "prompt": "Did both the customer and the agent speak? Respond with 'true' if yes, 'false' if not. Respond with only 'true' or 'false'.",
    "analysis_type": "engagement_analysis",
    "model": "gpt-4.1",
    "sampling_rate": 1,
    "temperature": 0.2,
    "source": {
        "analysis_type": "transcript",
        "text_location": "body.paragraphs.transcript",
    },
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "")  # Make it optional with empty default
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
def check_engagement(transcript, prompt, model, temperature, client) -> bool:
    # The new responses API expects a single string or a list of message dicts as 'input'
    input_text = f"{prompt}\n\nTranscript: {transcript}"

    response = client.responses.create(
        model=model,
        input=input_text,
        temperature=temperature
    )
    
    # The new API returns the result in response.output_text
    answer = response.output_text.strip().lower()
    return answer == "true"

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

    # Check for OPENAI_API_KEY in opts or environment
    openai_key = opts.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.warning("OPENAI_API_KEY not defined, skipping analysis for vCon: %s", vcon_uuid)
        return vcon_uuid
    opts["OPENAI_API_KEY"] = openai_key

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    if not is_included(opts, vCon):
        logger.info(f"Skipping {link_name} vCon {vcon_uuid} due to filters")
        return vcon_uuid

    if not randomly_execute_with_sampling(opts):
        logger.info(f"Skipping {link_name} vCon {vcon_uuid} due to sampling")
        return vcon_uuid

    client = OpenAI(api_key=opts["OPENAI_API_KEY"], timeout=120.0, max_retries=0)
    source_type = opts["source"]["analysis_type"]
    text_location = opts["source"]["text_location"]

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
        if analysis:
            logger.info(
                "Dialog %s already has a %s in vCon: %s",
                index,
                opts["analysis_type"],
                vCon.uuid,
            )
            continue

        logger.info(
            "Analyzing engagement for dialog %s with options: %s",
            index,
            {k: v for k, v in opts.items() if k != "OPENAI_API_KEY"},
        )
        start = time.time()
        try:
            is_engaged = check_engagement(
                transcript=source_text,
                prompt=opts["prompt"],
                model=opts["model"],
                temperature=opts["temperature"],
                client=client
            )

            # Always use string 'true'/'false' for tag and body
            is_engaged_str = "true" if is_engaged else "false"

            vendor_schema = {
                "model": opts["model"],
                "prompt": opts["prompt"],
                "is_engaged": is_engaged_str
            }

            vCon.add_analysis(
                type=opts["analysis_type"],
                dialog=index,
                vendor="openai",
                body=is_engaged_str,
                encoding="none",
                extra={
                    "vendor_schema": vendor_schema,
                },
            )

            vCon.add_tag(tag_name="engagement", tag_value=is_engaged_str)
            logger.info(f"Applied engagement tag: {is_engaged_str}")

            increment_counter(
                "conserver.link.openai.engagement_detected",
                value=1 if is_engaged else 0,
                attributes={"analysis_type": opts['analysis_type']},
            )

        except Exception as e:
            import traceback
            logger.error(
                "Failed to generate engagement analysis for vCon %s after multiple retries: %s\nException type: %s\nTraceback:\n%s",
                vcon_uuid,
                e,
                type(e).__name__,
                traceback.format_exc()
            )
            increment_counter(
                "conserver.link.openai.engagement_analysis_failures",
                attributes={"analysis_type": opts['analysis_type']},
            )
            raise e

        record_histogram(
            "conserver.link.openai.engagement_analysis_time",
            time.time() - start,
            attributes={"analysis_type": opts['analysis_type']},
        )

    vcon_redis.store_vcon(vCon)
    logger.info(f"Finished detect_engagement - {module_name}:{link_name} plugin for: {vcon_uuid}")

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