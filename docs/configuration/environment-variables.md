# Environment Variables

Complete reference for all environment variables used by vCon Server.

## Core Settings

### REDIS_URL

Redis connection URL for queues and caching.

| Property | Value |
|----------|-------|
| **Required** | Yes |
| **Default** | `redis://localhost` |
| **Format** | `redis://[user:password@]host[:port][/database]` |

```bash
# Local Redis
REDIS_URL=redis://localhost:6379

# Docker Redis
REDIS_URL=redis://redis:6379

# Redis with authentication
REDIS_URL=redis://user:password@redis-host:6379/0

# Redis Cluster
REDIS_URL=redis://redis-cluster:6379
```

### HOSTNAME

Server hostname used for generating URLs.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `http://localhost:8000` |

```bash
HOSTNAME=https://api.example.com
```

### ENV

Environment identifier for logging and behavior.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `dev` |
| **Options** | `dev`, `staging`, `production` |

```bash
ENV=production
```

### LOG_LEVEL

Logging verbosity level.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `DEBUG` |
| **Options** | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

```bash
LOG_LEVEL=INFO
```

### LOGGING_CONFIG_FILE

Path to logging configuration file.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `server/logging.conf` |

```bash
# Production (JSON logging)
LOGGING_CONFIG_FILE=server/logging.conf

# Development (simple logging)
LOGGING_CONFIG_FILE=server/logging_dev.conf
```

### CONSERVER_CONFIG_FILE

Path to YAML configuration file.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `./example_config.yml` |

```bash
CONSERVER_CONFIG_FILE=/etc/vcon/config.yml
```

### API_ROOT_PATH

Root path prefix for API endpoints.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `/api` |

```bash
API_ROOT_PATH=/api/v1
```

### TICK_INTERVAL

Processing tick interval in milliseconds.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `5000` |

```bash
TICK_INTERVAL=1000  # Check queues every second
```

## Authentication

### CONSERVER_API_TOKEN

API authentication token for all endpoints.

| Property | Value |
|----------|-------|
| **Required** | Yes (for production) |
| **Default** | None |

```bash
# Single token
CONSERVER_API_TOKEN=your-secure-token-here

# Generate secure token
openssl rand -hex 32
```

### CONSERVER_API_TOKEN_FILE

Path to file containing API tokens (one per line).

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | None |

```bash
CONSERVER_API_TOKEN_FILE=/etc/vcon/api_tokens.txt
```

File format:
```
token-one-here
token-two-here
admin-token-here
```

### CONSERVER_HEADER_NAME

HTTP header name for API token.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `x-conserver-api-token` |

```bash
CONSERVER_HEADER_NAME=Authorization
```

## Worker Configuration

### CONSERVER_WORKERS

Number of worker processes to spawn.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `1` |
| **Minimum** | `1` |

```bash
# Single worker (default)
CONSERVER_WORKERS=1

# Multi-worker mode
CONSERVER_WORKERS=4
```

!!! tip "Sizing Workers"
    For I/O-bound workloads (transcription, API calls), set to CPU core count.
    For CPU-bound workloads, set to CPU core count minus 1.

### CONSERVER_PARALLEL_STORAGE

Enable parallel writes to storage backends.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `true` |
| **Options** | `true`, `false`, `1`, `0`, `yes`, `no` |

```bash
# Enable parallel storage (default)
CONSERVER_PARALLEL_STORAGE=true

# Disable for sequential writes
CONSERVER_PARALLEL_STORAGE=false
```

### CONSERVER_START_METHOD

Multiprocessing start method for workers.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | Platform default |
| **Options** | `fork`, `spawn`, `forkserver` |

```bash
# Memory-efficient (Unix only)
CONSERVER_START_METHOD=fork

# Safer, cross-platform
CONSERVER_START_METHOD=spawn

# Hybrid approach
CONSERVER_START_METHOD=forkserver
```

| Method | Memory | Startup | Safety | Platform |
|--------|--------|---------|--------|----------|
| `fork` | Low (COW) | Fast | Lower | Unix only |
| `spawn` | Higher | Slower | Higher | All |
| `forkserver` | Medium | Medium | Medium | Unix |

## AI Service Keys

### DEEPGRAM_KEY

Deepgram API key for transcription.

| Property | Value |
|----------|-------|
| **Required** | If using Deepgram |
| **Default** | None |

```bash
DEEPGRAM_KEY=your-deepgram-api-key
```

### OPENAI_API_KEY

OpenAI API key for analysis and transcription.

| Property | Value |
|----------|-------|
| **Required** | If using OpenAI |
| **Default** | None |

```bash
OPENAI_API_KEY=sk-your-openai-api-key
```

### GROQ_API_KEY

Groq API key for Whisper transcription.

| Property | Value |
|----------|-------|
| **Required** | If using Groq |
| **Default** | None |

```bash
GROQ_API_KEY=gsk-your-groq-api-key
```

## Cache Settings

### VCON_REDIS_EXPIRY

