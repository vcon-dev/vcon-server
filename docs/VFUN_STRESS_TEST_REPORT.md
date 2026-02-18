# vfun Stress Test Report

**Date:** 2026-02-04 (Updated)
**Tester:** Thomas (with Claude Code)
**vfun Version:** Commit 0431d2d "hackery to avoid crash"
**Environment:** Ubuntu Linux, NVIDIA H100 NVL (95GB VRAM)

---

## Executive Summary

### Update (2026-02-04): Significant Improvement After Fix

Commit `0431d2d` ("hackery to avoid crash") dramatically improved stability:

| Test | Before Fix (97a9d1c) | After Fix (0431d2d) |
|------|---------------------|---------------------|
| 64 workers / 1,000 files | 30.6% (crashed ~306) | **100%** |
| 64 workers / 5,000 files | N/A | **100%** |
| 64 workers / 43,940 files | N/A | **100%** |
| 64 workers / 406,037 files | N/A | 22.3% (crashed ~90k) |

**Key finding:** The fix extended crash threshold from ~300-7000 files to ~90,000 files - a 10-100x improvement. However, crashes still occur on very long runs (400k+ files).

**Recommendation:** Use auto-restart wrapper for production runs exceeding 50k files.

---

## Post-Fix Test Results (2026-02-04)

### Test 1: 64 workers, 1,000 files
```
Processed:    1,000 files
Successful:   1,000 (100.0%)
Failed:       0
Throughput:   992 files/min
```

### Test 2: 64 workers, 5,000 files
```
Processed:    5,000 files
Successful:   5,000 (100.0%)
Failed:       0
Throughput:   2,711 files/min
```

### Test 3: 64 workers, 43,940 files (1 hour of data)
```
Processed:    43,940 files
Successful:   43,940 (100.0%)
Failed:       0
Elapsed:      1480.6s (~25 min)
Throughput:   1,781 files/min
```

### Test 4: 64 workers, 406,037 files (full day)
```
Processed:    406,037 files
Successful:   90,629 (22.3%)
Failed:       315,408
Elapsed:      30632.1s (~8.5 hours)
```
**Note:** vfun crashed after ~90k files. Remaining failures are connection refused errors after crash.

### Conclusion

The fix (`0431d2d`) significantly improved stability:
- **Before:** Crashed after 300-7,000 files depending on concurrency
- **After:** Stable for 44k files, crashes around 90k files

For production workloads >50k files, use `scripts/run_pipeline_with_restart.sh` which automatically restarts vfun on crash.

---

## Original Report (2026-02-03)

vfun crashes after processing a cumulative number of files regardless of worker/concurrency settings. The crash point scales inversely with concurrency - more workers = faster crash. This indicates **accumulated memory corruption** rather than an immediate concurrency issue.

The original fix (commit 97a9d1c - non-blocking CUDA streams and pinned memory) did not resolve the underlying issue.

---

## Test Results

| Workers | Files Tested | Success Rate | Files Before Crash | Crash Type |
|---------|-------------|--------------|-------------------|------------|
| 64 | 1,000 | 30.6% | ~306 | "corrupted double-linked list" |
| 32 | 1,000 | 13.0% | ~130 | Connection refused (process died) |
| 24 | 1,000 | 100% | - | No crash |
| 24 | 5,000 | 62.7% | ~3,134 | Connection refused |
| 16 | 1,000 | 100% | - | No crash |
| 16 | 5,000 | 100% | - | No crash |
| 16 | 43,940 | ~45% | ~6,923 | Connection refused |

### Key Observations

1. **Short tests pass**: 1000-file tests with 16-24 workers complete successfully
2. **Longer tests crash**: Extended runs eventually crash regardless of concurrency
3. **Crash threshold scales with concurrency**:
   - 64 workers: crashes after ~300 files
   - 16 workers: crashes after ~7000 files
   - Suggests ~300 * workers ≈ crash threshold (rough approximation)

