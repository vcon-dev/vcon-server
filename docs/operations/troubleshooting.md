# Fix common problems

This page lists common issues and their solutions. In the examples, `default` stands for your ingress list.

## Run the diagnostics

```bash
# API health. This shows only that the API process answers.
curl -s http://localhost:8000/api/health | jq .

# Service status
docker compose ps

# Recent logs
docker compose logs --tail=50 conserver

# Queue status
curl -s "http://localhost:8000/api/stats/queue?list_name=default"
curl -s "http://localhost:8000/api/stats/queue?list_name=DLQ:default"
```

### Script the diagnostics

```bash
#!/bin/bash
# diagnose.sh

echo "1. Service status:"
docker compose ps
echo

echo "2. API health:"
curl -s http://localhost:8000/api/health 2>/dev/null || echo "API unreachable"
echo

echo "3. Redis:"
docker compose exec -T redis redis-cli ping 2>/dev/null || echo "Redis unreachable"
echo

echo "4. Queue depths:"
echo "   default: $(docker compose exec -T redis redis-cli LLEN default 2>/dev/null || echo 'N/A')"
echo "   DLQ:default: $(docker compose exec -T redis redis-cli LLEN DLQ:default 2>/dev/null || echo 'N/A')"
echo

echo "5. Recent errors:"
docker compose logs --tail=200 conserver 2>&1 | grep -i error || echo "   No recent errors"
echo

echo "6. Resource usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "   Cannot get stats"
```

## Fix the startup problems

### Services fail to start

**Symptoms:** `docker compose up` fails, or containers exit immediately.

```bash
docker compose ps -a
docker compose logs
```

**Common causes:**

1. **Port already in use.** Find what holds the port, then set `CONSERVER_EXTERNAL_PORT` in `.env` to publish the API elsewhere.

    ```bash
    lsof -i :8000
    ```

2. **Missing environment variables.** See the [environment reference](../reference/environment.md).

    ```bash
    ls -la .env
    grep REDIS_URL .env
    grep CONSERVER_API_TOKEN .env
    ```

