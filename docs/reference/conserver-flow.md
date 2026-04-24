# Conserver End-to-End Flow

This document traces a vCon from the moment it arrives at the conserver through every chain, link, storage, and egress step, calling out each Redis interaction along the way.

## 1. High-Level Architecture

The conserver is a Redis-backed pipeline. vCons (Virtual Conversations, JSON documents) are created or submitted via the HTTP API, their UUIDs are pushed onto named Redis lists ("ingress lists"), and worker processes pop UUIDs off those lists and drive them through a configured **chain**. A chain is a sequence of **links** (processing steps) followed by **storages** (persistence backends) and **egress lists** (downstream queues).

```
API / Follower ──▶ Redis (vcon:{uuid}) ──▶ ingress list ──▶ Worker ──▶ Links ──▶ Storages
                                                                          │
                                                                          └──▶ Egress list ──▶ API consumer / next chain
```

Key concepts:

- **vCon** — JSON document stored at Redis key `vcon:{uuid}` (RedisJSON).
- **Ingress list** — Redis list of UUIDs waiting for chain processing.
- **Chain** — YAML-configured sequence of links + storages + egress lists.
- **Link** — Python module that reads a vCon, mutates it, writes it back.
- **Storage** — Python module that persists a finished vCon to an external backend.
- **Egress list** — Redis list of UUIDs that have finished a chain.
- **DLQ** — `DLQ:{ingress_list}` list where failed UUIDs end up.

## 2. Configuration (`config.yml`)

Everything is wired up in `example_config.yml`. A chain looks like:

```yaml
links:
  transcribe:
    module: links.transcribe
    options: {...}

storages:
  s3:
    module: storage.s3
    options: {...}

chains:
  sample_chain:
    ingress_lists: [test_list]
    links: [transcribe, summary, tag]
    storages: [s3, mongo]
    egress_lists: [test_output]
    enabled: 1
```

The config is loaded by `Configuration.get_config()` in `common/config.py:7` and is **re-read on every worker iteration**, so config changes take effect without a restart.

Relevant env vars (`common/settings.py`):

- `CONSERVER_WORKERS` — number of worker processes (default 1).
- `CONSERVER_PARALLEL_STORAGE` — run storages concurrently (default true).
- `CONSERVER_CONFIG_FILE` — path to the YAML config.
- `REDIS_URL` — Redis connection string.
- `VCON_REDIS_EXPIRY`, `VCON_DLQ_EXPIRY`, `VCON_CONTEXT_EXPIRY` — TTLs.

## 3. Ingress — How a vCon Enters the Conserver

There are three ways a vCon gets into the system:

### 3a. Direct creation via `POST /vcon`

Handled in `api/api.py:731`. The endpoint:

1. Validates the incoming JSON against the vCon schema.
2. Stores the vCon body at Redis key `vcon:{uuid}` as a RedisJSON document.
3. Adds the UUID to the sorted set `vcons` with the `created_at` timestamp as score (used for date-range listing).
4. Builds party indexes: `party:tel:{phone}` and `party:email:{email}` Redis sets containing UUIDs that reference that contact.
5. If the caller supplied `?ingress_lists=...`, extracts the current OpenTelemetry trace context, stores it at `context:{ingress_list}:{uuid}`, and `RPUSH`es the UUID onto each ingress list.

### 3b. Batch ingress via `POST /vcon/ingress`

Handled in `api/api.py:949`. Takes a list of UUIDs and a target ingress list name. For each UUID it:

1. Checks Redis for `vcon:{uuid}`. If missing, it tries to rehydrate from configured storage backends (so a vCon that has aged out of Redis can be re-queued).
2. Stores the trace context at `context:{ingress_list}:{uuid}` **before** pushing the UUID, to avoid a race where a worker pops the UUID before the context is available.
3. `RPUSH`es the UUID onto the named ingress list.

`POST /vcon/external-ingress` (`api/api.py:799`) is the same mechanism but gated by per-ingress-list API keys from `ingress_auth` in the config.

