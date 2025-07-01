#!/bin/bash

# scripts/monitor-milvus.sh - Health monitoring for Milvus

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

MILVUS_HOST=${MILVUS_HOST:-localhost}
MILVUS_PORT=${MILVUS_PORT:-19530}
ALERT_WEBHOOK=${ALERT_WEBHOOK:-""}

check_milvus_health() {
    echo -e "${YELLOW}🔍 Checking Milvus health...${NC}"
    
    # Check HTTP health endpoint
    if curl -f -s "http://${MILVUS_HOST}:9091/healthz" > /dev/null; then
        echo -e "${GREEN}✅ Milvus HTTP health: OK${NC}"
        HTTP_HEALTHY=true
    else
        echo -e "${RED}❌ Milvus HTTP health: FAILED${NC}"
        HTTP_HEALTHY=false
    fi
    
    # Check Milvus connection with Python
    PYTHON_CHECK=$(python3 << EOF
try:
    from pymilvus import connections, utility
    connections.connect(host='${MILVUS_HOST}', port='${MILVUS_PORT}')
    version = utility.get_server_version()
    print(f"Connected to Milvus {version}")
    connections.disconnect('default')
    exit(0)
except Exception as e:
    print(f"Connection failed: {e}")
    exit(1)
EOF
)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Milvus connection: OK${NC}"
        echo "   $PYTHON_CHECK"
        CONNECTION_HEALTHY=true
    else
        echo -e "${RED}❌ Milvus connection: FAILED${NC}"
        echo "   $PYTHON_CHECK"
        CONNECTION_HEALTHY=false
    fi
}

check_performance() {
    echo -e "${YELLOW}⚡ Running performance check...${NC}"
    
    # Simple performance test
    PERF_RESULT=$(python3 << 'EOF'
import time
try:
    from pymilvus import connections, utility
    start_time = time.time()
    connections.connect(host='localhost', port='19530')
    utility.list_collections()
    response_time = time.time() - start_time
    connections.disconnect('default')
    print(f"{response_time:.3f}")
    exit(0)
except Exception as e:
    print("FAILED")
    exit(1)
EOF
)
    
    if [ "$PERF_RESULT" != "FAILED" ]; then
        echo -e "${GREEN}✅ Response time: ${PERF_RESULT}s${NC}"
        if (( $(echo "$PERF_RESULT > 1.0" | bc -l) )); then
            echo -e "${YELLOW}⚠️  Slow response time detected${NC}"
            PERFORMANCE_WARNING=true
        else
            PERFORMANCE_WARNING=false
        fi
    else
        echo -e "${RED}❌ Performance check failed${NC}"
        PERFORMANCE_WARNING=true
    fi
}

send_alert() {
    local message="$1"
    local severity="$2"
    
    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -X POST "$ALERT_WEBHOOK" \
             -H "Content-Type: application/json" \
             -d "{\"text\":\"🚨 Milvus Alert [$severity]: $message\"}" \
             -s > /dev/null
        echo -e "${YELLOW}📢 Alert sent: $message${NC}"
    else
        echo -e "${YELLOW}⚠️  Alert would be sent: $message${NC}"
    fi
}

generate_report() {
    echo ""
    echo -e "${GREEN}📊 Milvus Health Report${NC}"
    echo "=========================="
    echo "Timestamp: $(date)"
    echo "Host: ${MILVUS_HOST}:${MILVUS_PORT}"
    echo ""
    
    if [ "$HTTP_HEALTHY" = true ] && [ "$CONNECTION_HEALTHY" = true ]; then
        echo -e "Overall Status: ${GREEN}HEALTHY${NC}"
        
        if [ "$PERFORMANCE_WARNING" = true ]; then
            echo -e "Performance: ${YELLOW}WARNING${NC}"
            send_alert "Milvus performance degraded" "WARNING"
        else
            echo -e "Performance: ${GREEN}GOOD${NC}"
        fi
    else
        echo -e "Overall Status: ${RED}UNHEALTHY${NC}"
        send_alert "Milvus service is down" "CRITICAL"
        exit 1
    fi
}

# Main execution
check_milvus_health
check_performance
generate_report

echo -e "${GREEN}🎉 Health check completed${NC}"