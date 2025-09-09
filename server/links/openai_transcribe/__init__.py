import re
from urllib.parse import unquote, urlparse
from lib.logging_utils import init_logger
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)  # for exponential backoff
from server.lib.vcon_redis import VconRedis
from lib.error_tracking import init_error_tracker
from lib.metrics import init_metrics, stats_gauge, stats_count
import time
import io
import requests
from openai import OpenAI, AzureOpenAI

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
default_options = {
    "OPENAI_API_KEY": None,
    "AZURE_OPENAI_API_KEY": None,
    "AZURE_OPENAI_ENDPOINT": None,
    "AZURE_OPENAI_API_VERSION": "2024-10-21",
    "model": "gpt-4o-transcribe",
    "language": "en",
    "minimum_duration": 3,
}


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
def transcribe_openai(url: str, opts: dict = None) -> dict:
    """
    Get the transcription result from the Azure OpenAI Whisper API.
    This is a standalone function that directly interacts with Azure OpenAI.

    Args:
        url: URL of the audio file to transcribe
        opts: Optional configuration dict with Azure OpenAI credentials

    Returns:
        dict: Transcription result with text, confidence, language, duration, and segments
    """
    if opts is None:
        opts = default_options

    # Extract credentials from options
    openai_api_key = opts.get("OPENAI_API_KEY")
    azure_openai_api_key = opts.get("AZURE_OPENAI_API_KEY")
    azure_openai_endpoint = opts.get("AZURE_OPENAI_ENDPOINT")
    api_version = opts.get("AZURE_OPENAI_API_VERSION")
    model = opts.get("model", "gpt-4o-transcribe")

    client = None
    if openai_api_key:
        client = OpenAI(api_key=openai_api_key)
        logger.info("Using public OpenAI client")
    elif azure_openai_api_key and azure_openai_endpoint:
        client = AzureOpenAI(api_key=azure_openai_api_key, azure_endpoint=azure_openai_endpoint, api_version=api_version)
        logger.info(f"Using Azure OpenAI client at endpoint:{azure_openai_endpoint}")
    else:
        raise ValueError("OpenAI or Azure OpenAI credentials not provided. Need OPENAI_API_KEY or AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT")

    try:
        # Download the audio file from the URL
        audio_response = requests.get(url, stream=True, timeout=30)
        audio_response.raise_for_status()

        # Try to get filename from headers
        filename = None
        cd = audio_response.headers.get("content-disposition")
        if cd:
            # e.g., 'attachment; filename="track.mp4"'
            match = re.findall('filename="?([^";]+)"?', cd)
            if match:
                filename = match[0]

        # Fallback: derive from URL
        if not filename:
            path = urlparse(url).path
            filename = unquote(path.split("/")[-1]) or "audio.mp4"
        logger.info(f"The filename is: {filename}")

        # Prepare the audio file for transcription
        audio_file = io.BytesIO(audio_response.content)
        audio_file.name = filename

        # Make the transcription request
        transcription = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
        )
        # Convert response to dict format
        result = transcription.dict()

        logger.info(f"Transcription result: {result}")

        return result

    except Exception as e:
        logger.error(f"Failed to transcribe audio from {url}: {e}")
        raise e


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    """
    Main entry point for the OpenAI Transcribe link.
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
    logger.info(f"Starting openai_transcribe plugin for vCon: {vcon_uuid} with options")

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)
    logger.debug(f"Loaded vCon {vcon_uuid} with {len(vCon.dialog)} dialogs.")

    for index, dialog in enumerate(vCon.dialog):
        logger.debug(f"Processing dialog {index}: {dialog}")
        if dialog["type"] != "recording":
            logger.info(
                "openai_transcribe plugin: skipping non-recording dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        if not dialog.get("url"):
            logger.info(
                "openai_transcribe plugin: skipping no URL dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        duration = dialog.get("duration")

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

        # Initialize OpenAI client for each dialog (in case key changes)
        start = time.time()
        result = None
        try:
            logger.info(f"Transcribing dialog {index} in vCon {vCon.uuid} via OpenAI API...")
            result = transcribe_openai(dialog["url"], opts)
        except Exception as e:
            logger.error("Failed to transcribe vCon %s after multiple retries: %s", vcon_uuid, e, exc_info=True)
            stats_count("conserver.link.openai.transcription_failures")
            raise e
        elapsed = time.time() - start
        stats_gauge("conserver.link.openai.transcription_time", elapsed)
        logger.info(f"Transcription for dialog {index} took {elapsed:.2f} seconds.")

        if not result:
            logger.warning("No transcription generated for vCon %s, dialog %s", vcon_uuid, index)
            stats_count("conserver.link.openai.transcription_failures")
            break

        logger.info("Transcribed vCon: %s, dialog: %s", vCon.uuid, index)

        # Prepare vendor schema, omitting credentials
        vendor_schema = {}
        vendor_schema["opts"] = {k: v for k, v in opts.items() if k != "OPENAI_API_KEY" and k != "AZURE_OPENAI_API_KEY"}

        # Add the transcript analysis to the vCon
        vCon.add_analysis(
            type="transcript",
            dialog=index,
            vendor="openai",
            body=result,
            extra={
                "vendor_schema": vendor_schema,
            },
        )
    # Store the updated vCon back in Redis
    vcon_redis.store_vcon(vCon)

    # Forward the vcon_uuid down the chain (or None to halt processing)
    logger.info("Finished openai_transcribe plugin for vCon: %s", vcon_uuid)
    return vcon_uuid
