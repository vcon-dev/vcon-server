# Monitoring

This guide covers monitoring, observability, and alerting for vCon Server.

## Health Endpoints

### API Health

```bash
curl http://localhost:8000/api/health
```

Response:

```json
{"status": "healthy"}
```

### Version Information

```bash
curl http://localhost:8000/api/version
```

Response:

```json
{
  "version": "2024.01.15",
  "git_commit": "a1b2c3d",
  "build_time": "2024-01-15T10:30:00Z"
}
```

## Key Metrics

### Queue Metrics

| Metric | Command | Description |
|--------|---------|-------------|
| Ingress Depth | `LLEN {ingress_list}` | Items waiting to process |
| Egress Depth | `LLEN {egress_list}` | Processed items awaiting pickup |
| DLQ Depth | `LLEN DLQ:{ingress_list}` | Failed items |

```bash
# Check queue depths
docker compose exec redis redis-cli LLEN default
docker compose exec redis redis-cli LLEN DLQ:default

# Watch queue depth over time
watch -n 5 'docker compose exec -T redis redis-cli LLEN default'
```

### Processing Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Processing Rate | vCons/minute | Depends on volume |
| Processing Latency | Time per vCon | < 30s typical |
| Error Rate | Failed/Total | < 5% |
| DLQ Growth | New DLQ items/hour | 0 |

### Resource Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| CPU Usage | Container CPU % | > 80% |
| Memory Usage | Container memory | > 80% |
| Disk Usage | Storage volume | > 80% |
| Network I/O | Bytes in/out | Baseline + 50% |

## OpenTelemetry Integration

vCon Server includes OpenTelemetry instrumentation.

### Enable Tracing

```bash
# Environment variables
OTEL_SERVICE_NAME=vcon-server
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
```

### Docker Compose with Collector

```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
    networks:
      - conserver

  conserver:
    environment:
      - OTEL_SERVICE_NAME=vcon-server
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### Collector Configuration

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:

exporters:
  logging:
    loglevel: debug
  
  # Jaeger for traces
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  
  # Prometheus for metrics
  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [jaeger, logging]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

## Prometheus Integration

### Metrics Endpoint

If using OpenTelemetry with Prometheus exporter:

```bash
curl http://localhost:8889/metrics
```

### Prometheus Configuration

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'vcon-server'
    static_configs:
      - targets: ['otel-collector:8889']
    
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
```

### Key Prometheus Queries

```promql
# Processing rate (vCons per minute)
rate(vcon_processed_total[5m]) * 60

# Error rate
rate(vcon_processing_errors_total[5m]) / rate(vcon_processed_total[5m])

# Average processing duration
histogram_quantile(0.95, rate(vcon_processing_duration_seconds_bucket[5m]))

# Queue depth
redis_list_length{list="default"}
```

## Datadog Integration

### Agent Configuration

```yaml
# docker-compose.yml
services:
  datadog-agent:
    image: datadog/agent:latest
    environment:
      - DD_API_KEY=${DD_API_KEY}
      - DD_SITE=datadoghq.com
      - DD_APM_ENABLED=true
      - DD_LOGS_ENABLED=true
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /proc/:/host/proc/:ro
      - /sys/fs/cgroup/:/host/sys/fs/cgroup:ro
    networks:
      - conserver
```

### Application Configuration

```bash
# Enable Datadog APM
DD_AGENT_HOST=datadog-agent
DD_TRACE_ENABLED=true
DD_PROFILING_ENABLED=true
```

### Datadog Dashboards

Create dashboards for:

1. **Overview**: Health, version, uptime
2. **Processing**: Queue depths, throughput, latency
3. **Errors**: DLQ depth, error rates, error types
4. **Resources**: CPU, memory, network, disk

## Grafana Dashboards

### Sample Dashboard JSON

```json
{
  "dashboard": {
    "title": "vCon Server",
    "panels": [
      {
        "title": "Queue Depth",
        "type": "graph",
        "targets": [
          {
            "expr": "redis_list_length{list=~\"default|production\"}",
            "legendFormat": "{{list}}"
          }
        ]
      },
      {
        "title": "Processing Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(vcon_processed_total[5m]) * 60"
          }
        ]
      },
      {
        "title": "DLQ Items",
        "type": "stat",
        "targets": [
          {
            "expr": "redis_list_length{list=~\"DLQ:.*\"}"
          }
        ]
      }
    ]
  }
}
```

## Alerting

### Alert Rules

```yaml
# prometheus-alerts.yml
groups:
  - name: vcon-server
    rules:
      - alert: HighQueueDepth
        expr: redis_list_length{list="default"} > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Queue depth is high"
          description: "Queue {{ $labels.list }} has {{ $value }} items"

      - alert: DLQNotEmpty
        expr: redis_list_length{list=~"DLQ:.*"} > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DLQ has items"
          description: "DLQ {{ $labels.list }} has {{ $value }} items"

      - alert: HighErrorRate
        expr: rate(vcon_processing_errors_total[5m]) / rate(vcon_processed_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate"
          description: "Error rate is {{ $value | humanizePercentage }}"

      - alert: ServiceDown
        expr: up{job="vcon-server"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "vCon Server is down"
```

### PagerDuty Integration

```yaml
# alertmanager.yml
receivers:
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: ${PAGERDUTY_SERVICE_KEY}
        severity: '{{ .Labels.severity }}'

route:
  receiver: 'pagerduty'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty'
```

## Custom Monitoring Script

```bash
#!/bin/bash
# monitor.sh - Custom monitoring script

API_URL="${API_URL:-http://localhost:8000/api}"
TOKEN="${CONSERVER_API_TOKEN}"
THRESHOLD_QUEUE=100
THRESHOLD_DLQ=0

# Check API health
health=$(curl -s "$API_URL/health" | jq -r .status)
if [ "$health" != "healthy" ]; then
    echo "CRITICAL: API health check failed"
    exit 2
fi

# Check queue depth
queue_depth=$(docker compose exec -T redis redis-cli LLEN default)
if [ "$queue_depth" -gt "$THRESHOLD_QUEUE" ]; then
    echo "WARNING: Queue depth is $queue_depth (threshold: $THRESHOLD_QUEUE)"
    exit 1
fi

# Check DLQ
dlq_depth=$(docker compose exec -T redis redis-cli LLEN DLQ:default)
if [ "$dlq_depth" -gt "$THRESHOLD_DLQ" ]; then
    echo "WARNING: DLQ has $dlq_depth items"
    exit 1
fi

echo "OK: All checks passed"
exit 0
```

## Logging Integration

### Ship Logs to ELK

```yaml
# docker-compose.yml
services:
  conserver:
    logging:
      driver: "fluentd"
      options:
        fluentd-address: localhost:24224
        tag: vcon.server
```

### Ship Logs to CloudWatch

```yaml
services:
  conserver:
    logging:
      driver: "awslogs"
      options:
        awslogs-region: us-east-1
        awslogs-group: vcon-server
        awslogs-stream: "{{.Name}}"
```

## Best Practices

### 1. Monitor All Layers

- Application (processing rate, errors)
- Infrastructure (CPU, memory, disk)
- Dependencies (Redis, databases)
- External services (Deepgram, OpenAI)

### 2. Set Meaningful Alerts

- Alert on symptoms, not causes
- Use appropriate thresholds
- Include runbook links in alerts
- Avoid alert fatigue

### 3. Visualize Trends

- Historical processing rates
- Queue depth over time
- Error patterns
- Resource usage trends

### 4. Regular Review

- Weekly review of dashboards
- Monthly alert threshold review
- Quarterly capacity planning
