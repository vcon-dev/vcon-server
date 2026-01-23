# deepgram_link

Transcribes audio using the Deepgram API.

## Configuration

```yaml
links:
  deepgram_link:
    module: links.deepgram_link
    options:
      model: nova-2
      language: en
      punctuate: true
      diarize: true
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | `nova-2` | Deepgram model (nova-2, nova, enhanced, base) |
| `language` | string | `en` | Language code |
| `punctuate` | bool | `true` | Add punctuation |
| `diarize` | bool | `false` | Speaker diarization |
| `smart_format` | bool | `true` | Smart formatting |
| `utterances` | bool | `false` | Split by utterance |
| `timeout` | int | `300` | Request timeout in seconds |

## Requirements

- `DEEPGRAM_KEY` environment variable

## Example

```yaml
chains:
  transcription:
    links:
      - deepgram_link:
          model: nova-2
          language: en
          diarize: true
    storages:
      - postgres
    ingress_lists:
      - audio_input
    enabled: 1
```

## Output

Adds transcription to vCon analysis:

```json
{
  "analysis": [
    {
      "type": "transcript",
      "vendor": "deepgram",
      "body": {
        "transcript": "Hello, how can I help you today?",
        "words": [...],
        "confidence": 0.95
      }
    }
  ]
}
```
