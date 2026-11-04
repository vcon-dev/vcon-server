# Run the server

This section covers day-to-day operation of vCon Server: checking it, recovering from failure and planning capacity.

| Topic | Description |
|-------|-------------|
| [Monitoring](monitoring.md) | Health checks, OpenTelemetry export and alerts |
| [Logging](logging.md) | Log configuration and analysis |
| [Troubleshooting](troubleshooting.md) | Common issues and solutions |
| [Dead letter queues](dead-letter-queue.md) | Failed chains and how to replay them |
| [Storage recovery](storage-recovery.md) | Failed backend writes and how to replay them |
| [Backup and restore](backup-restore.md) | Data protection procedures |
| [API reference](../reference/api.md) | Every REST endpoint |

In the examples, `default` stands for your own ingress list and `$TOKEN` for your API token. The API listens on port 8000. See [API reference](../reference/api.md#set-the-base-url) for the base URL.

## Check the service status

```bash
# Health and version need no token
curl http://localhost:8000/api/health
curl http://localhost:8000/api/version
```

`/health` confirms only that the API process answers. It does not check Redis or the workers. See [Monitoring](monitoring.md#check-the-server-health).

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

## Run the common tasks

### Restart the services

=== "Docker"

    ```bash
    # Restart all
    docker compose restart

    # Restart one service
    docker compose restart conserver

    # Recreate a service after changing .env
    docker compose up -d conserver
    ```

=== "Kubernetes"

    ```bash
    kubectl rollout restart deployment/worker -n vcon-server
    ```

`docker compose restart` keeps the old environment. After editing `.env`, use `docker compose up -d`.

### Read the logs

=== "Docker"

    ```bash
    docker compose logs -f
    docker compose logs --tail=100 conserver
    docker compose logs --since="1h" conserver
    ```

=== "Kubernetes"

    ```bash
    kubectl logs -f deployment/worker -n vcon-server
    kubectl logs --tail=100 -l app=worker -n vcon-server
    ```

### Check the queue status

```bash
# Queue depth through the API, no token needed
curl "http://localhost:8000/api/stats/queue?list_name=default"
curl "http://localhost:8000/api/stats/queue?list_name=DLQ:default"

# Queue depth in Redis
docker compose exec redis redis-cli LLEN default

# List every dead letter queue, without blocking Redis as KEYS would
docker compose exec redis redis-cli --scan --pattern 'DLQ:*'
```

### Submit a test vCon

The `uuid` must be a valid UUID, or the API returns 422.

```bash
curl -X POST "http://localhost:8000/api/vcon?ingress_lists=default" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{
    "vcon": "0.4.0",
    "uuid": "'$(uuidgen | tr 'A-Z' 'a-z')'",
    "created_at": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "parties": [{"tel": "+15551234567"}],
    "dialog": []
  }'
```

The API accepts any list name, even one no chain reads. An id pushed to such a list waits there and nothing processes it.

### Read the configuration

```bash
curl http://localhost:8000/api/config \
  -H "x-conserver-api-token: $TOKEN" | jq .
```

## Watch the key signals

Publish metrics through OpenTelemetry, then watch these signals. [Monitoring](monitoring.md#watch-the-key-signals) maps each one to a metric, and the [metrics reference](../reference/metrics.md) lists every name.

- Ingress queue depth
- Ingress and storage DLQ depth
- Chain processing time
- Link and storage errors
- Redis memory, and container CPU and memory

Set thresholds from your own baseline, since load depends on the chains you run.

### Script a quick health assessment

```bash
#!/bin/bash
# health-check.sh

API_URL="http://localhost:8000/api"
QUEUES="default"

echo -n "API health: "
curl -s "$API_URL/health" | jq -r .status

echo -n "Version: "
curl -s "$API_URL/version" | jq -r .version

for queue in $QUEUES; do
  for list in "$queue" "DLQ:$queue"; do
    echo -n "$list: "
    curl -s "$API_URL/stats/queue?list_name=$list" | jq -r .depth
  done
done

echo -n "Redis: "
docker compose exec -T redis redis-cli ping

docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

## Plan maintenance

No switch stops ingress on the server, so stop your producers first. Then drain the queues before stopping the workers.

1. Announce the maintenance to users.
2. Stop the systems that submit vCons.
3. Wait until the ingress lists reach 0 and `conserver.vcons.inflight` falls to 0.
4. Stop the workers and carry out the maintenance.
5. Start the workers and verify health.
6. Resume the producers.

```bash
docker compose stop conserver

# Perform the maintenance

docker compose start conserver
curl http://localhost:8000/api/health
```

!!! warning "Shutdown has a short grace period"
    A worker finishes the vCons it holds before it exits, but `docker-compose.yml` sets `stop_grace_period: 5s`. After that Docker kills the process. A popped id lives only in memory, so a vCon still running at that moment is lost from the queue. Drain first, or raise the grace period above your longest chain.

## Respond to an emergency

**Service unresponsive:**

```bash
docker compose restart

# If it still does not respond
docker compose down
docker compose up -d
```

**Queue backing up:**

```bash
curl "http://localhost:8000/api/stats/queue?list_name=default"

# Add worker containers
docker compose up -d --scale conserver=4
```

[Configure the workers](../configuration/workers.md) covers the other ways to add capacity.

**DLQ growing:** find the cause, then replay. See [Manage dead letter queues](dead-letter-queue.md).

**Storage DLQ growing:** fix the backend, then replay. See [Recover failed storage writes](storage-recovery.md).

## Plan the capacity

Treat these figures as starting points, not measurements. Throughput depends on your chains, and a chain that calls external transcription or analysis services behaves very differently from one that only tags and stores. Load test with your own chains.

<!-- TODO(verify): the repo holds no measured figures behind this table. docs/getting-started/requirements.md dropped its sizing tables for that reason. Replace these rows if a load test produces numbers. -->

| Scale | vCons/day | Workers | Memory | CPU |
|-------|-----------|---------|--------|-----|
| Small | < 1,000 | 1-2 | 2 GB | 2 cores |
| Medium | 1,000-10,000 | 4 | 4 GB | 4 cores |
| Large | 10,000-100,000 | 8 | 8 GB | 8 cores |
| Very large | > 100,000 | 16+ | 16+ GB | 16+ cores |

Scale up when the queue depth stays high, chain processing time climbs, or CPU stays high. Scale down when the queue stays empty and CPU stays low. Maximum parallel vCons per host is `CONSERVER_WORKERS` times `CONSERVER_VCON_CONCURRENCY`. See [Configure the workers](../configuration/workers.md).

The `redis` service in `docker-compose.yml` has `mem_limit: 1gb`. Bodies held for a DLQ stay in Redis for days, so raise the limit if a queue may grow large.

## Maintain the security

| Task | Frequency | Procedure |
|------|-----------|-----------|
| Rotate API tokens | Monthly | [Authentication](../configuration/authentication.md). The API reads its tokens at startup, so restart it |
| Review access logs | Weekly | See below |
| Update dependencies | Monthly | `uv lock --upgrade && docker compose build` |
| Apply security patches | As released | Apply and test |
| Verify backups | Weekly | [Test a restore](backup-restore.md#test-the-restores) |

The server has no dedicated audit log. To review access, search the API process output:

```bash
# Rejected requests
docker compose logs api | grep '" 403'

# Rejected keys on external ingress
docker compose logs api | grep "Invalid API key for ingress list"
```

## Read the next pages

- [Monitoring](monitoring.md) sets up observability
- [Troubleshooting](troubleshooting.md) solves common issues
- [API reference](../reference/api.md) documents every endpoint
