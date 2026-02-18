#!/usr/bin/env python3
"""High-concurrency stress test for vfun using NAS audio files"""

import time
import requests
import concurrent.futures
import statistics
import os
from pathlib import Path
from datetime import datetime
import random

VFUN_URL = "http://localhost:4380"
NAS_PATH = "/mnt/nas/Freeswitch1/2026-01-19/06"

def find_nas_wav_files(max_files=500):
    """Find wav files in NAS directory"""
    nas_dir = Path(NAS_PATH)
    if not nas_dir.exists():
        print(f"ERROR: NAS path not found: {NAS_PATH}")
        return []

    wav_files = list(nas_dir.glob("*.wav"))[:max_files]
    return wav_files

def single_request(audio_file):
    """Make a single transcription request"""
    start = time.time()
    try:
        with open(audio_file, 'rb') as f:
            files = {'file-binary': (audio_file.name, f, 'audio/wav')}
            resp = requests.post(f"{VFUN_URL}/wtf", files=files, timeout=120)
        elapsed = time.time() - start
        if resp.status_code == 200:
            result = resp.json()
            text = result.get('text', '')
            return (True, elapsed, len(text), audio_file.stat().st_size)
        return (False, elapsed, 0, audio_file.stat().st_size)
    except Exception as e:
        elapsed = time.time() - start
        return (False, elapsed, 0, 0)

def run_stress_test(num_files=100, concurrent_workers=32):
    """Run stress test with high concurrency"""
    print(f"\n{'='*70}")
    print(f"VFUN NAS STRESS TEST - {num_files} files, {concurrent_workers} concurrent workers")
    print(f"Source: {NAS_PATH}")
    print(f"{'='*70}")

    # Health check
    try:
        resp = requests.get(f"{VFUN_URL}/ready", timeout=5)
        print(f"Server status: {resp.json()}")
    except Exception as e:
        print(f"Server not ready: {e}")
        return

    # Find audio files
    all_files = find_nas_wav_files(max_files=num_files * 2)
    print(f"Found {len(all_files)} wav files on NAS")

    if len(all_files) == 0:
        print("ERROR: No audio files found!")
        return

    if len(all_files) < num_files:
        # Repeat files if needed
        test_files = all_files * ((num_files // len(all_files)) + 1)
    else:
        test_files = all_files

    # Shuffle and select
    random.shuffle(test_files)
    test_files = test_files[:num_files]

    total_size = sum(f.stat().st_size for f in test_files)
    print(f"Testing with {len(test_files)} files ({total_size / (1024*1024):.2f} MB)")
    print(f"Concurrent workers: {concurrent_workers}")
    print(f"\nStarting at: {datetime.now().isoformat()}")
    print("-" * 70)

    times = []
    successes = 0
    errors = 0
    total_text = 0
    total_bytes = 0

    start_total = time.time()
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_workers) as executor:
        futures = {executor.submit(single_request, f): f for f in test_files}

        for future in concurrent.futures.as_completed(futures):
            success, elapsed, text_len, file_size = future.result()
            times.append(elapsed)
            total_bytes += file_size
            completed += 1

            if success:
                successes += 1
                total_text += text_len
            else:
                errors += 1

            # Progress update every 10 files
            if completed % 10 == 0:
                elapsed_total = time.time() - start_total
                rate = completed / elapsed_total if elapsed_total > 0 else 0
                print(f"  Progress: {completed}/{num_files} ({rate:.1f} files/sec, {successes} ok, {errors} err)")

    total_time = time.time() - start_total

    print("-" * 70)
    print(f"Finished at: {datetime.now().isoformat()}")
    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}")
    print(f"  Files processed:   {len(test_files)}")
    print(f"  Success rate:      {successes}/{len(test_files)} ({100*successes/len(test_files):.1f}%)")
    print(f"  Errors:            {errors}")
    print(f"  Total data:        {total_bytes / (1024*1024):.2f} MB")
    print(f"  Total text:        {total_text} chars")
    print()
    print(f"  Total time:        {total_time:.2f}s")
    print(f"  Throughput:        {len(test_files)/total_time:.2f} files/sec")
    print(f"  Data rate:         {total_bytes / (1024*1024) / total_time:.2f} MB/sec")
    print()
    if times:
        print(f"  Min latency:       {min(times):.3f}s")
        print(f"  Max latency:       {max(times):.3f}s")
        print(f"  Avg latency:       {statistics.mean(times):.3f}s")
        print(f"  P50 latency:       {statistics.median(times):.3f}s")
        print(f"  P95 latency:       {sorted(times)[int(len(times)*0.95)]:.3f}s")
        print(f"  P99 latency:       {sorted(times)[int(len(times)*0.99)]:.3f}s")
        if len(times) > 1:
            print(f"  Std dev:           {statistics.stdev(times):.3f}s")
    print(f"{'='*70}")

    # Estimate batching efficiency
    avg_latency = statistics.mean(times) if times else 0
    theoretical_serial = avg_latency * len(test_files)
    actual_parallel = total_time
    parallelism = theoretical_serial / actual_parallel if actual_parallel > 0 else 0
    print(f"\nBATCHING ANALYSIS:")
    print(f"  Effective parallelism: {parallelism:.1f}x")
    print(f"  (If batching works well, this should be > {concurrent_workers}x)")
    print(f"  Theoretical serial time: {theoretical_serial:.1f}s")
    print(f"  Actual parallel time:    {actual_parallel:.1f}s")

if __name__ == "__main__":
    import sys
    num_files = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    run_stress_test(num_files=num_files, concurrent_workers=workers)
