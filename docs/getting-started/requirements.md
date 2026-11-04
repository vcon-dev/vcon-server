# System requirements

This page lists what you need before you start the server, so the [quick start](quick-start.md) runs first time.

## Install the required software

| Software | Version | Purpose |
|---|---|---|
| Docker Engine | Current release | Runs the services |
| Docker Compose | v2 plugin (`docker compose`) | Starts the stack from `docker-compose.yml` |
| Git | Any | Clones the repository |

Compose starts Redis for you, pinned to `redis:7.4-alpine`. Plain Redis is enough. If you run your own, you do not need RedisJSON or Redis Stack, and data from an older Redis Stack deployment needs the [Redis migration](../installation/redis-migration.md).

CI runs the test suite on Ubuntu 24.04 under Docker. Published images cover `linux/amd64` and `linux/arm64`.

## Add tools for local development

You need these only to run the code outside Docker.

| Software | Version | Purpose |
|---|---|---|
| Python | 3.12 or 3.13 (`>=3.12,<3.14`) | Runtime. The images use 3.12 |
| [uv](https://docs.astral.sh/uv/) | The images pin 0.10.9 | Dependency management, from `uv.lock` |
| Redis | Plain Redis. Compose uses 7.4 | Queues and vCon cache |
| ffmpeg, sox | Any | Audio handling in some links. The images install them |

See [Contributing](../contributing.md) for the setup.

## Choose optional backends

The default stack needs none of these. Each adapter page lists its options and credentials.

| Backend | Compose profile | Reference |
|---|---|---|
| PostgreSQL | `postgres` (`postgres:alpine`) | [PostgreSQL adapter](../reference/storage-adapters/postgres.md) |
| Elasticsearch | `elasticsearch` (8.13.4) | [Elasticsearch adapter](../reference/storage-adapters/elasticsearch.md) |
| MongoDB | None, bring your own | [MongoDB adapter](../reference/storage-adapters/mongo.md) |
| S3 | None, bring your own | [S3 adapter](../reference/storage-adapters/s3.md) |
| Anything else | None | [Storage adapters](../reference/storage-adapters/index.md) |

The `langfuse` profile adds a local Langfuse stack for trace inspection. See [monitoring](../operations/monitoring.md).

## Gather vendor credentials

Transcription and AI analysis links call outside services, so they need an API key and outbound HTTPS. A chain with only local links needs neither. Each [link page](../reference/links/index.md) names its option or environment variable, and [transcribe](../reference/links/transcribe.md) covers the speech to text vendors.

## Plan capacity

Size for your chains, since the work happens there. An I/O-bound chain, such as one waiting on an LLM or a transcription service, needs little CPU. Two settings control how many vCons run at once:

```text
maximum parallel vCons = CONSERVER_WORKERS x CONSERVER_VCON_CONCURRENCY
```

Each worker is a separate OS process. See [workers](../configuration/workers.md).

Compose caps the Redis container at 1 GB with `mem_limit`. Raise it if your queues and cached vCons need more.

<!-- TODO(verify): the repo holds no measured CPU, memory or disk figures. The old sizing tables were removed because nothing in the code supports them. Add measured figures here if a load test produces them. -->

## Open the network ports

The API listens on port 8000. Redis stays on the private `conserver` Docker network unless you publish it. See [ports](../reference/ports.md) for every service.

## Run on macOS or Windows

The containers run Linux, so nothing changes under Docker. Outside Docker, Python defaults to the `spawn` start method on macOS and Windows, against `fork` on Linux. Set `CONSERVER_START_METHOD` to override it. See [workers](../configuration/workers.md).

## Check your tools

```bash
docker --version
docker compose version
docker info
git --version
```

For local development:

```bash
uv --version
uv python list
```

## Pick your next page

- [Quick start](quick-start.md) runs the stack with Docker Compose.
- [Docker installation](../installation/docker.md) covers more Docker options.
- [Manual installation](../installation/manual-installation.md) runs the services without Docker.
