# VCONIC Conserver — Troubleshooting Guide

**Document ID:** VCONIC-CSV-TSG-001  
**Product:** VCONIC Conserver  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## 1. Troubleshooting Methodology

When diagnosing an issue with the Conserver, follow this systematic approach:

1. **Check service status:** `docker compose ps`
2. **Check health endpoint:** `curl http://localhost:8000/health`
3. **Check queue depths:** `curl "http://localhost:8000/stats/queue?list_name=default"`
4. **Check logs:** `docker compose logs --tail 50 <service>`
5. **Check DLQ:** `docker compose exec redis redis-cli LLEN "DLQ:default"`

---

## 2. Common Issues

### 2.1 Services Won't Start

**Symptom:** `docker compose up` fails or containers exit immediately.

| Possible Cause | Diagnosis | Resolution |
|----------------|-----------|------------|
| Port conflict | `docker compose logs <service>` shows "address already in use" | Change port in `.env` or stop conflicting service |
| Docker network missing | Error: "network conserver not found" | Run `docker network create conserver` |
| Invalid .env syntax | Container exits with code 1 | Check `.env` for syntax errors (no spaces around `=`) |
| Missing Docker image | "image not found" error | Run `docker compose build` |
| Insufficient memory | Container killed (OOM) | Check `docker logs` for OOM, increase host RAM |

**Diagnostic commands:**

```bash
docker compose logs --tail 20 api
docker compose logs --tail 20 conserver
docker compose logs --tail 20 redis
docker compose logs --tail 20 postgres
```

### 2.2 API Returns 401 Unauthorized

**Symptom:** API requests return HTTP 401.

| Possible Cause | Diagnosis | Resolution |
|----------------|-----------|------------|
| Wrong API token | Check token matches `.env` | Verify `CONSERVER_API_TOKEN` in `.env` |
| Wrong header name | Check request header | Use `x-conserver-api-token` (or custom `CONSERVER_HEADER_NAME`) |
| Token file not found | Check logs for file errors | Verify `CONSERVER_API_TOKEN_FILE` path is accessible inside container |
| Ingress-specific auth | Using external-ingress endpoint | Check `ingress_auth` in `config.yml` |

**Test command:**

```bash
curl -v http://localhost:8000/health  # No auth needed
curl -v -H "x-conserver-api-token: YOUR_TOKEN" http://localhost:8000/vcon
```

### 2.3 vCons Stuck in Queue (Not Processing)

**Symptom:** Queue depth grows but vCons are not being processed.

| Possible Cause | Diagnosis | Resolution |
|----------------|-----------|------------|
| No worker running | `docker compose ps` shows conserver not running | `docker compose up -d conserver` |
| Wrong ingress list | Worker watches different queue than API writes to | Check `ingress_lists` in `config.yml` matches API `ingress_list` parameter |
| Chain disabled | `enabled: 0` in config.yml | Set `enabled: 1` for the chain |
| Worker crash loop | Check worker logs | Fix the error, rebuild if needed |
| Redis connection failed | Worker logs show Redis errors | Verify `REDIS_URL` and Redis container status |

**Diagnostic commands:**

```bash
# Check queue depth
docker compose exec redis redis-cli LLEN default

# Check what queues exist
docker compose exec redis redis-cli KEYS "*"

# Check worker logs
docker compose logs --tail 50 conserver
```

### 2.4 Transcription Failures

**Symptom:** vCons are processed but have no transcript, or end up in DLQ.

| Possible Cause | Diagnosis | Resolution |
|----------------|-----------|------------|
| Invalid API key | Logs show 401 from Groq/Deepgram | Verify `GROQ_API_KEY` or `DEEPGRAM_KEY` in `.env` |
| No audio in vCon | vCon has empty dialog array | Ensure audio is included in the submitted vCon |
| Unsupported audio format | Logs show format error | Convert audio to WAV, MP3, or supported format |
| API rate limit | Logs show 429 status | Reduce worker count or add rate limiting |
| Network connectivity | Logs show connection timeout | Verify outbound access to API endpoint |

### 2.5 Analysis Failures (LLM)

**Symptom:** Transcription succeeds but analysis is missing or vCon goes to DLQ.

| Possible Cause | Diagnosis | Resolution |
|----------------|-----------|------------|
| Invalid OpenAI key | Logs show 401 from OpenAI | Verify `OPENAI_API_KEY` in `.env` |
| Model not available | Logs show model error | Check model name in `config.yml` is valid |
| Token limit exceeded | Logs show context length error | Use a model with larger context or truncate transcript |
| Rate limiting | Logs show 429 status | Reduce concurrency or upgrade API plan |

### 2.6 Database Connection Issues

**Symptom:** Storage fails, vCons go to DLQ with database errors.

| Possible Cause | Diagnosis | Resolution |
|----------------|-----------|------------|
| Wrong connection string | Logs show connection refused | Verify `VCON_STORAGE` in `.env` |
| Database not running | `docker compose ps` shows postgres down | `docker compose up -d postgres` |
| Database full | Logs show disk space error | Increase disk space or purge old data |
| Schema missing | Logs show relation not found | Run database migrations |
| Too many connections | Logs show connection pool exhausted | Reduce worker count or increase `max_connections` in PostgreSQL |

### 2.7 High Memory Usage

**Symptom:** Container uses excessive memory or gets OOM-killed.

