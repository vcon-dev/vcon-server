#!/usr/bin/env python3
"""
Production NAS Transcription Pipeline

High-throughput transcription pipeline for processing phone call recordings
from NAS storage using the vfun transcription server.

Performance characteristics (single vfun instance):
- Throughput: ~2,500 files/minute
- Latency: ~0.4s per file
- Capacity: ~3.5M files/day per vfun instance

Usage:
    # Process specific date/hour (transcription only)
    python3 nas_transcription_pipeline.py --date 2026-01-19 --hour 06 --limit 100

    # Process and store vCons in vcon-server
    python3 nas_transcription_pipeline.py --date 2026-01-19 --store-vcons

    # Process all files from a date
    python3 nas_transcription_pipeline.py --date 2026-01-19 --workers 16

    # Dry run to see file counts
    python3 nas_transcription_pipeline.py --date 2026-01-19 --dry-run

    # Save results to JSON
    python3 nas_transcription_pipeline.py --date 2026-01-19 --output results.json
"""

import os
import sys
import time
import json
import uuid
import queue
import threading
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any
import requests

# ============================================================================
# Configuration
# ============================================================================

# vfun transcription servers
VFUN_URLS = [
    "http://localhost:4380/wtf",
    # "http://localhost:4381/wtf",  # Multiple instances hurt performance on single GPU
    # "http://localhost:4382/wtf",
    # "http://localhost:4383/wtf",
]

# vcon-server API
VCON_API_URL = "http://localhost:8080/vcon"
VCON_INGRESS_LIST = "default"  # Ingress list for processed vCons

# NAS configuration
NAS_BASE = "/mnt/nas"
FREESWITCH_SERVERS = list(range(1, 21))  # Freeswitch1 through Freeswitch20

# Performance tuning
DEFAULT_WORKERS = 12         # Concurrent transcription workers
REQUEST_TIMEOUT = 300        # Transcription timeout (seconds)
MAX_RETRIES = 3              # Retries for NFS errors
RETRY_DELAY = 0.1            # Base delay between retries (seconds)
VCON_STORE_TIMEOUT = 30      # Timeout for storing vCons

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TranscriptionResult:
    filepath: str
    success: bool
    duration: float
    text: str = ""
    text_length: int = 0
    error: Optional[str] = None
    language: Optional[str] = None
    vcon_uuid: Optional[str] = None
    vcon_stored: bool = False

    def to_dict(self) -> Dict:
        return {
            "filepath": self.filepath,
            "filename": Path(self.filepath).name,
            "success": self.success,
            "duration": round(self.duration, 3),
            "text_length": self.text_length,
            "language": self.language,
            "error": self.error,
            "vcon_uuid": self.vcon_uuid,
            "vcon_stored": self.vcon_stored,
        }


@dataclass
class FileMetadata:
    """Metadata parsed from NAS filename."""
    campaign_id: str
    caller_number: str
    call_id: str
    call_date: str
    call_time: str
    freeswitch_server: str

    @classmethod
    def from_filepath(cls, filepath: str) -> Optional['FileMetadata']:
        """Parse metadata from NAS file path.

        Expected format: /mnt/nas/Freeswitch{N}/{date}/{hour}/{campaign}_{caller}_{callid}_{date}_{time}.wav
        Example: /mnt/nas/Freeswitch1/2026-01-19/06/6075_18557533609_993315706043435_2026-01-19_06:05:02.wav
        """
        try:
            path = Path(filepath)
            filename = path.stem  # Without .wav

            # Parse Freeswitch server from path
            parts = path.parts
            fs_server = None
            for part in parts:
                if part.startswith("Freeswitch"):
                    fs_server = part
                    break

            # Parse filename: campaign_caller_callid_date_time
            # Example: 6075_18557533609_993315706043435_2026-01-19_06:05:02
            segments = filename.split('_')
            if len(segments) >= 5:
                campaign_id = segments[0]
                caller_number = segments[1]
                call_id = segments[2]
                call_date = segments[3]
                call_time = segments[4].replace(':', '-')  # Normalize time format

                return cls(
                    campaign_id=campaign_id,
                    caller_number=caller_number,
                    call_id=call_id,
                    call_date=call_date,
                    call_time=call_time,
                    freeswitch_server=fs_server or "unknown"
                )
        except Exception as e:
            logger.debug(f"Failed to parse metadata from {filepath}: {e}")

        return None


