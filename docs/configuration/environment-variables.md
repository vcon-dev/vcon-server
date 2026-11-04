# Configure the server with environment variables

Environment variables set how the server connects, scales and reports. The [YAML file](yaml-configuration.md) sets what it does to each vCon.

This page groups the variables by task. The [environment reference](../reference/environment.md) is generated from the code and lists every variable, with its default, type and the file that reads it.

## Load variables from a .env file

`common/settings.py` calls `dotenv.load_dotenv()` on import, so a `.env` file works the same as exported variables. Docker Compose passes the same file to `api` and `conserver` through `env_file`.

Start from the example:

```bash
cp .env.example .env
```

This set is enough for the Compose stack:

```bash
REDIS_URL=redis://redis
CONSERVER_CONFIG_FILE=/app/config.yml
LOGGING_CONFIG_FILE=common/logging_dev.conf
CONSERVER_API_TOKEN=replace-with-a-long-random-value
```

Watch for these behaviours:

- Each process reads its variables at startup. After a change, run `docker compose up -d api conserver`. `docker compose restart` does not reread `.env`.
- An empty value is not the same as unset. `CONSERVER_CONFIG_FILE=` gives an empty path, not the default, and the server fails when it opens the file. `.env.example` ships that line empty, so fill it in.
- An empty value on an integer variable, such as `CONSERVER_WORKERS=`, raises `ValueError` on import.
- `.env.example` sets `LOGGING_CONFIG_FILE=server/logging_dev.conf`, and the repo has no `server/` folder. Use `common/logging_dev.conf`, or remove the line to use `common/logging.conf`.

## Connect the server to Redis

`REDIS_URL` is the one connection every process needs. The default is `redis://localhost`.

```bash
# Service on the Compose network
REDIS_URL=redis://redis

# External Redis with a password and a database number
REDIS_URL=redis://:password@redis-host:6379/0
```

The Docker entrypoint, `docker/wait_for_redis.sh`, pings this URL before it starts the service. With `REDIS_URL` unset or empty it skips the wait.

## Point the server at its files

| Variable | Use |
|---|---|
| `CONSERVER_CONFIG_FILE` | Path to the [YAML configuration](yaml-configuration.md). Compose mounts `./config.yml` at `/app/config.yml`, so use that path there. `POST /config` needs this variable set, because it does not use the `./example_config.yml` default |
| `LOGGING_CONFIG_FILE` | Path to a Python logging config. See [logging](../operations/logging.md) |

`LOG_LEVEL` has no effect. Set levels in the logging config file.

## Protect the API with keys

| Variable | Use |
|---|---|
| `CONSERVER_API_TOKEN` | One API key |
| `CONSERVER_API_TOKEN_FILE` | Path to a file of keys, one per line, added to the key above. The API reads it once at startup |
| `CONSERVER_HEADER_NAME` | Header that carries the key. The default is `x-conserver-api-token` |

With no key set, the main API routes are open. Keys for `POST /vcon/external-ingress` live in the `ingress_auth` section of the YAML file. See [authentication](authentication.md).

## Run the API behind a proxy

`API_ROOT_PATH` sets the FastAPI `root_path`, default `/api`, for a proxy that strips that prefix. It does not add the prefix to routes, so the app still serves `/vcon` and `/health`.

`CONSERVER_EXTERNAL_PORT` sets the host port Compose publishes for the `api` service, default `8000`. See [ports and services](../reference/ports.md).

## Tune worker throughput

| Variable | Default | Use |
|---|---|---|
| `CONSERVER_WORKERS` | `1` | Worker processes. Suits CPU-bound chains |
| `CONSERVER_VCON_CONCURRENCY` | `1` | vCons in flight per worker, in a thread pool. Suits chains that wait on the network |
| `CONSERVER_PARALLEL_STORAGE` | `true` | Writes to a chain's storage backends at the same time when it has more than one |
| `CONSERVER_START_METHOD` | platform default | `fork`, `spawn` or `forkserver`. Used only when `CONSERVER_WORKERS` is above 1 |

At most `CONSERVER_WORKERS` times `CONSERVER_VCON_CONCURRENCY` vCons run at once. [Workers](workers.md) covers sizing.

## Set Redis retention

