# Monitor the server

This page shows how to check the server, publish its telemetry and alert on the failures that matter. The [metrics reference](../reference/metrics.md) lists every metric name, and the [environment reference](../reference/environment.md) lists every variable.

![Metrics, traces, errors and chain tracers leaving the API and worker processes, with the Redis reads behind them](../diagrams/D14-observability.svg)

## Check the server health

Three monitoring routes need no API token. The FastAPI `/docs`, `/redoc` and `/openapi.json` pages are also open. See the [API reference](../reference/api.md#monitor-the-server) for the responses.

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/version
curl "http://localhost:8000/api/stats/queue?list_name=default"
```

`/health` returns a fixed `healthy` status with the version details. It proves that the API process answers and nothing more. It does not touch Redis or the workers, so pair it with a queue depth check and a Redis check.

The version fields come from the image build. Outside a built image they read `dev` and `unknown`. Every API response also carries `X-Vcon-Server-Version` and `X-Vcon-Server-Commit` headers.

## Read the queue depth

| Queue | Redis list | Holds |
|---|---|---|
| Ingress | `<ingress_list>` | Ids waiting for a worker |
| Egress | `<egress_list>` | Processed ids awaiting pickup |
| Ingress DLQ | `DLQ:<ingress_list>` | Ids whose chain failed |
| Storage DLQ | `DLQ:storage:<storage_name>` | Ids whose write to one backend failed |

```bash
# Through the API, for any Redis list
curl "http://localhost:8000/api/stats/queue?list_name=DLQ:default"

# In Redis
docker compose exec redis redis-cli LLEN default

# Watch the depth over time
watch -n 5 'docker compose exec -T redis redis-cli LLEN default'
```

## Watch the key signals

Set thresholds from your own baseline. The [metrics reference](../reference/metrics.md) gives each metric's type and attributes.

| Signal | Metric | Watch for |
|---|---|---|
| Ingress depth | `conserver.ingress_list.length` with `kind="ingress"` | Sustained growth |
| Ingress DLQ depth | `conserver.ingress_list.length` with `kind="dlq"` | Anything above 0 |
| Storage DLQ growth | `conserver.dlq.count` with a `DLQ:storage:` queue name | Any increase |
| Chain time | `conserver.main_loop.vcon_processing_time` | A rising upper percentile |
| Throughput | `conserver.main_loop.count_vcons_processed` | A drop against the ingress rate |
| Link errors | `conserver.link.count` with `outcome="error"` | Any sustained rate |
| Storage errors | `conserver.storage.count` with `outcome="error"` | Any sustained rate |
| In-flight work | `conserver.vcons.inflight` | Stuck at the concurrency limit |
| Redis memory | `conserver.redis.memory_used_bytes` | Nearing the limit |

The depth gauge covers configured ingress lists and their DLQs. It does not sample storage DLQs, so read those through `/stats/queue` or with `LLEN`.

Take CPU, memory, disk and network figures from your container platform. The server does not publish them.

## Publish the telemetry

The server has two separate OpenTelemetry pipelines.

**Metrics** go through `common/lib/metrics.py`. They publish only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, and always over OTLP gRPC, whatever `OTEL_EXPORTER_OTLP_PROTOCOL` says. Each process exports with its own `service.instance.id`, so sum across instances for a total.

**Traces** come from `opentelemetry-instrument`, which wraps both processes in `docker-compose.yml`. Workers open one span per vCon, with `link.*` and `storage.*` children, and `init_tracing` adds OpenAI LLM spans. The API has only auto-instrumented request spans.

Set the endpoint in `.env`. `docker-compose.yml` passes the `OTEL_EXPORTER_OTLP_*` variables through.

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

`docker-compose.yml` sets `OTEL_SERVICE_NAME` to `conserver` and `api`, so a value in `.env` has no effect on those services. Outside Compose the metrics default is `vcon-server`.

### Run a collector

Add the collector to `docker-compose.yml`:

```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8889:8889"   # Prometheus scrape
    networks:
      - conserver
```

Then configure it. This example sends traces to Jaeger and exposes metrics for Prometheus.

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
  debug:

  otlp/jaeger:
    endpoint: jaeger:4317
    tls:
      insecure: true

  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/jaeger, debug]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

### Send traces to Langfuse

Langfuse accepts traces over OTLP HTTP. Metrics cannot follow, since the metrics exporter is gRPC only. If you want metrics too, use [a collector to fan out](#fan-out-to-several-backends).

In Langfuse, open the API keys page in its settings and copy your public and secret keys. Then build the auth header:

```bash
echo -n "pk-lf-YOUR_PUBLIC_KEY:sk-lf-YOUR_SECRET_KEY" | base64
```

Add these to `.env`:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://<your-langfuse-host>:3000/api/public/otel
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <output_from_above>
```

For Langfuse Cloud, use `https://cloud.langfuse.com/api/public/otel` as the endpoint.

Traces appear under the service names `conserver` and `api`.

For local testing, `docker-compose.yml` has a `langfuse` profile with development credentials. Its comments give the `.env` values. Never use those credentials in production.

### Fan out to several backends

The server points at one OTLP endpoint. To reach several backends, send everything to a collector and let it fan out. This example uses SigNoz over gRPC and Langfuse over HTTP, and the same pattern works with any two OTLP backends.

Point the server at the collector as shown in [Publish the telemetry](#publish-the-telemetry), with no auth header. The collector authenticates to each backend itself. Then configure the collector:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317

processors:
  batch:

exporters:
  otlp/signoz:
    endpoint: <your-signoz-host>:4317
    tls:
      insecure: true

  otlphttp/langfuse:
    endpoint: http://<your-langfuse-host>:3000/api/public/otel
    headers:
      Authorization: "Basic <base64_from_above>"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/signoz, otlphttp/langfuse]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/signoz]
