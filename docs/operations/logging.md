# Logging

This guide covers logging configuration, log analysis, and debugging with logs.

## Logging Configuration

### Configuration Files

vCon Server includes two logging configurations:

| File | Format | Use Case |
|------|--------|----------|
| `server/logging.conf` | JSON | Production |
| `server/logging_dev.conf` | Simple text | Development |

### Selecting Configuration

```bash
# Production (default)
LOGGING_CONFIG_FILE=server/logging.conf

# Development
LOGGING_CONFIG_FILE=server/logging_dev.conf
```

### Log Level

```bash
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO
```

## Production Logging (JSON)

Production logging outputs structured JSON for easy parsing.

### Configuration

```ini
# server/logging.conf
[loggers]
keys=root,vcon,uvicorn,main,api

[handlers]
keys=custom_info,custom_error

[formatters]
keys=json

[logger_root]
level=INFO
handlers=custom_info,custom_error

[logger_vcon]
level=INFO
handlers=custom_info,custom_error
qualname=vcon
propagate=0

[handler_custom_info]
class=StreamHandler
level=INFO
formatter=json
args=(sys.stdout,)

[handler_custom_error]
class=StreamHandler
level=WARNING
formatter=json
args=(sys.stderr,)

[formatter_json]
format={"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}
```

### Sample Output

```json
{"timestamp": "2024-01-15 10:30:00,123", "level": "INFO", "logger": "vcon", "message": "Processing vCon abc-123"}
{"timestamp": "2024-01-15 10:30:01,456", "level": "INFO", "logger": "vcon", "message": "Completed processing abc-123"}
```

## Development Logging (Text)

Development logging uses human-readable format.

### Configuration

```ini
# server/logging_dev.conf
[loggers]
keys=root,vcon,uvicorn,main,api

[handlers]
keys=console

[formatters]
keys=simple

[logger_root]
level=DEBUG
handlers=console

[logger_vcon]
level=DEBUG
handlers=console
qualname=vcon
propagate=0

[handler_console]
class=StreamHandler
level=DEBUG
formatter=simple
args=(sys.stdout,)

[formatter_simple]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### Sample Output

```
2024-01-15 10:30:00,123 - vcon - DEBUG - Processing vCon abc-123
2024-01-15 10:30:00,456 - vcon - DEBUG - Running link: transcribe
2024-01-15 10:30:01,789 - vcon - INFO - Completed processing abc-123
```

## Logger Hierarchy

| Logger | Purpose |
|--------|---------|
| `root` | Catch-all for unhandled loggers |
| `vcon` | Core vCon processing |
| `api` | API endpoint handling |
| `main` | Main worker process |
| `uvicorn` | Web server |

### Using Loggers in Code

```python
from lib.logging_utils import init_logger

logger = init_logger(__name__)

def process():
    logger.debug("Starting process")
    logger.info("Process completed")
    logger.warning("Something unusual")
    logger.error("Something failed", exc_info=True)
```

## Viewing Logs

### Docker Compose

```bash
# All logs
docker compose logs

# Follow logs
docker compose logs -f

# Specific service
docker compose logs conserver

# Last N lines
docker compose logs --tail=100 conserver

# Since time
docker compose logs --since="1h" conserver

# Filter by time range
docker compose logs --since="2024-01-15T10:00:00" --until="2024-01-15T11:00:00"
```

### Kubernetes

```bash
# Pod logs
kubectl logs -f deployment/worker -n vcon-server

# All pods with label
kubectl logs -f -l app=worker -n vcon-server

# Previous container (after crash)
kubectl logs --previous deployment/worker -n vcon-server
```

### Container Logs

```bash
# Docker logs
docker logs -f vcon-server-conserver-1

# With timestamps
docker logs -t vcon-server-conserver-1
```

## Log Analysis

### Common Patterns

**Find errors:**

```bash
docker compose logs conserver | grep -i error
```

**Find specific vCon:**

```bash
docker compose logs conserver | grep "abc-123"
```

**Count log levels:**

```bash
docker compose logs conserver | grep -oE '"level": "[A-Z]+"' | sort | uniq -c
```

**Parse JSON logs with jq:**

```bash
docker compose logs conserver --no-log-prefix | jq -r 'select(.level == "ERROR")'
```

### Log Aggregation

#### Fluentd

```yaml
# docker-compose.yml
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

#### Loki

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

### Elasticsearch/Kibana

```yaml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node

  kibana:
    image: docker.elastic.co/kibana/kibana:8.11.0
    ports:
      - "5601:5601"

  filebeat:
    image: docker.elastic.co/beats/filebeat:8.11.0
    volumes:
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
```

## Debugging with Logs

### Enable Debug Logging

```bash
# Environment variable
LOG_LEVEL=DEBUG
LOGGING_CONFIG_FILE=server/logging_dev.conf

# Restart services
docker compose restart conserver
```

### Debug Specific Components

In `logging_dev.conf`:

```ini
[logger_links]
level=DEBUG
handlers=console
qualname=links
propagate=0

[logger_storage]
level=DEBUG
handlers=console
qualname=storage
propagate=0
```

### Trace Processing

```bash
# Watch for specific vCon
docker compose logs -f conserver | grep "uuid-to-trace"

# Watch processing steps
docker compose logs -f conserver | grep -E "(Starting|Completed|Error)"
```

## Log Rotation

### Docker Log Rotation

```yaml
# docker-compose.yml
services:
  conserver:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

### Logrotate (Manual Installation)

```
# /etc/logrotate.d/vcon-server
/var/log/vcon-server/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 vcon vcon
    postrotate
        systemctl reload vcon-server
    endscript
}
```

## Structured Logging Best Practices

### Include Context

```python
logger.info("Processing vCon", extra={
    "vcon_uuid": uuid,
    "chain": chain_name,
    "link": link_name
})
```

### Use Appropriate Levels

| Level | Use For |
|-------|---------|
| DEBUG | Detailed diagnostic info |
| INFO | General operational events |
| WARNING | Unexpected but handled situations |
| ERROR | Failures requiring attention |
| CRITICAL | System-wide failures |

### Avoid Sensitive Data

```python
# Bad
logger.info(f"Processing vCon with API key {api_key}")

# Good
logger.info(f"Processing vCon {uuid}")
```

## Troubleshooting

### No Logs Appearing

Check logging configuration:

```bash
# Verify environment
docker compose exec conserver env | grep LOG

# Check file exists
docker compose exec conserver cat /app/server/logging.conf
```

### Too Many Logs

Increase log level:

```bash
LOG_LEVEL=WARNING
```

### JSON Parse Errors

Some logs may not be JSON (e.g., library output):

```bash
# Filter valid JSON only
docker compose logs conserver --no-log-prefix 2>/dev/null | while read line; do
  echo "$line" | jq . 2>/dev/null || true
done
```

### Logs Missing Timestamps

Ensure formatter includes timestamps:

```ini
[formatter_json]
format={"timestamp": "%(asctime)s", ...}
```
