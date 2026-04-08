# VCONIC Conserver — Upgrade Guide

**Document ID:** VCONIC-CSV-UPG-001  
**Product:** VCONIC Conserver  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## 1. Overview

This guide covers the procedures for upgrading the VCONIC Conserver from one version to the next. Always review the [Release Notes](./07-release-notes.md) for the target version before upgrading.

---

## 2. Pre-Upgrade Checklist

Complete every item before beginning the upgrade:

- [ ] **Read the Release Notes** for the target version — note breaking changes
- [ ] **Back up the PostgreSQL database** (see [Administration Guide](./04-administration-guide.md))
- [ ] **Back up configuration files** (`.env`, `config.yml`, `docker-compose.yml`)
- [ ] **Verify current system health** — all services running, no DLQ backlog
- [ ] **Drain the ingress queues** — wait for all in-flight vCons to finish processing
- [ ] **Schedule a maintenance window** — brief downtime is expected during upgrade
- [ ] **Prepare a rollback plan** — know how to restore from backup

---

## 3. Upgrade Procedure

### 3.1 Drain Queues

Stop submitting new vCons and wait for queues to empty:

```bash
# Check queue depth
curl "http://localhost:8000/stats/queue?list_name=default"

# Wait until depth is 0
watch -n 5 'curl -s "http://localhost:8000/stats/queue?list_name=default"'
```

### 3.2 Back Up

```bash
# Database
docker compose exec -T postgres pg_dump -U postgres -Fc conserver > backup_pre_upgrade_$(date +%Y%m%d).dump

# Configuration
cp .env .env.backup_$(date +%Y%m%d)
cp config.yml config.yml.backup_$(date +%Y%m%d)
cp docker-compose.yml docker-compose.yml.backup_$(date +%Y%m%d)
```

### 3.3 Stop Services

```bash
docker compose down
```

### 3.4 Update Source Code

**From git:**

```bash
git fetch origin
git checkout <new-version-tag>
```

**From release archive:**

```bash
# Extract new version alongside current
tar xzf vconic-conserver-<new-version>.tar.gz -C /opt/vcon-server-new

# Copy configuration from old to new
cp /opt/vcon-server/.env /opt/vcon-server-new/.env
cp /opt/vcon-server/config.yml /opt/vcon-server-new/config.yml
cp /opt/vcon-server/docker-compose.yml /opt/vcon-server-new/docker-compose.yml

# Swap directories
mv /opt/vcon-server /opt/vcon-server-old
mv /opt/vcon-server-new /opt/vcon-server
```

### 3.5 Review Configuration Changes

Compare the new `.env.example` and `example_docker-compose.yml` with your current files:

```bash
diff .env.backup_$(date +%Y%m%d) .env.example
diff docker-compose.yml.backup_$(date +%Y%m%d) example_docker-compose.yml
```

Apply any new required settings to your `.env` and `docker-compose.yml`.

### 3.6 Rebuild and Start

```bash
docker compose build
docker compose up -d
```

### 3.7 Verify

```bash
# Check all services are running
docker compose ps

# Check health
curl http://localhost:8000/health

# Check version
curl http://localhost:8000/version

# Check logs for errors
docker compose logs --tail 50 conserver
docker compose logs --tail 50 api

# Submit a test vCon
curl -X POST http://localhost:8000/vcon \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: <token>" \
  -d '{"vcon":"0.0.1","parties":[],"dialog":[],"analysis":[],"attachments":[]}'
```

---

## 4. Rollback Procedure

If the upgrade fails or the new version has issues:

### 4.1 Stop New Version

```bash
docker compose down
```

### 4.2 Restore Previous Version

```bash
# If using directory swap
mv /opt/vcon-server /opt/vcon-server-failed
mv /opt/vcon-server-old /opt/vcon-server

# Or if using git
git checkout <previous-version-tag>
```

### 4.3 Restore Configuration

```bash
cp .env.backup_<date> .env
cp config.yml.backup_<date> config.yml
cp docker-compose.yml.backup_<date> docker-compose.yml
```

### 4.4 Restore Database (If Needed)

Only restore the database if the upgrade included schema changes that corrupted data:

```bash
docker compose up -d postgres
docker compose exec -T postgres pg_restore -U postgres -d conserver --clean backup_pre_upgrade_<date>.dump
```

### 4.5 Rebuild and Start

```bash
docker compose build
docker compose up -d
```

### 4.6 Verify Rollback

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/version
```

---

## 5. Upgrade Tips

- **Test upgrades in a staging environment first** if possible
- **Keep at least 3 backup generations** before removing old backups
- **Monitor closely for 24 hours** after an upgrade
- **Document any custom configuration changes** you make during upgrade

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
