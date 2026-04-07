# detect_engagement

Determines whether both the customer and the agent were actively engaged in a conversation, using an OpenAI model to evaluate each dialog transcript. The result (`true` or `false`) is stored as an analysis entry and also applied as an `engagement` tag on the vCon.

## Prerequisites

- `OPENAI_API_KEY` environment variable (or provided in options)

## Configuration

```yaml
links:
  detect_engagement:
    module: links.detect_engagement
    options:
      model: gpt-4.1
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `prompt` | string | `"Did both the customer and the agent speak? Respond with 'true' if yes, 'false' if not. Respond with only 'true' or 'false'."` | Prompt used to evaluate engagement |
| `analysis_type` | string | `engagement_analysis` | Type name stored on the resulting analysis entry |
| `model` | string | `gpt-4.1` | OpenAI model to use |
| `sampling_rate` | float | `1` | Fraction of vCons to process (1 = 100 %, 0.5 = 50 %) |
| `temperature` | float | `0.2` | Model temperature (0–1) |
| `source.analysis_type` | string | `transcript` | Type of analysis to read as input text |
| `source.text_location` | string | `body.paragraphs.transcript` | Dot-separated path to the text field within the source analysis |
| `OPENAI_API_KEY` | string | — | OpenAI API key (overrides environment variable) |

## Example

```yaml
chains:
  engagement_check:
    links:
      - detect_engagement:
          model: gpt-4.1
          temperature: 0.2
          source:
            analysis_type: transcript
            text_location: body.paragraphs.transcript
    storages:
      - postgres
    ingress_lists:
      - transcribed
    enabled: 1
```

## Output

Adds an `engagement_analysis` entry and an `engagement` tag to the vCon:

```json
{
  "analysis": [
    {
      "type": "engagement_analysis",
      "vendor": "openai",
      "dialog": 0,
      "body": "true"
    }
  ]
}
```

The vCon will also have a tag `engagement: true` (or `engagement: false`).

## Behavior

- Skips dialogs that have no source transcript analysis
- Skips dialogs that already have an `engagement_analysis` entry
- Respects `sampling_rate` to process only a fraction of vCons
- Gracefully skips the vCon if no API credentials are configured
- Retries API calls with exponential backoff (up to 6 attempts)
