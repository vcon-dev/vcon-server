# Makefile for vcon-server

.PHONY: help test milvus-test milvus-test-enhanced milvus-test-perf milvus-up milvus-down milvus-status

# Default target
help:
	@echo "Available commands:"
	@echo "  test                 - Run all tests"
	@echo "  milvus-test         - Run basic Milvus integration tests"
	@echo "  milvus-test-enhanced - Run enhanced Milvus tests"
	@echo "  milvus-test-perf    - Run Milvus performance tests"
	@echo "  milvus-up           - Start Milvus services"
	@echo "  milvus-down         - Stop Milvus services"
	@echo "  milvus-status       - Check Milvus service status"

# Basic test target
test:
	@echo "🧪 Running all tests..."
	@poetry run pytest

# Basic Milvus integration test
milvus-test:
	@echo "🧪 Running basic Milvus integration tests..."
	@./scripts/test-milvus.sh

# Enhanced Milvus tests with vCon functionality
milvus-test-enhanced:
	@echo "🚀 Running enhanced Milvus integration tests..."
	@export MILVUS_INTEGRATION_TESTS=true && \
	docker-compose -f docker-compose.milvus.yml up -d && \
	sleep 60 && \
	poetry run pytest server/storage/milvus/test_milvus_enhanced.py -v -m "not performance" && \
	docker-compose -f docker-compose.milvus.yml down -v

# Performance tests
milvus-test-perf:
	@echo "⚡ Running Milvus performance tests..."
	@export MILVUS_INTEGRATION_TESTS=true && \
	docker-compose -f docker-compose.milvus.yml up -d && \
	sleep 60 && \
	poetry run pytest server/storage/milvus/test_milvus_enhanced.py -v -m "performance" && \
	docker-compose -f docker-compose.milvus.yml down -v

# Start Milvus services only
milvus-up:
	@echo "🐳 Starting Milvus services..."
	@docker-compose -f docker-compose.milvus.yml up -d
	@echo "⏳ Waiting for services to be ready..."
	@sleep 60
	@echo "✅ Milvus services ready at:"
	@echo "   - Milvus API: http://localhost:19530"
	@echo "   - Health check: http://localhost:9091/healthz"
	@echo "   - MinIO console: http://localhost:9001"

# Stop Milvus services
milvus-down:
	@echo "🛑 Stopping Milvus services..."
	@docker-compose -f docker-compose.milvus.yml down -v

# Check Milvus service status
milvus-status:
	@echo "📊 Milvus service status:"
	@docker ps --filter "name=milvus" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "No Milvus containers running"
	@echo ""
	@echo "🔍 Health checks:"
	@curl -s http://localhost:9091/healthz >/dev/null && echo "✅ Milvus: Healthy" || echo "❌ Milvus: Not available"
	@curl -s http://localhost:9000/minio/health/live >/dev/null && echo "✅ MinIO: Healthy" || echo "❌ MinIO: Not available"
