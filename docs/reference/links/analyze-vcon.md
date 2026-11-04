# analyze_vcon

Sends the whole vCon to an LLM and stores the JSON reply as one analysis entry.

Module: `links.analyze_vcon`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `prompt` | string | `Analyze this vCon and return a JSON object with your analysis.` | Placed before the vCon JSON |
| `analysis_type` | string | `json_analysis` | The `type` of the analysis entry |
| `model` | string | `gpt-3.5-turbo-16k` | Model name |
| `sampling_rate` | float | `1` | See [filter options](index.md#set-the-shared-filter-options) |
| `temperature` | float | `0` | Sampling temperature |
| `system_prompt` | string | `You are a helpful assistant that analyzes conversation data and returns structured JSON output.` | System message |
| `remove_body_properties` | bool | `true` | Drops each dialog's `body` from the copy sent to the model |
| `only_if` | dict | none | See [filter options](index.md#set-the-shared-filter-options) |

The link also takes the [LLM client options](index.md#set-the-llm-client-options). One of those groups is required.

## Follow the processing steps

1. Merge the options, load the vCon, and apply `only_if` and `sampling_rate`.
2. Stop if the vCon already has an entry of this `analysis_type`.
3. Copy the vCon and, by default, drop the dialog bodies from the copy. Parties, attachments and analysis go to the model as they are.
4. Call the model in JSON mode, with up to 6 attempts.
5. Check that the reply parses as JSON, then add the analysis and save.

## Check the known issues

If the text of `system_prompt` appears anywhere in the vCon, the call fails with a `NameError` and the link raises after its retries. This happens when an earlier `analyze_vcon` link with the same `system_prompt` and a different `analysis_type` ran on the vCon, since `vendor_schema` records the prompt. Give each link its own `system_prompt`, or run [`diet`](diet.md) with `remove_system_prompts` between them.

## Read the return value

Returns the uuid, including when the vCon is skipped. A model failure or a reply that is not JSON raises, and the vCon goes to the dead letter queue. A missing vCon raises `AttributeError`, unless `only_if` is set, which then skips it and returns the uuid.

## Inspect the vCon changes

One analysis entry.

| Field | Value |
|---|---|
| `type` | `analysis_type` |
| `dialog` | `0`, though the entry covers the whole vCon |
| `vendor` | `openai`, whichever client group is in use |
| `body` | The parsed JSON value |
| `encoding` | `json` |
| `vendor_schema` | `model`, `prompt` and `system_prompt` |

## Copy a configuration example

```yaml
links:
  call_review:
    module: links.analyze_vcon
    options:
      OPENAI_API_KEY: your-openai-key
      model: gpt-4.1
      analysis_type: call_review
      prompt: Return a JSON object with keys outcome and next_step.
```

## Track the metrics

`conserver.link.openai.analysis_time`, `conserver.link.openai.analysis_failures` and `conserver.link.openai.invalid_json`. See [Metrics](../metrics.md).