| Possible Cause | Diagnosis | Resolution |
|----------------|-----------|------------|
| Large audio files | Check vCon sizes in Redis | Process smaller batches or increase memory |
| Too many workers | Each worker consumes memory | Reduce `CONSERVER_WORKERS` |
| Redis memory growth | `redis-cli INFO memory` | Set `maxmemory` policy in Redis or reduce TTLs |
| Memory leak | Memory grows without load | Restart containers; report to VCONIC engineering |

---

## 3. Dead Letter Queue (DLQ) Investigation

### 3.1 Checking the DLQ

```bash
# List DLQ items
curl http://localhost:8000/dlq/default \
  -H "x-conserver-api-token: <token>"

# Check DLQ depth
docker compose exec redis redis-cli LLEN "DLQ:default"
```

### 3.2 Inspecting a Failed vCon

```bash
# Get the UUID from the DLQ list, then retrieve the vCon
curl http://localhost:8000/vcon/<uuid> \
  -H "x-conserver-api-token: <token>"
```

### 3.3 Reprocessing Failed vCons

```bash
# Reprocess a single vCon
curl -X POST "http://localhost:8000/dlq/default/reprocess/<uuid>" \
  -H "x-conserver-api-token: <token>"
```

### 3.4 Common DLQ Causes

| Error Pattern | Likely Cause | Resolution |
|--------------|-------------|------------|
| "Connection refused" | External service down | Verify service connectivity, reprocess after fix |
| "401 Unauthorized" | Bad API key | Fix API key in `.env`, restart, reprocess |
| "429 Too Many Requests" | Rate limited | Wait and reprocess, or reduce concurrency |
| "Timeout" | Slow external service | Increase timeout, check network, reprocess |
| "Invalid audio" | Corrupt or unsupported file | Inspect the audio, resubmit with valid file |

---

## 4. Diagnostic Commands Reference

### 4.1 Service Diagnostics

```bash
# Full service status
docker compose ps

# Container resource usage
docker stats --no-stream

# Container inspect (networking, mounts, config)
docker inspect <container_name>
```

### 4.2 Redis Diagnostics

```bash
# Connection test
docker compose exec redis redis-cli PING

# Memory usage
docker compose exec redis redis-cli INFO memory

# Key count
docker compose exec redis redis-cli DBSIZE

# List all queues
docker compose exec redis redis-cli KEYS "*"

# Queue depth for specific queue
docker compose exec redis redis-cli LLEN default

# Peek at next item in queue (without removing)
docker compose exec redis redis-cli LINDEX default 0
```

### 4.3 PostgreSQL Diagnostics

```bash
# Connection test
docker compose exec postgres psql -U postgres -c "SELECT 1;"

# Active connections
docker compose exec postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"

# Database size
docker compose exec postgres psql -U postgres -d conserver -c "SELECT pg_size_pretty(pg_database_size('conserver'));"

# Table row counts
docker compose exec postgres psql -U postgres -d conserver -c "
  SELECT relname, n_live_tup
  FROM pg_stat_user_tables
  ORDER BY n_live_tup DESC;
"
```

### 4.4 Network Diagnostics

```bash
# Test outbound connectivity
curl -s -o /dev/null -w "HTTP %{http_code}" https://api.groq.com
curl -s -o /dev/null -w "HTTP %{http_code}" https://api.openai.com

# Check DNS resolution
docker compose exec api nslookup api.groq.com

# Check port connectivity between containers
docker compose exec api nc -zv redis 6379
docker compose exec api nc -zv postgres 5432
```

### 4.5 API Diagnostics

```bash
# Health (no auth)
curl -v http://localhost:8000/health

# Version (no auth)
curl http://localhost:8000/version

# Queue stats (no auth)
curl "http://localhost:8000/stats/queue?list_name=default"

# Submit test vCon
curl -X POST http://localhost:8000/vcon \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: <token>" \
  -d '{"vcon":"0.0.1","parties":[],"dialog":[],"analysis":[],"attachments":[]}'
```

---

## 5. Escalation Procedures

### 5.1 When to Escalate to VCONIC Engineering

Escalate when:

- DLQ items cannot be explained by external service issues
- Container crashes repeatedly with the same error
- Data corruption is suspected
- Performance degrades without configuration changes
- A bug in the processing logic is identified

### 5.2 Information to Collect Before Escalating

Gather and provide:

1. **Service status:** Output of `docker compose ps`
2. **Logs:** Last 200 lines from affected service
3. **Configuration:** `.env` and `config.yml` (redact API keys)
4. **Queue state:** Current depths of all queues and DLQ
5. **Error details:** Exact error message and timestamp
6. **Steps to reproduce:** What was happening when the issue occurred
7. **Environment:** Docker version, OS version, host resources

```bash
# Collect diagnostic bundle
mkdir -p /tmp/diagnostics
docker compose ps > /tmp/diagnostics/services.txt
docker compose logs --tail 200 > /tmp/diagnostics/logs.txt 2>&1
docker compose exec -T redis redis-cli INFO > /tmp/diagnostics/redis.txt
cp .env /tmp/diagnostics/env.txt  # REDACT API KEYS BEFORE SENDING
cp config.yml /tmp/diagnostics/config.yml
tar czf /tmp/diagnostics.tar.gz /tmp/diagnostics/
```

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
