# Install with Docker

This page starts the API, the conserver and Redis on one host with Docker Compose.

The Compose file suits development and small deployments. It builds `docker/Dockerfile`, bind-mounts the repo into each container and restarts the conserver when a Python file changes. For production, see [Run the published images](#run-the-published-images).

## Prepare the host

You need Git and Docker with the Compose plugin. See the [system requirements](../getting-started/requirements.md) for sizing.

If you already run Redis Stack, finish the [Redis migration](redis-migration.md) first. RedisJSON persistence files cannot be reused with the plain Redis image.

## Clone the repository

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
```

## Create the network

The Compose file declares the `conserver` network as external, so create it once:

```bash
docker network create conserver
```

## Set the environment

```bash
cp .env.example .env
```

Change these lines in `.env` before you start anything:

```bash
# The sample value points at a path that no longer exists and stops both services.
LOGGING_CONFIG_FILE=common/logging.conf

# The sample value is empty, which the services cannot open.
CONSERVER_CONFIG_FILE=./config.yml

# Blank means no API key check on the main routes.
CONSERVER_API_TOKEN=your-secure-token-here

# Optional services to start. Blank starts only api, conserver and redis.
COMPOSE_PROFILES=
```

`common/logging.conf` writes JSON for production. `common/logging_dev.conf` writes plain text, as the [quick start](../getting-started/quick-start.md) does, so log lines here look different from its samples.

Generate a token with `openssl rand -hex 32`. Every variable is listed in the [environment reference](../reference/environment.md), and the [environment guide](../configuration/environment-variables.md) helps you choose values.

## Write the chain configuration

The Compose file mounts `./config.yml` into the conserver, so the file must exist before the first start. Start with a small one:

```yaml
links:
  tag_processed:
    module: links.tag
    options:
      tags:
        - processed

storages:
  redis_storage:
    module: storage.redis_storage

chains:
  main_chain:
    links:
      - tag_processed
    storages:
      - redis_storage
    ingress_lists:
      - default
```

`example_config.yml` is a catalogue of syntax, not a working configuration. Its `imports` section names packages that do not exist, so a worker that loads it fails at startup. Copy from it, but do not run it as it stands.

See [YAML configuration](../configuration/yaml-configuration.md) to build your own.

## Start the services

```bash
docker compose up -d --build
```

## Check the installation

```bash
docker compose ps
curl http://localhost:8000/api/health
curl http://localhost:8000/api/version
docker compose logs -f conserver
```

The API listens on host port 8000, or on `CONSERVER_EXTERNAL_PORT` if you set it. To send a first vCon, follow the [quick start](../getting-started/quick-start.md).

Redis listens on port 6379 inside the Docker network and publishes no host port. The old `REDIS_EXTERNAL_PORT` setting no longer applies, and the file no longer includes Redis Insight. To reach Redis, run `docker compose exec redis redis-cli`.

## Add storage backends

PostgreSQL and Elasticsearch are Compose profiles. Add a profile to `.env`, then run `docker compose up -d`:

```bash
COMPOSE_PROFILES=postgres,elasticsearch
```

The credentials in the Compose file are for development only. Point the adapter at the service in `config.yml`. The [PostgreSQL](../reference/storage-adapters/postgres.md) and [Elasticsearch](../reference/storage-adapters/elasticsearch.md) reference pages list the options.

The Compose file has no MongoDB service. Add one, or point [`storage.mongo`](../reference/storage-adapters/mongo.md) at a server you run. For a local service, put this in a `docker-compose.override.yml` file:

```yaml
services:
  mongo:
    image: mongo:6
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: example
    volumes:
      - mongo_data:/data/db
    networks:
      - conserver

volumes:
  mongo_data:
```

The `langfuse` profile adds local LLM tracing. See [Ports and services](../reference/ports.md).

## Scale the workers

Run more conserver containers:

```bash
docker compose up -d --scale conserver=4
```

Or run more worker processes in one container with `CONSERVER_WORKERS` in `.env`. [Workers](../configuration/workers.md) compares the two.

Set resource limits in `docker-compose.override.yml`:

```yaml
services:
  conserver:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## Run the published images

CI publishes two multi-arch images, each smaller than the Compose image:

| Image | Built from | Holds |
|---|---|---|
| `public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server-api` | `docker/Dockerfile.api` | `api/`, `common/` and the `api` dependency group |
| `public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server-conserver` | `docker/Dockerfile.conserver` | `conserver/`, `common/` and the `conserver` dependency group |

A push to `main` publishes `latest` and `main-<sha>`. A `v1.2.3` tag publishes `1.2.3`, `1.2` and `1`. Each image starts its own process, so it needs no `command` override. Each waits for `REDIS_URL` to answer before it starts.

Neither image holds `storage-milvus`, and the [storage adapter reference](../reference/storage-adapters/index.md#install-the-adapter-packages) shows which adapters each image can load.

## Prepare for production

- Set API keys and use a [token file](../configuration/authentication.md#set-the-global-api-keys) for more than one key.
- Terminate TLS at a reverse proxy, and send it to `api:8000`. The `nginx.conf` in the repo is a sample with fixed certificate paths, so write your own.
- Keep Redis and databases off public networks. The `postgres` and `elasticsearch` profiles publish their ports on the host.
- The images define no `USER`, so containers run as root. Set a user in your runtime if your policy needs one.
- Rotate container logs:

```yaml
services:
  conserver:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

The images do not include `curl`, so write a health check in Python:

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

## Manage the services

```bash
docker compose up -d              # Start, or apply changes to .env
docker compose down               # Stop and remove the containers
docker compose restart conserver  # Restart one service
docker compose logs -f conserver  # Follow logs
docker compose exec conserver bash
docker stats
```

`docker compose restart` does not reread `.env`. Use `docker compose up -d` after you change it.

To update the code, see [Upgrading](upgrading.md).

## Troubleshoot a failed start

Start with the logs:

```bash
docker compose logs conserver --tail=100
```

| Symptom | Cause | Fix |
|---|---|---|
| `FileNotFoundError: server/logging_dev.conf` | `LOGGING_CONFIG_FILE` still holds the sample value | [Set the environment](#set-the-environment) |
| `FileNotFoundError` on an empty path | `CONSERVER_CONFIG_FILE` is empty | [Set the environment](#set-the-environment) |
| `IsADirectoryError` on `config.yml` | Docker created a folder because the file was missing | Remove the folder and [write the file](#write-the-chain-configuration) |
| Worker exits with `No matching distribution found` | The `imports` section of `example_config.yml` | [Write your own file](#write-the-chain-configuration) |
| `network conserver declared as external, but could not be found` | The network is missing | [Create the network](#create-the-network) |
| `Redis not ready yet. Retrying...` repeats | Wrong `REDIS_URL`, or Redis is down | Use `redis://redis` and check `docker compose exec redis redis-cli ping` |
| Port 8000 already in use | Another process holds it | Set `CONSERVER_EXTERNAL_PORT` in `.env` |
| Containers are killed for memory | Too many workers | Lower `CONSERVER_WORKERS` or raise Docker's memory limit |

To test Redis from the conserver container:

```bash
docker compose exec conserver redis-cli -h redis ping
```

See [Troubleshooting](../operations/troubleshooting.md) for faults after startup.

## Continue with these guides

- [Configuration guide](../configuration/index.md)
- [Workers](../configuration/workers.md)
- [Monitoring](../operations/monitoring.md)
