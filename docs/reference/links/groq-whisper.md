# groq_whisper

Transcribes recordings with Groq's hosted Whisper model.

Module: `links.groq_whisper`

!!! warning "Deprecated"
    Use [`links.transcribe`](transcribe.md) with `vendor: groq`. The worker reroutes `module: links.groq_whisper` there and logs a warning. This module remains the implementation, and the options below go under `vendor_options`.

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `minimum_duration` | number | `30` | Skips recordings shorter than this many seconds |
| `API_KEY` | string | `GROQ_API_KEY` from the environment at import, or `YOUR_GROQ_API_KEY` | Groq API key |
| `Content-Type` | string | `audio/flac` | In `default_options`, but no code reads it |

The model is fixed in the code as `whisper-large-v3-turbo`.

## Follow the processing steps

For each dialog:

1. Skip it unless its `type` is `recording`.
2. Skip it if `duration` is below `minimum_duration`. A dialog with no `duration` raises, and the vCon goes to the dead letter queue: `KeyError` when the key is absent, `TypeError` when it is null, as on any vCon sent through `POST /vcon` without one.
3. Skip it if it already has a `transcript` analysis.
4. Get the audio. An inline `body` is decoded by its `encoding`. Otherwise the link downloads `url` and, if the dialog has `alg` of `SHA-512` and a `signature`, verifies it.
5. Send the audio to Groq, with up to 6 attempts.
6. Add the analysis.

Any transcription failure stops the loop. The link counts the failure and logs it, saves the vCon, and the chain continues with no transcript for that dialog.

## Check the side effects

Importing this module changes the whole worker process. It removes `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` and their lowercase forms from the environment, and it replaces `httpx.Client` with a version that drops proxy arguments. Other links in that worker lose their proxy settings from that point on.

## Read the return value

Returns the uuid, also after a transcription failure. A missing vCon raises `AttributeError`.

## Inspect the vCon changes

One analysis entry per transcribed dialog.

| Field | Value |
|---|---|
| `type` | `transcript` |
| `dialog` | Dialog index |
| `vendor` | `groq_whisper` |
| `body` | The Groq response as an object, with the text in `text` |
| `encoding` | `json` |
| `vendor_schema` | `opts`, with credential-like option names removed |

## Copy a configuration example

```yaml
links:
  transcribe_groq:
    module: links.transcribe
    options:
      vendor: groq
      vendor_options:
        API_KEY: your-groq-key
        minimum_duration: 30
```

## Track the metrics

`conserver.link.groq_whisper.transcription_time` and `conserver.link.groq_whisper.transcription_failures`. See [Metrics](../metrics.md).