### 3c. Follower pull

`conserver/follower.py:19` runs as a background daemon that polls remote vcon-server instances, fetches their egress output, stores the vCons in the local Redis, and pushes the UUIDs onto a configured follower ingress list.

After ingress, the vCon is represented by three Redis artifacts:

| Key                              | Type        | Purpose                              |
|----------------------------------|-------------|--------------------------------------|
| `vcon:{uuid}`                    | JSON        | The vCon document itself             |
| `{ingress_list}`                 | List        | FIFO queue of UUIDs awaiting work    |
| `context:{ingress_list}:{uuid}`  | List        | OpenTelemetry trace context payload  |

## 4. The Worker Loop

The conserver process spawns `CONSERVER_WORKERS` worker processes. Each one runs `worker_loop(worker_id)` in `conserver/main.py:591`. One iteration does the following:

1. **Reload config.** `get_ingress_chain_map()` (`conserver/main.py:562`) walks `chains` in the config and returns `{ingress_list_name: chain_details}`. Every enabled chain contributes an entry for each of its ingress lists.
2. **Block on Redis.** `r.blpop(all_ingress_lists, timeout=15)` (line 670) atomically pops the first available UUID from any of the configured ingress lists. Redis's own semantics handle fair distribution across workers — no external coordination needed.
3. **Retrieve trace context.** `retrieve_context(r, ingress_list, vcon_id)` (`common/lib/context_utils.py:109`) `LPOP`s the oldest entry from `context:{ingress_list}:{uuid}` and parses it into OTel `trace_id` / `span_id` / `trace_flags`.
4. **Resolve the chain.** `chain_details = ingress_chain_map[ingress_list]` — the worker now knows which links, storages, and egress lists to run.
5. **Call the `before_processing` hook** (`conserver/hook.py`, empty by default).
6. **Build and run a `VconChainRequest`** (see §5).
7. On success, call `after_processing(vcon_id, chain_details, context, error=None)`.
8. On exception, send the UUID to the DLQ (see §8) and call `after_processing(..., error=exc)`.
9. Record metrics: `conserver.main_loop.vcon_processing_time` (histogram) and `conserver.main_loop.count_vcons_processed` (counter).

On shutdown, if a UUID has been popped but not yet processed, the worker `LPUSH`es it back onto its ingress list so no work is lost.

## 5. Chain Processing — `VconChainRequest`

The class `VconChainRequest` (`conserver/main.py:147`) owns a single vCon's journey through a single chain. Its entry point is `process()` at line 173.

```
process()
  ├── _create_span_from_context()   # OTel span linked to the parent trace
  ├── for link in chain["links"]:   # sequential
  │     └── _process_link(link)
  │           ├── import links.<name>
  │           ├── link.run(vcon_uuid, link_name, opts)
  │           └── record conserver.link.execution_time
  └── if chain completed:
        └── _wrap_up()              # egress + storages
```

### Link execution contract

Each link is a Python module under `server/links/<name>/__init__.py` exposing:

- `default_options` — dict of defaults merged with per-chain `options` from YAML.
- `run(vcon_uuid: str, link_name: str, opts: dict) -> str | None | False`.

Inside `run()` a link typically:

1. Loads the vCon: `VconRedis().get_vcon(vcon_uuid)` (`common/lib/vcon_redis.py:12`). This reads `vcon:{uuid}` from Redis and parses it into a `Vcon` object.
2. Does its work — adds a tag, appends an analysis entry, calls an external transcription service, etc.
3. Writes the mutated vCon back: `VconRedis().store_vcon(vcon)` (updates the same `vcon:{uuid}` JSON key).
4. Returns one of:
   - The same UUID → chain continues with the same vCon.
   - A **different** UUID → chain continues with a replacement vCon (used by `tag_router` / fan-out links).
   - `None` or `False` → chain halts. No further links run, **no storages run, no egress push happens**. The vCon simply stays in Redis.

### Example links

