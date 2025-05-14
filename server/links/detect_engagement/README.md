# Engagement Detection Link

This link analyzes conversations to determine if both the customer and agent are engaged in the dialogue. It uses OpenAI's GPT-4.1 model to analyze transcripts and determine engagement status.

## Features

- Analyzes each dialog in a vCon to detect engagement
- Uses GPT-4.1 for accurate conversation analysis
- Stores results both as analysis and tags
- Includes retry logic and error handling
- Provides metrics for monitoring

## Configuration Options

The link can be configured with the following options:

```python
default_options = {
    "prompt": "Did both the customer and the agent speak? Respond with 'true' if yes, 'false' if not. Respond with only 'true' or 'false'.",
    "analysis_type": "engagement_analysis",
    "model": "gpt-4.1",
    "sampling_rate": 1,
    "temperature": 0.2,
    "source": {
        "analysis_type": "transcript",
        "text_location": "body.paragraphs.transcript",
    }
}
```

### Options Description

- `prompt`: The prompt used to analyze engagement
- `analysis_type`: The type of analysis to store in the vCon
- `model`: The OpenAI model to use (default: gpt-4.1)
- `sampling_rate`: Rate at which to sample vCons for analysis
- `temperature`: Model temperature for response generation
- `source`: Configuration for where to find the transcript data

## Output

The link adds two types of data to the vCon:

1. Analysis: Stores the engagement status as an analysis object
2. Tags: Adds an "engagement" tag with the boolean result

## Metrics

The link provides the following metrics:

- `conserver.link.openai.engagement_detected`: Gauge for engagement status
- `conserver.link.openai.engagement_analysis_time`: Time taken for analysis
- `conserver.link.openai.engagement_analysis_failures`: Count of analysis failures

## Requirements

- OpenAI API key must be set in the environment
- vCon must contain transcript data 