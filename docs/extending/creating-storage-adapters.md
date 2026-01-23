# Creating Storage Adapters

Storage adapters persist vCons to external systems. This guide covers creating custom storage adapters.

## Storage Interface

Storage adapters implement these functions:

```python
def save(vcon_uuid: str, opts: dict = default_options) -> None:
    """Save a vCon to storage."""

def get(vcon_uuid: str, opts: dict = default_options) -> dict | None:
    """Retrieve a vCon from storage. Returns None if not found."""

def delete(vcon_uuid: str, opts: dict = default_options) -> bool:
    """Delete a vCon from storage. Returns True if deleted."""
```

Only `save` is required. `get` and `delete` are optional.

## Directory Structure

```
server/storage/
  my_storage/
    __init__.py     # Required: contains save(), get(), delete()
    README.md       # Optional: documentation
    tests/
      __init__.py
      test_my_storage.py
```

## Basic Storage Example

```python
# server/storage/my_storage/__init__.py

import json
import os
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "path": "/data/vcons",
    "file_extension": ".json"
}

def save(vcon_uuid, opts=default_options):
    """Save vCon to file system."""
    options = {**default_options, **opts}
    
    # Get vCon from Redis
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    if vcon is None:
        logger.error(f"vCon not found: {vcon_uuid}")
        raise ValueError(f"vCon not found: {vcon_uuid}")
    
    # Ensure directory exists
    os.makedirs(options["path"], exist_ok=True)
    
    # Write to file
    file_path = os.path.join(
        options["path"],
        f"{vcon_uuid}{options['file_extension']}"
    )
    
    with open(file_path, 'w') as f:
        json.dump(vcon.to_dict(), f, indent=2)
    
    logger.info(f"Saved {vcon_uuid} to {file_path}")

def get(vcon_uuid, opts=default_options):
    """Retrieve vCon from file system."""
    options = {**default_options, **opts}
    
    file_path = os.path.join(
        options["path"],
        f"{vcon_uuid}{options['file_extension']}"
    )
    
    if not os.path.exists(file_path):
        logger.debug(f"vCon not found: {file_path}")
        return None
    
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    logger.debug(f"Retrieved {vcon_uuid} from {file_path}")
    return data

def delete(vcon_uuid, opts=default_options):
    """Delete vCon from file system."""
    options = {**default_options, **opts}
    
    file_path = os.path.join(
        options["path"],
        f"{vcon_uuid}{options['file_extension']}"
    )
    
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"Deleted {vcon_uuid} from {file_path}")
        return True
    
    return False
```

## Configuration

Register the storage in `config.yml`:

```yaml
storages:
  my_storage:
    module: storage.my_storage
    options:
      path: /data/custom_vcons
      file_extension: .vcon.json

chains:
  my_chain:
    links:
      - transcribe
    storages:
      - my_storage
    ingress_lists:
      - default
    enabled: 1
```

## Common Patterns

### Database Storage

```python
# server/storage/my_database/__init__.py

import psycopg2
from contextlib import contextmanager
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "host": "localhost",
    "port": 5432,
    "database": "vcons",
    "user": "vcon",
    "password": ""
}

@contextmanager
def get_connection(opts):
    """Context manager for database connections."""
    conn = psycopg2.connect(
        host=opts["host"],
        port=opts["port"],
        database=opts["database"],
        user=opts["user"],
        password=opts["password"]
    )
    try:
        yield conn
    finally:
        conn.close()

def save(vcon_uuid, opts=default_options):
    """Save vCon to database."""
    options = {**default_options, **opts}
    
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    with get_connection(options) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO vcons (uuid, data, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (uuid) DO UPDATE SET data = %s
                """,
                (vcon_uuid, vcon.dumps(), vcon.created_at, vcon.dumps())
            )
        conn.commit()
    
    logger.info(f"Saved {vcon_uuid} to database")

def get(vcon_uuid, opts=default_options):
    """Retrieve vCon from database."""
    options = {**default_options, **opts}
    
    with get_connection(options) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM vcons WHERE uuid = %s",
                (vcon_uuid,)
            )
            row = cur.fetchone()
    
    if row:
        import json
        return json.loads(row[0])
    return None

def delete(vcon_uuid, opts=default_options):
    """Delete vCon from database."""
    options = {**default_options, **opts}
    
    with get_connection(options) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM vcons WHERE uuid = %s",
                (vcon_uuid,)
            )
            deleted = cur.rowcount > 0
        conn.commit()
    
    return deleted
```

