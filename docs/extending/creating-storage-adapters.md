# Create a storage adapter

A storage adapter keeps vCons in a backend. This page shows how to write one that the server can call, retry and read back from. The [storage adapter reference](../reference/storage-adapters/index.md) documents the adapters that ship with the server, including [how a write runs](../reference/storage-adapters/index.md#follow-a-write-through-the-server).

## Implement the interface

An adapter is a module with `default_options` and a `save` function. `get` and `delete` are optional.

```python
default_options = {}

def save(vcon_uuid: str, opts: dict = default_options) -> None:
    """Write the vCon. Raise on failure."""

def get(vcon_uuid: str, opts: dict = default_options) -> dict | None:
    """Return the vCon as a dict, or None if it is not here."""

def delete(vcon_uuid: str, opts: dict = default_options) -> bool:
    """Delete the vCon. Return True if it was deleted."""
```

| Function | Called by | When it is missing |
|---|---|---|
| `save` | The conserver, at the end of a chain | Required |
| `get` | `VconRedis` and the API, when Redis misses | The server treats the vCon as absent here |
| `delete` | `DELETE /vcon/{vcon_uuid}` | The server skips this backend |

`default_options` is required even if you always set `options`, because the server reads the attribute either way.

The server passes the id, so `save` loads the vCon itself with `VconRedis`. Adapters can run in the API image as well as the conserver image, so keep imports to `common/`.

## Lay out the module

```
common/storage/my_storage/
  __init__.py            # save(), get(), delete() and default_options
  README.md
  test_my_storage.py     # Tests sit beside the code
```

## Write a basic adapter

```python
# common/storage/my_storage/__init__.py

import json
from pathlib import Path

from lib.logging_utils import init_logger
from lib.vcon_egress_compat import to_configured_legacy
from lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "path": "/data/vcons",
}


def _file_path(vcon_uuid, opts):
    options = {**default_options, **(opts or {})}
    return Path(options["path"]) / f"{vcon_uuid}.json"


def save(vcon_uuid, opts=default_options):
    vcon = VconRedis().get_vcon(vcon_uuid)
    if vcon is None:
        raise ValueError(f"vCon not found: {vcon_uuid}")

    file_path = _file_path(vcon_uuid, opts)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(to_configured_legacy(vcon.to_dict())))
    logger.info("Saved %s to %s", vcon_uuid, file_path)


def get(vcon_uuid, opts=default_options):
    file_path = _file_path(vcon_uuid, opts)
    if not file_path.exists():
        return None
    return json.loads(file_path.read_text())


def delete(vcon_uuid, opts=default_options):
    file_path = _file_path(vcon_uuid, opts)
    if not file_path.exists():
        return False
    file_path.unlink()
    return True
```

`to_configured_legacy` applies `EGRESS_FORMAT_VERSION`, and returns the vCon unchanged when that is unset. See [egress compatibility](../configuration/egress-compatibility.md).

An `options` block replaces `default_options` and does not merge with it, so merge them yourself, as `_file_path` does. See [the rule for option defaults](../reference/storage-adapters/index.md#learn-the-rule-for-option-defaults).

## Register the adapter

```yaml
storages:
  my_storage:
    module: storage.my_storage
    options:
      path: /data/custom_vcons

chains:
  my_chain:
    links:
      - my_link
    storages:
      - my_storage
    ingress_lists:
      - default
```

The server imports the module by name and does not read `pip_name` for storages, so an adapter's package must already be installed. Add it to the `storage` group in `pyproject.toml` and run `uv lock`. If it is heavy, give it its own group, as `storage-milvus` does.

## Handle a failed write

Let `save` raise. The server catches the error, pushes the vCon onto `DLQ:storage:<name>`, extends its Redis expiry to `VCON_DLQ_EXPIRY` and moves on, so other backends are not affected and the chain is not rerun. `POST /dlq/storage/reprocess` then retries the write alone. The [storage adapter reference](../reference/storage-adapters/index.md#handle-a-failed-write) covers this in full.

If `save` catches an error and returns, the server records success, so nothing retries that write.

A replay runs `save` again, so make it safe to repeat:

- Use an upsert, or overwrite by id.
- Write to a temporary name and rename, if a half-written file would do harm.
- Use `tenacity` for short retries, and raise when they run out.

## Apply these patterns

### Write to a database

Open connections with a context manager, and upsert by id.

```python
from contextlib import contextmanager

import psycopg2

from lib.vcon_redis import VconRedis

default_options = {
    "host": "localhost",
    "port": 5432,
    "database": "vcons",
    "user": "vcon",
    "password": "",
}


@contextmanager
def get_connection(options):
    conn = psycopg2.connect(
        host=options["host"],
        port=options["port"],
        database=options["database"],
        user=options["user"],
        password=options["password"],
    )
    try:
        yield conn
    finally:
        conn.close()


def save(vcon_uuid, opts=default_options):
    options = {**default_options, **(opts or {})}

    vcon = VconRedis().get_vcon(vcon_uuid)
    if vcon is None:
        raise ValueError(f"vCon not found: {vcon_uuid}")

    with get_connection(options) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vcons (uuid, data, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (uuid) DO UPDATE SET data = EXCLUDED.data
                """,
                (vcon_uuid, vcon.dumps(), vcon.created_at),
            )
        conn.commit()
```

### Write to an HTTP API

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from lib.vcon_redis import VconRedis

default_options = {
    "base_url": "https://api.example.com",
    "api_key": "",
    "timeout": 30,
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10), reraise=True)
def _post(url, api_key, payload, timeout):
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()


def save(vcon_uuid, opts=default_options):
    options = {**default_options, **(opts or {})}

    vcon = VconRedis().get_vcon(vcon_uuid)
    if vcon is None:
        raise ValueError(f"vCon not found: {vcon_uuid}")

    _post(f"{options['base_url']}/vcons", options["api_key"], vcon.to_dict(), options["timeout"])
```

The bundled [webhook adapter](../reference/storage-adapters/webhook.md) already posts vCons to a URL. For S3-compatible object stores, see [`storage.s3`](../reference/storage-adapters/s3.md), which takes an `endpoint_url`.

### Share a connection

With parallel storage on, `save` runs in a thread pool, and `get` can run in the API at the same time. A client kept at module level must be safe across threads. Create it once and reuse it:

```python
import threading

_client = None
_client_lock = threading.Lock()


def _get_client(options):
    global _client
    with _client_lock:
        if _client is None:
            _client = make_client(options)
    return _client
```

A client created before a worker forks is shared with that worker, so create it inside the function, as above.

## Test the adapter

```python
# common/storage/my_storage/test_my_storage.py

from unittest.mock import patch

import pytest
from vcon import Vcon

from storage.my_storage import delete, get, save


@patch("storage.my_storage.VconRedis")
def test_save_and_get_round_trip(mock_vcon_redis, tmp_path):
    vcon = Vcon.build_new()
    mock_vcon_redis.return_value.get_vcon.return_value = vcon
    opts = {"path": str(tmp_path)}

    save(vcon.uuid, opts)

    assert get(vcon.uuid, opts)["uuid"] == vcon.uuid


@patch("storage.my_storage.VconRedis")
def test_save_raises_when_vcon_missing(mock_vcon_redis, tmp_path):
    mock_vcon_redis.return_value.get_vcon.return_value = None

    with pytest.raises(ValueError):
        save("missing-uuid", {"path": str(tmp_path)})


def test_get_returns_none_for_missing_file(tmp_path):
    assert get("missing-uuid", {"path": str(tmp_path)}) is None


def test_delete_returns_false_for_missing_file(tmp_path):
    assert delete("missing-uuid", {"path": str(tmp_path)}) is False
```

Run them with `uv run pytest common/storage/my_storage`.

## Follow these practices

- Raise on failure, so that the storage dead letter queue can do its job.
- Make `save` safe to repeat.
- Store the whole vCon, attachments included. Do not drop entries you do not recognise.
- Keep credentials out of logs, and out of your `default_options` values.
- Add a README with the options, and a page under `docs/reference/storage-adapters/`.
