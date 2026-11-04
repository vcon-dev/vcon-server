# Redis storage adapter

Copies a vCon to a second key in the server's own Redis, with a separate expiry. Use it to keep a vCon longer than `VCON_REDIS_EXPIRY` allows.

Module: `storage.redis_storage`. Needs no extra packages.

## Configure the adapter

```yaml
storages:
  redis_copy:
    module: storage.redis_storage
    options:
      prefix: vcon_storage
      expires: 604800
```

## Set the options

The adapter reads `prefix` and `expires` directly, so both are required in an `options` block.

| Option | Type | Default | Description |
|---|---|---|---|
| `redis_url` | string | `redis://:localhost:6379` | Not read by the adapter. It always uses the `redis_mgr` client, which connects to `REDIS_URL` |
| `prefix` | string | `vcon_storage` | Key prefix |
| `expires` | integer | `604800` | Key expiry in seconds. The default is seven days |

Because `redis_url` has no effect, this adapter cannot write to a different Redis.

## Save a vCon

`save` reads the vCon through `VconRedis` and sets `<prefix>:<uuid>` to its JSON, with `expires` as the TTL. The adapter does not apply `EGRESS_FORMAT_VERSION`.

## Read a vCon

`get` reads `<prefix>:<uuid>` and parses it. It returns `None` when the key is missing or on any error.

## Delete a vCon

The adapter has no `delete`. After `DELETE /vcon/{uuid}` the copy stays until its TTL runs out, and a later Redis miss can bring the vCon back through the [storage fallback](index.md#read-a-vcon-back-from-storage).

## Handle a failed write

Any exception raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). A failure here usually means Redis itself is down, and in that case the DLQ push fails too. The server then logs that manual recovery is required.

A repeated `save` overwrites the key and resets its TTL.
