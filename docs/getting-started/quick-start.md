# Quick Start

Get vCon Server running in 5 minutes using Docker Compose.

## Prerequisites

- Docker and Docker Compose installed ([verify](requirements.md#verifying-requirements))
- Git installed
- Terminal access

## Step 1: Clone the Repository

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
```

## Step 2: Configure Environment

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required: Redis connection
REDIS_URL=redis://redis:6379

# Required: API authentication token
CONSERVER_API_TOKEN=your-secret-token-here

# Optional: AI service keys (for transcription/analysis)
DEEPGRAM_KEY=your-deepgram-key
OPENAI_API_KEY=your-openai-key
```

!!! tip "Generate a Secure Token"
    Generate a secure API token:
    ```bash
    openssl rand -hex 32
    ```

## Step 3: Start Services

```bash
# Create the Docker network
docker network create conserver

# Copy and customize the Docker Compose file
cp example_docker-compose.yml docker-compose.yml

# Build and start all services
docker compose up -d --build
```

## Step 4: Verify Installation

Check that services are running:

```bash
docker compose ps
```

Expected output:

```
NAME                SERVICE      STATUS
vcon-server-api-1   api          running
vcon-server-conserver-1  conserver   running
vcon-server-redis-1 redis        running
```

Check the API health:

```bash
curl http://localhost:8000/api/health
```

Expected response:

```json
{"status": "healthy"}
```

Check the version:

```bash
curl http://localhost:8000/api/version
```

## Step 5: Submit a Test vCon

Create a simple test vCon:

```bash
curl -X POST http://localhost:8000/api/vcon \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: your-secret-token-here" \
  -d '{
    "vcon": "0.0.1",
    "uuid": "test-vcon-001",
    "created_at": "2024-01-15T10:30:00Z",
    "parties": [
      {"tel": "+15551234567", "name": "John Doe"},
      {"tel": "+15559876543", "name": "Jane Smith"}
    ],
    "dialog": []
  }'
```

Retrieve the vCon:

```bash
curl http://localhost:8000/api/vcon/test-vcon-001 \
  -H "x-conserver-api-token: your-secret-token-here"
```

## Step 6: View Logs

Monitor the processing:

```bash
# View all logs
docker compose logs -f

# View only conserver logs
docker compose logs -f conserver

# View only API logs
docker compose logs -f api
```

## Basic Configuration

The default configuration in `example_config.yml` includes a sample processing chain:

```yaml
chains:
  sample_chain:
    links:
      - transcribe
      - analyze
      - tag
    storages:
      - redis_storage
    ingress_lists:
      - default
    enabled: 1
```

This chain:

1. Transcribes audio using the configured transcription service
2. Analyzes the transcript for insights
3. Applies tags based on analysis
4. Stores the result in Redis

## Common Operations

### Stop Services

```bash
docker compose down
```

### Restart Services

```bash
docker compose restart
```

### View Configuration

```bash
curl http://localhost:8000/api/config \
  -H "x-conserver-api-token: your-secret-token-here"
```

### Check Queue Status

```bash
# Connect to Redis and check queue lengths
docker compose exec redis redis-cli LLEN default
```

## Troubleshooting

### Services Won't Start

Check Docker logs:

```bash
docker compose logs
```

Common issues:

- Port 8000 already in use
- Redis connection failed
- Invalid API token format

### API Returns 403 Forbidden

Verify your API token:

```bash
# Check if token is set
echo $CONSERVER_API_TOKEN

# Ensure header matches
curl -H "x-conserver-api-token: $CONSERVER_API_TOKEN" ...
```

### vCon Not Processing

Check the conserver logs:

```bash
docker compose logs conserver
```

Verify the ingress list is configured in a chain:

```yaml
chains:
  my_chain:
    ingress_lists:
      - default  # Must match where you're sending vCons
```

## Next Steps

Now that you have vCon Server running:

1. **[Docker Installation](../installation/docker.md)**: Learn about all Docker options
2. **[Configuration Guide](../configuration/index.md)**: Customize your setup
3. **[API Reference](../operations/api-reference.md)**: Explore all API endpoints
4. **[Creating Chains](../configuration/chains-and-pipelines.md)**: Build custom processing pipelines

## Example: Complete Workflow

Here's a complete example that demonstrates the full workflow:

```bash
#!/bin/bash
# complete-workflow.sh

API_URL="http://localhost:8000/api"
TOKEN="your-secret-token-here"

# 1. Check health
echo "Checking health..."
curl -s "$API_URL/health"
echo

# 2. Create a vCon with audio reference
echo "Creating vCon..."
VCON_UUID=$(uuidgen)
curl -s -X POST "$API_URL/vcon?ingress_lists=default" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d "{
    \"vcon\": \"0.0.1\",
    \"uuid\": \"$VCON_UUID\",
    \"created_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
    \"parties\": [
      {\"tel\": \"+15551234567\", \"name\": \"Customer\"},
      {\"tel\": \"+15559876543\", \"name\": \"Agent\"}
    ],
    \"dialog\": []
  }"
echo

# 3. Wait for processing
echo "Waiting for processing..."
sleep 5

# 4. Retrieve processed vCon
echo "Retrieving processed vCon..."
curl -s "$API_URL/vcon/$VCON_UUID" \
  -H "x-conserver-api-token: $TOKEN" | jq .
```
