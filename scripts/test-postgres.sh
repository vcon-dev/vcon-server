#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== PostgreSQL Integration Test Setup ===${NC}"

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

# Check if docker-compose.postgres.yml exists
if [ ! -f "docker-compose.postgres.yml" ]; then
    echo -e "${RED}Error: docker-compose.postgres.yml not found${NC}"
    exit 1
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

# Start PostgreSQL services
echo -e "${YELLOW}Starting PostgreSQL services...${NC}"
docker compose -f docker-compose.postgres.yml up -d

# Wait for PostgreSQL to be ready
wait_for_service "PostgreSQL" "docker exec vcon-postgres pg_isready -U vcon_user -d vcon_db"

echo -e "${GREEN}PostgreSQL is ready!${NC}"

# Set environment variables for tests
export POSTGRES_INTEGRATION_TESTS=true
export POSTGRES_TEST_HOST=localhost
export POSTGRES_TEST_PORT=5433
export POSTGRES_TEST_USER=vcon_user
export POSTGRES_TEST_PASSWORD=vcon_password
export POSTGRES_TEST_DB=vcon_db

# Run integration tests
echo -e "${YELLOW}Running PostgreSQL integration tests...${NC}"
poetry run pytest server/storage/postgres/test_postgres_integration.py -v

test_result=$?

if [ $test_result -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed${NC}"
fi

# Optional: Show PostgreSQL info
if [ "$1" = "--info" ]; then
    echo -e "${GREEN}PostgreSQL services info:${NC}"
    echo "  PostgreSQL: localhost:5433"
    echo "  Database: vcon_db"
    echo "  User: vcon_user"
    echo "  PgAdmin: http://localhost:8080 (admin@vcon.local/admin)"
    echo ""
    echo -e "${YELLOW}Press Enter to continue with cleanup, or Ctrl+C to keep services running...${NC}"
    read
fi

# Cleanup
echo -e "${YELLOW}Cleaning up services...${NC}"
docker compose -f docker-compose.postgres.yml down -v
echo -e "${GREEN}Cleanup complete!${NC}"

exit $test_result