4. **Performance when stable**:
   - 16 workers: 920 files/min, 1.0s avg latency
   - 24 workers: 179 files/min, 7.4s avg latency (slower due to saturation?)

---

## Crash Analysis

### Error Messages Observed

1. **"corrupted double-linked list"** (glibc heap corruption)
   - Observed with 64 workers
   - Indicates memory corruption in heap management

2. **Silent death** (no error logged)
   - Process dies, port becomes unavailable
   - `/ready` endpoint stops responding
   - No CUDA error or stack trace in logs

3. **Previous crash type** (from earlier testing):
   - `CUBLAS_STATUS_EXECUTION_FAILED` during `cublasLtMatmul`
   - Occurred in transformer decoder's forward pass

### Root Cause Hypothesis

The crash is NOT caused by:
- Immediate concurrency issues (16 workers is stable for 5000 files)
- Single problematic files (same files work individually)
- GPU memory exhaustion (VRAM stable at ~12.6GB)

The crash IS likely caused by:
- **Accumulated memory corruption** that builds up over many requests
- Possibly related to batch assembly/disassembly
- May be in queue management, tensor allocation, or FFmpeg decoding
- The corruption eventually corrupts glibc's heap metadata, causing "corrupted double-linked list"

---

## Recent Fixes Applied (Not Sufficient)

### Commit 97a9d1c (2026-02-03 18:03)
```
fix: use non-blocking streams and pinned memory for lens transfer

- Convert all cudaStreamCreate calls to cudaStreamCreateWithFlags(..., cudaStreamNonBlocking)
- Add pinned host memory and device memory for batch lengths
- Replace synchronous lens tensor creation with async H2D transfer
```

### Commit f924c67 (2026-02-03 17:38)
```
refactor: replace all malloc/realloc/calloc with _or_die variants

- All allocations now fail-fast on out-of-memory errors
```

### Commit fcf2c2e (2026-02-03 17:09)
```
Fix thread explosion: Limit MHD and OpenMP threads to 16
```

These fixes address specific issues but don't resolve the accumulated corruption.

---

## Suggested Investigation Areas

1. **Queue management** (`src/queue.c`)
   - Check for use-after-free or double-free
   - Verify thread-safe access to shared queues
   - Look for buffer overflows in batch assembly

2. **Tensor lifecycle**
   - Ensure tensors are properly freed after each batch
   - Check for leaks in error paths

3. **FFmpeg integration**
   - `av_malloc_or_die` wrapper - verify all allocations freed
   - Check for leaks in audio decoding path

4. **Memory debugging**
   - Run with AddressSanitizer: `ASAN_OPTIONS=detect_leaks=1`
   - Run with Valgrind (may be slow with CUDA)
   - Add heap corruption detection: `MALLOC_CHECK_=3`

---

## Workaround for Production

Use the auto-restart wrapper script that monitors health and restarts on crash:

```bash
./scripts/run_pipeline_with_restart.sh 2026-01-19 16 5000
```

This achieves sustained throughput by:
1. Processing in batches of 5000 files
2. Checking `/ready` endpoint after each batch
3. Restarting vfun if unresponsive
4. Continuing from checkpoint

Expected throughput with restarts: ~800-900 files/min sustained

---

## Test Commands Used

```bash
# Start vfun
cd ~/strolid/vfun && ./vfun --port 4380 > /tmp/vfun_4380.log 2>&1 &

# Run stress test
python3 scripts/nas_transcription_pipeline.py \
  --date 2026-01-19 \
  --hour 06 \
  --server 1 \
  --workers 16 \
  --limit 5000

# Check health
curl -s http://localhost:4380/ready

# View crash log
tail -50 /tmp/vfun_4380.log
```

---

## Appendix: Test Data

- **Source**: `/mnt/nas/Freeswitch1/2026-01-19/06/`
- **File count**: 43,940 WAV files
- **File format**: 8kHz, 16-bit, mono (standard telephony)
- **Avg duration**: ~60 seconds
- **Avg size**: ~960KB

---

**Report prepared by:** Claude Code
**Contact:** Thomas
