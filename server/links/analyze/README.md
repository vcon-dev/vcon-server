# Analyze Link

The Analyze link is a powerful plugin that performs AI-powered analysis on vCon transcripts using OpenAI's GPT models. It can generate various types of analysis, such as summaries, sentiment analysis, or any custom analysis based on the provided prompt.

## Features

- Flexible analysis types with customizable prompts
- Support for OpenAI's GPT models (default: gpt-3.5-turbo-16k)
- Configurable sampling rate for processing
- Automatic retry mechanism with exponential backoff
- Metrics tracking for analysis time and failures
- Support for different source types and text locations

## Configuration Options

```python
default_options = {
    "prompt": "Summarize this transcript in a few sentences.",
    "analysis_type": "summary",
    "model": "gpt-3.5-turbo-16k",
    "sampling_rate": 1,
    "temperature": 0,
    "source": {
        "analysis_type": "transcript",
        "text_location": "body.paragraphs.transcript",
    },
}
```

### Options Description

- `prompt`: The instruction given to the AI model for analysis
- `analysis_type`: The type of analysis to be performed (e.g., "summary", "sentiment")
- `model`: The OpenAI model to use for analysis
- `sampling_rate`: Rate at which vCons should be processed (0-1)
- `temperature`: Controls randomness in the model's output (0-1)
- `source`: Configuration for the input source
  - `analysis_type`: Type of source analysis to use
  - `text_location`: Path to the text content in the source analysis

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Applying configured filters and sampling
3. For each dialog in the vCon:
   - Retrieves the source text based on configuration
   - Generates analysis using OpenAI
   - Adds the analysis to the vCon
4. Stores the updated vCon back in Redis

## Error Handling

- Implements retry logic with exponential backoff
- Maximum of 6 retry attempts
- Logs failures and tracks metrics for analysis failures

## Metrics

The link tracks the following metrics:
- `conserver.link.openai.analysis_time`: Time taken for analysis
- `conserver.link.openai.analysis_failures`: Count of analysis failures

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