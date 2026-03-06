# PostgreSQL Storage Module for vCon Server

This module provides PostgreSQL storage integration for vCon Server, allowing vCons to be stored and retrieved from a PostgreSQL database.

## Features

- Full vCon storage in native JSONB format
- Indexed metadata fields for efficient querying
- Automatic table creation and schema management
- Connection pooling and proper resource cleanup
- Upsert support (insert or update based on UUID)

## Configuration

The module accepts the following configuration options:

```python
default_options = {
    "name": "postgres",      # Storage name identifier
    "database": "vcon_db",   # Database name
    "user": "postgres",      # Database username
    "password": "",          # Database password
    "host": "localhost",     # Database host
    "port": 5432,           # Database port
}
```

### Environment Variables

While configuration can be passed directly through options, it's recommended to use environment variables for sensitive information:

```bash
POSTGRES_DB=vcon_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

## Database Schema

The module creates a `vcons` table with the following schema:

| Column     | Type      | Description                        |
| ---------- | --------- | ---------------------------------- |
| id         | UUID      | Primary key (same as vCon UUID)    |
| vcon       | TEXT      | Raw vCon data                      |
| uuid       | UUID      | vCon UUID (indexed for lookups)    |
| created_at | TIMESTAMP | Creation timestamp                 |
| updated_at | TIMESTAMP | Last update timestamp              |
| subject    | TEXT      | vCon subject (for quick access)    |
| vcon_json  | JSONB     | vCon data in queryable JSON format |

## Usage

### Basic Usage

```python
from server.storage.postgres import save, get

# Save a vCon
save(vcon_uuid, options)

# Retrieve a vCon
vcon_data = get(vcon_uuid, options)
```

### Custom Configuration

```python
options = {
    "database": "custom_db",
    "user": "custom_user",
    "password": "custom_password",
    "host": "custom.host",
    "port": 5432
}

# Use custom configuration
save(vcon_uuid, options)
```

## Error Handling

The module implements comprehensive error handling:

- Connection errors are caught and logged
- Resource cleanup is guaranteed through `finally` blocks
- Non-existent vCons return `None` instead of raising exceptions
- Database errors are logged with detailed error messages

## Logging

All operations are logged using the standard logging framework:

- Operation start/end
- Errors with full stack traces
- Performance metrics
- Success/failure status

## Dependencies

- `peewee`: ORM for database operations
- `psycopg2`: PostgreSQL adapter for Python
- `playhouse`: Extended Peewee functionality

## Performance Considerations

- Uses connection pooling for efficient connection management
- Indexes on UUID and created_at fields
- JSONB type for efficient JSON operations
- Prepared statements for common operations

## Development

### Running Tests

```bash
python -m pytest server/storage/postgres/test_postgres.py
```

### Adding New Features

1. Update the schema in `__init__.py`
2. Add migration scripts if needed
3. Update tests
4. Update documentation

## Troubleshooting

Common issues and solutions:

1. Connection Refused

   - Check if PostgreSQL is running
   - Verify port configuration
   - Check firewall settings

2. Authentication Failed

   - Verify credentials
   - Check database user permissions
   - Ensure database exists

3. Schema Issues
   - Run with `create_tables(safe=True)`
   - Check table permissions
   - Verify database encoding

## Contributing

1. Follow the established error handling patterns
2. Maintain type hints and documentation
3. Add tests for new features
4. Update README with significant changes

## License

This module is part of the vCon Server project and follows its licensing terms.
