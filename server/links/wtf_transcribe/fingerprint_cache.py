"""Audio fingerprint cache using Shazam-style spectral peak matching.

Generates spectrogram peaks from audio, creates hashes from peak pairs
(frequency1, frequency2, time_delta), and stores them in a local in-memory
dict per worker process.

Volume-invariant (uses peak frequencies, not amplitudes).
Offset-invariant (hashes encode relative timing between peaks).
Tolerant of slight speed variations (coarse frequency/time bins).
"""

import hashlib
import io
import json
import logging
import struct
import time
import wave
from typing import Optional, Dict, Any, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# --- Spectrogram / peak config ---
FFT_SIZE = 1024
HOP_SIZE = 512       # ~23ms hop at 22050Hz
SAMPLE_RATE = 22050  # downsample everything to this
FREQ_BINS = 40       # number of frequency bands for binning
MIN_PEAK_AMP = 10    # minimum amplitude (log scale) to be a peak
PEAK_NEIGHBORHOOD = 10  # local max window size in spectrogram

# --- Hash config ---
TARGET_ZONE_T = 20   # look ahead up to 20 frames for target peak (~460ms)
TARGET_ZONE_F = 10   # frequency bin range for target peak
MAX_PEAKS = 200      # max peaks per file to keep compute bounded
MIN_MATCH_HASHES = 5 # minimum matching hashes to consider a match
MIN_STORE_SEEN = 2   # must see a fingerprint this many times before storing


def _decode_wav(audio_bytes: bytes) -> Optional[np.ndarray]:
    """Decode wav bytes to mono float32 samples at SAMPLE_RATE."""
    try:
        buf = io.BytesIO(audio_bytes)
        with wave.open(buf, "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            sample_width = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        if sample_width == 1:
            samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128
            samples /= 128.0
        elif sample_width == 2:
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            return None

        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)

        if sample_rate != SAMPLE_RATE:
            duration = len(samples) / sample_rate
            target_len = int(duration * SAMPLE_RATE)
            if target_len < FFT_SIZE:
                return None
            indices = np.linspace(0, len(samples) - 1, target_len).astype(np.int64)
            samples = samples[indices]

        return samples
    except Exception as e:
        logger.debug(f"wav decode failed: {e}")
        return None


