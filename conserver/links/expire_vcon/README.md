# Expire vCon Link

The Expire vCon link is a simple but effective plugin that sets an expiration time for vCon objects in Redis. This helps manage storage by automatically removing vCons after a specified period.

## Features

- Sets Redis expiration time for vCon objects
- Configurable expiration duration
- Simple and lightweight implementation
- Automatic cleanup of expired vCons

## Configuration Options

```python
default_options = {
    "seconds": 60 * 60 * 24  # Default: 24 hours (86400 seconds)
}
```

### Options Description

- `seconds`: The number of seconds after which the vCon will expire and be automatically removed from Redis

## Usage

The link processes vCons by:
1. Setting an expiration time on the vCon key in Redis
2. Logging the expiration time setting
3. Returning the vCon UUID to continue processing

## Implementation Details

The link uses Redis's built-in expiration mechanism:
- The `EXPIRE` command sets a timeout on a key
- After the timeout, Redis automatically removes the key
- No additional cleanup processes are required

## Dependencies

- Redis for vCon storage
- Custom utilities:
  - logging_utils

## Requirements

- Redis connection must be configured
- Appropriate permissions for vCon access and storage

## Common Use Cases

- Data retention policy enforcement
- Automatic cleanup of temporary vCons
- Storage optimization
- Privacy compliance (GDPR, CCPA, etc.) 