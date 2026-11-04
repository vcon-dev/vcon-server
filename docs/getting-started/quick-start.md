# Quick start

This page takes you from a fresh clone to a processed vCon with Docker Compose. It needs no vendor keys, and the first build takes a few minutes.

You need Docker with the Compose plugin and Git. See [system requirements](requirements.md).

## Clone the repository

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
```

The repository ships a ready `docker-compose.yml`, so there is no Compose file to copy.

## Set the environment

```bash
cp .env.example .env
openssl rand -hex 32
```

Edit `.env` and set these four values. Use the `openssl` output as your token.

```bash
CONSERVER_API_TOKEN=your-generated-token
CONSERVER_CONFIG_FILE=./config.yml
LOGGING_CONFIG_FILE=common/logging_dev.conf
COMPOSE_PROFILES=
```

Each one matters:

| Variable | Without this change |
|---|---|
| `CONSERVER_API_TOKEN` | A blank token turns API authentication off |
| `CONSERVER_CONFIG_FILE` | `.env.example` leaves it blank. A blank value overrides the built-in default, and the services cannot open a config file |
| `LOGGING_CONFIG_FILE` | `.env.example` names a path that does not exist, and both services stop at startup |
| `COMPOSE_PROFILES` | `.env.example` sets `postgres`, which starts PostgreSQL on host port 5432. This walkthrough does not use it |

`common/logging_dev.conf` writes plain text, which the samples on this page show. `common/logging.conf` writes JSON for production.

## Write the configuration

Create `config.yml` in the repository root:

```yaml
links:
  tag:
    module: links.tag
    options:
      tags:
        - quick_start

storages:
  file:
    module: storage.file
    options:
      path: /data/vcons

chains:
  quick_start:
    links:
      - tag
    storages:
      - file
    ingress_lists:
      - default
    egress_lists:
      - quick_start_output
    enabled: 1
```

This chain reads the `default` list, tags each vCon, writes it to a file inside the `conserver` container and pushes its uuid to `quick_start_output`.

Create this file before you start the stack. Compose mounts `./config.yml` into the `conserver` container, and Docker creates a directory of that name if no file exists.

Do not start from `example_config.yml`. It is a syntax sample, and it names placeholder packages, modules and backends that a fresh stack does not have. The worker tries to install those packages and stops.

## Start the stack

```bash
docker network create conserver
docker compose up -d --build
```

`docker-compose.yml` declares the `conserver` network as external, so it must exist first. If it already exists, the first command reports that and you can carry on.

Check the services:

```bash
docker compose ps
```

You should see `api`, `conserver` and `redis` running. The `conserver` container can show `Up` after its process has failed, because a file watcher wraps it in the Compose setup. Read its logs to be sure:

```bash
docker compose logs conserver | tail
```

A healthy worker logs `Worker-1 started`.

Check the API:

```bash
curl http://localhost:8000/api/health
```

```json
{"status":"healthy","version":{"version":"dev","git_commit":"unknown","build_time":"unknown"}}
```

A local build reports `dev`, because Compose passes no version at build time. This endpoint does not touch Redis, so it shows only that the API answers.

## Submit a vCon

Set the token and a uuid. The API rejects a `uuid` that is not a real UUID.

```bash
export TOKEN=your-generated-token
export VCON_UUID=$(uuidgen | tr 'A-Z' 'a-z')
export NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

Post a vCon to the `default` list:

```bash
curl -X POST "http://localhost:8000/api/vcon?ingress_lists=default" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{
    "vcon": "0.4.0",
    "uuid": "'"$VCON_UUID"'",
    "created_at": "'"$NOW"'",
    "parties": [
      {"tel": "+15551234567", "name": "Caller"},
      {"tel": "+15559876543", "name": "Agent"}
    ],
    "dialog": [
      {
        "type": "text",
        "start": "'"$NOW"'",
        "parties": [0, 1],
        "originator": 0,
        "mediatype": "text/plain",
        "encoding": "none",
        "body": "Hello, I have a question about my order."
      }
    ]
  }'
```

The API returns `201` and the stored vCon. The `ingress_lists` parameter is what starts processing. Without it the API stores the vCon and no chain runs.

