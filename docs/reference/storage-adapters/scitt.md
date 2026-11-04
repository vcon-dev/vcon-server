# SCITT storage adapter

Registers signed statements about a vCon on a SCRAPI-compatible transparency service. The service receives a hash-based statement. It does not receive the vCon, and the adapter cannot read one back.

Module: `storage.scitt`. It imports `links.scitt`, so it needs `conserver/` on `PYTHONPATH` and the `fastapi` package. Only the `docker/Dockerfile` image has both. See [the image table](index.md#install-the-adapter-packages).

## Configure the adapter

```yaml
storages:
  scitt:
    module: storage.scitt
    options:
      scrapi_url: http://scittles:8000
      signing_key_path: /etc/scitt/signing-key.pem
      issuer: conserver
      key_id: conserver-key-1
      operations:
        - vcon_enhanced
```

## Set the options

The adapter merges your options over the defaults.

| Option | Type | Default | Description |
|---|---|---|---|
| `scrapi_url` | string | `http://scittles:8000` | Base URL of the transparency service |
| `signing_key_pem` | string | none | Base64-encoded PEM signing key. Takes priority over `signing_key_path` |
| `signing_key_path` | string | `/etc/scitt/signing-key.pem` | Path to a PEM signing key |
| `issuer` | string | `conserver` | Issuer in the signed statement |
| `key_id` | string | `conserver-key-1` | Key id in the signed statement |
| `operations` | list | `["vcon_enhanced"]` | Operation labels. Each label produces its own statements |

The key loader in `links.scitt` expects a P-256 ECDSA key.

## Save a vCon

`save` reads the vCon through `VconRedis` and takes its SHA-256 hash. It then registers one statement for each operation and each party with a `tel`:

| Case | Subject | Payload | Metadata |
|---|---|---|---|
| Party has `tel` | `tel:<number>` | `<hash>:<operation>:<number>` | `vcon_operation`, `party_tel` |
| No party has `tel` | `vcon://<uuid>` | `<hash>:<operation>` | `vcon_operation` |

A party with no `tel` is skipped with a warning when another party has one.

The adapter never writes receipts back to the vCon, which avoids races with other storage writers running in parallel. The transparency service holds the receipts.

Registration posts to `<scrapi_url>/entries`. A `201` is complete. A `303` starts polling, every 10 seconds for up to 60 seconds. Each HTTP request has a 30 second timeout.

## Read or delete a vCon

The adapter has no `get` and no `delete`. Entries stay on the transparency service after `DELETE /vcon/{uuid}`.

## Handle a failed write

A signing key problem, an HTTP error or a polling timeout raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). A vCon that cannot be found logs a warning and returns, so the write counts as a success.

The adapter has no retry. A replay registers every statement again, including those that succeeded before the failure. The vCon hash is the same if the vCon has not changed. TODO(verify): whether the transparency service treats a repeated statement as a new entry.
