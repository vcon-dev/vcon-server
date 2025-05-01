# PostgreSQL Storage

This module implements relational database storage using PostgreSQL for the vCon server.

## Overview

PostgreSQL storage provides robust relational database capabilities, making it ideal for storing structured vCon data with strong consistency and ACID compliance.

## Configuration

Required configuration options:

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      host: localhost           # PostgreSQL host
      port: 5432               # PostgreSQL port
      database: vcon           # Database name
      user: postgres           # Username
      password: changeme       # Password
      schema: public           # Optional: schema name
```

## Features

- ACID compliance
- Relational data storage
- Transaction support
- JSON/JSONB support
- Automatic metrics logging
- Connection pooling
- Migration management

## Usage

```python
from storage import Storage

# Initialize PostgreSQL storage
pg_storage = Storage("postgres")

# Save vCon data
pg_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = pg_storage.get(vcon_id)
```

## Implementation Details

The PostgreSQL storage implementation:
- Uses SQLAlchemy for database operations
- Implements connection pooling
- Supports migrations using Alembic
- Provides transaction management
- Includes automatic metrics logging

## Dependencies

- sqlalchemy
- psycopg2-binary
- alembic (for migrations)

## Best Practices

1. Use appropriate indexes
2. Implement connection pooling
3. Use transactions for data consistency
4. Regular database maintenance
5. Monitor query performance
6. Implement proper error handling
7. Use appropriate data types
8. Regular backups
9. Use prepared statements
10. Implement proper schema versioning 