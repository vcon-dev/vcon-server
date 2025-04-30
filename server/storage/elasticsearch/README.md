# Elasticsearch Storage Module for vCon Server

This module provides Elasticsearch integration for vCon Server, enabling distributed storage and advanced search capabilities for vCons. It implements a component-based storage strategy where different parts of a vCon are stored in separate indices for optimized querying and search.

## Features

- Component-based storage architecture
- Automatic index management
- Support for Elastic Cloud and self-hosted deployments
- SSL/TLS security configuration
- JSON body parsing and validation
- Bulk operations support
- Configurable sharding and replication
- Tenant isolation support

## Configuration

The module accepts the following configuration options:

```python
default_options = {
    "name": "elasticsearch",
    "cloud_id": "",               # Elastic Cloud deployment ID
    "api_key": "",               # Elastic Cloud API key
    "url": "http://localhost:9200", # Self-hosted ES URL
    "username": "elastic",        # Basic auth username
    "password": "changeme",       # Basic auth password
    "ca_certs": None,            # Path to CA certificate
    "verify_certs": True,        # Whether to verify SSL certificates
    "index_prefix": "vcon_",     # Prefix for all indices
    "number_of_shards": 1,       # Number of primary shards per index
    "number_of_replicas": 1,     # Number of replica shards
}
```

### Environment Variables

Recommended environment variable configuration:

```bash
ELASTICSEARCH_URL=https://elasticsearch:9200
ELASTICSEARCH_USERNAME=elastic
ELASTICSEARCH_PASSWORD=changeme
ELASTICSEARCH_CLOUD_ID=deployment:xxx
ELASTICSEARCH_API_KEY=key
ELASTICSEARCH_CA_PATH=/path/to/ca.crt
```

## Index Structure

The module creates several indices for different vCon components:

| Index Pattern | Description | Example |
|--------------|-------------|----------|
| vcon_parties_* | Party information by role | vcon_parties_agent |
| vcon_attachments_* | Attachments by type | vcon_attachments_transcript |
| vcon_analysis_* | Analysis results by type | vcon_analysis_summary |
| vcon_dialog | Dialog entries | vcon_dialog |

## Usage

### Basic Usage

```python
from server.storage.elasticsearch import save, get

# Save a vCon
save(vcon_uuid, options)

# Retrieve a vCon
vcon_data = get(vcon_uuid, options)
```

### Cloud Configuration

```python
options = {
    "cloud_id": "deployment:xxx",
    "api_key": "key",
    "index_prefix": "prod_vcon_"
}

# Use cloud deployment
save(vcon_uuid, options)
```

### Self-hosted Configuration

```python
options = {
    "url": "https://elasticsearch:9200",
    "username": "elastic",
    "password": "changeme",
    "ca_certs": "/path/to/ca.crt"
}

# Use self-hosted deployment
save(vcon_uuid, options)
```

## Component Storage

### Parties
- Stored by role (agent, customer, etc.)
- Includes metadata and attributes
- Searchable by role and attributes

### Attachments
- Stored by type (transcript, metadata, etc.)
- JSON bodies are parsed if applicable
- Supports binary and text content

### Analysis
- Stored by analysis type
- Includes timestamps and metadata
- Supports structured and unstructured data

### Dialog
- Chronologically ordered
- Includes speaker information
- Supports rich media content

## Error Handling

The module implements comprehensive error handling:

- Connection validation
- Index existence checks
- Document validation
- Bulk operation error handling
- Detailed error logging

## Logging

All operations are logged using the standard logging framework:

- Operation start/end
- Component indexing status
- Search operations
- Error details
- Performance metrics

## Dependencies

- `elasticsearch`: Official Elasticsearch Python client
- `json`: JSON parsing and serialization
- Standard Python libraries

## Performance Considerations

- Uses bulk operations where possible
- Implements connection pooling
- Configurable sharding and replication
- Index optimization support
- Automatic retry mechanisms

## Development

### Running Tests

```bash
python -m pytest server/storage/elasticsearch/test_elasticsearch.py
```

### Adding New Features

1. Update the storage implementation
2. Add new indices if needed
3. Update mapping templates
4. Update tests
5. Update documentation

## Troubleshooting

Common issues and solutions:

1. Connection Issues
   - Verify Elasticsearch is running
   - Check network connectivity
   - Verify SSL/TLS configuration

2. Authentication Problems
   - Check credentials
   - Verify API key validity
   - Check role permissions

3. Index Issues
   - Check index existence
   - Verify mapping compatibility
   - Check storage capacity

## Security Considerations

- SSL/TLS support
- API key authentication
- Basic authentication
- Certificate validation
- Index-level security
- Role-based access control

## Contributing

1. Follow Elasticsearch best practices
2. Maintain type hints and documentation
3. Add tests for new features
4. Update README with significant changes

## Limitations

- Maximum document size (default 100MB)
- Index name restrictions
- Query complexity limits
- Storage capacity limits

## License

This module is part of the vCon Server project and follows its licensing terms. 