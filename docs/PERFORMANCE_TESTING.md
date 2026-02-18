# Performance Testing Notes

**Last Updated:** 2026-02-02

## Test Environment

### Servers
- **Conserver (vcon-server)**: http://localhost:8080 (token: `mulliganmccarthy`)
- **vfun (transcription)**: http://localhost:4380/wtf

### NAS Storage

**Mount Point:** `/mnt/nas`
```
64.187.219.131:/mnt/slave_recording → /mnt/nas (NFS4)
- rsize/wsize: 1MB
- Protocol: TCP
- Hard mount with 600s timeout
```

**Directory Structure:**
```
/mnt/nas/
├── Freeswitch1/              # 20 Freeswitch servers (1-20)
│   ├── 2026-01-19/           # Date directories (15+ days available)
│   │   ├── 06/               # Hour directories (00-23)
│   │   │   └── *.wav         # Recording files (~489k per day)
│   │   ├── 07/
│   │   └── ...
│   ├── 2026-01-20/
│   └── ...
├── Freeswitch2/
├── ...
├── Freeswitch20/
├── Batch1_recording/
├── pcaps_*/                  # Packet captures
└── fs_collect_by_number.sh   # Collection utility
```

**File Naming Pattern:**
```
{campaign}_{caller}_{callid}_{date}_{time}.wav
Example: 10508_12026661845_993317168030975_2026-01-19_06:47:08.wav

Fields:
- campaign: Campaign/extension ID (e.g., 10508, 6075, 9676)
- caller: Phone number (e.g., 12026661845)
- callid: Unique call ID (e.g., 993317168030975)
- date: YYYY-MM-DD
- time: HH:MM:SS
```

**Scale:**
- ~489,000 recordings per day per Freeswitch server
- ~9.78 million recordings/day across all 20 servers
- ~938 KB average file size (~60 seconds @ 8kHz 16-bit)
- ~9 TB/day of new recordings
- 15+ days of historical data
- Access requires `nasgroup` membership

---

## Performance Results (2026-02-02)

### Conserver API
| Metric | Value |
|--------|-------|
| Throughput | 151.68 req/s |
| Avg Latency | 57.22 ms |
| Success Rate | 100% |

### vfun Transcription (Local Files)
| Metric | Value |
|--------|-------|
| Throughput | 32.72 files/sec |
| Data Rate | 30.36 MB/sec |
| Peak GPU Utilization | 95% |

### vfun Transcription (NAS Files)
| Files | Workers | Throughput | Data Rate | Parallelism |
|-------|---------|------------|-----------|-------------|
| 100 | 32 | 48.40 files/sec | 34.08 MB/s | 25.9x |
| 200 | 64 | 45.60 files/sec | 30.92 MB/s | 47.9x |
| 500 | 64 | 43.63 files/sec | 30.85 MB/s | 59.4x |

### Full Pipeline (NAS → vfun → vCon → Conserver → vcon-mcp)
| Files | Workers | Throughput | vCons Stored | Success |
|-------|---------|------------|--------------|---------|
| 50 | 16 | 2,447 files/min | 35 | 100% |
| 500 | 48 | 2,576 files/min | 362 | 100% |
| 1,000 | 64 | **2,973 files/min** | 703 | 100% |

**Full Pipeline Capacity (single vfun instance):**
- ~3,000 files/min = **~4.3 million files/day**
- vCon creation adds minimal overhead (~1ms per vCon)
- Conserver chain processing: ~10ms per vCon
- Webhook to vcon-mcp (Supabase): ~100-200ms per vCon

**Key Findings:**
- NAS network storage does not bottleneck transcription
- GPU batching works efficiently (59.4x parallelism vs 64x max)
- Sustained ~44-48 files/sec with high concurrency
- 100% success rate across 1,500+ files
- Full pipeline maintains ~48 files/sec throughput