@dataclass
class PipelineStats:
    """Pipeline execution statistics."""
    start_time: float
    processed: int = 0
    successful: int = 0
    failed: int = 0
    total_transcription_time: float = 0.0
    total_text_chars: int = 0
    vcons_created: int = 0
    vcons_stored: int = 0

    def record(self, result: TranscriptionResult):
        self.processed += 1
        self.total_transcription_time += result.duration
        if result.success:
            self.successful += 1
            self.total_text_chars += result.text_length
            if result.vcon_uuid:
                self.vcons_created += 1
            if result.vcon_stored:
                self.vcons_stored += 1
        else:
            self.failed += 1

    def to_dict(self) -> Dict:
        elapsed = time.time() - self.start_time
        return {
            "processed": self.processed,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": round(self.successful / self.processed * 100, 1) if self.processed > 0 else 0,
            "elapsed_seconds": round(elapsed, 1),
            "throughput_per_min": round(self.processed / elapsed * 60, 1) if elapsed > 0 else 0,
            "avg_latency": round(self.total_transcription_time / self.processed, 3) if self.processed > 0 else 0,
            "total_text_chars": self.total_text_chars,
            "vcons_created": self.vcons_created,
            "vcons_stored": self.vcons_stored,
        }


# ============================================================================
# vCon Creation
# ============================================================================

def create_vcon(
    filepath: str,
    metadata: Optional[FileMetadata],
    transcription_text: str,
    language: str,
    audio_duration: float = 60.0
) -> Dict[str, Any]:
    """Create a vCon document from transcription result.

    Args:
        filepath: Path to the audio file
        metadata: Parsed file metadata
        transcription_text: The transcribed text
        language: Detected language code
        audio_duration: Duration of audio in seconds

    Returns:
        vCon dictionary ready for submission to vcon-server
    """
    vcon_uuid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Build parties from metadata
    parties = []
    if metadata:
        # Caller party
        caller_tel = metadata.caller_number
        if not caller_tel.startswith('+'):
            caller_tel = f"+1{caller_tel}" if len(caller_tel) == 10 else f"+{caller_tel}"
        parties.append({
            "tel": caller_tel,
            "name": "Caller",
            "meta": {"role": "customer"}
        })
        # Agent party (placeholder)
        parties.append({
            "tel": "+10000000000",
            "name": "Agent",
            "meta": {"role": "agent"}
        })
    else:
        parties = [
            {"tel": "+10000000001", "name": "Party 1"},
            {"tel": "+10000000002", "name": "Party 2"}
        ]

    # Build dialog with file:// URL reference (no embedding)
    dialog_start = now
    if metadata:
        try:
            # call_time is stored as HH-MM-SS, convert to HH:MM:SSZ
            dialog_start = f"{metadata.call_date}T{metadata.call_time.replace('-', ':')}Z"
        except:
            pass

    dialog = [{
        "type": "recording",
        "start": dialog_start,
        "parties": [0, 1],
        "duration": audio_duration,
        "mimetype": "audio/wav",
        "url": f"file://{filepath}",  # Reference file instead of embedding
    }]

    # Build WTF transcription analysis
    analysis_body = {
        "transcript": {
            "text": transcription_text,
            "language": language,
            "duration": audio_duration,
            "confidence": 0.9,
        },
        "segments": [],
        "metadata": {
            "created_at": now,
            "processed_at": now,
            "provider": "vfun",
            "model": "parakeet-tdt-110m",
            "audio": {"duration": audio_duration},
        },
        "quality": {
            "average_confidence": 0.9,
            "multiple_speakers": True,
            "low_confidence_words": 0,
        }
    }
    analysis = [{
        "type": "wtf_transcription",
        "dialog": 0,
        "vendor": "vfun",
        "product": "parakeet-tdt-110m",
        "schema": "wtf-1.0",
        "encoding": "json",
        "body": json.dumps(analysis_body),
    }]

    # Build attachments with source metadata
    attachments = []
    if metadata:
        attachment_body = {
            "freeswitch_server": metadata.freeswitch_server,
            "campaign_id": metadata.campaign_id,
            "call_id": metadata.call_id,
            "source_file": filepath,
        }
        attachments.append({
            "type": "source_metadata",
            "encoding": "json",
            "body": json.dumps(attachment_body),
        })

    return {
        "vcon": "0.0.1",
        "uuid": vcon_uuid,
        "created_at": now,
        "parties": parties,
        "dialog": dialog,
        "analysis": analysis,
        "attachments": attachments,
        "group": [],
        "redacted": {},
    }


