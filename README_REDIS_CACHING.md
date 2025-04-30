# Redis Caching for vCon API

## Overview

The vCon API uses Redis as a primary storage and caching layer. When a vCon is not found in Redis but exists in a configured storage backend (like PostgreSQL, MongoDB, etc.), the API will automatically store it back in Redis with a configurable expiration time. This improves performance for subsequent requests for the same vCon, as they'll be served from Redis instead of having to query the storage backend again.

## Configuration

The Redis caching behavior can be configured using the following environment variable:

- `VCON_REDIS_EXPIRY`: The expiration time in seconds for vCons stored in Redis after being fetched from a storage backend. Default is 3600 seconds (1 hour).

## How It Works

1. When a client requests a vCon by UUID, the API first checks if it exists in Redis.
2. If the vCon is not found in Redis, the API checks each configured storage backend.
3. If the vCon is found in a storage backend, it is:
   - Returned to the client
   - Stored back in Redis with the configured expiration time
   - Added to the sorted set for timestamp-based retrieval

## Benefits

- **Improved Performance**: Subsequent requests for the same vCon are served from Redis, which is faster than querying a storage backend.
- **Reduced Load**: Storage backends experience less load as frequently accessed vCons are cached in Redis.
- **Configurable Expiration**: The expiration time can be adjusted based on your specific requirements.

## Example

```bash
# Set the Redis expiration time to 2 hours (7200 seconds)
export VCON_REDIS_EXPIRY=7200
```

## Related Settings

- `VCON_INDEX_EXPIRY`: The expiration time in seconds for vCon indices in Redis. Default is 86400 seconds (1 day).
- `VCON_SORTED_SET_NAME`: The name of the Redis sorted set used for timestamp-based retrieval of vCons. Default is "vcons". 