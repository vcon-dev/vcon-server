# VCONIC Conserver — Administration Guide

**Document ID:** VCONIC-CSV-ADM-001  
**Product:** VCONIC Conserver  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## 1. Day-to-Day Operations

### 1.1 Service Management

**Check service status:**

```bash
docker compose ps
```

**Start all services:**

```bash
docker compose up -d
```

**Stop all services:**

```bash
docker compose down
```

**Restart a specific service:**

```bash
docker compose restart conserver   # Restart worker(s)
docker compose restart api         # Restart API
docker compose restart redis       # Restart Redis
```

**Scale workers:**

```bash
# Scale to 4 worker containers
docker compose up --scale conserver=4 -d
```

### 1.2 Health Monitoring

**API health check:**

```bash
curl http://localhost:8000/health
```

**Queue depth monitoring:**

```bash
# Check the default ingress queue
curl "http://localhost:8000/stats/queue?list_name=default"

# Check all known queues (via Redis CLI)
docker compose exec redis redis-cli KEYS "*"
```

**Quick status dashboard (run periodically):**

```bash
echo "=== Service Status ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}"

echo ""
echo "=== API Health ==="
curl -s http://localhost:8000/health | python3 -m json.tool

echo ""
echo "=== Queue Depths ==="
for queue in default; do
  depth=$(curl -s "http://localhost:8000/stats/queue?list_name=$queue" | python3 -c "import sys,json; print(json.load(sys.stdin).get('depth',0))")
  echo "  $queue: $depth"
done
```

### 1.3 Log Viewing

**View real-time logs:**

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f conserver
docker compose logs -f api

# Last N lines
docker compose logs --tail 100 conserver
```

**Filter for errors:**

```bash
docker compose logs conserver 2>&1 | grep -i error
docker compose logs api 2>&1 | grep -i error
```

**Log locations inside containers:**

| Service | Log Output |
|---------|-----------|
| api | stdout (captured by Docker) |
| conserver | stdout (captured by Docker) |
| redis | stdout + `/data/redis.log` |
| postgres | stdout + `/var/log/postgresql/` |

---

## 2. Queue Management

### 2.1 Understanding Queues

The Conserver uses three types of Redis queues:

| Queue Type | Naming | Purpose |
|-----------|--------|---------|
| Ingress | `<list_name>` (e.g., `default`) | New vCons waiting to be processed |
| Egress | `<list_name>` (e.g., `processed`) | Processed vCons available for downstream |
| Dead Letter (DLQ) | `DLQ:<ingress_list>` (e.g., `DLQ:default`) | Failed vCons for investigation |

### 2.2 Monitoring Queue Depth

```bash
# Via API
curl "http://localhost:8000/stats/queue?list_name=default"

# Via Redis CLI
docker compose exec redis redis-cli LLEN default
docker compose exec redis redis-cli LLEN "DLQ:default"
```

**Alert thresholds:**

| Queue Depth | Status | Action |
|-------------|--------|--------|
| 0–100 | Normal | No action needed |
| 100–1,000 | Elevated | Monitor — may need more workers |
| > 1,000 | Critical | Scale workers or investigate processing bottleneck |

### 2.3 Dead Letter Queue Management

**List DLQ contents:**

```bash
curl http://localhost:8000/dlq/default \
  -H "x-conserver-api-token: <token>"
```

**Reprocess a failed vCon:**

```bash
curl -X POST "http://localhost:8000/dlq/default/reprocess/<uuid>" \
  -H "x-conserver-api-token: <token>"
```

**Check DLQ depth:**

```bash
docker compose exec redis redis-cli LLEN "DLQ:default"
```

> **NOTE:** DLQ entries expire after the `VCON_DLQ_EXPIRY` period (default: 7 days). Investigate and reprocess or purge DLQ items before they expire.

---

## 3. Backup and Restore

### 3.1 What to Back Up

| Component | Data | Priority |
|-----------|------|----------|
| PostgreSQL | All vCon data, metadata, parties, analysis | Critical |
| Redis | Queue state, cached vCons | Important (can be rebuilt) |
| config.yml | Processing chain configuration | Critical |
| .env | Environment and credentials | Critical |
| docker-compose.yml | Service definitions | Important |

### 3.2 PostgreSQL Backup

**Full database dump:**

```bash
# Bundled PostgreSQL
docker compose exec postgres pg_dump -U postgres conserver > backup_$(date +%Y%m%d_%H%M%S).sql

# External PostgreSQL
pg_dump -h <host> -U <user> -d conserver > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Compressed backup:**

```bash
docker compose exec postgres pg_dump -U postgres -Fc conserver > backup_$(date +%Y%m%d).dump
```

**Schedule automated backups (crontab):**

