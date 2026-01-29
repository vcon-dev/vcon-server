# How to Create New Links

This guide will walk you through creating a new link processor for the vCon server. Links are modular components that process vCon objects as they flow through processing chains.

## Table of Contents

1. [Overview](#overview)
2. [Link Structure](#link-structure)
3. [Step-by-Step Guide](#step-by-step-guide)
4. [Code Examples](#code-examples)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [Best Practices](#best-practices)
8. [Common Patterns](#common-patterns)

## Overview

### What is a Link?

A link is a Python module that processes vCon objects. Each link:
- Receives a vCon UUID from the processing chain
- Retrieves the vCon from Redis
- Performs operations on the vCon (analysis, transcription, tagging, etc.)
- Stores the updated vCon back to Redis
- Returns the vCon UUID (or None to stop processing)

### Link Interface

Every link must implement a `run()` function with this signature:

```python
def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> Optional[str]:
    """
    Process a vCon through this link.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance (from config)
        opts: Configuration options for this link
        
    Returns:
        vcon_uuid if processing should continue, None to stop the chain
    """
    pass
```

## Link Structure

### Directory Structure

Create a new directory under `server/links/` with your link name:

```
server/links/
  your_link_name/
    __init__.py      # Main link implementation
    README.md        # Documentation (optional but recommended)
    tests/           # Test files (optional but recommended)
      test_your_link.py
```

### Required Components

1. **`__init__.py`**: Contains the `run()` function and any helper functions
2. **`default_options`**: Dictionary of default configuration values
3. **Logging**: Use the logging utility for consistent logging
4. **Error Handling**: Proper exception handling and logging

## Step-by-Step Guide

### Step 1: Create the Directory

Create a new directory for your link:

```bash
mkdir -p server/links/your_link_name
```

### Step 2: Create `__init__.py`

Start with a basic template:

```python
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    # Define your default configuration options here
    "option1": "default_value",
    "option2": 100,
}

def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> str:
    """
    Main function to run your link.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of the link (for logging purposes)
        opts: Options for the link
        
    Returns:
        str: The UUID of the processed vCon (or None to stop chain)
    """
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}: {link_name} plugin for: {vcon_uuid}")
    
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    # Get the vCon from Redis
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    if not vcon:
        logger.error(f"vCon not found: {vcon_uuid}")
        return None
    
    # TODO: Add your processing logic here
    
    # Store the updated vCon back to Redis
    vcon_redis.store_vcon(vcon)
    
    logger.info(f"Finished {module_name}:{link_name} plugin for: {vcon_uuid}")
    
    return vcon_uuid
```

### Step 3: Implement Your Logic

Add your specific processing logic. Common operations include:

#### Working with vCon Objects

```python
# Access vCon properties
vcon.uuid                    # Get vCon UUID
vcon.parties                 # List of parties
vcon.dialog                  # List of dialogs
vcon.analysis                # List of analysis entries
vcon.attachments             # List of attachments
vcon.tags                    # Get tags attachment

# Add tags
vcon.add_tag(tag_name="category", tag_value="important")

# Add analysis
vcon.add_analysis(
    type="sentiment",
    dialog=0,  # Dialog index, or None for vCon-level
    vendor="your_vendor",
    body={"sentiment": "positive", "score": 0.95},
    encoding="json",
    extra={"model": "gpt-4"}
)

# Add attachments
vcon.add_attachment(
    type="transcript",
    body="Full transcript text",
    encoding="none"
)

# Add parties
vcon.add_party({
    "tel": "+1234567890",
    "name": "John Doe"
})

# Add dialogs
vcon.add_dialog({
    "type": "recording",
    "start": "2024-01-01T00:00:00Z",
    "duration": 300
})

# Convert to dict for processing
vcon_dict = vcon.to_dict()

# Convert to JSON string
vcon_json = vcon.to_json()
```

#### Iterating Over Dialogs

```python
for index, dialog in enumerate(vcon.dialog):
    # Process each dialog
    dialog_type = dialog.get("type")
    if dialog_type == "recording":
        # Process recording
        pass
```

#### Checking Existing Analysis

```python
# Check if analysis already exists
def has_analysis(vcon, dialog_index, analysis_type):
    for analysis in vcon.analysis:
        if analysis.get("dialog") == dialog_index and analysis.get("type") == analysis_type:
            return True
    return False

# Use it to skip already processed items
if has_analysis(vcon, index, "transcription"):
    logger.info(f"Dialog {index} already transcribed, skipping")
    continue
```

### Step 4: Add Configuration to `config.yml`

Add your link to the configuration file:

```yaml
links:
  your_link_name:
    module: links.your_link_name
    ingress-lists: []  # Optional: specific ingress lists
    egress-lists: []   # Optional: specific egress lists
    options:
      option1: "custom_value"
      option2: 200
```

### Step 5: Add to a Chain

Add your link to a processing chain:

```yaml
chains:
  my_chain:
    links:
      - existing_link
      - your_link_name  # Your new link
      - another_link
    ingress_lists:
      - my_input_list
    storages:
      - mongo
    egress_lists:
      - my_output_list
    enabled: 1
```

## Code Examples

### Example 1: Simple Tag Link

This example adds tags to a vCon:

```python
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "tags": ["processed", "reviewed"],
}

def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> str:
    logger.info(f"Starting tag link for: {vcon_uuid}")
    
    # Merge options
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    # Get vCon
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    if not vcon:
        logger.error(f"vCon not found: {vcon_uuid}")
        return None
    
    # Add tags
    for tag in opts.get("tags", []):
        vcon.add_tag(tag_name=tag, tag_value=tag)
    
    # Store updated vCon
    vcon_redis.store_vcon(vcon)
    
    logger.info(f"Finished tag link for: {vcon_uuid}")
    return vcon_uuid
```

### Example 2: Analysis Link with External API

This example calls an external API and adds analysis:

```python
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = init_logger(__name__)

default_options = {
    "api_url": "https://api.example.com/analyze",
    "api_key": None,
    "analysis_type": "sentiment",
}

@retry(
    wait=wait_exponential(multiplier=2, min=1, max=65),
    stop=stop_after_attempt(6),
)
def call_api(text: str, opts: dict) -> dict:
    """Call external API with retry logic."""
    headers = {"Authorization": f"Bearer {opts['api_key']}"}
    response = requests.post(
        opts["api_url"],
        json={"text": text},
        headers=headers,
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> str:
    logger.info(f"Starting analysis link for: {vcon_uuid}")
    
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    if not opts.get("api_key"):
        raise ValueError("API key is required")
    
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    if not vcon:
        logger.error(f"vCon not found: {vcon_uuid}")
        return None
    
    # Process each dialog
    for index, dialog in enumerate(vcon.dialog):
        # Check if already analyzed
        existing = next(
            (a for a in vcon.analysis 
             if a.get("dialog") == index and a.get("type") == opts["analysis_type"]),
            None
        )
        if existing:
            logger.info(f"Dialog {index} already analyzed, skipping")
            continue
        
        # Extract text from dialog (example)
        text = dialog.get("body", {}).get("transcript", "")
        if not text:
            logger.warning(f"No transcript found for dialog {index}")
            continue
        
        # Call API
        try:
            result = call_api(text, opts)
            
            # Add analysis
            vcon.add_analysis(
                type=opts["analysis_type"],
                dialog=index,
                vendor="example_api",
                body=result,
                encoding="json"
            )
        except Exception as e:
            logger.error(f"Failed to analyze dialog {index}: {e}")
            raise
    
    vcon_redis.store_vcon(vcon)
    logger.info(f"Finished analysis link for: {vcon_uuid}")
    return vcon_uuid
```

### Example 3: Filtering Link

This example filters vCons based on conditions:

```python
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "min_duration": 60,  # Minimum duration in seconds
    "forward_on_match": True,  # Forward if matches, otherwise forward if doesn't match
}

def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> str:
    logger.info(f"Starting filter link for: {vcon_uuid}")
    
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    
    if not vcon:
        logger.error(f"vCon not found: {vcon_uuid}")
        return None
    
    # Check total duration
    total_duration = 0
    for dialog in vcon.dialog:
        duration = dialog.get("duration", 0)
        total_duration += duration
    
    # Apply filter
    matches = total_duration >= opts["min_duration"]
    should_forward = matches == opts["forward_on_match"]
    
    if should_forward:
        logger.info(f"vCon {vcon_uuid} matches filter - forwarding")
        return vcon_uuid
    else:
        logger.info(f"vCon {vcon_uuid} does not match filter - filtering out")
        return None  # Stop processing chain
```

## Configuration

### Option Merging Pattern

Always merge user-provided options with defaults:

```python
merged_opts = default_options.copy()
merged_opts.update(opts)
opts = merged_opts
```

This ensures all expected options are present with sensible defaults.

### Environment Variables

You can access environment variables in your link:

```python
import os

api_key = opts.get("API_KEY") or os.getenv("MY_API_KEY")
```

### Sensitive Data

For sensitive data like API keys, prefer configuration over hardcoding:

```yaml
links:
  my_link:
    module: links.my_link
    options:
      API_KEY: ${MY_API_KEY}  # Use environment variable substitution
```

## Testing

### Basic Test Structure

Create a test file in `server/links/your_link_name/tests/test_your_link.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from links.your_link_name import run
from vcon import Vcon

@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('links.your_link_name.VconRedis') as mock:
        yield mock

@pytest.fixture
def sample_vcon():
    """Create a sample vCon for testing"""
    return Vcon({
        "uuid": "test-uuid",
        "vcon": "0.0.1",
        "parties": [],
        "dialog": [
            {
                "type": "recording",
                "duration": 120
            }
        ],
        "analysis": [],
        "attachments": []
    })

@pytest.fixture
def mock_redis_with_vcon(mock_vcon_redis, sample_vcon):
    """Set up mock Redis with sample vCon"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon
    mock_vcon_redis.return_value = mock_instance
    return mock_vcon_redis

def test_basic_functionality(mock_redis_with_vcon):
    """Test basic link functionality"""
    mock_vcon_redis, _ = mock_redis_with_vcon
    
    opts = {
        "option1": "test_value"
    }
    
    result = run("test-uuid", "test-link", opts)
    
    # Verify vCon was retrieved
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.assert_called_once_with("test-uuid")
    
    # Verify vCon was stored
    mock_instance.store_vcon.assert_called_once()
    
    # Verify return value
    assert result == "test-uuid"

def test_missing_vcon(mock_vcon_redis):
    """Test handling of missing vCon"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = None
    mock_vcon_redis.return_value = mock_instance
    
    result = run("missing-uuid", "test-link")
    
    assert result is None
    mock_instance.store_vcon.assert_not_called()
```

### Running Tests

```bash
# Run all tests for your link
pytest server/links/your_link_name/tests/

# Run with verbose output
pytest -v server/links/your_link_name/tests/

# Run specific test
pytest server/links/your_link_name/tests/test_your_link.py::test_basic_functionality
```

## Best Practices

### 1. Logging

- Use the `init_logger(__name__)` utility for consistent logging
- Log at appropriate levels:
  - `logger.debug()`: Detailed debugging information
  - `logger.info()`: Important processing steps
  - `logger.warning()`: Non-fatal issues
  - `logger.error()`: Errors that need attention
- Include vCon UUID in log messages for traceability

### 2. Error Handling

- Always check if vCon exists before processing
- Handle missing or invalid data gracefully
- Use try/except blocks for external API calls
- Log errors with context
- Re-raise exceptions if the chain should stop

```python
try:
    result = external_api_call(data)
except requests.RequestException as e:
    logger.error(f"API call failed for vCon {vcon_uuid}: {e}")
    raise  # Re-raise to stop chain processing
```

### 3. Idempotency

Make your link idempotent when possible - safe to run multiple times:

```python
# Check if already processed
existing_analysis = next(
    (a for a in vcon.analysis 
     if a.get("type") == opts["analysis_type"]),
    None
)
if existing_analysis:
    logger.info("Already processed, skipping")
    return vcon_uuid
```

### 4. Performance

- Skip processing when possible (check for existing results)
- Use efficient data structures
- Consider batch operations for multiple items
- Log processing time for monitoring

```python
import time

start = time.time()
# ... processing ...
elapsed = time.time() - start
logger.info(f"Processing took {elapsed:.2f} seconds")
```

### 5. Metrics

Use the metrics utility for monitoring:

```python
from lib.metrics import init_metrics, stats_count, stats_gauge

init_metrics()

# Count events
stats_count("conserver.link.your_link.processed", tags=["status:success"])

# Track values
stats_gauge("conserver.link.your_link.processing_time", elapsed_time)
```

### 6. Return Values

- Return `vcon_uuid` (string) to continue processing
- Return `None` to stop the processing chain (useful for filters)
- You can return a different UUID if you create a new vCon

### 7. Documentation

- Add docstrings to your `run()` function
- Document all configuration options
- Include usage examples in README.md
- Document any external dependencies

## Common Patterns

### Pattern 1: Processing with Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

@retry(
    wait=wait_exponential(multiplier=2, min=1, max=65),
    stop=stop_after_attempt(6),
    before_sleep=before_sleep_log(logger, logging.INFO),
)
def call_external_service(data):
    # Your API call here
    pass
```

### Pattern 2: Sampling

```python
from lib.links.filters import randomly_execute_with_sampling

if not randomly_execute_with_sampling(opts):
    logger.info(f"Skipping {vcon_uuid} due to sampling")
    return vcon_uuid
```

### Pattern 3: Conditional Processing

```python
from lib.links.filters import is_included

if not is_included(opts, vcon):
    logger.info(f"Skipping {vcon_uuid} due to filters")
    return vcon_uuid
```

### Pattern 4: Processing Each Dialog

```python
for index, dialog in enumerate(vcon.dialog):
    # Skip if already processed
    if has_analysis(vcon, index, "my_analysis"):
        continue
    
    # Process dialog
    result = process_dialog(dialog)
    
    # Add result to vCon
    vcon.add_analysis(
        type="my_analysis",
        dialog=index,
        vendor="my_vendor",
        body=result,
        encoding="json"
    )
```

### Pattern 5: Extracting Text from Analysis

```python
def get_transcript_from_analysis(vcon, dialog_index):
    """Extract transcript from existing analysis."""
    for analysis in vcon.analysis:
        if analysis.get("dialog") == dialog_index and analysis.get("type") == "transcript":
            return analysis.get("body", {}).get("transcript", "")
    return None
```

## Next Steps

1. **Review Existing Links**: Look at similar links in `server/links/` for inspiration
2. **Test Thoroughly**: Write comprehensive tests for your link
3. **Document**: Create a README.md explaining your link's purpose and configuration
4. **Add to Chains**: Integrate your link into processing chains
5. **Monitor**: Use metrics and logging to monitor your link's performance

## Additional Resources

- See `server/links/README.md` for a list of available links
- See `prod_mgt/04_LINK_PROCESSORS.md` for more link documentation
- See `example_config.yml` for configuration examples
- Review existing link implementations for patterns and best practices

## Troubleshooting

### Link Not Being Called

- Check that the link is in `config.yml` under `links:`
- Verify the module path is correct: `module: links.your_link_name`
- Ensure the link is added to a chain's `links:` list
- Check that the chain is `enabled: 1`

### Import Errors

- Ensure your `__init__.py` has proper imports
- Check that dependencies are installed
- Verify module paths match the directory structure

### vCon Not Found

- Verify Redis is running and accessible
- Check that vCons are being stored correctly
- Ensure the vCon UUID is valid

### Options Not Working

- Verify option merging pattern is used
- Check that default_options includes all expected keys
- Ensure options are passed correctly in config.yml

