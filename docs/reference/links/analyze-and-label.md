# analyze_and_label

Analyzes vCon dialog content with an OpenAI model and applies the returned labels as tags on the vCon. The model is prompted to return a JSON object with a `labels` array; each label is then added as both a structured analysis entry and a vCon tag.

## Prerequisites

- `OPENAI_API_KEY` environment variable (or provided in options)

## Configuration

```yaml
links:
  analyze_and_label:
    module: links.analyze_and_label
    options:
      model: gpt-4-turbo
      prompt: "Analyze this transcript and provide a list of relevant labels..."
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `prompt` | string | `"Analyze this transcript and provide a list of relevant labels for categorization. Return your response as a JSON object with a single key 'labels' containing an array of strings."` | Prompt sent to the model; must instruct the model to return `{"labels": [...]}` |
| `analysis_type` | string | `labeled_analysis` | Type name stored on the resulting analysis entry |
| `model` | string | `gpt-4-turbo` | OpenAI model to use |
| `sampling_rate` | float | `1` | Fraction of vCons to process (1 = 100 %, 0.5 = 50 %) |
| `temperature` | float | `0.2` | Model temperature (0–1) |
| `source.analysis_type` | string | `transcript` | Type of analysis to read as input text |
| `source.text_location` | string | `body.paragraphs.transcript` | Dot-separated path to the text field within the source analysis |
| `response_format` | dict | `{"type": "json_object"}` | OpenAI response format parameter |
| `OPENAI_API_KEY` | string | — | OpenAI API key (overrides environment variable) |

## Example

```yaml
chains:
  label_calls:
    links:
      - analyze_and_label:
          model: gpt-4-turbo
          prompt: |
            Identify key topics, sentiments, and issues in this conversation.
            Return your response as a JSON object with a single key 'labels'
            containing an array of strings.
          sampling_rate: 1
          temperature: 0.2
    storages:
      - postgres
    ingress_lists:
      - transcribed
    enabled: 1
```

## Output

Adds a `labeled_analysis` entry to the vCon and applies each returned label as a tag:

```json
{
  "analysis": [
    {
      "type": "labeled_analysis",
      "vendor": "openai",
      "dialog": 0,
      "body": "{\"labels\": [\"billing\", \"refund\", \"escalation\"]}"
    }
  ]
}
```

The vCon will also have tags `billing`, `refund`, and `escalation` applied.

## Behavior

- Skips dialogs that have no source analysis of the configured type
- Skips dialogs that already have a `labeled_analysis` (or the configured `analysis_type`)
- Respects `sampling_rate` to process only a fraction of vCons
- Retries API calls with exponential backoff (up to 6 attempts)
