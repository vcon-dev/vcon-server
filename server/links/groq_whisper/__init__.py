"""Groq Face Whisper Integration Module

This module provides integration with Groq Face's Whisper ASR service for transcribing audio content
in vCon recordings. It handles the transcription process, error retries, and updates vCon objects with
transcription results.
"""

import base64
import hashlib
import logging
import tempfile
import time
import os
import sys
from typing import Optional, Dict, Any, Union
import importlib

# -----------------------------------------------------------------------------
# CRITICAL: Low-level monkey patching to resolve proxy issues
# -----------------------------------------------------------------------------
# The issue we're encountering is that httpx is picking up proxy settings from somewhere,
# and they're being injected into the Groq client initialization.
# We need to patch httpx before any Groq imports happen.

# Setup minimal logging for startup
startup_logger = logging.getLogger("server.links.groq_whisper.startup")
startup_logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
startup_logger.addHandler(handler)

# Clear proxy environment variables
proxy_env_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 'http_proxy', 'https_proxy', 'no_proxy']
for var in proxy_env_vars:
    if var in os.environ:
        startup_logger.warning(f"Unsetting proxy environment variable: {var}")
        del os.environ[var]

# Try to import and patch httpx before any Groq imports happen
try:
    import httpx
    
    # Store original Client class
    OriginalClient = httpx.Client
    
    # Create a patched Client class
    class PatchedClient(OriginalClient):
        def __init__(self, *args, **kwargs):
            # Remove proxy-related arguments
            for key in ['proxies', 'proxy']:
                if key in kwargs:
                    startup_logger.warning(f"Removing '{key}' from httpx.Client initialization")
                    del kwargs[key]
            # Call original init with cleaned kwargs
            super().__init__(*args, **kwargs)
    
    # Replace the httpx.Client with our patched version
    httpx.Client = PatchedClient
    startup_logger.info("Successfully patched httpx.Client to ignore proxy settings")
    
except ImportError:
    startup_logger.warning("Could not import httpx for patching")
except Exception as e:
    startup_logger.error(f"Failed to patch httpx: {e}")

# Now we can safely import the rest of the dependencies
import requests
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

# Import Groq client - should now be safe with patched httpx
from groq import Groq

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
    "API_KEY": os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY"),  # IMPORTANT: Replace with actual API key in environment variables
    "Content-Type": "audio/flac",
}


def get_transcription(vcon: Any, index: int) -> Optional[dict]:
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
                file_hash = base64.urlsafe_b64encode(
                    hashlib.sha512(content).digest()).decode('utf-8')
                if file_hash != dialog["signature"]:
                    raise Exception("File signature verification failed")
            else:
                raise Exception(f"Unsupported hash algorithm: {dialog['alg']}")

        return content
    else:
        raise Exception("Dialog contains neither inline body nor external URL")


