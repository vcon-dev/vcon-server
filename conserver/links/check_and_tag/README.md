# Check and Tag Link

## Overview

The `check_and_tag` link is a specialized component of the vCon server that evaluates dialog content against a specific question to determine if a particular tag should be applied. It uses OpenAI's language models to process various dialog formats (transcripts, messages, chats, emails) and makes a binary decision about whether a specific tag applies based on an evaluation question.

## How It Works

1. The link retrieves a vCon from Redis storage
2. For each dialog in the vCon, it checks if a source analysis (typically of type "transcript") is present
3. It extracts the text content from the source analysis (from the specified location in the configuration)
4. It sends the text to OpenAI's API with an evaluation question to determine if the specified tag applies
5. It processes the API response to get a yes/no decision
6. It adds the analysis as a new analysis object to the vCon
7. If the evaluation is positive, it applies the specified tag to the vCon

## Supported Dialog Formats

The link is designed to handle various text formats that might appear in dialogs, including:

- **Standard Transcripts**: Plain text transcripts of conversations
- **Email Format**: Text with headers, subject, body, etc.
- **Chat Format**: Text with timestamps and speaker identification
- **Message Format**: Text with headers and body

The link is able to intelligently process these different formats and evaluate them against the specified question regardless of the format.

## Configuration Options

The link accepts the following configuration options:

| Option | Description | Default |
|--------|-------------|--------|
| `tag_name` | The name of the tag to apply if evaluation is positive | Required |
| `evaluation_question` | The question to evaluate against the dialog content | Required |
| `analysis_type` | The type assigned to the analysis output | "tag_evaluation" |
| `model` | The OpenAI model to use | "gpt-5" |
| `sampling_rate` | Rate at which to run the analysis (1 = 100%, 0.5 = 50%, etc.) | 1 |
| `temperature` | The temperature parameter for the OpenAI API | 0.2 |
| `source.analysis_type` | The type of analysis to use as source | "transcript" |
| `source.text_location` | The JSON path to the text within the source analysis | "body.paragraphs.transcript" |
| `response_format` | Format specification for the OpenAI API response | `{"type": "json_object"}` |
| `OPENAI_API_KEY` | The OpenAI API key (required but not defined in defaults) | None |

## Usage Example

```python
from server.links.check_and_tag import run

# Run with required tag_name and evaluation_question
run(
    vcon_uuid="your-vcon-uuid",
    link_name="check_and_tag",
    opts={
        "OPENAI_API_KEY": "your-openai-api-key",
        "tag_name": "portal:eval_proper_greeting",
        "evaluation_question": "Did the specialist identify United Way 211 with a warm tone and thank the caller?",
        "model": "gpt-5"
    }
)
```

## Customizing Tag Evaluation

You can customize the tag evaluation process by modifying the `evaluation_question` parameter. The question should be specific and clear to get accurate yes/no responses from the model.

Example evaluation questions:

- **Greeting Quality**: "Did the specialist identify United Way 211 with a warm tone and thank the caller?"
- **Issue Resolution**: "Was the customer's primary issue resolved during this conversation?"

- **Service Quality**: "Did the specialist demonstrate active listening and empathy throughout the conversation?"

## Error Handling

The link includes robust error handling:

- Exponential backoff retry mechanism for API calls
- JSON parsing error handling for evaluation responses
- Logging of errors and performance metrics
- Graceful handling of missing required parameters (tag_name, evaluation_question)

## Testing

The link includes comprehensive tests for all functionality. To run the tests with actual OpenAI API calls (optional):

```bash
# Set environment variables
export OPENAI_API_KEY="your-api-key"
export RUN_OPENAI_CHECK_TAG_TESTS=1

# Run the tests
pytest server/links/check_and_tag/tests/test_check_and_tag.py
```

Without setting `RUN_OPENAI_CHECK_TAG_TESTS=1`, tests will run with mocked API responses.

## Metrics and Monitoring

The link emits several metrics for monitoring:

- `conserver.link.openai.tags_applied`: Number of tags applied per run
- `conserver.link.openai.evaluation_time`: Time taken for evaluation
- `conserver.link.openai.json_parse_failures`: Count of JSON parsing failures
- `conserver.link.openai.evaluation_failures`: Count of overall evaluation failures

## Integration with vCon Structure

The link integrates with the vCon structure in two ways:

1. It adds a new analysis object with the `tag_evaluation` type (or the configured type) containing the evaluation result
2. It conditionally adds the specified tag to the vCon if the evaluation is positive

This allows for both structured access to the full evaluation analysis and quick filtering/categorization using the applied tags.