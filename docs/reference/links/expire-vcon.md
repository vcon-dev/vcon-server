# expire_vcon

Sets a time to live on the vCon's Redis key.

Module: `links.expire_vcon`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `seconds` | int | `86400` | Time to live in seconds |

The link does not merge `default_options`. Set `seconds` in `options`, or the link raises `KeyError`.

## Follow the processing steps

The link calls `VconQueue().set_vcon_ttl`, which runs Redis `EXPIRE` on `vcon:<uuid>`. Later saves in the chain keep that expiry.

Only the Redis copy expires. Copies in storage backends stay, and when `VCON_STORAGE_FALLBACK_ENABLED` is on, a later read loads the vCon back from storage into Redis.

## Read the return value

Returns the uuid, also when the key does not exist.

## Inspect the vCon changes

None. The vCon content does not change.

## Copy a configuration example

```yaml
links:
  expire_in_a_day:
    module: links.expire_vcon
    options:
      seconds: 86400
```
