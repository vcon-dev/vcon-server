# S3 Storage

This module implements object storage using Amazon S3 for the vCon server.

## Overview

S3 storage provides scalable, durable object storage capabilities, making it ideal for storing vCon data with high availability and reliability.

## Configuration

Configuration options:

```yaml
storages:
  s3:
    module: storage.s3
    options:
      # Required options
      aws_access_key_id: your-access-key      # AWS access key ID
      aws_secret_access_key: your-secret-key  # AWS secret access key
      aws_bucket: your-bucket-name            # S3 bucket name

      # Optional options
      aws_region: us-east-1                   # AWS region (recommended to avoid cross-region errors)
      endpoint_url: null                      # Custom endpoint for S3-compatible services (e.g., MinIO)
      s3_path: vcons                          # Prefix for S3 keys (optional)
```

### Configuration Options

| Option | Required | Description |
|--------|----------|-------------|
| `aws_access_key_id` | Yes | AWS access key ID for authentication |
| `aws_secret_access_key` | Yes | AWS secret access key for authentication |
| `aws_bucket` | Yes | Name of the S3 bucket to store vCons |
| `aws_region` | No | AWS region where the bucket is located (e.g., `us-east-1`, `us-west-2`, `eu-west-1`). **Recommended** to avoid "AuthorizationHeaderMalformed" errors when the bucket is in a different region than the default. |
| `endpoint_url` | No | Custom endpoint URL for S3-compatible services like MinIO, LocalStack, or other providers |
| `s3_path` | No | Prefix path for organizing vCon objects within the bucket |

### Region Configuration

**Important:** If your S3 bucket is in a region other than `us-east-1`, you should explicitly set the `aws_region` option. Without this, you may encounter errors like:

```
AuthorizationHeaderMalformed: The authorization header is malformed;
the region 'us-east-1' is wrong; expecting 'us-east-2'
```

## Features

- Object storage with automatic date-based key organization (`YYYY/MM/DD/uuid.vcon`)
- High availability and durability
- Support for custom S3-compatible endpoints (MinIO, LocalStack, etc.)
- Configurable key prefix for organizing objects
- Automatic error logging

## Usage

```python
from storage import Storage

# Initialize S3 storage
s3_storage = Storage("s3")

# Save vCon data (retrieves from Redis and stores in S3)
s3_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = s3_storage.get(vcon_id)
```

## Key Structure

vCons are stored with keys following this pattern:
```
[s3_path/]YYYY/MM/DD/uuid.vcon
```

For example, a vCon created on January 15, 2024 with UUID `abc123` and `s3_path: vcons` would be stored at:
```
vcons/2024/01/15/abc123.vcon
```

## Dependencies

- boto3
- botocore

## Best Practices

1. Always configure `aws_region` to match your bucket's region
2. Use IAM roles with least-privilege access
3. Enable bucket versioning for data protection
4. Configure lifecycle rules for cost optimization
5. Enable server-side encryption
6. Use VPC endpoints for private connectivity
7. Monitor with CloudWatch metrics
8. Enable access logging for auditing