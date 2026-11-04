# openai_transcribe

Transcribes recordings with an OpenAI-compatible transcription API, splitting long audio into chunks.

Module: `links.openai_transcribe`

!!! warning "Deprecated"
    Use [`links.transcribe`](transcribe.md) with `vendor: openai`. The worker reroutes `module: links.openai_transcribe` there and logs a warning. This module remains the implementation, and the options below go under `vendor_options`.

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | string | `None` | See [LLM client options](index.md#set-the-llm-client-options) |
| `AZURE_OPENAI_API_KEY` | string | `None` | See [LLM client options](index.md#set-the-llm-client-options) |
| `AZURE_OPENAI_ENDPOINT` | string | `None` | See [LLM client options](index.md#set-the-llm-client-options) |
| `AZURE_OPENAI_API_VERSION` | string | `2024-10-21` | See [LLM client options](index.md#set-the-llm-client-options) |
| `model` | string | `gpt-4o-transcribe` | Transcription model |
| `language` | string | `en` | In `default_options`, but no code reads it, so it never reaches the API |
| `minimum_duration` | number | `3` | Skips recordings shorter than this many seconds |
| `max_chunk_duration` | number | `480` | Longest chunk in seconds |
| `use_silence_chunking` | bool | `true` | Splits at silences near each chunk boundary |
| `silence_thresh` | number | `-40` | Silence threshold in dBFS |
| `silence_len` | number | `2000` | Shortest silence in milliseconds |
| `send_ai_usage_data_to_url` | string | `""` | See [AI usage](index.md#report-ai-usage-to-an-endpoint) |
| `ai_usage_api_token` | string | `""` | See [AI usage](index.md#report-ai-usage-to-an-endpoint) |

## Follow the processing steps

For each dialog:

1. Skip it unless its `type` is `recording` and it has a `url`. Inline `body` audio is not read.
2. Skip it if `duration` is below `minimum_duration`. If `duration` is missing, go on with a warning.
3. Skip it if it already has a `transcript` analysis.
4. Download the audio and split it if it runs past `max_chunk_duration`. With silence chunking on, each split goes to the silence nearest the boundary, within a quarter of `max_chunk_duration`. Otherwise it falls on the boundary. Chunks are exported as mono 16 kHz MP3.
5. Transcribe each chunk in turn, with up to 6 attempts for the whole download and transcription. Join the chunk texts with spaces.
6. Add the analysis.

The link uses ffmpeg, which the server images install. An empty result stops the loop.

A failing dialog takes about a minute to reach the dead letter queue, because the waits between attempts add up to 62 seconds. That worker handles nothing else meanwhile unless `CONSERVER_VCON_CONCURRENCY` is above 1.

## Read the return value

Returns the uuid. A transcription failure after all retries raises, and the vCon goes to the dead letter queue. A missing vCon raises `AttributeError`.

## Inspect the vCon changes

One analysis entry per transcribed dialog.

| Field | Value |
|---|---|
| `type` | `transcript` |
| `dialog` | Dialog index |
| `vendor` | `openai` |
| `body` | The API response as an object, with the text in `text`. A chunked result also has `chunked_transcription` with `total_chunks` and `chunk_results` |
| `encoding` | `json` |
| `vendor_schema` | `opts`, with credential-like option names removed |

## Copy a configuration example

```yaml
links:
  transcribe_openai:
    module: links.transcribe
    options:
      vendor: openai
      vendor_options:
        OPENAI_API_KEY: your-openai-key
        model: gpt-4o-transcribe
        minimum_duration: 3
        max_chunk_duration: 480
```

## Track the metrics

`conserver.link.openai.transcription_time` and `conserver.link.openai.transcription_failures`. See [Metrics](../metrics.md).