```bash
# Daily at 2 AM
0 2 * * * cd /opt/vcon-server && docker compose exec -T postgres pg_dump -U postgres -Fc conserver > /backups/conserver_$(date +\%Y\%m\%d).dump 2>&1
```

### 3.3 PostgreSQL Restore

```bash
# From SQL dump
psql -h <host> -U <user> -d conserver < backup.sql

# From compressed dump
pg_restore -h <host> -U <user> -d conserver backup.dump
```

### 3.4 Configuration Backup

```bash
# Back up configuration files
cp /opt/vcon-server/.env /backups/conserver_env_$(date +%Y%m%d)
cp /opt/vcon-server/config.yml /backups/conserver_config_$(date +%Y%m%d).yml
cp /opt/vcon-server/docker-compose.yml /backups/conserver_compose_$(date +%Y%m%d).yml
```

### 3.5 Redis Backup

Redis data is transient (cache and queues) and can generally be rebuilt. If you need to preserve queue state:

```bash
# Trigger Redis snapshot
docker compose exec redis redis-cli BGSAVE

# Copy the dump file
docker cp $(docker compose ps -q redis):/data/dump.rdb /backups/redis_$(date +%Y%m%d).rdb
```

---

## 4. Monitoring and Alerting

### 4.1 Key Metrics to Monitor

| Metric | How to Check | Warning Threshold |
|--------|-------------|------------------|
| API health | `GET /health` | Non-200 response |
| Queue depth | `GET /stats/queue?list_name=<name>` | > 1,000 |
| DLQ depth | `redis-cli LLEN DLQ:<name>` | > 0 (investigate all DLQ items) |
| Container status | `docker compose ps` | Any service not "Up" |
| Disk usage | `df -h` | > 80% |
| Memory usage | `docker stats --no-stream` | > 85% of limit |
| CPU usage | `docker stats --no-stream` | Sustained > 90% |

### 4.2 Redis Insight

Redis Insight is available on port 8001 (configurable via `REDIS_EXTERNAL_PORT`):

```
http://localhost:8001
```

Use it to:
- Browse keys and queues
- Monitor memory usage
- View slow queries
- Inspect vCon JSON objects in the cache

### 4.3 OpenTelemetry Monitoring

If OpenTelemetry is configured, the following spans are reported:

| Span Name | Description |
|-----------|-------------|
| `conserver.main_loop` | Full processing cycle for one vCon |
| `link.<name>` | Individual link execution time |
| `storage.<name>` | Storage backend write time |
| `api.submit_vcon` | API vCon submission handler |

---

## 5. Scheduled Maintenance

### 5.1 Log Rotation

If using Docker's json-file log driver:

```yaml
# Add to docker-compose.yml for each service
logging:
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "5"
```

### 5.2 Database Maintenance

**Vacuum and analyze (weekly):**

```bash
docker compose exec postgres psql -U postgres -d conserver -c "VACUUM ANALYZE;"
```

**Check database size:**

```bash
docker compose exec postgres psql -U postgres -d conserver -c "
  SELECT pg_size_pretty(pg_database_size('conserver')) as db_size;
"
```

**Check table sizes:**

```bash
docker compose exec postgres psql -U postgres -d conserver -c "
  SELECT relname as table, pg_size_pretty(pg_total_relation_size(relid)) as size
  FROM pg_catalog.pg_statio_user_tables
  ORDER BY pg_total_relation_size(relid) DESC;
"
```

### 5.3 Redis Memory Management

```bash
# Check memory usage
docker compose exec redis redis-cli INFO memory | grep used_memory_human

# Check key count
docker compose exec redis redis-cli DBSIZE
```

### 5.4 Docker Maintenance

```bash
# Remove unused images (safe to run periodically)
docker image prune -f

# Remove unused volumes (WARNING: check what's unused first)
docker volume ls -f dangling=true
```

---

## 6. Scaling Operations

### 6.1 Horizontal Scaling (More Workers)

```bash
# Scale to 8 worker containers
docker compose up --scale conserver=8 -d

# Verify
docker compose ps
```

### 6.2 Vertical Scaling (Larger Workers)

Edit `docker-compose.yml` to increase resource limits:

```yaml
conserver:
  deploy:
    resources:
      limits:
        cpus: '4.0'
        memory: 8G
```

### 6.3 Scaling Guidelines

| Volume | Workers | Host Spec |
|--------|---------|-----------|
| < 1,000/day | 1–2 | 4 CPU, 16 GB RAM |
| 1,000–5,000/day | 2–4 | 8 CPU, 32 GB RAM |
| 5,000–20,000/day | 4–8 | 16 CPU, 64 GB RAM |
| > 20,000/day | 8+ across multiple hosts | Scale out |

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