def store_vcon(vcon: Dict[str, Any], ingress_list: Optional[str] = None) -> bool:
    """Store a vCon in vcon-server.

    Args:
        vcon: The vCon document to store
        ingress_list: Optional ingress list to add the vCon to

    Returns:
        True if stored successfully, False otherwise
    """
    try:
        params = {}
        if ingress_list:
            params["ingress_lists"] = [ingress_list]

        response = requests.post(
            VCON_API_URL,
            params=params,
            json=vcon,
            timeout=VCON_STORE_TIMEOUT
        )

        if response.status_code == 201:
            return True
        else:
            logger.warning(f"Failed to store vCon {vcon['uuid']}: {response.status_code} {response.text[:100]}")
            return False

    except Exception as e:
        logger.warning(f"Error storing vCon {vcon['uuid']}: {e}")
        return False


# ============================================================================
# Load Balancer
# ============================================================================

class VfunLoadBalancer:
    """Thread-safe round-robin load balancer for vfun instances."""

    def __init__(self, urls: List[str]):
        self.urls = urls
        self.index = 0
        self.lock = threading.Lock()
        self._check_health()

    def _check_health(self):
        """Check which vfun instances are healthy."""
        healthy = []
        for url in self.urls:
            try:
                ready_url = url.replace("/wtf", "/ready")
                resp = requests.get(ready_url, timeout=5)
                if resp.status_code == 200:
                    healthy.append(url)
                    logger.info(f"vfun healthy: {url}")
                else:
                    logger.warning(f"vfun unhealthy: {url} (status {resp.status_code})")
            except Exception as e:
                logger.warning(f"vfun unavailable: {url} ({e})")

        if not healthy:
            raise RuntimeError("No healthy vfun instances available!")

        self.urls = healthy

    def get_url(self) -> str:
        with self.lock:
            url = self.urls[self.index % len(self.urls)]
            self.index += 1
            return url


# ============================================================================
# Transcription
# ============================================================================

