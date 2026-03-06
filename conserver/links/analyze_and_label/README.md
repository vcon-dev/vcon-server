# Analyze and Label Link

## Overview

The `analyze_and_label` link is a powerful component of the vCon server that automatically analyzes dialog content and generates relevant labels/tags for categorization. It uses OpenAI's language models to process various dialog formats (transcripts, messages, chats, emails) and extract meaningful labels that are then applied as tags to the vCon.

## How It Works

1. The link retrieves a vCon from Redis storage
2. For each dialog in the vCon, it checks if a source analysis (typically of type "transcript") is present
3. It extracts the text content from the source analysis (from the specified location in the configuration)
4. It sends the text to OpenAI's API with a customizable prompt
5. It processes the API response to extract labels
6. It adds the analysis as a new analysis object to the vCon
7. It applies each extracted label as a tag to the vCon

## Supported Dialog Formats

The link is designed to handle various text formats that might appear in dialogs, including:

- **Standard Transcripts**: Plain text transcripts of conversations
- **Email Format**: Text with headers, subject, body, etc.
- **Chat Format**: Text with timestamps and speaker identification
- **Message Format**: Text with headers and body

The link is able to intelligently process these different formats and extract appropriate labels regardless of the format.

## Configuration Options

The link accepts the following configuration options:

| Option | Description | Default |
|--------|-------------|--------|
| `prompt` | The prompt sent to OpenAI for analysis | "Analyze this transcript and provide a list of relevant labels for categorization..." |
| `analysis_type` | The type assigned to the analysis output | "labeled_analysis" |
| `model` | The OpenAI model to use | "gpt-4-turbo" |
| `sampling_rate` | Rate at which to run the analysis (1 = 100%, 0.5 = 50%, etc.) | 1 |
| `temperature` | The temperature parameter for the OpenAI API | 0.2 |
| `source.analysis_type` | The type of analysis to use as source | "transcript" |
| `source.text_location` | The JSON path to the text within the source analysis | "body.paragraphs.transcript" |
| `response_format` | Format specification for the OpenAI API response | `{"type": "json_object"}` |
| `OPENAI_API_KEY` | The OpenAI API key (required but not defined in defaults) | None |

## Usage Example

```python
from server.links.analyze_and_label import run

# Run with default options (requires OPENAI_API_KEY in the options)
run(
    vcon_uuid="your-vcon-uuid",
    link_name="analyze_and_label",
    opts={
        "OPENAI_API_KEY": "your-openai-api-key",
        # Optionally override other defaults
        "prompt": "Identify key topics, sentiments, and issues in this conversation. Return your response as a JSON object with a single key 'labels' containing an array of strings.",
        "model": "gpt-3.5-turbo"
    }
)
```

## Customizing Label Generation

You can customize the label generation process by modifying the `prompt` parameter. The prompt should instruct the model to return labels in a specific format - a JSON object with a "labels" key containing an array of strings.

Example specialized prompts:

- **Support Issues**: "Analyze this transcript and identify the specific support issues mentioned. Return your response as a JSON object with a single key 'labels' containing an array of issue categories."
- **Sentiment Analysis**: "Analyze this conversation and identify the customer's sentiments and emotional states. Return your response as a JSON object with a single key 'labels' containing an array of sentiment descriptors."
- **Product Mentions**: "Identify all products or services mentioned in this transcript. Return your response as a JSON object with a single key 'labels' containing an array of product names."

## Error Handling

The link includes robust error handling:

- Exponential backoff retry mechanism for API calls
- JSON parsing error handling
- Logging of errors and performance metrics

## Testing

The link includes comprehensive tests for all functionality. To run the tests with actual OpenAI API calls (optional):

```bash
# Set environment variables
export OPENAI_API_KEY="your-api-key"
export RUN_OPENAI_ANALYZE_LABEL_TESTS=1

# Run the tests
pytest server/links/analyze_and_label/tests/test_analyze_and_label.py
```

Without setting `RUN_OPENAI_ANALYZE_LABEL_TESTS=1`, tests will run with mocked API responses.

## Metrics and Monitoring

The link emits several metrics for monitoring:

- `conserver.link.openai.labels_added`: Number of labels added per run
- `conserver.link.openai.analysis_time`: Time taken for analysis
- `conserver.link.openai.json_parse_failures`: Count of JSON parsing failures
- `conserver.link.openai.analysis_failures`: Count of overall analysis failures

## Integration with vCon Structure

The link integrates with the vCon structure in two ways:

1. It adds a new analysis object with the `labeled_analysis` type (or the configured type)
2. It adds tags to the vCon based on the extracted labels

This allows for both structured access to the full analysis and quick filtering/categorization using the applied tags.