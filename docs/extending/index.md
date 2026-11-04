# Extend vCon Server

You extend the server by writing Python modules and naming them in `config.yml`. There is no base class. A module works if it has the expected functions.

## Choose an extension point

| Extension | Purpose | Interface | Lives in | Guide |
|---|---|---|---|---|
| Link | Change, filter or route a vCon in a chain | `run(vcon_uuid, link_name, opts)` | `conserver/links/<name>/` | [Creating links](creating-links.md) |
| Storage adapter | Keep vCons in a backend | `save(vcon_uuid, opts)`, with optional `get` and `delete` | `common/storage/<name>/` | [Creating storage adapters](creating-storage-adapters.md) |
| Tracer | Report each chain step elsewhere | `run(in_vcon_uuid, out_vcon_uuid, tracer_name, links, link_index, opts)` | `conserver/tracers/<name>/` | [Creating tracers](creating-tracers.md) |
| External package | Ship a link or tracer outside the repo | As above, plus `pip_name` | PyPI or Git | [Dynamic modules](dynamic-modules.md) |

[Chains, links and storage](../concepts/chains-links-storage.md) explains how these fit into a run.

## Follow the shared rules

**Import from the top level.** The development image and `pytest.ini` put `common/`, `conserver/` and `api/` on the path. The published API image leaves out `conserver/`, and the published conserver image leaves out `api/`. Write `from lib.vcon_redis import VconRedis`, not a path through `common`.

**Use the local `Vcon` class.** On that path, `import vcon` loads `common/vcon.py`, not the `vcon` package named in `pyproject.toml`. Every link runs on the local class.

**Go through the helpers.** Read and write vCons with `lib.vcon_redis.VconRedis`, and queues with `lib.queue.VconQueue`. Do not import the Redis client.

**Read options defensively.** A link or tracer with no `options` key receives `None`, not its `default_options`. An `options` block replaces `default_options` and does not merge with it. Merge them yourself:

```python
options = {**default_options, **(opts or {})}
```

**Expect concurrency.** `CONSERVER_WORKERS` runs several processes. `CONSERVER_VCON_CONCURRENCY` and parallel storage run your code in several threads in one process. Keep module-level state safe for both.

**Check the image.** Links and tracers load only in the conserver. Storage adapters load in both the API and the conserver, so a new package for an adapter goes in the `storage` group of `pyproject.toml`, followed by `uv lock`.

## Build an extension

1. Create the folder and its `__init__.py`:

    ```bash
    mkdir -p conserver/links/my_link
    touch conserver/links/my_link/__init__.py
    ```

2. Write the interface from the guide for your extension type.

3. Add tests beside the code, for example `conserver/links/my_link/test_my_link.py`, and run them:

    ```bash
    uv run pytest conserver/links/my_link
    ```

4. Register the module in `config.yml`, with `options` set:

    ```yaml
    links:
      my_link:
        module: links.my_link
        options: {}

    chains:
      my_chain:
        links:
          - my_link
        storages:
          - file
        ingress_lists:
          - my_list
    ```

    The `file` backend is the one from the [quick start](../getting-started/quick-start.md#write-the-configuration). See [Register the link](creating-links.md#register-the-link) for why the chain has its own list.

5. Start the stack and submit a vCon:

    ```bash
    docker compose up -d

    curl -X POST "http://localhost:8000/api/vcon?ingress_lists=my_list" \
      -H "x-conserver-api-token: $TOKEN" \
      -H "Content-Type: application/json" \
      -d @vcon.json

    docker compose logs -f conserver
    ```

Use this sample for `vcon.json`. Change the `uuid` for each run.

```json
{
  "vcon": "0.4.0",
  "uuid": "018f0f2e-6c1a-8e3b-9a6d-2f4d1c7b9e10",
  "created_at": "2026-01-15T10:30:00Z",
  "parties": [
    {"tel": "+15551230100", "name": "Agent"},
    {"tel": "+15551230101", "name": "Caller"}
  ],
  "dialog": [
    {
      "type": "text",
      "start": "2026-01-15T10:30:00Z",
      "parties": [0, 1],
      "mediatype": "text/plain",
      "encoding": "none",
      "body": "Hello, I would like to check my order."
    }
  ]
}
```

## Replace a lifecycle hook

Three modules ship as no-ops. They are not configured in YAML: you replace the file when you build your image.

| File | Functions | Runs |
|---|---|---|
| `conserver/hook.py` | `before_processing`, `after_processing` | Around each chain run. A falsy return from `before_processing` skips the vCon with no dead letter entry |
| `conserver/after_link_hook.py` | `after_link` | After each link, on success or error |
| `api/vcon_hook.py` | `on_vcon_created`, `on_vcon_deleted` | When the REST API creates or deletes a vCon |

The code comments suggest audit logging, metrics and notifications. [Creating links](creating-links.md#follow-the-link-contract) shows where the conserver hooks fall in a run.

## Continue with these guides

- [Creating links](creating-links.md)
- [Creating storage adapters](creating-storage-adapters.md)
- [Creating tracers](creating-tracers.md)
- [Dynamic modules](dynamic-modules.md)
