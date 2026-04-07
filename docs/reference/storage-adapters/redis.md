# redis

Stores vCons in Redis as serialized JSON with optional TTL expiry.

## Prerequisites

- A running Redis instance
- The `redis` Python package (included in server dependencies)

## Configuration

```yaml
storages:
  redis:
    module: storage.redis_storage
    options:
      redis_url: redis://:password@localhost:6379
      prefix: vcon_storage
      expires: 604800
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `redis_url` | string | `redis://:localhost:6379` | Redis connection URL |
| `prefix` | string | `vcon_storage` | Key prefix used when storing vCons (`{prefix}:{uuid}`) |
| `expires` | integer | `604800` | TTL in seconds before keys expire (default: 7 days) |

## Example

### Local Redis

```yaml
storages:
  redis:
    module: storage.redis_storage
    options:
      redis_url: redis://localhost:6379
      prefix: vcon_storage
      expires: 86400

chains:
  main:
    links:
      - transcribe
    storages:
      - redis
    ingress_lists:
      - default
    enabled: 1
```

### Redis with Authentication

```yaml
storages:
  redis:
    module: storage.redis_storage
    options:
      redis_url: redis://:${REDIS_PASSWORD}@redis.example.com:6379
      prefix: prod_vcons
      expires: 604800
```

## Key Structure

vCons are stored as JSON strings under the key:

```
{prefix}:{vcon_uuid}
```

For example, with the default prefix:

```
vcon_storage:abc-123-def
```

Keys automatically expire after the configured `expires` duration. Set `expires` to `0` to disable expiry (keys persist indefinitely).
