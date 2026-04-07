# vCon Server (Conserver)

vCon Server is a pipeline-based conversation processing and storage system. It ingests [vCon](https://datatracker.ietf.org/doc/draft-ietf-vcon-vcon-container/) (Voice Conversation) records, routes them through configurable processing chains — transcription, AI analysis, tagging, webhooks — and writes results to one or more storage backends.

**Full documentation:** https://vcon-dev.github.io/vcon-server/

## Quick Start

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
cp example_docker-compose.yml docker-compose.yml
cp .env.example .env          # edit CONSERVER_API_TOKEN at minimum
docker network create conserver
docker compose up -d --build
curl http://localhost:8000/api/health
```

## Documentation by Audience

| Audience | Start here |
|----------|-----------|
| **New users** | [Getting Started](https://vcon-dev.github.io/vcon-server/getting-started/) |
| **Operators / DevOps** | [Installation](https://vcon-dev.github.io/vcon-server/installation/) · [Configuration](https://vcon-dev.github.io/vcon-server/configuration/) · [Operations](https://vcon-dev.github.io/vcon-server/operations/) |
| **Developers** | [Contributing](https://vcon-dev.github.io/vcon-server/contributing/) · [Extending](https://vcon-dev.github.io/vcon-server/extending/) · [Reference](https://vcon-dev.github.io/vcon-server/reference/) |

## Key Features

- **Chain-based processing** — compose reusable links into pipelines driven by Redis queues
- **20+ processing links** — transcription (Deepgram, Whisper), AI analysis (OpenAI, Groq), tagging, routing, webhooks, compliance (SCITT, DataTrails)
- **10+ storage backends** — PostgreSQL, MongoDB, S3, Elasticsearch, Milvus, Redis, SFTP, and more
- **Multi-worker scaling** — parallel workers with configurable process count and parallel storage writes
- **External ingress** — scoped API keys let third-party systems submit vCons to specific queues
- **OpenTelemetry** — built-in tracing and metrics export

## Running Tests

```bash
docker compose run --rm api poetry run pytest server/links/analyze/tests/ -v
```

## License

See [LICENSE](LICENSE).
