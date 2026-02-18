#!/usr/bin/env python3
"""Find the specific file that crashes vfun"""

import os
import sys
import time
import requests
from pathlib import Path

VFUN_URL = "http://localhost:4380/wtf"

def test_file(filepath):
    """Test a single file, return True if successful"""
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(
                VFUN_URL,
                files={"file-binary": ("audio.wav", f, "audio/wav")},
                timeout=60
            )
        return response.status_code == 200
    except Exception as e:
        return False

def is_vfun_alive():
    """Check if vfun is responding"""
    try:
        r = requests.get("http://localhost:4380/ready", timeout=5)
        return r.status_code == 200
    except:
        return False

def main():
    # Get files from hour 11
    base_dir = Path("/mnt/nas/Freeswitch1/2026-01-19/11")
    files = sorted(base_dir.glob("*.wav"))[:2000]  # First 2000 files

    print(f"Testing {len(files)} files to find crash point...")
    print("")

    last_good = None
    for i, filepath in enumerate(files):
        if not is_vfun_alive():
            print(f"\n!!! vfun CRASHED after file #{i}")
            print(f"Last good file: {last_good}")
            print(f"Crash likely caused by: {filepath}")
            print(f"Previous file: {files[i-1] if i > 0 else 'N/A'}")
            return

        success = test_file(filepath)
        if success:
            last_good = filepath
            if i % 100 == 0:
                print(f"Progress: {i}/{len(files)} - OK")
        else:
            if not is_vfun_alive():
                print(f"\n!!! vfun CRASHED processing file #{i}")
                print(f"Crash file: {filepath}")
                return
            else:
                print(f"File #{i} failed but vfun still alive: {filepath}")

    print(f"\nAll {len(files)} files processed successfully!")

if __name__ == "__main__":
    main()
