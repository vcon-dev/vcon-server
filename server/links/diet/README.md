# Diet Link

The Diet link is a specialized plugin that helps reduce the size and content of vCon objects by selectively removing or modifying specific elements. It's particularly useful for data minimization, privacy protection, and optimizing storage.

## Features

- Selective removal of dialog body content
- Optional media redirection to external storage
- Removal of analysis data
- Filtering of attachments by MIME type
- Removal of system prompts to prevent LLM instruction injection
- In-place modification of vCon objects in Redis

## Configuration Options

```python
default_options = {
    "remove_dialog_body": False,  # Remove body content from dialogs
    "post_media_to_url": "",      # URL endpoint to store media (if empty, media is just removed)
    "remove_analysis": False,     # Remove all analysis data
    "remove_attachment_types": [], # List of attachment types to remove (e.g., ["image/jpeg", "audio/mp3"])
    "remove_system_prompts": False, # Remove system_prompt keys to prevent LLM instruction insertion
}
```

### Options Description

- `remove_dialog_body`: Whether to remove body content from dialogs
- `post_media_to_url`: URL endpoint to store media content (if empty, media is just removed)
- `remove_analysis`: Whether to remove all analysis data
- `remove_attachment_types`: List of MIME types to remove from attachments
- `remove_system_prompts`: Whether to remove system_prompt keys to prevent LLM instruction injection

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Applying configured modifications:
   - Removing dialog body content (optionally posting to external URL)
   - Removing analysis data if specified
   - Filtering attachments by MIME type
   - Removing system prompts if specified
3. Storing the modified vCon back in Redis

## Media Redirection

When `post_media_to_url` is configured, the link will:
1. Post the media content to the specified URL
2. Replace the body content with the URL to the stored content
3. Set the body_type to "url"
4. If the post fails, the body content will be removed

## Security Features

- Recursive removal of system_prompt keys to prevent LLM instruction injection attacks
- Selective removal of sensitive data types
- Option to redirect media to secure storage

## Dependencies

- Redis for vCon storage
- Requests library for media redirection
- Custom utilities:
  - logging_utils

## Requirements

- Redis connection must be configured
- Appropriate permissions for vCon access and storage
- If using media redirection, a valid endpoint URL must be provided 