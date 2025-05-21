# 🐰 vCon Server

vCon Server is a powerful conversation processing and storage system that enables advanced analysis and management of conversation data. It provides a flexible pipeline for processing, storing, and analyzing conversations through various modules and integrations.

## Table of Contents
- [🐰 vCon Server](#-vcon-server)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Quick Start](#quick-start)
  - [Installation](#installation)
    - [Manual Installation](#manual-installation)
    - [Automated Installation](#automated-installation)
  - [Configuration](#configuration)
    - [Environment Variables](#environment-variables)
    - [Configuration File](#configuration-file)
  - [Deployment](#deployment)
    - [Docker Deployment](#docker-deployment)
    - [Scaling](#scaling)
  - [Storage Modules](#storage-modules)
    - [PostgreSQL Storage](#postgresql-storage)
    - [S3 Storage](#s3-storage)
    - [Elasticsearch Storage](#elasticsearch-storage)
    - [Milvus Vector Database Storage](#milvus-vector-database-storage)
  - [Monitoring and Logging](#monitoring-and-logging)
  - [Troubleshooting](#troubleshooting)
  - [License](#license)
  - [Production Deployment Best Practices](#production-deployment-best-practices)
    - [Example Directory Layout](#example-directory-layout)
    - [Example Redis Volume in docker-compose.yml](#example-redis-volume-in-docker-composeyml)
    - [User Creation and Permissions](#user-creation-and-permissions)

## Prerequisites

- Docker and Docker Compose
- Git
- Python 3.12 or higher (for local development)
- Poetry (for local development)

## Quick Start

For a quick start using the automated installation script:

```bash
# Download the installation script
curl -O https://raw.githubusercontent.com/vcon-dev/vcon-server/main/scripts/install_conserver.sh
chmod +x install_conserver.sh

# Run the installation script
sudo ./install_conserver.sh --domain your-domain.com --email your-email@example.com
```

## Installation

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
```

2. Create and configure the environment file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Create the Docker network:
```bash
docker network create conserver
```

4. Build and start the services:
```bash
docker compose build
docker compose up -d
```

### Automated Installation

The repository includes an automated installation script that handles the complete setup process. The script:

- Installs required dependencies
- Sets up Docker and Docker Compose
- Configures the environment
- Deploys the services
- Sets up monitoring

To use the automated installation:

```bash
./scripts/install_conserver.sh --domain your-domain.com --email your-email@example.com [--token YOUR_API_TOKEN]
```

Options:
- `--domain`: Your domain name (required)
- `--email`: Email for DNS registration (required)
- `--token`: API token (optional, generates random token if not provided)

## Configuration

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```bash
REDIS_URL=redis://redis
CONSERVER_API_TOKEN=your_api_token
CONSERVER_CONFIG_FILE=./config.yml
GROQ_API_KEY=your_groq_api_key
DNS_HOST=your-domain.com
DNS_REGISTRATION_EMAIL=your-email@example.com
```

### Configuration File

The `config.yml` file defines the processing pipeline, storage options, and chain configurations. Here's an example configuration:

```yaml
links:
  webhook_store_call_log:
    module: links.webhook
    options:
      webhook-urls:
        - https://example.com/conserver
  deepgram:
    module: links.deepgram
    options:
      DEEPGRAM_KEY: your_deepgram_key
      minimum_duration: 30
      api:
        model: "nova-2"
        smart_format: true
        detect_language: true
  summarize:
    module: links.analyze
    options:
      OPENAI_API_KEY: your_openai_key
      prompt: "Summarize this transcript..."
      analysis_type: summary
      model: 'gpt-4'

storages:
  postgres:
    module: storage.postgres
    options:
      user: postgres
      password: your_password
      host: your_host
      port: "5432"
      database: postgres
  s3:
    module: storage.s3
    options:
      aws_access_key_id: your_key
      aws_secret_access_key: your_secret
      aws_bucket: your_bucket

chains:
  main_chain:
    links:
      - deepgram
      - summarize
      - webhook_store_call_log
    storages:
      - postgres
      - s3
    enabled: 1
```

## Deployment

### Docker Deployment

The system is containerized using Docker and can be deployed using Docker Compose:

```bash
# Build the containers
docker compose build

# Start the services
docker compose up -d

# Scale the conserver service
docker compose up --scale conserver=4 -d
```

### Scaling

The system is designed to scale horizontally. The conserver service can be scaled to handle increased load:

```bash
docker compose up --scale conserver=4 -d
```

## Storage Modules

### PostgreSQL Storage

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      user: postgres
      password: your_password
      host: your_host
      port: "5432"
      database: postgres
```

### S3 Storage

```yaml
storages:
  s3:
    module: storage.s3
    options:
      aws_access_key_id: your_key
      aws_secret_access_key: your_secret
      aws_bucket: your_bucket
```

### Elasticsearch Storage

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      cloud_id: "your_cloud_id"
      api_key: "your_api_key"
      index: vcon_index
```

### Milvus Vector Database Storage

For semantic search capabilities:

```yaml
storages:
  milvus:
    module: storage.milvus
    options:
      host: "localhost"
      port: "19530"
      collection_name: "vcons"
      embedding_model: "text-embedding-3-small"
      embedding_dim: 1536
      api_key: "your-openai-api-key"
      organization: "your-org-id"
      create_collection_if_missing: true
```

## Monitoring and Logging

The system includes built-in monitoring through Datadog. Configure monitoring by setting the following environment variables:

```bash
DD_API_KEY=your_datadog_api_key
DD_SITE=datadoghq.com
```

View logs using:
```bash
docker compose logs -f
```

## Troubleshooting

Common issues and solutions:

1. Redis Connection Issues:
   - Check if Redis container is running: `docker ps | grep redis`
   - Verify Redis URL in .env file
   - Check Redis logs: `docker compose logs redis`

2. Service Scaling Issues:
   - Ensure sufficient system resources
   - Check network connectivity between containers
   - Verify Redis connection for all instances

3. Storage Module Issues:
   - Verify credentials and connection strings
   - Check storage service availability
   - Review storage module logs

For additional help, check the logs:
```bash
docker compose logs -f [service_name]
```

## License

This project is licensed under the terms specified in the LICENSE file.

## Production Deployment Best Practices

- **Install as a non-root user**: Create a dedicated user (e.g., `vcon`) for running the application and Docker containers.
- **Clone repositories to /opt**: Place `vcon-admin` and `vcon-server` in `/opt` for system-wide, non-root access.
- **Use persistent Docker volumes**: Map Redis and other stateful service data to `/opt/vcon-data` for durability.
- **Follow the updated install script**: Use `scripts/install_conserver.sh` which now implements these best practices.

### Example Directory Layout

```
/opt/vcon-admin
/opt/vcon-server
/opt/vcon-data/redis
```

### Example Redis Volume in docker-compose.yml

```yaml
volumes:
  - /opt/vcon-data/redis:/data
```

### User Creation and Permissions

The install script creates the `vcon` user and sets permissions for all necessary directories.

---
