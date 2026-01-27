# CLI Reference

Command-line options and usage for vCon Server components.

## Worker Process

The main worker process that executes processing chains.

### Basic Usage

```bash
python ./server/main.py
```

### With OpenTelemetry

```bash
opentelemetry-instrument python ./server/main.py
```

### Environment Configuration

The worker is configured entirely through environment variables:

```bash
# Required
export REDIS_URL=redis://localhost:6379
export CONSERVER_API_TOKEN=your-token
export CONSERVER_CONFIG_FILE=./config.yml

# Optional
export CONSERVER_WORKERS=4
export CONSERVER_PARALLEL_STORAGE=true
export CONSERVER_START_METHOD=fork
export LOG_LEVEL=INFO

# Run
python ./server/main.py
```

### Docker Usage

```bash
docker compose exec conserver python ./server/main.py
```

## API Server

The FastAPI server providing the REST API.

### Basic Usage

```bash
uvicorn server.api:app --host 0.0.0.0 --port 8000
```

### Development Mode

```bash
uvicorn server.api:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
gunicorn server.api:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers 4 \
  --bind 0.0.0.0:8000
```

### With OpenTelemetry

```bash
opentelemetry-instrument uvicorn server.api:app --host 0.0.0.0 --port 8000
```

### Uvicorn Options

| Option | Description |
|--------|-------------|
| `--host` | Bind address (default: 127.0.0.1) |
| `--port` | Bind port (default: 8000) |
| `--reload` | Auto-reload on code changes |
| `--workers` | Number of worker processes |
| `--log-level` | Log level (debug, info, warning, error) |
| `--access-log` | Enable/disable access log |

## Poetry Commands

### Install Dependencies

```bash
# Install all dependencies
poetry install

# Install with dev dependencies
poetry install --with dev

# Install only main dependencies
poetry install --only main
```

### Run Commands

```bash
# Run worker
poetry run python ./server/main.py

# Run API server
poetry run uvicorn server.api:app --reload

# Run tests
poetry run pytest

# Run linting
poetry run black server/
poetry run flake8 server/
```

### Manage Dependencies

```bash
# Add dependency
poetry add package-name

# Add dev dependency
poetry add --group dev package-name

# Update dependencies
poetry update

# Show outdated
poetry show --outdated
```

## Docker Commands

### Build

```bash
# Build image
docker compose build

# Build without cache
docker compose build --no-cache

# Build specific service
docker compose build conserver
```

### Run

```bash
# Start all services
docker compose up -d

# Start with logs
docker compose up

# Start specific service
docker compose up -d conserver

# Scale workers
docker compose up -d --scale conserver=4
```

### Logs

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
```

### Management

```bash
# Stop services
docker compose stop

# Restart services
docker compose restart

# Remove containers
docker compose down

# Remove with volumes
docker compose down -v

# Execute command
docker compose exec conserver bash
```

## Testing Commands

### Run All Tests

```bash
poetry run pytest
```

### Run with Options

```bash
# Verbose output
poetry run pytest -v

# Stop on first failure
poetry run pytest -x

# Max failures
poetry run pytest --maxfail=5

# Disable warnings
poetry run pytest --disable-warnings

# Run specific file
poetry run pytest server/tests/test_api.py

# Run specific test
poetry run pytest server/tests/test_api.py::test_health

# Run by marker
poetry run pytest -m integration

# With coverage
poetry run pytest --cov=server --cov-report=html
```

### Test Configuration

```ini
# pytest.ini
[pytest]
pythonpath = ., server
log_cli = 1
log_cli_level = INFO
markers =
    integration: mark a test as an integration test.
```

## Redis CLI

### Connect

```bash
# Local
redis-cli

# Docker
docker compose exec redis redis-cli

# Remote
redis-cli -h hostname -p 6379 -a password
```

### Common Commands

```bash
# Check connection
redis-cli ping

# List keys
redis-cli KEYS "*"

# Get queue length
redis-cli LLEN default

# Get queue items
redis-cli LRANGE default 0 -1

# Get vCon
redis-cli GET vcon:uuid-here

# Delete key
redis-cli DEL key-name

# Monitor commands
redis-cli MONITOR

# Server info
redis-cli INFO
```

## Utility Scripts

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

API_URL="${API_URL:-http://localhost:8000/api}"
TOKEN="${CONSERVER_API_TOKEN}"

# Check API
response=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/health")
if [ "$response" = "200" ]; then
    echo "API: OK"
else
    echo "API: FAILED ($response)"
    exit 1
fi

# Check Redis
if docker compose exec -T redis redis-cli ping | grep -q "PONG"; then
    echo "Redis: OK"
else
    echo "Redis: FAILED"
    exit 1
fi

echo "All checks passed"
```

### Queue Monitor Script

```bash
#!/bin/bash
# queue-monitor.sh

while true; do
    clear
    echo "=== Queue Status $(date) ==="
    echo
    for queue in default production test; do
        depth=$(docker compose exec -T redis redis-cli LLEN $queue 2>/dev/null || echo "N/A")
        dlq=$(docker compose exec -T redis redis-cli LLEN "DLQ:$queue" 2>/dev/null || echo "N/A")
        echo "$queue: $depth (DLQ: $dlq)"
    done
    sleep 5
done
```

### Backup Script

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="${1:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "Backing up to $BACKUP_DIR..."

# Redis
docker compose exec -T redis redis-cli BGSAVE
sleep 2
docker cp vcon-server-redis-1:/data/dump.rdb "$BACKUP_DIR/redis-$DATE.rdb"

# Config
cp .env "$BACKUP_DIR/env-$DATE"
cp config.yml "$BACKUP_DIR/config-$DATE.yml"

echo "Backup complete: $BACKUP_DIR"
```

## Environment Variables Reference

### Core Variables

```bash
# Redis connection
REDIS_URL=redis://localhost:6379

# API token
CONSERVER_API_TOKEN=your-token

# Config file
CONSERVER_CONFIG_FILE=./config.yml

# API path prefix
API_ROOT_PATH=/api

# Hostname
HOSTNAME=http://localhost:8000

# Environment
ENV=production
```

### Worker Variables

```bash
# Number of workers
CONSERVER_WORKERS=4

# Parallel storage
CONSERVER_PARALLEL_STORAGE=true

# Start method
CONSERVER_START_METHOD=fork

# Tick interval (ms)
TICK_INTERVAL=5000
```

### Logging Variables

```bash
# Log level
LOG_LEVEL=INFO

# Logging config file
LOGGING_CONFIG_FILE=server/logging.conf
```

### Cache Variables

```bash
# Redis cache expiry (seconds)
VCON_REDIS_EXPIRY=3600

# Index expiry (seconds)
VCON_INDEX_EXPIRY=86400

# Context expiry (seconds)
VCON_CONTEXT_EXPIRY=86400
```

### External Services

```bash
# Deepgram
DEEPGRAM_KEY=your-key

# OpenAI
OPENAI_API_KEY=your-key

# Groq
GROQ_API_KEY=your-key
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 130 | Interrupted (Ctrl+C) |
| 143 | Terminated (SIGTERM) |
