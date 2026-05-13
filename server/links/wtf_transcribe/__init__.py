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
    cacheish: Enable audio caching for repetitive content (default: true)

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
import hashlib
import json
import logging
import os
import random
import tempfile
import time
import threading
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.error_tracking import init_error_tracker
from lib.metrics import increment_counter
from redis_mgr import redis
from links.wtf_transcribe.fingerprint_cache import compute_hashes, FingerprintCache

init_error_tracker()
logger = init_logger(__name__)

# Per-worker in-memory fingerprint cache (populated after fork)
_fingerprint_cache = FingerprintCache(max_entries=1000)


# ---------------------------------------------------------------------------
# Health-aware vfun URL selector with self-healing
# ---------------------------------------------------------------------------
class _VfunHealthTracker:
    """Track vfun instance health across all workers in this process.

    Instances are marked DOWN on connection/timeout/HTTP errors and
    automatically re-checked after `recovery_seconds`.  Selection prefers
    healthy instances with random load balancing; when all are down the
    least-recently-failed instance is tried first.
    """

    def __init__(self, recovery_seconds: float = 30.0):
        self._lock = threading.Lock()
        # url -> timestamp when it was marked down (0 = healthy)
        self._down_since: Dict[str, float] = {}
        self._recovery_seconds = recovery_seconds

    def _is_healthy(self, url: str, now: float) -> bool:
        ts = self._down_since.get(url, 0)
        if ts == 0:
            return True
        # Self-heal: allow retry after recovery window
        return (now - ts) >= self._recovery_seconds

    def mark_down(self, url: str) -> None:
        with self._lock:
            if self._down_since.get(url, 0) == 0:
                logger.warning("vfun instance marked DOWN: %s", url)
            self._down_since[url] = time.monotonic()

    def mark_healthy(self, url: str) -> None:
        with self._lock:
            was_down = self._down_since.get(url, 0) != 0
            self._down_since[url] = 0
            if was_down:
                logger.info("vfun instance recovered: %s", url)

    def get_ordered_urls(self, urls: List[str]) -> List[str]:
        """Return URLs ordered: healthy (shuffled) first, then recovering
        (oldest-failure first), then remaining down instances."""
        now = time.monotonic()
        healthy = []
        recovering = []
        down = []
        with self._lock:
            for url in urls:
                ts = self._down_since.get(url, 0)
                if ts == 0:
                    healthy.append(url)
                elif (now - ts) >= self._recovery_seconds:
                    recovering.append((ts, url))
                else:
                    down.append((ts, url))
        random.shuffle(healthy)
        recovering.sort()  # oldest failure first (most likely recovered)
        down.sort()
        return healthy + [u for _, u in recovering] + [u for _, u in down]


# Module-level singleton shared across all workers in this process
_health_tracker = _VfunHealthTracker(recovery_seconds=30.0)

default_options = {
    "vfun-server-url": None,
    "vfun-server-urls": None,  # List of URLs for load balancing
    "diarize": True,
    "timeout": 300,
    "min-duration": 5,
    "api-key": None,
    "cache-ttl": 604800,  # 7 days in seconds
    "fingerprint-cache-size": 1000,  # max entries in fingerprint cache
}

# Redis cache key prefixes for transcription results
WTF_CACHE_PREFIX = "wtf_cache:"
TRANSCRIPTION_PREFIX = "transcription:"


def _get_filename_from_dialog(dialog: Dict[str, Any]) -> Optional[str]:
    """Extract the audio filename from a dialog's URL."""
    url = dialog.get("url", "")
    if url:
        if url.startswith("file://"):
            return os.path.basename(url[7:])
        else:
            return os.path.basename(url.split("?")[0])
    return None


def get_cache_key(dialog: Dict[str, Any]) -> Optional[str]:
    """Derive a cache key from the dialog's audio file URL or body hash."""
    filename = _get_filename_from_dialog(dialog)
    if filename:
        return f"{WTF_CACHE_PREFIX}{filename}"
    # Fall back to hashing the body content
    body = dialog.get("body")
    if body:
        body_hash = hashlib.sha256(body.encode() if isinstance(body, str) else body).hexdigest()[:32]
        return f"{WTF_CACHE_PREFIX}hash:{body_hash}"
    return None


