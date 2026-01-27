# Operations Guide

This section covers day-to-day operations, monitoring, troubleshooting, and maintenance of vCon Server.

## Operations Overview

| Topic | Description |
|-------|-------------|
| [API Reference](api-reference.md) | Complete API endpoint documentation |
| [Monitoring](monitoring.md) | Metrics, observability, and health checks |
| [Logging](logging.md) | Log configuration and analysis |
| [Troubleshooting](troubleshooting.md) | Common issues and solutions |
| [Dead Letter Queue](dead-letter-queue.md) | Managing failed processing |
| [Backup and Restore](backup-restore.md) | Data protection procedures |

## Quick Reference

### Health Check

```bash
curl http://localhost:8000/api/health
```

### Version Information

```bash
curl http://localhost:8000/api/version
```

### Service Status

=== "Docker"

    ```bash
    docker compose ps
    docker compose logs -f
    ```

=== "Kubernetes"

    ```bash
    kubectl get pods -n vcon-server
    kubectl logs -f deployment/worker -n vcon-server
    ```

=== "Systemd"

    ```bash
    systemctl status vcon-server
    journalctl -u vcon-server -f
    ```

## Common Operations

### Restart Services

=== "Docker"

    ```bash
    # Restart all
    docker compose restart
    
    # Restart specific service
    docker compose restart conserver
    ```

=== "Kubernetes"

    ```bash
    kubectl rollout restart deployment/worker -n vcon-server
    ```

### View Logs

=== "Docker"

    ```bash
    # All logs
    docker compose logs -f
    
    # Last 100 lines
    docker compose logs --tail=100 conserver
    
    # Filter by time
    docker compose logs --since="1h" conserver
    ```

=== "Kubernetes"

    ```bash
    kubectl logs -f deployment/worker -n vcon-server
    kubectl logs --tail=100 -l app=worker -n vcon-server
    ```

### Check Queue Status

```bash
# Get queue lengths
docker compose exec redis redis-cli LLEN default
docker compose exec redis redis-cli LLEN DLQ:default

# List all queues
docker compose exec redis redis-cli KEYS "*"
```

### Submit Test vCon

```bash
curl -X POST "http://localhost:8000/api/vcon?ingress_lists=default" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{
    "vcon": "0.0.1",
    "uuid": "test-'$(date +%s)'",
    "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "parties": [],
    "dialog": []
  }'
```

### View Configuration

```bash
curl http://localhost:8000/api/config \
  -H "x-conserver-api-token: $TOKEN" | jq .
```

## Operational Metrics

### Key Metrics to Monitor

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| Queue Depth | Items waiting in ingress queues | > 1000 |
| DLQ Depth | Items in dead letter queue | > 0 |
| Processing Latency | Time to process one vCon | > 30s |
| Error Rate | Percentage of failed processing | > 5% |
| Worker Count | Active worker processes | < expected |
| Memory Usage | Container/process memory | > 80% |
| CPU Usage | Container/process CPU | > 80% |

### Quick Health Assessment

```bash
#!/bin/bash
# health-check.sh

API_URL="http://localhost:8000/api"
TOKEN="your-token"

echo "=== vCon Server Health Check ==="

# API Health
echo -n "API Health: "
curl -s "$API_URL/health" | jq -r .status

# Version
echo -n "Version: "
curl -s "$API_URL/version" | jq -r .version

# Queue Status
echo "Queue Depths:"
for queue in default production test; do
  depth=$(docker compose exec -T redis redis-cli LLEN $queue 2>/dev/null || echo "N/A")
  echo "  $queue: $depth"
done

# DLQ Status
echo "DLQ Depths:"
for queue in default production test; do
  depth=$(docker compose exec -T redis redis-cli LLEN "DLQ:$queue" 2>/dev/null || echo "N/A")
  echo "  DLQ:$queue: $depth"
done

# Container Status
echo "Container Status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

## Maintenance Windows

### Planned Maintenance

1. **Announce maintenance** to users
2. **Stop ingress** (stop accepting new vCons)
3. **Drain queues** (wait for processing to complete)
4. **Perform maintenance**
5. **Verify health**
6. **Resume operations**

```bash
# Graceful shutdown (allows current processing to complete)
docker compose stop conserver

# Perform maintenance...

# Restart
docker compose start conserver

# Verify
curl http://localhost:8000/api/health
```

### Emergency Procedures

**Service Unresponsive:**

```bash
# Force restart
docker compose restart

# If still unresponsive
docker compose down
docker compose up -d
```

**Queue Backup:**

```bash
# Check queue depth
docker compose exec redis redis-cli LLEN default

# Scale workers
docker compose up -d --scale conserver=4
```

**DLQ Growing:**

```bash
# Check DLQ
curl "http://localhost:8000/api/dlq?ingress_list=default" \
  -H "x-conserver-api-token: $TOKEN"

# Fix issues, then reprocess
curl -X POST "http://localhost:8000/api/dlq/reprocess?ingress_list=default" \
  -H "x-conserver-api-token: $TOKEN"
```

## Capacity Planning

### Resource Requirements by Scale

| Scale | vCons/day | Workers | Memory | CPU |
|-------|-----------|---------|--------|-----|
| Small | < 1,000 | 1-2 | 2 GB | 2 cores |
| Medium | 1,000-10,000 | 4 | 4 GB | 4 cores |
| Large | 10,000-100,000 | 8 | 8 GB | 8 cores |
| Enterprise | > 100,000 | 16+ | 16+ GB | 16+ cores |

### Scaling Triggers

**Scale Up When:**

- Queue depth consistently > 100
- Processing latency > 10s
- CPU usage > 70%

**Scale Down When:**

- Queue depth consistently 0
- CPU usage < 30%
- Cost optimization needed

## Security Operations

### Regular Tasks

| Task | Frequency | Procedure |
|------|-----------|-----------|
| Rotate API tokens | Monthly | [Authentication Guide](../configuration/authentication.md) |
| Review access logs | Weekly | Check for unauthorized access |
| Update dependencies | Monthly | `poetry update && docker compose build` |
| Security patches | As released | Apply and test |
| Backup verification | Weekly | Test restore procedure |

### Audit Logging

Enable audit logging for compliance:

```bash
LOG_LEVEL=INFO
```

Review access patterns:

```bash
# Failed auth attempts
docker compose logs api | grep -i "403"

# Successful operations
docker compose logs api | grep "200"
```

## Next Steps

- [API Reference](api-reference.md) - Complete endpoint documentation
- [Monitoring](monitoring.md) - Set up observability
- [Troubleshooting](troubleshooting.md) - Solve common issues
