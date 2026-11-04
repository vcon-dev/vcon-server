# File storage adapter

Writes each vCon to the local file system as JSON, with optional gzip compression and date folders.

Module: `storage.file`. Needs no extra packages.

## Configure the adapter

```yaml
storages:
  file:
    module: storage.file
    options:
      path: /data/vcons
      organize_by_date: true
      compression: false
      max_file_size: 10485760
      file_permissions: 0644
      dir_permissions: 0755
```

!!! warning "Write permissions in a form YAML reads as a number"
    PyYAML reads `0644` as the integer 420, and reads `0o644` as the string `"0o644"`. A string in `file_permissions` makes `os.chmod` raise `TypeError`, which the adapter does not catch, so every save goes to the storage DLQ although the file was written. `example_config.yml` has this value. Use `0644` or `420`.

!!! warning "Share the path between containers"
    The API process also runs this adapter, for reads on a Redis miss and for [storage replay](../../operations/storage-recovery.md). `docker-compose.yml` mounts no volume at `/data` on `api` or `conserver`, so each container has its own folder. A read then finds nothing, and a replayed file lands in the `api` container. Mount one volume at `path` on both services.

## Set the options

Each key falls back to its default, so all of them are optional.

| Option | Type | Default | Description |
|---|---|---|---|
| `path` | string | `/data/vcons` | Base directory |
| `organize_by_date` | boolean | `true` | Write under `YYYY/MM/DD` from the vCon's `created_at` |
| `compression` | boolean | `false` | Gzip the file and use the `.json.gz` extension |
| `max_file_size` | integer | `10485760` | Largest allowed size in bytes, measured on the uncompressed JSON |
| `file_permissions` | integer | `0o644` | Mode set on the file. An `OSError` here is ignored |
| `dir_permissions` | integer | `0o755` | Mode set on directories. Any error here is ignored |

## Save a vCon

`save` reads the vCon through `VconRedis`, checks the size limit, and writes `<uuid>.json` or `<uuid>.json.gz`. With `organize_by_date` on, the path is `<path>/YYYY/MM/DD/<uuid>.<ext>`. When `created_at` is missing or will not parse, the file goes straight under `<path>`.

The adapter does not apply `EGRESS_FORMAT_VERSION`.

`_ensure_directory` applies `dir_permissions` to every ancestor of the file up to the file system root, not only to directories under `path`. As a non-root user it stops at the first directory it cannot change. As root it changes them all.

## Read a vCon

`get` looks for the file directly under `path`, then searches recursively. It tries the extension that matches `compression` first and then the other, so files survive a change to that option. It returns `None` when the file is missing or on any error.

## Delete a vCon

`delete` finds the file the same way, removes it, and removes any parent directories left empty, stopping at `path`. It returns `False` when nothing was found or on any error.

The module also has `exists` and `list_vcons`. `Storage` does not call them.

## Handle a failed write

Any exception in `save` raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). The adapter has no retry.

A vCon over `max_file_size` raises `ValueError` on each attempt. It will block a replay until you raise the limit, because draining stops at the first failure.

A repeated `save` overwrites the same path. If `compression` changed in between, both files remain.
