# Link Processors

## Overview

Link processors are modular components that perform specific operations on vCons as they flow through processing chains. Each link implements a focused functionality, allowing flexible pipeline construction.

## Available Link Processors

### 1. Transcription Links

#### Deepgram Link
**Purpose**: High-quality speech-to-text transcription

**Features**:
- Industry-leading accuracy with Nova-2 model
- Automatic language detection
- Real-time and batch processing
- Speaker diarization
- Confidence scoring
- Smart formatting and punctuation

**Configuration**:
```yaml
deepgram_link:
  module: links.deepgram_link
  options:
    DEEPGRAM_KEY: your-api-key
    minimum_duration: 30
    api:
      model: "nova-2"
      smart_format: true
      detect_language: true
```

#### Groq Whisper Link
**Purpose**: Fast transcription using Groq's Whisper implementation

**Features**:
- OpenAI Whisper compatibility
- High-speed inference
- Multiple language support
- Timestamp generation

#### Hugging Face Whisper Link
**Purpose**: Open-source transcription option

**Features**:
- No API key required for public models
- Local or cloud inference
- Customizable models
- Cost-effective for high volumes

### 2. Analysis Links

#### Analyze Link
**Purpose**: AI-powered conversation analysis

**Features**:
- Customizable prompts
- Multiple analysis types (summary, sentiment, intent)
- Support for GPT-4, GPT-3.5, and other models
- Configurable sampling rates
- Source selection (transcript, full vCon)

**Configuration**:
```yaml
analyze:
  module: links.analyze
  options:
    OPENAI_API_KEY: your-key
    prompt: "Summarize this conversation"
    analysis_type: "summary"
    model: "gpt-4"
```

#### Analyze vCon Link
**Purpose**: Analyze entire vCon structure

**Features**:
- Full vCon context analysis
- JSON output format
- System prompt support
- Complex reasoning tasks

#### Analyze and Label Link
**Purpose**: Combined analysis and labeling

**Features**:
- Performs analysis and adds labels
- Automated categorization
- Rule-based tagging
- ML-based classification

### 3. Integration Links

#### Webhook Link
**Purpose**: Send vCons to external systems

**Features**:
- Multiple webhook URLs
- Authentication support
- Retry logic
- Response logging

**Configuration**:
```yaml
webhook:
  module: links.webhook
  options:
    webhook-urls:
      - https://api.example.com/vcon
    auth_header: "Bearer token"
```

#### Post Analysis to Slack Link
**Purpose**: Slack notifications for analysis results

**Features**:
- Team-specific routing
- Conditional posting
- Rich message formatting
- Thread support

#### JLINC Link
**Purpose**: Data sovereignty and consent management

**Features**:
- JLINC protocol integration
- Consent tracking
- Data rights management

### 4. Data Processing Links

#### Diet Link
**Purpose**: Reduce vCon size and content

**Features**:
- Selective element removal
- Media redirection
- Privacy protection
- Storage optimization

**Configuration**:
```yaml
diet:
  module: links.diet
  options:
    remove_media: true
    remove_analysis: false
    redirect_urls: true
```

#### Tag Link
**Purpose**: Add tags to vCons

**Features**:
- Static tag addition
- Dynamic tag generation
- Multiple tag support

#### Tag Router Link
**Purpose**: Route vCons based on tags

**Features**:
- Tag-based routing rules
- Multiple destination queues
- Conditional routing
- Default routes

### 5. Filtering Links

#### JQ Link
**Purpose**: JSON query filtering

**Features**:
- Complex JSON queries
- Content-based routing
- Conditional processing
- jq expression support

**Configuration**:
```yaml
jq_link:
  module: links.jq_link
  options:
    expression: ".parties[].tel"
    forward_on_match: true
```

#### Sampler Link
**Purpose**: Statistical sampling of vCons

**Features**:
- Percentage-based sampling
- Rate limiting
- Modulo sampling
- Time-based sampling

### 6. Security & Compliance Links

#### SCITT Link
**Purpose**: Supply chain integrity and transparency

**Features**:
- Signed statement creation
- Transparency service registration
- Cryptographic verification
- Audit trail creation

#### DataTrails Link
**Purpose**: Immutable audit trails

**Features**:
- Blockchain-backed trails
- Event tracking
- Asset management
- Compliance reporting

### 7. Lifecycle Links

#### Expire vCon Link
**Purpose**: Set expiration for vCons

**Features**:
- TTL management
- Automatic cleanup
- Retention policy enforcement

## Link Chaining Patterns

### Common Patterns

1. **Standard Processing**
   ```yaml
   links:
     - deepgram_link      # Transcribe
     - analyze            # Analyze
     - tag               # Tag
     - webhook           # Notify
   ```

2. **Quality Assurance**
   ```yaml
   links:
     - deepgram_link
     - analyze_and_label
     - tag_router        # Route by quality
     - post_to_slack     # Alert on issues
   ```

3. **Compliance Pipeline**
   ```yaml
   links:
     - diet              # Remove sensitive data
     - scitt             # Create audit trail
     - expire_vcon       # Set retention
   ```

4. **Sampling Pipeline**
   ```yaml
   links:
     - sampler           # Sample 10%
     - deepgram_link
     - analyze
   ```

## Custom Link Development

### Link Interface
```python
def process(vcon_uuid):
    # Retrieve vCon
    vcon = get_vcon(vcon_uuid)
    
    # Process vCon
    result = perform_operation(vcon)
    
    # Store updated vCon
    store_vcon(vcon)
    
    # Return UUID for chaining
    return vcon_uuid
```

### Best Practices
1. **Single Responsibility**: Each link does one thing well
2. **Idempotent**: Safe to retry
3. **Error Handling**: Graceful failure
4. **Metrics**: Track performance
5. **Configuration**: Flexible options

## Performance Considerations

1. **Order Matters**: Place filters early in chain
2. **Parallel Processing**: Some links can run concurrently
3. **Caching**: Links can cache results in vCon
4. **Batch Operations**: Group similar operations
5. **Async Support**: Long-running operations