# Automated Installation Script

The automated installation script provides a one-command setup for production deployments on Ubuntu Linux.

## Overview

The `install_conserver.sh` script:

- Installs Docker and Docker Compose if needed
- Creates a dedicated `vcon` user
- Sets up directory structure
- Clones both vcon-server and vcon-admin repositories
- Configures SSL with Let's Encrypt
- Starts all services

## Requirements

- **Operating System**: Ubuntu 20.04 or later (recommended)
- **Access**: Root or sudo privileges
- **Network**: Public IP address with DNS record
- **Resources**: Minimum 4GB RAM, 20GB disk

## Usage

### Basic Installation

```bash
sudo ./scripts/install_conserver.sh \
  --domain your-domain.com \
  --email admin@your-domain.com
```

### With Custom API Token

```bash
sudo ./scripts/install_conserver.sh \
  --domain your-domain.com \
  --email admin@your-domain.com \
  --token your-custom-api-token
```

## Command Line Options

| Option | Required | Description |
|--------|----------|-------------|
| `--domain` | Yes | Domain name pointing to this server |
| `--email` | Yes | Email for SSL certificate registration |
| `--token` | No | Custom API token (auto-generated if not provided) |

## What Gets Installed

### Directory Structure

```
/opt/vcon-admin/     # Admin portal
/opt/vcon-server/    # vCon Server
/opt/vcon-data/      # Persistent data
  ├── redis/         # Redis data
  ├── mongo/         # MongoDB data
  └── uploads/       # Uploaded files
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| API | 8000 | vCon Server REST API |
| Admin | 3000 | Admin portal web UI |
| Redis | 6379 | Queue and cache |
| MongoDB | 27017 | Document storage |
| nginx | 80, 443 | Reverse proxy with SSL |

### User Account

A dedicated `vcon` user is created with:

- No login shell (security)
- Ownership of `/opt/vcon-*` directories
- Docker group membership

## Post-Installation

### Access Points

After installation, access your services at:

| Service | URL |
|---------|-----|
| Admin Portal | `https://your-domain.com/admin/` |
| API Documentation | `https://your-domain.com/api/docs` |
| API Health | `https://your-domain.com/api/health` |
| MongoDB Express | `https://your-domain.com/mongo-express` |
| Redis Insight | `http://your-server:8001` |

### API Token

If you didn't specify a token, find it in:

```bash
cat /opt/vcon-server/.env | grep CONSERVER_API_TOKEN
```

### Service Management

```bash
# View service status
cd /opt/vcon-server
docker compose ps

# View logs
docker compose logs -f

# Restart services
docker compose restart

# Stop services
docker compose down

# Start services
docker compose up -d
```

## Configuration

### Environment Variables

Edit `/opt/vcon-server/.env`:

```bash
sudo -u vcon nano /opt/vcon-server/.env
```

After changes, restart services:

```bash
cd /opt/vcon-server
docker compose restart
```

### Processing Chains

Edit `/opt/vcon-server/config.yml`:

```bash
sudo -u vcon nano /opt/vcon-server/config.yml
```

### SSL Certificates

Certificates are managed by Certbot and auto-renewed. Manual renewal:

```bash
certbot renew
```

## Upgrading

### Update vCon Server

```bash
cd /opt/vcon-server
sudo -u vcon git pull
docker compose build --no-cache
docker compose up -d
```

### Update Admin Portal

```bash
cd /opt/vcon-admin
sudo -u vcon git pull
docker compose build --no-cache
docker compose up -d
```

## Uninstallation

Use the uninstall script:

```bash
sudo ./scripts/uninstall_conserver.sh
```

This removes:

- Docker containers and images
- Configuration files
- The `vcon` user

!!! warning "Data Preservation"
    By default, data in `/opt/vcon-data` is preserved. Add `--remove-data` to delete everything.

## Troubleshooting

### Installation Failed

Check the installation log:

```bash
cat /var/log/conserver-install.log
```

Common issues:

1. **DNS not configured**: Ensure your domain points to the server IP
2. **Port 80/443 in use**: Stop any existing web servers
3. **Insufficient disk space**: Need at least 20GB free
4. **Docker installation failed**: Try installing Docker manually first

### Services Not Starting

Check Docker logs:

```bash
cd /opt/vcon-server
docker compose logs
```

Check system resources:

```bash
free -h
df -h
```

### SSL Certificate Issues

Verify DNS:

```bash
dig your-domain.com
```

Check Certbot logs:

```bash
cat /var/log/letsencrypt/letsencrypt.log
```

### Cannot Access Admin Portal

Check nginx configuration:

```bash
nginx -t
systemctl status nginx
```

Verify the admin service is running:

```bash
cd /opt/vcon-admin
docker compose ps
```

## Security Considerations

### Firewall Configuration

The script configures UFW. Required ports:

```bash
# View current rules
ufw status

# Required ports
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP (redirect to HTTPS)
ufw allow 443/tcp   # HTTPS
```

### Changing the API Token

1. Generate new token:
   ```bash
   openssl rand -hex 32
   ```

2. Update `.env`:
   ```bash
   sudo -u vcon nano /opt/vcon-server/.env
   ```

3. Restart services:
   ```bash
   cd /opt/vcon-server
   docker compose restart
   ```

4. Update any clients using the old token

### Database Security

MongoDB is configured with authentication. Default credentials are in `.env`. Change them for production:

1. Update `.env` with new credentials
2. Connect to MongoDB and update users
3. Restart services

## Next Steps

- [Configuration Guide](../configuration/index.md) - Customize settings
- [API Reference](../operations/api-reference.md) - Explore the API
- [Monitoring](../operations/monitoring.md) - Set up observability
