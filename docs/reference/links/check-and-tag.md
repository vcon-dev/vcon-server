# check_and_tag

Evaluates dialog content against a yes/no question using an OpenAI model and conditionally applies a tag if the answer is positive. Useful for quality-assurance checks such as greeting compliance, issue resolution, or call-handling standards.

## Prerequisites

- `OPENAI_API_KEY` environment variable (or provided in options)

## Configuration

```yaml
links:
  check_and_tag:
    module: links.check_and_tag
    options:
      tag_name: portal:eval_proper_greeting
      tag_value: "true"
      evaluation_question: "Did the specialist identify United Way 211 with a warm tone and thank the caller?"
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tag_name` | string | **Required** | Name of the tag to apply when the evaluation is positive |
| `tag_value` | string | **Required** | Value of the tag to apply when the evaluation is positive |
| `evaluation_question` | string | **Required** | Question the model evaluates against the dialog text (should yield a yes/no answer) |
| `analysis_type` | string | `tag_evaluation` | Type name stored on the resulting analysis entry |
| `model` | string | `gpt-5` | OpenAI model to use |
| `sampling_rate` | float | `1` | Fraction of vCons to process (1 = 100 %, 0.5 = 50 %) |
| `source.analysis_type` | string | `transcript` | Type of analysis to read as input text |
| `source.text_location` | string | `body` | Dot-separated path to the text field within the source analysis |
| `response_format` | dict | `{"type": "json_object"}` | OpenAI response format parameter |
| `verbosity` | string | `low` | Response verbosity hint passed to the model (`low`, `medium`, `high`) |
| `minimal_reasoning` | bool | `true` | Hint for faster model responses |
| `OPENAI_API_KEY` | string | — | OpenAI API key (overrides environment variable) |

## Example

```yaml
chains:
  qa_greeting:
    links:
      - check_and_tag:
          tag_name: qa:proper_greeting
          tag_value: pass
          evaluation_question: "Did the agent introduce themselves by name and greet the caller warmly?"
          model: gpt-5
          source:
            analysis_type: transcript
            text_location: body
    storages:
      - postgres
    ingress_lists:
      - transcribed
    enabled: 1
```

## Output

Adds a `tag_evaluation` analysis entry to the vCon. If the evaluation is positive, the specified tag is also applied:

```json
{
  "analysis": [
    {
      "type": "tag_evaluation",
      "vendor": "openai",
      "dialog": 0,
      "body": {
        "link_name": "check_and_tag",
        "tag": "qa:proper_greeting:pass",
        "applies": true
      }
    }
  ]
}
```

## Behavior

- Raises a `ValueError` if `tag_name`, `tag_value`, or `evaluation_question` are missing
- Skips dialogs that have no source analysis of the configured type
- Skips dialogs that already have a `tag_evaluation` entry (or the configured `analysis_type`)
- Respects `sampling_rate` to process only a fraction of vCons
- Retries API calls with exponential backoff (up to 6 attempts)
