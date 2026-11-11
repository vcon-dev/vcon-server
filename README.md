# vCon Server (Conserver)

vCon Server is a pipeline for [vCon](https://datatracker.ietf.org/doc/draft-ietf-vcon-vcon-core/) conversation records. It takes them in, runs them through configurable chains of links (transcription, AI analysis, tagging, routing, webhooks) and writes the results to one or more storage backends.

**Documentation:** start at [docs/index.md](docs/index.md). The `Docs` workflow publishes the same pages to https://vcon-dev.github.io/vcon-server/. For an introduction to vCons and the conserver, see [conserver.io](https://www.conserver.io/conserver).

## Start the server

You need Docker with the Compose plugin. The [quick start](docs/getting-started/quick-start.md) takes you from a fresh clone to a processed vCon. It sets three values in `.env`, writes a small `config.yml`, and starts the stack.

## Find the docs for your role

| Audience | Start here |
|----------|-----------|
| **New users** | [Getting Started](docs/getting-started/index.md) |
| **Operators** | [Installation](docs/installation/index.md), [Configuration](docs/configuration/index.md), [Operations](docs/operations/index.md) |
| **Developers** | [Contributing](docs/contributing.md), [Extending](docs/extending/index.md), [Reference](docs/reference/index.md) |

## Check the main features

- **Chain-based processing:** compose reusable links into pipelines driven by Redis queues
- **Processing links:** [transcription, AI analysis, tagging, routing, webhooks, SCITT and DataTrails records](docs/reference/links/index.md)
- **Storage backends:** [PostgreSQL, MongoDB, S3, Elasticsearch, Milvus, Redis, SFTP and more](docs/reference/storage-adapters/index.md)
- **Multi-worker scaling:** parallel workers, per-worker concurrency and parallel storage writes
- **External ingress:** scoped API keys let third-party systems submit vCons to specific queues
- **OpenTelemetry:** built-in tracing and metrics export

The server carries `lawful_basis` attachments through the pipeline. It does not create, validate or enforce consent. See [lawful basis](docs/concepts/lawful-basis.md).

## Run the tests

With the stack running:

```bash
docker compose run --rm conserver pytest
```

[Contributing](docs/contributing.md) covers local setup with uv.

## Read the license

MIT. See [LICENSE](LICENSE).
