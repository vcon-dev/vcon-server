# Space and Time Storage Module for vCon Server

This module provides integration with Space and Time's decentralized database for vCon Server, enabling secure storage with blockchain-level integrity and SQL compatibility.

## Features

- SQL-compatible storage interface
- Blockchain-level security
- Automatic table management
- Biscuit-based access control
- JSON data type support
- Connection management
- Automatic reconnection
- Schema validation

## Configuration

The module accepts the following configuration options:

```python
default_options = {
    "name": "spaceandtime",
    "api_key": "",                # Space and Time API key
    "table_name": "vcons",        # Target table name
    "write_biscuit": "",          # Write access biscuit
    "read_biscuit": "",           # Read access biscuit
    "authenticate": True,         # Auto-authenticate
    "auto_reconnect": True,      # Auto-reconnect on expiry
}
```

### Environment Variables

Required environment variables:

```bash
SXT_API_KEY=your_api_key
SXT_VCON_TABLENAME=vcons
SXT_VCON_TABLE_WRITE_BISCUIT=write_biscuit
SXT_VCON_TABLE_READ_BISCUIT=read_biscuit
```

## Table Schema

The module expects a table with the following schema:

| Column | Type | Description |
|--------|------|-------------|
| UUID | UUID | Primary key |
| VCON | TEXT | Raw vCon data |
| CREATED_AT | TIMESTAMP | Creation timestamp |
| SUBJECT | TEXT | vCon subject |
| VCON_JSON | JSONB | vCon data in JSON format |

## Usage

### Basic Usage

```python
from server.storage.spaceandtime import save, get

# Save a vCon
uuid = save(vcon_uuid, options)

# Retrieve a vCon
vcon_data = get(vcon_uuid, options)
```

### With Custom Configuration

```python
options = {
    "api_key": "your_api_key",
    "table_name": "custom_vcons",
    "write_biscuit": "write_access",
    "read_biscuit": "read_access"
}

# Use custom configuration
save(vcon_uuid, options)
```

## Authentication

The module supports two authentication methods:

1. API Key Authentication
   - Primary authentication method
   - Required for all operations
   - Automatically managed

2. Biscuit-based Access Control
   - Fine-grained permissions
   - Separate read/write access
   - Table-level control

## Error Handling

The module implements comprehensive error handling:

- Connection validation
- Authentication checks
- Schema validation
- Query error handling
- JSON parsing validation

## Logging

All operations are logged using the standard logging framework:

- Operation start/end
- Authentication status
- Query execution
- Error details
- Data validation

## Dependencies

Required packages:
- `spaceandtime`: Official Space and Time Python client
- `uuid6`: UUID generation
- `dotenv`: Environment variable management

## Development

### Running Tests

```bash
python -m pytest server/storage/spaceandtime/test_init.py
```

### Quick Test

```bash
python -m server.storage.spaceandtime
```

### Adding New Features

1. Update the storage implementation
2. Add new table columns if needed
3. Update schema validation
4. Update tests
5. Update documentation

## Troubleshooting

Common issues and solutions:

1. Authentication Issues
   - Verify API key validity
   - Check biscuit permissions
   - Verify environment variables

2. Connection Problems
   - Check network connectivity
   - Verify service status
   - Check authentication status

3. Data Issues
   - Verify schema compatibility
   - Check JSON validity
   - Validate UUID format

## Security Considerations

- API key protection
- Biscuit-based access control
- SQL injection prevention
- Data validation
- Secure connection handling

## Testing

The module includes a basic test function that can be run directly:

```python
from server.storage.spaceandtime import test

# Run basic tests
test()
```

This will:
1. Create a test vCon
2. Retrieve the test vCon
3. Test retrieval of non-existent vCon

## License

This module is part of the vCon Server project and follows its licensing terms. 