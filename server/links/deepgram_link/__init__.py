from typing import Optional
from lib.logging_utils import init_logger
import logging
from deepgram import DeepgramClient, PrerecordedOptions
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)  # for exponential backoff
from server.lib.vcon_redis import VconRedis
import json
from lib.error_tracking import init_error_tracker
from lib.metrics import init_metrics, stats_gauge, stats_count
from lib.ai_usage import send_ai_usage_data_for_tracking
import time
import io
import requests
import wave

# Initialize error tracking and metrics systems for observability
init_error_tracker()
init_metrics()
# Set up a module-level logger
logger = init_logger(__name__)

# Default options for Deepgram transcription link
# - minimum_duration: minimum length (in seconds) for a dialog to be considered for transcription
# - DEEPGRAM_KEY: API key for Deepgram
# - api: dictionary of Deepgram API options
# (Note: 'api' is not present in the original default_options, but is expected in opts in run)
default_options = {"minimum_duration": 60, "DEEPGRAM_KEY": None}


def get_transcription(vcon, index):
    """
    Check if a transcript already exists for a given dialog index in the vCon.
    Returns the transcript analysis dict if found, else None.
    """
    for a in vcon.analysis:
        if a["dialog"] == index and a["type"] == "transcript":
            return a
    return None


@retry(
    wait=wait_exponential(
        multiplier=2, min=1, max=65
    ),  # Exponential backoff: 1, 2, 4, ... up to 32 seconds, max total < 65s
    stop=stop_after_attempt(6),  # Retry up to 6 times
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def transcribe_dg(dg_client, dialog, opts, vcon_uuid=None, run_opts=None) -> Optional[dict]:
    """
    Call Deepgram API to transcribe the audio at dialog['url'] with given options.
    Returns the transcript dict with detected language, or None on failure.
    Retries on failure with exponential backoff.
    
    Args:
        dg_client: Deepgram client instance
        dialog: Dialog dict containing the audio URL
        opts: Deepgram API options
        vcon_uuid: Optional vCon UUID for usage tracking
        run_opts: Optional full options dict containing usage tracking config
    """
    url = dialog["url"]
    logger.debug(f"Preparing to transcribe URL: {url}")
    source = {"url": url}
    options = PrerecordedOptions(**opts)
    url_response = dg_client.listen.rest.v("1").transcribe_url(source, options)
    response = json.loads(url_response.to_json())
    logger.debug(f"Deepgram API response: {response}")

    # Extract duration from response metadata (in seconds, per Deepgram API docs)
    # Reference: https://developers.deepgram.com/docs/pre-recorded-audio#results
    metadata = response.get("metadata", {})
    duration_seconds = round(metadata.get("duration", 0))

    print(f"Duration seconds: {duration_seconds}")
    print(f"Metadata: {metadata}")
    
    # Send AI usage data for tracking (Deepgram bills on input seconds)
    if vcon_uuid and run_opts:
        send_ai_usage_data_to_url = run_opts.get("send_ai_usage_data_to_url", "")
        ai_usage_api_token = run_opts.get("ai_usage_api_token", "")
        
        send_ai_usage_data_for_tracking(
            vcon_uuid=vcon_uuid,
            input_units=duration_seconds,
            output_units=0,  # Deepgram doesn't bill on output
            unit_type="seconds",
            type="VCON_PROCESSING",
            send_ai_usage_data_to_url=send_ai_usage_data_to_url,
            ai_usage_api_token=ai_usage_api_token,
            model="nova-3",
            sub_type="DEEPGRAM_TRANSCRIBE",
        )

    alternatives = response["results"]["channels"][0]["alternatives"]
    detected_language = response["results"]["channels"][0].get("detected_language", "en")
    transcript = alternatives[0]
    transcript["detected_language"] = detected_language
    return transcript


def get_wav_duration_from_url(url):
    """
    Returns the duration in seconds of a WAV file at the given URL.
    Only works for uncompressed WAV files.
    """
    try:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        with io.BytesIO(response.content) as wav_io:
            with wave.open(wav_io, 'rb') as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                duration = frames / float(rate)
        return duration
    except Exception as e:
        logger.warning(f"Could not determine duration for {url}: {e}")
        return None


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    """
    Main entry point for the Deepgram link.
    Processes each dialog in the vCon:
      - Filters for recordings with valid URLs and sufficient duration
      - Skips already transcribed dialogs
      - Calls Deepgram API for transcription
      - Stores transcript in vCon if confidence is high enough
      - Tracks metrics and logs progress
    Returns the vcon_uuid if processing continues, or None to halt the chain.
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    logger.info(f"Starting deepgram plugin for vCon: {vcon_uuid}")

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)
    logger.debug(f"Loaded vCon {vcon_uuid} with {len(vCon.dialog)} dialogs.")

    for index, dialog in enumerate(vCon.dialog):
        logger.debug(f"Processing dialog {index}: {dialog}")
        if dialog["type"] != "recording":
            logger.info(
                "deepgram plugin: skipping non-recording dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        if not dialog["url"]:
            logger.info(
                "deepgram plugin: skipping no URL dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        duration = dialog.get("duration")
        if duration is None and dialog["url"].lower().endswith('.wav'):
            logger.info(f"Duration missing for dialog {index}, attempting to fetch from WAV file at {dialog['url']}")
            duration = get_wav_duration_from_url(dialog["url"])
            if duration is not None:
                dialog["duration"] = duration  # Optionally, store it for future use

        if duration is not None:
            if duration < opts["minimum_duration"]:
                logger.info("Skipping short recording dialog %s in vCon: %s (duration: %s < min: %s)", index, vCon.uuid, duration, opts["minimum_duration"])
                continue
        else:
            logger.warning("Duration missing for dialog %s in vCon: %s and could not determine from file. Proceeding with transcription anyway.", index, vCon.uuid)

        # Check if already transcribed
        if get_transcription(vCon, index):
            logger.info("Dialog %s already transcribed on vCon: %s", index, vCon.uuid)
            continue

        # Initialize Deepgram client for each dialog (in case key changes)
        dg_client = DeepgramClient(opts["DEEPGRAM_KEY"])
        start = time.time()
        try:
            logger.info(f"Transcribing dialog {index} in vCon {vCon.uuid} via Deepgram API...")
            result = transcribe_dg(dg_client, dialog, opts["api"], vcon_uuid=vcon_uuid, run_opts=opts)
        except Exception as e:
            logger.error("Failed to transcribe vCon %s after multiple retries: %s", vcon_uuid, e, exc_info=True)
            stats_count("conserver.link.deepgram.transcription_failures")
            raise e
        elapsed = time.time() - start
        stats_gauge("conserver.link.deepgram.transcription_time", elapsed)
        logger.info(f"Transcription for dialog {index} took {elapsed:.2f} seconds.")

        if not result:
            logger.warning("No transcription generated for vCon %s, dialog %s", vcon_uuid, index)
            stats_count("conserver.link.deepgram.transcription_failures")
            break

        # Log and track confidence
        stats_gauge("conserver.link.deepgram.confidence", result["confidence"])
        logger.info(f"Transcription confidence for dialog {index}: {result['confidence']}")

        # If the confidence is too low, don't store the transcript
        if result["confidence"] < 0.5:
            logger.warning("Low confidence result for vCon %s, dialog %s: %s", vcon_uuid, index, result["confidence"])
            stats_count("conserver.link.deepgram.transcription_failures")
            break

        logger.info("Transcribed vCon: %s, dialog: %s", vCon.uuid, index)

        # Prepare vendor schema, omitting credentials
        vendor_schema = {}
        vendor_schema["opts"] = {k: v for k, v in opts.items() if k != "DEEPGRAM_KEY"}

        # Add the transcript analysis to the vCon
        vCon.add_analysis(
            type="transcript",
            dialog=index,
            vendor="deepgram",
            body=result,
            extra={
                "vendor_schema": vendor_schema,
            },
        )
    # Store the updated vCon back in Redis
    vcon_redis.store_vcon(vCon)

    # Forward the vcon_uuid down the chain (or None to halt processing)
    logger.info("Finished deepgram plugin for vCon: %s", vcon_uuid)
    return vcon_uuid
