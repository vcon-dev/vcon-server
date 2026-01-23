# Architecture & Design

## System Architecture

### High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   API Clients   │     │  Webhook Sources│     │   Admin Tools   │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                         │
         ▼                       ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway (FastAPI)                    │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Auth Module │  │ Rate Limiter │  │ Request Router        │ │
│  └─────────────┘  └──────────────┘  └───────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
┌─────────────────┐                   ┌─────────────────────┐
│  vCon Service   │                   │ Configuration Mgmt  │
│  ┌───────────┐  │                   │  ┌───────────────┐ │
│  │   CRUD    │  │                   │  │ Config Store  │ │
│  │Operations │  │                   │  └───────────────┘ │
│  └───────────┘  │                   └─────────────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Processing Pipeline (Multi-Worker)                │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────┐   │
│  │Chain Manager│  │Link Executor│  │Storage Dispatcher        │   │
│  └─────────────┘  └─────────────┘  │(ThreadPoolExecutor)      │   │
│                                     └──────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Worker Processes (CONSERVER_WORKERS)            │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐       │  │
│  │  │Worker-1 │  │Worker-2 │  │Worker-3 │  │Worker-N │       │  │
│  │  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘       │  │
│  │       └────────────┴────────────┴────────────┘             │  │
│  │                         │ BLPOP (atomic)                    │  │
│  └─────────────────────────┼───────────────────────────────────┘  │
└────────────────────────────┼──────────────────────────────────────┘
                             │
         ┌───────────────────┴───────────────────┐
         ▼                                       ▼
┌─────────────┐ ┌─────────────────┐ ┌──────────────────────────┐
│Redis Queue  │ │  Link Modules   │ │Storage Adapters          │
│  & Cache    │ │  ┌───────────┐ │ │(Parallel Writes)         │
│┌───────────┐│ │  │Deepgram   │ │ │ ┌────────┬────────────┐ │
││ Ingress   ││ │  │Analyze    │ │ │ │Postgres│    S3      │ │
││ Egress    ││ │  │Webhook    │ │ │ ├────────┼────────────┤ │
││ DLQ       ││ │  │Tag Router │ │ │ │Elastic │   Milvus   │ │
│└───────────┘│ │  └───────────┘ │ │ └────────┴────────────┘ │
└─────────────┘ └─────────────────┘ └──────────────────────────┘
```

### Component Architecture

#### 1. API Layer
- **FastAPI Framework**: High-performance async API
- **Authentication**: Token-based with header validation
- **CORS Support**: Cross-origin resource sharing
- **OpenAPI/Swagger**: Auto-generated documentation

#### 2. Core Services
- **vCon Service**: CRUD operations and validation
- **Chain Manager**: Orchestrates processing pipelines
- **Link Executor**: Manages link module execution
- **Storage Dispatcher**: Routes to appropriate storage

#### 3. Data Layer
- **Redis**: Primary cache and queue management
- **Storage Adapters**: Pluggable persistence layer
- **Search Indices**: Optimized retrieval structures

## Design Patterns

### 1. Chain of Responsibility
```python
class Link:
    def process(self, vcon_uuid: str) -> str:
        # Process vCon
        result = self.execute(vcon_uuid)
        # Pass to next link
        return vcon_uuid
```

### 2. Adapter Pattern
```python
class StorageAdapter:
    def save(self, vcon_uuid: str, options: dict) -> None:
        # Implementation specific
        pass
    
    def get(self, vcon_uuid: str, options: dict) -> dict:
        # Implementation specific
        pass
```

### 3. Factory Pattern
```python
class LinkFactory:
    @staticmethod
    def create_link(module_name: str, options: dict) -> Link:
        module = importlib.import_module(module_name)
        return module.Link(options)
```

### 4. Observer Pattern
```python
class EventDispatcher:
    def emit(self, event: str, data: dict):
        for listener in self.listeners[event]:
            listener.handle(data)
```

## Data Flow

### 1. Ingress Flow
```
API Request → Validation → Redis Queue → Chain Processing → Storage
     │                          │                │
     └── Authentication         └── Indexing     └── Notifications
```

### 2. Processing Flow
```
vCon UUID → Retrieve from Redis → Link 1 → Link 2 → ... → Link N
                │                     │        │              │
                └── Fallback          └── Update vCon        └── Store
                    to Storage
```

### 3. Egress Flow
```
Processed vCon → Egress Queue → External Systems
                     │               │
                     └── Webhooks    └── APIs
```

## Scalability Design

### Multi-Worker Processing
The server supports multiple parallel worker processes for improved throughput:

```
┌─────────────────────────────────────────────────────────┐
│                    Main Process                          │
│  - Spawns N worker processes (CONSERVER_WORKERS)        │
│  - Monitors worker health, restarts on failure          │
│  - Handles graceful shutdown (SIGTERM/SIGINT)           │
└────────────────────────┬────────────────────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌─────────┐        ┌─────────┐        ┌─────────┐
│Worker-1 │        │Worker-2 │        │Worker-N │
│ (PID A) │        │ (PID B) │        │ (PID N) │
└────┬────┘        └────┬────┘        └────┬────┘
     │                  │                  │
     └──────────────────┴──────────────────┘
                        │
                        ▼ BLPOP (atomic)
                 ┌──────────────┐
                 │ Redis Queues │
                 └──────────────┘
