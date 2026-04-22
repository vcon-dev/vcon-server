# vCon Server Core Documentation

## Overview

The vCon Server is a robust processing pipeline designed to handle vCon objects through configurable processing chains. It implements a Redis-based queue system for managing the flow of vCons through various processing stages.

## Core Components

### 1. Main Processing Pipeline (`main.py`)

The main processing pipeline is the heart of the vCon server, responsible for:
- Managing processing chains
- Handling vCon processing through configured links
- Managing storage operations
- Implementing queue-based processing

#### Key Classes and Functions

##### `VconChainRequest`
The primary class for processing individual vCons through a chain:
- Manages the execution of processing links
- Handles storage operations
- Controls egress queue placement
- Tracks processing metrics and timing

Key methods:
- `process()`: Main processing loop for a vCon
- `_process_link()`: Handles individual link processing
- `_process_storage()`: Manages storage backend operations
- `_wrap_up()`: Handles post-processing operations

##### Chain Configuration
The system uses a `ChainConfig` TypedDict to define processing chains with:
- Chain name
- Processing links
- Storage backends
- Ingress/egress queues
- Processing timeout
- Enable/disable status

### 2. Configuration Management (`config.py`)

The configuration system provides:
- YAML-based configuration loading
- Centralized config access
- Storage configuration management
- Follower configuration management
- Import configuration management
- Ingress authentication configuration for external API access

### 3. API Layer (`api.py`)

The API layer provides HTTP endpoints for vCon submission and management:
- RESTful API endpoints using FastAPI
- Authentication and authorization mechanisms
- Internal vCon submission (`/vcon`) with full system access
- External partner submission (`/vcon/external-ingress`) with scoped access
- API key validation and ingress-specific access control
- Request validation and error handling

#### Key Features
- **Multi-tier Authentication**: Different API keys for internal vs external access
- **Scoped Authorization**: External API keys limited to specific ingress lists
- **Input Validation**: Automatic vCon schema validation
- **Error Handling**: Comprehensive HTTP error responses
- **Logging**: Detailed request and processing logging

### 4. Redis Queue Management (`redis_mgr.py`)

The Redis management system provides:
- Connection pool management
- Synchronous and asynchronous client support
- JSON-based key-value operations
- Pattern-based key searching
- Connection lifecycle management

## Processing Flow

1. **Ingress**
   - vCons enter through multiple pathways:
     - **API Endpoints**: HTTP submission via `/vcon` (internal) or `/vcon/external-ingress` (external partners)
     - **Queue Processing**: Direct ingress queue processing for automated workflows
   - Each ingress queue is mapped to a specific processing chain
   - API submissions are authenticated and automatically queued to specified ingress lists

2. **Chain Processing**
   - vCons are processed through configured links in sequence
   - Each link can modify the vCon or halt processing
   - Processing metrics and timing are tracked

3. **Storage**
   - Processed vCons are saved to configured storage backends
   - Multiple storage backends can be configured per chain

4. **Egress**
   - Processed vCons are forwarded to configured egress queues
   - Multiple egress queues can be configured per chain

## Authentication and Authorization

The system implements multi-tier authentication and authorization:

### API Authentication
- **Header-based Authentication**: Uses `x-conserver-api-token` header
- **Internal API Keys**: Full system access for internal operations
- **External API Keys**: Scoped access limited to specific ingress lists

### Authorization Levels
1. **Internal Access**: Full system access with main API token
   - Access to all API endpoints
   - Full vCon retrieval and management capabilities
   - System configuration access

2. **External Partner Access**: Limited scope via `ingress_auth` configuration
   - Access only to `/vcon/external-ingress` endpoint
   - Restricted to pre-configured ingress lists
   - No access to existing vCon data or system resources

### Configuration-Based Access Control
- External API keys are configured in `config.yml` under `ingress_auth`
- Supports single or multiple API keys per ingress list
- Provides secure isolation between different external partners

## Error Handling

The system implements comprehensive error handling:
- Link-level error tracking
- Storage operation error handling
- API authentication and authorization errors
- Graceful shutdown support
- Dead Letter Queue (DLQ) for failed processing

## Metrics and Monitoring

The system tracks various metrics:
- vCon processing time
- Link-level processing time
- Processing counts
- Queue lengths
- Error rates

## Configuration

The system is configured through a YAML file that defines:
- Processing chains
- Link configurations
- Storage backends
- Queue mappings
- Processing timeouts
- External API authentication (`ingress_auth`)

### Ingress Authentication Configuration
The `ingress_auth` section configures external partner access:
```yaml
ingress_auth:
  # Single API key per ingress list
  customer_data: "api-key-123"
  
  # Multiple API keys per ingress list
  support_calls:
    - "partner1-key"
    - "partner2-key"
```

## Dependencies

Core dependencies include:
- Redis for queue management and vCon storage
- FastAPI for HTTP API endpoints and request handling
- PyYAML for configuration management
- Pydantic for data validation and serialization
- Custom storage backends
- Processing link modules

## Best Practices

1. **Chain Configuration**
   - Keep chains focused and modular
   - Configure appropriate timeouts
   - Enable/disable chains as needed

2. **Link Development**
   - Implement proper error handling
   - Return appropriate continue/halt signals
   - Log processing details

3. **Storage Configuration**
   - Configure appropriate storage backends
   - Handle storage failures gracefully
   - Monitor storage performance

4. **Queue Management**
   - Monitor queue lengths
   - Configure appropriate DLQs
   - Handle queue processing errors

5. **API Security**
   - Use strong, unique API keys for external partners
   - Rotate API keys regularly for security
   - Configure minimal necessary access per ingress list
   - Monitor API usage and authentication attempts
   - Implement rate limiting for external endpoints

6. **Authentication Configuration**
   - Separate internal and external API keys
   - Use configuration-based access control
   - Document API key assignments and permissions
   - Test authentication scenarios thoroughly 