from typing import Optional
from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
import whisper
import requests
# import os


def read_url_to_file(url, file_name):
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        # Raise an HTTPError if the response was unsuccessful
        response.raise_for_status()
        # Open a file in write mode and write the content of the URL to a wav file
        with open(file_name, 'wb') as file:
            file.write(response.content)
        print(f"Content from {url} has been saved to {file_name}")
    except requests.exceptions.RequestException as e:
        print(f"Error reading URL {url}: {e}")


logger = init_logger(__name__)

default_options = {"minimum_duration": 30}


def get_transcription(vcon, index):
    for a in vcon.analysis:
        if a["dialog"] == index and a["type"] == "transcript":
            return a
    return None


def transcribe_whisper(file) -> Optional[dict]:
    model = whisper.load_model("base")
    result = model.transcribe(file)
    return result


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    logger.info("Starting whisper plugin for vCon: %s", vcon_uuid)

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    for index, dialog in enumerate(vCon.dialog):
        if dialog["type"] != "recording":
            logger.info(
                "whisper plugin: skipping non-recording dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        if not dialog["url"]:
            logger.info(
                "whisper plugin: skipping no URL dialog %s in vCon: %s",
                index,
                vCon.uuid,
            )
            continue

        if dialog["duration"] < opts["minimum_duration"]:
            logger.info(
                "Skipping short recording dialog %s in vCon: %s", index, vCon.uuid
            )
            continue

        # See if it was already transcibed
        if get_transcription(vCon, index) and opts["force_transcription"] is False:
            logger.info("Dialog %s already transcribed on vCon: %s", index, vCon.uuid)
            continue

        try:
            read_url_to_file(dialog['url'], f"dialog_{index}.wav")
            result = transcribe_whisper(f"dialog_{index}.wav")
            print(result)
        except Exception as e:
            logger.error(
                "Failed to transcribe vCon %s : %s", vcon_uuid, e
            )
            break

        if not result:
            logger.warning("No transcription generated for vCon %s", vcon_uuid)
            break

        logger.info("Transcribed via Whisper vCon: %s", vCon.uuid)

        body = {
            "transcript": result["text"],
            "sentences": result["segments"],
            "words": [],
            "confidence": 1,
            "detected_language": result["language"],
        }

        vCon.add_analysis(
            type="transcript",
            dialog=index,
            vendor="whisper",
            body=body,
        )

    vcon_redis.store_vcon(vCon)
    # delete the file
    # os.remove(f"dialog_{index}.wav")
    # Forward the vcon_uuid down the chain.
    # If you want the vCon processing to stop (if you are filtering them out, for instance)
    # send None
    logger.info("Finished whisper plugin for vCon: %s", vcon_uuid)
    return vcon_uuid