### API Storage

```python
# server/storage/api_storage/__init__.py

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "base_url": "https://api.example.com",
    "api_key": "",
    "timeout": 30
}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10)
)
def _make_request(method, url, **kwargs):
    """Make HTTP request with retry."""
    response = requests.request(method, url, **kwargs)
    response.raise_for_status()
    return response

def save(vcon_uuid, opts=default_options):
    """Save vCon via API."""
    options = {**default_options, **opts}
    
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    _make_request(
        "POST",
        f"{options['base_url']}/vcons",
        headers={
            "Authorization": f"Bearer {options['api_key']}",
            "Content-Type": "application/json"
        },
        json=vcon.to_dict(),
        timeout=options["timeout"]
    )
    
    logger.info(f"Saved {vcon_uuid} via API")

def get(vcon_uuid, opts=default_options):
    """Retrieve vCon via API."""
    options = {**default_options, **opts}
    
    try:
        response = _make_request(
            "GET",
            f"{options['base_url']}/vcons/{vcon_uuid}",
            headers={"Authorization": f"Bearer {options['api_key']}"},
            timeout=options["timeout"]
        )
        return response.json()
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return None
        raise

def delete(vcon_uuid, opts=default_options):
    """Delete vCon via API."""
    options = {**default_options, **opts}
    
    try:
        _make_request(
            "DELETE",
            f"{options['base_url']}/vcons/{vcon_uuid}",
            headers={"Authorization": f"Bearer {options['api_key']}"},
            timeout=options["timeout"]
        )
        return True
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return False
        raise
```

### Cloud Storage (S3-Compatible)

```python
# server/storage/cloud_storage/__init__.py

import boto3
import json
from botocore.exceptions import ClientError
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "bucket": "vcons",
    "prefix": "",
    "region": "us-east-1",
    "access_key": "",
    "secret_key": "",
    "endpoint_url": None  # For S3-compatible services
}

def _get_client(opts):
    """Get S3 client."""
    return boto3.client(
        's3',
        region_name=opts["region"],
        aws_access_key_id=opts["access_key"],
        aws_secret_access_key=opts["secret_key"],
        endpoint_url=opts.get("endpoint_url")
    )

def _get_key(vcon_uuid, opts):
    """Get S3 key for vCon."""
    prefix = opts.get("prefix", "")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return f"{prefix}{vcon_uuid}.json"

def save(vcon_uuid, opts=default_options):
    """Save vCon to S3."""
    options = {**default_options, **opts}
    
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    client = _get_client(options)
    key = _get_key(vcon_uuid, options)
    
    client.put_object(
        Bucket=options["bucket"],
        Key=key,
        Body=json.dumps(vcon.to_dict()),
        ContentType="application/json"
    )
    
    logger.info(f"Saved {vcon_uuid} to s3://{options['bucket']}/{key}")

def get(vcon_uuid, opts=default_options):
    """Retrieve vCon from S3."""
    options = {**default_options, **opts}
    
    client = _get_client(options)
    key = _get_key(vcon_uuid, options)
    
    try:
        response = client.get_object(
            Bucket=options["bucket"],
            Key=key
        )
        return json.loads(response['Body'].read())
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise

def delete(vcon_uuid, opts=default_options):
    """Delete vCon from S3."""
    options = {**default_options, **opts}
    
    client = _get_client(options)
    key = _get_key(vcon_uuid, options)
    
    try:
        client.delete_object(
            Bucket=options["bucket"],
            Key=key
        )
        return True
    except ClientError:
        return False
```

## Error Handling

### Connection Errors

```python
def save(vcon_uuid, opts=default_options):
    options = {**default_options, **opts}
    
    try:
        # Attempt to save
        _save_to_backend(vcon_uuid, options)
    except ConnectionError as e:
        logger.error(f"Connection failed: {e}")
        raise  # Will cause retry or DLQ
    except TimeoutError as e:
        logger.error(f"Timeout: {e}")
        raise
```

### Partial Failures

When using multiple storages with parallel writes, handle individual failures:

