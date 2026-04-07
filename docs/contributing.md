# Contributing to vCon Server

This guide covers everything you need to set up a local development environment, run the test suite, understand the project layout, and submit changes.

---

## Prerequisites

| Tool | Minimum Version | Notes |
|---|---|---|
| Python | 3.12 | Required for local development outside Docker |
| Poetry | latest stable | Dependency and virtualenv management |
| Docker | latest stable | Required for running the full stack |
| Docker Compose | v2 (bundled with Docker Desktop) | Used for all service orchestration |

Verify you have these installed:

```bash
python --version      # 3.12+
poetry --version
docker --version
docker compose version
```

---

## Cloning and Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server

# 2. Copy and configure the environment file
cp .env.example .env
# Edit .env — at minimum set REDIS_URL and CONSERVER_API_TOKEN

# 3. Copy and customise the Docker Compose file
cp example_docker-compose.yml docker-compose.yml

# 4. Create the shared Docker network
docker network create conserver

# 5. Build the containers
docker compose build
```

To start all services:

```bash
docker compose up -d
```

---

## Running the Test Suite

Tests are run inside the Docker environment so that all service dependencies (Redis, etc.) are available.

```bash
# Run the full test suite
docker compose run --rm api poetry run pytest server/links/analyze/tests/ server/storage/milvus/test_milvus.py -v
```

To suppress OpenTelemetry export errors when Datadog is not configured, unset the OTLP endpoint:

```bash
docker compose run --rm -e OTEL_EXPORTER_OTLP_ENDPOINT= api poetry run pytest server/links/analyze/tests/ -v
```

Run a specific test file:

```bash
docker compose run --rm api poetry run pytest server/links/my_link/tests/test_my_link.py -v
```

---

## Project Structure

```
vcon-server/
├── server/                     # All application source code
│   ├── main.py                 # vCon processing pipeline — chain management,
│   │                           #   worker processes, Redis queue consumption
│   ├── api.py                  # FastAPI REST API — CRUD for vCons, chain
│   │                           #   ingress/egress, config and DLQ endpoints
│   ├── vcon.py                 # vCon data model — Vcon class with all
│   │                           #   builder methods and property accessors
│   ├── config.py               # Config loading — reads CONSERVER_CONFIG_FILE
│   │                           #   (YAML) and exposes worker/storage settings
│   ├── settings.py             # Environment variables — all os.getenv() calls
│   │                           #   with defaults live here
│   ├── redis_mgr.py            # Redis connection management — single shared
│   │                           #   connection pool used by API and pipeline
│   ├── follower.py             # Ingress follower — BLPOP loop that drives
│   │                           #   vCons from queue into a chain
│   ├── hook.py                 # Pre/post-link hook system
│   ├── dlq_utils.py            # Dead-letter queue helpers
│   ├── version.py              # Version string utilities
│   │
│   ├── links/                  # Processing link modules (one subdirectory each)
│   │   ├── analyze/            # LLM-based analysis (summary, labels, etc.)
│   │   ├── deepgram_link/      # Deepgram speech-to-text transcription
│   │   ├── tag/                # Applies configurable tags to vCons
│   │   ├── webhook/            # HTTP webhook delivery
│   │   └── ...                 # Additional built-in links
│   │
│   ├── storage/                # Storage adapter modules (one subdirectory each)
│   │   ├── base.py             # Abstract Storage base class
│   │   ├── file/               # Local filesystem storage
│   │   ├── mongo/              # MongoDB storage
│   │   ├── postgres/           # PostgreSQL storage
│   │   ├── s3/                 # AWS S3 (and S3-compatible) storage
│   │   ├── milvus/             # Milvus vector database storage
│   │   └── ...                 # Additional storage adapters
│   │
│   ├── tracers/                # Audit tracer modules
│   │   └── jlinc/              # JLINC zero-knowledge auditing tracer
│   │
│   └── lib/                    # Shared utilities
│       ├── logging_utils.py    # init_logger() — standard logger factory
│       ├── vcon_redis.py       # VconRedis — high-level Redis get/store for vCons
│       ├── context_utils.py    # OpenTelemetry trace context propagation
│       ├── metrics.py          # Counter and histogram helpers
│       ├── error_tracking.py   # Error tracker initialisation
│       └── ...
│
├── docs/                       # MkDocs documentation source
├── example_config.yml          # Annotated reference configuration
├── example_docker-compose.yml  # Starting point for docker-compose.yml
├── pyproject.toml              # Poetry project and dependency manifest
└── .env.example                # Template for the required environment file
```

---

## Environment Variables

All environment variables are declared in `server/settings.py`. Key variables:

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost` | Redis connection string |
| `CONSERVER_API_TOKEN` | _(none)_ | Bearer token for the REST API |
| `CONSERVER_CONFIG_FILE` | `./example_config.yml` | Path to the YAML config file |
| `CONSERVER_WORKERS` | `1` | Number of parallel worker processes |
| `CONSERVER_PARALLEL_STORAGE` | `true` | Write to storage backends concurrently |
| `CONSERVER_START_METHOD` | _(platform default)_ | Multiprocessing start method: `fork`, `spawn`, or `forkserver` |
| `LOG_LEVEL` | `DEBUG` | Python logging level |
| `ENV` | `dev` | Runtime environment label |
| `VCON_REDIS_EXPIRY` | `3600` | TTL (seconds) for vCons cached back in Redis |
| `VCON_INDEX_EXPIRY` | `86400` | TTL (seconds) for the vCon sorted-set index |
| `VCON_DLQ_EXPIRY` | `604800` | TTL (seconds) for dead-letter queue entries |
| `UUID8_DOMAIN_NAME` | `strolid.com` | DNS domain used when generating UUID v8 identifiers |
| `OPENAI_API_KEY` | _(none)_ | OpenAI key (used by analysis links) |
| `DEEPGRAM_KEY` | _(none)_ | Deepgram key (used by transcription links) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(none)_ | OTLP endpoint for OpenTelemetry traces/metrics |

