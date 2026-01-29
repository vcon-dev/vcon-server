# ChatGPT Files Storage Module for vCon Server

This module enables vCon Server to store and retrieve vCons using OpenAI's Files API, making them available for use with ChatGPT and other OpenAI services. It includes support for vector store integration, enabling semantic search capabilities.

## Features

- Direct integration with OpenAI's Files API
- Vector store support for semantic search
- Automatic file lifecycle management
- Support for multiple OpenAI organizations and projects
- Temporary file cleanup
- Configurable file naming

## Configuration

The module accepts the following configuration options:

```python
default_options = {
    "organization_key": "org-xxxxx",      # OpenAI organization ID
    "project_key": "proj_xxxxxxx",        # OpenAI project ID
    "api_key": "YOUR_OPENAI_API_KEY",     # OpenAI API key
    "vector_store_id": "xxxxxx",          # Vector store ID for embeddings
    "purpose": "assistants",              # Purpose for file upload
    "cleanup_local_files": True,          # Auto-cleanup of temp files
    "file_prefix": "",                    # Optional file name prefix
}
```

### Environment Variables

Recommended environment variable configuration:

```bash
OPENAI_API_KEY=YOUR_OPENAI_API_KEY
OPENAI_ORG_ID=org-...
OPENAI_PROJECT_ID=proj_...
OPENAI_VECTOR_STORE_ID=vs-...
```

## Usage

### Basic Usage

```python
from server.storage.chatgpt_files import save, get

# Save a vCon
save(vcon_uuid, options)

# Retrieve a vCon
vcon_data = get(vcon_uuid, options)
```

### With Vector Store Integration

```python
options = {
    "organization_key": "org-xxx",
    "project_key": "proj_xxx",
    "api_key": "YOUR_OPENAI_API_KEY",
    "vector_store_id": "vs-xxx",
    "purpose": "assistants"
}

# Save vCon and add to vector store
save(vcon_uuid, options)
```

## File Storage Details

### File Format

- Files are stored with the pattern: `{prefix}{uuid}.vcon.json`
- JSON format for compatibility with OpenAI services
- Automatic content-type detection

### Vector Store Integration

- Optional integration with OpenAI's vector stores
- Enables semantic search capabilities
- Automatic embedding generation
- Configurable vector store settings

## Error Handling

The module implements comprehensive error handling:

- API authentication validation
- Network error handling
- File operation error management
- Automatic cleanup on failures
- Detailed error logging

## Logging

All operations are logged using the standard logging framework:

- Operation start/end
- File upload/download status
- Vector store operations
- Error details
- Cleanup operations

## Dependencies

- `openai`: OpenAI Python client
- `redis_mgr`: Redis client for vCon retrieval
- Standard Python libraries: `json`, `os`

## Performance Considerations

- Uses temporary local files for upload
- Automatic file cleanup
- Efficient file searching
- Connection reuse through client objects

## Development

### Running Tests

```bash
python -m pytest server/storage/chatgpt_files/test_init.py
```

### Adding New Features

1. Update the storage implementation in `__init__.py`
2. Add new configuration options if needed
3. Update tests
4. Update documentation

## Troubleshooting

Common issues and solutions:

1. Authentication Errors

   - Verify API key validity
   - Check organization and project IDs
   - Ensure proper permissions

2. File Upload Failures

   - Check file size limits
   - Verify file format
   - Check network connectivity

3. Vector Store Issues
   - Verify vector store ID
   - Check embedding compatibility
   - Ensure vector store access

## Security Considerations

- API keys are never logged
- Temporary files are securely handled
- Automatic cleanup of sensitive data
- Support for organization isolation

## Contributing

1. Follow OpenAI's best practices
2. Maintain type hints and documentation
3. Add tests for new features
4. Update README with significant changes

## Limitations

- File size limits apply (varies by OpenAI tier)
- Rate limits based on OpenAI account type
- Vector store availability depends on OpenAI access level
- Temporary local storage required for uploads

## License

This module is part of the vCon Server project and follows its licensing terms.
