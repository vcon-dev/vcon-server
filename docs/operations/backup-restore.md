# Backup and Restore

This guide covers backup strategies and recovery procedures for vCon Server.

## What to Backup

| Component | Priority | Frequency | Method |
|-----------|----------|-----------|--------|
| Configuration | Critical | On change | File copy |
| Redis data | High | Daily | RDB/AOF |
| Storage backends | High | Daily | Native tools |
| vCon data | High | Continuous | Storage replication |

## Configuration Backup

### Environment Files

```bash
# Backup
cp .env ./backups/.env.$(date +%Y%m%d)
cp config.yml ./backups/config.yml.$(date +%Y%m%d)

# Restore
cp ./backups/.env.20240115 .env
cp ./backups/config.yml.20240115 config.yml
```

### Docker Compose

```bash
# Backup
cp docker-compose.yml ./backups/docker-compose.yml.$(date +%Y%m%d)
```

### Automated Config Backup

```bash
#!/bin/bash
# backup-config.sh
BACKUP_DIR="./backups/config"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

cp .env "$BACKUP_DIR/.env.$DATE"
cp config.yml "$BACKUP_DIR/config.yml.$DATE"
cp docker-compose.yml "$BACKUP_DIR/docker-compose.yml.$DATE"

# Keep last 30 days
find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "Configuration backed up to $BACKUP_DIR"
```

## Redis Backup

### RDB Snapshot

```bash
# Trigger snapshot
docker compose exec redis redis-cli BGSAVE

# Wait for completion
docker compose exec redis redis-cli LASTSAVE

# Copy snapshot
docker cp vcon-server-redis-1:/data/dump.rdb ./backups/redis-dump.$(date +%Y%m%d).rdb
```

### AOF Backup

If using AOF persistence:

```bash
# Rewrite AOF
docker compose exec redis redis-cli BGREWRITEAOF

# Copy AOF file
docker cp vcon-server-redis-1:/data/appendonly.aof ./backups/
```

### Automated Redis Backup

```bash
#!/bin/bash
# backup-redis.sh
BACKUP_DIR="./backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Trigger background save
docker compose exec -T redis redis-cli BGSAVE

# Wait for save to complete (max 60 seconds)
for i in {1..60}; do
    if docker compose exec -T redis redis-cli LASTSAVE | grep -q "$(date +%s)"; then
        break
    fi
    sleep 1
done

# Copy snapshot
docker cp vcon-server-redis-1:/data/dump.rdb "$BACKUP_DIR/dump.$DATE.rdb"

# Compress
gzip "$BACKUP_DIR/dump.$DATE.rdb"

# Keep last 7 days
find "$BACKUP_DIR" -name "*.rdb.gz" -mtime +7 -delete

echo "Redis backed up to $BACKUP_DIR/dump.$DATE.rdb.gz"
```

### Restore Redis

```bash
# Stop services
docker compose stop conserver api

# Replace dump file
docker cp ./backups/redis-dump.20240115.rdb vcon-server-redis-1:/data/dump.rdb

# Restart Redis
docker compose restart redis

# Start services
docker compose start conserver api
```

## PostgreSQL Backup

### pg_dump

```bash
# Backup
docker compose exec postgres pg_dump -U vcon vcon_server > ./backups/postgres-$(date +%Y%m%d).sql

# Compressed backup
docker compose exec postgres pg_dump -U vcon vcon_server | gzip > ./backups/postgres-$(date +%Y%m%d).sql.gz
```

### Restore PostgreSQL

```bash
# Drop and recreate database
docker compose exec postgres psql -U vcon -c "DROP DATABASE IF EXISTS vcon_server;"
docker compose exec postgres psql -U vcon -c "CREATE DATABASE vcon_server;"

# Restore
docker compose exec -T postgres psql -U vcon vcon_server < ./backups/postgres-20240115.sql

# Or from compressed
gunzip -c ./backups/postgres-20240115.sql.gz | docker compose exec -T postgres psql -U vcon vcon_server
```

## MongoDB Backup

### mongodump

```bash
# Backup
docker compose exec mongo mongodump \
  --username root \
  --password example \
  --authenticationDatabase admin \
  --db conserver \
  --out /tmp/backup

# Copy from container
docker cp vcon-server-mongo-1:/tmp/backup ./backups/mongo-$(date +%Y%m%d)
```

### Restore MongoDB

```bash
# Copy to container
docker cp ./backups/mongo-20240115 vcon-server-mongo-1:/tmp/restore

# Restore
docker compose exec mongo mongorestore \
  --username root \
  --password example \
  --authenticationDatabase admin \
  --db conserver \
  /tmp/restore/conserver
```

## S3 Backup

### Cross-Region Replication

Configure S3 bucket replication for disaster recovery:

```json
{
  "Rules": [
    {
      "ID": "BackupRule",
      "Status": "Enabled",
      "Destination": {
        "Bucket": "arn:aws:s3:::backup-bucket",
        "StorageClass": "STANDARD_IA"
      }
    }
  ]
}
```

### S3 Sync

```bash
# Backup to another bucket
aws s3 sync s3://vcon-bucket s3://vcon-backup-bucket

# Backup to local
aws s3 sync s3://vcon-bucket ./backups/s3-$(date +%Y%m%d)
```

## Elasticsearch Backup

### Snapshot Repository

```bash
# Create repository
curl -X PUT "localhost:9200/_snapshot/backup" -H 'Content-Type: application/json' -d'
{
  "type": "fs",
  "settings": {
    "location": "/backups"
  }
}'

# Create snapshot
curl -X PUT "localhost:9200/_snapshot/backup/snapshot_$(date +%Y%m%d)"
```

