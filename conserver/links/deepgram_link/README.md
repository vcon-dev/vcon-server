# Deepgram Link

The Deepgram link is a specialized plugin that performs speech-to-text transcription on audio recordings in vCon dialogs using the Deepgram API. It supports automatic language detection and confidence scoring for transcription quality.

## Features

- Speech-to-text transcription using Deepgram's API
- Automatic language detection
- Confidence scoring for transcription quality
- Minimum duration filtering for recordings
- Automatic retry mechanism with exponential backoff
- Metrics tracking for transcription time and failures
- Support for URL-based audio sources
- **Comprehensive logging and code comments for observability and maintainability**

## Configuration Options

```python
default_options = {
    "minimum_duration": 60,  # Minimum duration in seconds for recordings to process
    "DEEPGRAM_KEY": None,   # Your Deepgram API key
    "api": {
        # Deepgram API options
        "model": "nova-2",
        "language": "en",
        "smart_format": True,
        "punctuate": True,
        "diarize": False,
        "utterances": False,
        "profanity_filter": False,
        "redact": False,
        "tier": "enhanced"
    }
}
```

### Options Description

- `minimum_duration`: Minimum duration in seconds for recordings to process
- `DEEPGRAM_KEY`: Your Deepgram API key
- `api`: Deepgram API configuration options
  - `model`: Deepgram model to use (e.g., "nova-2")
  - `language`: Language code (e.g., "en")
  - `smart_format`: Enable smart formatting
  - `punctuate`: Enable punctuation
  - `diarize`: Enable speaker diarization
  - `utterances`: Enable utterance detection
  - `profanity_filter`: Enable profanity filtering
  - `redact`: Enable redaction
  - `tier`: API tier to use (e.g., "enhanced")

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. For each dialog in the vCon:
   - Checking if it's a recording with a URL
   - Verifying it meets the minimum duration requirement
   - Checking if it's already transcribed
   - Transcribing the audio using Deepgram
   - Validating the transcription confidence
   - Adding the transcription to the vCon
3. Storing the updated vCon back in Redis

## Transcription Output

The transcription includes:
- `transcript`: The transcribed text
- `confidence`: Confidence score for the transcription
- `detected_language`: Automatically detected language
- `words`: Word-level details with timestamps
- Additional metadata based on API options

## Error Handling

- Implements retry logic with exponential backoff
- Maximum of 6 retry attempts
- Logs failures and tracks metrics for transcription failures
- Skips recordings with low confidence scores (< 0.5)

## Metrics

The link tracks the following metrics:
- `conserver.link.deepgram_link.transcription_time`: Time taken for transcription
- `conserver.link.deepgram_link.transcription_failures`: Count of transcription failures
- `conserver.link.deepgram_link.confidence`: Confidence score of transcriptions

## Logging and Observability

This link now features **comprehensive logging** at multiple levels (INFO, WARNING, ERROR, DEBUG) to provide:
- Start and end of processing for each vCon
- Option merging and configuration details
- Dialog filtering decisions (type, URL, duration)
- API request and response debug information
- Transcription timing and confidence values
- Error details with stack traces on failures
- Progress and status for each dialog

Additionally, the code is now thoroughly commented, explaining the purpose and logic of each function, block, and key decision point. This makes the codebase easier to maintain, debug, and extend.

## Dependencies

- Deepgram Python client
- Tenacity for retry logic
- Redis for vCon storage
- Custom utilities:
  - vcon_redis
  - logging_utils
  - metrics
  - error_tracking

## Requirements

- Deepgram API key must be provided in the options
- Redis connection must be configured
- Audio recordings must be accessible via URL
- Appropriate permissions for vCon access and storage 