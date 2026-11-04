# analyze_and_label

Asks an LLM for a list of labels per dialog, stores the reply as analysis and applies each label as a tag.

Module: `links.analyze_and_label`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | `Analyze this transcript and provide a list of relevant labels for categorization. Return your response as a JSON object with a single key 'labels' containing an array of strings.` | Placed before the transcript |
| `analysis_type` | string | `labeled_analysis` | The `type` of the analysis entry |
| `model` | string | `gpt-4-turbo` | Model name |
| `sampling_rate` | float | `1` | See [filter options](index.md#set-the-shared-filter-options) |
| `temperature` | float | `0.2` | Sampling temperature |
| `source.analysis_type` | string | `transcript` | Analysis entry to read |
| `source.text_location` | string | `body.paragraphs.transcript` | Path to the text. See [transcript text](index.md#point-analysis-at-the-transcript-text) |
| `response_format` | dict | `{"type": "json_object"}` | Passed to the model call |
| `only_if` | dict | none | See [filter options](index.md#set-the-shared-filter-options) |

The link also takes the [LLM client options](index.md#set-the-llm-client-options). One of those groups is required. The system message is fixed in the code.

## Follow the processing steps

1. Merge the options, load the vCon, and apply `only_if` and `sampling_rate`.
2. For each dialog, read the source text. Skip the dialog if the text is missing or if it already has an entry of this `analysis_type`.
3. Call the model, with up to 6 attempts, and parse the reply as JSON.
4. Add the analysis, then add one tag for each item in `labels`.
5. Save the vCon after the last dialog.

If the reply is not valid JSON, the link stores the raw text, adds no tags, and counts `conserver.link.openai.json_parse_failures`. The chain continues.

## Read the return value

Returns the uuid, including when the vCon is skipped. A model failure after all retries raises, and the vCon goes to the dead letter queue. A missing vCon raises `AttributeError`, unless `only_if` is set, which then skips it and returns the uuid.

## Inspect the vCon changes

One analysis entry per processed dialog.

| Field | Value |
|---|---|
| `type` | `analysis_type` |
| `dialog` | Dialog index |
| `vendor` | `openai`, whichever client group is in use |
| `body` | The model's reply as a string |
| `encoding` | `json`, or `none` when the reply did not parse |
| `vendor_schema` | `model` and `prompt`, plus `parse_error` when the reply did not parse |

A label `billing` becomes the tag `billing:billing`. See [tag](tag.md#inspect-the-vcon-changes) for how tags are stored.

## Copy a configuration example

```yaml
links:
  label_calls:
    module: links.analyze_and_label
    options:
      OPENAI_API_KEY: your-openai-key
      model: gpt-4.1
      source:
        analysis_type: transcript
        text_location: body.text
```

## Track the metrics

`conserver.link.openai.analysis_time`, `conserver.link.openai.analysis_failures`, `conserver.link.openai.labels_added` and `conserver.link.openai.json_parse_failures`. See [Metrics](../metrics.md).
