# ChatGPT Files Storage

This module implements storage for ChatGPT-related files in the vCon server.

## Overview

ChatGPT Files storage provides specialized storage capabilities for managing files associated with ChatGPT interactions, including conversation history, embeddings, and related metadata.

## Configuration

Required configuration options:

```yaml
storages:
  chatgpt_files:
    module: storage.chatgpt_files
    options:
      base_path: /path/to/chatgpt/files  # Base directory for file storage
      file_format: json                  # File format (json/txt)
      compression: true                  # Enable compression
      max_file_size: 10485760           # Max file size in bytes (10MB)
```

## Features

- File-based storage
- JSON/TXT format support
- Compression support
- File size limits
- Automatic metrics logging
- File organization
- Metadata management

## Usage

```python
from storage import Storage

# Initialize ChatGPT Files storage
chatgpt_storage = Storage("chatgpt_files")

# Save ChatGPT interaction data
chatgpt_storage.save(vcon_id)

# Retrieve ChatGPT interaction data
interaction_data = chatgpt_storage.get(vcon_id)
```

## Implementation Details

The ChatGPT Files storage implementation:
- Uses file system operations
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