def transcribe_file(
    filepath: str,
    vfun_lb: VfunLoadBalancer,
    store_vcons: bool = False,
    ingress_list: Optional[str] = None
) -> TranscriptionResult:
    """Transcribe a single audio file with retry logic for NFS errors.

    Args:
        filepath: Path to the audio file
        vfun_lb: Load balancer for vfun instances
        store_vcons: Whether to create and store a vCon
        ingress_list: Optional ingress list for the vCon

    Returns:
        TranscriptionResult with transcription and optional vCon info
    """
    start = time.time()
    last_error = None
    audio_data = None
    file_size = 0

    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                time.sleep(RETRY_DELAY * attempt)

            with open(filepath, 'rb') as f:
                audio_data = f.read()
                file_size = len(audio_data)

            url = vfun_lb.get_url()
            response = requests.post(
                url,
                files={"file-binary": ("audio.wav", audio_data, "audio/wav")},
                timeout=REQUEST_TIMEOUT
            )

            duration = time.time() - start

            if response.status_code == 200:
                data = response.json()
                text = data.get("text", "")
                language = data.get("language", "en")

                result = TranscriptionResult(
                    filepath=filepath,
                    success=True,
                    duration=duration,
                    text=text,
                    text_length=len(text),
                    language=language
                )

                # Create and store vCon if requested
                if store_vcons and text:
                    # Estimate audio duration from file size (8kHz 16-bit mono)
                    audio_duration = file_size / 16000.0 if file_size > 0 else 60.0

                    metadata = FileMetadata.from_filepath(filepath)
                    vcon = create_vcon(
                        filepath=filepath,
                        metadata=metadata,
                        transcription_text=text,
                        language=language,
                        audio_duration=audio_duration
                    )
                    result.vcon_uuid = vcon["uuid"]

                    if store_vcon(vcon, ingress_list):
                        result.vcon_stored = True

                return result
            else:
                last_error = f"HTTP {response.status_code}: {response.text[:100]}"

        except OSError as e:
            last_error = str(e)
            continue
        except requests.exceptions.Timeout:
            last_error = "Request timeout"
            continue
        except Exception as e:
            last_error = str(e)
            break

    return TranscriptionResult(
        filepath=filepath,
        success=False,
        duration=time.time() - start,
        error=last_error
    )


# ============================================================================
# File Discovery
# ============================================================================

def find_audio_files(
    base_path: str,
    date: Optional[str] = None,
    hour: Optional[str] = None,
    servers: Optional[List[int]] = None,
    limit: Optional[int] = None
) -> List[str]:
    """Find audio files in the NAS Freeswitch structure."""
    files = []
    servers = servers or FREESWITCH_SERVERS

    for server_num in servers:
        server_path = Path(base_path) / f"Freeswitch{server_num}"
        if not server_path.exists():
            continue

        if date and hour:
            search_path = server_path / date / hour
            if search_path.exists():
                for f in search_path.iterdir():
                    if f.suffix == '.wav':
                        files.append(str(f))
                        if limit and len(files) >= limit:
                            return files
        elif date:
            date_path = server_path / date
            if date_path.exists():
                for hour_dir in date_path.iterdir():
                    if hour_dir.is_dir():
                        try:
                            for f in hour_dir.iterdir():
                                if f.suffix == '.wav':
                                    files.append(str(f))
                                    if limit and len(files) >= limit:
                                        return files
                        except PermissionError:
                            logger.warning(f"Permission denied: {hour_dir}")
                            continue
        else:
            for f in server_path.rglob("*.wav"):
                files.append(str(f))
                if limit and len(files) >= limit:
                    return files

    return files


# ============================================================================
# Pipeline Execution
# ============================================================================

