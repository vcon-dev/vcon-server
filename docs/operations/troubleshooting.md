# Troubleshooting

Common issues and solutions for vCon Server.

## Diagnostic Commands

### Quick Health Check

```bash
# API health
curl -s http://localhost:8000/api/health | jq .

# Service status
docker compose ps

# Recent logs
docker compose logs --tail=50 conserver

# Queue status
docker compose exec redis redis-cli LLEN default
docker compose exec redis redis-cli LLEN DLQ:default
```

### Comprehensive Diagnostic Script

```bash
#!/bin/bash
# diagnose.sh

echo "=== vCon Server Diagnostics ==="
echo

echo "1. Service Status:"
docker compose ps
echo

echo "2. API Health:"
curl -s http://localhost:8000/api/health 2>/dev/null || echo "API unreachable"
echo

echo "3. Version:"
curl -s http://localhost:8000/api/version 2>/dev/null || echo "Cannot get version"
echo

echo "4. Queue Depths:"
echo "   default: $(docker compose exec -T redis redis-cli LLEN default 2>/dev/null || echo 'N/A')"
echo "   DLQ:default: $(docker compose exec -T redis redis-cli LLEN DLQ:default 2>/dev/null || echo 'N/A')"
echo

echo "5. Recent Errors:"
docker compose logs --tail=20 conserver 2>&1 | grep -i error || echo "   No recent errors"
echo

echo "6. Resource Usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "   Cannot get stats"
```

## Startup Issues

### Services Won't Start

**Symptoms:**
- `docker compose up` fails
- Containers exit immediately

**Check:**

```bash
# View exit codes
docker compose ps -a

# Check logs for errors
docker compose logs
```

**Common Causes:**

1. **Port already in use**
   ```bash
   # Find what's using port 8000
   lsof -i :8000
   
   # Change port in docker-compose.yml
   ports:
     - "8080:8000"
   ```

2. **Missing environment variables**
   ```bash
   # Check .env file exists
   ls -la .env
   
   # Verify required variables
   grep REDIS_URL .env
   grep CONSERVER_API_TOKEN .env
   ```

3. **Invalid configuration**
   ```bash
   # Validate YAML
   python -c "import yaml; yaml.safe_load(open('config.yml'))"
   ```

4. **Network not created**
   ```bash
   docker network create conserver
   ```

### Redis Connection Failed

**Symptoms:**
- `Connection refused` errors
- Workers not processing

**Check:**

```bash
# Redis running?
docker compose ps redis

# Can connect?
docker compose exec redis redis-cli ping
```

**Solutions:**

1. **Redis not started**
   ```bash
   docker compose up -d redis
   ```

2. **Wrong URL**
   ```bash
   # Should match docker-compose service name
   REDIS_URL=redis://redis:6379
   ```

3. **Network issue**
   ```bash
   # Recreate network
   docker compose down
   docker network rm conserver
   docker network create conserver
   docker compose up -d
   ```

## Processing Issues

### vCons Not Processing

**Symptoms:**
- Queue depth increasing
- No processing logs

**Check:**

```bash
# Workers running?
docker compose ps conserver

# Processing logs?
docker compose logs --tail=50 conserver | grep -i "processing"

# Queue has items?
docker compose exec redis redis-cli LLEN default
```

**Solutions:**

1. **Chain not enabled**
   ```yaml
   chains:
     my_chain:
       enabled: 1  # Must be 1
   ```

2. **Ingress list mismatch**
   ```yaml
   # Submission ingress_list must match chain
   chains:
     my_chain:
       ingress_lists:
         - default  # Must match submission
   ```

3. **Workers crashed**
   ```bash
   # Restart workers
   docker compose restart conserver
   ```

### Slow Processing

**Symptoms:**
- High queue depth
- Long processing times

**Check:**

```bash
# Queue depth trend
watch -n 5 'docker compose exec -T redis redis-cli LLEN default'

# Processing logs
docker compose logs -f conserver
```

**Solutions:**

1. **Scale workers**
   ```bash
   CONSERVER_WORKERS=4
   docker compose restart conserver
   ```

2. **Enable parallel storage**
   ```bash
   CONSERVER_PARALLEL_STORAGE=true
   ```

3. **Check external API latency**
   ```bash
   # If using transcription
   time curl -X POST https://api.deepgram.com/...
   ```

### DLQ Growing

**Symptoms:**
- Items appearing in DLQ
- Processing failures

**Check:**

```bash
# View DLQ contents
curl "http://localhost:8000/api/dlq?ingress_list=default" \
  -H "x-conserver-api-token: $TOKEN"

# Check logs for errors
docker compose logs conserver | grep -i error
```

**Solutions:**

1. **Fix the root cause** (check error logs)

2. **Reprocess after fix**
   ```bash
   curl -X POST "http://localhost:8000/api/dlq/reprocess?ingress_list=default" \
     -H "x-conserver-api-token: $TOKEN"
   ```

## API Issues

### 403 Forbidden

