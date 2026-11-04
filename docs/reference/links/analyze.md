# analyze

Sends each dialog's transcript to an LLM and stores the reply as analysis.

Module: `links.analyze`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | `""` | Placed before the transcript in the user message |
| `analysis_type` | string | `summary` | The `type` of the analysis entry |
| `model` | string | `gpt-3.5-turbo-16k` | Model name |
| `sampling_rate` | float | `1` | See [filter options](index.md#set-the-shared-filter-options) |
| `temperature` | float | `0` | Sampling temperature |
| `system_prompt` | string | `You are a helpful assistant.` | System message |
| `source.analysis_type` | string | `transcript` | Analysis entry to read |
| `source.text_location` | string | `body.paragraphs.transcript` | Path to the text. See [transcript text](index.md#point-analysis-at-the-transcript-text) |
| `only_if` | dict | none | See [filter options](index.md#set-the-shared-filter-options) |
| `send_ai_usage_data_to_url` | string | `""` | See [AI usage](index.md#report-ai-usage-to-an-endpoint) |
| `ai_usage_api_token` | string | `""` | See [AI usage](index.md#report-ai-usage-to-an-endpoint) |

The link also takes the [LLM client options](index.md#set-the-llm-client-options). One of those groups is required.

## Follow the processing steps

1. Merge the options over `default_options` and load the vCon.
2. Apply `only_if` and `sampling_rate`.
3. For each dialog, read the source text. Skip the dialog if the text is missing or if it already has an entry of this `analysis_type`.
4. Call the model, with up to 6 attempts.
5. Save the vCon after the last dialog.

A second `analyze` link needs its own `analysis_type`. With the same value it skips every dialog.

## Read the return value

Returns the uuid, including when the vCon is skipped. A model failure after all retries raises, and the vCon goes to the dead letter queue. A missing vCon raises `AttributeError`, unless `only_if` is set, which then skips it and returns the uuid.

## Inspect the vCon changes

One analysis entry per processed dialog.

| Field | Value |
|---|---|
| `type` | `analysis_type` |
| `dialog` | Dialog index |
| `vendor` | Derived from the client options: `openai`, `azure`, or with LiteLLM the provider inferred from the model name |
| `body` | The model's reply as a string |
| `encoding` | `none` |
| `vendor_schema` | `model` and `prompt` |

## Copy a configuration example

```yaml
links:
  summarize:
    module: links.analyze
    options:
      OPENAI_API_KEY: your-openai-key
      model: gpt-4.1
      analysis_type: summary
      prompt: Summarize this conversation in two sentences.
      source:
        analysis_type: transcript
        text_location: body.text
```

## Track the metrics

`conserver.link.openai.analysis_time` and `conserver.link.openai.analysis_failures`. See [Metrics](../metrics.md).