```

**Key Features:**
- **Atomic Distribution**: Redis BLPOP ensures each vCon is processed by exactly one worker
- **Process Isolation**: Worker crashes don't affect other workers
- **Graceful Shutdown**: Workers complete current vCon before exiting
- **Auto-Restart**: Main process restarts failed workers

### Parallel Storage Operations
When multiple storage backends are configured, writes execute concurrently:

```python
# Sequential (old): ~400ms for 4 backends @ 100ms each
for storage in storages:
    storage.save(vcon)

# Parallel (new): ~100ms for 4 backends @ 100ms each
with ThreadPoolExecutor(max_workers=len(storages)) as executor:
    futures = [executor.submit(s.save, vcon) for s in storages]
    for future in as_completed(futures):
        future.result()
```

### Horizontal Scaling
1. **Multi-Worker Mode**: Scale within instance via CONSERVER_WORKERS
2. **Multi-Instance**: Scale instances across hosts
3. **Queue-Based Distribution**: Redis BLPOP for atomic work distribution
4. **Shared Nothing Architecture**: Independent worker processes
5. **Load Balancing**: Redis queues provide natural load balancing

### Vertical Scaling
1. **Worker Count**: Increase CONSERVER_WORKERS for more parallelism
2. **Resource Pooling**: Connection pools per worker
3. **Parallel Storage**: Concurrent writes to multiple backends
4. **Caching Strategy**: Multi-tier caching
5. **Start Method Selection**: Choose fork/spawn based on memory needs

### Database Design

#### Redis Schema
```
# vCon Storage
vcon:{uuid} → JSON document

# Search Indices
tel:{phone} → SET of UUIDs
mailto:{email} → SET of UUIDs
name:{name} → SET of UUIDs

# Sorted Set (by timestamp)
vcons → ZSET of UUID:timestamp

# Queues
{chain}_ingress → LIST of UUIDs
{chain}_egress → LIST of UUIDs
{chain}_dlq → LIST of failed UUIDs
```

#### PostgreSQL Schema
```sql
CREATE TABLE vcons (
    id UUID PRIMARY KEY,
    vcon TEXT NOT NULL,
    uuid UUID UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subject TEXT,
    vcon_json JSONB NOT NULL
);

CREATE INDEX idx_vcons_created_at ON vcons(created_at);
CREATE INDEX idx_vcons_uuid ON vcons(uuid);
CREATE INDEX idx_vcons_json ON vcons USING GIN(vcon_json);
```

## Security Architecture

### Authentication Flow
```
Request → API Gateway → Token Validation → Authorized Request
              │                │
              └── Rate Limit   └── Audit Log
```

### Data Security
1. **Encryption at Rest**: Storage-level encryption
2. **Encryption in Transit**: TLS 1.3
3. **Access Control**: Token-based authentication
4. **Audit Trails**: Comprehensive logging

### Network Security
```
Internet → WAF → Load Balancer → API Gateway → Internal Network
                       │                              │
                       └── SSL Termination           └── Private Subnet
```

## Performance Optimization

### Caching Strategy
```
L1 Cache: Application Memory (10ms)
    ↓
L2 Cache: Redis (1ms)
    ↓
L3 Cache: CDN (Regional)
    ↓
Origin: Storage Backend
```

### Query Optimization
1. **Index Design**: Covering indices
2. **Query Planning**: Prepared statements
3. **Connection Pooling**: Reuse connections
4. **Batch Operations**: Reduce round trips

## Reliability Design

### Fault Tolerance
1. **Circuit Breakers**: Prevent cascade failures
2. **Retry Logic**: Exponential backoff
3. **Dead Letter Queues**: Capture failures
4. **Health Checks**: Proactive monitoring

### High Availability
```
┌─────────────┐     ┌─────────────┐
│   Primary   │────│   Standby   │
└──────┬──────┘     └──────┬──────┘
       │                   │
┌──────▼──────┐     ┌──────▼──────┐
│ Redis Master│────│Redis Replica│
└─────────────┘     └─────────────┘
```

### Disaster Recovery
1. **Backup Strategy**: Regular snapshots
2. **Replication**: Multi-region copies
3. **Recovery Time Objective**: < 1 hour
4. **Recovery Point Objective**: < 5 minutes

## Monitoring Architecture

### Metrics Collection
```
Application → StatsD → Aggregator → Time Series DB → Dashboard
     │                                    │
     └── Logs → Elasticsearch            └── Alerts
```

### Key Metrics
- **System**: CPU, Memory, Disk, Network
- **Application**: Request rate, Error rate, Latency
- **Business**: vCons processed, Success rate
- **Queue**: Length, Processing time

## Development Architecture

### Module Structure
```
server/
├── api.py              # API endpoints
├── main.py             # Core processing
├── config.py           # Configuration
├── links/              # Link modules
│   ├── __init__.py
│   └── {link_name}/
├── storage/            # Storage adapters
│   ├── __init__.py
│   └── {storage_name}/
└── lib/                # Shared libraries
```

### Testing Strategy
1. **Unit Tests**: Individual components
2. **Integration Tests**: Component interaction
3. **End-to-End Tests**: Full pipeline
4. **Performance Tests**: Load testing

### CI/CD Pipeline
```
Code Push → Build → Unit Tests → Integration Tests → Deploy Staging → E2E Tests → Deploy Production
                         │                                    │
                         └── Code Quality Checks             └── Rollback on Failure
```