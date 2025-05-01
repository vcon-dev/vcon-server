# HuggingFace LLM Link

A vCon Link component that processes conversation data using HuggingFace's language models. This link extracts transcripts from vCon documents and leverages LLMs to generate conversation analysis including summaries, sentiment analysis, and key discussion points.

## Overview

This link is part of the vCon processing pipeline and works alongside other links to provide comprehensive conversation analysis. It integrates with HuggingFace's models to provide:

- Conversation summaries
- Sentiment analysis
- Key discussion point extraction
- Configurable model parameters
- Support for both API and local model inference

## Configuration

The link can be configured through environment variables or the link configuration:

```env
HUGGINGFACE_API_KEY=your-api-key  # Required for API-based inference
```

Additional configuration options:
- `model`: HuggingFace model ID (default: "meta-llama/Llama-2-70b-chat-hf")
- `use_local_model`: Toggle local model inference (default: false)
- `max_length`: Maximum output length (default: 1000)
- `temperature`: Sampling temperature (default: 0.7)
- `top_p`: Nucleus sampling parameter (default: 0.95)
- `top_k`: Top-k sampling parameter (default: 50)

## Output Format

The link adds analysis results to the vCon document under the "llm_analysis" type:

```json
{
  "type": "llm_analysis",
  "vendor": "huggingface",
  "body": {
    "analysis": {
      "summary": "Brief overview of the conversation",
      "sentiment": "Overall sentiment analysis",
      "key_points": ["Key point 1", "Key point 2"]
    },
    "model": "meta-llama/Llama-2-70b-chat-hf",
    "parameters": {
      "max_length": 1000,
      "temperature": 0.7
    }
  }
}
```

## Error Handling

The link implements error handling for:
- API rate limiting
- Model loading failures
- Token length exceeded
- Network connectivity issues

Errors are logged using the application's logging system. 