def run_pipeline(
    files: List[str],
    workers: int,
    vfun_lb: VfunLoadBalancer,
    verbose: bool = False,
    store_vcons: bool = False,
    ingress_list: Optional[str] = None
) -> tuple[List[TranscriptionResult], PipelineStats]:
    """Execute the transcription pipeline.

    Args:
        files: List of audio file paths to process
        workers: Number of concurrent workers
        vfun_lb: Load balancer for vfun instances
        verbose: Whether to print detailed output
        store_vcons: Whether to create and store vCons
        ingress_list: Optional ingress list for vCons

    Returns:
        Tuple of (results list, stats)
    """
    stats = PipelineStats(start_time=time.time())
    results = []
    lock = threading.Lock()

    def process_and_record(filepath):
        result = transcribe_file(filepath, vfun_lb, store_vcons, ingress_list)
        with lock:
            stats.record(result)
            results.append(result)

            if verbose:
                status = "✓" if result.success else "✗"
                filename = Path(filepath).name[:50]
                print(f"  {status} {filename}: {result.duration:.2f}s", end="")
                if result.success:
                    extra = f" ({result.text_length} chars, {result.language})"
                    if result.vcon_stored:
                        extra += f" [vCon: {result.vcon_uuid[:8]}...]"
                    print(extra)
                else:
                    print(f" ERROR: {result.error}")
            else:
                if result.vcon_stored:
                    sys.stdout.write("V")  # V for vCon stored
                elif result.success:
                    sys.stdout.write(".")
                else:
                    sys.stdout.write("X")
                sys.stdout.flush()

        return result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_and_record, f) for f in files]
        for future in as_completed(futures):
            future.result()  # Raise any exceptions

    if not verbose:
        print()

    return results, stats


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Production NAS transcription pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--date", help="Process specific date (YYYY-MM-DD)")
    parser.add_argument("--hour", help="Process specific hour (00-23)")
    parser.add_argument("--server", type=int, action="append",
                       help="Specific Freeswitch server number (can repeat)")
    parser.add_argument("--limit", type=int, help="Limit files to process")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS,
                       help=f"Concurrent workers (default: {DEFAULT_WORKERS})")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    parser.add_argument("--dry-run", action="store_true",
                       help="Find files but don't process")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    parser.add_argument("--store-vcons", action="store_true",
                       help="Create and store vCons in vcon-server")
    parser.add_argument("--ingress-list", default=VCON_INGRESS_LIST,
                       help=f"Ingress list for vCons (default: {VCON_INGRESS_LIST})")
    args = parser.parse_args()

    # Header
    print("=" * 70)
    print("NAS TRANSCRIPTION PIPELINE")
    print("=" * 70)

    # Initialize vfun load balancer
    try:
        vfun_lb = VfunLoadBalancer(VFUN_URLS)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print(f"vfun instances: {len(vfun_lb.urls)}")
    print(f"Workers: {args.workers}")
    print(f"Filters: date={args.date or 'all'}, hour={args.hour or 'all'}")
    if args.limit:
        print(f"Limit: {args.limit} files")
    if args.store_vcons:
        print(f"vCon storage: ENABLED (ingress: {args.ingress_list})")
    print()

    # Find files
    logger.info("Scanning NAS for audio files...")
    files = find_audio_files(
        NAS_BASE,
        date=args.date,
        hour=args.hour,
        servers=args.server,
        limit=args.limit
    )
    print(f"Found {len(files):,} audio files")

    if not files:
        print("No files found!")
        sys.exit(0)

    if args.dry_run:
        print("\nDry run - sample files:")
        for f in files[:10]:
            print(f"  {f}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10:,} more")
        sys.exit(0)

    # Run pipeline
    print(f"\nProcessing {len(files):,} files...")
    if args.store_vcons:
        print("Legend: V=vCon stored, .=transcribed, X=failed")
    print("-" * 70)

    results, stats = run_pipeline(
        files,
        args.workers,
        vfun_lb,
        verbose=args.verbose,
        store_vcons=args.store_vcons,
        ingress_list=args.ingress_list if args.store_vcons else None
    )

    # Summary
    summary = stats.to_dict()
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"Processed:    {summary['processed']:,} files")
    print(f"Successful:   {summary['successful']:,} ({summary['success_rate']}%)")
    print(f"Failed:       {summary['failed']:,}")
    print(f"Elapsed:      {summary['elapsed_seconds']}s")
    print(f"Throughput:   {summary['throughput_per_min']:,.0f} files/min")
    print(f"Avg latency:  {summary['avg_latency']}s per file")
    print(f"Total text:   {summary['total_text_chars']:,} characters")
    if args.store_vcons:
        print(f"vCons created: {summary['vcons_created']:,}")
        print(f"vCons stored:  {summary['vcons_stored']:,}")

    # Errors
    errors = [r for r in results if not r.success]
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors[:5]:
            print(f"  {Path(e.filepath).name}: {e.error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more")

    # Save results
    if args.output:
        output_data = {
            "stats": summary,
            "config": {
                "date": args.date,
                "hour": args.hour,
                "workers": args.workers,
                "vfun_instances": len(vfun_lb.urls),
            },
            "results": [r.to_dict() for r in results],
        }
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()
