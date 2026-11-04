# API reference

This page gives each REST endpoint's parameters, responses and status codes, so you can write a client without reading `api/api.py`. For a one-line index of every route, see the generated [API routes](api-routes.md) page.

## Set the base URL

The API listens on port 8000. The Compose file publishes it on `CONSERVER_EXTERNAL_PORT`, default `8000`.

```bash
export API=http://localhost:8000/api
export TOKEN=your-token
```

`API_ROOT_PATH`, default `/api`, sets the FastAPI `root_path`. It does not move the routes. With the versions in `uv.lock`, `/health` and `/api/health` reach the same handler, and the OpenAPI document lists `/api` as its server URL. Examples on this page use the `/api` form.

## Authenticate a request

Each route follows one rule. See [Authentication](../configuration/authentication.md) to configure them.

| Rule | Routes | Check |
|---|---|---|
| API key | All routes not listed below | The header named by `CONSERVER_HEADER_NAME`, default `x-conserver-api-token`, must hold a key from `CONSERVER_API_TOKEN` or `CONSERVER_API_TOKEN_FILE` |
| Ingress API key | `POST /vcon/external-ingress` | The same header must hold a key listed for that ingress list under `ingress_auth` in the configuration |
| None | `GET /version`, `GET /health`, `GET /stats/queue`, and the [generated API pages](#read-the-generated-api-pages) | No check |

```bash
curl -H "x-conserver-api-token: $TOKEN" "$API/vcon"
```

A missing or wrong key on an API key route returns `403` with `{"detail": "Invalid API Key"}`.

!!! warning "No keys means no check"
    With neither `CONSERVER_API_TOKEN` nor `CONSERVER_API_TOKEN_FILE` set, or with an empty token file, every API key route is open. The ingress rule still applies.

The API reads both settings once at startup, so a new key needs a restart. A token file that cannot be opened stops the API from starting.

`GET /stats/queue` has no check and accepts any Redis key name. Anyone who can reach the API can read list depths, so restrict it at your proxy if that matters.

## Read the response headers

The API adds two headers to each response from a handler. An unhandled `500` does not carry them.

| Header | Value |
|---|---|
| `X-Vcon-Server-Version` | `VCON_SERVER_VERSION`, set at image build. `dev` when unset |
| `X-Vcon-Server-Commit` | `VCON_SERVER_GIT_COMMIT`, set at image build. `unknown` when unset |

CORS is open. `CORSMiddleware` allows any origin, method and header, with credentials.

## Monitor the server

### Check server health

```http
GET /health
```

Returns a fixed status plus the version fields. The handler does not touch Redis, so `200` only shows that the API process answers. It still returns `healthy` with Redis down.

```json
{
  "status": "healthy",
  "version": {
    "version": "dev",
    "git_commit": "unknown",
    "build_time": "unknown"
  }
}
```

**Status:** `200`

### Read the server version

```http
GET /version
```

Returns the same three fields, from `VCON_SERVER_VERSION`, `VCON_SERVER_GIT_COMMIT` and `VCON_SERVER_BUILD_TIME`. Images take these as build arguments. Outside an image they read `dev` and `unknown`.

```json
{
  "version": "dev",
  "git_commit": "unknown",
  "build_time": "unknown"
}
```

**Status:** `200`

### Read queue depth

```http
GET /stats/queue
```

Returns the length of a Redis list. Use it for monitoring and backpressure. It works on ingress lists, egress lists and dead letter queues.

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `list_name` | string | Yes | Redis list to measure, such as `test_list` or `DLQ:test_list` |

```bash
curl "$API/stats/queue?list_name=test_list"
```

```json
{"list_name": "test_list", "depth": 3}
```

A list that does not exist reports depth `0`.

| Status | Meaning |
|---|---|
| `200` | Depth returned |
| `422` | `list_name` missing |
| `500` | `Failed to get queue depth`: Redis is unreachable, or the key is not a list |

### Read the generated API pages

FastAPI serves its default pages with no check.

| Route | Content |
|---|---|
| `GET /docs` | Swagger UI |
| `GET /docs/oauth2-redirect` | Swagger UI OAuth helper page |
| `GET /redoc` | ReDoc |
| `GET /openapi.json` | OpenAPI document |

The OpenAPI document comes from the route decorators, so it repeats the two mismatches noted under [Pop UUIDs from an egress list](#pop-uuids-from-an-egress-list) and [Count an egress list](#count-an-egress-list). This page describes what the server returns.

## Manage vCons

### List vCon UUIDs

```http
GET /vcon
```

Returns UUIDs from the sorted set named by `VCON_SORTED_SET_NAME`, default `vcons`, newest `created_at` first.

| Query parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | `1` | Page number, from 1 |
| `size` | int | `50` | Items per page |
| `since` | datetime | none | Keep vCons created at or after this time |
| `until` | datetime | none | Keep vCons created at or before this time |

```bash
curl "$API/vcon?page=1&size=50&since=2026-01-01" \
  -H "x-conserver-api-token: $TOKEN"
```

The response is a plain JSON array, with no total count.

```json
["018f0000-0000-8000-8000-000000000001"]
```

The sorted set has no expiry and no code removes entries from it. A UUID stays listed after its Redis body expires or after [Delete a vCon](#delete-a-vcon).

!!! warning "A storage read-back can break this route"
    When a vCon is restored from a storage backend, the code adds a bare UUID to the sorted set, while `POST /vcon` adds `vcon:<uuid>`. This route then fails with an unhandled `500` on any page that includes the bare member. `GET /index_vcons` does not remove it. To clear it, run `ZREM vcons <uuid>` in Redis.

| Status | Meaning |
|---|---|
| `200` | UUID array, empty past the last page |
| `403` | Bad API key |
| `422` | Bad `page`, `size`, `since` or `until` |
| `500` | See the warning above |

### Fetch one vCon

```http
GET /vcon/{vcon_uuid}
```

Returns the full vCon. On a Redis miss the API tries each configured storage backend in order. A hit is normalized to the current spec, cached in Redis for `VCON_REDIS_EXPIRY` seconds and added to the sorted set. This path does not read `VCON_STORAGE_FALLBACK_ENABLED`, so it always tries storage.

With `EGRESS_FORMAT_VERSION` set, the response uses that legacy format and Redis stays on the current spec. See [Egress compatibility](../configuration/egress-compatibility.md).

```bash
curl "$API/vcon/018f0000-0000-8000-8000-000000000001" \
  -H "x-conserver-api-token: $TOKEN"
```

| Status | Meaning |
|---|---|
| `200` | vCon returned |
| `403` | Bad API key |
| `404` | `vCon not found` in Redis or any storage backend |
| `422` | `vcon_uuid` is not a UUID |
| `500` | A storage backend raised an error, the configuration file cannot be read, or `EGRESS_FORMAT_VERSION` holds an unsupported value |

### Fetch several vCons

```http
GET /vcons
```

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `vcon_uuids` | UUID, repeatable | Yes in practice | Repeat the parameter once per UUID |

```bash
curl "$API/vcons?vcon_uuids=018f0000-0000-8000-8000-000000000001&vcon_uuids=018f0000-0000-8000-8000-000000000002" \
  -H "x-conserver-api-token: $TOKEN"
```

The response is an array in request order. A UUID found nowhere gives `null` in its position. Lookup and egress format follow [Fetch one vCon](#fetch-one-vcon).

| Status | Meaning |
|---|---|
| `200` | Array returned |
| `403` | Bad API key |
| `422` | A value is not a UUID |
| `500` | `vcon_uuids` left out, which the code does not guard against, or a storage error |

### Create a vCon

```http
POST /vcon
```

Stores a vCon in Redis, adds it to the sorted set, indexes its parties for search and optionally queues it.

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `ingress_lists` | string, repeatable | No | Repeat once per list: `?ingress_lists=a&ingress_lists=b`. A comma is part of the name |

```bash
curl -X POST "$API/vcon?ingress_lists=test_list" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{
    "vcon": "0.4.0",
    "uuid": "018f0000-0000-8000-8000-000000000001",
    "created_at": "2026-01-15T10:30:00Z",
    "parties": [{"tel": "+15551234567"}],
    "dialog": []
  }'
```

The response is the stored vCon, with the model's defaults filled in.

```json
{
  "vcon": "0.4.0",
  "uuid": "018f0000-0000-8000-8000-000000000001",
  "created_at": "2026-01-15T10:30:00+00:00",
  "subject": null,
  "redacted": {},
  "appended": null,
  "group": [],
  "parties": [{"tel": "+15551234567"}],
  "dialog": [],
  "analysis": [],
  "attachments": []
}
```

| Status | Meaning |
|---|---|
| `201` | Stored |
| `403` | Bad API key |
| `422` | Body failed [validation](#meet-the-vcon-body-rules) |
| `500` | `Failed to store vCon` |

Behaviour to plan around:

- This route writes to Redis only. The body expires after `VCON_REDIS_EXPIRY` seconds, default 3600. To keep it, queue it on a chain with a storage step.
- A UUID that already exists is overwritten with no conflict error, and its expiry restarts.
- The route does not normalize the body. Empty `redacted` and `group` and the legacy `appended` key stay in Redis until a worker writes the vCon, or a read restores it from storage. Those writes drop the empty keys and rename `appended` to `amended`.
- `api/vcon_hook.py` runs after a create and a delete. The default does nothing, and the API ignores any error it raises.

### Meet the vCon body rules

`POST /vcon` and `POST /vcon/external-ingress` validate the body with the same model. Unknown fields pass through.

| Field | Rule |
|---|---|
| `vcon` | Required string. The model requires it even though the spec marks it optional. Use `"0.4.0"` |
| `uuid` | Required UUID |
| `created_at` | Required datetime |
| `parties[].tel` | Must look like a phone number. An empty string counts as absent. `Anonymous` fails |
| `dialog[].parties` | List of integers, each a valid index into `parties`. A bare integer fails |
| `dialog[].duration` | Zero or more |
| `dialog[].url` | Must have a URL scheme. An empty string counts as absent |
| `dialog[].mimetype` | Must look like a media type. The check does not cover `mediatype`, which passes through |
| `dialog[].alg` | One of `SHA-256`, `SHA-384`, `SHA-512`, or `HS`, `RS`, `ES` or `PS` followed by `256`, `384` or `512` |
| `analysis`, `attachments` | Lists of objects, stored as sent |

The model also fills absent keys with `null` on each party and dialog entry it validates: `tel` on parties, and `duration`, `start`, `parties`, `url`, `mimetype` and `alg` on dialog entries.

The API stores `attachments` entries as sent. That includes a `lawful_basis` attachment, which it carries and does not create, validate or act on. See [Lawful basis](../concepts/lawful-basis.md).

### Delete a vCon

```http
DELETE /vcon/{vcon_uuid}
```

Deletes the Redis body, then calls `delete` on every configured storage backend. A failure on one backend does not stop the others.

```bash
curl -X DELETE "$API/vcon/018f0000-0000-8000-8000-000000000001" \
  -H "x-conserver-api-token: $TOKEN"
```

The route leaves the sorted set entry and the party search indexes in place, so [List vCon UUIDs](#list-vcon-uuids) and [Search vCons by party](#search-vcons-by-party) can still return the UUID. Search entries expire with `VCON_INDEX_EXPIRY`. Sorted set entries do not expire.

| Status | Meaning |
|---|---|
| `204` | Finished. Also returned when the vCon did not exist or a backend failed, so check the logs for failures |
| `403` | Bad API key |
| `422` | `vcon_uuid` is not a UUID |
| `500` | The configuration file cannot be read |

### Search vCons by party

```http
GET /vcons/search
```

| Query parameter | Type | Description |
|---|---|---|
| `tel` | string | Exact phone number |
| `mailto` | string | Exact email address |
| `name` | string | Exact party name |

Supply at least one. Matching is exact: `tel=+1555` does not find `+15551234567`. Encode `+` as `%2B` in a query string.

```bash
curl "$API/vcons/search?tel=%2B15551234567" \
  -H "x-conserver-api-token: $TOKEN"
```

The response is an array of UUIDs in no set order.

```json
["018f0000-0000-8000-8000-000000000001"]
```

Search reads the Redis sets `tel:<value>`, `mailto:<value>` and `name:<value>`. `POST /vcon`, `POST /vcon/external-ingress` and `GET /index_vcons` write them. Each set expires `VCON_INDEX_EXPIRY` seconds after its last write, default 86400. A vCon older than that, or one read back from storage, is not found until you rebuild the index.

With more than one term, the result is not a strict AND:

| Terms | Result |
|---|---|
| Every term has matches | vCons that match all terms |
| Some terms have matches | The terms with no matches are ignored, and the rest are intersected |
| No term has matches | `500` |

A single term with no matches returns `[]`. A term with an empty value, such as `tel=`, does not count as a term, so on its own it also returns `[]`.

| Status | Meaning |
|---|---|
| `200` | Array returned |
| `400` | `At least one search parameter must be provided` |
| `403` | Bad API key |
| `500` | `An error occurred during the search`, including the case above |

## Move vCons through chains

The ingress routes append to the tail of a Redis list. When a trace is active they also store its context for the worker under `context:<list>:<uuid>`, for `VCON_CONTEXT_EXPIRY` seconds. The count of queued vCons appears as `conserver.api.count_vcons_enqueued`. See [Metrics](metrics.md).

### Add vCons to an ingress list

```http
POST /vcon/ingress
```

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `ingress_list` | string | Yes | Ingress list to add to |

The body is a JSON array of UUIDs. It is not an object.

```bash
curl -X POST "$API/vcon/ingress?ingress_list=test_list" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '["018f0000-0000-8000-8000-000000000001"]'
```

The API looks up each vCon in Redis, then in storage. It queues the ones it finds, and logs and skips the rest. The response has no body, so it does not show what was skipped.

| Status | Meaning |
|---|---|
| `204` | Finished, including when every UUID was skipped |
| `403` | Bad API key |
| `422` | `ingress_list` missing, or the body is not an array of UUIDs |
| `500` | `Failed to add to ingress list` |

### Pop UUIDs from an egress list

```http
GET /vcon/egress
```

Removes up to `limit` UUIDs from an egress list and returns them. This is a `GET` that changes state, so do not retry it blindly.

| Query parameter | Type | Default | Description |
|---|---|---|---|
| `egress_list` | string | Required | Egress list to pop from |
| `limit` | int | `1` | Maximum UUIDs to remove |

```bash
curl "$API/vcon/egress?egress_list=processed&limit=5" \
  -H "x-conserver-api-token: $TOKEN"
```

```json
["018f0000-0000-8000-8000-000000000001"]
```

Workers append to the tail and this route pops from the tail, so the newest UUID comes first.

The decorator declares `204`, but the handler returns a JSON body with `200`. Clients receive `200`.

| Status | Meaning |
|---|---|
| `200` | Array returned, empty when the list is empty |
| `403` | Bad API key |
| `422` | `egress_list` missing |
| `500` | `Failed to pop from egress list` |

### Count an egress list

```http
GET /vcon/count
```

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `egress_list` | string | Yes | List to count |

!!! warning "This route cannot be reached"
    `GET /vcon/{vcon_uuid}` is registered first and captures this path, so the request fails UUID validation and returns `422`, with or without `egress_list`. Use [Read queue depth](#read-queue-depth) until the code changes.

The handler is written to return the count as a bare integer, or `500` with `Failed to count egress list`. Neither happens today.

### Submit a vCon from an external system

```http
POST /vcon/external-ingress
```

Lets a third party submit vCons to one ingress list with a key that opens nothing else. The route stores and indexes the vCon as `POST /vcon` does, then always queues it.

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `ingress_list` | string | Yes | Target list. Must appear under `ingress_auth` |

Keys live in the configuration file. A list takes one key or several.

```yaml
ingress_auth:
  third_party_input: third-party-key
  shared_input:
    - first-key
    - second-key
```

```bash
curl -X POST "$API/vcon/external-ingress?ingress_list=third_party_input" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: third-party-key" \
  -d '{
    "vcon": "0.4.0",
    "uuid": "018f0000-0000-8000-8000-000000000001",
    "created_at": "2026-01-15T10:30:00Z",
    "parties": [{"tel": "+15551234567"}],
    "dialog": []
  }'
```

An ingress key fails on every other route, unless the same value is also a main API key. With no main API keys set, the main routes are open to everyone, so the scoping protects nothing there. A main API key fails here unless it is listed for that ingress list. The check runs even when the main API has no keys. The API re-reads `ingress_auth` on each request, so key changes need no restart.

Body and query validation run before the key check, so an invalid body returns `422` even with a bad key.

The [body rules](#meet-the-vcon-body-rules) and the Redis expiry from [Create a vCon](#create-a-vcon) apply here too.

| Status | Detail | Meaning |
|---|---|---|
| `204` | | Stored and queued. No body |
| `403` | `API Key required` | No key in the header |
| `403` | `No ingress authentication configured` | `ingress_auth` is missing or empty |
| `403` | `Ingress list '<name>' not configured` | The list is not under `ingress_auth` |
| `403` | `Invalid configuration for ingress list '<name>'` | The value is neither a string nor a list |
| `403` | `Invalid API Key for ingress list '<name>'` | The key is not listed for this ingress list |
| `422` | | `ingress_list` missing or body invalid |
| `500` | `Failed to store vCon` | Redis or queue failure |
| `500` | `Internal Server Error` | The configuration file cannot be read. The body is plain text |

## Work with dead letter queues

Each ingress list and each storage backend has its own queue. See [Dead letter queue](../operations/dead-letter-queue.md) for how to work with them.

| Queue | Redis list | Holds | Replay runs |
|---|---|---|---|
| Ingress DLQ | `DLQ:<ingress_list>` | vCons whose chain failed | The whole chain |
| Storage DLQ | `DLQ:storage:<storage_name>` | vCons whose write to one backend failed | Only that storage write |

### Read an ingress DLQ

```http
GET /dlq
```

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `ingress_list` | string | Yes | Ingress list that owns the DLQ |

```bash
curl "$API/dlq?ingress_list=test_list" \
  -H "x-conserver-api-token: $TOKEN"
```

The response is the whole list as a JSON array of UUIDs, oldest failure first.

| Status | Meaning |
|---|---|
| `200` | Array returned |
| `403` | Bad API key |
| `422` | `ingress_list` missing |
| `500` | `Failed to read DLQ` |

### Replay an ingress DLQ

```http
POST /dlq/reprocess
```

Moves items from `DLQ:<ingress_list>` to the tail of the ingress list, oldest first.

| Query parameter | Type | Default | Description |
|---|---|---|---|
| `ingress_list` | string | Required | Ingress list to replay to |
| `count` | int | `1000` | Maximum items to move, from 1 to 100000 |

```bash
curl -X POST "$API/dlq/reprocess?ingress_list=test_list&count=1000" \
  -H "x-conserver-api-token: $TOKEN"
```

The response is the number of items moved, as a bare integer. To drain a large DLQ, call the route until it returns `0`.

| Status | Meaning |
|---|---|
| `200` | Count returned |
| `403` | Bad API key |
| `422` | `ingress_list` missing or `count` out of range |
| `500` | `Failed to reprocess DLQ` |

### Read a storage DLQ

```http
GET /dlq/storage
```

| Query parameter | Type | Required | Description |
|---|---|---|---|
| `storage_name` | string | Yes | Storage backend name from the configuration |

```bash
curl "$API/dlq/storage?storage_name=s3" \
  -H "x-conserver-api-token: $TOKEN"
```

The response is a JSON array of UUIDs. The route does not check the name, so an unknown backend returns `[]`.

| Status | Meaning |
|---|---|
| `200` | Array returned |
| `403` | Bad API key |
| `422` | `storage_name` missing |
| `500` | `Failed to read storage DLQ` |

### Replay a storage DLQ

```http
POST /dlq/storage/reprocess
```

Retries the storage write for vCons in `DLQ:storage:<storage_name>`, oldest first. The chain does not run again.

| Query parameter | Type | Default | Description |
|---|---|---|---|
| `storage_name` | string | Required | Storage backend to retry |
| `count` | int | `1000` | Maximum items to retry, from 1 to 100000 |

```bash
curl -X POST "$API/dlq/storage/reprocess?storage_name=s3&count=1000" \
  -H "x-conserver-api-token: $TOKEN"
```

The response is the number of successful writes, as a bare integer.

- An item leaves the DLQ only after its write succeeds.
- The first failed write ends the call. The response is still `200` with the count so far, and `0` does not prove the DLQ is empty. Check with [Read a storage DLQ](#read-a-storage-dlq).
- Recovery is at least once. A backend can see the same UUID twice.
- The write reads the vCon through `VconRedis`, so it needs the body in Redis or in another configured backend. Most adapters then fail and the item stays. `scitt` logs a warning and counts a success, so the item leaves the DLQ with nothing registered.

One replay runs per backend, under the Redis lock `DLQ:storage:<storage_name>:replay-lock`. The lock has no expiry. If a process dies during a replay, the lock stays and each later call returns `409`. Confirm that no replay is running, then delete that key.

| Status | Meaning |
|---|---|
| `200` | Count returned |
| `403` | Bad API key |
| `404` | `Unknown storage backend: <name>`. Any failure to load the backend gives this, not only an unknown name |
| `409` | `Storage replay already running or requires lock recovery` |
| `422` | `storage_name` missing or `count` out of range |
| `500` | `Failed to reprocess storage DLQ` |

## Manage the configuration

### Read the configuration

```http
GET /config
```

Returns the configuration file as JSON. The API reads the file on each call.

```bash
curl "$API/config" -H "x-conserver-api-token: $TOKEN" | jq .
```

!!! warning "Secrets in the response"
    The response holds the whole file, including `ingress_auth` keys and any credentials in link or storage options.

| Status | Meaning |
|---|---|
| `200` | Configuration returned |
| `403` | Bad API key |
| `500` | `Failed to read configuration` |

### Replace the configuration

```http
POST /config
```

Writes the JSON body to the file named by `CONSERVER_CONFIG_FILE`, as YAML. This replaces the whole file. It is not a partial update.

```bash
curl -X POST "$API/config" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d @config.json
```

- The API checks only that the body is a JSON object. A bad configuration is written as sent.
- Comments and key order in the file are lost.
- The route reads the variable directly. If `CONSERVER_CONFIG_FILE` is unset, it returns `500`, even though reads fall back to `./example_config.yml`.
- Most sections need no restart: the API re-reads the file on each use and workers re-read it on each pass of their loop, as long as they share the file. `imports` apply only when a worker starts, and `followers` only when the conserver process starts. See [reload timing](../configuration/yaml-configuration.md#plan-for-reloads). Environment variables still need a restart.

| Status | Meaning |
|---|---|
| `204` | Written. No body |
| `403` | Bad API key |
| `422` | Body is not a JSON object |
| `500` | `Failed to update configuration` |

### Rebuild the search index

```http
GET /index_vcons
```

Runs Redis `KEYS vcon:*`, then for each key adds the vCon to the sorted set and rewrites its party search entries. This is a `GET` that changes state. `KEYS` blocks Redis while it runs, so take care on a large database.

Only vCons in Redis are indexed, and the rebuild removes nothing.

```bash
curl "$API/index_vcons" -H "x-conserver-api-token: $TOKEN"
```

The response is the number of keys found, as a bare integer.

| Status | Meaning |
|---|---|
| `200` | Count returned |
| `403` | Bad API key |
| `500` | Body `{"detail": "Internal Server Error"}` |

## Handle error responses

Errors raised by a handler have a string `detail`.

```json
{"detail": "vCon not found"}
```

A `422` from request validation has a list instead.

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "list_name"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

An unhandled error, such as Redis being down on a route with no error handling, returns `500` with the plain text body `Internal Server Error`.

## Limit the request rate

The API has no rate limiting, and neither does the `nginx.conf` in this repo. Add it at your reverse proxy.

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

server {
    location /api {
        limit_req zone=api burst=200 nodelay;
        proxy_pass http://api:8000;
    }
}
```

## Write a client

This repo ships no client library. These short classes show the request shapes.

### Python

```python
import requests


class VconClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"x-conserver-api-token": token}

    def get_vcon(self, vcon_uuid):
        response = requests.get(f"{self.base_url}/vcon/{vcon_uuid}", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def create_vcon(self, vcon, ingress_lists=None):
        response = requests.post(
            f"{self.base_url}/vcon",
            headers=self.headers,
            params={"ingress_lists": ingress_lists or []},
            json=vcon,
        )
        response.raise_for_status()
        return response.json()

    def search(self, **terms):
        response = requests.get(f"{self.base_url}/vcons/search", headers=self.headers, params=terms)
        response.raise_for_status()
        return response.json()


client = VconClient("http://localhost:8000/api", "your-token")
uuids = client.search(tel="+15551234567")
```

### JavaScript

```javascript
class VconClient {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl;
    this.headers = { 'x-conserver-api-token': token, 'Content-Type': 'application/json' };
  }

  async request(path, options = {}) {
    const response = await fetch(`${this.baseUrl}${path}`, { headers: this.headers, ...options });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  getVcon(uuid) {
    return this.request(`/vcon/${uuid}`);
  }

  createVcon(vcon, ingressLists = []) {
    const query = new URLSearchParams(ingressLists.map((name) => ['ingress_lists', name]));
    return this.request(`/vcon?${query}`, { method: 'POST', body: JSON.stringify(vcon) });
  }

  search(terms) {
    return this.request(`/vcons/search?${new URLSearchParams(terms)}`);
  }
}

const client = new VconClient('http://localhost:8000/api', 'your-token');
const uuids = await client.search({ tel: '+15551234567' });
```
