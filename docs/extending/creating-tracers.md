# Creating Tracers

Tracers provide audit trails and event logging for vCon processing. This guide covers creating custom tracers.

## Tracer Interface

Tracers are called at key points during vCon processing:

```python
def trace(vcon_uuid: str, event: str, opts: dict = default_options) -> None:
    """
    Record a trace event.
    
    Args:
        vcon_uuid: UUID of the vCon being processed
        event: Event type (e.g., "chain_start", "chain_complete", "error")
        opts: Configuration options
    """
```

## Events

Tracers receive these events:

| Event | Description |
|-------|-------------|
| `chain_start` | vCon entered a processing chain |
| `link_start` | Processing link started |
| `link_complete` | Processing link completed |
| `link_error` | Processing link failed |
| `storage_start` | Storage operation started |
| `storage_complete` | Storage operation completed |
| `storage_error` | Storage operation failed |
| `chain_complete` | Chain processing completed |
| `chain_error` | Chain processing failed |

## Directory Structure

```
server/tracers/
  my_tracer/
    __init__.py     # Required: contains trace()
    README.md       # Optional: documentation
    tests/
      __init__.py
      test_my_tracer.py
```

## Basic Tracer Example

```python
# server/tracers/my_tracer/__init__.py

import json
from datetime import datetime
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "log_file": "/var/log/vcon/audit.log",
    "include_vcon_data": False
}

def trace(vcon_uuid, event, opts=default_options):
    """Log trace event to file."""
    options = {**default_options, **opts}
    
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "vcon_uuid": vcon_uuid,
        "event": event
    }
    
    if options.get("include_vcon_data"):
        from server.lib.vcon_redis import VconRedis
        vcon = VconRedis().get_vcon(vcon_uuid)
        if vcon:
            record["vcon_summary"] = {
                "parties": len(vcon.parties),
                "dialog_count": len(vcon.dialog)
            }
    
    with open(options["log_file"], "a") as f:
        f.write(json.dumps(record) + "\n")
    
    logger.debug(f"Traced {event} for {vcon_uuid}")
```

## Configuration

Register the tracer in `config.yml`:

```yaml
tracers:
  my_tracer:
    module: tracers.my_tracer
    options:
      log_file: /var/log/vcon/audit.log
      include_vcon_data: true

chains:
  audited_chain:
    links:
      - transcribe
    storages:
      - postgres
    tracers:
      - my_tracer
    ingress_lists:
      - default
    enabled: 1
```

## Common Patterns

### Database Audit Trail

```python
# server/tracers/db_audit/__init__.py

import psycopg2
from datetime import datetime
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "host": "localhost",
    "database": "audit",
    "user": "audit",
    "password": "",
    "table": "vcon_events"
}

def trace(vcon_uuid, event, opts=default_options):
    """Record event to audit database."""
    options = {**default_options, **opts}
    
    conn = psycopg2.connect(
        host=options["host"],
        database=options["database"],
        user=options["user"],
        password=options["password"]
    )
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {options['table']} 
                (vcon_uuid, event, timestamp, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    vcon_uuid,
                    event,
                    datetime.utcnow(),
                    json.dumps({"source": "vcon-server"})
                )
            )
        conn.commit()
    finally:
        conn.close()
    
    logger.debug(f"Recorded {event} for {vcon_uuid}")
```

### External Audit Service

```python
# server/tracers/external_audit/__init__.py

import requests
from datetime import datetime
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "api_url": "https://audit.example.com/events",
    "api_key": "",
    "system_id": "vcon-server"
}

def trace(vcon_uuid, event, opts=default_options):
    """Send event to external audit service."""
    options = {**default_options, **opts}
    
    payload = {
        "system_id": options["system_id"],
        "entity_id": vcon_uuid,
        "entity_type": "vcon",
        "event_type": event,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    try:
        response = requests.post(
            options["api_url"],
            headers={
                "Authorization": f"Bearer {options['api_key']}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=5
        )
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to send audit event: {e}")
        if options.get("dlq_vcon_on_error", False):
            raise
```

### Compliance Tracer

```python
# server/tracers/compliance/__init__.py

import hashlib
import json
from datetime import datetime
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "hash_algorithm": "sha256",
    "include_content_hash": True,
    "retention_policy": "7_years"
}

def trace(vcon_uuid, event, opts=default_options):
    """Create compliance-grade audit record."""
    options = {**default_options, **opts}
    
    record = {
        "record_id": f"{vcon_uuid}_{event}_{datetime.utcnow().timestamp()}",
        "vcon_uuid": vcon_uuid,
        "event": event,
        "timestamp": datetime.utcnow().isoformat(),
        "retention_policy": options["retention_policy"]
    }
    
    # Add content hash for integrity verification
    if options.get("include_content_hash") and event in ["chain_complete", "storage_complete"]:
        vcon = VconRedis().get_vcon(vcon_uuid)
        if vcon:
            content = vcon.dumps()
            hash_algo = hashlib.new(options["hash_algorithm"])
            hash_algo.update(content.encode())
            record["content_hash"] = hash_algo.hexdigest()
            record["hash_algorithm"] = options["hash_algorithm"]
    
    # Store record (implement based on your compliance requirements)
    _store_compliance_record(record, options)

def _store_compliance_record(record, options):
    """Store compliance record - implement based on requirements."""
    # Could be: immutable storage, blockchain, WORM storage, etc.
    logger.info(f"Compliance record: {json.dumps(record)}")
```

