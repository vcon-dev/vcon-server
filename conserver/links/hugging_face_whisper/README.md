# Hugging Face Whisper Link

The Hugging Face Whisper link is a specialized plugin that performs speech-to-text transcription on audio recordings in vCon dialogs using Hugging Face's implementation of the Whisper ASR service. It provides high-quality transcription with support for various audio formats and robust error handling.

## Features

- Speech-to-text transcription using Hugging Face's Whisper service
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
    "API_URL": "https://xxxxxx.us-east-1.aws.endpoints.huggingface.cloud",  # Hugging Face API endpoint
    "API_KEY": "Bearer hf_XXXXX",  # Hugging Face API key
    "Content-Type": "audio/flac",  # Content type of the audio files
}
```

### Options Description

- `minimum_duration`: Minimum duration in seconds for recordings to process
- `API_URL`: The Hugging Face API endpoint URL
- `API_KEY`: Your Hugging Face API key (should be set via environment variables)
- `Content-Type`: MIME type of the audio files being processed

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. For each dialog in the vCon:
   - Checking if it's a recording with sufficient duration
   - Verifying if it's already transcribed
   - Retrieving the audio content (from inline body or external URL)
   - Verifying file integrity if signature is provided
   - Transcribing the audio using Hugging Face's Whisper service
   - Adding the transcription to the vCon
3. Storing the updated vCon back in Redis

## Transcription Output

The transcription includes:
- `text`: The transcribed text
- Additional metadata from the Hugging Face Whisper API response
- Vendor schema with configuration details (excluding API key)

## Error Handling

- Implements retry logic with exponential backoff
- Maximum of 6 retry attempts
- File integrity verification
- Logs failures and tracks metrics for transcription failures
- Graceful handling of various error conditions

## Metrics

The link tracks the following metrics:
- `conserver.link.hugging_face_whisper.transcription_time`: Time taken for transcription
- `conserver.link.hugging_face_whisper.transcription_failures`: Count of transcription failures

## Dependencies

- Requests library for API communication and external file retrieval
- Tenacity for retry logic
- Redis for vCon storage
- Custom utilities:
  - vcon_redis
  - logging_utils
  - metrics
  - error_tracking

## Requirements

- Hugging Face API key must be provided (preferably via environment variables)
- Redis connection must be configured
- Audio recordings must be accessible (either inline or via URL)
- Appropriate permissions for vCon access and storage 