- `transcribe`, `openai_transcribe`, `deepgram_link`, `groq_whisper`, `hugging_face_whisper` — speech-to-text.
- `tag`, `check_and_tag`, `tag_router` — tagging and routing by tag.
- `analyze`, `analyze_vcon`, `detect_engagement` — LLM analysis.
- `webhook`, `post_analysis_to_slack`, `scitt`, `datatrails` — external notifications / attestations.
- `jq_link` — JQ-based JSON transformation.
- `expire_vcon` — sets an explicit Redis TTL on `vcon:{uuid}`.
- `sampler` — probabilistic drop (returns `None` to halt).

Each link runs inside its own OpenTelemetry span named `link.<link_name>` with attributes `vcon_id`, `link_name`, `link_index`, `chain_name`, so traces show per-link latency.

## 6. Wrap-Up — Egress and Storage

When all links have run successfully, `_wrap_up()` (`conserver/main.py:313`) handles post-processing.

### 6a. Egress

```python
egress_lists = self.chain_details.get("egress_lists", [])
context = extract_otel_trace_context()
for egress_list in egress_lists:
    if context:
        store_context_sync(r, egress_list, self.vcon_id, context)
    r.lpush(egress_list, self.vcon_id)
```

For each egress list:

1. Extract the current OTel context so downstream consumers can link back to this trace.
2. Write the context to `context:{egress_list}:{uuid}` **before** pushing the UUID (same race-avoidance pattern as ingress).
3. `LPUSH` the UUID onto the egress list.

An egress list can be another chain's ingress list — that's how multi-chain pipelines are built.

Consumers pull from egress via `GET /vcon/egress?egress_list=...&limit=N` (`api/api.py:549`), which `RPOP`s UUIDs off the list.

### 6b. Storages

```python
storage_backends = self.chain_details.get("storages", [])
if is_parallel_storage_enabled() and len(storage_backends) > 1:
    self._process_storage_parallel(storage_backends)
else:
    for storage_name in storage_backends:
        self._process_storage(storage_name)
```

Each storage is a module under `server/storage/<name>/__init__.py` conforming to the interface in `common/storage/base.py:44`:

- `default_options` — config defaults.
- `save(vcon_id, opts)` — persist the vCon.
- `get(vcon_id, opts)` — retrieve it.
- `delete(vcon_id, opts)` — remove it.

`save()` typically reads `vcon:{uuid}` from Redis via `VconRedis`, serialises it, and writes it to the external backend.

Storages run **after all links succeed**. If a link halts the chain (returns `None`/`False`), storages are skipped.

With `CONSERVER_PARALLEL_STORAGE=true` (the default) and more than one backend, storages run concurrently in a `ThreadPoolExecutor` sized to the number of backends. Each storage runs inside an OTel span named `storage.<storage_name>`.

### Example storages

- `file` — local filesystem, optional gzip, optional `YYYY/MM/DD` date folders.
- `mongo` — MongoDB document with `_id = uuid`.
- `postgres` — PostgreSQL.
- `s3` — S3 object at `[s3_path/][YYYY/MM/DD/]{uuid}.vcon`, plus a lookup stub at `lookup/{uuid}.txt`.
- `milvus` — vector DB (embeddings).
- `elasticsearch`, `redis_storage`, `webhook`, `scitt`, `sftp`, `dataverse`, `chatgpt_files`, `vcon_mcp`, `spaceandtime`.

## 7. All Redis Touchpoints

Every Redis interaction the conserver performs, in one table:

