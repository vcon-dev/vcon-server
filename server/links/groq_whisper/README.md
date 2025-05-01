# Groq Whisper Link

The Groq Whisper link is a specialized plugin that performs speech-to-text transcription on audio recordings in vCon dialogs using Groq's implementation of the Whisper ASR service. It provides high-quality transcription with support for various audio formats and robust error handling.

## Features

- Speech-to-text transcription using Groq's Whisper service
- Support for both inline and external audio files
- File integrity verification with signature checking
- Minimum duration filtering for recordings
- Automatic retry mechanism with exponential backoff
- Metrics tracking for transcription time and failures
- Support for various audio formats (default: FLAC)

## Configuration Options

```python
default_options = {
    "minimum_duration": 30,  # Minimum duration in seconds for recordings to process
    "API_KEY": os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY"),  # Groq API key
    "Content-Type": "audio/flac",  # Content type of the audio files
}
```

### Options Description

- `minimum_duration`: Minimum duration in seconds for recordings to process
- `API_KEY`: Your Groq API key (should be set via environment variables)
- `Content-Type`: MIME type of the audio files being processed

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. For each dialog in the vCon:
   - Checking if it's a recording with sufficient duration
   - Verifying if it's already transcribed
   - Retrieving the audio content (from inline body or external URL)
   - Verifying file integrity if signature is provided
   - Transcribing the audio using Groq's Whisper service
   - Adding the transcription to the vCon
3. Storing the updated vCon back in Redis

## Transcription Output

The transcription includes:
- `text`: The transcribed text
- Additional metadata from the Groq Whisper API response
- Vendor schema with configuration details (excluding API key)

## Error Handling

- Implements retry logic with exponential backoff
- Maximum of 6 retry attempts
- File integrity verification
- Logs failures and tracks metrics for transcription failures
- Graceful handling of various error conditions

## Metrics

The link tracks the following metrics:
- `conserver.link.groq_whisper.transcription_time`: Time taken for transcription
- `conserver.link.groq_whisper.transcription_failures`: Count of transcription failures

## Dependencies

- Groq Python client
- Requests library for external file retrieval
- Tenacity for retry logic
- Redis for vCon storage
- Custom utilities:
  - vcon_redis
  - logging_utils
  - metrics
  - error_tracking

## Requirements

- Groq API key must be provided (preferably via environment variables)
- Redis connection must be configured
- Audio recordings must be accessible (either inline or via URL)
- Appropriate permissions for vCon access and storage

## Installation

1. Install the required dependencies:

```bash
poetry add groq
```

2. Set your Groq API key in the environment:

```bash
export GROQ_API_KEY=your_groq_api_key_here
```

Alternatively, you can add the API key to your `.env` file:

```
GROQ_API_KEY=your_groq_api_key_here
```

## Configuration

The link accepts the following configuration options:

| Option | Description | Default |
|--------|-------------|---------|
| `API_KEY` | Groq API key for authentication | From GROQ_API_KEY environment variable |
| `minimum_duration` | Minimum duration (in seconds) of audio to transcribe | 30 |

## Usage

To use this link in a vCon processing chain:

```python
from server.links.groq_whisper import run

result = run(
    vcon_uuid="your-vcon-uuid",
    link_name="groq_whisper",
    opts={
        "minimum_duration": 60  # Optional override
    }
)
```

## How It Works

1. The link retrieves the vCon object from Redis
2. For each recording dialog in the vCon:
   - Skips dialogs shorter than the minimum duration
   - Skips dialogs that already have a transcript
   - Extracts audio content (from inline base64 or external URL)
   - Sends the audio to Groq's Whisper API for transcription
   - Adds transcription results as a new analysis entry
3. Stores the updated vCon back to Redis

## Testing

To run the unit tests (with mocked API):

```bash
# Set a dummy API key for testing (not required, will be set by the test automatically)
export GROQ_API_KEY=test_api_key_for_testing

# Run the tests
poetry run pytest server/links/groq_whisper/test_groq_whisper.py -v
```

### Integration Testing

The test suite also includes integration tests that make real API calls to Groq if a valid API key is available. By default, these tests are skipped if a valid API key is not provided or if it's the test placeholder.

To run the integration tests:

```bash
# Set your real Groq API key
export GROQ_API_KEY=your_actual_groq_api_key

# Run just the integration tests
poetry run python -m server.links.groq_whisper.test_groq_whisper

# Or run all tests including integration tests
poetry run pytest server/links/groq_whisper/test_groq_whisper.py -v
```

**Important Notes:**
- The GROQ_API_KEY environment variable must be set **before** running the tests
- If you see "Groq API key not configured" in the test output, it means your key wasn't recognized
- The key might not be recognized if you set it in a different shell or after running the tests
- Integration tests create synthetic audio samples which might not yield meaningful transcriptions
- Running integration tests will use your Groq API quota and may incur charges

## Response Format

The Groq Whisper API returns transcription results in the following format:

```json
{
  "text": "The complete transcription text.",
  "chunks": [
    {
      "text": "Chunk of transcription",
      "timestamp": [0.0, 5.0]
    },
    {
      "text": "Another chunk",
      "timestamp": [5.1, 10.0]
    }
  ],
  "language": "en"
}
```

This response is stored in the vCon's analysis section as a transcript entry. 