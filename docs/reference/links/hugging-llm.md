# hugging_llm_link

Sends a vCon's transcripts to a Hugging Face language model, through the hosted API or a local model.

Module: `links.hugging_llm_link`

!!! danger "Known issue"
    The link does not work as written. See [the known issues](#check-the-known-issues) before adding it to a chain. Its tests in the repo are commented out.

## Set the options

The module has no `default_options`. Its defaults come from the `LLMConfig` dataclass.

| Option | Type | Default | Description |
|---|---|---|---|
| `HUGGINGFACE_API_KEY` | string | none | Bearer token for the hosted API |
| `model` | string | `meta-llama/Llama-2-70b-chat-hf` | Model name |
| `use_local_model` | bool | `false` | Runs the model in the worker through `transformers`, on CPU |
| `max_length` | int | `1000` | Generation length |
| `temperature` | float | `0.7` | Sampling temperature |

The local path needs an optional dependency group and a model backend such as torch:

```bash
uv sync --group conserver --group conserver-local
```

## Follow the processing steps

1. Load the vCon. Stop if it already has an `llm_analysis` entry.
2. Join the `body.transcript` text of every `transcript` analysis. Stop if there is none, so transcripts that keep their text in `body.text` count as missing.
3. Call the model with a fixed prompt that asks for a summary, sentiment and key points.
4. Add the analysis and save the vCon.

## Check the known issues

Step 4 raises `TypeError`, because `_add_analysis_to_vcon` calls `add_analysis` with no `dialog`, which `common/vcon.py` requires. Any vCon that reaches that step goes to the dead letter queue.

On the hosted API path the code also calls the async `analyze` method without awaiting it, so no request is made.

`conserver/links/hugging_llm_link/main.py` defines a separate `HuggingLLMLink` class. It has no `run` function and the worker does not use it.

## Read the return value

Returns the uuid when the vCon already has the analysis, has no transcript, or the model call fails. The failure in step 4 raises.

## Inspect the vCon changes

None as the code stands. The code is written to add an entry of type `llm_analysis` with vendor `huggingface`, a `body` holding `analysis`, `model` and `parameters`, and a `vendor_schema` holding the options.

## Copy a configuration example

```yaml
links:
  hf_analysis:
    module: links.hugging_llm_link
    options:
      HUGGINGFACE_API_KEY: your-hugging-face-token
      model: meta-llama/Llama-2-70b-chat-hf
      max_length: 1000
      temperature: 0.7
```

## Track the metrics

`conserver.link.huggingface.llm_time` and `conserver.link.huggingface.llm_failures`. See [Metrics](../metrics.md).
