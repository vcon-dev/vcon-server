# SFTP Storage

This module implements secure file transfer protocol storage for the vCon server.

## Overview

SFTP storage provides secure file transfer capabilities, making it ideal for storing vCon data on remote servers with encrypted transmission.

## Configuration

Required configuration options:

```yaml
storages:
  sftp:
    module: storage.sftp
    options:
      host: sftp.example.com           # SFTP server host
      port: 22                         # SFTP port
      username: user                   # SFTP username
      password: null                   # Optional: password
      key_file: /path/to/key          # Optional: SSH key file
      remote_path: /path/to/vcons     # Remote directory path
      local_path: /path/to/local      # Local cache directory
```

## Features

- Secure file transfer
- SSH key authentication
- Password authentication
- Automatic metrics logging
- File caching
- Directory management
- Transfer resume

## Usage

```python
from storage import Storage

# Initialize SFTP storage
sftp_storage = Storage("sftp")

# Save vCon data
sftp_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = sftp_storage.get(vcon_id)
```

## Implementation Details

The SFTP storage implementation:
- Uses paramiko for SFTP operations
- Implements connection pooling
- Supports key-based authentication
- Provides file caching
- Includes automatic metrics logging

## Dependencies

- paramiko
- cryptography

## Best Practices

1. Use SSH key authentication
2. Implement proper access control
3. Use appropriate file permissions
4. Monitor disk space
5. Regular backup
6. Implement proper error handling
7. Use appropriate file formats
8. Configure connection timeouts
9. Monitor transfer performance
10. Use connection pooling
11. Implement retry logic
12. Secure credential management 