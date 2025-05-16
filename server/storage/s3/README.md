# S3 Storage

This module implements object storage using Amazon S3 for the vCon server.

## Overview

S3 storage provides scalable, durable object storage capabilities, making it ideal for storing vCon data with high availability and reliability.

## Configuration

Required configuration options:

```yaml
storages:
  s3:
    module: storage.s3
    options:
      bucket: your-bucket-name           # S3 bucket name
      region: us-west-2                  # AWS region
      access_key: your-access-key        # AWS access key
      secret_key: your-secret-key        # AWS secret key
      prefix: vcons/                     # Optional: key prefix
      endpoint_url: null                 # Optional: custom endpoint
```

## Features

- Object storage
- High availability
- Durability
- Versioning support
- Lifecycle management
- Automatic metrics logging
- Encryption support
- Access control

## Usage

```python
from storage import Storage

# Initialize S3 storage
s3_storage = Storage("s3")

# Save vCon data
s3_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = s3_storage.get(vcon_id)
```

## Implementation Details

The S3 storage implementation:
- Uses boto3 for AWS S3 operations
- Implements retry logic
- Supports multipart uploads
- Provides encryption
- Includes automatic metrics logging

## Dependencies

- boto3
- botocore

## Best Practices

1. Secure credential management
2. Implement proper access control
3. Use appropriate storage classes
4. Enable versioning
5. Configure lifecycle rules
6. Implement proper error handling
7. Use appropriate encryption
8. Monitor costs
9. Implement retry logic
10. Use appropriate regions
11. Enable logging
12. Regular backup verification 