# Space and Time storage adapter

Intended to insert each vCon as a row in a Space and Time table.

!!! warning "This adapter does not work as written"
    `save` fails for real vCons and hides the failure, and the `spaceandtime` package is not in any dependency group. See [Check the known problems](#check-the-known-problems).

Module: `storage.spaceandtime`. Needs `spaceandtime`, which `pyproject.toml` and `uv.lock` do not include, so the module will not import in any image.

## Configure the adapter

```yaml
storages:
  spaceandtime:
    module: storage.spaceandtime
```

Connection settings come from the environment, not from `options`. The module also calls `load_dotenv()`.

| Variable | Use |
|---|---|
| `SXT_API_KEY` | API key |
| `SXT_VCON_TABLENAME` | Table name |
| `SXT_VCON_TABLE_WRITE_BISCUI` | Write biscuit, used for reads as well. The code reads this exact name, with no final `T` |

See the [environment reference](../environment.md).

The module authenticates at import time, so a bad key fails when `Storage` first loads it.

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `name` | string | `spaceandtime` | Not read by the adapter |

`save` and `get` use no other option.

## Save a vCon

`save` reads the vCon through `VconRedis`, refreshes the session if it has expired, checks each vCon key against the table columns, and inserts one row.

`save` has a self-test branch. When the UUID is the literal string `test`, it builds a stub record with `"vcon": "test"` and writes that. The `__main__` block in the module uses it. Real vCons do not reach this branch.

## Read a vCon

`get` selects on `uuid` and returns the parsed `VCON_JSON` column. It returns `None` when no row matches or on any error. Those errors are logged with the text `Postgres storage plugin`.

## Delete a vCon

The adapter has no `delete`.

## Handle a failed write

`save` catches every exception, logs it and returns. The server counts a success and nothing reaches the [storage DLQ](index.md#handle-a-failed-write), so a failed write can only be found in the logs. Search for `spaceandtime storage plugin: failed to insert`.

## Check the known problems

- `VconRedis.get_vcon` returns a `Vcon` object, and `save` then calls `vcon.keys()`. `Vcon` has no such method, so each real save logs `AttributeError` and writes nothing.
- `get` builds its SQL by string formatting. The API validates the UUID path parameter. Other callers pass the id as given.
- `common/storage/spaceandtime/README.md` lists options and variables the code does not read.
