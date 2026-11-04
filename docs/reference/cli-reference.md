# CLI reference

This page lists the commands that run, test and inspect the server, so you can find the right one without reading the Dockerfiles.

The repo installs no command of its own: `pyproject.toml` defines no scripts. The worker and the API take no flags. Configure them with environment variables, listed on the generated [Environment variables](environment.md) page.

## Set up a local environment

The project uses uv with `uv.lock`, and needs Python 3.12 or 3.13.

```bash
uv sync --frozen --group conserver --group api --group dev
export PYTHONPATH=.:common:conserver:api
```

Run these from the repo root. The code imports from `common/`, `conserver/` and `api/` as top-level paths, so it needs `PYTHONPATH`. `pytest.ini` and the `docker/Dockerfile` image set the same paths. `Dockerfile.conserver` leaves out `api`, and `Dockerfile.api` leaves out `conserver`. `common/settings.py` also loads a `.env` file, and `.env.example` shows the format.

| Group | Adds |
|---|---|
| `storage` | Storage backend clients |
| `storage-milvus` | Milvus backend. Kept out of `storage` for its size |
| `api` | `storage`, plus FastAPI, uvicorn and gunicorn |
| `conserver` | `storage`, plus the packages links use, and `watchdog` |
| `conserver-local` | `transformers` for local Hugging Face inference |
| `dev` | pytest, black and test helpers. `uv sync` includes it by default |

### Manage dependencies

```bash
# Add a runtime dependency
uv add package-name

# Add to a group
uv add --group dev package-name

# Upgrade the lock file
uv lock --upgrade

# Show outdated packages
uv tree --outdated
```

## Run the worker

The worker runs the chains. Its entry point is `conserver/main.py`.

```bash
uv run python conserver/main.py
```

With OpenTelemetry, as the Docker images run it:

```bash
uv run opentelemetry-instrument python conserver/main.py
```

`SIGTERM` or `SIGINT` starts a graceful shutdown: each worker finishes its current vCon and exits. See [Workers](../configuration/workers.md) for `CONSERVER_WORKERS` and related settings.

## Run the API server

The FastAPI app is `app` in `api/api.py`, loaded as `api:app`.

```bash
# Basic
uv run uvicorn api:app --host 0.0.0.0 --port 8000

# Development, with reload
uv run uvicorn api:app --reload --host 0.0.0.0 --port 8000

# With OpenTelemetry, as the Docker images run it
uv run opentelemetry-instrument uvicorn api:app --host 0.0.0.0 --port 8000

# Several workers under gunicorn
uv run gunicorn api:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000
```

### Set uvicorn options

| Option | Description |
|---|---|
| `--host` | Bind address. Default `127.0.0.1` |
| `--port` | Bind port. Default `8000` |
| `--reload` | Restart on code changes. Cannot combine with `--workers` |
| `--workers` | Number of worker processes |
| `--log-level` | One of `critical`, `error`, `warning`, `info`, `debug`, `trace` |
| `--access-log`, `--no-access-log` | Turn the access log on or off |

## Run with Docker Compose

Compose needs the external network, a `.env` file and a `config.yml` before it starts. See [Docker installation](../installation/docker.md).

```bash
docker network create conserver
```

`redis`, `conserver` and `api` always start. `postgres`, `elasticsearch` and `langfuse` start only through `COMPOSE_PROFILES` in `.env`. See [Ports](ports.md) for what each one publishes.

```bash
# Build
docker compose build
docker compose build --no-cache
docker compose build conserver

# Start
docker compose up -d
docker compose up -d conserver

# Run more worker containers
docker compose up -d --scale conserver=4

# Read logs
docker compose logs -f
docker compose logs --tail=100 conserver
docker compose logs --since=1h conserver

# Stop and remove
docker compose stop
docker compose restart
docker compose down

# Open a shell
docker compose exec conserver bash
```

!!! danger "Data loss"
    `docker compose down -v` also deletes the named volumes, including Redis data.

Compose runs the worker under `watchmedo auto-restart`, so it restarts when a `.py` file changes in the mounted repo. `stop_grace_period` is 5 seconds. A worker still busy after that is killed.

## Run the tests

The API and Redis tests need Redis at `REDIS_URL`. `pytest.ini` sets the import paths and loads `.env.test`, and `.env.test.example` shows the format.

```bash
# All tests
uv run pytest

# Common options
uv run pytest -v
uv run pytest -x
uv run pytest --maxfail=5 --disable-warnings

# One file or one test
uv run pytest common/tests/test_api.py
uv run pytest common/tests/test_api.py::test_api_vcon_lifecycle

# By marker
uv run pytest -m integration
uv run pytest -m "not integration"

# With coverage
uv run pytest --cov --cov-report=html
```

CI runs the tests in the conserver container, whose dev image includes every group the tests need:

