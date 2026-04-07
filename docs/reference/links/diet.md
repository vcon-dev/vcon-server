# diet

Reduces the size of vCon objects by selectively removing or offloading content. Useful for data minimization, privacy compliance, and keeping Redis memory usage low after downstream processing has already consumed the full data.

## Configuration

```yaml
links:
  diet:
    module: links.diet
    options:
      remove_dialog_body: true
      remove_analysis: false
      remove_system_prompts: false
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `remove_dialog_body` | bool | `false` | Remove the `body` field from every dialog entry. If an external storage target is also configured, the body is offloaded there first. |
| `post_media_to_url` | string | `""` | HTTP endpoint that receives the dialog body via `POST`. On success the body is replaced with the returned URL. Ignored when `s3_bucket` is set. |
| `remove_analysis` | bool | `false` | Delete the entire `analysis` array from the vCon. |
| `remove_attachment_types` | list | `[]` | List of MIME types (e.g. `["image/jpeg", "audio/mp3"]`) whose attachments should be deleted. |
| `remove_system_prompts` | bool | `false` | Recursively remove all `system_prompt` keys from the vCon to prevent LLM prompt-injection attacks. |
| `s3_bucket` | string | `""` | S3 bucket name for offloading dialog bodies. Takes precedence over `post_media_to_url`. |
| `s3_path` | string | `""` | Optional key prefix within the bucket (e.g. `"dialogs/archived"`). |
| `aws_access_key_id` | string | `""` | AWS access key ID. |
| `aws_secret_access_key` | string | `""` | AWS secret access key. |
| `aws_region` | string | `us-east-1` | AWS region for the S3 bucket. |
| `presigned_url_expiration` | int \| null | `null` | Presigned URL lifetime in seconds. `null` defaults to 3600 (1 hour). |

## Example

### Remove dialog bodies and offload to S3

```yaml
chains:
  archive:
    links:
      - diet:
          remove_dialog_body: true
          s3_bucket: my-vcon-archive
          s3_path: dialogs/processed
          aws_access_key_id: "${AWS_ACCESS_KEY_ID}"
          aws_secret_access_key: "${AWS_SECRET_ACCESS_KEY}"
          aws_region: us-west-2
          presigned_url_expiration: 86400
    storages:
      - postgres
    ingress_lists:
      - analyzed
    enabled: 1
```

### Strip analysis and system prompts for long-term storage

```yaml
chains:
  slim_storage:
    links:
      - diet:
          remove_analysis: true
          remove_system_prompts: true
    storages:
      - postgres
    ingress_lists:
      - archived
    enabled: 1
```

## Behavior

1. Loads the vCon directly from Redis using `JSON.GET`.
2. For each dialog, if `remove_dialog_body` is enabled:
   - If `s3_bucket` is set: uploads the body to S3 and replaces it with a presigned URL.
   - Else if `post_media_to_url` is set: POSTs the body to the URL and replaces it with the returned URL.
   - Otherwise: sets the body to an empty string.
3. Removes the `analysis` array if `remove_analysis` is `true`.
4. Removes attachments whose `mime_type` is listed in `remove_attachment_types`.
5. Recursively removes all `system_prompt` keys if `remove_system_prompts` is `true`.
6. Writes the modified vCon back to Redis using `JSON.SET`.

## Prerequisites

- AWS credentials with `s3:PutObject` and `s3:GetObject` permissions are required when using S3 offload.
- The `boto3` Python package must be installed when using S3 offload.
