# deepgram_link

Transcribes recordings with the Deepgram API, or through a LiteLLM proxy.

Module: `links.deepgram_link`

!!! warning "Deprecated"
    Use [`links.transcribe`](transcribe.md) with `vendor: deepgram`. The worker reroutes `module: links.deepgram_link` there and logs a warning. This module remains the implementation, and the options below go under `vendor_options`.

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `minimum_duration` | number | `60` | Skips recordings shorter than this many seconds |
| `DEEPGRAM_KEY` | string | `None` | Deepgram API key. Required unless the LiteLLM pair is set |
| `minimum_confidence` | float | `0.5` | Discards transcripts below this confidence |
| `api` | dict | none | Keyword arguments for Deepgram's `PrerecordedOptions`. Required on the direct path, and has no default |
| `LITELLM_PROXY_URL` | string | none | With `LITELLM_MASTER_KEY`, routes through LiteLLM |
| `LITELLM_MASTER_KEY` | string | none | See `LITELLM_PROXY_URL` |
| `model` | string | none | LiteLLM path only. Falls back to `api.model`, then `nova-3` |
| `send_ai_usage_data_to_url` | string | `""` | See [AI usage](index.md#report-ai-usage-to-an-endpoint). Direct path only |
| `ai_usage_api_token` | string | `""` | See [AI usage](index.md#report-ai-usage-to-an-endpoint) |

## Follow the processing steps

For each dialog:

1. Skip it unless its `type` is `recording` and it has a `url`. A dialog with no `url` key raises `KeyError`.
2. If `duration` is missing and the URL ends in `.wav`, fetch the file to measure it and store the value on the dialog.
3. Skip it if it is shorter than `minimum_duration`. If the duration is still unknown, go on with a warning.
4. Skip it if it already has a `transcript` analysis.
5. Transcribe it, with up to 6 attempts.
6. On the direct path, discard the result if confidence is below `minimum_confidence`, count a failure, and go on to the next dialog. The LiteLLM path returns no confidence, so it skips this check.
7. Add the analysis.

An empty result stops the loop. The vCon is saved after the loop.

## Read the return value

Returns the uuid, or `None` when the vCon is missing. A transcription failure after all retries raises, and the vCon goes to the dead letter queue. Missing credentials or a missing `api` raise the same way.

## Inspect the vCon changes

One analysis entry per transcribed dialog. The direct path can also set `duration` on a dialog.

| Field | Value |
|---|---|
| `type` | `transcript` |
| `dialog` | Dialog index |
| `vendor` | `deepgram` |
| `body` | Direct path: Deepgram's first alternative, with `detected_language` added. LiteLLM path: an object with `transcript` |
| `encoding` | `json` |
| `vendor_schema` | `opts`, with credential-like option names removed |

## Copy a configuration example

```yaml
links:
  transcribe_deepgram:
    module: links.transcribe
    options:
      vendor: deepgram
      vendor_options:
        DEEPGRAM_KEY: your-deepgram-key
        minimum_duration: 30
        minimum_confidence: 0.5
        api:
          model: nova-3
          smart_format: true
```

## Track the metrics

`conserver.link.deepgram.transcription_time`, `conserver.link.deepgram.transcription_failures` and `conserver.link.deepgram.confidence`. See [Metrics](../metrics.md).
