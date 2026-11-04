# PostgreSQL storage adapter

Stores each vCon as one row in a PostgreSQL table, with the full vCon in a JSONB column.

Module: `storage.postgres`. Needs `peewee` and `psycopg2-binary`, from the `storage` dependency group.

## Configure the adapter

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      host: postgres
      port: 5432
      database: vcon_db
      user: postgres
      password: example-password
      table_name: vcons
```

The `postgres` service in `docker-compose.yml`, started by the `postgres` profile, creates no `vcon_db`. Match its development values instead:

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      host: postgres
      port: 5432
      database: postgres
      user: postgres
      password: postgres
```

## Set the options

The adapter reads the connection keys directly, so `database`, `user`, `password`, `host` and `port` are required in an `options` block.

| Option | Type | Default | Description |
|---|---|---|---|
| `name` | string | `postgres` | Not read by the adapter |
| `database` | string | `vcon_db` | Database name |
| `user` | string | `postgres` | Database user |
| `password` | string | `""` | Database password |
| `host` | string | `localhost` | Database host |
| `port` | integer | `5432` | Database port |
| `table_name` | string | `vcons` | Table name. Falls back to `vcons` when left out |

## Check the table

`save` creates the table if it does not exist. `get` and `delete` do not.

| Column | Type | Content |
|---|---|---|
| `id` | UUID, primary key | vCon UUID |
| `vcon` | TEXT | The vCon's syntax version, such as `0.4.0`. This column does not hold the vCon |
| `uuid` | UUID | vCon UUID again |
| `created_at` | TIMESTAMP | vCon `created_at` |
| `updated_at` | TIMESTAMP, nullable | Time of the last write |
| `subject` | TEXT, nullable | vCon subject |
| `vcon_json` | JSONB, nullable | The full vCon |

## Save a vCon

`save` reads the vCon through `VconRedis`, applies `EGRESS_FORMAT_VERSION`, opens a connection, creates the table if needed, and inserts the row. On a conflict on `id` it updates all columns. It closes the connection afterwards.

With `EGRESS_FORMAT_VERSION` set, `vcon_json` and the `vcon` column hold the legacy form. The server normalises the vCon up to the current form when it reads it back.

## Read a vCon

`get` returns `vcon_json`. It returns `None` when the row is missing or on any error, including a missing table.

## Delete a vCon

`delete` removes the row and returns `True`, or `False` when no row matched. It raises on a database error.

## Handle a failed write

Any exception raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). The adapter has no retry.

A repeated `save` is safe, because it upserts on `id`.

## Query the table

```sql
-- Get a vCon by UUID
SELECT vcon_json FROM vcons WHERE id = '018f4a2e-7b1c-8000-9000-000000000001';

-- Search by party phone
SELECT id FROM vcons
WHERE vcon_json->'parties' @> '[{"tel": "+15555550100"}]';

-- Find recent vCons
SELECT id, created_at FROM vcons
ORDER BY created_at DESC LIMIT 10;
```
