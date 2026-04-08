# VCONIC Conserver — Quick Start Guide

**Document ID:** VCONIC-CSV-QSG-001  
**Product:** VCONIC Conserver  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## Purpose

This guide gets the VCONIC Conserver running on a single host in under 30 minutes. For full installation procedures, see the [Installation Guide](./02-installation-guide.md).

---

## Prerequisites Checklist

Before you begin, confirm the following:

- [ ] Linux host with Docker Engine 24+ and Docker Compose V2
- [ ] Minimum 4 CPU cores, 16 GB RAM, 50 GB free disk
- [ ] Outbound HTTPS access to api.groq.com and api.openai.com
- [ ] A Groq API key (for transcription) — obtain from https://console.groq.com
- [ ] An OpenAI API key (for analysis) — obtain from https://platform.openai.com
- [ ] The VCONIC Conserver release package or access to the container registry

---

## Step 1: Prepare the Host

Verify Docker is installed and running:

```bash
docker --version       # Expect: Docker version 24.x or later
docker compose version # Expect: Docker Compose version v2.x
```

Create the Docker network used by all VCONIC services:

```bash
docker network create conserver
```

---

## Step 2: Extract and Configure

Clone or extract the Conserver package to the installation directory:

```bash
cd /opt
git clone <conserver-repo-url> vcon-server
cd vcon-server
```

Create the configuration files from templates:

```bash
cp example_docker-compose.yml docker-compose.yml
cp .env.example .env
```

Edit the `.env` file and set these required values:

```bash
# Required: API authentication token (generate a strong random string)
CONSERVER_API_TOKEN=<your-secure-token>

# Required: Enable PostgreSQL storage
COMPOSE_PROFILES=postgres

# Required: External service API keys
GROQ_API_KEY=<your-groq-api-key>
OPENAI_API_KEY=<your-openai-api-key>
```

---

## Step 3: Build and Start

Build the container images:

```bash
docker compose build
```

Start all services:

```bash
docker compose up -d
```

---

## Step 4: Verify

Check that all containers are running:

```bash
docker compose ps
```

You should see `conserver`, `api`, `redis`, and `postgres` all in "Up" state.

Hit the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status": "healthy", "version": {...}}
```

Check the Conserver worker logs:

```bash
docker compose logs conserver --tail 20
```

You should see the worker starting and waiting for vCons on the ingress queue.

---

## Step 5: Submit a Test vCon

Send a minimal test vCon to confirm end-to-end operation:

```bash
curl -X POST http://localhost:8000/vcon \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: <your-secure-token>" \
  -d '{
    "vcon": "0.0.1",
    "parties": [
      {"tel": "+1234567890", "name": "Test Caller"},
      {"tel": "+0987654321", "name": "Test Agent"}
    ],
    "dialog": [],
    "analysis": [],
    "attachments": []
  }'
```

A successful response returns the stored vCon with its UUID.

---

## What's Next

| Task | Document |
|------|----------|
| Full installation with SSL, scaling, and production hardening | [Installation Guide](./02-installation-guide.md) |
| Configure processing chains, storage backends, and API keys | [Configuration Guide](./03-configuration-guide.md) |
| Day-to-day operations, backups, and monitoring | [Administration Guide](./04-administration-guide.md) |
| Troubleshoot issues | [Troubleshooting Guide](./05-troubleshooting-guide.md) |

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
