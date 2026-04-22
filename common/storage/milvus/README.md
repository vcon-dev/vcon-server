# Milvus Storage

This module implements vector database storage using Milvus for the vCon server.

## Overview

Milvus storage provides high-performance vector similarity search capabilities, ideal for storing and retrieving vector embeddings of vCon data. It's particularly useful for semantic search and similarity matching applications.

## Configuration

Required configuration options:

```yaml
storages:
  milvus:
    module: storage.milvus
    options:
      host: localhost           # Milvus server host
      port: 19530              # Milvus server port
      collection: vcon_vectors # Collection name
      dim: 1536               # Vector dimension
      index_type: IVF_FLAT    # Index type
      metric_type: L2         # Distance metric
```

## Features

- Vector similarity search
- Multiple index types support
- Scalable vector storage
- Automatic metrics logging
- Batch operations
- Partition management

## Usage

```python
from storage import Storage

# Initialize Milvus storage
milvus_storage = Storage("milvus")

# Save vector embeddings
milvus_storage.save(vcon_id)

# Search similar vectors
results = milvus_storage.search(query_vector, top_k=10)
```

## Implementation Details

The Milvus storage implementation:
- Uses pymilvus for Milvus connectivity
- Supports multiple index types (IVF_FLAT, HNSW, etc.)
- Implements efficient batch operations
- Provides partition management
- Includes automatic metrics logging

## Dependencies

- pymilvus
- numpy

## Best Practices

1. Choose appropriate index type based on your use case
2. Configure proper partition strategy
3. Use batch operations for better performance
4. Monitor search latency metrics
5. Regular index optimization
6. Implement proper error handling
7. Use appropriate distance metrics for your data