### Metrics Tracer

```python
# server/tracers/metrics/__init__.py

import time
from lib.logging_utils import init_logger

logger = init_logger(__name__)

# Track timing
_start_times = {}

default_options = {
    "statsd_host": "localhost",
    "statsd_port": 8125,
    "prefix": "vcon"
}

def trace(vcon_uuid, event, opts=default_options):
    """Record metrics to StatsD."""
    options = {**default_options, **opts}
    
    import statsd
    client = statsd.StatsClient(
        options["statsd_host"],
        options["statsd_port"],
        prefix=options["prefix"]
    )
    
    # Count events
    client.incr(f"events.{event}")
    
    # Track timing for paired events
    if event.endswith("_start"):
        _start_times[vcon_uuid] = time.time()
    elif event.endswith("_complete") or event.endswith("_error"):
        start_time = _start_times.pop(vcon_uuid, None)
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
            base_event = event.rsplit("_", 1)[0]
            client.timing(f"duration.{base_event}", duration_ms)
    
    # Track errors
    if event.endswith("_error"):
        client.incr("errors.total")
```

## Error Handling

### Fail-Safe Tracing

```python
def trace(vcon_uuid, event, opts=default_options):
    """Trace with fail-safe behavior."""
    options = {**default_options, **opts}
    
    try:
        _send_trace(vcon_uuid, event, options)
    except Exception as e:
        logger.error(f"Tracing failed: {e}")
        
        # Optionally send to DLQ
        if options.get("dlq_vcon_on_error", False):
            raise
        
        # Otherwise, log and continue
        # Processing continues even if tracing fails
```

### Async Tracing

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=5)

def trace(vcon_uuid, event, opts=default_options):
    """Non-blocking trace."""
    # Submit to thread pool, don't wait
    _executor.submit(_do_trace, vcon_uuid, event, opts)

def _do_trace(vcon_uuid, event, opts):
    """Actual tracing logic."""
    try:
        # ... tracing implementation ...
        pass
    except Exception as e:
        logger.error(f"Async trace failed: {e}")
```

## Testing Tracers

### Unit Tests

```python
# server/tracers/my_tracer/tests/test_my_tracer.py

import pytest
from unittest.mock import patch, mock_open
import json

class TestMyTracer:
    def test_trace_writes_to_file(self):
        """Test trace writes correct format."""
        with patch('builtins.open', mock_open()) as mock_file:
            from server.tracers.my_tracer import trace
            trace("test-uuid", "chain_start", {"log_file": "/tmp/test.log"})
            
            # Verify write was called
            mock_file.assert_called_with("/tmp/test.log", "a")
            
            # Verify content
            handle = mock_file()
            written = handle.write.call_args[0][0]
            record = json.loads(written.strip())
            
            assert record["vcon_uuid"] == "test-uuid"
            assert record["event"] == "chain_start"
            assert "timestamp" in record

    def test_trace_handles_errors(self):
        """Test trace handles write errors gracefully."""
        with patch('builtins.open', side_effect=IOError("Write failed")):
            from server.tracers.my_tracer import trace
            
            # Should not raise
            trace("test-uuid", "chain_start", {"log_file": "/invalid/path"})
```

## Best Practices

### 1. Keep Tracing Fast

```python
def trace(vcon_uuid, event, opts=default_options):
    # Avoid heavy processing in trace
    # Use async/background processing for heavy operations
```

### 2. Handle Failures Gracefully

```python
def trace(vcon_uuid, event, opts=default_options):
    try:
        _trace_impl(vcon_uuid, event, opts)
    except Exception as e:
        logger.error(f"Trace failed: {e}")
        # Don't let tracing failures break processing
```

### 3. Use Structured Data

```python
record = {
    "timestamp": datetime.utcnow().isoformat(),
    "vcon_uuid": vcon_uuid,
    "event": event,
    "metadata": {
        "chain": chain_name,
        "link": link_name
    }
}
```

### 4. Consider Retention

```python
default_options = {
    "retention_days": 90,
    "archive_after_days": 30
}
```

### 5. Document Requirements

```markdown
# My Tracer

Records audit events to external system.

## Requirements

- Network access to audit service
- API key with write permissions

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| api_url | string | Required | Audit service URL |
| api_key | string | Required | Authentication key |
```
