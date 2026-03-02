# WTF Transcription Link (vfun Integration)

A link that sends vCon audio dialogs to a vfun transcription server and adds the results as WTF (World Transcription Format) analysis entries.

## Overview

This link integrates with the vfun transcription server to provide:
- Multi-language speech recognition (English + auto-detect)
- Speaker diarization (who spoke when)
- GPU-accelerated processing with CUDA
- WTF-compliant output format per IETF draft-howe-vcon-wtf-extension-01

## Configuration

```yaml
wtf_transcribe:
  module: links.wtf_transcribe
  options:
    # Required: URL of the vfun transcription server
    vfun-server-url: http://localhost:8443/transcribe

    # Optional: Enable speaker diarization (default: true)
    diarize: true

    # Optional: Request timeout in seconds (default: 300)
    timeout: 300

    # Optional: Minimum dialog duration to transcribe in seconds (default: 5)
    min-duration: 5

    # Optional: API key for vfun server authentication
    api-key: your-api-key-here
```

## How It Works

1. **Extract Audio**: Reads audio from vCon dialog (supports `body` with base64/base64url encoding, or `url` with file:// or http:// references)
2. **Send to vfun**: POSTs audio file to vfun's `/transcribe` endpoint
3. **Create WTF Analysis**: Formats the transcription result as a WTF analysis entry
4. **Update vCon**: Adds the WTF analysis to the vCon and stores it back to Redis

## Output Format

The link adds analysis entries with the WTF format:

```json
{
  "type": "wtf_transcription",
  "dialog": 0,
  "mediatype": "application/json",
  "vendor": "vfun",
  "product": "parakeet-tdt-110m",
  "schema": "wtf-1.0",
  "encoding": "json",
  "body": {
    "transcript": {
      "text": "Hello, how can I help you today?",
      "language": "en-US",
      "duration": 30.0,
      "confidence": 0.95
    },
    "segments": [
      {
        "id": 0,
        "start": 0.0,
        "end": 3.5,
        "text": "Hello, how can I help you today?",
        "confidence": 0.95,
        "speaker": 0
      }
    ],
    "metadata": {
      "created_at": "2024-01-15T10:30:00Z",
      "processed_at": "2024-01-15T10:30:05Z",
      "provider": "vfun",
      "model": "parakeet-tdt-110m"
    },
    "speakers": {
      "0": {
        "id": 0,
        "label": "Speaker 0",
        "segments": [0],
        "total_time": 15.2
      }
    },
    "quality": {
      "average_confidence": 0.95,
      "multiple_speakers": true,
      "low_confidence_words": 0
    }
  }
}
```

## Behavior

- **Skips non-recording dialogs**: Only processes dialogs with `type: "recording"`
- **Skips already transcribed**: Dialogs with existing WTF transcriptions are skipped
- **Duration filtering**: Dialogs shorter than `min-duration` are skipped
- **File URL support**: Can read audio from local `file://` URLs directly

## Example Chain Configuration

```yaml
chains:
  transcription_chain:
    links:
      - tag
      - wtf_transcribe
      - supabase_webhook
    ingress_lists:
      - transcribe
    egress_lists:
      - transcribed
    enabled: 1
```

## vfun Server

The vfun server provides GPU-accelerated transcription:

```bash
# Start vfun server
cd /path/to/vfun
./vfun server

# Test health
curl http://localhost:8443/ping

# Manual transcription test
curl -X POST http://localhost:8443/transcribe \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@audio.wav" \
  -F "diarize=true"
```

## Related

- [vfun](https://github.com/strolid/vfun) - GPU-accelerated transcription server
- [draft-howe-vcon-wtf-extension](https://datatracker.ietf.org/doc/html/draft-howe-vcon-wtf-extension) - IETF WTF specification
