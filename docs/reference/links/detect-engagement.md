# detect_engagement

Asks an LLM whether both the customer and the agent spoke, then records the answer as analysis and a tag.

Module: `links.detect_engagement`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | `Did both the customer and the agent speak? Respond with 'true' if yes, 'false' if not. Respond with only 'true' or 'false'.` | Placed before the transcript |
| `analysis_type` | string | `engagement_analysis` | The `type` of the analysis entry |
| `model` | string | `gpt-4.1` | Model name |
| `sampling_rate` | float | `1` | See [filter options](index.md#set-the-shared-filter-options) |
| `temperature` | float | `0.2` | Sampling temperature |
| `source.analysis_type` | string | `transcript` | Analysis entry to read |
| `source.text_location` | string | `body.paragraphs.transcript` | Path to the text. See [transcript text](index.md#point-analysis-at-the-transcript-text) |
| `OPENAI_API_KEY` | string | `OPENAI_API_KEY` from the environment at import, or `""` | OpenAI key |
| `only_if` | dict | none | See [filter options](index.md#set-the-shared-filter-options) |

The link also takes the other [LLM client options](index.md#set-the-llm-client-options). This is the one LLM link that falls back to the environment for its key.

## Follow the processing steps

1. Merge the options, load the vCon, and apply `only_if` and `sampling_rate`.
2. Build the client. With no credentials the link logs a warning and skips the vCon.
3. For each dialog, read the source text. Skip the dialog if the text is missing or if it already has an entry of this `analysis_type`.
4. Call the model through the Responses API (`client.responses.create`), with up to 6 attempts. Only a reply equal to `true`, ignoring case and surrounding space, counts as engaged.
5. Add the analysis and the tag.
6. Save the vCon after the last dialog.

## Read the return value

Returns the uuid, including when the vCon is skipped. A model failure after all retries raises, and the vCon goes to the dead letter queue. A missing vCon raises `AttributeError`, unless `only_if` is set, which then skips it and returns the uuid.

## Inspect the vCon changes

One analysis entry per processed dialog.

| Field | Value |
|---|---|
| `type` | `analysis_type` |
| `dialog` | Dialog index |
| `vendor` | `openai`, whichever client group is in use |
| `body` | The string `true` or `false` |
| `encoding` | `none` |
| `vendor_schema` | `model`, `prompt` and `is_engaged` |

The link also adds the tag `engagement:true` or `engagement:false`. See [tag](tag.md#inspect-the-vcon-changes) for how tags are stored.

## Copy a configuration example

```yaml
links:
  engagement:
    module: links.detect_engagement
    options:
      OPENAI_API_KEY: your-openai-key
      source:
        analysis_type: transcript
        text_location: body.text
```

## Track the metrics

`conserver.link.openai.engagement_analysis_time`, `conserver.link.openai.engagement_analysis_failures` and `conserver.link.openai.engagement_detected`. See [Metrics](../metrics.md).