```

Langfuse ingests only traces, so metrics go to SigNoz alone.

### Send telemetry to Datadog

The server has no Datadog library, so `DD_*` application settings do nothing. Send OTLP to a collector or to a Datadog Agent with OTLP intake enabled, and follow the Datadog documentation for that side.

## Scrape the metrics with Prometheus

The server exposes no metrics port of its own. Prometheus scrapes the collector.

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'vcon-server'
    static_configs:
      - targets: ['otel-collector:8889']
```

The collector's Prometheus exporter rewrites names. Dots become underscores and counters gain `_total`, so `conserver.dlq.count` becomes `conserver_dlq_count_total`. Attribute dots change too, so `chain.name` becomes `chain_name`. Check the names at `http://localhost:8889/metrics`, since exporter settings can change them.

<!-- TODO(verify): the Prometheus names below follow the collector's default naming and were not checked against a running collector. The conserver side of each name is confirmed in docs/reference/metrics.md. -->

```promql
# vCons finished per minute
sum(rate(conserver_main_loop_count_vcons_processed_total[5m])) * 60

# Share of link runs that failed
sum(rate(conserver_link_count_total{outcome="error"}[5m]))
  / sum(rate(conserver_link_count_total[5m]))

# 95th percentile chain time in seconds
histogram_quantile(0.95,
  sum by (le) (rate(conserver_main_loop_vcon_processing_time_bucket[5m])))

# Ingress depth. Each worker process reports the gauge, so take the maximum.
max by (ingress_list) (conserver_ingress_list_length{kind="ingress"})
```

## Build a Grafana dashboard

```json
{
  "dashboard": {
    "title": "vCon Server",
    "panels": [
      {
        "title": "Queue depth",
        "type": "timeseries",
        "targets": [
          {
            "expr": "max by (ingress_list) (conserver_ingress_list_length{kind=\"ingress\"})",
            "legendFormat": "{{ingress_list}}"
          }
        ]
      },
      {
        "title": "vCons per minute",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(rate(conserver_main_loop_count_vcons_processed_total[5m])) * 60"
          }
        ]
      },
      {
        "title": "DLQ items",
        "type": "stat",
        "targets": [
          {
            "expr": "sum(max by (ingress_list) (conserver_ingress_list_length{kind=\"dlq\"}))"
          }
        ]
      }
    ]
  }
}
```