### vfun Batching Configuration
```
GPU_MAX_BATCH_SIZE = 64
GPU_COALESCE_TIMEOUT_US = 5000 (5ms)
GPU_COALESCE_MIN_FILL = 16
```

---

## Test Scripts

Located in `scripts/`:
- `nas_transcription_pipeline.py` - **Production pipeline** with vCon creation and storage
- `nas_stress_test.py` - High-concurrency vfun stress test with NAS files

### Running Tests

```bash
# Check servers
curl -s http://localhost:8080/docs | head -5
curl -s http://localhost:4380/ready

# Start vfun if needed
cd ~/strolid/vfun && ./vfun --port 4380

# Run vfun-only stress test
python3 scripts/nas_stress_test.py 200 64

# Run full pipeline (transcription + vCon storage)
python3 scripts/nas_transcription_pipeline.py --date 2026-01-19 --hour 06 --limit 500 --workers 48 --store-vcons

# Dry run to see file counts
python3 scripts/nas_transcription_pipeline.py --date 2026-01-19 --dry-run
```

### Pipeline Chain Configuration
```
main_chain:     ingress:default → tag → supabase_webhook → egress:processed
transcription:  ingress:transcribe → tag → wtf_transcribe → keyword_tagger → supabase_webhook → egress:transcribed
```

---

## vfun Stability Issues (CUDA Crashes)

### Root Cause Analysis (2026-02-02)

**Problem:** vfun crashes intermittently after processing hundreds of files under sustained load.

**Investigation findings:**
1. **NOT the NAS** - Files read correctly, NAS performance is stable
2. **NOT memory leaks** - GPU memory stable at ~12.6GB throughout processing
3. **NOT single file issues** - Crash-causing files process fine individually
4. **IS a CUDA batching issue** - Specific batch combinations trigger cuBLAS failures

**Error signature:**
```
RuntimeError: CUDA error: CUBLAS_STATUS_EXECUTION_FAILED when calling cublasLtMatmul
with transpose_mat1 1 transpose_mat2 0 m 1024 n 251 k 1024
```

**What happens:**
1. Under high concurrency, vfun batches audio files for GPU processing
2. Certain combinations of audio lengths create tensor dimensions that trigger cuBLAS matrix multiplication failures
3. The CUDA error corrupts GPU state, leaving vfun hung (process exists but unresponsive to `/ready` endpoint)
4. GPU memory shows 0 MiB used after crash (resources released but process not terminated)

**Affected dimensions:** The `n=251` parameter in the error suggests certain audio sequence lengths cause problematic matrix sizes during the transformer decoder forward pass.

### Workarounds for Production

**1. Auto-restart script:**
```bash
#!/bin/bash
# Run pipeline with automatic vfun restart on crash
restart_vfun() {
    pkill -9 -f "vfun --port 4380"
    sleep 2
    cd ~/strolid/vfun && ./vfun --port 4380 > /tmp/vfun.log 2>&1 &
    sleep 10
}

# Check health every 30 seconds, restart if hung
while true; do
    if ! curl -s --max-time 5 http://localhost:4380/ready > /dev/null 2>&1; then
        echo "$(date) - vfun crash detected, restarting..."
        restart_vfun
    fi
    sleep 30
done
```

**2. Reduce concurrency** (may reduce throughput but fewer crashes):
- Try 32-48 workers instead of 64
- Smaller batches reduce likelihood of problematic tensor dimensions

**3. Batch processing with checkpoints:**
- Process in batches of 2000-3000 files
- Restart vfun between batches preventively
- Track progress in checkpoint files

### Investigation Scripts

Located in `scripts/`:
- `find_bad_file.py` - Tests files sequentially to identify crash point
- `run_pipeline_with_restart.sh` - Pipeline with auto-restart capability

### Logs to Check
- `/tmp/vfun.log` or `/tmp/vfun_test.log` - vfun stdout/stderr including CUDA errors
- Pipeline logs show last successful file before crash
