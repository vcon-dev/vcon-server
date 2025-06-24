# Storage Adapters

## Overview

vCon Server supports multiple storage backends through a modular adapter system. Each storage adapter implements a common interface while providing backend-specific optimizations and features.

## Available Storage Adapters

### 1. PostgreSQL Storage
**Purpose**: Relational database storage with JSONB support

**Key Features**:
- Native JSONB storage for efficient querying
- Indexed metadata fields
- ACID compliance
- Automatic schema management
- Connection pooling

**Use Cases**:
- Primary production storage
- Complex querying requirements
- Transactional consistency needs

**Configuration**:
```yaml
postgres:
  module: storage.postgres
  options:
    host: localhost
    port: 5432
    database: vcon_db
    user: postgres
    password: secure_password
```

### 2. MongoDB Storage
**Purpose**: Document-based NoSQL storage

**Key Features**:
- Native JSON document storage
- Flexible schema
- Horizontal scaling
- Rich query capabilities

**Use Cases**:
- Large-scale deployments
- Flexible schema requirements
- Geographic distribution

### 3. Elasticsearch Storage
**Purpose**: Full-text search and analytics

**Key Features**:
- Component-based storage architecture
- Advanced search capabilities
- Real-time analytics
- Distributed architecture
- Multiple index support

**Use Cases**:
- Advanced search requirements
- Analytics and reporting
- Log aggregation
- Multi-tenant deployments

**Configuration**:
```yaml
elasticsearch:
  module: storage.elasticsearch
  options:
    cloud_id: "deployment:xxx"
    api_key: "your-api-key"
    index_prefix: "vcon_"
```

### 4. S3 Storage
**Purpose**: Object storage for long-term archival

**Key Features**:
- Unlimited storage capacity
- High durability (99.999999999%)
- Lifecycle management
- Cross-region replication
- Cost-effective archival

**Use Cases**:
- Long-term archival
- Backup storage
- Compliance requirements
- Media file storage

**Configuration**:
```yaml
s3:
  module: storage.s3
  options:
    bucket: vcon-storage
    region: us-west-2
    access_key: AWS_ACCESS_KEY
    secret_key: AWS_SECRET_KEY
```

### 5. Milvus Vector Storage
**Purpose**: Vector database for semantic search

**Key Features**:
- High-performance vector similarity search
- Multiple index types (IVF_FLAT, HNSW)
- Scalable architecture
- GPU acceleration support
- Hybrid search capabilities

**Use Cases**:
- Semantic search
- Similar conversation finding
- AI/ML applications
- Recommendation systems

**Configuration**:
```yaml
milvus:
  module: storage.milvus
  options:
    host: localhost
    port: 19530
    collection: vcon_vectors
    dim: 1536
    embedding_model: "text-embedding-3-small"
```

### 6. Redis Storage
**Purpose**: In-memory storage for high-speed access

**Key Features**:
- Microsecond latency
- Pub/sub capabilities
- TTL support
- Cluster mode

**Use Cases**:
- Hot data caching
- Real-time applications
- Session storage

### 7. File Storage
**Purpose**: Local filesystem storage

**Key Features**:
- Simple deployment
- No external dependencies
- Directory-based organization

**Use Cases**:
- Development environments
- Small deployments
- Backup to local disk

### 8. SFTP Storage
**Purpose**: Remote file storage via SFTP

**Key Features**:
- Secure file transfer
- Remote storage
- Standard protocol support

**Use Cases**:
- Legacy system integration
- Partner data exchange
- Remote backup

### 9. Dataverse Storage
**Purpose**: Research data repository

**Key Features**:
- DOI assignment
- Metadata standards
- Version control
- Access control

**Use Cases**:
- Research projects
- Academic institutions
- Data publication

### 10. Space and Time Storage
**Purpose**: Blockchain-verified data warehouse

**Key Features**:
- Cryptographic proofs
- Tamper-proof storage
- SQL interface
- Decentralized architecture

**Use Cases**:
- Compliance requirements
- Audit trails
- Verified data storage

## Storage Selection Guide

### Performance Requirements
- **Highest Performance**: Redis, Milvus
- **High Performance**: PostgreSQL, MongoDB, Elasticsearch
- **Standard Performance**: S3, File, SFTP

### Scalability
- **Unlimited**: S3, Elasticsearch, MongoDB
- **High**: PostgreSQL, Milvus
- **Limited**: File, Redis (without cluster)

### Query Capabilities
- **Advanced Search**: Elasticsearch, Milvus
- **SQL Queries**: PostgreSQL, Space and Time
- **Document Queries**: MongoDB
- **Key-Value**: Redis, S3

### Cost Considerations
- **Low Cost**: File, PostgreSQL
- **Medium Cost**: MongoDB, Redis
- **Usage-Based**: S3, Elasticsearch Cloud

## Multi-Storage Strategies

### Common Patterns

1. **Hot-Warm-Cold Architecture**
   ```yaml
   storages:
     - redis      # Hot: Recent data
     - postgres   # Warm: Active data
     - s3         # Cold: Archival
   ```

2. **Search + Storage**
   ```yaml
   storages:
     - elasticsearch  # Search index
     - postgres      # Primary storage
   ```

3. **Geographic Distribution**
   ```yaml
   storages:
     - postgres_us   # US region
     - postgres_eu   # EU region
     - s3_global    # Global backup
   ```

## Implementation Best Practices

1. **Use Multiple Storages**: Combine storages for optimal performance and cost
2. **Configure Indexes**: Ensure proper indexing for query patterns
3. **Monitor Performance**: Track storage metrics and latency
4. **Plan for Growth**: Choose scalable options early
5. **Implement Backup**: Always have a backup storage configured
6. **Consider Compliance**: Choose storages that meet regulatory requirements