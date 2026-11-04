# Read and configure logs

This page covers the logging configuration, how to search the logs and how to turn on debug output.

## Choose the log format

Python's `logging.config.fileConfig` loads one file at import, named by `LOGGING_CONFIG_FILE`. Two files ship in the repo:

| File | Format | Use |
|------|--------|-----|
| `common/logging.conf` | JSON | The default |
| `common/logging_dev.conf` | Plain text | Development |

```bash
# Plain text in a container
LOGGING_CONFIG_FILE=/app/common/logging_dev.conf
```

Apply a change with `docker compose up -d conserver api`, since `docker compose restart` keeps the old environment.

!!! warning "The example path does not exist"
    `.env.example` sets `LOGGING_CONFIG_FILE=server/logging_dev.conf`, and the repo has no `server/` folder. A process with that value fails at import. Use the path above, or remove the line to use the default.

Both files write everything to stdout. A `custom_error` handler for stderr is defined, but no logger uses it.

## Set the log level

Levels live in the config file. `LOG_LEVEL` is read into `settings`, but no code uses it, so setting it changes nothing.

Both shipped files stop at `INFO`, including `logging_dev.conf`, because the root logger and the `custom_info` handler are both at `INFO`. Its `DEBUG` loggers have no handler that passes `DEBUG`. To see debug output, see [Turn on debug output](#turn-on-debug-output).

## Read the JSON output

The JSON formatter is `pythonjsonlogger`. Fields passed through `extra` become top-level keys.

```json
{"asctime": "2026-11-03 17:46:27,793", "levelname": "INFO", "name": "storage.base", "message": "Finished storage postgres module storage.postgres save for vCon: 018f0000-0000-8000-8000-000000000001 in 0.12 seconds.", "taskName": null, "storage_processing_time": 0.12}
```

The plain text format is `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.

```
2026-11-03 17:46:27 - main - INFO - Worker-1 started (PID 12)
```

## Identify the loggers

| Logger | Source |
|--------|--------|
| `main` | `conserver/main.py` |
| `api` | `api/api.py` |
| `vcon` | `common/vcon.py` |
| `uvicorn` | The web server |
| `root` | Everything else. Modules log under their own names, such as `links.tag`, `storage.base` and `lib.vcon_redis`, and pass up to `root` |

Use the helper in your own code:

```python
from lib.logging_utils import init_logger

logger = init_logger(__name__)
```

## View the logs

### Use Docker Compose

```bash
docker compose logs -f
docker compose logs --tail=100 conserver
docker compose logs --since="1h" conserver
docker compose logs --since="2026-01-15T10:00:00" --until="2026-01-15T11:00:00"
```

### Use Kubernetes

```bash
kubectl logs -f deployment/worker -n vcon-server
kubectl logs -f -l app=worker -n vcon-server

# The previous container, after a crash
kubectl logs --previous deployment/worker -n vcon-server
```

## Search the logs

These lines mark the events you will look for most.

| Search for | Meaning |
|---|---|
| `Completed processing vCon` | A chain finished |
| `halted chain processing` | A link returned a falsy value, so egress and storage were skipped |
| `Moving to DLQ` | A chain failed and the vCon went to the ingress DLQ |
| `Moving to storage DLQ` | A write to one backend failed |
| `manual recovery required` | A failed write could not reach the storage DLQ |
| `Deprecated link module` | A chain uses a legacy transcribe module |

```bash
# Find one vCon
docker compose logs conserver | grep "<uuid>"

# Count the log levels
docker compose logs conserver | grep -oE '"levelname": "[A-Z]+"' | sort | uniq -c

# Parse JSON and skip any line that is not JSON
docker compose logs conserver --no-log-prefix | jq -R 'fromjson? | select(.levelname == "ERROR")'
```

Some output, such as library messages, is not JSON. The `fromjson?` filter skips those lines.

## Turn on debug output

Make your own copy of a config file and lower two levels. `docker-compose.yml` mounts the repo at `/app`, so a file in the repo root is visible in the containers.

```bash
cp common/logging_dev.conf logging_debug.conf
```

In `logging_debug.conf`, set `level = DEBUG` under `[logger_root]` and under `[handler_custom_info]`. The `main` and `api` loggers are already at `DEBUG`.

```bash
# In .env
LOGGING_CONFIG_FILE=/app/logging_debug.conf
```

```bash
docker compose up -d conserver api
```

To debug one area, keep `[handler_custom_info]` at `DEBUG`, put `[logger_root]` back to `INFO` and add a logger. Add its name to `keys` under `[loggers]` first.

```ini
[loggers]
keys = root, vcon, uvicorn, main, api, links

[logger_links]
level = DEBUG
handlers = custom_info
propagate = 0
qualname = links
```

Debug output is heavy. The worker logs each link of each vCon at `DEBUG`, so turn it off when you finish.

## Limit the log size

`docker-compose.yml` sets no log limits, so the default driver can fill a disk. Add a limit for each service:

```yaml
services:
  conserver:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

The server writes no log files of its own, so there is nothing to rotate inside the containers.

## Forward logs to an aggregator

The server logs to stdout, so forwarding is a Docker or platform setting. In Kubernetes, use your cluster's log agent.

### Use Fluentd

```yaml
services:
  fluentd:
    image: fluent/fluentd:v1.16
    volumes:
      - ./fluentd.conf:/fluentd/etc/fluent.conf
    ports:
      - "24224:24224"

  conserver:
    logging:
      driver: "fluentd"
      options:
        fluentd-address: localhost:24224
        tag: vcon.conserver
```

### Use Loki

```yaml
services:
  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - ./promtail.yml:/etc/promtail/promtail.yml
```

### Use CloudWatch

```yaml
services:
  conserver:
    logging:
      driver: "awslogs"
      options:
        awslogs-region: us-east-1
        awslogs-group: vcon-server
        awslogs-stream: "{{.Name}}"
```

### Use Elasticsearch and Kibana

Run Filebeat against `/var/lib/docker/containers`, read-only, and send to your Elasticsearch cluster. The JSON format needs no parsing rules.

## Write good log lines

Pass context through `extra`, so it reaches the JSON output as fields:

```python
logger.info("Saved vCon", extra={"chain": chain_name, "link": link_name})
```

| Level | Use for |
|-------|---------|
| DEBUG | Detailed diagnostic information |
| INFO | General operational events |
| WARNING | Unexpected but handled situations |
| ERROR | Failures that need attention. With Sentry on, these become events |
| CRITICAL | System-wide failures |

Never log secrets or conversation content. Log the vCon UUID instead.

```python
# Bad
logger.info(f"Processing vCon with API key {api_key}")

# Good
logger.info("Processing vCon %s", vcon_uuid)
```

## Fix the common logging problems

**A process exits at import with a logging error.** Check the path in `LOGGING_CONFIG_FILE`:

```bash
docker compose exec conserver env | grep LOGGING_CONFIG_FILE
docker compose exec conserver ls /app/common/logging.conf
```

If the container exits too fast for `exec`, read `docker compose logs conserver` and check `.env`.

**Too many logs.** Raise a level in your config file. `LOG_LEVEL` does nothing.

**No debug lines appear.** Lower both the logger and the handler. See [Turn on debug output](#turn-on-debug-output).

**jq fails on some lines.** Use `jq -R 'fromjson?'` as shown in [Search the logs](#search-the-logs).
