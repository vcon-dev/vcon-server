# Implementing New Modules for vCon Server

This guide provides instructions for extending vcon-server with custom Links and Storage modules.

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Implementing a Link Module](#implementing-a-link-module)
  - [Link Module Requirements](#link-module-requirements)
  - [Link Module Structure](#link-module-structure)
  - [Link Module Example](#link-module-example)
  - [Testing a Link Module](#testing-a-link-module)
- [Implementing a Storage Module](#implementing-a-storage-module)
  - [Storage Module Requirements](#storage-module-requirements)
  - [Storage Module Structure](#storage-module-structure)
  - [Storage Module Example](#storage-module-example)
  - [Testing a Storage Module](#testing-a-storage-module)
- [Configuration and Integration](#configuration-and-integration)
- [Best Practices](#best-practices)

## Overview

vcon-server is a modular system for processing vCons (Virtual Conversation Objects) with two main types of extension points:

1. **Link Modules**: Process vCons in a chain, performing operations like transcription, analysis, data enrichment, and filtering.
2. **Storage Modules**: Store vCons in different backends (databases, object stores, etc.).

Each module type follows a specific interface pattern and is dynamically loaded at runtime based on configuration.

## Project Structure

```
server/
├── links/                 # Link modules directory
│   ├── analyze/           # Analyze link example
│   ├── deepgram/          # Deepgram transcription link
│   ├── groq_whisper/      # Groq Whisper link
│   └── ...
├── storage/               # Storage modules directory
│   ├── base.py            # Base storage interface
│   ├── s3/                # S3 storage module
│   ├── postgres/          # PostgreSQL storage module
│   ├── mongo/             # MongoDB storage module
│   └── ...
```

## Implementing a Link Module

Links process vCons sequentially in a chain, with each link getting a chance to modify the vCon or decide if it should continue through the chain.

### Link Module Requirements

1. Each link module must be in its own directory under `server/links/`.
2. Link modules must implement a `run(vcon_uuid, link_name, opts=default_options)` function.
3. Links should return:
   - The vCon UUID if processing should continue to the next link
   - `None` if processing should stop for this vCon

### Link Module Structure

```python
# Required imports
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

# Initialize logger
logger = init_logger(__name__)

# Default options with documentation
default_options = {
    "option1": "default_value",  # Document each option
    "option2": 123,              # Document each option
}

def run(vcon_uuid, link_name, opts=default_options):
    """Process a vCon through this link.

    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance
        opts: Options dictionary from configuration

    Returns:
        str: vcon_uuid if processing should continue, None to stop chain
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    logger.info(f"Starting {link_name} for vCon: {vcon_uuid}")

    try:
        # Get vCon from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Process vCon here...
        # ...
        
        # Optional: Modify vCon and store it back
        vcon_redis.store_vcon(vcon)
        
        logger.info(f"Finished {link_name} for vCon: {vcon_uuid}")
        return vcon_uuid  # Continue processing
    except Exception as e:
        logger.error(f"Error processing vCon {vcon_uuid}: {e}")
        return None  # Stop chain processing
```

### Link Module Example

Here's a simplified version of a filtering link that uses jq expressions:

```python
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
import jq

logger = init_logger(__name__)

default_options = {
    "filter": ".",             # jq filter expression to evaluate
    "forward_matches": True,   # if True, forward vCons that match; if False, forward non-matches
}

def run(vcon_uuid, link_name, opts=default_options):
    """JQ Filter link that uses jq expressions to filter vCons.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance
        opts: Filter configuration
        
    Returns:
        str or None: vcon_uuid if vCon should continue through chain, None to stop
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    logger.info(f"Starting JQ filter {link_name} for vCon: {vcon_uuid}")
    
    try:
        # Get vCon from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Apply jq filter
        filter_expr = opts["filter"]
        vcon_dict = vcon.to_dict()
        
        # Run jq filter
        result = jq.compile(filter_expr).input(vcon_dict).first()
        
        # Check if we should forward this vCon
        matches = bool(result)
        should_forward = matches if opts["forward_matches"] else not matches
        
        if should_forward:
            logger.info(f"vCon {vcon_uuid} matches filter, forwarding")
            return vcon_uuid
        else:
            logger.info(f"vCon {vcon_uuid} does not match filter, stopping chain")
            return None
    except Exception as e:
        logger.error(f"Error applying JQ filter to vCon {vcon_uuid}: {e}")
        return None  # Stop chain processing on error
```

### Testing a Link Module

Create a test file in your link directory, such as `test_init.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from . import run, default_options

# Create test fixture for mocking Redis and vCon
@pytest.fixture
def mock_vcon_redis():
    with patch('server.lib.vcon_redis.VconRedis') as mock_redis_class:
        mock_redis = MagicMock()
        mock_vcon = MagicMock()
        mock_redis.get_vcon.return_value = mock_vcon
        mock_redis_class.return_value = mock_redis
        yield mock_redis, mock_vcon

def test_link_basic_functionality(mock_vcon_redis):
    mock_redis, mock_vcon = mock_vcon_redis
    
    # Test with default options
    result = run("test-uuid", "test-link")
    
    # Verify Redis was called to get vCon
    mock_redis.get_vcon.assert_called_once_with("test-uuid")
    
    # Verify other functionality as needed
    # ...
    
    # Verify result
    assert result == "test-uuid"  # Or whatever your expected result is
```

## Implementing a Storage Module

Storage modules are responsible for storing vCons to different backend systems.

### Storage Module Requirements

1. Each storage module must be in its own directory under `server/storage/`.
2. Storage modules must implement a `save(vcon_uuid, opts=default_options)` function.
3. Storage modules may optionally implement a `get(vcon_uuid, opts=default_options)` function.
4. Storage modules must define a `default_options` dictionary.

### Storage Module Structure

```python
# Required imports
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

# Initialize logger
logger = init_logger(__name__)

# Default options with documentation
default_options = {
    "option1": "default_value",  # Document each option
    "option2": 123,              # Document each option
}

def save(vcon_uuid, opts=default_options):
    """Save a vCon to storage.
    
    Args:
        vcon_uuid: UUID of the vCon to save
        opts: Storage configuration options
        
    Raises:
        Exception: If saving fails
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    logger.info(f"Starting storage for vCon: {vcon_uuid}")
    
    try:
        # Get vCon from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Save vCon to storage backend
        # ...
        
        logger.info(f"Successfully saved vCon {vcon_uuid}")
    except Exception as e:
        logger.error(f"Failed to save vCon {vcon_uuid}: {e}")
        raise e  # Re-raise to let chain handler know about the error

def get(vcon_uuid, opts=default_options):
    """Retrieve a vCon from storage (optional).
    
    Args:
        vcon_uuid: UUID of the vCon to retrieve
        opts: Storage configuration options
        
    Returns:
        dict or None: vCon data if found, None otherwise
    """
    # Implementation of retrieval logic
    # ...
```

### Storage Module Example

Here's a simplified version of an S3 storage module:

```python
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
import boto3
from datetime import datetime

logger = init_logger(__name__)

default_options = {
    "aws_access_key_id": None,
    "aws_secret_access_key": None,
    "aws_bucket": "vcons",
    "s3_path": None,  # Optional prefix
}

def save(vcon_uuid, opts=default_options):
    """Save a vCon to S3 storage.
    
    Args:
        vcon_uuid: UUID of the vCon to save
        opts: S3 configuration options
        
    Raises:
        Exception: If saving fails
    """
    logger.info(f"Starting S3 storage for vCon: {vcon_uuid}")
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Create S3 client
        s3 = boto3.client(
            "s3",
            aws_access_key_id=opts["aws_access_key_id"],
            aws_secret_access_key=opts["aws_secret_access_key"],
        )

        # Build S3 path with date-based organization
        s3_path = opts.get("s3_path")
        created_at = datetime.fromisoformat(vcon.created_at)
        timestamp = created_at.strftime("%Y/%m/%d")
        key = vcon_uuid + ".vcon"
        destination_directory = f"{timestamp}/{key}"
        if s3_path:
            destination_directory = s3_path + "/" + destination_directory
            
        # Save to S3
        s3.put_object(
            Bucket=opts["aws_bucket"], 
            Key=destination_directory, 
            Body=vcon.dumps()
        )
        logger.info(f"Finished S3 storage for vCon: {vcon_uuid}")
    except Exception as e:
        logger.error(f"S3 storage failed for vCon: {vcon_uuid}, error: {e}")
        raise e
```

### Testing a Storage Module

Create a test file in your storage directory:

```python
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from . import save, default_options

@pytest.fixture
def mock_vcon_redis():
    with patch('server.lib.vcon_redis.VconRedis') as mock_redis_class:
        mock_redis = MagicMock()
        mock_vcon = MagicMock()
        mock_vcon.uuid = "test-uuid"
        mock_vcon.created_at = datetime.now().isoformat()
        mock_vcon.dumps.return_value = '{"uuid": "test-uuid"}'
        mock_redis.get_vcon.return_value = mock_vcon
        mock_redis_class.return_value = mock_redis
        yield mock_redis, mock_vcon

@pytest.fixture
def mock_storage_backend():
    # Mock your storage backend (e.g., boto3, pg connection, etc.)
    with patch('boto3.client') as mock_client_factory:
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client
        yield mock_client

def test_storage_save(mock_vcon_redis, mock_storage_backend):
    mock_redis, mock_vcon = mock_vcon_redis
    
    # Test with customized options
    test_options = default_options.copy()
    test_options.update({
        "aws_access_key_id": "test-key",
        "aws_secret_access_key": "test-secret",
        "aws_bucket": "test-bucket"
    })
    
    # Call save function
    save("test-uuid", test_options)
    
    # Verify Redis was called to get vCon
    mock_redis.get_vcon.assert_called_once_with("test-uuid")
    
    # Verify storage backend was called correctly
    mock_storage_backend.put_object.assert_called_once()
    call_kwargs = mock_storage_backend.put_object.call_args[1]
    assert call_kwargs["Bucket"] == "test-bucket"
    assert "test-uuid.vcon" in call_kwargs["Key"]
    assert call_kwargs["Body"] == '{"uuid": "test-uuid"}'
```

## Configuration and Integration

Once you've implemented your module, add it to your `config.yml`:

### Adding a Link Module

```yaml
links:
  my_custom_link:
    module: links.my_custom_link
    options:
      option1: "custom_value"
      option2: 456
```

### Adding a Storage Module

```yaml
storages:
  my_custom_storage:
    module: storage.my_custom_storage
    options:
      option1: "custom_value"
      option2: 456
```

### Integrating into a Chain

```yaml
chains:
  my_chain:
    links:
      - my_custom_link
      - other_link
    ingress_lists:
      - input_queue
    storages:
      - my_custom_storage
      - postgres
    egress_lists:
      - output_queue
    enabled: 1
```

## Best Practices

1. **Error Handling**:
   - Always use try/except blocks to catch and log errors
   - For links: return None on error to stop chain processing
   - For storage: re-raise exceptions to inform the chain handler

2. **Logging**:
   - Use the logger from `lib.logging_utils` for consistent logging
   - Log the start and end of processing with appropriate log levels
   - Include the vCon UUID in all log messages

3. **Configuration**:
   - Document all options in the `default_options` dictionary
   - Provide sensible defaults where possible
   - Validate required options before processing

4. **Testing**:
   - Create unit tests for your module using pytest
   - Mock external dependencies (Redis, storage backends, APIs)
   - Test both success and error scenarios

5. **Documentation**:
   - Include a README.md in your module directory
   - Document how the module works and its configuration options
   - Provide example configurations

6. **Performance**:
   - Use asynchronous operations where appropriate
   - Consider adding metrics for monitoring (using `lib.metrics`)
   - Be mindful of memory usage when processing large vCons