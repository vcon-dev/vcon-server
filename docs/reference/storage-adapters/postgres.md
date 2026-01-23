# postgres

Stores vCons in PostgreSQL database.

## Configuration

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      user: vcon
      password: vcon_password
      host: postgres
      port: "5432"
      database: vcon_server
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | string | `localhost` | Database host |
| `port` | string | `5432` | Database port |
| `database` | string | Required | Database name |
| `user` | string | Required | Database user |
| `password` | string | Required | Database password |
| `table` | string | `vcons` | Table name |

## Schema

The storage creates this table if it doesn't exist:

```sql
CREATE TABLE vcons (
    uuid VARCHAR(255) PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_vcons_created_at ON vcons(created_at);
```

## Example

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      host: postgres.example.com
      port: "5432"
      database: vcon_production
      user: vcon_app
      password: ${POSTGRES_PASSWORD}

chains:
  main:
    links:
      - transcribe
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

## Queries

Query vCons directly:

```sql
-- Get vCon by UUID
SELECT data FROM vcons WHERE uuid = 'abc-123';

-- Search by party phone
SELECT * FROM vcons 
WHERE data->'parties' @> '[{"tel": "+15551234567"}]';

-- Find recent vCons
SELECT uuid, created_at FROM vcons 
ORDER BY created_at DESC LIMIT 10;
```
