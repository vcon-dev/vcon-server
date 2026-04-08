# VCONIC Conserver — Configuration Guide

**Document ID:** VCONIC-CSV-CFG-001  
**Product:** VCONIC Conserver  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## 1. Overview

The Conserver is configured through two files:

| File | Purpose | Restart Required? |
|------|---------|-------------------|
| `.env` | Infrastructure settings (ports, credentials, scaling) | Yes |
| `config.yml` | Processing logic (chains, links, storages) | Yes |

Both files are located in the Conserver installation directory (e.g., `/opt/vcon-server`).

---

## 2. Environment Variables Reference (.env)

### 2.1 Docker Compose Profiles

| Variable | Default | Description |
|----------|---------|-------------|
| `COMPOSE_PROFILES` | *(empty)* | Comma-separated list of service profiles to activate |

**Available profiles:**

| Profile | Services Started |
|---------|-----------------|
| `postgres` | PostgreSQL database container |
| `elasticsearch` | Elasticsearch search engine container |
| `langfuse` | Langfuse LLM observability (+ postgres, clickhouse, minio) |

**Examples:**

```bash
# Minimal: bundled PostgreSQL only
COMPOSE_PROFILES=postgres

# With search indexing
COMPOSE_PROFILES=postgres,elasticsearch

# External databases (no bundled services)
COMPOSE_PROFILES=
```

### 2.2 API Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CONSERVER_API_TOKEN` | *(empty)* | API authentication token. If empty, auth is disabled. |
| `CONSERVER_API_TOKEN_FILE` | *(empty)* | Path to file containing one token per line (for multiple tokens) |
| `CONSERVER_HEADER_NAME` | `x-conserver-api-token` | HTTP header name for API authentication |
| `CONSERVER_EXTERNAL_PORT` | `8000` | Port exposed on the host for the API |
| `API_ROOT_PATH` | `/api` | Root path prefix for all API endpoints |
| `HOSTNAME` | `http://localhost:8000` | Base URL for the API (used in responses) |

### 2.3 Processing Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CONSERVER_WORKERS` | `1` | Number of worker processes per container |
| `CONSERVER_PARALLEL_STORAGE` | `true` | Write to multiple storage backends simultaneously |
| `CONSERVER_CONFIG_FILE` | `./config.yml` | Path to the processing chain configuration |
| `CONSERVER_START_METHOD` | *(auto)* | Python multiprocessing start method: `fork`, `spawn`, or `forkserver` |

**Worker scaling guidelines:**

| Conversations/Day | Recommended Workers |
|-------------------|-------------------|
| < 1,000 | 1–2 |
| 1,000–5,000 | 2–4 |
| 5,000–20,000 | 4–8 |
| > 20,000 | 8+ (use multiple containers) |

### 2.4 Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis` | Redis connection URL |
| `REDIS_EXTERNAL_PORT` | `8001` | Port for Redis Insight management UI |
| `VCON_REDIS_EXPIRY` | `3600` | vCon cache TTL in seconds (1 hour) |
| `VCON_INDEX_EXPIRY` | `86400` | Party index TTL in seconds (1 day) |
| `VCON_DLQ_EXPIRY` | `604800` | Dead letter queue retention in seconds (7 days) |
| `VCON_CONTEXT_EXPIRY` | `86400` | Trace context TTL in seconds (1 day) |
| `VCON_SORTED_SET_NAME` | `vcons` | Redis sorted set key for timestamp indexing |

### 2.5 Database Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `VCON_STORAGE` | *(empty)* | PostgreSQL connection string for vCon storage |

**Connection string format:**

```
postgresql://<user>:<password>@<host>:<port>/<database>
```

### 2.6 External Service API Keys

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(empty)* | OpenAI API key for LLM analysis |
| `GROQ_API_KEY` | *(empty)* | Groq API key for speech-to-text |
| `DEEPGRAM_KEY` | *(empty)* | Deepgram API key for speech-to-text |

### 2.7 Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `DEBUG` | Logging level: `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `LOGGING_CONFIG_FILE` | `server/logging.conf` | Path to Python logging configuration |
| `ENV` | `dev` | Environment name: `dev`, `staging`, `prod` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(empty)* | OpenTelemetry collector endpoint |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | OTLP protocol: `grpc` or `http/protobuf` |
| `OTEL_SERVICE_NAME` | `conserver` | Service name in telemetry data |

---

## 3. Processing Chain Configuration (config.yml)

The `config.yml` file defines how vCons are processed. It has four sections: **imports**, **links**, **storages**, and **chains**.

### 3.1 Structure

```yaml
# Optional: dynamic module imports
imports:
  <name>:
    module: <python_module_path>
    pip_name: <pip_package_name>

# Optional: per-ingress API authentication
ingress_auth:
  <ingress_list_name>: "<api_key>"

# Processing links (transformation steps)
links:
  <link_name>:
    module: <module_path>
    options:
      <key>: <value>

# Tracers (audit/integrity — optional)
tracers:
  <tracer_name>:
    module: <module_path>
    options:
      <key>: <value>

# Storage backends
storages:
  <storage_name>:
    module: <module_path>
    options:
      <key>: <value>

# Processing chains
chains:
  <chain_name>:
    links:
      - <link_name>
      - <link_name>
    tracers:
      - <tracer_name>
    storages:
      - <storage_name>
    ingress_lists:
      - <queue_name>
    egress_lists:
      - <queue_name>
    enabled: 1
```

### 3.2 Available Links

