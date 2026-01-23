# Core Functionality

## vCon Data Model

### Structure
The vCon (Voice Conversation) is the fundamental data structure that represents a conversation:

```json
{
  "uuid": "unique-identifier",
  "vcon": "0.0.1",
  "created_at": "ISO-8601-timestamp",
  "redacted": {},
  "group": [],
  "parties": [
    {
      "tel": "+1234567890",
      "mailto": "user@example.com",
      "name": "John Doe",
      "role": "agent"
    }
  ],
  "dialog": [
    {
      "type": "recording",
      "start": "timestamp",
      "duration": 300,
      "parties": [0],
      "url": "https://example.com/recording.mp3"
    }
  ],
  "attachments": [
    {
      "type": "transcript",
      "body": "conversation text...",
      "encoding": "none"
    }
  ],
  "analysis": [
    {
      "type": "summary",
      "dialog": [0],
      "vendor": "openai",
      "body": "analysis results..."
    }
  ]
}
```

### Key Components

1. **Parties**: Participants in the conversation
   - Phone numbers, emails, names
   - Roles (agent, customer, etc.)
   - Indexed for efficient searching

2. **Dialog**: The actual conversation content
   - Recordings with URLs
   - Text messages
   - Timestamps and duration

3. **Attachments**: Additional data
   - Transcripts
   - Metadata
   - Tags
   - Custom data

4. **Analysis**: AI-generated insights
   - Summaries
   - Sentiment analysis
   - Custom analysis types
   - Vendor attribution

## Processing Pipeline

### Chain Architecture
- **Ingress Lists**: Entry points for vCons
- **Processing Links**: Sequential processing steps
- **Storage Operations**: Persistence to backends (with parallel write support)
- **Egress Lists**: Output queues for processed vCons

### Multi-Worker Architecture
The server supports parallel vCon processing through multiple worker processes:

- **Single Worker Mode** (default): Traditional single-threaded processing
- **Multi-Worker Mode**: Multiple processes consuming from Redis queues concurrently
- **Atomic Work Distribution**: Redis BLPOP ensures each vCon is processed by exactly one worker
- **Graceful Shutdown**: Workers complete current vCon before exiting on SIGTERM/SIGINT

### Parallel Storage Operations
When multiple storage backends are configured, writes can execute concurrently:

- **ThreadPoolExecutor**: Concurrent writes to all storage backends
- **Independent Failures**: One backend failure doesn't block others
- **Significant Speedup**: 3-4x faster with multiple I/O-bound backends
- **Configurable**: Can be disabled for sequential writes if needed

### Chain Configuration Example
```yaml
chains:
  main_chain:
    links:
      - deepgram_link      # Transcription
      - analyze            # AI analysis
      - tag               # Tagging
      - webhook           # External notification
    storages:
      - postgres          # Primary storage
      - s3               # Backup storage
      - milvus           # Vector storage (all written in parallel)
    ingress_lists:
      - main_ingress
    egress_lists:
      - processed_queue
    enabled: 1
```

### Processing Flow
1. vCon enters via ingress list
2. Worker atomically pops vCon from queue (BLPOP)
3. Each link processes sequentially within the worker
4. Storage operations execute (parallel or sequential based on config)
5. vCon moves to egress lists
6. Dead letter queue for failures

## API Functionality

### Core Endpoints

#### vCon Management
- `POST /api/vcon` - Create new vCon
- `GET /api/vcon/{uuid}` - Retrieve vCon
- `PUT /api/vcon/{uuid}` - Update vCon
- `DELETE /api/vcon/{uuid}` - Delete vCon
- `GET /api/vcons` - Batch retrieval

#### Search Operations
- `GET /api/vcons/search?tel={phone}` - Search by phone
- `GET /api/vcons/search?mailto={email}` - Search by email
- `GET /api/vcons/search?name={name}` - Search by name
- Multiple parameters for AND operations

#### Chain Management
- `POST /api/chain/{chain_name}/ingress` - Add to chain
- `POST /api/chain/{chain_name}/egress` - Process chain

#### Configuration
- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration

#### Queue Management
- `GET /api/dlq` - View dead letter queue
- `POST /api/dlq/reprocess` - Reprocess failed items

### Authentication
- Header-based: `x-conserver-api-token`
- File-based token management
- Environment variable support

## Redis Integration

### Caching Strategy
1. **Primary Storage**: vCons stored as JSON
2. **Sorted Sets**: Timestamp-based ordering
3. **Index Sets**: Search acceleration
4. **Expiration**: Configurable TTL

### Key Patterns
- `vcon:{uuid}` - vCon data
- `tel:{number}` - Phone index
- `mailto:{email}` - Email index
- `name:{name}` - Name index
- `vcons` - Sorted set by timestamp

### Performance Features
- Automatic cache population from storage
- Configurable expiration (VCON_REDIS_EXPIRY)
- Index expiration (VCON_INDEX_EXPIRY)
- Batch operations support

## Error Handling

### Dead Letter Queue (DLQ)
- Automatic failure capture
- Per-ingress-list DLQs
- Reprocessing capability
- Error tracking

### Retry Mechanisms
- Configurable retry counts
- Exponential backoff
- Link-specific retry logic
- Metrics tracking

## Metrics & Monitoring

### Built-in Metrics
- Processing time per link
- Success/failure rates
- Storage operation timing
- API request metrics

### Integration Points
- Datadog support
- Custom metrics via StatsD
- Structured logging
- Error tracking services