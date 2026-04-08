# VCONIC Conserver — Release Notes

**Document ID:** VCONIC-CSV-RN-001  
**Product:** VCONIC Conserver  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## Current Release

### Version: Initial Release (April 2026)

**Release Date:** April 2026  
**Build:** See `GET /version` endpoint for exact build information

#### New Features

- **Multi-worker processing engine** — Parallel vCon processing with configurable worker count
- **Configurable processing chains** — YAML-based chain definitions with links, tracers, and storages
- **Multiple transcription backends** — Support for Groq (Whisper), Deepgram, and Hugging Face models
- **LLM analysis** — OpenAI-powered summarization, categorization, and structured analysis
- **Multi-storage architecture** — Simultaneous writes to PostgreSQL, Elasticsearch, S3, MongoDB, and Milvus
- **External partner API** — Separate ingress endpoint with per-source authentication
- **Dead Letter Queue (DLQ)** — Automatic capture and reprocessing of failed vCons
- **OpenTelemetry observability** — Distributed tracing with Datadog, Jaeger, and OTLP support
- **Zero-knowledge auditing** — JLINC and SCITT integrity verification (optional)
- **Redis-based queuing** — High-performance ingress/egress queue system
- **Horizontal scaling** — Scale workers independently with Docker Compose
- **Health monitoring** — `/health`, `/version`, and `/stats/queue` endpoints

#### Known Issues

- Cascading deletes on large datasets may be slow when Supabase Real-Time is enabled. Disable Real-Time replication slots if experiencing deletion performance issues.
- `CONSERVER_START_METHOD=fork` may cause issues on some Linux distributions with certain Python versions. Use `spawn` as a workaround.

#### Compatibility

| Component | Supported Versions |
|-----------|--------------------|
| Docker Engine | 24.0+ |
| Docker Compose | V2 (2.20+) |
| PostgreSQL | 14, 15, 16 |
| Redis | 7.x (Redis Stack recommended) |
| Elasticsearch | 8.x |
| Python | 3.11+ (inside container) |
| Operating System | Ubuntu 22.04+, RHEL 8+, any Linux with Docker |

---

## Release Notes Template

*Future releases will follow this format:*

### Version: X.Y.Z (Month Year)

**Release Date:** Month DD, YYYY  
**Upgrade Path:** From version A.B.C → X.Y.Z

#### New Features
- Feature description

#### Enhancements
- Enhancement description

#### Bug Fixes
- Fix description

#### Breaking Changes
- Description of change and migration steps

#### Known Issues
- Description and workaround

#### Compatibility Changes
- Any changes to supported versions

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