def get_cached_transcription(cache_key: str, dialog: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check Redis for a cached WTF transcription result.

    Checks two key patterns:
      1. wtf_cache:{filename}  — full WTF body (stored by this link)
      2. transcription:{filename} — simple {text, language, duration} (pre-populated)
    """
    # Check wtf_cache: first (full body, ready to use)
    try:
        cached = redis.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.debug(f"Cache lookup failed for {cache_key}: {e}")

    # Check transcription: prefix (simpler format, needs conversion)
    filename = _get_filename_from_dialog(dialog)
    if filename:
        try:
            cached = redis.get(f"{TRANSCRIPTION_PREFIX}{filename}")
            if cached:
                data = json.loads(cached)
                # Convert simple format to WTF body
                now = datetime.now(timezone.utc).isoformat()
                duration = float(data.get("duration", dialog.get("duration", 30.0)))
                return {
                    "transcript": {
                        "text": data.get("text", ""),
                        "language": data.get("language", "en-US"),
                        "duration": duration,
                        "confidence": 0.9,
                    },
                    "segments": [],
                    "metadata": {
                        "created_at": now,
                        "processed_at": now,
                        "provider": "vfun",
                        "model": "parakeet-tdt-110m",
                        "source": "redis_cache",
                    },
                    "quality": {
                        "average_confidence": 0.9,
                        "multiple_speakers": False,
                        "low_confidence_words": 0,
                    },
                }
        except Exception as e:
            logger.debug(f"Transcription cache lookup failed for {filename}: {e}")

    return None


def store_cached_transcription(cache_key: str, wtf_body: Dict[str, Any], ttl: int = 604800):
    """Store a WTF transcription result in Redis cache."""
    try:
        redis.setex(cache_key, ttl, json.dumps(wtf_body))
    except Exception as e:
        logger.debug(f"Cache store failed for {cache_key}: {e}")


def get_vfun_urls(opts: Dict[str, Any]) -> List[str]:
    """Get vfun server URLs ordered by health (healthy first, shuffled)."""
    urls = opts.get("vfun-server-urls")
    if urls and isinstance(urls, list) and len(urls) > 0:
        return _health_tracker.get_ordered_urls(urls)
    single = opts.get("vfun-server-url")
    return [single] if single else []


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
            # Read via the brick-direct bypass mount when available. The
            # gluster mount at /mnt/nas is currently performing terribly
            # (5s readdir, 14s for a 17KB read); the bypass NFSv3 goes
            # straight to the XFS brick and is orders of magnitude faster.
            # Falls back to the original path if the bypass copy is missing.
            import os as _os, errno, time as _time
            _BRICK_BASE = _os.environ.get("BRICK_BASE", "/mnt/slave_recording_bypass")
            _NAS_BASE = _os.environ.get("NAS_BASE", "/mnt/nas")
            read_path = filepath
            if filepath.startswith(_NAS_BASE + "/") and _os.path.isdir(_BRICK_BASE):
                candidate = _BRICK_BASE + filepath[len(_NAS_BASE):]
                if _os.path.lexists(candidate):
                    read_path = candidate
            for attempt in range(5):
                try:
                    with open(read_path, "rb") as f:
                        return f.read()
                except OSError as e:
                    last_exc = e
                    if e.errno in (errno.ESTALE, errno.ENOENT):
                        try:
                            _os.stat(_os.path.dirname(read_path) or ".")
                        except Exception:
                            pass
                        _time.sleep(0.05 * (1 << attempt))
                        continue
                    logger.error(f"Failed to read file {read_path}: {e}")
                    return None
            logger.error(
                f"Failed to read file {read_path} after retries: {last_exc}"
            )
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
    # vfun can return either:
    # 1. Direct response: {"type": "wtf_transcription", "body": {...}}
    # 2. Wrapped in analysis: {"analysis": [{"type": "wtf_transcription", "body": {...}}]}

    full_text = ""
    segments = []
    language = "en-US"

    # Check for direct response format first (vfun native format)
    if vfun_response.get("type") in ("transcription", "wtf_transcription"):
        body = vfun_response.get("body", {})
        if isinstance(body, dict):
            transcript = body.get("transcript", {})
            full_text = transcript.get("text", body.get("text", ""))
            language = transcript.get("language", body.get("language", "en-US"))
            segments = body.get("segments", [])
        elif isinstance(body, str):
            full_text = body
    else:
        # Try wrapped analysis format
        analysis_entries = vfun_response.get("analysis", [])
        for entry in analysis_entries:
            if entry.get("type") in ("transcription", "wtf_transcription"):
                body = entry.get("body", {})
                if isinstance(body, dict):
                    transcript = body.get("transcript", {})
                    full_text = transcript.get("text", body.get("text", ""))
                    language = transcript.get("language", body.get("language", "en-US"))
                    segments = body.get("segments", [])
                elif isinstance(body, str):
                    full_text = body
                break

    # If no text found, check for direct text field
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

    # Update fingerprint cache size from config
    fp_max = opts.get("fingerprint-cache-size", 1000)
    _fingerprint_cache._max_entries = fp_max

    # Check if any vfun URL is configured
    if not opts.get("vfun-server-url") and not opts.get("vfun-server-urls"):
        logger.error("wtf_transcribe: vfun-server-url or vfun-server-urls is required")
        return vcon_uuid

    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)

    if not vcon:
        logger.error(f"wtf_transcribe: vCon {vcon_uuid} not found")
        return vcon_uuid

    # Find dialogs to transcribe
    dialogs_processed = 0
    dialogs_skipped = 0
    cache_hits = 0
    cache_misses = 0
    cache_ttl = opts.get("cache-ttl", 604800)

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

        # Check fingerprint cache before calling vfun
        fp_hashes = compute_hashes(audio_content)
        if fp_hashes:
            cached_body = _fingerprint_cache.lookup(fp_hashes)
            if cached_body:
                vcon.add_analysis(
                    type="wtf_transcription",
                    dialog=i,
                    vendor="vfun",
                    body=cached_body,
                    extra={
                        "mediatype": "application/json",
                        "product": "parakeet-tdt-110m",
                        "schema": "wtf-1.0",
                    },
                )
                dialogs_processed += 1
                logger.info(f"Fingerprint HIT for dialog {i} (matches={cached_body.get('metadata',{}).get('fingerprint_matches',0)})")
                continue

        logger.info(f"Transcribing dialog {i} via vfun")

        # Try each vfun instance in health-priority order until one succeeds
        vfun_urls = get_vfun_urls(opts)
        if not vfun_urls:
            logger.error("wtf_transcribe: no vfun URLs available")
            dialogs_skipped += 1
            continue

        mimetype = dialog.get("mimetype", "audio/wav")
        headers = {}
        api_key = opts.get("api-key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        timeout = opts.get("timeout", 300)

        transcribed = False
        for attempt, vfun_server_url in enumerate(vfun_urls):
            try:
                files = {
                    "file-binary": ("audio", audio_content, mimetype),
                    "cachish": (None, "true")
                }
                response = requests.post(
                    vfun_server_url,
                    files=files,
                    headers=headers,
                    timeout=timeout,
                )

                if response.status_code in (200, 302):
                    _health_tracker.mark_healthy(vfun_server_url)
                    vfun_response = response.json()
                    if isinstance(vfun_response, str):
                        vfun_response = json.loads(vfun_response)

                    duration = dialog.get("duration", 30.0)
                    wtf_analysis = create_wtf_analysis(i, vfun_response, float(duration))

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

                    # Track fingerprint candidate; only store after seen multiple times
                    if fp_hashes:
                        fp_id = _fingerprint_cache.note_candidate(fp_hashes)
                        if _fingerprint_cache.should_store(fp_id):
                            _fingerprint_cache.store(fp_id, fp_hashes, wtf_analysis["body"])

                    dialogs_processed += 1
                    if attempt > 0:
                        logger.info(f"Added WTF transcription for dialog {i} (succeeded on attempt {attempt + 1})")
                    else:
                        logger.info(f"Added WTF transcription for dialog {i}")
                    transcribed = True
                    break  # success — stop trying other URLs

                else:
                    _health_tracker.mark_down(vfun_server_url)
                    logger.warning(
                        f"vfun {vfun_server_url} returned {response.status_code} for dialog {i}, "
                        f"trying next instance ({attempt + 1}/{len(vfun_urls)})"
                    )

            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                _health_tracker.mark_down(vfun_server_url)
                logger.warning(
                    f"vfun {vfun_server_url} unreachable for dialog {i}: {type(e).__name__}, "
                    f"trying next instance ({attempt + 1}/{len(vfun_urls)})"
                )
            except Exception as e:
                _health_tracker.mark_down(vfun_server_url)
                logger.error(
                    f"Unexpected error from vfun {vfun_server_url} for dialog {i}: {e}",
                    exc_info=True,
                )

        if not transcribed:
            logger.error(
                f"All {len(vfun_urls)} vfun instances failed for dialog {i} of vCon {vcon_uuid}"
            )

    if dialogs_processed > 0:
        vcon_redis.store_vcon(vcon)
        logger.info(
            f"Updated vCon {vcon_uuid}: processed={dialogs_processed}, "
            f"skipped={dialogs_skipped}"
        )
    else:
        logger.info(f"No dialogs transcribed for vCon {vcon_uuid}")

    return vcon_uuid
