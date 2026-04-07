# sftp

Transfers vCons to a remote server over SFTP (SSH File Transfer Protocol). Each vCon is uploaded as a JSON file; the filename can optionally include a timestamp to avoid collisions.

## Prerequisites

- An accessible SFTP server with a valid account
- The `paramiko` Python package

```
pip install paramiko
```

## Configuration

```yaml
storages:
  sftp:
    module: storage.sftp
    options:
      url: sftp.example.com
      port: 22
      username: vcon_user
      password: ${SFTP_PASSWORD}
      path: /uploads/vcons
      filename: vcon
      extension: json
      add_timestamp_to_filename: true
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | `sftp` | Adapter name |
| `url` | string | `sftp://localhost` | SFTP server hostname or address |
| `port` | integer | `22` | SSH/SFTP port |
| `username` | string | `username` | SFTP account username |
| `password` | string | `password` | SFTP account password |
| `path` | string | `.` | Remote directory where files are uploaded |
| `filename` | string | `vcon` | Base name for the uploaded file |
| `extension` | string | `json` | File extension |
| `add_timestamp_to_filename` | boolean | `true` | Append an ISO 8601 timestamp to the filename to prevent overwriting (e.g. `vcon_2024-03-14T10:30:00.json`) |

## Example

```yaml
storages:
  sftp:
    module: storage.sftp
    options:
      url: files.example.com
      port: 22
      username: vcon_user
      password: ${SFTP_PASSWORD}
      path: /var/uploads/vcons
      filename: vcon
      extension: json
      add_timestamp_to_filename: true

chains:
  main:
    links:
      - transcribe
    storages:
      - sftp
    ingress_lists:
      - default
    enabled: 1
```

## File Naming

With `add_timestamp_to_filename: true` (default):

```
/var/uploads/vcons/vcon_2024-03-14T10:30:00.123456.json
```

With `add_timestamp_to_filename: false`:

```
/var/uploads/vcons/vcon.json
```

Disable the timestamp only when storing a single vCon at a time, or when your pipeline ensures the remote path is unique per transfer.

## Notes

- The adapter uses password-based authentication. SSH key-based authentication is not currently supported via configuration options.
- The `get` function lists the remote directory and returns the content of the lexicographically latest matching file, which corresponds to the most recently uploaded vCon when timestamps are enabled.
- The transport connection is opened and closed for each `save` or `get` call.
