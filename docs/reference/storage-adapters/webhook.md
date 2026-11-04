# Webhook storage adapter

Posts the vCon as JSON to one or more URLs when a chain finishes. It differs from the [webhook link](../links/webhook.md), which runs as a step inside a chain.

Module: `storage.webhook`. Needs no extra packages.

## Configure the adapter

```yaml
storages:
  webhook:
    module: storage.webhook
    options:
      webhook-urls:
        - https://example.com/vcon-hook
      headers:
        Authorization: Bearer example-token
      timeout: 30
      pool-size: 16
```

The option names `webhook-urls` and `pool-size` use hyphens.

## Set the options

Each key falls back to its default, so all of them are optional.

| Option | Type | Default | Description |
|---|---|---|---|
| `webhook-urls` | list | `[]` | Target URLs. When empty, `save` logs a warning and returns |
| `headers` | map | `{}` | Headers sent with each post |
| `timeout` | integer | `30` | Request timeout in seconds |
| `pool-size` | integer | `16` | Keep-alive connections kept per worker process |

Size `pool-size` to `CONSERVER_VCON_CONCURRENCY`. Extra connections still work but close after use. The HTTP session is built once per process, so the first call's `pool-size` applies to all webhook storages in that process.

## Save a vCon

`save` reads the vCon through `VconRedis` and posts it to each URL in turn. It records the response time in `conserver.webhook.duration`, with a `status_code` attribute.

If the payload's `vcon` is `0.0.1` or absent, the adapter sets it to `0.3.0` in the posted copy. The adapter does not apply `EGRESS_FORMAT_VERSION`. The webhook link does.

## Read or delete a vCon

The adapter has no `get` and no `delete`.

## Handle a failed write

A connection error, a timeout or a `4xx` or `5xx` response raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). The adapter has no retry.

The first failure stops the loop, so later URLs are not called. A replay posts to every URL again from the start, and URLs that already succeeded receive the vCon a second time. Receivers should tolerate duplicates. For independent delivery, define one storage entry per URL.
