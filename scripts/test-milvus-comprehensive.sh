#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🧪 Comprehensive Milvus Integration Testing${NC}"
echo "=================================================="

# Parse command line arguments
INCLUDE_PERFORMANCE=false
KEEP_RUNNING=false
SHOW_UI=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --performance)
            INCLUDE_PERFORMANCE=true
            shift
            ;;
        --keep-running)
            KEEP_RUNNING=true
            shift
            ;;
        --ui)
            SHOW_UI=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --performance    Include performance tests"
            echo "  --keep-running   Keep services running after tests"
            echo "  --ui            Show UI information and pause"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Function to wait for service
wait_for_service() {
    local service_name=$1
    local check_command=$2
    local max_attempts=60
    local attempt=1

    echo -e "${YELLOW}⏳ Waiting for $service_name...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if eval $check_command >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        
        if [ $((attempt % 5)) -eq 0 ]; then
            echo "   Still waiting... (attempt $attempt/$max_attempts)"
        fi
        
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start${NC}"
    return 1
}

# Cleanup function
cleanup() {
    if [ "$KEEP_RUNNING" = false ]; then
        echo -e "${YELLOW}🧹 Cleaning up services...${NC}"
        docker-compose -f docker-compose.milvus.yml down -v >/dev/null 2>&1
        echo -e "${GREEN}✅ Cleanup complete${NC}"
    else
        echo -e "${BLUE}🔄 Services kept running as requested${NC}"
        echo "   Use 'docker-compose -f docker-compose.milvus.yml down -v' to stop"
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Start services
echo -e "${YELLOW}🐳 Starting Milvus services...${NC}"
docker-compose -f docker-compose.milvus.yml up -d

# Wait for services
wait_for_service "MinIO" "curl -f http://localhost:9000/minio/health/live"
wait_for_service "Milvus" "curl -f http://localhost:9091/healthz"

echo -e "${GREEN}🎉 All services are ready!${NC}"

# Set environment variables
export MILVUS_INTEGRATION_TESTS=true
export MILVUS_TEST_HOST=localhost
export MILVUS_TEST_PORT=19530

# Test Results Summary
BASIC_RESULT=0
ENHANCED_RESULT=0
PERFORMANCE_RESULT=0

# Run basic tests
echo -e "${BLUE}📋 Running basic connectivity tests...${NC}"
poetry run pytest server/storage/milvus/test_milvus_simple.py -v
BASIC_RESULT=$?

# Run enhanced tests if they exist
if [ -f "server/storage/milvus/test_milvus_enhanced.py" ]; then
    echo -e "${BLUE}🚀 Running enhanced vCon integration tests...${NC}"
    poetry run pytest server/storage/milvus/test_milvus_enhanced.py -v -m "not performance"
    ENHANCED_RESULT=$?
else
    echo -e "${YELLOW}⚠️  Enhanced tests not found (test_milvus_enhanced.py)${NC}"
fi

# Run performance tests if requested
if [ "$INCLUDE_PERFORMANCE" = true ]; then
    echo -e "${BLUE}⚡ Running performance tests...${NC}"
    if [ -f "server/storage/milvus/test_milvus_enhanced.py" ]; then
        poetry run pytest server/storage/milvus/test_milvus_enhanced.py -v -m "performance"
        PERFORMANCE_RESULT=$?
    else
        echo -e "${YELLOW}⚠️  Performance tests not found${NC}"
    fi
fi

# Show UI information if requested
if [ "$SHOW_UI" = true ]; then
    echo -e "${GREEN}🌐 Milvus Services Information:${NC}"
    echo "   Milvus API:     http://localhost:19530"
    echo "   Milvus Health:  http://localhost:9091/healthz"
    echo "   MinIO Console:  http://localhost:9001 (minioadmin/minioadmin)"
    echo "   Attu UI:        http://localhost:3000"
    echo ""
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read
fi

# Summary
echo ""
echo -e "${GREEN}📊 Test Results Summary${NC}"
echo "========================="

if [ $BASIC_RESULT -eq 0 ]; then
    echo -e "✅ Basic connectivity tests: ${GREEN}PASSED${NC}"
else
    echo -e "❌ Basic connectivity tests: ${RED}FAILED${NC}"
fi

if [ -f "server/storage/milvus/test_milvus_enhanced.py" ]; then
    if [ $ENHANCED_RESULT -eq 0 ]; then
        echo -e "✅ Enhanced vCon tests: ${GREEN}PASSED${NC}"
    else
        echo -e "❌ Enhanced vCon tests: ${RED}FAILED${NC}"
    fi
fi

if [ "$INCLUDE_PERFORMANCE" = true ]; then
    if [ $PERFORMANCE_RESULT -eq 0 ]; then
        echo -e "✅ Performance tests: ${GREEN}PASSED${NC}"
    else
        echo -e "❌ Performance tests: ${RED}FAILED${NC}"
    fi
fi

# Calculate overall result
OVERALL_RESULT=0
if [ $BASIC_RESULT -ne 0 ] || [ $ENHANCED_RESULT -ne 0 ] || [ $PERFORMANCE_RESULT -ne 0 ]; then
    OVERALL_RESULT=1
fi

if [ $OVERALL_RESULT -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed successfully!${NC}"
else
    echo -e "${RED}💥 Some tests failed${NC}"
fi

exit $OVERALL_RESULT