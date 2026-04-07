# file

Stores vCons as JSON files on the local filesystem. Supports optional gzip compression, date-based directory organization, and configurable Unix permissions.

## Prerequisites

- A writable directory on the host filesystem
- No additional Python packages required (uses the standard library)

When running in Docker, mount a persistent volume:

```yaml
services:
  conserver:
    volumes:
      - vcon_files:/data/vcons

volumes:
  vcon_files: {}
```

## Configuration

```yaml
storages:
  file:
    module: storage.file
    options:
      path: /data/vcons
      organize_by_date: true
      compression: false
      max_file_size: 10485760
      file_permissions: 0o644
      dir_permissions: 0o755
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | string | `/data/vcons` | Base directory where vCon files are written |
| `organize_by_date` | boolean | `true` | When enabled, files are placed under `YYYY/MM/DD/` subdirectories based on the vCon creation date |
| `compression` | boolean | `false` | Compress files with gzip (files are saved as `{uuid}.json.gz`) |
| `max_file_size` | integer | `10485760` | Maximum allowed file size in bytes (default: 10 MB). Raises an error if exceeded |
| `file_permissions` | integer | `0o644` | Unix permissions applied to each written file |
| `dir_permissions` | integer | `0o755` | Unix permissions applied to created directories |

## File Layout

### Date-based organization (default)

```
/data/vcons/
└── 2024/
    └── 03/
        └── 14/
            ├── abc-123.json
            └── def-456.json
```

### Flat layout (`organize_by_date: false`)

```
/data/vcons/
├── abc-123.json
└── def-456.json
```

### With compression enabled

```
/data/vcons/
└── 2024/
    └── 03/
        └── 14/
            └── abc-123.json.gz
```

## Example

```yaml
storages:
  file:
    module: storage.file
    options:
      path: /data/vcons
      organize_by_date: true
      compression: true
      max_file_size: 52428800

chains:
  archive:
    links:
      - transcribe
    storages:
      - file
    ingress_lists:
      - default
    enabled: 1
```

## Notes

- On `delete`, empty parent directories created by date-based organization are automatically removed.
- The adapter searches both flat and date-organized layouts when locating a vCon by UUID, so the directory structure can be changed without losing access to previously stored files.
- For production deployments with large volumes of vCons, consider using the [S3](s3.md) adapter instead.
