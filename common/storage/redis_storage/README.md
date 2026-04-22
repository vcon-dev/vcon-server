# Redis Storage

This module implements in-memory data structure storage using Redis for the vCon server.

## Overview

Redis storage provides fast, in-memory data storage capabilities with persistence options, making it ideal for caching and temporary storage of vCon data.

## Configuration

Required configuration options:

```yaml
storages:
  redis:
    module: storage.redis_storage
    options:
      host: localhost           # Redis host
      port: 6379               # Redis port
      db: 0                    # Redis database number
      password: null           # Optional: Redis password
      key_prefix: vcon:        # Optional: key prefix
      ttl: 3600               # Optional: time to live in seconds
```

## Features

- In-memory storage
- Data persistence
- Key-value storage
- Automatic metrics logging
- TTL support
- Pub/Sub capabilities
- Atomic operations

## Usage

```python
from storage import Storage

# Initialize Redis storage
redis_storage = Storage("redis")

# Save vCon data
redis_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = redis_storage.get(vcon_id)
```

## Implementation Details

The Redis storage implementation:
- Uses redis-py for Redis operations
- Implements connection pooling
- Supports data serialization
- Provides TTL management
- Includes automatic metrics logging

## Dependencies

- redis
- msgpack (for serialization)

## Best Practices

1. Configure appropriate memory limits
2. Use proper key naming
3. Implement TTL for temporary data
4. Monitor memory usage
5. Regular backup
6. Implement proper error handling
7. Use appropriate data types
8. Configure persistence
9. Monitor performance
10. Use connection pooling
11. Implement retry logic
12. Use appropriate serialization 