3. **Bad logging path.** `.env.example` sets `LOGGING_CONFIG_FILE=server/logging_dev.conf`, and that path does not exist. Remove the line or use `/app/common/logging_dev.conf`. See [Choose the log format](logging.md#choose-the-log-format).

4. **Invalid configuration.**

    ```bash
    python -c "import yaml; yaml.safe_load(open('config.yml'))"
    ```

5. **Network not created.** The `conserver` network is external.

    ```bash
    docker network create conserver
    ```

### Redis connection fails

**Symptoms:** `Connection refused` errors, or workers not processing.

```bash
docker compose ps redis
docker compose exec redis redis-cli ping
```

**Solutions:**

1. **Redis not started.**

    ```bash
    docker compose up -d redis
    ```

2. **Wrong URL.** The host must match the Compose service name.

    ```bash
    REDIS_URL=redis://redis:6379
    ```

3. **Network problem.**

    ```bash
    docker compose down
    docker network rm conserver
    docker network create conserver
    docker compose up -d
    ```

4. **Data from an older Redis image.** Persistence files from an older image may not load. See the [Redis migration](../installation/redis-migration.md).

## Fix the processing problems

### vCons wait in the queue

**Symptoms:** queue depth rises and the logs show no processing.

```bash
docker compose ps conserver
docker compose logs --tail=50 conserver
curl -s "http://localhost:8000/api/stats/queue?list_name=default"
```

**Solutions:**

1. **No chain reads the list.** The API accepts any list name. The name you submit to must appear under a chain's `ingress_lists`:

    ```yaml
    chains:
      my_chain:
        ingress_lists:
          - default
    ```

2. **No ingress lists at all.** The worker logs `No ingress lists configured, retrying in 15s`. Check `CONSERVER_CONFIG_FILE`, which defaults to `./example_config.yml`.

3. **Workers crashed.**

    ```bash
    docker compose restart conserver
    ```

A chain's `enabled` key does not help here, because the worker does not read it. A chain runs if it lists an ingress list. To stop a chain, remove its `ingress_lists`.

### vCons finish but never reach storage

**Symptoms:** the log shows `halted chain processing`, and no egress or storage follows.

A link returned a falsy value, which stops the chain with no error and no DLQ entry. Filter links do this on purpose. Check the link's [reference page](../reference/links/index.md).

### Processing runs slowly

**Symptoms:** high queue depth and long processing times.

```bash
watch -n 5 'docker compose exec -T redis redis-cli LLEN default'
docker compose logs -f conserver
```

**Solutions:**

1. **Add worker capacity.** Set the values in `.env`, then recreate the service, since `docker compose restart` keeps the old environment. See [Configure the workers](../configuration/workers.md).

    ```bash
    CONSERVER_WORKERS=4
    CONSERVER_VCON_CONCURRENCY=4
    ```

    ```bash
    docker compose up -d conserver
    ```

2. **Check parallel storage.** `CONSERVER_PARALLEL_STORAGE` is on by default, and helps only with two or more backends.

3. **Check external services.** `conserver.link.execution_time` shows which link takes the time. See the [metrics reference](../reference/metrics.md).

### The DLQ grows

**Symptoms:** items appear in a DLQ.

```bash
curl "http://localhost:8000/api/dlq?ingress_list=default" \
  -H "x-conserver-api-token: $TOKEN"

docker compose logs conserver | grep "Moving to DLQ"
```

Fix the cause, then replay. See [Manage dead letter queues](dead-letter-queue.md).

## Fix the API problems

### The API returns 403

**Symptoms:** the response body is `{"detail":"Invalid API Key"}`, or `Invalid API Key for ingress list '<name>'` on external ingress.

```bash
echo $CONSERVER_API_TOKEN
curl -v -H "x-conserver-api-token: $TOKEN" http://localhost:8000/api/vcon
```

**Solutions:**

1. **Set the token.** Set it in `.env`, then run `docker compose up -d api`. The API reads tokens only at startup.

2. **Check the header name.** The default is `x-conserver-api-token`. `CONSERVER_HEADER_NAME` changes it.

3. **Check `ingress_auth` for external ingress.** The key must match the list you submit to.

    ```yaml
    ingress_auth:
      customer_data: "customer-api-key-12345"
    ```

See [Authentication](../configuration/authentication.md).

### The API returns 404

**Symptoms:** vCon not found, or endpoint not found.

**Solutions:**

1. **Check the UUID in Redis.**

    ```bash
    docker compose exec redis redis-cli EXISTS vcon:<uuid>
    ```

2. **Fetch it.** A GET looks in the configured storages when Redis has no copy.

    ```bash
    curl http://localhost:8000/api/vcon/<uuid> -H "x-conserver-api-token: $TOKEN"
    ```

3. **Check the expiry.** A vCon that never reached a storage backend is gone once its Redis TTL ends.

4. **Check the route.** See the [generated route list](../reference/api-routes.md).

### The API returns 422

The vCon body failed validation. A common cause is a `uuid` that is not a valid UUID. See the [body rules](../reference/api.md#meet-the-vcon-body-rules).

### The API returns 500

```bash
docker compose logs api | grep -i error
```

**Solutions:**

1. **Check the configuration.**

    ```bash
    curl http://localhost:8000/api/config -H "x-conserver-api-token: $TOKEN"
    ```

2. **Restart the API.**

    ```bash
    docker compose restart api
    ```

## Fix the storage problems

### Storage writes fail

**Symptoms:** chains finish but data does not persist. The log shows `Moving to storage DLQ`.

```bash
docker compose logs conserver | grep "storage DLQ"

# Test a backend. Use a name from your storages config.
docker compose exec conserver python -c "
from storage.base import Storage
s = Storage('postgres')
print(s.get('<uuid>'))
"

# Test the network path
docker compose exec conserver python -c "
import socket
socket.create_connection(('postgres', 5432), 3)
print('ok')
"
```

**Solutions:**

1. **Check the credentials.** See the backend's page in the [adapter reference](../reference/storage-adapters/index.md).

2. **Check the backend service.**

    ```bash
    docker compose ps postgres
    ```

3. **Replay after the fix.** See [Recover failed storage writes](storage-recovery.md).

### Storage replay returns 409

Another replay is running, or a crash left the lock behind. See [Recover the replay lock](storage-recovery.md#recover-the-replay-lock).

### Storage replay stops early

The batch stops at the first failed write. If the count stays at 0 with a healthy backend, an entry is blocking the queue. See [Clear a blocked entry](storage-recovery.md#clear-a-blocked-entry).

### A stored vCon does not appear in the API

**Symptoms:** a vCon is in storage but missing from list or search results.

1. **Fetch it by UUID.** A GET finds it in storage and caches it back in Redis. It also adds a bare id to the sorted set, which can make `GET /vcon` return 500 for any page that holds it, as [the lifecycle page](../concepts/vcon-lifecycle.md#read-a-stored-vcon) warns. To clear that, remove the bare member with `ZREM vcons <uuid>`. The fetch does not restore the party index.

    ```bash
    curl http://localhost:8000/api/vcon/<uuid> -H "x-conserver-api-token: $TOKEN"
    ```

2. **Check the fallback.** `VCON_STORAGE_FALLBACK_ENABLED=false` turns the worker's read fallback off.

3. **Rebuild the index for what Redis holds.** This route walks `vcon:*` keys in Redis only, so it cannot find a vCon that exists only in storage. A vCon that step 1 cached is in Redis, so this adds its prefixed key back to the list. See [the route](../reference/api.md#rebuild-the-search-index).

    ```bash
    curl http://localhost:8000/api/index_vcons -H "x-conserver-api-token: $TOKEN"
    ```

## Fix the resource problems

### Memory use runs high

**Symptoms:** OOM kills or slow performance.

```bash
docker stats
```

**Solutions:**

1. **Reduce the workers.** Set `CONSERVER_WORKERS=2` in `.env`, then run `docker compose up -d conserver`.

2. **Review the start method.** `CONSERVER_START_METHOD` affects memory, and `fork` has a shutdown caveat. See [Configure the workers](../configuration/workers.md).

3. **Add memory limits.**

    ```yaml
    services:
      conserver:
        deploy:
          resources:
            limits:
              memory: 2G
    ```

4. **Check Redis.** The Compose service has `mem_limit: 1gb`. A large DLQ keeps bodies in Redis for days.

### CPU use runs high

**Symptoms:** CPU at 100% and slow responses.

1. **Look for repeated failures.**

    ```bash
    docker compose logs --tail=100 conserver
    ```

2. **Reduce the workers.** Set `CONSERVER_WORKERS=2` in `.env`, then run `docker compose up -d conserver`.

### The disk fills up

**Symptoms:** write failures or service crashes.

```bash
df -h
docker system df
```

**Solutions:**

1. **Clean Docker.**

    ```bash
    docker system prune -f
    ```

    !!! warning "Keep your volumes"
        Do not run `docker volume prune` as routine cleanup. A stopped stack's `redis_data` and `postgres_data` volumes count as unused, and pruning can remove them.

2. **Limit the container logs.** Compose sets no limit by default. See [Limit the log size](logging.md#limit-the-log-size).

## Get help

### Collect the diagnostics

```bash
mkdir -p /tmp/vcon-diag
docker compose ps > /tmp/vcon-diag/services.txt
docker compose logs --tail=1000 > /tmp/vcon-diag/logs.txt
docker stats --no-stream > /tmp/vcon-diag/stats.txt
sed 's/=.*/=REDACTED/' .env > /tmp/vcon-diag/env.txt.redacted
tar -czf vcon-diagnostics.tar.gz -C /tmp vcon-diag
```

Read the logs before you share them, since they can hold phone numbers and other conversation details.

### Report the issue

Include:

1. The version from `/api/version`
2. Error messages from the logs
3. Steps to reproduce
4. The configuration, with secrets removed
5. The diagnostic bundle

Open issues at [GitHub Issues](https://github.com/vcon-dev/vcon-server/issues).
