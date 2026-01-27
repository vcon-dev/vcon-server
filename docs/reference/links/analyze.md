# analyze

Analyzes vCon content using AI (OpenAI GPT models).

## Configuration

```yaml
links:
  analyze:
    module: links.analyze
    options:
      model: gpt-4
      temperature: 0.3
      prompt: "Analyze this conversation..."
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | `gpt-4` | OpenAI model |
| `temperature` | float | `0.3` | Response randomness (0-1) |
| `prompt` | string | Default | Analysis prompt |
| `max_tokens` | int | `1000` | Maximum response tokens |
| `timeout` | int | `60` | Request timeout in seconds |

## Requirements

- `OPENAI_API_KEY` environment variable

## Example

```yaml
chains:
  analysis:
    links:
      - analyze:
          model: gpt-4
          prompt: |
            Analyze this conversation and provide:
            1. Summary (2-3 sentences)
            2. Key topics discussed
            3. Action items
            4. Overall sentiment
    storages:
      - postgres
    ingress_lists:
      - transcribed
    enabled: 1
```

## Output

Adds analysis to vCon:

```json
{
  "analysis": [
    {
      "type": "summary",
      "vendor": "openai",
      "body": {
        "summary": "Customer called about billing issue...",
        "topics": ["billing", "refund"],
        "action_items": ["Process refund"],
        "sentiment": "negative"
      }
    }
  ]
}
```
