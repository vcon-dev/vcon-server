# File Storage

This module implements local file system storage for the vCon server.

## Overview

File storage provides simple, local file system storage capabilities, making it ideal for development, testing, and small-scale deployments of vCon data.

## Configuration

Required configuration options:

```yaml
storages:
  file:
    module: storage.file
    options:
      base_path: /path/to/storage     # Base directory for file storage
      file_format: json               # File format (json/txt)
      compression: false              # Enable compression
      max_file_size: 10485760        # Max file size in bytes (10MB)
      file_permissions: 0644          # File permissions
```

## Features

- Local file storage
- Multiple file formats
- Compression support
- File size limits
- Automatic metrics logging
- File organization
- Permission management

## Usage

```python
from storage import Storage

# Initialize File storage
file_storage = Storage("file")

# Save vCon data
file_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = file_storage.get(vcon_id)
```

## Implementation Details

The File storage implementation:
- Uses standard file system operations
- Implements file compression
- Supports multiple file formats
- Provides file organization
- Includes automatic metrics logging

## Dependencies

- json
- gzip
- pathlib

## Best Practices

1. Regular file cleanup
2. Implement file rotation
3. Use appropriate file formats
4. Monitor disk space
5. Implement proper error handling
6. Use compression for large files
7. Regular backup
8. Implement file size limits
9. Use appropriate file permissions
10. Monitor file system performance
11. Implement proper directory structure
12. Handle file locking 