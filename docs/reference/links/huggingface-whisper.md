# hugging_face_whisper

Transcribes audio recordings in vCon dialogs using a Hugging Face hosted Whisper ASR endpoint.

## Prerequisites

- A Hugging Face API key with access to a deployed Whisper inference endpoint
- The endpoint URL for your Hugging Face Whisper deployment

## Configuration

```yaml
links:
  hugging_face_whisper:
    module: links.hugging_face_whisper
    options:
      API_URL: https://your-endpoint.us-east-1.aws.endpoints.huggingface.cloud
      API_KEY: hf_your_key_here
      minimum_duration: 30
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `API_URL` | string | `https://xxxxxx.us-east-1.aws.endpoints.huggingface.cloud` | Hugging Face inference endpoint URL |
| `API_KEY` | string | `Bearer hf_XXXXX` | Hugging Face API key (include "Bearer " prefix) |
| `minimum_duration` | int | `30` | Minimum recording duration in seconds to transcribe |
| `Content-Type` | string | `audio/flac` | MIME type of the audio content sent to the endpoint |

## Example

```yaml
chains:
  transcription:
    links:
      - hugging_face_whisper:
          API_URL: https://abc123.us-east-1.aws.endpoints.huggingface.cloud
          API_KEY: Bearer hf_xxxxxxxxxxxxxxxxxxxx
          minimum_duration: 30
          Content-Type: audio/flac
    storages:
      - postgres
    ingress_lists:
      - audio_input
    enabled: 1
```

## Output

Adds a transcript analysis entry to the vCon for each qualifying dialog:

```json
{
  "analysis": [
    {
      "type": "transcript",
      "vendor": "hugging_face_whisper",
      "dialog": 0,
      "body": {
        "text": "Hello, how can I help you today?"
      }
    }
  ]
}
```

## Behavior

- Skips dialogs that are not of type `recording`
- Skips dialogs shorter than `minimum_duration`
- Skips dialogs that already have a transcript analysis
- Supports both inline base64-encoded audio and external URL references
- Verifies file integrity via SHA-512 signature when provided on external URLs
- Retries failed API calls with exponential backoff (up to 6 attempts)
