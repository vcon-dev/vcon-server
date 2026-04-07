# analyze_vcon

Performs AI-powered analysis on the entire vCon object (rather than a single dialog) using an OpenAI GPT model. The whole vCon is serialized to JSON and sent to the model, which must return a structured JSON response. The result is stored as a single analysis entry on the vCon.

## Prerequisites

- `OPENAI_API_KEY` environment variable (or provided in options)

## Configuration

```yaml
links:
  analyze_vcon:
    module: links.analyze_vcon
    options:
      model: gpt-3.5-turbo-16k
      prompt: "Analyze this vCon and return a JSON object with your analysis."
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `prompt` | string | `"Analyze this vCon and return a JSON object with your analysis."` | User-level instruction given to the model |
| `analysis_type` | string | `json_analysis` | Type name stored on the resulting analysis entry |
| `model` | string | `gpt-3.5-turbo-16k` | OpenAI model to use |
| `sampling_rate` | float | `1` | Fraction of vCons to process (1 = 100 %, 0.5 = 50 %) |
| `temperature` | int | `0` | Model temperature (0–1); 0 gives the most deterministic output |
| `system_prompt` | string | `"You are a helpful assistant that analyzes conversation data and returns structured JSON output."` | System-level context prompt |
| `remove_body_properties` | bool | `true` | Strip `body` fields from dialogs before sending to save tokens |
| `OPENAI_API_KEY` | string | — | OpenAI API key (overrides environment variable) |

## Example

```yaml
chains:
  full_vcon_analysis:
    links:
      - analyze_vcon:
          model: gpt-3.5-turbo-16k
          prompt: |
            Analyze this vCon and return a JSON object containing:
            - summary: a two-sentence summary
            - sentiment: overall sentiment (positive/neutral/negative)
            - topics: list of key topics
          remove_body_properties: true
    storages:
      - postgres
    ingress_lists:
      - transcribed
    enabled: 1
```

## Output

Adds a `json_analysis` entry to the vCon:

```json
{
  "analysis": [
    {
      "type": "json_analysis",
      "vendor": "openai",
      "dialog": 0,
      "body": {
        "summary": "Customer called about a billing dispute...",
        "sentiment": "negative",
        "topics": ["billing", "refund"]
      }
    }
  ]
}
```

## Behavior

- Skips the vCon if a `json_analysis` entry (or the configured `analysis_type`) already exists
- Respects `sampling_rate` to process only a fraction of vCons
- Validates that the model response is valid JSON before storing
- Retries API calls with exponential backoff (up to 6 attempts)
