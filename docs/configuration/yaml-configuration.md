# YAML Configuration

Complete reference for the vCon Server YAML configuration file.

## File Structure

```yaml
# API key authentication for ingress lists
ingress_auth:
  ...

# Dynamic module imports
imports:
  ...

# Processing link definitions
links:
  ...

# Storage backend definitions
storages:
  ...

# Tracer definitions
tracers:
  ...

# Processing chain definitions
chains:
  ...

# Follower configurations (distributed mode)
followers:
  ...
```

## Ingress Authentication

Map API keys to specific ingress lists for external integrations.

### Single Key

```yaml
ingress_auth:
  customer_data: "customer-api-key-12345"
```

### Multiple Keys

```yaml
ingress_auth:
  support_calls:
    - "support-api-key-67890"
    - "support-client-2-key"
    - "support-vendor-key-xyz"
```

### Usage

External systems use the `/vcon/external-ingress` endpoint with their assigned key:

```bash
curl -X POST "http://api/vcon/external-ingress?ingress_list=customer_data" \
  -H "x-conserver-api-token: customer-api-key-12345" \
  -H "Content-Type: application/json" \
  -d '{"vcon": "0.0.1", ...}'
```

## Imports

Define modules to import dynamically from PyPI or GitHub.

### From PyPI

```yaml
imports:
  custom_utility:
    module: custom_utils
    pip_name: custom-utils-package
```

### From GitHub

```yaml
imports:
  github_helper:
    module: github_helper
    pip_name: git+https://github.com/username/helper-repo.git
```

### Direct Module

```yaml
imports:
  # Module name matches pip package
  requests_import:
    module: requests
```

## Links

Define processing links that transform vCons.

### Basic Link

```yaml
links:
  transcribe:
    module: links.transcribe
```

### Link with Options

```yaml
links:
  deepgram_link:
    module: links.deepgram_link
    options:
      model: nova-2
      language: en
      punctuate: true
      diarize: true
```

### External Link

```yaml
links:
  custom_analyzer:
    module: custom_analyzer_module
    pip_name: custom-analyzer-package
    options:
      api_key: your-key
      endpoint: https://api.example.com
```

### Available Links

| Link | Module | Description |
|------|--------|-------------|
| `deepgram_link` | `links.deepgram_link` | Deepgram transcription |
| `groq_whisper` | `links.groq_whisper` | Groq Whisper transcription |
| `hugging_face_whisper` | `links.hugging_face_whisper` | HuggingFace Whisper |
| `openai_transcribe` | `links.openai_transcribe` | OpenAI Whisper |
| `analyze` | `links.analyze` | AI analysis |
| `analyze_and_label` | `links.analyze_and_label` | Analysis with labeling |
| `analyze_vcon` | `links.analyze_vcon` | vCon-specific analysis |
| `detect_engagement` | `links.detect_engagement` | Engagement detection |
| `tag` | `links.tag` | Add static tags |
| `check_and_tag` | `links.check_and_tag` | Conditional tagging |
| `tag_router` | `links.tag_router` | Route by tags |
| `sampler` | `links.sampler` | Random sampling |
| `webhook` | `links.webhook` | HTTP webhook delivery |
| `post_analysis_to_slack` | `links.post_analysis_to_slack` | Slack notifications |
| `diet` | `links.diet` | Reduce vCon size |
| `expire_vcon` | `links.expire_vcon` | Set expiration |
| `jq_link` | `links.jq_link` | jq transformations |

## Storages

Define storage backends for persisting vCons.

### Redis Storage

```yaml
storages:
  redis_storage:
    module: storage.redis_storage
```

### PostgreSQL

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      user: vcon
      password: vcon_password
      host: postgres
      port: "5432"
      database: vcon_server
```

### MongoDB

```yaml
storages:
  mongo:
    module: storage.mongo
    options:
      url: mongodb://root:example@mongo:27017/
      database: conserver
      collection: vcons
```

### Amazon S3

```yaml
storages:
  s3:
    module: storage.s3
    options:
      aws_access_key_id: your-access-key
      aws_secret_access_key: your-secret-key
      aws_bucket: vcon-archive
      aws_region: us-east-1
      s3_path: vcons/  # Optional prefix
```

### S3-Compatible Storage

```yaml
storages:
  minio:
    module: storage.s3
    options:
      aws_access_key_id: minioadmin
      aws_secret_access_key: minioadmin
      aws_bucket: vcons
      endpoint_url: http://minio:9000
```

### Elasticsearch

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      hosts:
        - http://elasticsearch:9200
      index: vcons
```

### Milvus (Vector Database)

