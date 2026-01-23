# Upgrading vCon Server

This guide covers upgrading vCon Server to newer versions safely.

## Before You Upgrade

### 1. Check Release Notes

Review the release notes for your target version:

- [GitHub Releases](https://github.com/vcon-dev/vcon-server/releases)
- Breaking changes
- New features
- Deprecations

### 2. Backup Your Data

=== "Docker"

    ```bash
    # Backup Redis data
    docker compose exec redis redis-cli BGSAVE
    docker cp vcon-server-redis-1:/data/dump.rdb ./backup/redis-dump.rdb
    
    # Backup configuration
    cp .env ./backup/.env.bak
    cp config.yml ./backup/config.yml.bak
    
    # Backup storage volumes
    docker compose exec postgres pg_dump -U vcon vcon_server > ./backup/postgres.sql
    ```

=== "Kubernetes"

    ```bash
    # Backup ConfigMap
    kubectl get configmap vcon-config -n vcon-server -o yaml > backup/configmap.yaml
    
    # Backup Secrets
    kubectl get secret vcon-secrets -n vcon-server -o yaml > backup/secrets.yaml
    
    # Backup Redis data
    kubectl exec -n vcon-server redis-0 -- redis-cli BGSAVE
    kubectl cp vcon-server/redis-0:/data/dump.rdb ./backup/redis-dump.rdb
    ```

### 3. Test in Staging

Always test upgrades in a staging environment first:

```bash
# Clone production config to staging
cp .env .env.staging
# Edit .env.staging with staging settings

# Run staging environment
docker compose -f docker-compose.staging.yml up -d
```

## Version Compatibility

### vCon Format Compatibility

| Server Version | vCon Format |
|---------------|-------------|
| 1.0.x | 0.0.1 |
| 1.1.x | 0.0.1 |

### Breaking Changes by Version

#### v1.0 to v1.1

**New Features:**

- Multi-worker support (`CONSERVER_WORKERS`)
- Parallel storage writes (`CONSERVER_PARALLEL_STORAGE`)
- Configurable start method (`CONSERVER_START_METHOD`)

**Breaking Changes:**

- None

**Configuration Changes:**

```bash
# New environment variables (optional)
CONSERVER_WORKERS=4              # Default: 1
CONSERVER_PARALLEL_STORAGE=true  # Default: true
CONSERVER_START_METHOD=fork      # Default: platform default
```

## Upgrade Procedures

### Docker Compose

#### Rolling Update (Zero Downtime)

```bash
# Pull latest code
git fetch origin
git checkout v1.1.0  # or desired version

# Pull new images
docker compose pull

# Rebuild if using local Dockerfile
docker compose build --no-cache

# Rolling restart (one at a time)
docker compose up -d --no-deps api
docker compose up -d --no-deps conserver
```

#### Full Restart

```bash
# Stop services
docker compose down

# Pull latest code
git pull origin main

# Rebuild and start
docker compose up -d --build
```

### Kubernetes

#### Rolling Update

```bash
# Update image tag in deployment
kubectl set image deployment/api \
  api=public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server:v1.1.0 \
  -n vcon-server

kubectl set image deployment/worker \
  worker=public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server:v1.1.0 \
  -n vcon-server

# Monitor rollout
kubectl rollout status deployment/api -n vcon-server
kubectl rollout status deployment/worker -n vcon-server
```

#### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/api -n vcon-server
kubectl rollout undo deployment/worker -n vcon-server

# Rollback to specific revision
kubectl rollout undo deployment/api --to-revision=2 -n vcon-server
```

### Manual Installation

```bash
# Stop services
pkill -f "python ./server/main.py"
pkill -f "uvicorn server.api"

# Backup current version
cp -r server server.bak

# Pull latest code
git fetch origin
git checkout v1.1.0

# Update dependencies
poetry install

# Start services
poetry run python ./server/main.py &
poetry run uvicorn server.api:app --host 0.0.0.0 --port 8000 &
```

## Post-Upgrade Steps

### 1. Verify Health

```bash
# Check API health
curl http://localhost:8000/api/health

# Check version
curl http://localhost:8000/api/version
```

### 2. Check Logs

```bash
# Docker
docker compose logs -f --tail=100

# Kubernetes
kubectl logs -f deployment/worker -n vcon-server
```

### 3. Verify Processing

Submit a test vCon and verify it processes correctly:

```bash
curl -X POST http://localhost:8000/api/vcon?ingress_lists=default \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{"vcon": "0.0.1", "uuid": "upgrade-test-001", ...}'
```

### 4. Update Configuration

Review and update configuration for new features:

```bash
# Check for new configuration options
diff example_config.yml config.yml

# Update .env for new environment variables
diff .env.example .env
```

## Rollback Procedures

### Docker Compose

```bash
# Stop current version
docker compose down

# Checkout previous version
git checkout v1.0.0

# Start previous version
docker compose up -d --build
```

### Restore from Backup

```bash
# Restore configuration
cp ./backup/.env.bak .env
cp ./backup/config.yml.bak config.yml

# Restore Redis data
docker compose stop redis
docker cp ./backup/redis-dump.rdb vcon-server-redis-1:/data/dump.rdb
docker compose start redis

# Restore PostgreSQL
docker compose exec -T postgres psql -U vcon vcon_server < ./backup/postgres.sql
```

## Database Migrations

Some upgrades may include database schema changes.

### Check for Migrations

```bash
# View migration status (if using Alembic)
poetry run alembic current

# Run pending migrations
poetry run alembic upgrade head
```

### Manual Schema Updates

If migrations aren't automated, apply changes manually:

```sql
-- Example: Add new column
ALTER TABLE vcons ADD COLUMN processed_at TIMESTAMP;
```

## Troubleshooting Upgrades

### Service Won't Start

Check for configuration errors:

```bash
# Validate configuration
poetry run python -c "from server.config import get_config; print(get_config())"

# Check for missing environment variables
poetry run python -c "from server import settings; print(dir(settings))"
```

### Processing Stopped

Check worker status:

```bash
# Docker
docker compose logs conserver --tail=100

# Check Redis queues
docker compose exec redis redis-cli LLEN default
```

### API Errors

Check for breaking API changes:

```bash
# View API docs
curl http://localhost:8000/api/docs

# Check for deprecation warnings in logs
docker compose logs api | grep -i deprecat
```

## Upgrade Checklist

- [ ] Review release notes for target version
- [ ] Backup all data (Redis, databases, configuration)
- [ ] Test upgrade in staging environment
- [ ] Schedule maintenance window (if needed)
- [ ] Notify users of planned downtime (if any)
- [ ] Perform upgrade
- [ ] Verify health endpoints
- [ ] Check logs for errors
- [ ] Test processing pipeline
- [ ] Update monitoring/alerting thresholds
- [ ] Document any issues encountered

## Getting Help

If you encounter issues during upgrade:

1. Check [GitHub Issues](https://github.com/vcon-dev/vcon-server/issues)
2. Review [Troubleshooting Guide](../operations/troubleshooting.md)
3. Open a new issue with:
   - Current version
   - Target version
   - Error messages
   - Configuration (redacted)
