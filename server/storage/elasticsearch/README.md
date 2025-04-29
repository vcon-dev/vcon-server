# Elasticsearch Storage

This module implements full-text search and analytics storage using Elasticsearch for the vCon server.

## Overview

Elasticsearch storage provides powerful full-text search capabilities, making it ideal for storing and searching vCon content with rich text analysis features.

## Configuration

Required configuration options:

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      hosts: ["http://localhost:9200"]  # Elasticsearch hosts
      index: vcons                      # Index name
      username: elastic                 # Optional: username
      password: changeme               # Optional: password
      use_ssl: false                   # Optional: use SSL
```

## Features

- Full-text search
- Rich text analysis
- Faceted search
- Aggregations
- Automatic metrics logging
- Bulk operations
- Index management

## Usage

```python
from storage import Storage

# Initialize Elasticsearch storage
es_storage = Storage("elasticsearch")

# Save vCon data
es_storage.save(vcon_id)

# Search vCons
results = es_storage.search({
    "query": {
        "match": {
            "content": "search term"
        }
    }
})
```

## Implementation Details

The Elasticsearch storage implementation:
- Uses elasticsearch-py for Elasticsearch connectivity
- Supports bulk operations for better performance
- Implements index lifecycle management
- Provides rich query DSL support
- Includes automatic metrics logging

## Dependencies

- elasticsearch
- elasticsearch-async (for async operations)

## Best Practices

1. Configure appropriate index settings
2. Use bulk operations for better performance
3. Implement proper mapping for fields
4. Set up index aliases for zero-downtime reindexing
5. Monitor cluster health and performance
6. Regular backup and maintenance
7. Use appropriate analyzers for text fields
8. Implement proper error handling 