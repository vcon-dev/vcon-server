#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Milvus Integration Test Setup ===${NC}"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command -v docker compose >/dev/null 2>&1; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

# Check if docker-compose.milvus.yml exists
if [ ! -f "docker-compose.milvus.yml" ]; then
    echo -e "${RED}Error: docker-compose.milvus.yml not found${NC}"
    echo -e "${YELLOW}Creating docker-compose.milvus.yml...${NC}"
    
    cat > docker-compose.milvus.yml << 'COMPOSE_EOF'
services:
  etcd:
    container_name: milvus-etcd
    image: quay.io/coreos/etcd:v3.5.5
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
      - ETCD_SNAPSHOT_COUNT=50000
    volumes:
      - etcd_data:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd

  minio:
    container_name: milvus-minio
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    environment:
      MINIO_ACCESS_KEY: minioadmin
      MINIO_SECRET_KEY: minioadmin
    ports:
      - "9001:9001"
      - "9000:9000"
    volumes:
      - minio_data:/data
    command: minio server /data --console-address ":9001"

  milvus:
    container_name: milvus-standalone
    image: milvusdb/milvus:v2.4.15
    command: ["milvus", "run", "standalone"]
    security_opt:
    - seccomp:unconfined
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - milvus_data:/var/lib/milvus
    ports:
      - "19530:19530"
      - "9091:9091"
    depends_on:
      - "etcd"
      - "minio"

volumes:
  etcd_data:
  minio_data:
  milvus_data:
COMPOSE_EOF
    
    echo -e "${GREEN}Created docker-compose.milvus.yml${NC}"
fi

# Function to wait for service with custom timeout (macOS compatible)
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local max_attempts=60  # 60 * 5 = 5 minutes
    local attempt=1

    echo -e "${YELLOW}Waiting for $service_name to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if eval $check_command >/dev/null 2>&1; then
            echo -e "${GREEN}$service_name is ready!${NC}"
            return 0
        fi
        
        echo "Attempt $attempt/$max_attempts: $service_name not ready yet..."
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}Error: $service_name failed to start within expected time${NC}"
    return 1
}

# Start Milvus services
echo -e "${YELLOW}Starting Milvus services...${NC}"
docker compose -f docker-compose.milvus.yml up -d

# Wait for each service individually
wait_for_service "MinIO" "curl -f http://localhost:9000/minio/health/live"
wait_for_service "Milvus" "curl -f http://localhost:9091/healthz"

echo -e "${GREEN}All services are ready!${NC}"

# Set environment variables for tests
export MILVUS_INTEGRATION_TESTS=true
export MILVUS_TEST_HOST=localhost
export MILVUS_TEST_PORT=19530

# Run integration tests
echo -e "${YELLOW}Running Milvus integration tests...${NC}"
poetry run pytest server/storage/milvus/test_milvus_integration.py -v

test_result=$?

if [ $test_result -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
fi

# Optional: Show Milvus info
if [ "$1" = "--info" ]; then
    echo -e "${GREEN}Milvus services info:${NC}"
    echo "  Milvus API: http://localhost:19530"
    echo "  Milvus Health: http://localhost:9091/healthz"
    echo "  MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
    echo ""
    echo -e "${YELLOW}Press Enter to continue with cleanup, or Ctrl+C to keep services running...${NC}"
    read
fi

# Cleanup
echo -e "${YELLOW}Cleaning up services...${NC}"
docker compose -f docker-compose.milvus.yml down -v
echo -e "${GREEN}Cleanup complete!${NC}"

exit $test_result