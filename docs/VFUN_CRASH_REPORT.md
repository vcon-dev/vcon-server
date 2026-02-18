# vfun CUDA Crash Report

**Date:** 2026-02-02
**Environment:** Ubuntu Linux, NVIDIA H100 NVL (95GB VRAM)
**vfun version:** Built from ~/strolid/vfun
**Model:** parakeet-tdt-110m (NeMo ASR)

---

## Executive Summary

vfun crashes intermittently after processing hundreds of audio files under sustained concurrent load. The crash is caused by a **cuBLAS matrix multiplication failure** (`CUBLAS_STATUS_EXECUTION_FAILED`) that occurs when certain batch combinations create problematic tensor dimensions during the transformer decoder's forward pass.

**Key finding:** Individual files process successfully. The crash only occurs under batched/concurrent workloads when specific tensor dimension combinations are formed.

---

## Symptom

When processing large volumes of audio files (500+) with high concurrency (64 workers), vfun:

1. Processes successfully for a period (typically 100-500+ files)
2. Suddenly stops responding to requests
3. Process remains alive but `/ready` endpoint times out
4. GPU memory drops to 0 MiB (resources released)
5. Subsequent requests fail silently

The service does not exit or restart automatically - it enters a hung state.

---

## Reproduction Steps

```bash
# Start vfun
cd ~/strolid/vfun && ./vfun --port 4380 > /tmp/vfun.log 2>&1 &

# Wait for ready
sleep 10 && curl http://localhost:4380/ready

# Send concurrent requests (64 parallel workers)
ls /path/to/wav/files/*.wav | head -500 | \
  xargs -P 64 -I {} curl -s -X POST \
    -F "file-binary=@{};type=audio/wav" \
    http://localhost:4380/wtf

# vfun will crash after processing 100-500 files
```

**Audio file characteristics:**
- Format: WAV, 8kHz, 16-bit, mono (standard telephony)
- Duration: ~60 seconds each
- Size: ~960KB each
- Source: Freeswitch call recordings

---

## Error Message

From `/tmp/vfun.log` after crash:

```
RuntimeError: CUDA error: CUBLAS_STATUS_EXECUTION_FAILED when calling cublasLtMatmul
with transpose_mat1 1 transpose_mat2 0 m 1024 n 251 k 1024 mat1_ld 1024 mat2_ld 1024
result_ld 1024 abcType 0 computeType 68 scaleType 0
```

---

## Full Stack Trace

```
File "code/__torch__/nemo/collections/asr/modules/transformer/transformer_decoders/___torch_mangle_1124.py", line 27, in forward
    _2 = (first_sub_layer).forward(_0, _1, argument_2, )
    input = torch.add_(_2, argument_1)
    _3 = (second_sub_layer).forward((layer_norm_2).forward(input, ), encoder_embeddings, argument_4, )
          ~~~~~~~~~~~~~~~~~~~~~~~~~ <--- HERE

File "code/__torch__/nemo/collections/asr/modules/transformer/transformer_modules/___torch_mangle_1118.py", line 23, in forward
    query_net = self.query_net
    _0 = (query_net).forward(argument_1, )
    _1 = (key_net).forward(encoder_embeddings, )
          ~~~~~~~~~~~~~~~~ <--- HERE

File "code/__torch__/torch/nn/modules/linear/___torch_mangle_1113.py", line 12, in forward
    bias = self.bias
    weight = self.weight
    x = torch.linear(encoder_embeddings, weight, bias)
        ~~~~~~~~~~~~ <--- HERE

Traceback of TorchScript, original code (most recent call last):
/home/dev/vfun/.venv/lib/python3.12/site-packages/torch/nn/modules/linear.py(134): forward
/home/dev/vfun/.venv/lib/python3.12/site-packages/nemo/collections/asr/modules/transformer/transformer_modules.py(174): forward
/home/dev/vfun/.venv/lib/python3.12/site-packages/nemo/collections/asr/modules/transformer/transformer_decoders.py(98): forward_preln
/home/dev/vfun/.venv/lib/python3.12/site-packages/nemo/collections/asr/modules/transformer/transformer_decoders.py(158): forward
/home/dev/vfun/.venv/lib/python3.12/site-packages/nemo/collections/asr/modules/transformer/transformer_decoders.py(255): forward
/home/dev/vfun/export-scripts/canary-to-torchscript.py(62): forward
```

---

## Analysis

### What's Happening

1. **Batching behavior:** vfun batches concurrent requests for GPU efficiency using:
   ```
   GPU_MAX_BATCH_SIZE = 64
   GPU_COALESCE_TIMEOUT_US = 5000 (5ms)
   GPU_COALESCE_MIN_FILL = 16
   ```