```bash
docker compose run --rm conserver pytest --maxfail=5 --disable-warnings --cov
```

Format code with black, which reads its settings from `pyproject.toml`:

```bash
uv run black api common conserver
```

## Inspect Redis

In Compose, prefix these with `docker compose exec redis`. vCons are plain JSON strings, so `GET` reads them.

| Purpose | Command |
|---|---|
| Check the connection | `redis-cli ping` |
| Read a vCon | `redis-cli GET vcon:<uuid>` |
| See a vCon's remaining lifetime | `redis-cli TTL vcon:<uuid>` |
| Measure a queue | `redis-cli LLEN <list>` |
| Read a queue | `redis-cli LRANGE <list> 0 -1` |
| Read an ingress DLQ | `redis-cli LRANGE DLQ:<ingress_list> 0 -1` |
| Read a storage DLQ | `redis-cli LRANGE DLQ:storage:<storage_name> 0 -1` |
| List recent vCons | `redis-cli ZREVRANGE vcons 0 9` |
| Read a party search entry | `redis-cli SMEMBERS tel:<number>` |
| Find keys without blocking | `redis-cli --scan --pattern 'vcon:*'` |
| Show server details | `redis-cli INFO` |

The API exposes most of this over HTTP, which suits scripts:

```bash
API=http://localhost:8000/api
curl -s "$API/health"
curl -s "$API/stats/queue?list_name=test_list"
curl -s "$API/stats/queue?list_name=DLQ:test_list"
```

`/health` does not check Redis. `/stats/queue` does, and returns `500` when Redis is down. See the [API reference](api.md).

For backups, see [Backup and restore](../operations/backup-restore.md).

## Use the repository scripts

### Install and remove a server

`scripts/install_conserver.sh` sets up a server on Ubuntu. See [Automated script](../installation/automated-script.md).

| Option | Required | Description |
|---|---|---|
| `-d`, `--domain DOMAIN` | Yes | Domain name for the installation |
| `-e`, `--email EMAIL` | Yes | Email for DNS registration |
| `-t`, `--token TOKEN` | No | API token. Default is a random value |
| `-h`, `--help` | No | Show help |

`scripts/uninstall_conserver.sh` takes no options. It must run as root and asks for confirmation.

!!! danger "Data loss"
    The uninstall script removes containers, images, volumes, networks, data and the `vcon` user. It cannot be undone.

### Migrate Redis data

`scripts/migrate_redis_json.py` copies a stopped Redis database to an empty target and converts RedisJSON values. See [Redis migration](../installation/redis-migration.md).

```bash
REDIS_MIGRATION_SOURCE_URL=redis://old:6379 \
REDIS_MIGRATION_TARGET_URL=redis://new:6379 \
uv run python scripts/migrate_redis_json.py --match '*' --writers-stopped
```

| Option | Required | Description |
|---|---|---|
| `--match PATTERN` | Yes | Key pattern to copy. Repeatable |
| `--writers-stopped` | Yes | Confirms that writers on both ends are stopped and the source is backed up |

It prints a JSON object with `selected`, `copied` and `expired` counts. Use `*` only on a database the server owns alone.

### Check the docs

`scripts/docs/check.sh` runs the page generators, renders the diagrams and builds the site with `mkdocs build --strict`. CI runs the same script.

```bash
bash scripts/docs/check.sh
```

Each generated page has its own script in `scripts/docs/`: `gen_env.py`, `gen_ports.py`, `gen_routes.py` and `gen_metrics.py`. Edit `scripts/docs/descriptions.yml` for their text.

```bash
uv run -q --no-project --python 3.12 --with pyyaml python scripts/docs/gen_routes.py
```

### Use the other helpers

| Script | Purpose |
|---|---|
| `docker/wait_for_redis.sh` | Entry point of each image. Waits until `REDIS_URL` answers, then runs the given command. Skips the wait when `REDIS_URL` is unset |
| `common/tests/load_test_vcons.py [count]` | Posts generated test vCons to `http://localhost:8000/vcon`, one by default. Sends no API key, so it works only on an API with no keys set |
| `conserver/links/scitt/dump_cbor.py --input FILE` | Prints a COSE Sign1 statement from a CBOR file. The default file is `transparent-statement.cbor` |
| `conserver/links/scitt/create_hashed_signed_statement.py` | Creates a signed statement over a hashed payload. Run it with `--help` for its options. See the [`scitt` link](links/scitt.md) |

## Read the exit codes

| Process | Code | Meaning |
|---|---|---|
| Worker | `0` | Clean stop, including after `SIGTERM` or `SIGINT` |
| Worker | `1` | Unhandled startup error, such as a missing configuration file |
| `migrate_redis_json.py` | `2` | Missing or invalid arguments |
| `install_conserver.sh` | `0` | Also returned for a missing or unknown option, because the help function exits first |

The worker sets no exit codes of its own, so these come from Python and the signal handlers.
