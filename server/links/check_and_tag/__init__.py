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
from lib.metrics import record_histogram, increment_counter
import time
from lib.links.filters import is_included, randomly_execute_with_sampling

logger = init_logger(__name__)

default_options = {
    "analysis_type": "tag_evaluation",
    "model": "gpt-5",
    "sampling_rate": 1,
    "source": {
        "analysis_type": "transcript",
        "text_location": "body",
    },
    "response_format": {"type": "json_object"},
    # Note: GPT-5 supports additional parameters like:
    "verbosity": "low",  # , "medium", "high" (controls response detail)
    "minimal_reasoning": True  # true/false (for faster responses)
    # - CFG (Context-Free Grammar) for structured outputs
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
def generate_tag_evaluation(transcript, evaluation_question, model,  client, response_format) -> str:
    messages = [
        {
            "role": "system", 
            "content": "You are a helpful assistant that evaluates text against specific questions and provides yes/no answers."
        },
        {
            "role": "user", 
            "content": (
                f"Question: {evaluation_question}\n\nText to evaluate:\n{transcript}\n\n"
                "Please answer with a JSON object containing a single key 'applies' with a boolean value "
                "(true if the tag applies, false if it doesn't)."
            )
        },
    ]

    response = client.chat.completions.create(
        model=model, 
        messages=messages, 
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

    # Validate required parameters
    if not opts.get("tag_name"):
        raise ValueError("tag_name is required for check_and_tag link")
    if not opts.get("tag_value"):
        raise ValueError("tag_value is required for check_and_tag link")
    if not opts.get("evaluation_question"):
        raise ValueError("evaluation_question is required for check_and_tag link")

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)
    if not vCon:
        logger.error(f"No vCon found for {vcon_uuid}")
        return vcon_uuid

    if not is_included(opts, vCon):
        logger.info(f"Skipping {link_name} vCon {vcon_uuid} due to filters")
        return vcon_uuid

    if not randomly_execute_with_sampling(opts):
        logger.info(f"Skipping {link_name} vCon {vcon_uuid} due to sampling")
        return vcon_uuid

    client = OpenAI(api_key=opts["OPENAI_API_KEY"], timeout=120.0, max_retries=0)
    source_type = navigate_dict(opts, "source.analysis_type")
    text_location = navigate_dict(opts, "source.text_location")

    logger.info("starting loop for vcon.dialog with %s dialogs", len(vCon.dialog))

    for index, dialog in enumerate(vCon.dialog):
        logger.info(
            "Analysing dialog %s for tag %s:%s",
            index,
            opts["tag_name"],
            opts["tag_value"],
        )
        start = time.time()
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
            # Get the tag evaluation
            analysis_json_str = generate_tag_evaluation(
                transcript=source_text,
                evaluation_question=opts["evaluation_question"],
                model=opts["model"],
                client=client,
                response_format=opts.get("response_format", {"type": "json_object"})
            )
            
            # Parse the response to get evaluation result
            analysis_data = json.loads(analysis_json_str)
            applies = analysis_data.get("applies", False)

            body = {
                "link_name": link_name,
                "tag": f"{opts['tag_name']}:{opts['tag_value']}",
                "applies": applies,
            }
            
            # Add the structured analysis to the vCon
            vendor_schema = {}
            vendor_schema["model"] = opts["model"]
            vendor_schema["evaluation_question"] = opts["evaluation_question"]
            vCon.add_analysis(
                type=opts["analysis_type"],
                dialog=index,
                vendor="openai",
                body=body,
                encoding="none",
                extra={
                    "vendor_schema": vendor_schema,
                },
            )
            
            # Apply tag if evaluation is positive
            if applies:
                vCon.add_tag(tag_name=opts["tag_name"], tag_value=opts["tag_value"])
                logger.info(f"Applied tag: {opts['tag_name']}:{opts['tag_value']} (evaluation: {applies})")
                increment_counter(
                    "conserver.link.openai.tags_applied",
                    attributes={"analysis_type": opts['analysis_type'], "tag_name": opts['tag_name'], "tag_value": opts['tag_value']},
                )
            else:
                logger.info(f"Tag not applied: {opts['tag_name']}:{opts['tag_value']} (evaluation: {applies})")
        except Exception as e:
            logger.error(
                "Failed to generate analysis for vCon %s after multiple retries: %s",
                vcon_uuid,
                e,
            )
            increment_counter(
                "conserver.link.openai.evaluation_failures",
                attributes={"analysis_type": opts['analysis_type'], "tag_name": opts['tag_name'], "tag_value": opts['tag_value']},
            )
            raise e

        record_histogram(
            "conserver.link.openai.evaluation_time",
            time.time() - start,
            attributes={"analysis_type": opts['analysis_type'], "tag_name": opts['tag_name'], "tag_value": opts['tag_value']},
        )

    vcon_redis.store_vcon(vCon)
    logger.info(f"Finished check_and_tag - {module_name}:{link_name} plugin for: {vcon_uuid}")

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
