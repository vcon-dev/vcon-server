# groq_whisper

Transcribes audio recordings in vCon dialogs using the Groq Whisper ASR API.

## Prerequisites

- `GROQ_API_KEY` environment variable

## Configuration

```yaml
links:
  groq_whisper:
    module: links.groq_whisper
    options:
      minimum_duration: 30
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `API_KEY` | string | `$GROQ_API_KEY` | Groq API key for authentication |
| `minimum_duration` | int | `30` | Minimum recording duration in seconds to transcribe |
| `Content-Type` | string | `audio/flac` | MIME type of audio content sent to the API |

## Example

```yaml
chains:
  transcription:
    links:
      - groq_whisper:
          minimum_duration: 60
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
      "vendor": "groq_whisper",
      "dialog": 0,
      "body": {
        "text": "Hello, how can I help you today?",
        "language": "en"
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
- Retries failed API calls with exponential backoff (up to 6 attempts)
