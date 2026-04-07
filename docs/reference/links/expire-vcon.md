# expire_vcon

Sets a Redis TTL on a vCon key so that it is automatically deleted after a configured duration. Useful for enforcing data-retention policies and keeping Redis memory usage bounded.

## Configuration

```yaml
links:
  expire_vcon:
    module: links.expire_vcon
    options:
      seconds: 86400
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `seconds` | int | `86400` | Number of seconds after which the vCon key expires and is removed from Redis. Default is 24 hours (60 × 60 × 24). |

## Example

```yaml
chains:
  retain_7_days:
    links:
      - expire_vcon:
          seconds: 604800
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

### Combine with other processing

```yaml
chains:
  process_and_expire:
    links:
      - deepgram_link
      - analyze
      - expire_vcon:
          seconds: 172800
    storages:
      - postgres
    ingress_lists:
      - audio_input
    enabled: 1
```

## Behavior

1. Calls Redis `EXPIRE vcon:<uuid> <seconds>` to set the TTL on the vCon key.
2. Logs the expiration at INFO level.
3. Returns the vCon UUID so processing continues down the chain.

The link does **not** retrieve or modify the vCon object itself — it only sets the expiry on the existing Redis key.
