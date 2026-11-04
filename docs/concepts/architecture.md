# Server architecture

This page shows which process does what, so you can place a config change or a fault in the right service before you open the reference pages.

vCon Server is two Python services around one Redis instance. The `api` service takes vCons in and serves them back. The `conserver` service runs them through chains. The services never call each other. They share Redis, the YAML config file and the storage backends.

## See the system context

```mermaid
--8<-- "docs/diagrams/D01-system-context.mmd"
```

Dashed edges exist only when the config asks for them. Storage and link edges are solid, but the config still picks each system. [Open the diagram as an SVG](../diagrams/D01-system-context.svg).

| Part | Code | Job |
|---|---|---|
| `api` service | `api/api.py` | FastAPI app. Accepts vCons, pushes UUIDs to lists, reads and deletes vCons, replays dead letter queues |
| `conserver` service | `conserver/main.py` | Runs the workers and any followers. Workers pop UUIDs and run chains |
| Redis | `common/redis_mgr.py`, `common/lib/queue.py` | Holds working vCons, lists and indexes. Plain Redis, with no modules |
| Config file | `common/config.py` | YAML file named by `CONSERVER_CONFIG_FILE`. Defines chains, links, storages, tracers and followers |
| Storage backends | `common/storage/` | Keep vCons after a chain finishes. Chosen per chain |

[Ports and services](../reference/ports.md) lists the Compose services and published ports. [Authentication](../configuration/authentication.md) covers the API keys.

## Trace the ingress paths

Every path ends the same way. A vCon UUID lands on a Redis list and a worker pops it. The list carries only the UUID. The vCon body sits in its own Redis key.

```mermaid
--8<-- "docs/diagrams/D04-ingress-paths.mmd"
```

[Open the diagram as an SVG](../diagrams/D04-ingress-paths.svg).

| Path | Takes | Behaviour to expect |
|---|---|---|
| `POST /vcon` | A full vCon | Stores and indexes it. Queues it only when the request names `ingress_lists` |
| `POST /vcon/external-ingress` | A full vCon | Stores and indexes it, then queues it on the one `ingress_list` its key allows |
| `POST /vcon/ingress` | A list of UUIDs | Queues vCons that already exist. Loads a missing body from storage, and logs and skips a UUID found nowhere |
| Follower | UUIDs from another server | Pops the upstream egress list, copies each body into Redis, with no TTL on a new key and any existing TTL kept, then queues it. It adds no sorted set or party index entry |
| Internal re-entry | A UUID | A chain's `egress_lists`, the `tag_router` link and `POST /dlq/reprocess` all push to lists a chain may read |

A worker reads only the lists named in some chain's `ingress_lists`. The API does not check this, so a push to any other list waits there unread.

The follower pop is destructive on the upstream side. If the upstream then returns 404 for a UUID, the follower logs the error and drops it.

The [API reference](../reference/api.md) has the request shapes. [Pull from another server](../configuration/yaml-configuration.md#pull-from-another-server) has the follower keys.

## Keep working state in Redis

Redis is the working copy. Links read a vCon from it and write it back, and the storage backends are where it stays once Redis lets it go.

| Key | Type | Holds |
|---|---|---|
| `vcon:<uuid>` | String | The vCon as JSON, written with `SET` |
| Each ingress or egress list | List | vCon UUIDs waiting for a chain or a follower |
| `DLQ:<ingress list>` | List | UUIDs that failed in a link |
| `DLQ:storage:<backend>` | List | UUIDs whose write to one backend failed |
| `VCON_SORTED_SET_NAME`, default `vcons` | Sorted set | vCons by creation time, for listing |
| `tel:<value>`, `mailto:<value>`, `name:<value>` | Set | Party search index, kept for `VCON_INDEX_EXPIRY` seconds |
| `context:<list>:<uuid>` | List | Trace context passed from the producer to the worker |

On a Redis miss, the server tries every backend under `storages:` in config order and re-caches the first hit. On the API path, a backend that fails to load or raises from `get` fails the request with a 500 and later backends are not tried. `VconRedis` logs the error and moves to the next backend. This covers all configured backends, not only the ones in the current chain. A backend with no `get` never answers. `VCON_STORAGE_FALLBACK_ENABLED` switches this off for `VconRedis`, the class links use. The API read path has its own lookup and ignores that setting.

[vCon lifecycle](vcon-lifecycle.md) follows a vCon through these keys and its expiry times.

## Run the conserver processes

At startup the main process starts any followers, then runs the workers. With `CONSERVER_WORKERS` at its default of 1, the single worker runs in the main process. With more, the main process spawns one process per worker, checks them every 5 seconds and restarts any that die.

Each worker blocks on `BLPOP` across all ingress lists, with a 15 second timeout. Redis gives each UUID to one worker. `CONSERVER_VCON_CONCURRENCY` lets a worker run several chains at once on threads.

On `SIGTERM` or `SIGINT`, a worker stops taking work. A UUID popped just as the signal arrived goes back to the head of its list.

[Worker configuration](../configuration/workers.md) covers sizing and start methods.

## Read the configuration file

The two services read the YAML file separately. A worker re-reads it on each loop, so most edits apply without a restart. Environment variables do not: each process reads them when it starts. `POST /config` overwrites the whole file.

[Plan for reloads](../configuration/yaml-configuration.md#plan-for-reloads) says which sections reload. [Environment variables](../reference/environment.md) lists every setting.

## Separate the two failure paths

A link failure and a storage failure take different routes, because they need different repairs.

| Failure | Where the UUID goes | What a replay does |
|---|---|---|
| A link raises an exception | `DLQ:<ingress list>` | Runs the whole chain again |
| One storage write fails | `DLQ:storage:<backend>` | Repeats that write alone. The chain itself does not fail |

Both paths use `VCON_DLQ_EXPIRY` to keep the vCon body in Redis long enough to replay. See [Dead Letter Queue](../operations/dead-letter-queue.md) and [storage recovery](../operations/storage-recovery.md).

## Continue with related pages

- [Chains, links and storage](chains-links-storage.md) explains what happens inside a worker.
- [vCon lifecycle](vcon-lifecycle.md) tracks one vCon from ingress to expiry.
- [Monitoring](../operations/monitoring.md) covers metrics and traces, and [the metric list](../reference/metrics.md) names them.
