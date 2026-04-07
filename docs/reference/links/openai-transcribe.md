# openai_transcribe

!!! note "Stub"
    No source directory for this link (`server/links/openai_transcribe/`) exists in the current codebase. This page is a placeholder based on the expected behaviour of a link that transcribes audio using the [OpenAI Whisper API](https://platform.openai.com/docs/guides/speech-to-text).

Transcribes audio recordings in vCon dialogs using the OpenAI Whisper speech-to-text API. The transcription result is stored as a `transcript` analysis entry on the vCon.

## Prerequisites

- `OPENAI_API_KEY` environment variable must be set with a valid OpenAI API key.

## Configuration

```yaml
links:
  openai_transcribe:
    module: links.openai_transcribe
    options:
      model: whisper-1
      language: en
      minimum_duration: 0
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | `whisper-1` | OpenAI Whisper model to use for transcription. |
| `language` | string | — | Optional BCP-47 language code (e.g. `en`, `es`). Omit to let the model auto-detect. |
| `minimum_duration` | int | `0` | Minimum recording duration in seconds. Dialogs shorter than this value are skipped. |
| `API_KEY` | string | `$OPENAI_API_KEY` | OpenAI API key. Reads from the `OPENAI_API_KEY` environment variable by default. |

## Example

```yaml
chains:
  transcription:
    links:
      - openai_transcribe:
          model: whisper-1
          language: en
          minimum_duration: 5
    storages:
      - postgres
    ingress_lists:
      - audio_input
    enabled: 1
```

## Output

Adds a `transcript` analysis entry to the vCon for each processed dialog:

```json
{
  "analysis": [
    {
      "type": "transcript",
      "vendor": "openai",
      "dialog": 0,
      "body": {
        "text": "Hello, how can I help you today?"
      }
    }
  ]
}
```

## Behavior

- Skips dialogs that are not of type `recording`.
- Skips dialogs shorter than `minimum_duration` seconds.
- Skips dialogs that already have a `transcript` analysis entry.
- Supports both inline base64-encoded audio (`body`) and external URL references (`url`).
- Saves the updated vCon back to Redis after processing all dialogs.
