# vCon MCP storage adapter

Stores vCons in a vcon-mcp service through its REST API.

Module: `storage.vcon_mcp`. Needs no extra packages.

## Configure the adapter

```yaml
storages:
  vcon_mcp:
    module: storage.vcon_mcp
    options:
      base_url: http://vcon-mcp:3000/api/v1
      api_key: example-key
      timeout: 30
      transient_retries: 3
      transient_backoff_base_s: 0.5
```

## Set the options

Each key falls back to its default, so all of them are optional.

| Option | Type | Default | Description |
|---|---|---|---|
| `base_url` | string | `http://127.0.0.1:3000/api/v1` | REST API root |
| `api_key` | string | `""` | Sent as `Authorization: Bearer <api_key>` when set |
| `timeout` | integer | `30` | Request timeout in seconds |
| `transient_retries` | integer | `3` | Retries for transient failures |
| `transient_backoff_base_s` | number | `0.5` | Backoff factor in seconds |

## Save a vCon

`save` reads the vCon through `VconRedis` and sends it to `POST {base_url}/vcons`. A vCon missing from Redis raises `ValueError`. The adapter does not apply `EGRESS_FORMAT_VERSION`.

## Read a vCon

`get` calls `GET {base_url}/vcons/{uuid}` and returns the `vcon` key of the JSON response. It returns `None` on `404`, when that key is absent, and on any request error.

## Delete a vCon

`delete` calls `DELETE {base_url}/vcons/{uuid}`. It returns `True` on success and `False` on `404`, and raises on any other request error.

## Handle a failed write

Each call uses a session that retries before any failure reaches the server.

| Setting | Value |
|---|---|
| Retried failures | Connection errors, read timeouts, and `429`, `502`, `503` and `504` responses |
| Methods | `GET`, `POST`, `DELETE` |
| Attempts | `transient_retries` retries after the first request |
| Backoff | Exponential, with `transient_backoff_base_s` as the factor |
| `Retry-After` | Honoured on `429` and `503` |

Other statuses such as `400`, `401` and `404` are not retried. When retries run out, or on any other error, `save` raises and the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write).

Retrying `POST` and replaying from the DLQ are both safe, because vcon-mcp upserts on the vCon UUID.
