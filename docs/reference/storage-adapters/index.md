# Storage adapters

A storage adapter copies a vCon from Redis to another system when a chain finishes. Each adapter is a module in `common/storage/`, loaded by the `Storage` class in `common/storage/base.py`. A module must expose `save` and `default_options`. `get` and `delete` are optional.

## Configure an adapter

Define each backend under `storages:` and name it in a chain. The name under `storages:` is yours to choose. The `module` value selects the adapter.

```yaml
storages:
  archive:
    module: storage.s3
    options:
      aws_access_key_id: example-key
      aws_secret_access_key: example-secret
      aws_bucket: vcon-archive

chains:
  main:
    links:
      - tag
    storages:
      - archive
    ingress_lists:
      - default
    enabled: 1
```

`Storage` reads only `module` and `options`. It imports the module with `importlib` and does not install packages, so the `pip_name` key that links and tracers accept has no effect here.

The config file is parsed with `yaml.safe_load`. The server does not expand `${VAR}` references, so a value written that way reaches the adapter as literal text. Write the real value, or render the file before the server reads it.

## Compare the adapters

| Adapter | Module | `save` | `get` | `delete` | Failed `save` |
|---|---|---|---|---|---|
| [chatgpt_files](chatgpt_files.md) | `storage.chatgpt_files` | Yes, see page | No | No | Storage DLQ |
| [dataverse](dataverse.md) | `storage.dataverse` | Yes | Yes | No | Storage DLQ |
| [elasticsearch](elasticsearch.md) | `storage.elasticsearch` | Yes | No | Yes | Storage DLQ, except per-document errors |
| [file](file.md) | `storage.file` | Yes | Yes | Yes | Storage DLQ |
| [milvus](milvus.md) | `storage.milvus` | Yes | Partial record | No | Storage DLQ |
| [mongo](mongo.md) | `storage.mongo` | Yes | Yes | No | Storage DLQ |
| [postgres](postgres.md) | `storage.postgres` | Yes | Yes | Yes | Storage DLQ |
| [redis_storage](redis_storage.md) | `storage.redis_storage` | Yes | Yes | No | Storage DLQ |
| [s3](s3.md) | `storage.s3` | Yes | Yes | Yes | Storage DLQ |
| [scitt](scitt.md) | `storage.scitt` | Yes | No | No | Storage DLQ |
| [sftp](sftp.md) | `storage.sftp` | Fails, see page | Wrong vCon possible, see page | No | Storage DLQ |
| [spaceandtime](spaceandtime.md) | `storage.spaceandtime` | Fails, see page | Yes | No | Logged only |
| [utopia](utopia.md) | `storage.utopia` | Yes | No | Yes | Storage DLQ |
| [vcon_mcp](vcon_mcp.md) | `storage.vcon_mcp` | Yes | Yes | Yes | Storage DLQ |
| [webhook](webhook.md) | `storage.webhook` | Yes | No | No | Storage DLQ |

When a module has no `get`, `Storage.get` returns `None`. When it has no `delete`, `Storage.delete` returns `False`.

## Install the adapter packages

| Adapter | Python package | `pyproject.toml` group |
|---|---|---|
| `dataverse` | `msal` | `storage` |
| `elasticsearch` | `elasticsearch` | `storage` |
| `mongo` | `pymongo` | `storage` |
| `postgres` | `peewee`, `psycopg2-binary` | `storage` |
| `s3` | `boto3` | `storage` |
| `milvus` | `pymilvus`, `openai` | `storage-milvus` |
| `chatgpt_files` | `openai` | `conserver` |
| `scitt` | `ecdsa`, `pycose` from the core set, plus `fastapi` through `links.scitt` | Core and `api` |
| `file`, `redis_storage`, `vcon_mcp`, `utopia`, `webhook` | None beyond the core set | Core |
| `sftp` | `paramiko` | None. Not in `uv.lock` |
| `spaceandtime` | `spaceandtime` | None. Not in `uv.lock` |