| Link Module | Purpose | Key Options |
|-------------|---------|-------------|
| `links.groq_transcribe` | Speech-to-text via Groq | `model`: whisper model name |
| `links.deepgram_transcribe` | Speech-to-text via Deepgram | `model`: deepgram model name |
| `links.openai_analyze` | LLM analysis via OpenAI | `model`, `prompt` |
| `links.webhook` | Send vCon to external URL | `url`, `method`, `headers` |
| `links.slack` | Post to Slack channel | `webhook_url`, `channel` |

### 3.3 Available Storages

| Storage Module | Purpose | Key Options |
|----------------|---------|-------------|
| `storage.postgres` | PostgreSQL database | `connection_string` |
| `storage.s3` | AWS S3 object storage | `bucket`, `region`, `prefix` |
| `storage.mongodb` | MongoDB document store | `connection_string`, `database`, `collection` |
| `storage.elasticsearch` | Elasticsearch index | `hosts`, `index_name` |
| `storage.milvus` | Milvus vector database | `host`, `port`, `collection` |

### 3.4 Example Configurations

**Basic: Transcribe and store**

```yaml
links:
  transcribe:
    module: links.groq_transcribe
    options:
      model: whisper-large-v3

storages:
  postgres:
    module: storage.postgres
    options:
      connection_string: ${VCON_STORAGE}

chains:
  default:
    links:
      - transcribe
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

**Advanced: Multi-source with analysis and webhooks**

```yaml
links:
  transcribe:
    module: links.groq_transcribe
    options:
      model: whisper-large-v3

  summarize:
    module: links.openai_analyze
    options:
      model: gpt-4
      prompt: |
        Provide a 2-3 sentence summary of this conversation.
        Identify the primary topic and outcome.

  categorize:
    module: links.openai_analyze
    options:
      model: gpt-4o-mini
      prompt: |
        Categorize this conversation into one of:
        sales, support, billing, complaint, general.
        Return only the category name.

  notify_slack:
    module: links.slack
    options:
      webhook_url: ${SLACK_WEBHOOK_URL}

storages:
  postgres:
    module: storage.postgres
    options:
      connection_string: ${VCON_STORAGE}

  search:
    module: storage.elasticsearch
    options:
      hosts:
        - http://elasticsearch:9200
      index_name: vcons

ingress_auth:
  support_calls: "support-api-key-abc123"
  sales_calls: "sales-api-key-xyz789"

chains:
  support_chain:
    links:
      - transcribe
      - summarize
      - categorize
      - notify_slack
    storages:
      - postgres
      - search
    ingress_lists:
      - support_calls
    enabled: 1

  sales_chain:
    links:
      - transcribe
      - summarize
    storages:
      - postgres
      - search
    ingress_lists:
      - sales_calls
    enabled: 1
```

### 3.5 Ingress-Specific Authentication

The `ingress_auth` section allows different API keys for different data sources:

```yaml
ingress_auth:
  # Single key per ingress
  support_calls: "key-abc-123"
  
  # Multiple keys per ingress
  partner_data:
    - "partner-key-1"
    - "partner-key-2"
```

Clients submit to a specific ingress using the query parameter:

```
POST /vcon/external-ingress?ingress_list=support_calls
Header: x-conserver-api-token: key-abc-123
```

---

## 4. Configuration Change Procedures

### 4.1 Changing .env Values

1. Edit the `.env` file
2. Restart affected services:

```bash
# Restart all services
docker compose restart

# Or restart specific services
docker compose restart api conserver
```

### 4.2 Changing config.yml

1. Edit `config.yml`
2. Restart the Conserver worker(s):

```bash
docker compose restart conserver
```

> **NOTE:** The API service does not need to be restarted for config.yml changes. Only the worker processes read this file.

### 4.3 Adding a New Processing Chain

1. Add the new link, storage, and chain definitions to `config.yml`
2. Restart the Conserver workers
3. Verify by submitting a test vCon to the new ingress queue:

```bash
curl -X POST "http://localhost:8000/vcon?ingress_list=new_queue" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: <token>" \
  -d '{"vcon":"0.0.1","parties":[],"dialog":[],"analysis":[],"attachments":[]}'
```

### 4.4 Configuration Validation

After any configuration change, verify:

```bash
# Check all services are healthy
docker compose ps

# Check API health
curl http://localhost:8000/health

# Check logs for errors
docker compose logs --tail 20 conserver
docker compose logs --tail 20 api
```

---

## 5. Common Configuration Scenarios

### 5.1 Using an External PostgreSQL Database

```bash
# .env
COMPOSE_PROFILES=           # Remove 'postgres' profile
VCON_STORAGE=postgresql://user:password@db.example.com:5432/conserver
```

### 5.2 Adding Elasticsearch for Search

```bash
# .env
COMPOSE_PROFILES=postgres,elasticsearch
```

```yaml
# config.yml — add to storages
storages:
  search:
    module: storage.elasticsearch
    options:
      hosts:
        - http://elasticsearch:9200
      index_name: vcons

# Add 'search' to chain storages
chains:
  default:
    storages:
      - postgres
      - search
```

### 5.3 Configuring Multiple API Tokens

Create a token file:

```bash
echo "token-for-internal-api" > /opt/vcon-server/api_tokens.txt
echo "token-for-partner-1" >> /opt/vcon-server/api_tokens.txt
echo "token-for-partner-2" >> /opt/vcon-server/api_tokens.txt
```

```bash
# .env
CONSERVER_API_TOKEN_FILE=./api_tokens.txt
```

### 5.4 Enabling OpenTelemetry

```bash
# .env
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_SERVICE_NAME=conserver
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
