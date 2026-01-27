# Reference

Complete reference documentation for vCon Server components.

## Available Links

Processing links transform and analyze vCons.

| Link | Module | Description |
|------|--------|-------------|
| [deepgram_link](links/deepgram.md) | `links.deepgram_link` | Deepgram transcription |
| [groq_whisper](links/groq-whisper.md) | `links.groq_whisper` | Groq Whisper transcription |
| [hugging_face_whisper](links/huggingface-whisper.md) | `links.hugging_face_whisper` | HuggingFace Whisper |
| [openai_transcribe](links/openai-transcribe.md) | `links.openai_transcribe` | OpenAI Whisper |
| [analyze](links/analyze.md) | `links.analyze` | AI analysis |
| [analyze_and_label](links/analyze-and-label.md) | `links.analyze_and_label` | Analysis with labeling |
| [analyze_vcon](links/analyze-vcon.md) | `links.analyze_vcon` | vCon-specific analysis |
| [detect_engagement](links/detect-engagement.md) | `links.detect_engagement` | Engagement detection |
| [tag](links/tag.md) | `links.tag` | Add static tags |
| [check_and_tag](links/check-and-tag.md) | `links.check_and_tag` | Conditional tagging |
| [tag_router](links/tag-router.md) | `links.tag_router` | Route by tags |
| [sampler](links/sampler.md) | `links.sampler` | Random sampling |
| [webhook](links/webhook.md) | `links.webhook` | HTTP webhook delivery |
| [post_analysis_to_slack](links/slack.md) | `links.post_analysis_to_slack` | Slack notifications |
| [diet](links/diet.md) | `links.diet` | Reduce vCon size |
| [expire_vcon](links/expire-vcon.md) | `links.expire_vcon` | Set expiration |
| [jq_link](links/jq.md) | `links.jq_link` | jq transformations |

## Available Storage Adapters

Storage adapters persist vCons to various backends.

| Storage | Module | Description |
|---------|--------|-------------|
| [redis_storage](storage-adapters/redis.md) | `storage.redis_storage` | Redis storage |
| [postgres](storage-adapters/postgres.md) | `storage.postgres` | PostgreSQL |
| [mongo](storage-adapters/mongo.md) | `storage.mongo` | MongoDB |
| [elasticsearch](storage-adapters/elasticsearch.md) | `storage.elasticsearch` | Elasticsearch |
| [s3](storage-adapters/s3.md) | `storage.s3` | Amazon S3 / S3-compatible |
| [milvus](storage-adapters/milvus.md) | `storage.milvus` | Milvus vector database |
| [file](storage-adapters/file.md) | `storage.file` | Local filesystem |
| [sftp](storage-adapters/sftp.md) | `storage.sftp` | SFTP server |
| [dataverse](storage-adapters/dataverse.md) | `storage.dataverse` | Microsoft Dataverse |
| [chatgpt_files](storage-adapters/chatgpt-files.md) | `storage.chatgpt_files` | ChatGPT Files |

## Available Tracers

Tracers provide audit trails for processing.

| Tracer | Module | Description |
|--------|--------|-------------|
| jlinc | `tracers.jlinc` | JLINC audit trail |

## CLI Reference

See [CLI Reference](cli-reference.md) for command-line options.

## Quick Reference

### Common Link Options

```yaml
links:
  my_link:
    module: links.my_link
    options:
      timeout: 30          # Request timeout in seconds
      retry_count: 3       # Number of retries on failure
      retry_delay: 1       # Delay between retries
```

### Common Storage Options

```yaml
storages:
  my_storage:
    module: storage.my_storage
    options:
      timeout: 30          # Connection timeout
      batch_size: 100      # Items per batch operation
```

### Chain Configuration

```yaml
chains:
  chain_name:
    links:
      - link1
      - link2:
          option: value
    storages:
      - storage1
      - storage2
    tracers:
      - tracer1
    ingress_lists:
      - input_queue
    egress_lists:
      - output_queue
    enabled: 1
```

## Environment Variables Quick Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost` | Redis connection |
| `CONSERVER_API_TOKEN` | - | API authentication |
| `CONSERVER_CONFIG_FILE` | `./example_config.yml` | Config file path |
| `CONSERVER_WORKERS` | `1` | Worker processes |
| `CONSERVER_PARALLEL_STORAGE` | `true` | Parallel storage writes |
| `CONSERVER_START_METHOD` | Platform default | Multiprocessing method |
| `LOG_LEVEL` | `DEBUG` | Logging level |
| `DEEPGRAM_KEY` | - | Deepgram API key |
| `OPENAI_API_KEY` | - | OpenAI API key |
| `GROQ_API_KEY` | - | Groq API key |

See [Environment Variables](../configuration/environment-variables.md) for complete list.

## API Endpoints Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/version` | Version info |
| `GET` | `/vcon` | List vCons |
| `GET` | `/vcon/{uuid}` | Get vCon |
| `POST` | `/vcon` | Create vCon |
| `DELETE` | `/vcon/{uuid}` | Delete vCon |
| `GET` | `/vcons/search` | Search vCons |
| `POST` | `/vcon/ingress` | Queue for processing |
| `GET` | `/vcon/egress` | Get processed vCons |
| `POST` | `/vcon/external-ingress` | External submission |
| `GET` | `/dlq` | View DLQ |
| `POST` | `/dlq/reprocess` | Reprocess DLQ |
| `GET` | `/config` | Get configuration |

See [API Reference](../operations/api-reference.md) for complete documentation.
