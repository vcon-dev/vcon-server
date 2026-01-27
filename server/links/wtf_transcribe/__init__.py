"""WTF Transcription Link (vfun integration)

This link sends vCon audio dialogs to a vfun transcription server and adds
the results as WTF (World Transcription Format) analysis entries.

The vfun server provides:
- Multi-language speech recognition (English + auto-detect)
- Speaker diarization (who spoke when)
- GPU-accelerated processing with CUDA

Configuration options:
    vfun-server-url: URL of the vfun transcription server (required)
    diarize: Enable speaker diarization (default: true)
    timeout: Request timeout in seconds (default: 300)
    min-duration: Minimum dialog duration to transcribe in seconds (default: 5)
    api-key: Optional API key for vfun server authentication

Example configuration in config.yml:
    wtf_transcribe:
      module: links.wtf_transcribe
      options:
        vfun-server-url: http://localhost:8443/transcribe
        diarize: true
        timeout: 300
        min-duration: 5
        api-key: your-api-key-here
"""

import base64
import json
import logging
import os
import tempfile
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.error_tracking import init_error_tracker

init_error_tracker()
logger = init_logger(__name__)

default_options = {
    "vfun-server-url": None,
    "diarize": True,
    "timeout": 300,
    "min-duration": 5,
    "api-key": None,
}


def has_wtf_transcription(vcon: Any, dialog_index: int) -> bool:
    """Check if a dialog already has a WTF transcription."""
    for analysis in vcon.analysis:
        if (analysis.get("type") == "wtf_transcription" and
            analysis.get("dialog") == dialog_index):
            return True
    return False


def should_transcribe_dialog(dialog: Dict[str, Any], min_duration: float) -> bool:
    """Check if a dialog should be transcribed."""
    if dialog.get("type") != "recording":
        return False
    if not dialog.get("body") and not dialog.get("url"):
        return False
    duration = dialog.get("duration")
    if duration is not None and float(duration) < min_duration:
        return False
    return True