```python
def save(vcon_uuid, opts=default_options):
    options = {**default_options, **opts}
    
    try:
        _save_to_backend(vcon_uuid, options)
    except Exception as e:
        # Log but don't raise - other storages can continue
        logger.error(f"Storage failed for {vcon_uuid}: {e}")
        # Optionally: record failure for later retry
        _record_failure(vcon_uuid, str(e))
```

## Testing Storage Adapters

### Unit Tests

```python
# server/storage/my_storage/tests/test_my_storage.py

import pytest
from unittest.mock import MagicMock, patch, mock_open
import json

class TestMyStorage:
    def test_save_creates_file(self):
        """Test save creates file with correct content."""
        mock_vcon = MagicMock()
        mock_vcon.to_dict.return_value = {"uuid": "test-123"}
        
        with patch('server.storage.my_storage.VconRedis') as mock_redis_class:
            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = mock_vcon
            mock_redis_class.return_value = mock_redis
            
            with patch('builtins.open', mock_open()) as mock_file:
                with patch('os.makedirs'):
                    from server.storage.my_storage import save
                    save("test-123", {"path": "/tmp/test"})
                    
                    # Verify file was written
                    mock_file.assert_called_once()
                    handle = mock_file()
                    written_data = ''.join(
                        call.args[0] for call in handle.write.call_args_list
                    )
                    assert "test-123" in written_data

    def test_get_returns_none_for_missing_file(self):
        """Test get returns None when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            from server.storage.my_storage import get
            result = get("nonexistent", {"path": "/tmp/test"})
            assert result is None

    def test_delete_removes_file(self):
        """Test delete removes existing file."""
        with patch('os.path.exists', return_value=True):
            with patch('os.remove') as mock_remove:
                from server.storage.my_storage import delete
                result = delete("test-123", {"path": "/tmp/test"})
                
                assert result is True
                mock_remove.assert_called_once()
```

### Integration Tests

```python
@pytest.mark.integration
class TestMyStorageIntegration:
    def test_save_and_get(self, temp_directory):
        """Test full save and get cycle."""
        from server.storage.my_storage import save, get
        
        # Setup test vCon in Redis
        # ... (requires running Redis)
        
        opts = {"path": temp_directory}
        
        # Save
        save("test-uuid", opts)
        
        # Verify file exists
        import os
        assert os.path.exists(f"{temp_directory}/test-uuid.json")
        
        # Get
        result = get("test-uuid", opts)
        assert result is not None
        assert result["uuid"] == "test-uuid"
```

## Best Practices

### 1. Use Connection Pooling

```python
from contextlib import contextmanager
from some_db import ConnectionPool

_pool = None

def _get_pool(opts):
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            host=opts["host"],
            max_connections=10
        )
    return _pool

@contextmanager
def get_connection(opts):
    pool = _get_pool(opts)
    conn = pool.get()
    try:
        yield conn
    finally:
        pool.release(conn)
```

### 2. Implement Idempotent Saves

```python
def save(vcon_uuid, opts=default_options):
    # Use upsert pattern
    # If vCon exists, update it
    # If not, insert it
```

### 3. Handle Large vCons

```python
def save(vcon_uuid, opts=default_options):
    vcon = VconRedis().get_vcon(vcon_uuid)
    
    # Check size
    data = vcon.dumps()
    if len(data) > opts.get("max_size", 10_000_000):
        logger.warning(f"vCon {vcon_uuid} exceeds max size")
        # Handle: compress, split, or reject
```

### 4. Add Metadata

```python
def save(vcon_uuid, opts=default_options):
    vcon = VconRedis().get_vcon(vcon_uuid)
    
    metadata = {
        "uuid": vcon_uuid,
        "created_at": vcon.created_at,
        "stored_at": datetime.utcnow().isoformat(),
        "storage_version": "1.0"
    }
    
    # Store with metadata
```

### 5. Document Your Storage

```markdown
# My Storage Adapter

Stores vCons in a custom backend.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| path | string | /data/vcons | Storage path |

## Setup

1. Create directory: `mkdir -p /data/vcons`
2. Set permissions: `chmod 755 /data/vcons`

## Example

    storages:
      my_storage:
        module: storage.my_storage
        options:
          path: /data/custom
```