### Restore Snapshot

```bash
# List snapshots
curl "localhost:9200/_snapshot/backup/_all"

# Restore
curl -X POST "localhost:9200/_snapshot/backup/snapshot_20240115/_restore"
```

## Complete Backup Script

```bash
#!/bin/bash
# full-backup.sh

set -e

BACKUP_BASE="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_BASE/$DATE"

echo "Starting full backup to $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"

# 1. Configuration
echo "Backing up configuration..."
cp .env "$BACKUP_DIR/"
cp config.yml "$BACKUP_DIR/"
cp docker-compose.yml "$BACKUP_DIR/"

# 2. Redis
echo "Backing up Redis..."
docker compose exec -T redis redis-cli BGSAVE
sleep 5  # Wait for save
docker cp vcon-server-redis-1:/data/dump.rdb "$BACKUP_DIR/redis-dump.rdb"

# 3. PostgreSQL (if used)
if docker compose ps postgres | grep -q "running"; then
    echo "Backing up PostgreSQL..."
    docker compose exec -T postgres pg_dump -U vcon vcon_server > "$BACKUP_DIR/postgres.sql"
fi

# 4. MongoDB (if used)
if docker compose ps mongo | grep -q "running"; then
    echo "Backing up MongoDB..."
    docker compose exec -T mongo mongodump \
        --username root --password example \
        --authenticationDatabase admin \
        --db conserver --out /tmp/mongodump
    docker cp vcon-server-mongo-1:/tmp/mongodump "$BACKUP_DIR/mongo"
fi

# 5. Compress
echo "Compressing backup..."
cd "$BACKUP_BASE"
tar -czf "$DATE.tar.gz" "$DATE"
rm -rf "$DATE"

# 6. Cleanup old backups (keep 7 days)
find "$BACKUP_BASE" -name "*.tar.gz" -mtime +7 -delete

echo "Backup complete: $BACKUP_BASE/$DATE.tar.gz"
```

## Complete Restore Script

```bash
#!/bin/bash
# full-restore.sh

set -e

BACKUP_FILE="${1:?Usage: $0 <backup-file.tar.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Restoring from $BACKUP_FILE"

# Extract backup
RESTORE_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$RESTORE_DIR"
BACKUP_DIR=$(ls "$RESTORE_DIR")

# Stop services
echo "Stopping services..."
docker compose stop conserver api

# 1. Configuration
echo "Restoring configuration..."
cp "$RESTORE_DIR/$BACKUP_DIR/.env" .env
cp "$RESTORE_DIR/$BACKUP_DIR/config.yml" config.yml

# 2. Redis
echo "Restoring Redis..."
docker cp "$RESTORE_DIR/$BACKUP_DIR/redis-dump.rdb" vcon-server-redis-1:/data/dump.rdb
docker compose restart redis

# 3. PostgreSQL
if [ -f "$RESTORE_DIR/$BACKUP_DIR/postgres.sql" ]; then
    echo "Restoring PostgreSQL..."
    docker compose exec -T postgres psql -U vcon -c "DROP DATABASE IF EXISTS vcon_server;"
    docker compose exec -T postgres psql -U vcon -c "CREATE DATABASE vcon_server;"
    docker compose exec -T postgres psql -U vcon vcon_server < "$RESTORE_DIR/$BACKUP_DIR/postgres.sql"
fi

# 4. MongoDB
if [ -d "$RESTORE_DIR/$BACKUP_DIR/mongo" ]; then
    echo "Restoring MongoDB..."
    docker cp "$RESTORE_DIR/$BACKUP_DIR/mongo" vcon-server-mongo-1:/tmp/mongorestore
    docker compose exec -T mongo mongorestore \
        --username root --password example \
        --authenticationDatabase admin \
        --db conserver /tmp/mongorestore/conserver
fi

# Cleanup
rm -rf "$RESTORE_DIR"

# Start services
echo "Starting services..."
docker compose start conserver api

echo "Restore complete. Verify with: curl http://localhost:8000/api/health"
```

## Disaster Recovery

### Recovery Time Objectives

| Scenario | RTO | RPO |
|----------|-----|-----|
| Configuration loss | Minutes | On change |
| Redis failure | Minutes | Last backup |
| Database failure | Hours | Last backup |
| Complete failure | Hours | Last full backup |

### Recovery Procedure

1. **Assess damage**
   ```bash
   docker compose ps
   docker compose logs --tail=100
   ```

2. **Restore infrastructure**
   ```bash
   docker compose up -d redis postgres mongo
   ```

3. **Restore data**
   ```bash
   ./full-restore.sh ./backups/latest.tar.gz
   ```

4. **Verify health**
   ```bash
   curl http://localhost:8000/api/health
   curl http://localhost:8000/api/version
   ```

5. **Test functionality**
   ```bash
   # Submit test vCon
   # Verify processing
   # Check storage backends
   ```

## Best Practices

### 1. Test Restores Regularly

```bash
# Monthly restore test to staging
./full-restore.sh ./backups/latest.tar.gz
# Verify everything works
```

### 2. Offsite Backups

```bash
# Sync to cloud storage
aws s3 sync ./backups s3://vcon-backups/
```

### 3. Encrypt Sensitive Backups

```bash
# Encrypt before upload
gpg --symmetric --cipher-algo AES256 backup.tar.gz
```

### 4. Monitor Backup Jobs

```bash
# Add to cron with notification
0 2 * * * /path/to/full-backup.sh && echo "Backup OK" | mail -s "vCon Backup" admin@example.com
```

### 5. Document Recovery Procedures

Keep runbooks updated with:

- Contact information
- Access credentials (securely stored)
- Step-by-step procedures
- Verification checklists
