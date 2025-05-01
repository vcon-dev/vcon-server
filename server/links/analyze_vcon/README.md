# Analyze vCon Link

The Analyze vCon link is a specialized plugin that performs AI-powered analysis on entire vCon objects using OpenAI's GPT models. Unlike the standard analyze link that processes individual dialogs, this link analyzes the complete vCon structure and returns structured JSON output.

## Features

- Whole vCon analysis with structured JSON output
- Support for OpenAI's GPT models (default: gpt-3.5-turbo-16k)
- Configurable system prompts for analysis context
- Optional body property removal to optimize token usage
- Automatic retry mechanism with exponential backoff
- JSON response validation
- Metrics tracking for analysis time and failures

## Configuration Options

```python
default_options = {
    "prompt": "Analyze this vCon and return a JSON object with your analysis.",
    "analysis_type": "json_analysis",
    "model": "gpt-3.5-turbo-16k",
    "sampling_rate": 1,
    "temperature": 0,
    "system_prompt": "You are a helpful assistant that analyzes conversation data and returns structured JSON output.",
    "remove_body_properties": True,
}
```

### Options Description

- `prompt`: The instruction given to the AI model for analysis
- `analysis_type`: The type of analysis to be performed (e.g., "json_analysis")
- `model`: The OpenAI model to use for analysis
- `sampling_rate`: Rate at which vCons should be processed (0-1)
- `temperature`: Controls randomness in the model's output (0-1)
- `system_prompt`: Context-setting prompt for the AI model
- `remove_body_properties`: Whether to remove body properties from dialogs to optimize token usage

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Applying configured filters and sampling
3. Preparing the vCon data for analysis (optionally removing body properties)
4. Generating analysis using OpenAI with JSON response format
5. Validating the JSON response
6. Adding the analysis to the vCon
7. Storing the updated vCon back in Redis

## Error Handling

- Implements retry logic with exponential backoff
- Maximum of 6 retry attempts
- JSON response validation
- Logs failures and tracks metrics for analysis failures

## Metrics

The link tracks the following metrics:
- `conserver.link.openai.analysis_time`: Time taken for analysis
- `conserver.link.openai.analysis_failures`: Count of analysis failures
- `conserver.link.openai.invalid_json`: Count of invalid JSON responses

## Dependencies

- OpenAI Python client
- Tenacity for retry logic
- Redis for vCon storage
- Custom utilities:
  - vcon_redis
  - logging_utils
  - metrics
  - filters

## Requirements

- OpenAI API key must be provided in the options
- Redis connection must be configured
- Appropriate permissions for vCon access and storage 