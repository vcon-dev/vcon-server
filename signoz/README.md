# SigNoz Observability Stack for vcon-server

This directory contains the configuration for SigNoz, a self-hosted observability platform that collects traces, metrics, and logs from the vcon-mcp server via OpenTelemetry.

## Architecture

```
┌─────────────────┐     OTLP/HTTP      ┌──────────────────────┐
│    vcon-mcp     │ ─────────────────► │  signoz-otel-collector│
│  (instrumented) │     :4318          │     (OTLP receiver)   │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                                  ▼
┌─────────────────┐                    ┌──────────────────────┐
│  signoz (UI)    │ ◄────────────────► │  signoz-clickhouse   │
│    :3301        │      TCP :9000     │   (time-series DB)   │
└─────────────────┘                    └──────────┬───────────┘
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │  signoz-zookeeper    │
                                       │   (coordination)     │
                                       └──────────────────────┘
```

## Components

| Service | Image | Purpose | Ports |
|---------|-------|---------|-------|
| signoz | `signoz/query-service:latest` | Query API + Web UI | 3301 (mapped from 8080) |
| signoz-otel-collector | `signoz/signoz-otel-collector:latest` | OTLP ingestion | 4317 (gRPC), 4318 (HTTP) |
| signoz-clickhouse | `clickhouse/clickhouse-server:24.1.2-alpine` | Time-series storage | 8123, 9000 (internal) |
| signoz-zookeeper | `zookeeper:3.9` | ClickHouse coordination | 2181 (internal) |

## Configuration Files

### otel-collector-config.yaml
OpenTelemetry Collector pipeline configuration:
- **Receivers**: OTLP gRPC (4317) and HTTP (4318)
- **Processors**: Batch processing
- **Exporters**: ClickHouse for traces, metrics, and logs

### zz-clickhouse-config.xml
ClickHouse server configuration:
- IPv4 listening (0.0.0.0)
- Single-node cluster named "cluster" (required by SigNoz schema migrator)
- ZooKeeper integration for distributed DDL

### clickhouse-users.xml
ClickHouse user permissions with default user having full access.

### alertmanager.yml
Basic alertmanager configuration (not currently active).

## Usage

### Start with SigNoz

```bash
cd /home/thomas/bds/vcon-dev/vcon-server
docker compose -f docker-compose.yml -f docker-compose.override.yml -f docker-compose.signoz.yml up -d
```

### Start without SigNoz (normal operation)

```bash
cd /home/thomas/bds/vcon-dev/vcon-server
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

### Stop SigNoz only

```bash
docker compose -f docker-compose.signoz.yml down
```

### Access the UI

Open http://localhost:3301 in your browser.

## First-Time Setup

After starting SigNoz for the first time, run the schema migrations:

```bash
docker run --rm --network conserver \
  signoz/signoz-schema-migrator:latest \
  sync --dsn='tcp://signoz-clickhouse:9000'
```

Note: Some migrations may fail due to JSON type syntax incompatibility with ClickHouse 24.1. Core functionality still works.

## vcon-mcp Integration

The vcon-mcp service is configured with these environment variables in `docker-compose.override.yml`:

```yaml
environment:
  OTEL_ENABLED: "true"
  OTEL_EXPORTER_TYPE: otlp
  OTEL_ENDPOINT: http://signoz-otel-collector:4318
  OTEL_SERVICE_NAME: vcon-mcp-server
```

## Verification

1. Check service health:
   ```bash
   curl http://localhost:3301/api/v1/health
   # Returns: {"status":"ok"}
   ```

2. Check container status:
   ```bash
   docker ps | grep signoz
   ```

3. View collector logs:
   ```bash
   docker logs signoz-otel-collector
   ```

## Troubleshooting

### ClickHouse won't start
- Check if port 9000 is in use
- Verify zookeeper is healthy first
- Check logs: `docker logs signoz-clickhouse`

### OTEL Collector errors
- Ensure ClickHouse is healthy before starting collector
- Verify schema migrations have run
- Check config syntax: `docker logs signoz-otel-collector`

### No data in UI
- Verify vcon-mcp is sending data (check its logs for OTEL export messages)
- Ensure collector is receiving data: check collector metrics at port 8888
- Verify ClickHouse tables exist: `docker exec signoz-clickhouse clickhouse-client --query "SHOW TABLES FROM signoz_traces"`

### Port conflicts
- Default ports: 3301 (UI), 4317 (gRPC), 4318 (HTTP)
- Change in docker-compose.signoz.yml if needed

## Known Issues

1. **Schema Migration Failures**: Some newer SigNoz migrations use JSON column types with syntax not supported in ClickHouse 24.1.2. Core observability works but some advanced features may be limited.

2. **Alertmanager**: Not configured for this deployment. Would require additional setup for alerts.

3. **Health Check Timing**: The OTEL collector health check may show "starting" for extended periods but the service is functional.

## Future Improvements

- Upgrade ClickHouse to latest version for full schema compatibility
- Add alertmanager configuration for alerts
- Configure data retention policies
- Add authentication to SigNoz UI
- Set up dashboards for vcon-mcp metrics

## Data Persistence

Data is stored in Docker volumes:
- `signoz_clickhouse_data` - Traces, metrics, logs
- `signoz_zookeeper_data` - ZooKeeper state
- `signoz_data` - SigNoz query service state

To reset all data:
```bash
docker compose -f docker-compose.signoz.yml down -v
```

## Resources

- [SigNoz Documentation](https://signoz.io/docs/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [ClickHouse Documentation](https://clickhouse.com/docs/)
