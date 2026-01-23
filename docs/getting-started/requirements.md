# System Requirements

This page describes the hardware and software requirements for running vCon Server.

## Software Requirements

### Required Components

| Component | Version | Purpose |
|-----------|---------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Redis | 7.0+ | Queue management and caching |

### Optional Components

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.12+ | Local development without Docker |
| Poetry | 2.0+ | Python dependency management |
| PostgreSQL | 14+ | Relational storage backend |
| MongoDB | 6.0+ | Document storage backend |
| Elasticsearch | 8.0+ | Search storage backend |

## Hardware Requirements

### Minimum (Development/Testing)

| Resource | Requirement |
|----------|-------------|
| CPU | 2 cores |
| RAM | 4 GB |
| Storage | 20 GB SSD |
| Network | Stable internet connection |

### Recommended (Production)

| Resource | Small | Medium | Large |
|----------|-------|--------|-------|
| CPU | 4 cores | 8 cores | 16+ cores |
| RAM | 8 GB | 16 GB | 32+ GB |
| Storage | 100 GB SSD | 500 GB SSD | 1+ TB SSD |
| Workers | 2-4 | 4-8 | 8-16 |

### Scaling Considerations

**CPU**: Each worker process uses approximately 1 CPU core during active processing. Set `CONSERVER_WORKERS` based on available cores.

**Memory**: Base memory usage is approximately 500MB. Each worker adds 200-500MB depending on:

- Processing link complexity
- Audio file sizes being processed
- Caching configuration

**Storage**: Storage requirements depend on:

- Number of vCons processed
- Audio file retention policy
- Storage backends used

**Network**: Consider bandwidth for:

- Audio file ingestion
- External API calls (transcription, AI services)
- Storage backend communication

## Operating System Support

### Fully Supported

- **Linux**: Ubuntu 20.04+, Debian 11+, RHEL 8+, Amazon Linux 2
- **macOS**: 12.0+ (Monterey and later)

### Container Support

- Docker Desktop (Windows, macOS)
- Kubernetes 1.24+
- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Instances

### Windows

Windows is supported via:

- Docker Desktop with WSL2
- Windows Subsystem for Linux (WSL2)

!!! note "Windows Native"
    Native Windows installation is not recommended due to:
    
    - `fork` multiprocessing not available (must use `spawn`)
    - Path handling differences
    - Limited testing coverage

## Network Requirements

### Inbound Ports

| Port | Service | Required |
|------|---------|----------|
| 8000 | API Server | Yes |
| 6379 | Redis (if external) | Optional |

### Outbound Connections

| Service | URL | Required |
|---------|-----|----------|
| Deepgram | api.deepgram.com | If using Deepgram transcription |
| OpenAI | api.openai.com | If using OpenAI analysis/transcription |
| Groq | api.groq.com | If using Groq Whisper |
| Hugging Face | huggingface.co | If using HF models |

### Firewall Rules

For production deployments, ensure:

1. API server port (8000) accessible to clients
2. Redis port (6379) accessible only internally
3. Outbound HTTPS (443) for external AI services
4. Storage backend ports accessible from workers

## External Service Requirements

### AI Services (Optional)

To use transcription and analysis features, you need API keys for:

| Service | Environment Variable | Free Tier |
|---------|---------------------|-----------|
| Deepgram | `DEEPGRAM_KEY` | Yes (limited) |
| OpenAI | `OPENAI_API_KEY` | No |
| Groq | `GROQ_API_KEY` | Yes (limited) |

### Storage Services (Optional)

| Service | Credentials Needed |
|---------|-------------------|
| AWS S3 | Access Key ID, Secret Access Key |
| MongoDB Atlas | Connection string |
| Elasticsearch Cloud | API key or credentials |

## Verifying Requirements

### Check Docker

```bash
# Check Docker version
docker --version
# Expected: Docker version 20.10.0 or higher

# Check Docker Compose version
docker compose version
# Expected: Docker Compose version 2.0.0 or higher

# Verify Docker is running
docker info
```

### Check Python (for local development)

```bash
# Check Python version
python3 --version
# Expected: Python 3.12.0 or higher

# Check Poetry version
poetry --version
# Expected: Poetry version 2.0.0 or higher
```

### Check System Resources

```bash
# Linux/macOS - Check available memory
free -h  # Linux
vm_stat  # macOS

# Check available disk space
df -h

# Check CPU cores
nproc  # Linux
sysctl -n hw.ncpu  # macOS
```

## Next Steps

Once you have verified your system meets the requirements:

1. **[Quick Start](quick-start.md)**: Get running in 5 minutes
2. **[Docker Installation](../installation/docker.md)**: Detailed Docker setup
3. **[Manual Installation](../installation/manual-installation.md)**: Development setup with Poetry