**Symptoms:**
- API returns 403
- "Invalid or missing API token"

**Check:**

```bash
# Token set?
echo $CONSERVER_API_TOKEN

# Correct header?
curl -v -H "x-conserver-api-token: $TOKEN" http://localhost:8000/api/vcon
```

**Solutions:**

1. **Set token in environment**
   ```bash
   export CONSERVER_API_TOKEN=your-token
   ```

2. **Check header name**
   ```bash
   # Default header
   -H "x-conserver-api-token: $TOKEN"
   
   # Custom header (check CONSERVER_HEADER_NAME)
   -H "$CUSTOM_HEADER: $TOKEN"
   ```

3. **For external ingress, check ingress_auth**
   ```yaml
   ingress_auth:
     partner_input: "partner-key"  # Key must match
   ```

### 404 Not Found

**Symptoms:**
- vCon not found
- Endpoint not found

**Solutions:**

1. **Check UUID exists**
   ```bash
   docker compose exec redis redis-cli EXISTS vcon:abc-123
   ```

2. **Sync from storage**
   ```bash
   # GET will sync from storage if not in Redis
   curl http://localhost:8000/api/vcon/abc-123 -H "x-conserver-api-token: $TOKEN"
   ```

3. **Check API path**
   ```bash
   # Include /api prefix
   curl http://localhost:8000/api/vcon  # Correct
   curl http://localhost:8000/vcon      # Wrong
   ```

### 500 Internal Server Error

**Symptoms:**
- Server errors
- Unexpected failures

**Check:**

```bash
# API logs
docker compose logs api | grep -i error
```

**Solutions:**

1. **Check configuration**
   ```bash
   curl http://localhost:8000/api/config -H "x-conserver-api-token: $TOKEN"
   ```

2. **Restart API**
   ```bash
   docker compose restart api
   ```

## Storage Issues

### Storage Write Failures

**Symptoms:**
- Processing completes but data not persisted
- Storage-related errors in logs

**Check:**

```bash
# Check storage logs
docker compose logs conserver | grep -i storage

# Test storage connectivity
docker compose exec conserver python -c "
from storage import Storage
s = Storage('postgres')
print(s.get('test-uuid'))
"
```

**Solutions:**

1. **Check credentials**
   ```yaml
   storages:
     postgres:
       options:
         user: correct_user
         password: correct_password
   ```

2. **Check connectivity**
   ```bash
   docker compose exec conserver ping postgres
   ```

3. **Check storage service running**
   ```bash
   docker compose ps postgres
   ```

### Storage Sync Issues

**Symptoms:**
- vCon in storage but not found via API

**Solutions:**

1. **Force sync**
   ```bash
   # GET syncs from storage
   curl http://localhost:8000/api/vcon/abc-123 -H "x-conserver-api-token: $TOKEN"
   ```

2. **Rebuild index**
   ```bash
   curl http://localhost:8000/api/index_vcons -H "x-conserver-api-token: $TOKEN"
   ```

## Resource Issues

### High Memory Usage

**Symptoms:**
- OOM kills
- Slow performance

**Check:**

```bash
docker stats
```

**Solutions:**

1. **Reduce workers**
   ```bash
   CONSERVER_WORKERS=2
   ```

2. **Use fork start method**
   ```bash
   CONSERVER_START_METHOD=fork
   ```

3. **Add memory limits**
   ```yaml
   services:
     conserver:
       deploy:
         resources:
           limits:
             memory: 2G
   ```

### High CPU Usage

**Symptoms:**
- CPU at 100%
- Slow response

**Solutions:**

1. **Check for processing loops**
   ```bash
   docker compose logs conserver | tail -100
   ```

2. **Reduce workers**
   ```bash
   CONSERVER_WORKERS=2
   ```

### Disk Full

**Symptoms:**
- Write failures
- Service crashes

**Check:**

```bash
df -h
docker system df
```

**Solutions:**

1. **Clean Docker**
   ```bash
   docker system prune -f
   docker volume prune -f
   ```

2. **Clean old logs**
   ```bash
   docker compose logs --tail=0  # Truncate logs
   ```

## Getting Help

### Collect Diagnostics

```bash
# Create diagnostic bundle
mkdir -p /tmp/vcon-diag
docker compose ps > /tmp/vcon-diag/services.txt
docker compose logs --tail=1000 > /tmp/vcon-diag/logs.txt
docker stats --no-stream > /tmp/vcon-diag/stats.txt
cp .env /tmp/vcon-diag/env.txt.redacted
# Remove secrets from env file
sed -i 's/=.*/=REDACTED/' /tmp/vcon-diag/env.txt.redacted
tar -czf vcon-diagnostics.tar.gz /tmp/vcon-diag
```

### Report Issues

When reporting issues, include:

1. vCon Server version (`/api/version`)
2. Error messages from logs
3. Steps to reproduce
4. Configuration (redacted secrets)
5. Diagnostic bundle

Open issues at: [GitHub Issues](https://github.com/vcon-dev/vcon-server/issues)
