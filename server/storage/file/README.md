# File Storage

This module implements local file system storage for the vCon server.

## Overview

File storage provides local file system storage capabilities, making it ideal for development, testing, and small-scale deployments. Files are stored using the vCon UUID as the filename, with optional date-based directory organization and gzip compression.

## Configuration

Configuration options in `config.yml`:

```yaml
storages:
  file:
    module: storage.file
    options:
      path: /data/vcons              # Base directory for storage
      organize_by_date: true         # Store in YYYY/MM/DD subdirectories
      compression: false             # Enable gzip compression
      max_file_size: 10485760        # Max file size in bytes (10MB)
      file_permissions: 0o644        # Unix file permissions (octal)
      dir_permissions: 0o755         # Unix directory permissions (octal)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | `/data/vcons` | Base directory for vCon file storage |
| `organize_by_date` | boolean | `true` | Organize files in YYYY/MM/DD subdirectories based on vCon creation date |
| `compression` | boolean | `false` | Enable gzip compression (files saved as `.json.gz`) |
| `max_file_size` | integer | `10485760` | Maximum file size in bytes (10MB default) |
| `file_permissions` | integer | `0o644` | Unix permissions for created files |
| `dir_permissions` | integer | `0o755` | Unix permissions for created directories |

## Features

- **UUID-based filenames**: Files are named `{uuid}.json` or `{uuid}.json.gz`
- **Date-based organization**: Optional YYYY/MM/DD directory structure based on vCon creation date
- **Gzip compression**: Reduce storage space with optional compression
- **File size limits**: Prevent oversized files from consuming disk space
- **Permission management**: Configure Unix file and directory permissions
- **Automatic cleanup**: Empty directories are removed when vCons are deleted
- **Metrics logging**: All operations are automatically timed and logged

## Docker Volume Configuration

When using Docker, mount a volume for persistent file storage:

```yaml
services:
  conserver:
    volumes:
      - vcon_files:/data/vcons

volumes:
  vcon_files: {}
```

## Usage

```python
from storage import Storage

# Initialize file storage
file_storage = Storage("file")

# Save vCon data (retrieves from Redis and writes to file)
file_storage.save(vcon_uuid)

# Retrieve vCon data
vcon_data = file_storage.get(vcon_uuid)

# Delete vCon file
file_storage.delete(vcon_uuid)
```

### Direct Module Usage

For more control, you can use the module functions directly:

```python
from server.storage.file import save, get, delete, exists, list_vcons

# Check if vCon exists
if exists("my-uuid", opts):
    data = get("my-uuid", opts)

# List all vCons with pagination
uuids = list_vcons(opts, limit=100, offset=0)

# Delete a vCon
deleted = delete("my-uuid", opts)
```

## File Organization

### Flat Structure (`organize_by_date: false`)
```
/data/vcons/
├── abc123.json
├── def456.json
└── ghi789.json.gz
```

### Date-Based Structure (`organize_by_date: true`)
```
/data/vcons/
├── 2024/
│   ├── 03/
│   │   ├── 14/
│   │   │   ├── abc123.json
│   │   │   └── def456.json
│   │   └── 15/
│   │       └── ghi789.json
│   └── 04/
│       └── 01/
│           └── jkl012.json
```

## API Reference

### `save(vcon_uuid: str, opts: dict = None) -> None`
Save a vCon to file storage. Retrieves the vCon from Redis and writes it to a file.

### `get(vcon_uuid: str, opts: dict = None) -> Optional[dict]`
Retrieve a vCon from file storage by UUID. Returns `None` if not found.

### `delete(vcon_uuid: str, opts: dict = None) -> bool`
Delete a vCon file. Returns `True` if deleted, `False` if not found.

### `exists(vcon_uuid: str, opts: dict = None) -> bool`
Check if a vCon exists in file storage.

### `list_vcons(opts: dict = None, limit: int = 100, offset: int = 0) -> list[str]`
List vCon UUIDs in storage with pagination support. Returns UUIDs sorted by modification time (newest first).

## Dependencies

- `json` - JSON serialization
- `gzip` - Compression support
- `pathlib` - Path manipulation
- `glob` - File pattern matching

## Best Practices

1. **Use compression** for large vCons to save disk space
2. **Enable date organization** for easier manual browsing and archival
3. **Set appropriate permissions** for security (default 0o644 for files)
4. **Monitor disk space** - implement cleanup policies for old files
5. **Configure volume mounts** in Docker for data persistence
6. **Set reasonable file size limits** to prevent runaway storage
7. **Use S3 or other cloud storage** for production deployments with large volumes