# MongoDB Storage

This module implements document-based storage using MongoDB for the vCon server.

## Overview

MongoDB storage provides a flexible, document-oriented storage solution that's well-suited for storing vCon data. It supports rich querying capabilities and horizontal scaling.

## Configuration

Required configuration options:

```yaml
storages:
  mongodb:
    module: storage.mongo
    options:
      uri: mongodb://localhost:27017  # MongoDB connection URI
      database: vcon                  # Database name
      collection: vcons              # Collection name (optional, defaults to 'vcons')
```

## Features

- Document-based storage
- Rich querying capabilities
- Indexing support
- Automatic metrics logging
- Connection pooling
- Error handling and retries

## Usage

```python
from storage import Storage

# Initialize MongoDB storage
mongo_storage = Storage("mongodb")

# Save a vCon
mongo_storage.save(vcon_id)

# Retrieve a vCon
vcon_data = mongo_storage.get(vcon_id)
```

## Implementation Details

The MongoDB storage implementation:
- Uses PyMongo for MongoDB connectivity
- Implements connection pooling for better performance
- Includes automatic retry logic for transient failures
- Supports custom indexes for optimized queries
- Provides metrics for monitoring performance

## Dependencies

- pymongo
- motor (for async operations)

## Best Practices

1. Always use indexes for frequently queried fields
2. Configure appropriate connection pool sizes
3. Use proper error handling for database operations
4. Monitor performance metrics
5. Regular backup and maintenance 