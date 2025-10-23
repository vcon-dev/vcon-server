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
import tempfile
import os
import ffmpeg
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
    "max_chunk_duration": 480,  # 8 minutes in seconds (OpenAI context window limit)
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


def get_audio_duration(audio_file_path: str) -> float:
    """
    Get the duration of an audio file using ffmpeg.
    
    Args:
        audio_file_path: Path to the audio file
        
    Returns:
        float: Duration in seconds
    """
    try:
        probe = ffmpeg.probe(audio_file_path)
        duration = float(probe['streams'][0]['duration'])
        return duration
    except Exception as e:
        logger.error(f"Failed to get audio duration for {audio_file_path}: {e}")
        raise e


def split_audio_file(audio_file_path: str, max_duration: int = 480) -> list:
    """
    Split an audio file into chunks that are under the maximum duration.
    
    Args:
        audio_file_path: Path to the audio file to split
        max_duration: Maximum duration per chunk in seconds (default: 480 = 8 minutes)
        
    Returns:
        list: List of paths to the split audio files
    """
    try:
        duration = get_audio_duration(audio_file_path)
        logger.info(f"Audio duration: {duration:.2f} seconds")
        
        if duration <= max_duration:
            logger.info("Audio is within duration limit, no splitting needed")
            return [audio_file_path]
        
        # Calculate number of chunks needed
        num_chunks = int(duration / max_duration) + 1
        chunk_files = []
        
        # Create temporary directory for chunks
        temp_dir = tempfile.mkdtemp()
        base_name = os.path.splitext(os.path.basename(audio_file_path))[0]
        
        for i in range(num_chunks):
            start_time = i * max_duration
            chunk_duration = min(max_duration, duration - start_time)
            
            if chunk_duration <= 0:
                break
                
            chunk_filename = f"{base_name}_chunk_{i:03d}.mp3"
            chunk_path = os.path.join(temp_dir, chunk_filename)
            
            # Use ffmpeg to extract the chunk
            (
                ffmpeg
                .input(audio_file_path, ss=start_time, t=chunk_duration)
                .output(chunk_path, acodec='mp3', ac=1, ar=16000)  # Convert to mono 16kHz for better transcription
                .overwrite_output()
                .run(quiet=True)
            )
            
            chunk_files.append(chunk_path)
            logger.info(f"Created chunk {i + 1}/{num_chunks}: {chunk_filename} ({chunk_duration:.2f}s)")
        
        return chunk_files
        
    except Exception as e:
        logger.error(f"Failed to split audio file {audio_file_path}: {e}")
        raise e


def combine_transcription_results(results: list) -> dict:
    """
    Combine multiple transcription results into a single result.
    
    Args:
        results: List of transcription result dictionaries
        
    Returns:
        dict: Combined transcription result
    """
    if not results:
        return {}
    
    if len(results) == 1:
        return results[0]
    
    # Combine text from all results
    combined_text = " ".join([result.get("text", "") for result in results if result.get("text")])
    
    # Combine usage statistics
    total_input_tokens = sum([result.get("usage", {}).get("input_tokens", 0) for result in results])
    total_output_tokens = sum([result.get("usage", {}).get("output_tokens", 0) for result in results])
    total_tokens = sum([result.get("usage", {}).get("total_tokens", 0) for result in results])
    
    # Use the first result as base and update with combined data
    combined_result = results[0].copy()
    combined_result["text"] = combined_text
    combined_result["usage"] = {
        "type": "tokens",
        "input_tokens": total_input_tokens,
        "total_tokens": total_tokens,
        "output_tokens": total_output_tokens,
        "input_token_details": {
            "text_tokens": 0,
            "audio_tokens": total_input_tokens
        }
    }
    
    # Add metadata about chunking
    combined_result["chunked_transcription"] = {
        "total_chunks": len(results),
        "chunk_results": results
    }
    
    return combined_result


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
    This function handles audio files longer than 25 minutes by splitting them into chunks.

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
    max_chunk_duration = opts.get("max_chunk_duration", 480)

    client = None
    if openai_api_key:
        client = OpenAI(api_key=openai_api_key)
        logger.info("Using public OpenAI client")
    elif azure_openai_api_key and azure_openai_endpoint:
        client = AzureOpenAI(
            api_key=azure_openai_api_key,
            azure_endpoint=azure_openai_endpoint,
            api_version=api_version
        )
        logger.info(f"Using Azure OpenAI client at endpoint:{azure_openai_endpoint}")
    else:
        raise ValueError(
            "OpenAI or Azure OpenAI credentials not provided. "
            "Need OPENAI_API_KEY or AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT"
        )

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

        # Save audio to temporary file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
            temp_file.write(audio_response.content)
            temp_file_path = temp_file.name

        try:
            # Split audio into chunks if needed
            chunk_files = split_audio_file(temp_file_path, max_chunk_duration)
            logger.info(f"Split audio into {len(chunk_files)} chunks")

            # Transcribe each chunk
            transcription_results = []
            for i, chunk_path in enumerate(chunk_files):
                logger.info(f"Transcribing chunk {i + 1}/{len(chunk_files)}")
                
                with open(chunk_path, 'rb') as chunk_file:
                    chunk_file_obj = io.BytesIO(chunk_file.read())
                    chunk_file_obj.name = os.path.basename(chunk_path)
                    
                    # Make the transcription request for this chunk
                    transcription = client.audio.transcriptions.create(
                        model=model,
                        file=chunk_file_obj,
                    )
                    # Convert response to dict format
                    result = transcription.dict()
                    logger.info(f"Transcription result: {result}")  
                    transcription_results.append(result)
                    logger.info(f"Completed transcription for chunk {i + 1}/{len(chunk_files)}")

            # Combine results if multiple chunks
            if len(transcription_results) > 1:
                logger.info("Combining transcription results from multiple chunks")
                result = combine_transcription_results(transcription_results)
            else:
                result = transcription_results[0]

            return result

        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_file_path)
                # TEMPORARILY COMMENTED OUT - Keep chunks for debugging
                # for chunk_path in chunk_files:
                #     if chunk_path != temp_file_path:  # Don't try to delete the original temp file twice
                #         os.unlink(chunk_path)
                # # Remove the temporary directory if it was created
                # if len(chunk_files) > 1:
                #     temp_dir = os.path.dirname(chunk_files[0])
                #     if temp_dir and temp_dir != os.path.dirname(temp_file_path):
                #         os.rmdir(temp_dir)
                logger.info(f"DEBUG: Chunk files preserved for inspection: {chunk_files}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temporary files: {cleanup_error}")

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
                logger.info(
                    "Skipping short recording dialog %s in vCon: %s (duration: %s < min: %s)",
                    index, vCon.uuid, duration, opts["minimum_duration"]
                )
                continue
        else:
            logger.warning(
                "Duration missing for dialog %s in vCon: %s and could not determine from file. "
                "Proceeding with transcription anyway.",
                index, vCon.uuid
            )

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