```yaml
storages:
  milvus:
    module: storage.milvus
    options:
      host: milvus
      port: "19530"
      collection_name: vcons
      embedding_model: text-embedding-3-small
      embedding_dim: 1536
      api_key: your-openai-key  # For embeddings
      create_collection_if_missing: true
      index_type: IVF_FLAT
      metric_type: L2
```

### File Storage

```yaml
storages:
  file:
    module: storage.file
    options:
      path: /data/vcons
      organize_by_date: true
      compression: false
```

### SFTP

```yaml
storages:
  sftp:
    module: storage.sftp
    options:
      host: sftp.example.com
      username: vcon
      private_key_path: /etc/vcon/sftp_key
      remote_path: /uploads/vcons
```

## Tracers

Define tracers for audit trails and monitoring.

### JLINC Tracer

```yaml
tracers:
  jlinc:
    module: tracers.jlinc
    options:
      data_store_api_url: http://jlinc-server:9090
      data_store_api_key: your-key
      archive_api_url: http://jlinc-server:9090
      archive_api_key: your-key
      system_prefix: VCONProd
      agreement_id: 00000000-0000-0000-0000-000000000000
      hash_event_data: true
      dlq_vcon_on_error: true
```

## Chains

Define processing chains that combine links, storage, and routing.

### Basic Chain

```yaml
chains:
  simple_chain:
    links:
      - transcribe
    storages:
      - redis_storage
    ingress_lists:
      - default
    enabled: 1
```

### Full Chain

```yaml
chains:
  production_chain:
    links:
      - deepgram_link
      - analyze
      - tag
      - tag_router
    storages:
      - postgres
      - s3
      - elasticsearch
    tracers:
      - jlinc
    ingress_lists:
      - production_ingress
    egress_lists:
      - processed_vcons
      - analytics_queue
    enabled: 1
```

### Chain with Link Options

```yaml
chains:
  custom_chain:
    links:
      - deepgram_link:
          model: nova-2
          diarize: true
      - analyze:
          model: gpt-4
          prompt: "Summarize this call"
      - sampler:
          rate: 0.1  # Sample 10%
    storages:
      - postgres
    ingress_lists:
      - sample_input
    enabled: 1
```

### Disabled Chain

```yaml
chains:
  disabled_chain:
    links:
      - transcribe
    storages:
      - redis_storage
    ingress_lists:
      - unused
    enabled: 0  # Chain is disabled
```

## Followers

Configure follower processes for distributed deployments.

```yaml
followers:
  upstream_server:
    url: http://upstream-vcon-server:8000
    egress_list: processed_vcons
    follower_ingress_list: incoming_from_upstream
    auth_token: upstream-api-token
    pulling_interval: 60  # seconds
    fetch_vcon_limit: 10
```

## Complete Example

```yaml
---
# =============================================================================
# vCon Server Configuration
# =============================================================================

# Ingress-specific authentication
ingress_auth:
  partner_a: "partner-a-secure-key"
  partner_b:
    - "partner-b-key-1"
    - "partner-b-key-2"

# Processing links
links:
  deepgram_link:
    module: links.deepgram_link
    options:
      model: nova-2
      language: en
      punctuate: true
      diarize: true

  analyze:
    module: links.analyze
    options:
      model: gpt-4
      temperature: 0.3

  tag:
    module: links.tag
    options:
      tags:
        - processed
        - v1

  tag_router:
    module: links.tag_router
    options:
      rules:
        - tag: urgent
          queue: urgent_queue
        - tag: routine
          queue: routine_queue

# Storage backends
storages:
  postgres:
    module: storage.postgres
    options:
      user: vcon
      password: vcon_password
      host: postgres
      port: "5432"
      database: vcon_server

  s3:
    module: storage.s3
    options:
      aws_access_key_id: ${AWS_ACCESS_KEY_ID}
      aws_secret_access_key: ${AWS_SECRET_ACCESS_KEY}
      aws_bucket: vcon-archive
      aws_region: us-east-1

  elasticsearch:
    module: storage.elasticsearch
    options:
      hosts:
        - http://elasticsearch:9200
      index: vcons

# Tracers
tracers:
  jlinc:
    module: tracers.jlinc
    options:
      data_store_api_url: http://jlinc:9090
      data_store_api_key: jlinc-key
      system_prefix: PROD

# Processing chains
chains:
  main_pipeline:
    links:
      - deepgram_link
      - analyze
      - tag
      - tag_router
    storages:
      - postgres
      - s3
      - elasticsearch
    tracers:
      - jlinc
    ingress_lists:
      - main_ingress
      - partner_a
      - partner_b
    egress_lists:
      - processed
    enabled: 1

  archive_only:
    links: []
    storages:
      - s3
    ingress_lists:
      - archive_ingress
    enabled: 1
```