def get_audio_content(dialog: Dict[str, Any]) -> Optional[bytes]:
    """Extract audio content from dialog body or URL."""
    if dialog.get("body"):
        encoding = dialog.get("encoding", "base64")
        if encoding == "base64url":
            return base64.urlsafe_b64decode(dialog["body"])
        elif encoding == "base64":
            return base64.b64decode(dialog["body"])
        else:
            return dialog["body"].encode() if isinstance(dialog["body"], str) else dialog["body"]

    if dialog.get("url"):
        url = dialog["url"]
        if url.startswith("file://"):
            filepath = url[7:]
            try:
                with open(filepath, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read file {filepath}: {e}")
                return None
        else:
            try:
                resp = requests.get(url, timeout=60)
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                logger.error(f"Failed to fetch URL {url}: {e}")
                return None
    return None


def create_wtf_analysis(
    dialog_index: int,
    vfun_response: Dict[str, Any],
    duration: float,
) -> Dict[str, Any]:
    """Create a WTF analysis entry from vfun response."""
    now = datetime.now(timezone.utc).isoformat()

    # Extract text and segments from vfun response
    # vfun returns: analysis[].body with transcription data
    analysis_entries = vfun_response.get("analysis", [])

    full_text = ""
    segments = []
    language = "en-US"

    for entry in analysis_entries:
        if entry.get("type") in ("transcription", "wtf_transcription"):
            body = entry.get("body", {})

            # Handle different response formats
            if isinstance(body, dict):
                # WTF format from vfun
                transcript = body.get("transcript", {})
                full_text = transcript.get("text", body.get("text", ""))
                language = transcript.get("language", body.get("language", "en-US"))
                segments = body.get("segments", [])
            elif isinstance(body, str):
                full_text = body
            break

    # If no analysis found, check for direct text field
    if not full_text:
        full_text = vfun_response.get("text", "")
        segments = vfun_response.get("segments", [])

    # Calculate confidence
    if segments:
        confidences = [s.get("confidence", 0.9) for s in segments]
        avg_confidence = sum(confidences) / len(confidences)
    else:
        avg_confidence = 0.9

    # Build WTF segments
    wtf_segments = []
    for i, seg in enumerate(segments):
        wtf_seg = {
            "id": seg.get("id", i),
            "start": float(seg.get("start", seg.get("start_time", 0.0))),
            "end": float(seg.get("end", seg.get("end_time", 0.0))),
            "text": seg.get("text", seg.get("transcription", "")),
            "confidence": float(seg.get("confidence", 0.9)),
        }
        if "speaker" in seg:
            wtf_seg["speaker"] = seg["speaker"]
        wtf_segments.append(wtf_seg)

    # Build speakers section
    speakers = {}
    for seg in wtf_segments:
        speaker = seg.get("speaker")
        if speaker is not None:
            speaker_key = str(speaker)
            if speaker_key not in speakers:
                speakers[speaker_key] = {
                    "id": speaker,
                    "label": f"Speaker {speaker}",
                    "segments": [],
                    "total_time": 0.0,
                }
            speakers[speaker_key]["segments"].append(seg["id"])
            speakers[speaker_key]["total_time"] += seg["end"] - seg["start"]

    # Build WTF body
    wtf_body = {
        "transcript": {
            "text": full_text,
            "language": language,
            "duration": float(duration),
            "confidence": float(avg_confidence),
        },
        "segments": wtf_segments,
        "metadata": {
            "created_at": now,
            "processed_at": now,
            "provider": "vfun",
            "model": "parakeet-tdt-110m",
            "audio": {
                "duration": float(duration),
            },
        },
        "quality": {
            "average_confidence": float(avg_confidence),
            "multiple_speakers": len(speakers) > 1,
            "low_confidence_words": sum(1 for s in wtf_segments if s.get("confidence", 1.0) < 0.5),
        },
    }

    if speakers:
        wtf_body["speakers"] = speakers

    return {
        "type": "wtf_transcription",
        "dialog": dialog_index,
        "mediatype": "application/json",
        "vendor": "vfun",
        "product": "parakeet-tdt-110m",
        "schema": "wtf-1.0",
        # Note: encoding omitted since body is a direct object, not a JSON string
        "body": wtf_body,
    }


def run(
    vcon_uuid: str,
    link_name: str,
    opts: Dict[str, Any] = None,
) -> Optional[str]:
    """Process a vCon through the vfun transcription service."""
    merged_opts = default_options.copy()
    if opts:
        merged_opts.update(opts)
    opts = merged_opts

    logger.info(f"Starting wtf_transcribe link for vCon: {vcon_uuid}")

    vfun_server_url = opts.get("vfun-server-url")
    if not vfun_server_url:
        logger.error("wtf_transcribe: vfun-server-url is required")
        return vcon_uuid

    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)

    if not vcon:
        logger.error(f"wtf_transcribe: vCon {vcon_uuid} not found")
        return vcon_uuid

    # Find dialogs to transcribe
    dialogs_processed = 0
    dialogs_skipped = 0

    for i, dialog in enumerate(vcon.dialog):
        if not should_transcribe_dialog(dialog, opts.get("min-duration", 5)):
            logger.debug(f"Skipping dialog {i} (not eligible)")
            dialogs_skipped += 1
            continue

        if has_wtf_transcription(vcon, i):
            logger.debug(f"Skipping dialog {i} (already transcribed)")
            dialogs_skipped += 1
            continue

        # Get audio content
        audio_content = get_audio_content(dialog)
        if not audio_content:
            logger.warning(f"Could not extract audio from dialog {i}")
            dialogs_skipped += 1
            continue

        logger.info(f"Transcribing dialog {i} for vCon {vcon_uuid}")

        try:
            # Build request to vfun server
            headers = {}
            api_key = opts.get("api-key")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # Get filename from dialog or generate one
            filename = dialog.get("filename", f"audio_{i}.wav")
            mimetype = dialog.get("mimetype", "audio/wav")

            # Send audio to vfun server
            files = {"file": (filename, audio_content, mimetype)}
            data = {
                "diarize": str(opts.get("diarize", True)),
                "block": "true",
            }

            response = requests.post(
                vfun_server_url,
                files=files,
                data=data,
                headers=headers,
                timeout=opts.get("timeout", 300),
            )

            if response.status_code in (200, 302):
                vfun_response = response.json()
                # Handle double-encoded JSON (vfun sometimes returns JSON string)
                if isinstance(vfun_response, str):
                    vfun_response = json.loads(vfun_response)

                duration = dialog.get("duration", 30.0)
                wtf_analysis = create_wtf_analysis(i, vfun_response, float(duration))

                # Add analysis to vCon
                vcon.add_analysis(
                    type=wtf_analysis["type"],
                    dialog=wtf_analysis["dialog"],
                    vendor=wtf_analysis.get("vendor"),
                    body=wtf_analysis["body"],
                    extra={
                        "mediatype": wtf_analysis.get("mediatype"),
                        "product": wtf_analysis.get("product"),
                        "schema": wtf_analysis.get("schema"),
                    },
                )

                dialogs_processed += 1
                logger.info(f"Added WTF transcription for dialog {i}")

            else:
                logger.error(
                    f"vfun transcription failed for dialog {i}: "
                    f"status={response.status_code}, response={response.text[:200]}"
                )

        except requests.exceptions.Timeout:
            logger.error(f"vfun transcription timed out for dialog {i}")
        except Exception as e:
            logger.error(f"Error transcribing dialog {i}: {e}", exc_info=True)

    if dialogs_processed > 0:
        vcon_redis.store_vcon(vcon)
        logger.info(
            f"Updated vCon {vcon_uuid}: processed={dialogs_processed}, "
            f"skipped={dialogs_skipped}"
        )
    else:
        logger.info(f"No dialogs transcribed for vCon {vcon_uuid}")

    return vcon_uuid
