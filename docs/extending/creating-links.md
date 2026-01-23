# Creating Processing Links

Links are the building blocks of vCon processing pipelines. This guide covers creating custom links.

## Link Interface

Every link must implement the `run` function:

```python
def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> str | None:
    """
    Process a vCon.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance (from config)
        opts: Configuration options dictionary
        
    Returns:
        str: Return the vcon_uuid to continue the chain
        None: Return None to filter/stop the vCon
    """
```

## Directory Structure

```
server/links/
  my_link/
    __init__.py     # Required: contains run() and default_options
    README.md       # Optional: documentation
    tests/
      __init__.py
      test_my_link.py
```

## Basic Link Example

```python
# server/links/my_link/__init__.py

from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "tag_name": "processed",
    "tag_value": "true"
}

def run(vcon_uuid, link_name, opts=default_options):
    """Add a tag to the vCon."""
    logger.debug(f"Starting {link_name}::run for {vcon_uuid}")
    
    # Merge default options with provided options
    options = {**default_options, **opts}
    
    # Get vCon from Redis
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    if vcon is None:
        logger.error(f"vCon not found: {vcon_uuid}")
        return None
    
    # Process the vCon
    vcon.add_tag(
        tag_name=options["tag_name"],
        tag_value=options["tag_value"]
    )
    
    # Save changes back to Redis
    vcon_redis.store_vcon(vcon)
    
    logger.info(f"Completed {link_name}::run for {vcon_uuid}")
    return vcon_uuid
```

## Configuration

Register the link in `config.yml`:

```yaml
links:
  my_link:
    module: links.my_link
    options:
      tag_name: custom_tag
      tag_value: custom_value

chains:
  my_chain:
    links:
      - my_link
    storages:
      - redis_storage
    ingress_lists:
      - default
    enabled: 1
```

## Common Patterns

### Working with vCon Data

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    # Access basic properties
    uuid = vcon.uuid
    created_at = vcon.created_at
    
    # Access parties
    for party in vcon.parties:
        tel = party.get("tel")
        email = party.get("mailto")
        name = party.get("name")
    
    # Access dialog
    for dialog in vcon.dialog:
        dialog_type = dialog.get("type")  # "recording", "text", etc.
        start_time = dialog.get("start")
        parties = dialog.get("parties")
        body = dialog.get("body")  # Text content
        url = dialog.get("url")    # Audio/video URL
    
    # Access analysis
    for analysis in vcon.analysis:
        analysis_type = analysis.get("type")
        body = analysis.get("body")
        vendor = analysis.get("vendor")
    
    # Access attachments
    for attachment in vcon.attachments:
        filename = attachment.get("filename")
        content = attachment.get("body")
    
    return vcon_uuid
```

### Adding Analysis

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    # Perform analysis
    result = analyze_vcon(vcon)
    
    # Add analysis to vCon
    vcon.add_analysis(
        type="custom_analysis",
        body=result,
        vendor="my_company",
        dialog=0,  # Optional: index of dialog this applies to
        encoding="json"
    )
    
    vcon_redis.store_vcon(vcon)
    return vcon_uuid
```

### Adding Tags

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    # Add single tag
    vcon.add_tag("status", "processed")
    
    # Add multiple tags
    for tag in opts.get("tags", []):
        vcon.add_tag(tag["name"], tag["value"])
    
    vcon_redis.store_vcon(vcon)
    return vcon_uuid
```

### Filtering vCons

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    # Filter by duration
    min_duration = opts.get("min_duration", 60)
    if get_duration(vcon) < min_duration:
        logger.info(f"Filtering {vcon_uuid}: duration too short")
        return None  # Stop processing
    
    # Filter by party
    required_domain = opts.get("required_domain")
    if required_domain:
        has_domain = any(
            required_domain in p.get("mailto", "")
            for p in vcon.parties
        )
        if not has_domain:
            logger.info(f"Filtering {vcon_uuid}: missing required domain")
            return None
    
    return vcon_uuid  # Continue processing
```

### Calling External APIs

```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

default_options = {
    "api_url": "https://api.example.com/analyze",
    "api_key": "",
    "timeout": 30
}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, max=10)
)
def call_api(url, api_key, data, timeout):
    """Call external API with retry logic."""
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key}"},
        json=data,
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()

def run(vcon_uuid, link_name, opts=default_options):
    options = {**default_options, **opts}
    
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    # Call external API
    try:
        result = call_api(
            options["api_url"],
            options["api_key"],
            vcon.to_dict(),
            options["timeout"]
        )
    except requests.RequestException as e:
        logger.error(f"API call failed: {e}")
        raise  # Will send to DLQ
    
    # Add result to vCon
    vcon.add_analysis(type="external_analysis", body=result)
    vcon_redis.store_vcon(vcon)
    
    return vcon_uuid
```

### Routing to Different Queues

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    # Determine destination based on vCon properties
    destination = determine_destination(vcon, opts.get("rules", []))
    
    if destination:
        # Push to destination queue
        redis_client = vcon_redis.get_redis()
        redis_client.lpush(destination, vcon_uuid)
        logger.info(f"Routed {vcon_uuid} to {destination}")
    
    return vcon_uuid