---

## Coding Conventions

### Logger initialisation

Every module that needs logging calls `init_logger` from `lib/logging_utils.py` rather than using `logging.getLogger` directly:

```python
from lib.logging_utils import init_logger
logger = init_logger(__name__)
```

### The VconRedis pattern

Links and other components that need to read or write vCons use `VconRedis` from `lib/vcon_redis.py`. This provides a consistent interface and ensures the correct Redis key format (`vcon:<uuid>`):

```python
from lib.vcon_redis import VconRedis

vcon_redis = VconRedis()
vcon = vcon_redis.get_vcon(vcon_uuid)   # returns a Vcon instance or None
# ... modify vcon ...
vcon_redis.store_vcon(vcon)             # serialises and saves back to Redis
```

### default_options dict

Every link module exposes a module-level `default_options` dictionary that declares all supported configuration keys and their defaults. The `run` function merges caller-supplied options on top of the defaults:

```python
default_options = {
    "threshold": 0.5,
    "model": "gpt-4",
}

def run(vcon_uuid, link_name, opts=default_options):
    options = {**default_options, **opts}
    ...
```

This convention makes options self-documenting and ensures backward compatibility when new options are added.

### Error handling

- Raise an exception (letting the pipeline move the vCon to the DLQ) for permanent or unknown failures.
- Return `None` to silently filter a vCon out of the chain without moving it to the DLQ.
- Return `vcon_uuid` to continue processing normally.

---

## Creating a New Processing Link

See [docs/extending/creating-links.md](extending/creating-links.md) for the complete guide, including the required `run()` signature, directory layout, configuration registration, testing patterns, and best practices.

Quick reference — minimum viable link:

```
server/links/my_link/
    __init__.py     # must contain run() and default_options
    tests/
        __init__.py
        test_my_link.py
```

---

## Creating a New Storage Adapter

See [docs/extending/creating-storage-adapters.md](extending/creating-storage-adapters.md) for the full guide, including how to subclass `storage.base.Storage`, the required method signatures, and how to register the adapter in `config.yml`.

---

## Branch and PR Workflow

1. **Branch from `main`**:

   ```bash
   git checkout main
   git pull origin main
   git checkout -b your-feature-branch
   ```

2. **Make your changes**, following the coding conventions above. Add or update tests.

3. **Run the tests** inside Docker to confirm nothing is broken:

   ```bash
   docker compose run --rm api poetry run pytest server/links/analyze/tests/ -v
   ```

4. **Open a Pull Request against `main`** on GitHub at [https://github.com/vcon-dev/vcon-server](https://github.com/vcon-dev/vcon-server). Provide a clear description of what the PR does and why, and link any related issues.

5. Maintainers will review the PR. Address any requested changes by pushing additional commits to the same branch — do not force-push.
