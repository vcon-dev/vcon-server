# Docker Installation

This guide covers installing vCon Server using Docker and Docker Compose.

## Prerequisites

- Docker 20.10 or later
- Docker Compose 2.0 or later
- Git
- 4GB RAM minimum (8GB recommended)
- 20GB disk space minimum

## Quick Installation

```bash
# Clone the repository
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server

# Create Docker network
docker network create conserver

# Copy configuration files
cp .env.example .env
cp example_docker-compose.yml docker-compose.yml

# Edit .env with your settings
nano .env

# Build and start services
docker compose up -d --build
```

## Detailed Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
```

### Step 2: Create Docker Network

The `conserver` network allows containers to communicate:

```bash
docker network create conserver
```

### Step 3: Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with required settings:

```bash
# Required Settings
REDIS_URL=redis://redis:6379
CONSERVER_API_TOKEN=your-secure-token-here

# Optional: AI Services
DEEPGRAM_KEY=your-deepgram-api-key
OPENAI_API_KEY=your-openai-api-key
GROQ_API_KEY=your-groq-api-key

# Optional: Worker Configuration
CONSERVER_WORKERS=4
CONSERVER_PARALLEL_STORAGE=true
CONSERVER_START_METHOD=fork

# Optional: Logging
LOG_LEVEL=INFO
ENV=production
```

!!! tip "Secure Token Generation"
    Generate a secure API token:
    ```bash
    openssl rand -hex 32
    ```

### Step 4: Configure Docker Compose

Copy and customize the Docker Compose file:

```bash
cp example_docker-compose.yml docker-compose.yml
```

The default configuration includes:

```yaml
services:
  redis:
    image: redis/redis-stack:latest
    ports:
      - "6379:6379"
      - "8001:8001"  # Redis Insight UI
    volumes:
      - redis_data:/data
    networks:
      - conserver

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: >
      opentelemetry-instrument
      uvicorn server.api:app
      --host 0.0.0.0
      --port 8000
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - redis
    networks:
      - conserver

  conserver:
    build:
      context: .
      dockerfile: docker/Dockerfile
    command: opentelemetry-instrument python ./server/main.py
    env_file:
      - .env
    depends_on:
      - redis
    networks:
      - conserver

volumes:
  redis_data:

networks:
  conserver:
    external: true
```

### Step 5: Build and Start

Build the Docker images:

```bash
docker compose build
```

Start all services:

```bash
docker compose up -d
```

### Step 6: Verify Installation

Check service status:

```bash
docker compose ps
```

Check API health:

```bash
curl http://localhost:8000/api/health
```

View logs:

```bash
docker compose logs -f
```

## Configuration Options

### Adding Storage Backends

#### PostgreSQL

Add to `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: vcon
      POSTGRES_PASSWORD: vcon_password
      POSTGRES_DB: vcon_server
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - conserver

volumes:
  postgres_data:
```

Add to `.env`:

```bash
POSTGRES_USER=vcon
POSTGRES_PASSWORD=vcon_password
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=vcon_server
```

#### MongoDB

Add to `docker-compose.yml`:

```yaml
services:
  mongo:
    image: mongo:6
    environment:
      MONGO_INITDB_ROOT_USERNAME: root
      MONGO_INITDB_ROOT_PASSWORD: example
    volumes:
      - mongo_data:/data/db
    networks:
      - conserver

volumes:
  mongo_data:
```

#### Elasticsearch

Add to `docker-compose.yml`:

```yaml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    volumes:
      - es_data:/usr/share/elasticsearch/data
    networks:
      - conserver

volumes:
  es_data:
```

### Scaling Workers

Scale the conserver service for more throughput:

```bash
# Run 4 conserver instances
docker compose up -d --scale conserver=4
```

Or use the `CONSERVER_WORKERS` environment variable for multi-worker mode within a single container:

```bash
CONSERVER_WORKERS=4
```

### Resource Limits

Add resource constraints in `docker-compose.yml`:

```yaml
services:
  conserver:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## Docker Commands Reference

### Service Management

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# Restart a specific service
docker compose restart conserver

# View logs
docker compose logs -f [service]

# Check status
docker compose ps
```

### Maintenance

```bash
# Update to latest code
git pull
docker compose build --no-cache
docker compose up -d

# Clean up unused images
docker image prune -f

# View resource usage
docker stats
```

### Debugging

```bash
# Execute shell in container
docker compose exec conserver bash

# View container logs
docker compose logs conserver --tail=100

# Check container health
docker inspect --format='{{.State.Health.Status}}' vcon-server-conserver-1
```

## Production Considerations

### Security

1. **Use secrets management** instead of environment variables for sensitive data
2. **Enable TLS** with a reverse proxy (nginx, Traefik)
3. **Restrict network access** to Redis and database ports
4. **Use non-root users** in containers (already configured in Dockerfile)

### Reverse Proxy with nginx

Add nginx for TLS termination:

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api
    networks:
      - conserver
```

### Health Checks

Add health checks to ensure service reliability:

```yaml
services:
  api:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

### Logging

Configure centralized logging:

```yaml
services:
  conserver:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Troubleshooting

### Container Won't Start

Check logs for errors:

```bash
docker compose logs conserver
```

Common issues:

- Redis not reachable (check network)
- Invalid configuration file
- Insufficient memory

### Redis Connection Failed

Verify Redis is running:

```bash
docker compose exec redis redis-cli ping
```

Check network connectivity:

```bash
docker compose exec conserver ping redis
```

### Out of Memory

Increase Docker memory limit or reduce worker count:

```bash
CONSERVER_WORKERS=2
```

### Port Already in Use

Check what's using the port:

```bash
lsof -i :8000
```

Change the port mapping in `docker-compose.yml`:

```yaml
ports:
  - "8080:8000"  # Map to different host port
```

## Next Steps

- [Configuration Guide](../configuration/index.md) - Customize your installation
- [Multi-Worker Configuration](../configuration/workers.md) - Scale processing
- [Monitoring](../operations/monitoring.md) - Set up observability