Default TTL (Time-To-Live) for vCons stored in Redis (seconds).

This expiry applies to:

- **vCons created via POST `/vcon`**: New vCons are stored with this TTL
- **vCons created via POST `/vcon/external-ingress`**: External submissions use this TTL
- **vCons synced from storage backends**: When a vCon is fetched from storage and cached in Redis

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `3600` (1 hour) |

```bash
VCON_REDIS_EXPIRY=7200  # 2 hours
```

!!! warning "Cache Expiry Behavior"
    vCons will be automatically removed from Redis after this TTL expires.
    To ensure long-term retention, configure storage backends (S3, PostgreSQL, etc.)
    in your processing chains to persist vCons before they expire from Redis.

### VCON_INDEX_EXPIRY

Index expiration time in seconds.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `86400` (24 hours) |

```bash
VCON_INDEX_EXPIRY=172800  # 48 hours
```

### VCON_CONTEXT_EXPIRY

Context data expiration for ingress operations (seconds).

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `86400` (24 hours) |

```bash
VCON_CONTEXT_EXPIRY=43200  # 12 hours
```

### VCON_DLQ_EXPIRY

TTL for vCons moved to the Dead Letter Queue (seconds).

When a vCon fails processing and is moved to the DLQ, its TTL is extended to this value to ensure operators have sufficient time to investigate failures. This prevents vCons from expiring before they can be reviewed and reprocessed.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `604800` (7 days) |

```bash
# Extend DLQ retention to 14 days
VCON_DLQ_EXPIRY=1209600

# Disable DLQ expiry (vCons persist indefinitely)
VCON_DLQ_EXPIRY=0
```

!!! tip "DLQ Retention Strategy"
    The default 7-day retention gives operators time to investigate and reprocess failed vCons. Set to `0` if you want DLQ vCons to persist indefinitely (useful when using persistent storage backends).

### VCON_SORTED_SET_NAME

Redis sorted set name for vCon indexing.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `vcons` |

```bash
VCON_SORTED_SET_NAME=vcon_index
```

### VCON_SORTED_FORCE_RESET

Force reset sorted set on startup.

| Property | Value |
|----------|-------|
| **Required** | No |
| **Default** | `true` |

```bash
VCON_SORTED_FORCE_RESET=false
```

## Vector Database

### WEVIATE_HOST

Weaviate vector database host.

| Property | Value |
|----------|-------|
| **Required** | If using Weaviate |
| **Default** | `localhost:8000` |

```bash
WEVIATE_HOST=weaviate:8080
```

### WEVIATE_API_KEY

Weaviate API key.

| Property | Value |
|----------|-------|
| **Required** | If using Weaviate with auth |
| **Default** | None |

```bash
WEVIATE_API_KEY=your-weaviate-key
```

## Build Information

These are typically set at build time:

### VCON_SERVER_VERSION

Server version in CalVer format.

```bash
VCON_SERVER_VERSION=2024.01.15
```

### VCON_SERVER_GIT_COMMIT

Git commit hash of the build.

```bash
VCON_SERVER_GIT_COMMIT=a1b2c3d
```

### VCON_SERVER_BUILD_TIME

ISO timestamp of the build.

```bash
VCON_SERVER_BUILD_TIME=2024-01-15T10:30:00Z
```

## Complete Example

```bash
# =============================================================================
# vCon Server Environment Configuration
# =============================================================================

# Core Settings
REDIS_URL=redis://redis:6379
HOSTNAME=https://api.example.com
ENV=production
LOG_LEVEL=INFO
CONSERVER_CONFIG_FILE=/etc/vcon/config.yml

# Authentication
CONSERVER_API_TOKEN=your-secure-production-token
CONSERVER_HEADER_NAME=x-conserver-api-token

# Worker Configuration
CONSERVER_WORKERS=4
CONSERVER_PARALLEL_STORAGE=true
CONSERVER_START_METHOD=fork

# AI Services
DEEPGRAM_KEY=your-deepgram-key
OPENAI_API_KEY=your-openai-key
GROQ_API_KEY=your-groq-key

# Cache Settings
VCON_REDIS_EXPIRY=3600
VCON_INDEX_EXPIRY=86400
VCON_CONTEXT_EXPIRY=86400

# Processing
TICK_INTERVAL=5000
```

## Environment-Specific Configurations

### Development

```bash
ENV=dev
LOG_LEVEL=DEBUG
LOGGING_CONFIG_FILE=server/logging_dev.conf
CONSERVER_WORKERS=1
CONSERVER_API_TOKEN=dev-token
```

### Staging

```bash
ENV=staging
LOG_LEVEL=INFO
CONSERVER_WORKERS=2
CONSERVER_API_TOKEN=staging-token
```

### Production

```bash
ENV=production
LOG_LEVEL=INFO
LOGGING_CONFIG_FILE=server/logging.conf
CONSERVER_WORKERS=8
CONSERVER_PARALLEL_STORAGE=true
CONSERVER_START_METHOD=fork
```
