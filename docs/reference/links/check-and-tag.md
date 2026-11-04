# check_and_tag

Asks an LLM a yes or no question about each dialog and adds a tag when the answer is yes.

Module: `links.check_and_tag`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `tag_name` | string | required | Name of the tag to add |
| `tag_value` | string | required | Value of the tag to add |
| `evaluation_question` | string | required | The question put to the model |
| `analysis_type` | string | `tag_evaluation` | The `type` of the analysis entry |
| `model` | string | `gpt-5` | Model name |
| `sampling_rate` | float | `1` | See [filter options](index.md#set-the-shared-filter-options) |
| `source.analysis_type` | string | `transcript` | Analysis entry to read |
| `source.text_location` | string | `body` | Path to the text. See [transcript text](index.md#point-analysis-at-the-transcript-text) |
| `response_format` | dict | `{"type": "json_object"}` | Passed to the model call |
| `verbosity` | string | `low` | In `default_options`, but no code reads it |
| `minimal_reasoning` | bool | `true` | In `default_options`, but no code reads it |
| `only_if` | dict | none | See [filter options](index.md#set-the-shared-filter-options) |

The link also takes the [LLM client options](index.md#set-the-llm-client-options). One of those groups is required. The call sets no temperature.

With the default `text_location` of `body`, a transcript whose body is an object reaches the model as the text form of that whole object. Set a narrower path such as `body.text`.

## Follow the processing steps

1. Raise `ValueError` if `tag_name`, `tag_value` or `evaluation_question` is empty.
2. Load the vCon and apply `only_if` and `sampling_rate`.
3. For each dialog, read the source text. Skip the dialog if the text is missing or if it already has an entry of this `analysis_type`.
4. Call the model, with up to 6 attempts. The link asks for a JSON object with a boolean `applies`.
5. Add the analysis, and add the tag when `applies` is true.
6. Save the vCon after the last dialog.

Several `check_and_tag` links in one chain each need their own `analysis_type`. With the same value, the second link skips every dialog.

## Read the return value

Returns the uuid, including when the vCon is skipped or missing. A model failure or a reply that is not JSON raises, and the vCon goes to the dead letter queue.

## Inspect the vCon changes

One analysis entry per processed dialog, whatever the answer.

| Field | Value |
|---|---|
| `type` | `analysis_type` |
| `dialog` | Dialog index |
| `vendor` | `openai`, whichever client group is in use |
| `body` | Object with `link_name`, `tag` as `name:value`, and `applies` |
| `encoding` | `json` |
| `vendor_schema` | `model` and `evaluation_question` |

When the answer is yes, the link adds the tag `tag_name:tag_value`. See [tag](tag.md#inspect-the-vcon-changes) for how tags are stored.

## Copy a configuration example

```yaml
links:
  check_refund:
    module: links.check_and_tag
    options:
      OPENAI_API_KEY: your-openai-key
      analysis_type: refund_check
      tag_name: refund
      tag_value: requested
      evaluation_question: Did the customer ask for a refund?
      source:
        analysis_type: transcript
        text_location: body.text
```

## Track the metrics

`conserver.link.openai.evaluation_time`, `conserver.link.openai.evaluation_failures` and `conserver.link.openai.tags_applied`. See [Metrics](../metrics.md).