This test vCon has no `lawful_basis` attachment, and the server does not add one. See [lawful basis](../concepts/lawful-basis.md).

## Read the result

Fetch the vCon:

```bash
curl "http://localhost:8000/api/vcon/$VCON_UUID" \
  -H "x-conserver-api-token: $TOKEN"
```

The `attachments` array now holds an entry the chain added:

```json
{"purpose": "tags", "body": "[\"quick_start:quick_start\"]", "encoding": "json"}
```

The `body` is a JSON string, not an array. Decode it with `fromjson` in `jq`:

```bash
curl -s "http://localhost:8000/api/vcon/$VCON_UUID" \
  -H "x-conserver-api-token: $TOKEN" \
  | jq '.attachments[] | select(.purpose == "tags") | .body | fromjson'
```

Check the two other results of the chain:

```bash
curl "http://localhost:8000/api/stats/queue?list_name=quick_start_output"
docker compose exec conserver find /data/vcons -type f
```

The first shows `"depth":1`. The second lists the stored file, under a date folder. That folder is inside the container, so recreating the container removes it. A real deployment uses a [storage adapter](../reference/storage-adapters/index.md) with durable storage.

The API answers for one hour from Redis. After that, this setup returns `404`, because the file backend is visible only to the `conserver` container. See [read a stored vCon](../concepts/vcon-lifecycle.md#read-a-stored-vcon).

The logs show the same run:

```bash
docker compose logs conserver | grep "Completed processing"
```

## Change the chain

An idle worker rereads `config.yml` within 15 seconds, so chain changes need no restart. Compose mounts the file on its own, and on a Linux host an editor that saves by replacing the file leaves the container on the old copy. If an edit has no effect, run `docker compose up -d --force-recreate conserver`.

To go further:

- Add speech to text with [transcribe a recording](../configuration/chains-and-pipelines.md#transcribe-a-recording). The text dialog on this page has no audio, so `transcribe` skips it. Follow with an [analyze](../reference/links/analyze.md) step.
- Build your own chain from [chains and pipelines](../configuration/chains-and-pipelines.md).
- Browse the [API reference](../reference/api.md).

## Stop the stack

```bash
docker compose down
```

Add `-v` to delete the Redis volume as well.

## Fix common problems

| Symptom | Cause | Fix |
|---|---|---|
| `api` exits with code 1, logs show `server/logging_dev.conf doesn't exist` | `.env` still holds the value from `.env.example` | Set `LOGGING_CONFIG_FILE=common/logging_dev.conf` |
| `FileNotFoundError` naming an empty path, or `500` from `/config` | `CONSERVER_CONFIG_FILE` is blank | Set `CONSERVER_CONFIG_FILE=./config.yml` |
| `IsADirectoryError` naming `./config.yml` | The stack started before the file existed | Stop the stack, delete the `config.yml` directory, then create the file |
| `CalledProcessError` from `pip install` | `config.yml` names a package that cannot be installed, as `example_config.yml` does | Use the configuration on this page |
| `network conserver declared as external, but could not be found` | The network does not exist | `docker network create conserver` |
| Host port 8000 in use | Another process holds it | Set `CONSERVER_EXTERNAL_PORT` in `.env` |
| `403` with `Invalid API Key` | Wrong or missing header | Send `x-conserver-api-token` with the value in `.env`. After you change `.env`, run `docker compose up -d api` |
| `422` on `POST /vcon` | The body failed validation, often a `uuid` that is not a UUID | Read the `detail` field in the response |
| vCon stays unprocessed | No `ingress_lists` parameter, or the list is not in a chain | Post with `?ingress_lists=default` and check `ingress_lists` in `config.yml` |

For anything else, see [troubleshooting](../operations/troubleshooting.md). Failed vCons go to the [dead letter queue](../operations/dead-letter-queue.md).

## Take the next step

- [Docker installation](../installation/docker.md) covers more Docker options.
- [Configuration](../configuration/index.md) covers the environment and YAML settings.
- [Authentication](../configuration/authentication.md) covers API keys and scoped ingress keys.
