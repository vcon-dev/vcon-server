"""Hugging Face Whisper Integration Module

This module provides integration with Hugging Face's Whisper ASR service for transcribing audio content
in vCon recordings. It handles the transcription process, error retries, and updates vCon objects with
transcription results.
"""

import base64
import hashlib
import logging
import tempfile
import time
from typing import Optional

import requests
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from lib.error_tracking import init_error_tracker
from lib.logging_utils import init_logger
from lib.metrics import init_metrics, stats_gauge, stats_count
from server.lib.vcon_redis import VconRedis


# Initialize services
init_error_tracker()
init_metrics()
logger = init_logger(__name__)

# Default configuration for the Whisper service
default_options = {
    "minimum_duration": 30,  # Minimum duration in seconds for audio to be transcribed
    "API_URL": "https://xxxxxx.us-east-1.aws.endpoints.huggingface.cloud",
    "API_KEY": "Bearer hf_XXXXX",
    "Content-Type": "audio/flac",
}


def get_transcription(vcon, index: int) -> Optional[dict]:
    """Retrieve existing transcription for a dialog at specified index.

    Args:
        vcon: The vCon object containing the dialog
        index (int): Index of the dialog to check

    Returns:
        Optional[dict]: The transcription analysis if found, None otherwise
    """
    for a in vcon.analysis:
        if a["dialog"] == index and a["type"] == "transcript":
            return a
    return None


def get_file_content(dialog: dict) -> bytes:
    """Get file content from either inline or external reference.

    Args:
        dialog (dict): Dialog object containing file information

    Returns:
        bytes: The file content

    Raises:
        Exception: If file cannot be retrieved or verified
    """
    if "body" in dialog:
        # body contains the base64 encoded content. Decode and return
        return base64.b64decode(dialog["body"])

    elif "url" in dialog:
        # Handle external file
        response = requests.get(dialog["url"], verify=True)
        if response.status_code != 200:
            raise Exception(f"Failed to download file from {dialog['url']}")

        content = response.content

        # Verify file integrity if signature is provided
        if "signature" in dialog and "alg" in dialog:
            if dialog["alg"] == "SHA-512":
                file_hash = base64.urlsafe_b64encode(hashlib.sha512(content).digest()).decode('utf-8')
                if file_hash != dialog["signature"]:
                    raise Exception("File signature verification failed")
            else:
                raise Exception(f"Unsupported hash algorithm: {dialog['alg']}")

        return content
    else:
        raise Exception("Dialog contains neither inline body nor external URL")


@retry(
    wait=wait_exponential(multiplier=2, min=12, max=100),  # Will wait 12, 24, 48, 96, 192 seconds between retries
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def transcribe_hugging_face_whisper(dialog: dict, opts: dict) -> Optional[dict]:
    """Send audio to Hugging Face Whisper API for transcription.

    This function implements exponential backoff retry logic for API resilience.

    Args:
        dialog (dict): Dialog object containing the audio file information
        opts (dict): Configuration options including API credentials and settings

    Returns:
        Optional[dict]: Transcription result from the API

    Raises:
        RetryError: If all retry attempts fail
    """
    # Get file content handling both inline and external references
    content = get_file_content(dialog)

    # Write content to temporary file
    # with tempfile.NamedTemporaryFile(suffix='.flac', delete=True) as temp_file:
    #     temp_file.write(content)
    #     temp_file.flush()

    headers = {
        "Accept": "application/json",
        "Authorization": "Bearer " + opts['API_KEY'],
        "Content-Type": opts['Content-Type'],
    }
    response = requests.post(opts["API_URL"], headers=headers, data=content)
    # with open(temp_file.name, "rb") as f:

    return response.json()


def run(
    vcon_uuid: str,
    link_name: str,
    opts: dict = default_options,
) -> Optional[str]:
    """Process a vCon object through the Whisper transcription service.

    This function:
    1. Retrieves the vCon from Redis
    2. Processes each recording dialog that meets the minimum duration requirement
    3. Skips already transcribed dialogs
    4. Adds transcription results as analysis entries
    5. Updates the vCon in Redis

    Args:
        vcon_uuid (str): UUID of the vCon to process
        link_name (str): Name of the link (unused but required for plugin interface)
        opts (dict): Optional configuration overrides

    Returns:
        Optional[str]: The vcon_uuid if processing should continue, None to stop chain
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    logger.info("Starting whisper plugin for vCon: %s", vcon_uuid)

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    for index, dialog in enumerate(vCon.dialog):
        # Skip non-recording dialogs
        if dialog["type"] != "recording":
            logger.info(
                "whisper plugin: skipping non-recording dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        # Skip short recordings
        if int(dialog["duration"]) < opts["minimum_duration"]:
            logger.info("Skipping short recording dialog %s in vCon: %s", index, vCon.uuid)
            continue

        # Skip already transcribed dialogs
        if get_transcription(vCon, index):
            logger.info("Dialog %s already transcribed on vCon: %s", index, vCon.uuid)
            continue

        try:
            # Attempt transcription with timing metrics
            start = time.time()
            logger.debug("Transcribing dialog %s in vCon: %s", index, vCon.uuid)
            result = transcribe_hugging_face_whisper(dialog, opts)
            stats_gauge("conserver.link.hugging_face_whisper.transcription_time", time.time() - start)
        except (RetryError, Exception) as e:
            logger.error("Failed to transcribe vCon %s after multiple retries: %s", vcon_uuid, e)
            stats_count("conserver.link.hugging_face_whisper.transcription_failures")
            break

        if not result:
            logger.warning("No transcription generated for vCon %s", vcon_uuid)
            stats_count("conserver.link.hugging_face_whisper.transcription_failures")
            break

        logger.info("Transcribed vCon: %s", vCon.uuid)
        logger.info(result)

        # Prepare vendor schema without sensitive data
        vendor_schema = {"opts": {k: v for k, v in opts.items() if k != "API_KEY"}}

        # Add transcription analysis to vCon
        vCon.add_analysis(
            type="transcript",
            dialog=index,
            vendor="hugging_face_whisper",
            body=result,
            extra={
                "vendor_schema": vendor_schema,
            },
        )

    # Store updated vCon
    vcon_redis.store_vcon(vCon)

    logger.info("Finished hugging_face_whisper plugin for vCon: %s", vcon_uuid)
    return vcon_uuid