| Key / Pattern                     | Type        | Written by                              | Read by                                  |
|-----------------------------------|-------------|-----------------------------------------|------------------------------------------|
| `vcon:{uuid}`                     | JSON        | API create, links via `VconRedis`, storage rehydrate | Links, storages, API `GET /vcon/{uuid}` |
| `vcons`                           | Sorted Set  | API on create (`ZADD` with timestamp)   | API list/paginate endpoints              |
| `party:tel:{phone}`, `party:email:{email}` | Set | API on create (`SADD uuid`)             | API search endpoints                     |
| `{ingress_list}`                  | List        | API `RPUSH`, follower                   | Worker `BLPOP`                           |
| `{egress_list}`                   | List        | Worker `LPUSH` in `_wrap_up()`          | API `RPOP` via `/vcon/egress`, or next chain's `BLPOP` |
| `context:{list}:{uuid}`           | List        | API + `_wrap_up()` via `store_context_sync` | Worker via `retrieve_context` (`LPOP`)   |
| `DLQ:{ingress_list}`              | List        | Worker on exception (`LPUSH`)           | API `/dlq/reprocess` (`RPOP`)            |

TTLs:

- `vcon:{uuid}` — no TTL when created directly; set to `VCON_REDIS_EXPIRY` (default 1h) when rehydrated from a storage backend; extended to `VCON_DLQ_EXPIRY` (default 7d) when the vCon lands in a DLQ.
- `context:{list}:{uuid}` — `VCON_CONTEXT_EXPIRY` (default 1d).

Clients:

- `common/redis_mgr.py:20` — sync client used by the conserver workers and links.
- Async client initialised in the API on startup for FastAPI handlers.

## 8. Failure Handling — The DLQ

If any link or storage raises an exception, the worker's `try/except` around `VconChainRequest.process()` (`conserver/main.py:726`) catches it and:

1. Computes `dlq_name = DLQ:{ingress_list}` via `dlq_utils.get_ingress_list_dlq_name()`.
2. `LPUSH`es the failed UUID onto that DLQ list.
3. Extends the vCon's TTL to `VCON_DLQ_EXPIRY` so operators have time to investigate.
4. Calls `after_processing(..., error=exc)`.
5. Continues to the next iteration — the worker is not killed.

Operators can replay DLQ items back onto their original ingress lists via the API.

## 9. End-to-End Sequence

Putting it all together, the full life of a vCon:

1. **Client** sends `POST /vcon` with the vCon JSON.
2. **API** stores `vcon:{uuid}`, updates `vcons` sorted set, adds party indexes.
3. **API** (if `ingress_lists` query param given, or via a follow-up `POST /vcon/ingress`) stores OTel context at `context:{list}:{uuid}` and `RPUSH`es the UUID onto the ingress list.
4. **Worker** wakes from `BLPOP`, pops `(ingress_list, uuid)`, `LPOP`s the context.
5. **Worker** looks up the chain for that ingress list, builds a `VconChainRequest`.
6. **Worker** runs each link in order. Each link reads `vcon:{uuid}`, mutates it, writes it back. A link may halt the chain by returning falsy or reroute it by returning a different UUID.
7. **Worker** runs `_wrap_up()`:
   - For each egress list: store context, `LPUSH` the UUID.
   - For each storage: call `save(uuid)`, sequentially or in a thread pool.
8. **Worker** records metrics, calls `after_processing`, and returns to `BLPOP`.
9. **Downstream consumer** either `RPOP`s the egress list via `GET /vcon/egress`, or the next chain's worker picks it up via `BLPOP` on the same list.
10. **On failure** at any point, the UUID is moved to `DLQ:{ingress_list}` and the vCon's TTL is extended for later inspection.

## 10. Key Source Locations

- Worker loop: `conserver/main.py:591`
- `VconChainRequest.process`: `conserver/main.py:173`
- Link dispatch: `conserver/main.py:481`
- Wrap-up (egress + storages): `conserver/main.py:313`
- Ingress-to-chain map: `conserver/main.py:562`
- Redis client: `common/redis_mgr.py:20`
- vCon helper: `common/lib/vcon_redis.py:12`
- Context utils: `common/lib/context_utils.py`
- DLQ naming: `common/dlq_utils.py:3`
- Storage base class: `common/storage/base.py:44`
- Config loader: `common/config.py:7`
- API create: `api/api.py:731`
- API batch ingress: `api/api.py:949`
- API egress consumer: `api/api.py:549`
- Follower daemon: `conserver/follower.py:19`