@retry(
    wait=wait_exponential(multiplier=2, min=12, max=100),
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def transcribe_groq_whisper(dialog: dict, opts: dict) -> Union[Dict[str, Any], Any]:
    """Send audio to Groq Whisper API for transcription using the Groq Python library.

    Args:
        dialog (dict): Dialog object containing the audio file information
        opts (dict): Configuration options including API credentials and settings

    Returns:
        Union[Dict[str, Any], Any]: Transcription result from the API, which may be a dict
        or a Groq library response object

    Raises:
        RetryError: If all retry attempts fail
    """
    # Get file content handling both inline and external references
    content = get_file_content(dialog)

    # Write content to temporary file
    with tempfile.NamedTemporaryFile(suffix='.flac', delete=True) as temp_file:
        temp_file.write(content)
        temp_file.flush()
        
        # Initialize Groq client with API key
        api_key = opts['API_KEY']
        client = Groq(api_key=api_key)
        
        # Log client initialization
        logger.info(f"Initialized Groq client with version: {getattr(client, '__version__', 'unknown')}")
        
        # Get file name for the API request
        file_name = temp_file.name
        logger.debug(f"Using temporary file: {file_name}")
        
        # Log available client attributes to help debugging
        logger.debug(f"Groq client attributes: {dir(client)}")
        
        # Check for audio transcription capabilities
        if hasattr(client, 'audio') and hasattr(client.audio, 'transcriptions'):
            logger.info("Using client.audio.transcriptions API")
            # Open the audio file for the API request
            with open(file_name, 'rb') as audio_file:
                # Make the transcription request using the Groq client
                response = client.audio.transcriptions.create(
                    file=(file_name, audio_file.read()),
                    model="whisper-large-v3-turbo",  # Updated model name
                    response_format="json"
                )
                
                # Return the response
                return response
        elif hasattr(client, 'transcriptions'):
            logger.info("Using client.transcriptions API")
            # Alternative API structure
            with open(file_name, 'rb') as audio_file:
                response = client.transcriptions.create(
                    file=(file_name, audio_file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="json"
                )
                return response
        else:
            # Fallback for older API versions
            logger.warning("Could not find audio transcription API in Groq client. Using audio request directly.")
            
            # Create custom request to the Groq API endpoint directly
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            with open(file_name, 'rb') as audio_file:
                files = {
                    "file": (file_name, audio_file, "audio/flac")
                }
                data = {
                    "model": "whisper-large-v3-turbo",
                    "response_format": "json"
                }
                
                response = requests.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()  # Raise exception for HTTP errors
                
                # Parse the JSON response
                result = response.json()
                
                # Create a simple object with text attribute to match API
                class TranscriptionResult:
                    def __init__(self, text):
                        self.text = text
                
                return TranscriptionResult(result.get("text", ""))
            
        # Return the response (could be a dict or an object depending on Groq library version)
        return response


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
    
    # Add enhanced logging for debugging
    logger.debug(f"Python version: {sys.version}")
    logger.debug(f"Environment: {[(k, v) for k, v in os.environ.items() if 'proxy' in k.lower()]}")
    
    # Log versions of key dependencies if available
    try:
        import groq
        logger.info(f"Groq version: {getattr(groq, '__version__', 'unknown')}")
    except ImportError:
        logger.warning("Groq package not available for version checking")
    
    try:
        import httpx
        logger.info(f"httpx version: {httpx.__version__}")
    except ImportError:
        logger.debug("httpx not available for version checking")

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
            logger.info("Skipping short recording dialog %s in vCon: %s",
                        index, vCon.uuid)
            continue

        # Skip already transcribed dialogs
        if get_transcription(vCon, index):
            logger.info("Dialog %s already transcribed on vCon: %s", index,
                        vCon.uuid)
            continue

        try:
            # Attempt transcription with timing metrics
            start = time.time()
            logger.debug("Transcribing dialog %s in vCon: %s", index,
                         vCon.uuid)
            result = transcribe_groq_whisper(dialog, opts)
            stats_gauge("conserver.link.groq_whisper.transcription_time",
                        time.time() - start)
        except RetryError as re:
            logger.error(
                "Failed to transcribe vCon %s after multiple retry attempts: %s",
                vcon_uuid, re)
            stats_count("conserver.link.groq_whisper.transcription_failures")
            break
        except Exception as e:
            logger.error(
                "Unexpected error transcribing vCon %s: %s",
                vcon_uuid, e)
            stats_count("conserver.link.groq_whisper.transcription_failures")
            break

        if not result:
            logger.warning("No transcription generated for vCon %s", vcon_uuid)
            stats_count(
                "conserver.link.groq_whisper.transcription_failures")
            break

        logger.info("Transcribed vCon: %s", vCon.uuid)
        logger.info(f"Transcription result type: {type(result)}")
        logger.info(f"Transcription result attributes: {dir(result)}")
        
        # Check if result is a successful transcription
        if not hasattr(result, 'text'):
            logger.warning(f"Unexpected result format: {result}")
            stats_count("conserver.link.groq_whisper.transcription_failures")
            break

        # Handle different response formats from the Groq API
        # The result could be a dict, an object with model_dump method, or something else
        try:
            # First log the raw text
            logger.info(f"Transcription text: {result.text}")
            
            # Try to convert to a standard format
            transcription_data = None
            if hasattr(result, 'model_dump'):
                # For pydantic models
                transcription_data = result.model_dump()
            elif hasattr(result, '__dict__'):
                # For custom objects with __dict__
                transcription_data = vars(result)
            elif isinstance(result, dict):
                # Already a dict
                transcription_data = result
            else:
                # Fallback to a simple dict with text
                transcription_data = {
                    "text": str(result.text),
                    "raw_response": str(result)
                }
                
            # Ensure text is included
            if "text" not in transcription_data and hasattr(result, 'text'):
                transcription_data["text"] = result.text
                
            logger.info(f"Processed transcription data: {transcription_data}")
        except Exception as e:
            logger.error(f"Error processing transcription result: {e}")
            # Fallback to a very simple format
            transcription_data = {"text": str(getattr(result, 'text', result))}

        # Prepare vendor schema without sensitive data
        vendor_schema = {
            "opts": {
                k: v
                for k, v in opts.items() if k != "API_KEY"
            }
        }

        # Add transcription analysis to vCon
        vCon.add_analysis(
            type="transcript",
            dialog=index,
            vendor="groq_whisper",
            body=transcription_data,
            extra={
                "vendor_schema": vendor_schema,
            },
        )

    # Store updated vCon
    vcon_redis.store_vcon(vCon)

    logger.info("Finished groq_whisper plugin for vCon: %s", vcon_uuid)
    return vcon_uuid
