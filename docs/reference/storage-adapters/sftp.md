# SFTP storage adapter

Intended to upload each vCon as a file to an SFTP server.

!!! warning "This adapter does not work as written"
    `save` fails on every upload, and `paramiko` is not in any dependency group. See [Check the known problems](#check-the-known-problems).

Module: `storage.sftp`. Needs `paramiko`, which `pyproject.toml` and `uv.lock` do not include, so the module will not import in any image.

## Configure the adapter

```yaml
storages:
  sftp:
    module: storage.sftp
    options:
      url: sftp.example.com
      port: 22
      username: example-user
      password: example-password
      path: /uploads
      add_timestamp_to_filename: true
      filename: vcon
      extension: json
```

## Set the options

The adapter reads every key directly, so all of them except `name` are required in an `options` block.

| Option | Type | Default | Description |
|---|---|---|---|
| `name` | string | `sftp` | Not read by the adapter |
| `url` | string | `sftp://localhost` | Passed to `paramiko.Transport` as the host name, so use a bare host. The default value has a scheme and will not resolve |
| `port` | integer | `22` | SSH port |
| `username` | string | `username` | SSH user |
| `password` | string | `password` | SSH password |
| `path` | string | `.` | Remote directory |
| `add_timestamp_to_filename` | boolean | `true` | Append `_<ISO timestamp>` to the file name |
| `filename` | string | `vcon` | File name stem. The vCon UUID is not part of the name |
| `extension` | string | `json` | File extension |

## Save a vCon

`save` opens a transport, reads the vCon through `VconRedis`, builds `<path>/<filename>[_<timestamp>].<extension>`, and calls `putfo`. The connection closes afterwards.

## Read a vCon

`get` ignores the requested UUID. It lists `path`, keeps files that start with `filename` and end with the extension, and returns the one with the greatest name. It returns `None` when nothing matches or on any error.

## Delete a vCon

The adapter has no `delete`.

## Handle a failed write

Any exception raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). The adapter has no retry.

## Check the known problems

- The local `SFTPClient` subclass overrides `putfo` with a method that calls itself, so each upload ends in `RecursionError`. The value passed is also a string, where paramiko expects a file object.
- `get` can return a different vCon from the one requested. Under the [storage fallback](index.md#read-a-vcon-back-from-storage) that record would be served as the requested vCon.
- With `add_timestamp_to_filename` off, every vCon writes to the same file name.
