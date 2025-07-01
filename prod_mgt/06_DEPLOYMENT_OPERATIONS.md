# Deployment & Operations

## Deployment Models

### 1. Docker Deployment (Recommended)

#### Single Host Deployment
```bash
# Quick start
docker compose up -d

# With scaling
docker compose up --scale conserver=4 -d
```

#### Production Deployment
```yaml
# docker-compose.yml
services:
  conserver:
    image: vcon/server:latest
    deploy:
      replicas: 4
      resources:
        limits:
          cpus: '2'
          memory: 4G
    environment:
      - REDIS_URL=redis://redis:6379
      - CONSERVER_API_TOKEN=${API_TOKEN}
```

### 2. Kubernetes Deployment

#### Basic Deployment
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vcon-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: vcon-server
  template:
    spec:
      containers:
      - name: vcon-server
        image: vcon/server:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2"
```

#### Helm Chart Features
- ConfigMap management
- Secret handling
- Horizontal Pod Autoscaling
- Ingress configuration
- Service mesh ready

### 3. Cloud Platform Deployments

#### AWS Deployment
- **ECS**: Container service
- **EKS**: Kubernetes service
- **Lambda**: Serverless functions
- **RDS**: PostgreSQL backend
- **ElastiCache**: Redis cluster

#### Azure Deployment
- **AKS**: Kubernetes service
- **Container Instances**: Simple containers
- **Functions**: Serverless
- **Database for PostgreSQL**
- **Cache for Redis**

#### GCP Deployment
- **GKE**: Kubernetes engine
- **Cloud Run**: Serverless containers
- **Cloud SQL**: PostgreSQL
- **Memorystore**: Redis

## Installation Methods

### 1. Automated Installation
```bash
# Download and run installer
curl -O https://raw.githubusercontent.com/vcon-dev/vcon-server/main/scripts/install_conserver.sh
chmod +x install_conserver.sh
sudo ./install_conserver.sh --domain your-domain.com --email admin@example.com
```

**Installer Features**:
- System dependency installation
- Docker setup
- SSL certificate configuration
- Monitoring setup
- User creation
- Directory structure

### 2. Manual Installation
```bash
# Clone repository
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server

# Configure environment
cp .env.example .env
vim .env

# Create Docker network
docker network create conserver

# Build and start
docker compose build
docker compose up -d
```

## Configuration Management

### Environment Variables
```bash
# Core settings
REDIS_URL=redis://redis:6379
CONSERVER_API_TOKEN=secure-token
CONSERVER_CONFIG_FILE=./config.yml

# Service keys
DEEPGRAM_KEY=dg-key
OPENAI_API_KEY=sk-key
GROQ_API_KEY=gsk-key

# Performance tuning
VCON_REDIS_EXPIRY=3600
VCON_INDEX_EXPIRY=86400
TICK_INTERVAL=5000
```

### Configuration File Structure
```yaml
# config.yml
links:
  transcription:
    module: links.deepgram_link
    options:
      DEEPGRAM_KEY: ${DEEPGRAM_KEY}
      
storages:
  primary:
    module: storage.postgres
    options:
      host: ${DB_HOST}
      
chains:
  main:
    links: [transcription, analysis]
    storages: [primary, backup]
    enabled: 1
```

## Scaling Strategies

### Horizontal Scaling
1. **Stateless Workers**: Scale conserver instances
2. **Queue Distribution**: Redis-based load balancing
3. **Storage Scaling**: Distributed storage backends
4. **Cache Scaling**: Redis cluster mode

### Vertical Scaling
1. **Resource Allocation**: CPU and memory limits
2. **Connection Pooling**: Database connections
3. **Batch Processing**: Larger batch sizes
4. **Caching**: Increase cache sizes

### Performance Optimization
```yaml
# Optimized configuration
chains:
  high_performance:
    links:
      - sampler:         # Process 10% sample
          rate: 0.1
      - deepgram_link:
          batch_size: 50
    workers: 8
    timeout: 300
```

## Monitoring & Observability

### Metrics Collection
- **Datadog Integration**: APM and custom metrics
- **Prometheus**: Time-series metrics
- **StatsD**: Application metrics

### Key Metrics
```python
# Processing metrics
conserver.link.{link_name}.process_time
conserver.link.{link_name}.success_count
conserver.link.{link_name}.failure_count

# Storage metrics
conserver.storage.{storage_name}.save_time
conserver.storage.{storage_name}.get_time

# Queue metrics
conserver.queue.{queue_name}.length
conserver.queue.{queue_name}.processing_time
```

### Logging
```python
# Logging configuration
LOG_LEVEL=INFO
LOGGING_CONFIG_FILE=./logging.conf

# Structured logging
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "vcon-server",
  "vcon_id": "uuid",
  "link": "deepgram_link",
  "message": "Processing complete"
}
```

### Health Checks
```yaml
# Docker health check
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Backup & Recovery

### Backup Strategies
1. **Database Backups**: PostgreSQL dumps
2. **Object Storage**: S3 versioning
3. **Redis Persistence**: RDB snapshots
4. **Configuration**: Git versioning

### Disaster Recovery
```bash
# Backup script
#!/bin/bash
# Backup PostgreSQL
pg_dump -h localhost -U postgres vcon_db > backup.sql

# Backup Redis
redis-cli --rdb dump.rdb

# Sync to S3
aws s3 sync ./backups s3://backup-bucket/
```

## Security Operations

### Access Control
1. **API Authentication**: Token management
2. **Network Security**: VPC/firewall rules
3. **TLS/SSL**: Certificate management
4. **Secret Management**: Vault integration

### Security Scanning
```bash
# Container scanning
docker scan vcon/server:latest

# Dependency scanning
pip audit

# Code scanning
bandit -r server/
```

## Maintenance Tasks

### Regular Maintenance
1. **Log Rotation**: Prevent disk fill
2. **Cache Cleanup**: Redis memory management
3. **Database Vacuum**: PostgreSQL optimization
4. **Index Rebuild**: Search performance

### Update Procedures
```bash
# Rolling update
docker compose pull
docker compose up -d --no-deps --scale conserver=4 conserver

# Database migrations
python manage.py migrate

# Configuration reload
docker compose exec conserver reload
```

## Troubleshooting

### Common Issues

1. **Redis Connection Issues**
   ```bash
   # Check Redis
   redis-cli ping
   # Check connectivity
   docker compose logs redis
   ```

2. **Storage Failures**
   ```bash
   # Check storage logs
   docker compose logs -f conserver | grep storage
   # Test connection
   python -m server.storage.test_connection
   ```

3. **Performance Issues**
   ```bash
   # Check queue lengths
   redis-cli llen main_ingress
   # Monitor processing
   docker stats
   ```

### Debug Mode
```bash
# Enable debug logging
LOG_LEVEL=DEBUG docker compose up

# Trace specific vCon
curl -X GET /api/vcon/{uuid}?debug=true
```