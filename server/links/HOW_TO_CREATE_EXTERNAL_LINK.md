# How to Create an External Link with Its Own Repository

This guide explains how to create a vCon server link as a standalone Python package in its own repository that can be installed by reference from GitHub or PyPI.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Repository Setup](#repository-setup)
4. [Package Structure](#package-structure)
5. [Implementing the Link](#implementing-the-link)
6. [Dependencies](#dependencies)
7. [Publishing to GitHub](#publishing-to-github)
8. [Installing in vCon Server](#installing-in-vcon-server)
9. [Version Management](#version-management)
10. [Testing](#testing)
11. [Best Practices](#best-practices)

## Overview

An external link is a Python package that:
- Lives in its own repository (separate from vcon-server)
- Can be installed via pip from GitHub or PyPI
- Implements the standard vCon link interface
- Can be referenced in vcon-server configuration without being part of the main codebase

### Benefits

- **Separation of concerns**: Keep your link code separate from the main server
- **Version control**: Independent versioning and release cycles
- **Reusability**: Share links across multiple vcon-server instances
- **Privacy**: Keep proprietary links in private repositories
- **Distribution**: Publish to PyPI for public distribution

## Prerequisites

- Python 3.12+ (matching vcon-server requirements)
- Git installed and configured
- GitHub account (or Git hosting service)
- Basic understanding of Python packaging
- Access to a vcon-server instance for testing

## Repository Setup

### Step 1: Create a New Repository

Create a new repository on GitHub (or your preferred Git hosting service):

```bash
# Create a new directory for your link
mkdir my-vcon-link
cd my-vcon-link
git init
```

### Step 2: Initialize Git Repository

```bash
# Create .gitignore
cat > .gitignore << EOF
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/
.venv/
venv/
.env
*.log
.pytest_cache/
.coverage
htmlcov/
EOF

git add .gitignore
git commit -m "Initial commit: Add .gitignore"
```

## Package Structure

Create the following directory structure:

```
my-vcon-link/
├── my_vcon_link/          # Main package directory (matches module name)
│   ├── __init__.py       # Link implementation
│   └── utils.py          # Optional helper utilities
├── tests/                 # Test directory
│   ├── __init__.py
│   └── test_link.py
├── pyproject.toml         # Package configuration (modern approach)
├── README.md              # Documentation
├── LICENSE                 # License file
└── .gitignore
```

### Step 3: Create Package Directory

```bash
mkdir -p my_vcon_link tests
touch my_vcon_link/__init__.py
touch my_vcon_link/utils.py
touch tests/__init__.py
touch tests/test_link.py
```

## Implementing the Link

### Step 4: Create `pyproject.toml`

Create a `pyproject.toml` file for your package:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "my-vcon-link"
version = "0.1.0"
description = "A custom vCon server link"
readme = "README.md"
requires-python = ">=3.12,<3.14"
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
license = {text = "MIT"}
keywords = ["vcon", "link", "processor"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "vcon>=0.1.0",  # vCon library - check available version
    "redis>=4.6.0",  # Redis client
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=4.0.0",
    "black>=24.0.0",
]

[tool.setuptools]
packages = ["my_vcon_link"]

[tool.setuptools.package-data]
"*" = ["*.md", "*.txt"]

[tool.black]
line-length = 120
```

**Important Notes:**
- The package name (`name`) can differ from the module name (`my_vcon_link`)
- The module name (directory name) is what will be imported in vcon-server config
- Ensure Python version matches vcon-server requirements (>=3.12,<3.14)
- Include `vcon` and `redis` as dependencies

### Step 5: Implement the Link Interface

Create `my_vcon_link/__init__.py` with your link implementation:

```python
"""My Custom vCon Link

A link that processes vCon objects for the vCon server.
"""

import logging
from typing import Optional
import redis
from redis.commands.json.path import Path
import vcon

# Initialize logger
logger = logging.getLogger(__name__)

# Default configuration options
default_options = {
    "option1": "default_value",
    "option2": 100,
    "redis_host": "localhost",
    "redis_port": 6379,
    "redis_db": 0,
}


def get_redis_connection(opts: dict):
    """Get Redis connection based on options.
    
    Args:
        opts: Configuration options that may include redis_host, redis_port, redis_db
        
    Returns:
        Redis connection object
    """
    host = opts.get("redis_host", "localhost")
    port = opts.get("redis_port", 6379)
    db = opts.get("redis_db", 0)
    
    return redis.Redis(host=host, port=port, db=db, decode_responses=False)


def get_vcon_from_redis(redis_conn, vcon_uuid: str) -> Optional[vcon.Vcon]:
    """Retrieve a vCon from Redis.
    
    Args:
        redis_conn: Redis connection object
        vcon_uuid: UUID of the vCon to retrieve
        
    Returns:
        vCon object or None if not found
    """
    try:
        vcon_dict = redis_conn.json().get(f"vcon:{vcon_uuid}", Path.root_path())
        if not vcon_dict:
            return None
        return vcon.Vcon(vcon_dict)
    except Exception as e:
        logger.error(f"Error retrieving vCon {vcon_uuid} from Redis: {e}")
        return None


def store_vcon_to_redis(redis_conn, vcon_obj: vcon.Vcon) -> bool:
    """Store a vCon to Redis.
    
    Args:
        redis_conn: Redis connection object
        vcon_obj: vCon object to store
        
    Returns:
        True if successful, False otherwise
    """
    try:
        key = f"vcon:{vcon_obj.uuid}"
        vcon_dict = vcon_obj.to_dict()
        redis_conn.json().set(key, Path.root_path(), vcon_dict)
        return True
    except Exception as e:
        logger.error(f"Error storing vCon {vcon_obj.uuid} to Redis: {e}")
        return False


def run(
    vcon_uuid: str,
    link_name: str,
    opts: dict = default_options
) -> Optional[str]:
    """Main link function - required interface for vCon server links.
    
    This function is called by the vCon server to process a vCon through this link.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance (from config)
        opts: Configuration options for this link (merged with defaults)
        
    Returns:
        vcon_uuid (str) if processing should continue, None to stop the chain
        
    Raises:
        Exception: If processing fails and chain should stop
    """
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}:{link_name} plugin for: {vcon_uuid}")
    
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    # Get Redis connection
    redis_conn = get_redis_connection(opts)
    
    # Retrieve vCon from Redis
    vcon_obj = get_vcon_from_redis(redis_conn, vcon_uuid)
    if not vcon_obj:
        logger.error(f"vCon not found: {vcon_uuid}")
        return None
    
    # TODO: Add your processing logic here
    # Example: Add a tag
    # vcon_obj.add_tag(tag_name="processed_by", tag_value=link_name)
    
    # Example: Add analysis
    # vcon_obj.add_analysis(
    #     type="custom_analysis",
    #     dialog=None,  # None for vCon-level analysis
    #     vendor="my_vendor",
    #     body={"result": "processed"},
    #     encoding="json"
    # )
    
    # Example: Process each dialog
    # for index, dialog in enumerate(vcon_obj.dialog):
    #     # Process dialog
    #     pass
    
    # Store updated vCon back to Redis
    if not store_vcon_to_redis(redis_conn, vcon_obj):
        logger.error(f"Failed to store vCon: {vcon_uuid}")
        return None
    
    logger.info(f"Finished {module_name}:{link_name} plugin for: {vcon_uuid}")
    return vcon_uuid
```

### Alternative: Using vcon-server Utilities (If Available)

If your link will always run in a vcon-server environment, you can optionally use vcon-server's internal utilities:

```python
"""Alternative implementation using vcon-server utilities if available."""

import logging
from typing import Optional

# Try to import vcon-server utilities, fall back to direct implementation
try:
    from lib.vcon_redis import VconRedis
    from lib.logging_utils import init_logger
    USE_VCON_SERVER_UTILS = True
except ImportError:
    USE_VCON_SERVER_UTILS = False
    # Use direct Redis/vcon implementation (as shown above)
    import redis
    from redis.commands.json.path import Path
    import vcon

logger = logging.getLogger(__name__)
if USE_VCON_SERVER_UTILS:
    logger = init_logger(__name__)

default_options = {
    "option1": "default_value",
    "option2": 100,
}

def run(
    vcon_uuid: str,
    link_name: str,
    opts: dict = default_options
) -> Optional[str]:
    """Main link function."""
    logger.info(f"Starting {__name__}:{link_name} plugin for: {vcon_uuid}")
    
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    if USE_VCON_SERVER_UTILS:
        # Use vcon-server utilities
        vcon_redis = VconRedis()
        vcon_obj = vcon_redis.get_vcon(vcon_uuid)
        if not vcon_obj:
            logger.error(f"vCon not found: {vcon_uuid}")
            return None
        
        # Your processing logic here
        
        vcon_redis.store_vcon(vcon_obj)
    else:
        # Use direct implementation
        redis_conn = get_redis_connection(opts)
        vcon_obj = get_vcon_from_redis(redis_conn, vcon_uuid)
        if not vcon_obj:
            logger.error(f"vCon not found: {vcon_uuid}")
            return None
        
        # Your processing logic here
        
        store_vcon_to_redis(redis_conn, vcon_obj)
    
    logger.info(f"Finished {__name__}:{link_name} plugin for: {vcon_uuid}")
    return vcon_uuid
```

**Recommendation**: Use the standalone approach (first example) for maximum portability and independence from vcon-server internals.

## Dependencies

### Required Dependencies

Your link must include these in `pyproject.toml`:

- `vcon`: The vCon library for working with vCon objects
- `redis`: Redis client library (version >=4.6.0 to match vcon-server)

### Optional Dependencies

Add any additional dependencies your link needs:

```toml
dependencies = [
    "vcon>=0.1.0",
    "redis>=4.6.0",
    "requests>=2.31.0",  # For API calls
    "tenacity>=8.2.3",   # For retry logic
]
```

### Finding the vcon Library Version

Check what version of vcon is available:

```bash
pip search vcon
# or
pip index versions vcon
```

If vcon is not on PyPI, you may need to install it from source or specify it as a dependency from GitHub.

## Publishing to GitHub

### Step 6: Create README.md

Create a comprehensive README:

```markdown
# My vCon Link

A custom link processor for the vCon server.

## Features

- Feature 1
- Feature 2

## Installation

This link can be installed directly from GitHub:

```bash
pip install git+https://github.com/yourusername/my-vcon-link.git
```

## Configuration

Add to your vcon-server `config.yml`:

```yaml
links:
  my_link:
    module: my_vcon_link
    pip_name: git+https://github.com/yourusername/my-vcon-link.git
    options:
      option1: "value"
      option2: 200
```

## Options

- `option1`: Description of option1
- `option2`: Description of option2

## Usage

Add to a processing chain:

```yaml
chains:
  my_chain:
    links:
      - my_link
    ingress_lists:
      - my_input_list
    enabled: 1
```

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
pytest

# Format code
black my_vcon_link/
```

## License

MIT
```

### Step 7: Commit and Push to GitHub

```bash
# Add all files
git add .

# Commit
git commit -m "Initial implementation of my-vcon-link"

# Add remote (replace with your repository URL)
git remote add origin https://github.com/yourusername/my-vcon-link.git

# Push to GitHub
git branch -M main
git push -u origin main
```

### Step 8: Create a Release Tag (Optional but Recommended)

For version management, create a git tag:

```bash
# Create an annotated tag
git tag -a v0.1.0 -m "Initial release"

# Push tag to GitHub
git push origin v0.1.0
```

## Installing in vCon Server

### Step 9: Configure in vcon-server

Add your link to the vcon-server `config.yml`:

```yaml
links:
  my_custom_link:
    module: my_vcon_link          # Module name (directory name in your package)
    pip_name: git+https://github.com/yourusername/my-vcon-link.git@main
    options:
      option1: "custom_value"
      option2: 200
      redis_host: "localhost"     # If using direct Redis access
      redis_port: 6379
```

### Version-Specific Installation

Install from a specific tag, branch, or commit:

```yaml
links:
  # From a specific tag
  my_link_v1:
    module: my_vcon_link
    pip_name: git+https://github.com/yourusername/my-vcon-link.git@v0.1.0
    
  # From a specific branch
  my_link_dev:
    module: my_vcon_link
    pip_name: git+https://github.com/yourusername/my-vcon-link.git@develop
    
  # From a specific commit
  my_link_commit:
    module: my_vcon_link
    pip_name: git+https://github.com/yourusername/my-vcon-link.git@abc123def456
```

### Private Repository

For private repositories, use a personal access token:

```yaml
links:
  private_link:
    module: my_vcon_link
    pip_name: git+https://token:your_github_token@github.com/yourusername/my-vcon-link.git
    options:
      option1: "value"
```

**Security Note**: Store tokens securely. Consider using environment variables or secrets management.

### Step 10: Add to a Processing Chain

Add your link to a chain:

```yaml
chains:
  my_processing_chain:
    links:
      - existing_link
      - my_custom_link    # Your new link
      - another_link
    ingress_lists:
      - my_input_list
    storages:
      - mongo
    egress_lists:
      - my_output_list
    enabled: 1
```

## Version Management

### Semantic Versioning

Follow semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes to the interface or options
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Updating Versions

1. Update version in `pyproject.toml`:
   ```toml
   version = "0.2.0"
   ```

2. Commit and tag:
   ```bash
   git add pyproject.toml
   git commit -m "Bump version to 0.2.0"
   git tag -a v0.2.0 -m "Release version 0.2.0"
   git push origin main
   git push origin v0.2.0
   ```

3. Update vcon-server config to use new version:
   ```yaml
   links:
     my_link:
       module: my_vcon_link
       pip_name: git+https://github.com/yourusername/my-vcon-link.git@v0.2.0
   ```

### Version Constraints

Users can specify version constraints in the pip_name:

```yaml
links:
  # Exact version
  my_link:
    module: my_vcon_link
    pip_name: git+https://github.com/yourusername/my-vcon-link.git@v0.1.0
    
  # Latest from branch
  my_link:
    module: my_vcon_link
    pip_name: git+https://github.com/yourusername/my-vcon-link.git@main
```

## Testing

### Step 11: Write Tests

Create `tests/test_link.py`:

```python
"""Tests for my_vcon_link."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import vcon

# Import your link module
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from my_vcon_link import run, default_options


@pytest.fixture
def mock_redis():
    """Mock Redis connection."""
    with patch('my_vcon_link.get_redis_connection') as mock:
        redis_conn = MagicMock()
        mock.return_value = redis_conn
        yield redis_conn


@pytest.fixture
def sample_vcon():
    """Create a sample vCon for testing."""
    return vcon.Vcon({
        "uuid": "test-uuid-123",
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
def mock_vcon_retrieval(mock_redis, sample_vcon):
    """Mock vCon retrieval from Redis."""
    mock_redis.json().get.return_value = sample_vcon.to_dict()
    mock_redis.json().set.return_value = True
    return mock_redis


def test_run_success(mock_vcon_retrieval, sample_vcon):
    """Test successful link execution."""
    opts = {
        "option1": "test_value"
    }
    
    result = run("test-uuid-123", "test_link", opts)
    
    assert result == "test-uuid-123"
    mock_vcon_retrieval.json().get.assert_called_once()
    mock_vcon_retrieval.json().set.assert_called_once()


def test_run_missing_vcon(mock_redis):
    """Test handling of missing vCon."""
    mock_redis.json().get.return_value = None
    
    result = run("missing-uuid", "test_link")
    
    assert result is None
    mock_redis.json().set.assert_not_called()


def test_default_options():
    """Test that default options are used."""
    result = run("test-uuid", "test_link", {})
    
    # Verify defaults are applied (test will depend on your implementation)
    assert True  # Replace with actual assertions
```

### Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=my_vcon_link --cov-report=html
```

## Best Practices

### 1. Error Handling

Always handle errors gracefully:

```python
def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> Optional[str]:
    try:
        # Your processing logic
        pass
    except Exception as e:
        logger.error(f"Error processing vCon {vcon_uuid}: {e}", exc_info=True)
        # Decide: return None to stop chain, or raise to propagate error
        raise  # or return None
```

### 2. Logging

Use appropriate log levels:

```python
logger.debug("Detailed debugging information")
logger.info("Important processing steps")
logger.warning("Non-fatal issues")
logger.error("Errors that need attention")
```

### 3. Idempotency

Make your link idempotent when possible:

```python
# Check if already processed
existing_analysis = next(
    (a for a in vcon_obj.analysis 
     if a.get("type") == "my_analysis_type"),
    None
)
if existing_analysis:
    logger.info(f"vCon {vcon_uuid} already processed, skipping")
    return vcon_uuid
```

### 4. Configuration Validation

Validate configuration options:

```python
def validate_options(opts: dict) -> None:
    """Validate configuration options."""
    required = ["api_key", "api_url"]
    for key in required:
        if key not in opts or not opts[key]:
            raise ValueError(f"Required option '{key}' is missing or empty")
```

### 5. Documentation

- Document all configuration options
- Include usage examples
- Document any external API requirements
- Include troubleshooting section

### 6. Redis Connection Management

For production, consider connection pooling:

```python
import redis
from redis.connection import ConnectionPool

# Create connection pool
pool = ConnectionPool(
    host=opts.get("redis_host", "localhost"),
    port=opts.get("redis_port", 6379),
    db=opts.get("redis_db", 0),
    max_connections=10
)

redis_conn = redis.Redis(connection_pool=pool)
```

### 7. Environment Variables

Support environment variables for sensitive data:

```python
import os

default_options = {
    "api_key": os.getenv("MY_LINK_API_KEY"),
    "redis_host": os.getenv("REDIS_HOST", "localhost"),
}
```

## Publishing to PyPI (Optional)

If you want to publish to PyPI for easier installation:

### Step 12: Build and Publish

```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Upload to PyPI (test first)
python -m twine upload --repository testpypi dist/*

# Upload to production PyPI
python -m twine upload dist/*
```

Then users can install with:

```yaml
links:
  my_link:
    module: my_vcon_link
    pip_name: my-vcon-link==0.1.0  # No git+ prefix needed
```

## Troubleshooting

### Module Not Found

- Verify the module name in config matches the package directory name
- Check that the package structure is correct
- Ensure `__init__.py` exists in the package directory

### Import Errors

- Verify all dependencies are listed in `pyproject.toml`
- Check Python version compatibility
- Ensure vcon library is available

### Redis Connection Issues

- Verify Redis is accessible from vcon-server
- Check host, port, and database settings
- Ensure Redis JSON module is enabled

### Version Not Updating

- Clear pip cache: `pip cache purge`
- Rebuild Docker container if using Docker
- Verify git tag/branch exists and is pushed

## Example: Complete Minimal Link

Here's a complete minimal example:

**Directory structure:**
```
simple-link/
├── simple_link/
│   └── __init__.py
├── pyproject.toml
├── README.md
└── .gitignore
```

**`simple_link/__init__.py`:**
```python
import logging
from typing import Optional
import redis
from redis.commands.json.path import Path
import vcon

logger = logging.getLogger(__name__)

default_options = {
    "redis_host": "localhost",
    "redis_port": 6379,
}

def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> Optional[str]:
    logger.info(f"Processing {vcon_uuid} with {link_name}")
    
    opts = {**default_options, **opts}
    redis_conn = redis.Redis(host=opts["redis_host"], port=opts["redis_port"])
    
    vcon_dict = redis_conn.json().get(f"vcon:{vcon_uuid}", Path.root_path())
    if not vcon_dict:
        logger.error(f"vCon not found: {vcon_uuid}")
        return None
    
    vcon_obj = vcon.Vcon(vcon_dict)
    
    # Add a simple tag
    vcon_obj.add_tag(tag_name="processed", tag_value="true")
    
    redis_conn.json().set(f"vcon:{vcon_uuid}", Path.root_path(), vcon_obj.to_dict())
    
    return vcon_uuid
```

**`pyproject.toml`:**
```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "simple-link"
version = "0.1.0"
description = "A simple vCon link"
requires-python = ">=3.12,<3.14"
dependencies = ["vcon", "redis>=4.6.0"]

[tool.setuptools]
packages = ["simple_link"]
```

## Next Steps

1. **Test locally**: Test your link with a local vcon-server instance
2. **Add features**: Implement your specific processing logic
3. **Write tests**: Add comprehensive test coverage
4. **Document**: Create detailed README and inline documentation
5. **Publish**: Push to GitHub and optionally to PyPI
6. **Iterate**: Gather feedback and improve

## Additional Resources

- [vCon Server Link Documentation](../HOW_TO_CREATE_LINKS.md)
- [Python Packaging Guide](https://packaging.python.org/)
- [setuptools Documentation](https://setuptools.pypa.io/)
- [GitHub Actions for Python](https://docs.github.com/en/actions/guides/building-and-testing-python)