| Variable | Default | Controls |
|---|---|---|
| `VCON_REDIS_EXPIRY` | `3600` | TTL on vCons written by `POST /vcon` and `POST /vcon/external-ingress`, and on vCons cached back from storage |
| `VCON_DLQ_EXPIRY` | `604800` | TTL once a vCon reaches a dead letter queue |
| `VCON_CONTEXT_EXPIRY` | `86400` | TTL on the ingress context stored beside a queue entry |
| `VCON_INDEX_EXPIRY` | `86400` | TTL on the party search keys the API writes |
| `VCON_STORAGE_FALLBACK_ENABLED` | `true` | Whether a Redis miss in `VconRedis.get_vcon` tries the storage backends |
| `VCON_SORTED_SET_NAME` | `vcons` | Redis sorted set that orders vCons by time |

Set `VCON_REDIS_EXPIRY` above your longest queue wait. A vCon that expires in the queue, with no copy in a storage backend, comes back as `None` from `VconRedis.get_vcon`.

`VCON_DLQ_EXPIRY` works differently on the two dead letter queues. The ingress DLQ sets the TTL to this value. The storage DLQ only raises a lower TTL. `0` leaves the TTL as it is on both. See the [dead letter queue](../operations/dead-letter-queue.md).

## Give links their vendor keys

Most vendor keys belong in link options in the YAML file, not in the environment. The YAML loader does not expand `${VAR}`, so write the value itself. See [links](yaml-configuration.md#add-processing-links).

Two variables act as defaults for a link option:

| Variable | Link | Option it fills |
|---|---|---|
| `GROQ_API_KEY` | `groq_whisper`, also through `links.transcribe` with `vendor: groq` | `API_KEY` |
| `OPENAI_API_KEY` | `detect_engagement` | `OPENAI_API_KEY` |

The link reads the variable when its module loads. Other links that use OpenAI take the key from their own options. `DEEPGRAM_KEY` in the environment has no effect, so set `DEEPGRAM_KEY` in the link options.

## Emit a legacy vCon format

Set `EGRESS_FORMAT_VERSION=0.0.1` for downstream consumers that still need the old schema. Set it on both `api` and `conserver`. See [egress format compatibility](egress-compatibility.md).

## Export metrics and traces

| Variable | Use |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP endpoint. Unset or empty, the metric helpers do nothing |
| `OTEL_SERVICE_NAME` | `service.name` on metrics. Compose sets `api` and `conserver` |
| `OTEL_METRIC_EXPORT_INTERVAL` | Metric export interval in milliseconds, default `5000` |

The `api` and `conserver` Compose commands run under `opentelemetry-instrument`, which also takes `OTEL_EXPORTER_OTLP_PROTOCOL`, `OTEL_EXPORTER_OTLP_INSECURE` and `OTEL_EXPORTER_OTLP_HEADERS`.

The server's own metrics always use the OTLP gRPC exporter, and `OTEL_EXPORTER_OTLP_PROTOCOL` does not change that. An endpoint that accepts only `http/protobuf`, such as the Langfuse examples in `.env.example`, suits the auto-instrumented traces and not those metrics.

The [metrics reference](../reference/metrics.md) lists the metric names. [Monitoring](../operations/monitoring.md) covers the setup.

## Report errors to Sentry

Set `SENTRY_DSN` to turn on Sentry. `ENV` must then be set too, because `common/lib/error_tracking.py` reads it directly and raises `KeyError` without it. The `dev` default in `settings` does not apply there.

`VCON_SERVER_GIT_COMMIT`, when set, becomes the Sentry release.

## Configure the Space and Time adapter

The `spaceandtime` storage adapter reads its settings from the environment, not from YAML options.

| Variable | Use |
|---|---|
| `SXT_API_KEY` | API key |
| `SXT_VCON_TABLENAME` | Table name |
| `SXT_VCON_TABLE_WRITE_BISCUI` | Write biscuit. The code reads this exact name, with no final `T` |

## Read the build information

`VCON_SERVER_VERSION`, `VCON_SERVER_GIT_COMMIT` and `VCON_SERVER_BUILD_TIME` are Docker build arguments that the images keep as variables. `GET /version` returns them. Without them the values are `dev` and `unknown`.

## Skip the variables with no effect

The code reads these variables and then never uses the value. Older guides mention some of them.

| Variable | Note |
|---|---|
| `DEEPGRAM_KEY` | Set the key in link options |
| `HOSTNAME` | |
| `LOG_LEVEL` | Set levels in the logging config file |
| `TICK_INTERVAL` | |
| `UUID8_DOMAIN_NAME` | |
| `VCON_SORTED_FORCE_RESET` | |
| `VCON_STORAGE` | The API defines a Peewee model on it, and nothing uses the model |
| `WEVIATE_API_KEY`, `WEVIATE_HOST` | Spelled this way in the code |
