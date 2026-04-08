"""WTF Transcription Link (vfun integration)

This link sends every transcribable dialog to vfun for transcription,
and receives WTF (World Transcription Format) JSON objects.

Configuration options:
    vfun-server-url: URL of the vfun transcription server (required)
    language: Language override ("en" or "es"). If omitted, vfun auto-detects.
    diarize: Enable speaker diarization (default: False) (WIP)
    vfun-timeout: Request timeout in seconds (default: 300)
    url-timeout: URL Request timeout (when converting dialog url to audio)
    api-key: Optional API key for vfun server authentication

Example configuration in config.yml:
    wtf_transcribe:
      module: links.wtf_transcribe
      options:
        vfun-server-url: http://localhost:4380/wtf
        language: en
        diarize: true
        vfun-timeout: 300
        api-key: your-api-key-here
        url-timeout: 300
"""

import base64
import json
import logging
import requests
from typing import Optional, Dict, Any

from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.error_tracking import init_error_tracker

init_error_tracker()
logger = init_logger(__name__)

default_options = {
    "vfun-server-url": None,
    "language": None,
    "diarize": False,
    "vfun-timeout": 300,
    "url-timeout": 60,
    "api-key": None,
}

def analysis_is_wtf_transcription(analysis):
    return analysis.get("type") == "wtf_transcription"

def analysis_dialog_index(analysis):
    return analysis.get("dialog")

def is_dialog_recording(dialog):
    return dialog.get("type") == "recording"


def is_dialog_index_already_transcribed(vcon: Any, dialog_index: int) -> bool:
    for analysis in vcon.analysis:
        if (analysis_is_wtf_transcription(analysis) and
            analysis_dialog_index(analysis) == dialog_index):
            return True
    return False

def dialog_to_index(vcon, dialog):
    return vcon.dialog.index(dialog)

def is_dialog_already_transcribed(vcon, dialog):
    dialog_index = dialog_to_index(vcon, dialog)
    return is_dialog_index_already_transcribed(vcon, dialog_index)

def is_url_dialog(dialog):
    return bool(dialog.get("url"))

def is_file_url(url):
    return url.startswith("file://")

def file_url_to_path(url):
    return url.removeprefix("file://")

def maybe_load_file_url(url):
    path = file_url_to_path(url)
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read file {path}: {e}")

def maybe_load_remote_url(url, timeout):
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        return None

def url_dialog_to_binary(dialog, timeout=60):
    url = dialog["url"]
    if is_file_url(url):
        return maybe_load_file_url(url)
    return maybe_load_remote_url(url, timeout)

def has_body(dialog):
    return bool(dialog.get("body"))

def has_base64url_encoding(dialog):
    return dialog.get("encoding") == "base64url"

def is_base64url_dialog(dialog):
    return has_base64url_encoding(dialog) and has_body(dialog)

def base64url_dialog_to_binary(dialog):
    return base64.urlsafe_b64decode(dialog["body"])

def is_base64_dialog(dialog):
    return has_body(dialog)

def base64_dialog_to_binary(dialog):
    return base64.b64decode(dialog["body"])

def dialog_to_binary(dialog, url_timeout=60):
    if is_url_dialog(dialog):
        return url_dialog_to_binary(dialog, timeout=url_timeout)
    if is_base64url_dialog(dialog):
        return base64url_dialog_to_binary(dialog)
    if is_base64_dialog(dialog):
        return base64_dialog_to_binary(dialog)
    raise TypeError("Failed to convert dialog to binary-- unrecognized type")


def should_transcribe_dialog(vcon, dialog):
    if is_dialog_recording(dialog):
        if not is_dialog_already_transcribed(vcon, dialog):
            return True
    return False

def create_wtf_analysis(
    dialog_index: int,
    vfun_response: Dict[str, Any],
    language: Optional[str] = None) -> Dict[str, Any]:
    """Create a WTF analysis entry from vfun response.

    vfun returns a WTF-compliant body directly. If language is set in
    config, it is added to the transcript object.
    """
    if language and "transcript" in vfun_response:
        vfun_response["transcript"]["language"] = language

    return {
        "type": "wtf_transcription",
        "dialog": dialog_index,
        "mediatype": "application/json",
        "vendor": "vfun",
        "schema": "wtf-1.0",
        "body": vfun_response,
    }

def install_opts(opts):
    for key, value in default_options.items():
        if key not in opts:
            opts[key] = value
        