Each image installs different groups:

| Image | Groups | Effect on adapters |
|---|---|---|
| `docker/Dockerfile`, used by `docker-compose.yml` | `conserver`, `api`, `dev`, `storage-milvus` | All adapters import except `sftp` and `spaceandtime` |
| `docker/Dockerfile.conserver` | `conserver` | No `milvus`. No `scitt`, because `fastapi` is absent. No `sftp` or `spaceandtime` |
| `docker/Dockerfile.api` | `api` | No `milvus` or `chatgpt_files`, because `openai` is absent. No `scitt`, because `conserver/` is not on `PYTHONPATH`. No `sftp` or `spaceandtime` |

The API imports adapters too. On a Redis miss it walks every entry under `storages:`, so a module that will not import in the API image affects reads as well as writes. See [Read a vCon back from storage](#read-a-vcon-back-from-storage).

## Learn the rule for option defaults

`Storage.__init__` runs `storage.get("options", module.default_options)`. An `options` block replaces `default_options`. It does not merge with it. A key you leave out of the block keeps its default only when the adapter handles that itself.

| Adapters | What happens to a key left out of `options` |
|---|---|
| `milvus`, `scitt`, `utopia` | The adapter merges your options over `default_options`, so every default applies |
| `file` | Each key falls back to its default |
| `vcon_mcp` | `base_url`, `timeout`, `transient_retries` and `transient_backoff_base_s` fall back to their defaults |
| `webhook` | `timeout` and `pool-size` fall back to their defaults. `headers` and `webhook-urls` fall back to empty |
| `elasticsearch` | `cloud_id`, `api_key`, `ca_certs` and `index_prefix` are read safely. `url`, `username` and `password` raise `KeyError` on the non-cloud path |
| `postgres` | `table_name` falls back to `vcons`. All other keys raise `KeyError` |
| `s3` | `aws_region`, `endpoint_url` and `s3_path` are optional. The rest raise `KeyError`. `default_options` is empty |
| `chatgpt_files`, `dataverse`, `mongo`, `redis_storage`, `sftp` | The adapter reads the key directly, so a missing key raises `KeyError`. A missing `dataverse` auth key surfaces as `Failed to create Dataverse session with valid token` |

The option tables on each page give the `default_options` value. Where that value applies only when the whole `options` block is absent, the page marks the option as required in practice.

## Combine backends on a chain

Every name in a chain's `storages` list gets the same write. The list is a set of copies and not a set of tiers, and the server never moves a vCon between backends later.

| Goal | `storages` list | Note |
|---|---|---|
| Primary store plus search | `postgres`, `elasticsearch` | `elasticsearch` has no `get`, so reads come from `postgres` |
| Primary store plus object archive | `postgres`, `s3` | Both have `get`. The first one under the top-level `storages:` key answers reads |
| Two targets on one adapter | `postgres_us`, `postgres_eu` | Each name is its own entry under `storages:`, with its own `module` and `options` |

## Follow a write through the server

1. A chain finishes its links. `VconChainRequest._wrap_up` in `conserver/main.py` pushes the vCon to the chain's egress lists first.
2. It then calls `Storage(name).save(vcon_id)` for each name in the chain's `storages` list.
3. With `CONSERVER_PARALLEL_STORAGE` on, the default, and more than one backend, the writes run in a thread pool. Otherwise they run in list order.
4. Each adapter reads the vCon through `VconRedis`, which itself falls back to storage on a Redis miss. `chatgpt_files` is the exception and reads Redis directly.

Each write is timed and counted in `conserver.storage.count` and `conserver.storage.duration_ms`, with `backend` and `outcome` attributes. See the [metrics reference](../metrics.md).

`elasticsearch`, `postgres` and `s3` apply `EGRESS_FORMAT_VERSION` before they write. The others write the canonical form. See [egress compatibility](../../configuration/egress-compatibility.md).

## Handle a failed write

An exception from `save`, or from loading the module, is caught per backend in `_process_storage`. It does not stop the other backends and does not send the vCon to the ingress DLQ. The server pushes the vCon id to `DLQ:storage:<name>`, where `<name>` is the key under `storages:`, and records `outcome: error`.

The push runs as one Redis script. It extends the vCon's TTL to `VCON_DLQ_EXPIRY` when the current TTL is shorter, and leaves a longer TTL or a persistent key alone. If the vCon body is already gone from Redis, nothing is pushed and the server logs that manual recovery is required.

The server does not retry a failed write by itself. Replay is an operator action:

```bash
curl -X POST "$API/dlq/storage/reprocess?storage_name=archive&count=100" \
  -H "x-conserver-api-token: $TOKEN"
```

`GET /dlq/storage?storage_name=archive` lists the ids. The header name comes from `CONSERVER_HEADER_NAME`. See the [API routes](../api-routes.md) and [storage recovery](../../operations/storage-recovery.md).

Replay behaves as follows:

- It repeats the storage write only. The chain does not run again.
- It takes a Redis lock with no expiry on `DLQ:storage:<name>:replay-lock`. A second caller gets `409`. A crash during replay leaves the lock in place for an operator to clear.
- An id leaves the list only after its write succeeds.
- Draining stops at the first failure. An item that always fails stays at the head and holds back every item behind it.
- Recovery is at-least-once, so a backend can see the same vCon twice. Each adapter page says what a repeated `save` does.
- An unknown `storage_name`, or a module that fails to import, returns `404`.

### Find the writes that never reach the DLQ

`save` can return without writing and without raising. The server then counts a success.

| Adapter | Condition |
|---|---|
| `elasticsearch` | The vCon has no dialog. A single document that fails to index is also logged and skipped |
| `milvus` | `skip_if_exists` finds the vCon, or no text can be extracted. A failed embedding stores a zero vector |
| `scitt` | The vCon cannot be found |
| `spaceandtime` | Any error. The adapter logs and returns |
| `utopia` | `require_analysis_grant` is on and no basis grants `analysis` |
| `webhook` | `webhook-urls` is empty |

## Read a vCon back from storage

A vCon missing from Redis is read from adapters on the paths below. Both walk `Configuration.get_storages()`, which is every entry under `storages:` in file order, whether or not a chain uses it. The first truthy result wins and is cached back to Redis with `VCON_REDIS_EXPIRY`.

| Path | Caller | Adapter errors | `VCON_STORAGE_FALLBACK_ENABLED` |
|---|---|---|---|
| `VconRedis._load_from_storage` | Links, adapters, tracers | Logged, next backend tried | Honoured |
| `sync_vcon_from_storage` in `api/api.py` | API read routes and `POST /vcon/ingress` | Not caught in the function. The read routes return a plain `500`, and `POST /vcon/ingress` returns `Failed to add to ingress list` | Not read |

Order matters. `milvus` returns a partial record and `sftp` can return a different vCon, and neither path can tell. Put adapters that hold the full vCon first under `storages:`.

## Delete a vCon from storage

`DELETE /vcon/{uuid}` removes the Redis key and calls `Storage.delete` on every entry under `storages:`. An adapter with no `delete` returns `False`, the API logs a warning, and the stored copy stays. The route still answers with success when a backend fails, so check the logs.

## Carry lawful basis attachments

Adapters that store the whole vCon keep every attachment, including `lawful_basis`. `tests/storage/` covers the round trip for `mongo`, `postgres`, `s3` and `vcon_mcp`. `to_legacy` keeps the attachment too when `EGRESS_FORMAT_VERSION` is set.

No adapter creates, validates or manages a lawful basis. Only `utopia` reads one. It writes a sentence about the basis into its rendering and offers the opt-in [`require_analysis_grant`](utopia.md#require-an-analysis-grant) option, which affects that adapter alone. Storing a vCon does not make a deployment compliant with anything.

## Write a new adapter

See [creating storage adapters](../../extending/creating-storage-adapters.md).
