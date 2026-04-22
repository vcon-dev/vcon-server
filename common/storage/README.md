# Storage System

This directory contains the storage implementations for the vCon server. The storage system is designed to be modular and extensible, allowing for multiple storage backends to be used simultaneously.

## Overview

The storage system is built around a base `Storage` class that provides common functionality and metrics logging. Each storage implementation is a separate module that can be configured independently.

## Storage Types

The following storage backends are supported:

- **MongoDB** (`mongo/`): Document-based storage using MongoDB
- **Milvus** (`milvus/`): Vector database for similarity search
- **Elasticsearch** (`elasticsearch/`): Full-text search and analytics engine
- **PostgreSQL** (`postgres/`): Relational database storage
- **Space and Time** (`spaceandtime/`): Blockchain-based storage
- **ChatGPT Files** (`chatgpt_files/`): Storage for ChatGPT-related files
- **S3** (`s3/`): Object storage using Amazon S3
- **Redis** (`redis_storage/`): In-memory data structure store
- **SFTP** (`sftp/`): Secure file transfer protocol storage
- **File** (`file/`): Local file system storage

## Configuration

Storage backends are configured in the main configuration file. Each storage type can have its own options and settings.

Example configuration:
```yaml
storages:
  mongodb:
    module: storage.mongo
    options:
      uri: mongodb://localhost:27017
      database: vcon
  elasticsearch:
    module: storage.elasticsearch
    options:
      hosts: ["http://localhost:9200"]
```

## Usage

The storage system is used through the base `Storage` class:

```python
from storage import Storage

# Initialize a storage backend
storage = Storage("mongodb")

# Save data
storage.save(vcon_id)

# Retrieve data
data = storage.get(vcon_id)
```

## Metrics

All storage operations are automatically logged with timing metrics using the `@log_metrics` decorator. This provides visibility into storage performance and helps with monitoring and debugging.

## Adding New Storage Backends

To add a new storage backend:

1. Create a new directory in the `storage` folder
2. Implement the required interface (save/get methods)
3. Add configuration options
4. Update the main configuration file

See individual storage READMEs for specific implementation details. 