```

## Error Handling

### Graceful Degradation

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    try:
        # Try primary processing
        result = primary_process(vcon)
    except PrimaryServiceError:
        logger.warning(f"Primary service failed, using fallback")
        try:
            # Try fallback
            result = fallback_process(vcon)
        except FallbackServiceError:
            logger.warning(f"Fallback failed, skipping processing")
            # Continue chain without this processing
            return vcon_uuid
    
    vcon.add_analysis(type="process_result", body=result)
    vcon_redis.store_vcon(vcon)
    return vcon_uuid
```

### DLQ vs Skip

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    try:
        process(vcon)
    except TemporaryError as e:
        # Temporary issue - skip this vCon
        logger.warning(f"Temporary error, skipping: {e}")
        return None  # Filter out, don't DLQ
    except PermanentError as e:
        # Permanent issue - needs investigation
        logger.error(f"Permanent error: {e}")
        raise  # Will go to DLQ
    except Exception as e:
        # Unknown error - DLQ for safety
        logger.error(f"Unknown error: {e}")
        raise
    
    return vcon_uuid
```

## Testing Links

### Unit Tests

```python
# server/links/my_link/tests/test_my_link.py

import pytest
from unittest.mock import MagicMock, patch

class TestMyLink:
    def test_run_adds_tag(self):
        """Test that run adds the expected tag."""
        with patch('server.links.my_link.VconRedis') as mock_redis_class:
            # Setup mock
            mock_vcon = MagicMock()
            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = mock_vcon
            mock_redis_class.return_value = mock_redis
            
            # Import and run
            from server.links.my_link import run
            result = run("test-uuid", "my_link", {"tag_name": "test", "tag_value": "value"})
            
            # Verify
            assert result == "test-uuid"
            mock_vcon.add_tag.assert_called_once_with("test", "value")
            mock_redis.store_vcon.assert_called_once_with(mock_vcon)
    
    def test_run_returns_none_when_vcon_not_found(self):
        """Test that run returns None when vCon doesn't exist."""
        with patch('server.links.my_link.VconRedis') as mock_redis_class:
            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = None
            mock_redis_class.return_value = mock_redis
            
            from server.links.my_link import run
            result = run("nonexistent-uuid", "my_link", {})
            
            assert result is None
    
    def test_run_uses_default_options(self):
        """Test that default options are used when not provided."""
        with patch('server.links.my_link.VconRedis') as mock_redis_class:
            mock_vcon = MagicMock()
            mock_redis = MagicMock()
            mock_redis.get_vcon.return_value = mock_vcon
            mock_redis_class.return_value = mock_redis
            
            from server.links.my_link import run, default_options
            run("test-uuid", "my_link", {})
            
            mock_vcon.add_tag.assert_called_once_with(
                default_options["tag_name"],
                default_options["tag_value"]
            )
```

### Integration Tests

```python
# server/links/my_link/tests/test_my_link_integration.py

import pytest

@pytest.mark.integration
class TestMyLinkIntegration:
    def test_full_processing(self, redis_client, sample_vcon):
        """Test full processing with real Redis."""
        from server.lib.vcon_redis import VconRedis
        from server.links.my_link import run
        
        # Setup
        vcon_redis = VconRedis()
        vcon_redis.store_vcon(sample_vcon)
        
        # Run
        result = run(sample_vcon.uuid, "my_link", {"tag_name": "test"})
        
        # Verify
        assert result == sample_vcon.uuid
        updated_vcon = vcon_redis.get_vcon(sample_vcon.uuid)
        assert any(t.get("name") == "test" for t in updated_vcon.tags)
```

## Best Practices

### 1. Always Use Default Options

```python
default_options = {
    "option1": "default_value",
    "option2": 100
}

def run(vcon_uuid, link_name, opts=default_options):
    options = {**default_options, **opts}  # Merge with provided
```

### 2. Use Logging Appropriately

```python
logger.debug("Detailed info for debugging")
logger.info("Normal operations")
logger.warning("Unexpected but handled")
logger.error("Failures", exc_info=True)  # Include traceback
```

### 3. Handle Missing Data Gracefully

```python
def run(vcon_uuid, link_name, opts=default_options):
    vcon = VconRedis().get_vcon(vcon_uuid)
    
    # Check for required data
    if not vcon.dialog:
        logger.info(f"No dialog in {vcon_uuid}, skipping")
        return vcon_uuid  # Continue but skip processing
```

### 4. Document Your Link

Create a README.md:

```markdown
# My Link

Processes vCons by adding custom tags.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| tag_name | string | "processed" | Name of tag to add |
| tag_value | string | "true" | Value of tag |

## Example Configuration

    links:
      my_link:
        module: links.my_link
        options:
          tag_name: custom
          tag_value: value
```

### 5. Keep Links Focused

Each link should do one thing well:

```python
# Good: Single responsibility
def run_transcribe(vcon_uuid, link_name, opts):
    # Only handles transcription
    
def run_analyze(vcon_uuid, link_name, opts):
    # Only handles analysis

# Bad: Multiple responsibilities
def run_do_everything(vcon_uuid, link_name, opts):
    # Transcribes AND analyzes AND routes AND stores
```
