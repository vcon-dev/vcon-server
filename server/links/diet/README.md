# Diet Link

The Diet link is a specialized plugin that helps reduce the size and content of vCon objects by selectively removing or modifying specific elements. It's particularly useful for data minimization, privacy protection, and optimizing storage.

## Features

- Selective removal of dialog body content
- Optional media redirection to external storage (HTTP endpoint or S3)
- S3 storage with presigned URL generation for secure access
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
    # S3 storage options for dialog bodies
    "s3_bucket": "",              # S3 bucket name for storing dialog bodies
    "s3_path": "",                # Optional path prefix within the bucket
    "aws_access_key_id": "",      # AWS access key ID
    "aws_secret_access_key": "",  # AWS secret access key
    "aws_region": "us-east-1",    # AWS region (default: us-east-1)
    "presigned_url_expiration": None,  # Presigned URL expiration in seconds (None = default 1 hour)
}
```

### Options Description

- `remove_dialog_body`: Whether to remove body content from dialogs
- `post_media_to_url`: URL endpoint to store media content (if empty, media is just removed)
- `remove_analysis`: Whether to remove all analysis data
- `remove_attachment_types`: List of MIME types to remove from attachments
- `remove_system_prompts`: Whether to remove system_prompt keys to prevent LLM instruction injection

### S3 Storage Options

- `s3_bucket`: The S3 bucket name where dialog bodies will be stored
- `s3_path`: Optional path prefix within the bucket (e.g., "dialogs/processed")
- `aws_access_key_id`: AWS access key ID for authentication
- `aws_secret_access_key`: AWS secret access key for authentication
- `aws_region`: AWS region where the bucket is located (default: "us-east-1")
- `presigned_url_expiration`: Expiration time in seconds for presigned URLs (optional, defaults to 3600 seconds / 1 hour)

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Applying configured modifications:
   - Removing dialog body content (optionally posting to external URL)
   - Removing analysis data if specified
   - Filtering attachments by MIME type
   - Removing system prompts if specified
3. Storing the modified vCon back in Redis

## Media Storage Options

The diet link supports two methods for storing dialog bodies externally:

### S3 Storage (Recommended)

When `s3_bucket` is configured, the link will:
1. Upload dialog body content to the specified S3 bucket
2. Generate a presigned URL for secure access
3. Replace the body content with the presigned URL
4. Set the body_type to "url"
5. If the upload fails, the body content will be removed

**S3 takes precedence over HTTP endpoint** - if both `s3_bucket` and `post_media_to_url` are configured, S3 will be used.

Example S3 configuration:
```python
{
    "remove_dialog_body": True,
    "s3_bucket": "my-vcon-storage",
    "s3_path": "dialogs/archived",
    "aws_access_key_id": "AKIAXXXXXXXX",
    "aws_secret_access_key": "xxxxxxxxxxxxx",
    "aws_region": "us-west-2",
    "presigned_url_expiration": 86400,  # 24 hours
}
```

The S3 key structure is: `{s3_path}/{vcon_uuid}/{dialog_id}_{unique_id}.txt`

### HTTP Endpoint Storage

When `post_media_to_url` is configured (and `s3_bucket` is not), the link will:
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
- Requests library for HTTP media redirection
- boto3 library for S3 storage
- Custom utilities:
  - logging_utils

## Requirements

- Redis connection must be configured
- Appropriate permissions for vCon access and storage
- If using HTTP media redirection, a valid endpoint URL must be provided
- If using S3 storage:
  - Valid AWS credentials with write access to the specified bucket
  - The bucket must exist and be accessible