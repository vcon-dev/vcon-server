# hugging_face_whisper

Transcribes recordings with a Whisper model on a Hugging Face inference endpoint.

Module: `links.hugging_face_whisper`

!!! warning "Deprecated"
    Use [`links.transcribe`](transcribe.md) with `vendor: hugging_face`. The worker reroutes `module: links.hugging_face_whisper` there and logs a warning. This module remains the implementation, and the options below go under `vendor_options`.

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `minimum_duration` | number | `30` | Skips recordings shorter than this many seconds |
| `API_URL` | string | `https://xxxxxx.us-east-1.aws.endpoints.huggingface.cloud` | Placeholder. Set your endpoint URL |
| `API_KEY` | string | `Bearer hf_XXXXX` | Placeholder. Set the bare token: the code adds `Bearer ` itself |
| `Content-Type` | string | `audio/flac` | Request content type. Match it to your audio |

## Follow the processing steps

For each dialog:

1. Skip it unless its `type` is `recording`.
2. Skip it if `duration` is below `minimum_duration`. A dialog with no `duration` raises, and the vCon goes to the dead letter queue: `KeyError` when the key is absent, `TypeError` when it is null, as on any vCon sent through `POST /vcon` without one.
3. Skip it if it already has a `transcript` analysis.
4. Get the audio. An inline `body` is decoded by its `encoding`. Otherwise the link downloads `url` and, if the dialog has `alg` of `SHA-512` and a `signature`, verifies it.
5. Post the audio to `API_URL`, with up to 6 attempts.
6. Add the analysis.

The link does not check the HTTP status. Any JSON reply, including an error object from the endpoint, is stored as the transcript.

An exception or an empty reply stops the loop. The link counts the failure and logs it, saves the vCon, and the chain continues.

## Read the return value

Returns the uuid, also after a transcription failure. A missing vCon raises `AttributeError`.

## Inspect the vCon changes

One analysis entry per transcribed dialog.

| Field | Value |
|---|---|
| `type` | `transcript` |
| `dialog` | Dialog index |
| `vendor` | `hugging_face_whisper` |
| `body` | The endpoint's JSON reply |
| `encoding` | `json` when the reply is an object or list |
| `vendor_schema` | `opts`, with credential-like option names removed |

## Copy a configuration example

```yaml
links:
  transcribe_hf:
    module: links.transcribe
    options:
      vendor: hugging_face
      vendor_options:
        API_URL: https://your-endpoint.endpoints.huggingface.cloud
        API_KEY: your-hugging-face-token
        Content-Type: audio/flac
        minimum_duration: 30
```

## Track the metrics

`conserver.link.hugging_face_whisper.transcription_time` and `conserver.link.hugging_face_whisper.transcription_failures`. See [Metrics](../metrics.md).
