# VCONIC Conserver — Installation Guide

**Document ID:** VCONIC-CSV-INST-001  
**Product:** VCONIC Conserver  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## 1. Overview

This guide provides step-by-step procedures for installing the VCONIC Conserver on a production host. The Conserver is the core conversation processing engine that ingests, transcribes, analyzes, and stores vCon data.

For a quick evaluation setup, see the [Quick Start Guide](./01-quick-start-guide.md).

---

## 2. Pre-Installation Checklist

Complete every item before beginning installation.

### 2.1 Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 16 GB | 32 GB |
| Disk | 100 GB SSD | 500 GB NVMe SSD |
| Network | 100 Mbps | 1 Gbps |

### 2.2 Software Requirements

| Software | Version | Purpose |
|----------|---------|---------|
| Linux OS | Ubuntu 22.04+, RHEL 8+, or equivalent | Host operating system |
| Docker Engine | 24.0+ | Container runtime |
| Docker Compose | V2 (2.20+) | Container orchestration |
| git | 2.x | Source retrieval (if cloning) |

Verify Docker installation:

```bash
docker --version
docker compose version
```

### 2.3 Network Requirements

**Inbound ports (from load balancer or clients):**

| Port | Protocol | Purpose |
|------|----------|---------|
| 8000 | HTTP | Conserver API (behind reverse proxy in production) |

**Outbound access required:**

| Destination | Port | Purpose | Required? |
|-------------|------|---------|-----------|
| api.groq.com | 443 | Speech-to-text transcription | Yes (if using Groq) |
| api.deepgram.com | 443 | Speech-to-text transcription | Yes (if using Deepgram) |
| api.openai.com | 443 | LLM analysis and summarization | Yes (if using OpenAI) |
| Docker registry | 443 | Image pulls | Yes (initial install and upgrades) |

### 2.4 External Service Accounts

Obtain the following credentials before installation:

| Service | Credential | How to Obtain |
|---------|------------|---------------|
| Groq | API key | https://console.groq.com — Create account, generate API key |
| OpenAI | API key | https://platform.openai.com — Create account, generate API key |
| Deepgram (optional) | API key | https://console.deepgram.com — Create account, generate API key |

### 2.5 Pre-Installation Verification

Run these commands on the target host to confirm readiness:

```bash
# Check Docker
docker info | grep "Server Version"

# Check available disk
df -h /var/lib/docker

# Check available memory
free -h

# Check CPU count
nproc

# Check outbound connectivity
curl -s -o /dev/null -w "%{http_code}" https://api.groq.com
curl -s -o /dev/null -w "%{http_code}" https://api.openai.com
```

---

## 3. Installation Procedure

### 3.1 Create the Docker Network

All VCONIC services communicate over a shared Docker network:

```bash
docker network create conserver
```

> **NOTE:** This network is shared across all VCONIC products. Create it once. If it already exists, the command will report an error — this is safe to ignore.

### 3.2 Obtain the Software

**Option A: Clone from repository**

```bash
cd /opt
git clone <conserver-repo-url> vcon-server
cd vcon-server
```

**Option B: Extract from release archive**

```bash
cd /opt
tar xzf vconic-conserver-<version>.tar.gz
cd vcon-server
```

### 3.3 Create Configuration Files

```bash
cp example_docker-compose.yml docker-compose.yml
cp .env.example .env
```

### 3.4 Configure the Environment File

Edit `.env` with the values for this deployment:

```bash
# ==============================================================
# REQUIRED SETTINGS
# ==============================================================

# Docker Compose profiles - determines which services to start
# Options: postgres, elasticsearch, langfuse (comma-separated)
COMPOSE_PROFILES=postgres

# API authentication token
# Generate with: openssl rand -hex 32
CONSERVER_API_TOKEN=<your-secure-token>

# External service API keys
GROQ_API_KEY=<your-groq-api-key>
OPENAI_API_KEY=<your-openai-api-key>

# ==============================================================
# PROCESSING SETTINGS
# ==============================================================

# Number of worker processes (one per CPU core recommended)
CONSERVER_WORKERS=4

# Enable parallel writes to storage backends
CONSERVER_PARALLEL_STORAGE=true

# Path to the processing chain configuration
CONSERVER_CONFIG_FILE=./config.yml

# ==============================================================
# REDIS SETTINGS
# ==============================================================

# Redis connection URL (default uses the bundled Redis container)
REDIS_URL=redis://redis

# Redis Insight UI port (for administration)
REDIS_EXTERNAL_PORT=8001

# vCon cache TTL in seconds (default: 1 hour)
VCON_REDIS_EXPIRY=3600

# Dead letter queue retention in seconds (default: 7 days)
VCON_DLQ_EXPIRY=604800

# ==============================================================
# DATABASE SETTINGS (when using bundled PostgreSQL)
# ==============================================================

# PostgreSQL connection string
VCON_STORAGE=postgresql://postgres:postgres@postgres:5432/conserver

# ==============================================================
# OBSERVABILITY (Optional)
# ==============================================================

# Log level: DEBUG, INFO, WARN, ERROR
LOG_LEVEL=INFO

# OpenTelemetry (uncomment to enable)
# OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
# OTEL_EXPORTER_OTLP_PROTOCOL=grpc
# OTEL_SERVICE_NAME=conserver
```

### 3.5 Configure the Processing Chain

Edit `config.yml` to define how vCons are processed. A typical production configuration:

```yaml
# Processing links (transformation steps)
links:
  transcribe:
    module: links.groq_transcribe
    options:
      model: whisper-large-v3

  analyze:
    module: links.openai_analyze
    options:
      model: gpt-4
      prompt: |
        Summarize this conversation. Identify the customer's issue,
        the resolution provided, and the sentiment of the interaction.

# Storage backends
storages:
  postgres:
    module: storage.postgres
    options:
      connection_string: ${VCON_STORAGE}

# Processing chains
chains:
  default:
    links:
      - transcribe
      - analyze
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

> **NOTE:** The `config.yml` file supports multiple chains for different data sources. Each chain specifies which ingress queue it consumes, which links to run, and which storage backends to write to. See the [Configuration Guide](./03-configuration-guide.md) for all available links and options.

### 3.6 Build Container Images

```bash
docker compose build
```

This typically takes 3–5 minutes on first build.

### 3.7 Start Services

```bash
docker compose up -d
```

### 3.8 Verify Service Status

```bash
docker compose ps
```

Expected output shows all services in "Up" state:

```
NAME         SERVICE      STATUS       PORTS
api          api          Up           0.0.0.0:8000->8000/tcp
conserver    conserver    Up
postgres     postgres     Up           0.0.0.0:5432->5432/tcp
redis        redis        Up           0.0.0.0:6379->6379/tcp, 0.0.0.0:8001->8001/tcp
```

---

## 4. Post-Installation Verification

### 4.1 Health Check

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status": "healthy", "version": {...}}
```

### 4.2 Version Check

```bash
curl http://localhost:8000/version
```

### 4.3 Queue Depth Check

```bash
curl "http://localhost:8000/stats/queue?list_name=default"
```

Expected:

```json
{"list_name": "default", "depth": 0}
```

### 4.4 End-to-End Smoke Test

Submit a test vCon and verify it is processed:

```bash
# Submit a test vCon
UUID=$(curl -s -X POST http://localhost:8000/vcon \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: <your-token>" \
  -d '{
    "vcon": "0.0.1",
    "parties": [
      {"tel": "+15551234567", "name": "Smoke Test Caller"},
      {"tel": "+15559876543", "name": "Smoke Test Agent"}
    ],
    "dialog": [],
    "analysis": [],
    "attachments": []
  }' | python3 -c "import sys,json; print(json.load(sys.stdin)['uuid'])")

echo "Submitted vCon UUID: $UUID"

# Wait for processing
sleep 5

# Retrieve the processed vCon
curl -s http://localhost:8000/vcon/$UUID \
  -H "x-conserver-api-token: <your-token>" | python3 -m json.tool
```

### 4.5 Log Verification

Check that no errors appear in the logs:

```bash
docker compose logs --tail 50 api
docker compose logs --tail 50 conserver
```

---

## 5. Production Hardening

### 5.1 SSL/TLS Configuration

For production deployments, place nginx in front of the Conserver API:

The Conserver includes an `install_conserver.sh` script that automates nginx + Let's Encrypt setup:

```bash
./scripts/install_conserver.sh \
  --domain conserver.example.com \
  --email admin@example.com \
  --token <your-api-token>
```

For manual nginx configuration, create a site configuration:

```nginx
server {
    listen 443 ssl;
    server_name conserver.example.com;

    ssl_certificate     /etc/ssl/certs/conserver.crt;
    ssl_certificate_key /etc/ssl/private/conserver.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5.2 Scaling Workers

Scale the number of Conserver workers based on conversation volume:

```bash
docker compose up --scale conserver=4 -d
```

**Guideline:** 1 worker per CPU core. Each worker processes vCons independently.

Also set `CONSERVER_WORKERS` in `.env` to control the number of processing threads within each container.

### 5.3 External Database

For production, use a managed PostgreSQL instance instead of the bundled container:

1. Set `COMPOSE_PROFILES=` (empty — no bundled postgres)
2. Set `VCON_STORAGE=postgresql://<user>:<pass>@<host>:5432/<db>` in `.env`

### 5.4 External Redis

For high-availability deployments, use a managed Redis instance:

1. Set `REDIS_URL=redis://<user>:<pass>@<host>:6379` in `.env`
2. Remove the `redis` service from `docker-compose.yml`

### 5.5 Firewall Rules

Apply the following rules on the host:

```bash
# Allow HTTPS from clients
ufw allow 443/tcp

# Allow API from internal network only (if no nginx)
ufw allow from 10.0.0.0/8 to any port 8000

# Deny direct access to Redis, PostgreSQL from outside
ufw deny 6379/tcp
ufw deny 5432/tcp
```

### 5.6 Log Persistence

Configure Docker log drivers for centralized logging:

```yaml
# In docker-compose.yml, add to each service:
logging:
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "5"
```

---

## 6. Uninstallation

To completely remove the Conserver:

```bash
# Stop all services
docker compose down

# Remove volumes (WARNING: destroys all data)
docker compose down -v

# Remove images
docker compose down --rmi all

# Remove installation directory
rm -rf /opt/vcon-server

# Remove Docker network (only if no other VCONIC products use it)
docker network rm conserver
```

> **CAUTION:** The `docker compose down -v` command permanently deletes all database and Redis data. Always perform a backup before uninstalling. See the [Administration Guide](./04-administration-guide.md) for backup procedures.

---

## 7. Installation Checklist Summary

Use this checklist to verify a complete installation:

- [ ] Docker network `conserver` created
- [ ] Software extracted to `/opt/vcon-server`
- [ ] `.env` configured with all required values
- [ ] `config.yml` configured with processing chain
- [ ] Container images built successfully
- [ ] All services running (`docker compose ps`)
- [ ] Health endpoint returns healthy
- [ ] Smoke test vCon submitted and processed
- [ ] No errors in logs
- [ ] SSL/TLS configured (production)
- [ ] Firewall rules applied (production)
- [ ] Log rotation configured (production)
- [ ] Backup procedures documented and tested

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