def _get_peaks(samples: np.ndarray) -> List[Tuple[int, int]]:
    """Extract spectrogram peaks as (time_frame, freq_bin) pairs."""
    from scipy.ndimage import maximum_filter

    n_frames = (len(samples) - FFT_SIZE) // HOP_SIZE + 1
    if n_frames < 2:
        return []

    window = np.hanning(FFT_SIZE)
    spec = np.zeros((FFT_SIZE // 2, n_frames))
    for i in range(n_frames):
        start = i * HOP_SIZE
        frame = samples[start:start + FFT_SIZE] * window
        fft = np.abs(np.fft.rfft(frame))[:-1]
        spec[:, i] = fft

    spec = np.log1p(spec * 100)

    neighborhood = maximum_filter(spec, size=PEAK_NEIGHBORHOOD)
    peaks = (spec == neighborhood) & (spec > MIN_PEAK_AMP)

    freq_indices, time_indices = np.where(peaks)
    n_freqs = spec.shape[0]
    bin_size = max(1, n_freqs // FREQ_BINS)
    freq_binned = freq_indices // bin_size

    amplitudes = spec[freq_indices, time_indices]
    order = np.argsort(-amplitudes)[:MAX_PEAKS]

    return [(int(time_indices[i]), int(freq_binned[i])) for i in order]


def _make_hashes(peaks: List[Tuple[int, int]]) -> List[Tuple[str, int]]:
    """Generate (hash, anchor_time) pairs from peak constellation."""
    peaks = sorted(peaks, key=lambda p: p[0])
    hashes = []

    for i, (t1, f1) in enumerate(peaks):
        for j in range(i + 1, len(peaks)):
            t2, f2 = peaks[j]
            dt = t2 - t1
            if dt > TARGET_ZONE_T:
                break
            if abs(f2 - f1) > TARGET_ZONE_F:
                continue
            dt_q = dt // 2
            h = f"{f1}:{f2}:{dt_q}"
            hashes.append((h, t1))

    return hashes


def compute_hashes(audio_bytes: bytes) -> Optional[List[Tuple[str, int]]]:
    """Compute spectral peak hashes from wav audio bytes."""
    samples = _decode_wav(audio_bytes)
    if samples is None or len(samples) < FFT_SIZE:
        return None

    peaks = _get_peaks(samples)
    if len(peaks) < 3:
        return None

    hashes = _make_hashes(peaks)
    return hashes if hashes else None


class FingerprintCache:
    """In-memory per-worker fingerprint cache.

    Stores hash → fingerprint_id mappings and fingerprint_id → metadata.
    Only promotes a fingerprint to "stored" after seeing it MIN_STORE_SEEN times,
    preventing the cache from filling with one-off unique audio.
    """

    def __init__(self, max_entries: int = 1000):
        self._max_entries = max_entries
        # hash_str → fp_id
        self._hash_to_id: Dict[str, str] = {}
        # fp_id → {"wtf_body": ..., "count": int, "last_seen": float}
        self._entries: Dict[str, Dict[str, Any]] = {}
        # Candidates: fp_id → seen_count (not yet promoted to stored)
        self._candidates: Dict[str, int] = {}
        # fp_id → list of (hash, offset) for eviction cleanup
        self._id_hashes: Dict[str, List[str]] = {}

    def lookup(self, hashes: List[Tuple[str, int]]) -> Optional[Dict[str, Any]]:
        """Check if hashes match a stored fingerprint."""
        if not hashes:
            return None

        matches: Dict[str, int] = {}
        for h, _ in hashes:
            fp_id = self._hash_to_id.get(h)
            if fp_id:
                matches[fp_id] = matches.get(fp_id, 0) + 1

        if not matches:
            return None

        best_id, best_count = max(matches.items(), key=lambda x: x[1])
        if best_count < MIN_MATCH_HASHES:
            return None

        entry = self._entries.get(best_id)
        if not entry:
            return None

        entry["count"] += 1
        entry["last_seen"] = time.time()

        # Deep copy the body and add fingerprint metadata
        body = json.loads(json.dumps(entry["wtf_body"]))
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        if "metadata" not in body:
            body["metadata"] = {}
        body["metadata"]["processed_at"] = now
        body["metadata"]["fingerprinted"] = True
        body["metadata"]["fingerprint_matches"] = best_count
        body["metadata"]["fingerprint_id"] = best_id
        body["metadata"]["fingerprint_total_hits"] = entry["count"]

        return body

    def note_candidate(self, hashes: List[Tuple[str, int]]) -> str:
        """Note that we've seen these hashes. Returns fp_id.
        Call this BEFORE store() to track how many times we've seen it."""
        fp_id = hashlib.sha256(
            ":".join(h for h, _ in hashes[:20]).encode()
        ).hexdigest()[:16]
        self._candidates[fp_id] = self._candidates.get(fp_id, 0) + 1
        return fp_id

    def should_store(self, fp_id: str) -> bool:
        """Returns True if this candidate has been seen enough times to store."""
        return self._candidates.get(fp_id, 0) >= MIN_STORE_SEEN

    def store(self, fp_id: str, hashes: List[Tuple[str, int]], wtf_body: Dict[str, Any]) -> None:
        """Store a fingerprint after it's been seen enough times."""
        if fp_id in self._entries:
            self._entries[fp_id]["count"] += 1
            self._entries[fp_id]["last_seen"] = time.time()
            return

        if len(self._entries) >= self._max_entries:
            self._evict()

        self._entries[fp_id] = {
            "wtf_body": wtf_body,
            "count": self._candidates.get(fp_id, 1),
            "last_seen": time.time(),
        }

        hash_keys = []
        for h, _ in hashes:
            self._hash_to_id[h] = fp_id
            hash_keys.append(h)
        self._id_hashes[fp_id] = hash_keys

    def _evict(self) -> None:
        """Evict lowest-value entries: lowest count first, then oldest."""
        entries = [(fp_id, e["count"], e["last_seen"])
                   for fp_id, e in self._entries.items()]
        entries.sort(key=lambda x: (x[1], x[2]))

        to_evict = max(1, len(entries) // 10)
        for fp_id, _, _ in entries[:to_evict]:
            # Remove hash mappings
            for h in self._id_hashes.get(fp_id, []):
                self._hash_to_id.pop(h, None)
            self._id_hashes.pop(fp_id, None)
            self._entries.pop(fp_id, None)
            self._candidates.pop(fp_id, None)

    @property
    def size(self) -> int:
        return len(self._entries)
