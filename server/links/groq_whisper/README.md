# Groq Whisper Link

A vCon-server link that provides automatic transcription of audio content using Groq's implementation of Whisper ASR.

## Overview

This link processes vCon objects containing audio recordings and transcribes them using Groq's Whisper API. The transcription results are added back to the vCon as analysis entries.

## Requirements

- Python 3.12+
- A valid Groq API key
- The `groq` Python package

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

To run the tests:

```bash
# Set a dummy API key for testing
export GROQ_API_KEY=test_api_key_for_testing

# Run the tests
pytest server/links/groq_whisper/test_groq_whisper.py -v
```

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