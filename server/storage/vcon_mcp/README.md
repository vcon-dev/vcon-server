# vCon-MCP REST Storage Module for vCon Server

This module implements the vcon-server storage interface by delegating to the **vcon-mcp** project via its REST API. For a given `vcon_id`, it saves, gets, and deletes vCons using vcon-mcp’s HTTP endpoints.

## Features

- **save(vcon_id, opts)** – Loads the vCon from Redis and POSTs it to vcon-mcp `POST /vcons`.
- **get(vcon_id, opts)** – Returns the vCon by calling vcon-mcp `GET /vcons/:uuid`; returns `None` if not found.
- **delete(vcon_id, opts)** – Removes the vCon via vcon-mcp `DELETE /vcons/:uuid`; returns `True` if deleted, `False` if not found.

## Configuration

Options (e.g. in `config.yml` under `storages.<name>.options`):

| Option    | Description                                      | Default                        |
| --------- | ------------------------------------------------ | ------------------------------ |
| base_url  | vcon-mcp REST API base (e.g. `/api/v1` included) | `http://127.0.0.1:3000/api/v1` |
| api_key   | Optional. Sent as `Authorization: Bearer <key>`   | `""`                           |
| timeout   | Request timeout in seconds                       | `30`                           |

Example in `config.yml`:

```yaml
storages:
  vcon_mcp:
    module: storage.vcon_mcp
    options:
      base_url: http://127.0.0.1:3000/api/v1
      api_key: ""   # set if vcon-mcp API_AUTH_REQUIRED is true
      timeout: 30
```

Add the storage name (e.g. `vcon_mcp`) to a chain’s `storages` list so vCons are written to vcon-mcp after processing.

## vcon-mcp REST API

The module uses these endpoints (relative to `base_url`):

- **POST /vcons** – Create/ingest a single vCon (body: vCon JSON).
- **GET /vcons/:uuid** – Get a vCon by UUID (response: `{ "success": true, "vcon": {...} }`).
- **DELETE /vcons/:uuid** – Delete a vCon by UUID.

Ensure vcon-mcp is running with HTTP transport (`MCP_TRANSPORT=http`) and that `base_url` matches its `REST_API_BASE_PATH` (default `/api/v1`).

## Dependencies

- `requests` – HTTP client for calling vcon-mcp.

## Error Handling

- **save**: Raises if the vCon is missing in Redis or if the vcon-mcp request fails (e.g. 4xx/5xx).
- **get**: Returns `None` on 404 or other request errors (errors are logged).
- **delete**: Returns `False` on 404; raises on other request errors.

## Usage

Used like other storages via the storage base class:

```python
from storage.base import Storage

storage = Storage("vcon_mcp")
storage.save(vcon_id)
vcon_dict = storage.get(vcon_id)
deleted = storage.delete(vcon_id)
```