def verify_opts(opts):
    if not opts.get("vfun-server-url"):
        logger.error("wtf_transcribe: vfun-server-url is required")
        return False
    return True

def uuid_to_vcon(uuid, redis):
    return redis.get_vcon(uuid)

def init_redis():
    return VconRedis()

def dialog_to_audio_binary(dialog, url_timeout):
    return dialog_to_binary(dialog, url_timeout=url_timeout)

def dialog_filename(dialog, dialog_index):
    return dialog.get("filename", f"audio_{dialog_index}.wav")

def dialog_mimetype(dialog):
    return dialog.get("mimetype", "audio/wav")

def build_vfun_headers(api_key):
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers

def build_vfun_data(diarize, language):
    data = {"diarize": str(diarize).lower()}
    if language:
        data["language"] = language
    return data

def maybe_decode_double_encoded_json(response_json):
    if isinstance(response_json, str):
        return json.loads(response_json)
    return response_json

def send_audio_to_vfun(audio_binary, dialog, dialog_index, vfun_server_url, api_key, diarize, language, vfun_timeout):
    filename = dialog_filename(dialog, dialog_index)
    mimetype = dialog_mimetype(dialog)
    files = {"file-binary": (filename, audio_binary, mimetype)}
    headers = build_vfun_headers(api_key)
    data = build_vfun_data(diarize, language)
    response = requests.post(
        vfun_server_url,
        files=files,
        data=data,
        headers=headers,
        timeout=vfun_timeout,
    )
    response.raise_for_status()
    return maybe_decode_double_encoded_json(response.json())

def add_transcription_to_vcon(vcon, dialog_index, vfun_response, language):
    analysis = create_wtf_analysis(dialog_index, vfun_response, language=language)
    vcon.add_analysis(
        type=analysis["type"],
        dialog=analysis["dialog"],
        vendor=analysis.get("vendor"),
        body=analysis["body"],
        extra={
            "mediatype": analysis.get("mediatype"),
            "schema": analysis.get("schema"),
        },
    )

def transcribe_dialog(vcon, dialog, dialog_index, vfun_server_url, api_key, diarize, language, vfun_timeout, url_timeout):
    try:
        audio_binary = dialog_to_audio_binary(dialog, url_timeout)
        if not audio_binary:
            logger.warning(f"Could not extract audio from dialog {dialog_index}")
            return False
        vfun_response = send_audio_to_vfun(audio_binary, dialog, dialog_index, vfun_server_url, api_key, diarize, language, vfun_timeout)
        add_transcription_to_vcon(vcon, dialog_index, vfun_response, language)
        logger.info(f"Added WTF transcription for dialog {dialog_index}")
        return True
    except requests.exceptions.Timeout:
        logger.error(f"vfun transcription timed out for dialog {dialog_index}")
        return False
    except Exception as e:
        logger.error(f"Error transcribing dialog {dialog_index}: {e}", exc_info=True)
        return False

def transcribe_vcon_dialogs(vcon, vfun_server_url, api_key, diarize, language, vfun_timeout, url_timeout):
    for dialog_index, dialog in enumerate(vcon.dialog):
        if should_transcribe_dialog(vcon, dialog):
            transcribe_dialog(vcon, dialog, dialog_index, vfun_server_url, api_key, diarize, language, vfun_timeout, url_timeout)

def save_vcon(vcon, redis):
    redis.store_vcon(vcon)

def run(
    vcon_uuid: str,
    link_name: str,
    opts: Dict[str, Any] = None) -> Optional[str]:
    logger.info(f"Starting wtf_transcribe link for vCon: {vcon_uuid}")
    # default {} can be confusing
    opts = opts or {}
    install_opts(opts)
    redis = init_redis()

    if not verify_opts(opts):
        return None

    vcon = uuid_to_vcon(vcon_uuid, redis)
    if not vcon:
        logger.error(f"wtf_transcribe: vCon {vcon_uuid} not found")
        return None

    transcribe_vcon_dialogs(
        vcon,
        vfun_server_url=opts["vfun-server-url"],
        api_key=opts["api-key"],
        diarize=opts["diarize"],
        language=opts["language"],
        vfun_timeout=opts["vfun-timeout"],
        url_timeout=opts["url-timeout"],
    )
    save_vcon(vcon, redis)
    return vcon_uuid