## Write the alert rules

```yaml
# prometheus-alerts.yml
groups:
  - name: vcon-server
    rules:
      - alert: HighQueueDepth
        expr: max by (ingress_list) (conserver_ingress_list_length{kind="ingress"}) > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Queue depth is high"
          description: "Queue {{ $labels.ingress_list }} has {{ $value }} items"

      - alert: IngressDLQNotEmpty
        expr: max by (ingress_list) (conserver_ingress_list_length{kind="dlq"}) > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "An ingress DLQ has items"
          description: "DLQ for {{ $labels.ingress_list }} has {{ $value }} items"

      - alert: StorageDLQGrowing
        expr: sum by (queue_name) (increase(conserver_dlq_count_total{queue_name=~"DLQ:storage:.*"}[15m])) > 0
        labels:
          severity: warning
        annotations:
          summary: "Storage writes are failing"
          description: "{{ $labels.queue_name }} gained entries"

      - alert: HighLinkErrorRate
        expr: |
          sum(rate(conserver_link_count_total{outcome="error"}[5m]))
            / sum(rate(conserver_link_count_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High link error rate"
          description: "Error rate is {{ $value | humanizePercentage }}"
```

Treat 1000 items and 5% as examples. The `up` metric for this scrape job describes the collector, not the server, so probe `/health` with a blackbox check to catch a dead API. A stalled worker shows up as rising ingress depth.

### Route alerts to PagerDuty

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

## Report errors to Sentry

Set `SENTRY_DSN` and `ENV` to turn on Sentry for the conserver side. Logging at `ERROR` becomes an event, and `INFO` and above become breadcrumbs. The API process does not initialize Sentry. See the [environment reference](../reference/environment.md).

## Record chain events with a tracer

Tracers are separate from OpenTelemetry. Every entry under `tracers` in the config runs before the first link and after each link. The repo ships one, described in the [JLINC tracer reference](../reference/tracers/jlinc.md).

## Script a monitoring check

```bash
#!/bin/bash
# monitor.sh

API_URL="${API_URL:-http://localhost:8000/api}"
QUEUE="${QUEUE:-default}"
THRESHOLD_QUEUE=100

health=$(curl -s "$API_URL/health" | jq -r .status)
if [ "$health" != "healthy" ]; then
    echo "CRITICAL: API health check failed"
    exit 2
fi

redis_ping=$(docker compose exec -T redis redis-cli ping)
if [ "$redis_ping" != "PONG" ]; then
    echo "CRITICAL: Redis did not answer"
    exit 2
fi

queue_depth=$(curl -s "$API_URL/stats/queue?list_name=$QUEUE" | jq -r .depth)
if [ "$queue_depth" -gt "$THRESHOLD_QUEUE" ]; then
    echo "WARNING: Queue depth is $queue_depth (threshold: $THRESHOLD_QUEUE)"
    exit 1
fi

dlq_depth=$(curl -s "$API_URL/stats/queue?list_name=DLQ:$QUEUE" | jq -r .depth)
if [ "$dlq_depth" -gt 0 ]; then
    echo "WARNING: DLQ has $dlq_depth items"
    exit 1
fi

echo "OK: All checks passed"
```

## Ship the logs

See [Forward logs to an aggregator](logging.md#forward-logs-to-an-aggregator).

## Review the coverage

- Monitor each layer: the application, the host, Redis and your storage backends, and external services such as Deepgram and OpenAI.
- Alert on symptoms, and link a runbook from each alert. [Dead letter queues](dead-letter-queue.md) and [storage recovery](storage-recovery.md) are good targets.
- Review dashboards and thresholds on a regular schedule, and revisit capacity as volume changes.
