# Back up and restore data

This page covers what to back up and how to restore it, using the services in `docker-compose.yml`.

## Decide what to back up

| Component | Holds | Priority | Method |
|-----------|-------|----------|--------|
| Configuration | `.env`, `config.yml`, `docker-compose.yml` | Critical | File copy on each change |
| Storage backends | Your durable vCons | High | The backend's own tools |
| Redis | Queues, DLQs, search indexes and vCon bodies still inside their TTL | High | Archive of the data directory |

Redis is a working store. A vCon body stays there for a limited time, so the storage backends named in your chains hold the long-term copy. A vCon in a queue or a DLQ may exist only in Redis, which is why Redis still needs a backup.

Backups hold conversation data, and `.env` holds secrets. [Encrypt them](#protect-the-backups).

## Back up the configuration

```bash
#!/bin/bash
# backup-config.sh
BACKUP_DIR="./backups/config"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

cp .env "$BACKUP_DIR/.env.$DATE"
cp config.yml "$BACKUP_DIR/config.yml.$DATE"
cp docker-compose.yml "$BACKUP_DIR/docker-compose.yml.$DATE"

# Keep the last 30 days
find "$BACKUP_DIR" -type f -mtime +30 -delete
```

To restore, copy the files back and run `docker compose up -d`. `POST /config` also rewrites the config file, so take a copy after any change made that way.

## Back up Redis

The `redis` service runs with `--appendonly yes`, so its data lives in `/data/appendonlydir/` on the `redis_data` volume, beside a `dump.rdb` snapshot. Back up the whole directory.

!!! warning "A dump.rdb alone does not restore this service"
    With `appendonly yes`, Redis loads the AOF files at startup and ignores `dump.rdb`. Copying a dump into place leaves the old data in Redis. If the AOF directory is missing too, Redis starts empty.

```bash
# Compact the AOF files
docker compose exec -T redis redis-cli BGREWRITEAOF

# Wait until this prints aof_rewrite_in_progress:0
docker compose exec -T redis redis-cli INFO persistence | grep aof_rewrite_in_progress

# Archive the data directory
docker compose exec -T redis tar -czf - -C /data . > ./backups/redis-data.$(date +%Y%m%d).tar.gz
```

### Restore Redis

```bash
# Stop everything that uses Redis, then Redis itself
docker compose stop conserver api redis

# Replace the data directory
docker compose run --rm --no-deps -T -v "$PWD/backups:/backup:ro" --entrypoint sh redis \
  -c 'rm -rf /data/* && tar -xzf /backup/redis-data.20260115.tar.gz -C /data'

# Start Redis and check it
docker compose start redis
docker compose exec -T redis redis-cli DBSIZE

# List any replay lock captured in the backup
docker compose exec -T redis redis-cli --scan --pattern 'DLQ:storage:*:replay-lock'
# After confirming no replay can be running, delete each one: redis-cli DEL <key>

docker compose start conserver api
```

These commands were tested on the `redis:7.4-alpine` image with the same server flags as `docker-compose.yml`.

A restore brings back the queues as they stood at backup time. vCons that finished after the backup may run through their chains again, and TTLs carry on from their stored expiry times. A replay lock in the archive blocks that backend's replay until you delete it. See [Recover the replay lock](storage-recovery.md#recover-the-replay-lock).

## Back up PostgreSQL

Use the user and database from your `postgres` storage options. The adapter defaults to database `vcon_db`, and the Compose `postgres` service creates user `postgres` and database `postgres`. See the [PostgreSQL adapter reference](../reference/storage-adapters/postgres.md).

```bash
PG_USER=postgres
PG_DB=vcon_db

docker compose exec -T postgres pg_dump -U "$PG_USER" "$PG_DB" | gzip > ./backups/postgres-$(date +%Y%m%d).sql.gz
```

### Restore PostgreSQL

Stop the workers and the API first, so nothing holds a connection.

```bash
docker compose stop conserver api

docker compose exec -T postgres psql -U "$PG_USER" -d template1 -c "DROP DATABASE IF EXISTS $PG_DB;"
docker compose exec -T postgres psql -U "$PG_USER" -d template1 -c "CREATE DATABASE $PG_DB;"

gunzip -c ./backups/postgres-20260115.sql.gz | docker compose exec -T postgres psql -U "$PG_USER" "$PG_DB"

docker compose start conserver api
```

## Back up MongoDB

`docker-compose.yml` has no MongoDB service, so run these where the tools can reach your server. The adapter defaults to database `conserver`. See the [MongoDB adapter reference](../reference/storage-adapters/mongo.md).

```bash
mongodump --uri "$MONGO_URL" --db conserver --out ./backups/mongo-$(date +%Y%m%d)
```

### Restore MongoDB

```bash
mongorestore --uri "$MONGO_URL" --db conserver ./backups/mongo-20260115/conserver
```

## Back up S3

```bash
# Copy to another bucket
aws s3 sync s3://vcon-bucket s3://vcon-backup-bucket

# Copy to local disk
aws s3 sync s3://vcon-bucket ./backups/s3-$(date +%Y%m%d)
```

For disaster recovery, configure bucket replication in AWS.

## Back up Elasticsearch

A filesystem snapshot repository needs `path.repo` set on the Elasticsearch node, and the Compose service does not set it. That service also has security on, so pass credentials. Its values are for development only.

```bash
# Create the repository
curl -u "elastic:$ELASTIC_PASSWORD" -X PUT "localhost:9200/_snapshot/backup" \
  -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/backups"
  }
}'

# Create a snapshot
curl -u "elastic:$ELASTIC_PASSWORD" -X PUT "localhost:9200/_snapshot/backup/snapshot_$(date +%Y%m%d)"
```

### Restore a snapshot

```bash
# List the snapshots
curl -u "elastic:$ELASTIC_PASSWORD" "localhost:9200/_snapshot/backup/_all"

# Restore one
curl -u "elastic:$ELASTIC_PASSWORD" -X POST "localhost:9200/_snapshot/backup/snapshot_20260115/_restore"
```

## Back up the other backends

Use each system's own tools. The [storage adapter reference](../reference/storage-adapters/index.md) shows where each adapter writes.

## Script a full backup

This script covers the configuration, Redis and a Compose PostgreSQL. Add your other backends.

```bash
#!/bin/bash
# full-backup.sh

set -e

BACKUP_BASE="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE/$DATE"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-vcon_db}"

mkdir -p "$BACKUP_DIR"

echo "Backing up configuration..."
cp .env config.yml docker-compose.yml "$BACKUP_DIR/"

echo "Backing up Redis..."
docker compose exec -T redis redis-cli BGREWRITEAOF
until docker compose exec -T redis redis-cli INFO persistence | grep -q "aof_rewrite_in_progress:0"; do
    sleep 1
done
docker compose exec -T redis tar -czf - -C /data . > "$BACKUP_DIR/redis-data.tar.gz"

if [ -n "$(docker compose ps -q postgres)" ]; then
    echo "Backing up PostgreSQL..."
    docker compose exec -T postgres pg_dump -U "$PG_USER" "$PG_DB" > "$BACKUP_DIR/postgres.sql"
fi

echo "Compressing..."
tar -czf "$BACKUP_BASE/$DATE.tar.gz" -C "$BACKUP_BASE" "$DATE"
rm -rf "$BACKUP_DIR"

# Keep the last 7 days
find "$BACKUP_BASE" -maxdepth 1 -name "*.tar.gz" -mtime +7 -delete

echo "Backup complete: $BACKUP_BASE/$DATE.tar.gz"
```

## Script a full restore

```bash
#!/bin/bash
# full-restore.sh

set -e

BACKUP_FILE="${1:?Usage: $0 <backup-file.tar.gz>}"
PG_USER="${PG_USER:-postgres}"
PG_DB="${PG_DB:-vcon_db}"

RESTORE_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR"
BACKUP_DIR="$RESTORE_DIR/$(ls "$RESTORE_DIR")"

echo "Stopping services..."
docker compose stop conserver api redis

echo "Restoring configuration..."
cp "$BACKUP_DIR/.env" .env
cp "$BACKUP_DIR/config.yml" config.yml

echo "Restoring Redis..."
docker compose run --rm --no-deps -T -v "$BACKUP_DIR:/backup:ro" --entrypoint sh redis \
  -c 'rm -rf /data/* && tar -xzf /backup/redis-data.tar.gz -C /data'
docker compose start redis

if [ -f "$BACKUP_DIR/postgres.sql" ]; then
    echo "Restoring PostgreSQL..."
    docker compose exec -T postgres psql -U "$PG_USER" -d template1 -c "DROP DATABASE IF EXISTS $PG_DB;"
    docker compose exec -T postgres psql -U "$PG_USER" -d template1 -c "CREATE DATABASE $PG_DB;"
    docker compose exec -T postgres psql -U "$PG_USER" "$PG_DB" < "$BACKUP_DIR/postgres.sql"
fi

rm -rf "$RESTORE_DIR"

echo "Starting services..."
docker compose start conserver api

echo "Restore complete. Verify with: curl http://localhost:8000/api/health"
```

## Recover from a disaster

Set your own targets. These rows show what usually drives each one.

| Scenario | Recovery time depends on | Data loss back to |
|----------|--------------------------|-------------------|
| Configuration loss | Copying files | The last change you saved |
| Redis failure | Restoring the archive | The last Redis backup |
| Database failure | The size of the database | The last database backup |
| Complete failure | Rebuilding hosts and restoring everything | The last full backup |

1. **Assess the damage.**

    ```bash
    docker compose ps
    docker compose logs --tail=100
    ```

2. **Restore the infrastructure.** The network is external, and `COMPOSE_PROFILES` in `.env` starts the optional services.

    ```bash
    docker network create conserver
    docker compose up -d redis postgres
    ```

3. **Restore the data.**

    ```bash
    ./full-restore.sh ./backups/<timestamp>.tar.gz
    ```

4. **Verify the health.**

    ```bash
    curl http://localhost:8000/api/health
    docker compose exec -T redis redis-cli ping
    ```

5. **Test the pipeline.** [Submit a test vCon](index.md#submit-a-test-vcon), confirm it runs, and check that it reaches your storage backends.

## Test the restores

Run a restore in a staging environment every month. A backup you have never restored is not proven.

## Protect the backups

```bash
# Encrypt before upload
gpg --symmetric --cipher-algo AES256 backup.tar.gz

# Sync to offsite storage
aws s3 sync ./backups s3://vcon-backups/
```

Add the backup to cron with a notification, so a failed run gets noticed:

```bash
0 2 * * * /path/to/full-backup.sh && echo "Backup OK" | mail -s "vCon Backup" admin@example.com
```

Keep your runbooks current, with contacts, where credentials are stored, the steps above and a verification checklist.