2. **Tensor dimension issue:** When batching audio of varying lengths, the resulting `encoder_embeddings` tensor has shape `[batch, seq_len, 1024]`. The error shows `n=251` which suggests a sequence length dimension.

3. **cuBLAS failure:** The `cublasLtMatmul` call fails when the resulting matrix dimensions hit certain values. This may be related to:
   - Memory alignment issues at specific sizes
   - cuBLAS kernel selection for unusual dimensions
   - Tensor core compatibility with non-standard shapes

4. **No recovery:** After the CUDA error, the GPU context is corrupted. vfun doesn't catch this exception at the HTTP handler level, so it hangs indefinitely.

### Why Single Files Work

When processing files individually:
- Batch size is always 1
- Sequence lengths are consistent per-request
- No cross-request tensor dimension combinations occur

### Suspected Root Causes

1. **Batch padding edge case:** When batching audio of different durations, padding may create tensor dimensions that cuBLAS handles poorly.

2. **Missing dimension validation:** The model may not validate that input dimensions are compatible with cuBLAS kernel requirements before calling `torch.linear()`.

3. **CUDA error handling:** The exception isn't caught and handled gracefully - the service should restart or reset the CUDA context.

---

## Observations

| Test | Result |
|------|--------|
| Single file processing | Always succeeds |
| Sequential processing (1 worker) | Succeeds for 1000+ files |
| Parallel processing (64 workers) | Crashes after 100-500 files |
| Same "crash file" sent individually | Succeeds |
| Reduced concurrency (8 workers) | Still crashes, just takes longer |

**GPU Memory:** Stable at ~12.6GB during processing until crash. No memory leak observed.

**File Characteristics:** Crash files have no distinguishing features - same format, similar duration, similar content to files that succeed.

---

## Suggested Fixes

### 1. Exception Handling (Quick Fix)

Wrap the inference call in try/except and reset CUDA context on failure:

```python
try:
    result = model.forward(batch)
except RuntimeError as e:
    if "CUDA" in str(e) or "cuBLAS" in str(e):
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        # Return error response instead of hanging
        return {"error": "CUDA error, please retry"}
    raise
```

### 2. Dimension Validation (Preventive)

Before batching, validate that resulting tensor dimensions are safe:

```python
def is_safe_batch(sequences):
    """Check if batch dimensions are compatible with cuBLAS"""
    max_len = max(len(s) for s in sequences)
    # Avoid problematic dimensions (may need empirical tuning)
    if max_len % 8 != 0:  # Ensure alignment
        max_len = ((max_len + 7) // 8) * 8
    return max_len
```

### 3. Graceful Degradation

If a batch fails, retry with smaller batch size or process files individually:

```python
def process_with_fallback(files, batch_size=64):
    try:
        return process_batch(files, batch_size)
    except RuntimeError:
        if batch_size > 1:
            # Retry with smaller batches
            return process_with_fallback(files, batch_size // 2)
        else:
            # Process individually as last resort
            return [process_single(f) for f in files]
```

### 4. Health Check Watchdog

Add internal watchdog that restarts the service if inference hangs:

```python
import signal

def timeout_handler(signum, frame):
    logger.error("Inference timeout - restarting")
    torch.cuda.empty_cache()
    os._exit(1)  # Force restart

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30 second timeout per batch
```

---

## Current Workaround

We're using an external monitoring script that:

1. Checks `/ready` endpoint every 30 seconds
2. If unresponsive, kills vfun process (`pkill -9`)
3. Restarts vfun
4. Continues processing from checkpoint

This achieves ~3000 files/minute with occasional 10-second restart pauses.

---

## Environment Details

```
GPU: NVIDIA H100 NVL
VRAM: 95,320 MiB total
CUDA: (check with nvidia-smi)
PyTorch: 2.x (from vfun venv)
NeMo: (from vfun venv)

vfun config:
  GPU_MAX_BATCH_SIZE = 64
  GPU_COALESCE_TIMEOUT_US = 5000
  GPU_COALESCE_MIN_FILL = 16
```

---

## Files for Testing

Sample files that trigger the crash (when processed concurrently with others):

```
/mnt/nas/Freeswitch1/2026-01-19/11/10508_12706498965_993318019641306_2026-01-19_11:14:08.wav
/mnt/nas/Freeswitch1/2026-01-19/11/10508_17019013723_993313073314983_2026-01-19_11:11:14.wav
```

Note: These files process successfully individually. The crash occurs when they're part of a batch with other files.

---

## Contact

Report prepared by: Claude Code (assisted investigation)
System operator: Thomas
Date: 2026-02-02
