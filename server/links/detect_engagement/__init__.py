from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.metrics import record_histogram, increment_counter
from lib.links.filters import is_included, randomly_execute_with_sampling
from lib.llm_client import create_llm_client, get_vendor_from_response
import time
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


def check_engagement(transcript, prompt, client, vcon_uuid, opts) -> tuple:
    """Check engagement using the LLM client.

    Returns:
        Tuple of (is_engaged: bool, response) where response contains provider info
    """
    # Convert from Responses API format to Chat Completions format
    messages = [
        {"role": "user", "content": f"{prompt}\n\nTranscript: {transcript}"}
    ]

    response = client.complete_with_tracking(
        messages=messages,
        vcon_uuid=vcon_uuid,
        tracking_opts=opts,
        sub_type="DETECT_ENGAGEMENT",
    )

    # The response content should be "true" or "false"
    answer = response.content.strip().lower()
    is_engaged = answer == "true"

    return is_engaged, response


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

    # Check for API key in opts or environment (for backward compatibility)
    api_key = opts.get("OPENAI_API_KEY") or opts.get("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("No LLM API key defined, skipping analysis for vCon: %s", vcon_uuid)
        return vcon_uuid

    # Ensure at least one API key is set in opts for the llm_client
    if not opts.get("OPENAI_API_KEY") and not opts.get("ANTHROPIC_API_KEY"):
        opts["OPENAI_API_KEY"] = api_key

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
            "Analyzing engagement for dialog %s with options: %s",
            index,
            filtered_opts,
        )
        start = time.time()
        try:
            is_engaged, response = check_engagement(
                transcript=source_text,
                prompt=opts["prompt"],
                client=client,
                vcon_uuid=vcon_uuid,
                opts=opts,
            )

            # Always use string 'true'/'false' for tag and body
            is_engaged_str = "true" if is_engaged else "false"

            vendor_schema = {
                "model": response.model,
                "prompt": opts["prompt"],
                "is_engaged": is_engaged_str,
                "provider": response.provider,
            }

            vCon.add_analysis(
                type=opts["analysis_type"],
                dialog=index,
                vendor=get_vendor_from_response(response),
                body=is_engaged_str,
                encoding="none",
                extra={
                    "vendor_schema": vendor_schema,
                },
            )

            vCon.add_tag(tag_name="engagement", tag_value=is_engaged_str)
            logger.info(f"Applied engagement tag: {is_engaged_str}")

            increment_counter(
                "conserver.link.llm.engagement_detected",
                value=1 if is_engaged else 0,
                attributes={"analysis_type": opts['analysis_type'], "provider": client.provider_name},
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
                "conserver.link.llm.engagement_analysis_failures",
                attributes={"analysis_type": opts['analysis_type'], "provider": client.provider_name},
            )
            raise e

        record_histogram(
            "conserver.link.llm.engagement_analysis_time",
            time.time() - start,
            attributes={"analysis_type": opts['analysis_type'], "provider": client.provider_name},
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
