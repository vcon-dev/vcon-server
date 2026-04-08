# VCONIC Platform Architecture Guide

**Document ID:** VCONIC-ARCH-001  
**Audience:** Value Added Reseller (VAR) / Systems Integrator  
**Last Updated:** April 2026

---

## 1. Platform Overview

The VCONIC platform is an enterprise conversation intelligence system that captures, processes, stores, and analyzes voice, video, and text conversations. It implements the IETF vCon standard (draft-ietf-vcon-vcon-core) for portable, interoperable conversation data.

The platform consists of three products that work together:

| Product | Function | Analogy |
|---------|----------|---------|
| **VCONIC Conserver** | Conversation processing engine | The factory — ingests raw conversations, runs them through transcription and AI analysis, stores the results |
| **VCONIC MCP Server** | AI integration layer | The API gateway — enables AI assistants to search, query, and manage conversation data |
| **VCONIC Portal** | Web application | The control panel — provides dashboards, search, AI chat, alerts, and administration |

---

## 2. What is a vCon?

A vCon (Virtual Conversation) is a standardized JSON container for conversation data defined by the IETF. Think of it as a universal envelope that holds everything about a conversation:

```
┌─────────────────────────────────────────┐
│  vCon Container                         │
│                                         │
│  ┌─────────┐  ┌──────────────────────┐  │
│  │ Parties  │  │ Dialog               │  │
│  │ - Caller │  │ - Audio recording    │  │
│  │ - Agent  │  │ - Transcript text    │  │
│  │ - Bot    │  │ - Chat messages      │  │
│  └─────────┘  └──────────────────────┘  │
│                                         │
│  ┌──────────────┐  ┌────────────────┐   │
│  │ Analysis      │  │ Attachments    │   │
│  │ - Summary     │  │ - Tags         │   │
│  │ - Sentiment   │  │ - Documents    │   │
│  │ - Categories  │  │ - Metadata     │   │
│  └──────────────┘  └────────────────┘   │
│                                         │
│  UUID: 550e8400-e29b-41d4-a716-...      │
│  Created: 2026-04-08T14:30:00Z          │
└─────────────────────────────────────────┘
```

Every vCon has a unique UUID. As it moves through the system, analysis and metadata are added to it while preserving the original conversation data.

---

## 3. System Architecture

### 3.1 High-Level Topology

```
                    ┌─────────────────────────┐
                    │   External Sources       │
                    │  (PBX, SIP Recorder,     │
                    │   Contact Center, etc.)  │
                    └───────────┬─────────────┘
                                │ Audio/vCon
                                ▼
┌───────────────────────────────────────────────────────────┐
│                    VCONIC Conserver                        │
│                                                           │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌───────┐  │
│  │  API    │──▶│  Redis   │──▶│ Workers  │──▶│Storage│  │
│  │ :8000   │   │  Queues  │   │ (Chains) │   │Backends│  │
│  └─────────┘   └──────────┘   └──────────┘   └───────┘  │
│                                    │                      │
│                    ┌───────────────┼───────────────┐      │
│                    ▼               ▼               ▼      │
│              ┌──────────┐  ┌────────────┐  ┌──────────┐  │
│              │Transcribe│  │  Analyze   │  │  Trace   │  │
│              │  (Groq/  │  │ (OpenAI/   │  │ (Audit/  │  │
│              │ Deepgram)│  │  Local LLM)│  │ Integrity│  │
│              └──────────┘  └────────────┘  └──────────┘  │
└──────────────────────┬────────────────────────────────────┘
                       │ Stores processed vCons
                       ▼
              ┌─────────────────┐
              │   PostgreSQL    │◄──────────────────────┐
              │   (vCon Store)  │                       │
              └────────┬────────┘                       │
                       │                                │
          ┌────────────┼─────────────┐                  │
          ▼                          ▼                  │
┌──────────────────┐    ┌─────────────────────┐         │
│  VCONIC MCP      │    │   VCONIC Portal     │         │
│  Server          │    │                     │         │
│  :3000           │    │  ┌───────────────┐  │         │
│                  │    │  │ Conversation  │  │         │
│  ┌────────────┐  │    │  │ Search        │──┼────┐    │
│  │ 31 AI Tools│  │    │  ├───────────────┤  │    │    │
│  │ for Claude │  │    │  │ AI Chat       │  │    │    │
│  │ and other  │  │    │  │ Assistant     │  │    │    │
│  │ assistants │  │    │  ├───────────────┤  │    │    │
│  └────────────┘  │    │  │ Signal Alerts │  │    │    │
│                  │    │  ├───────────────┤  │    │    │
│                  │    │  │ Admin Panel   │──┼────┼──┐ │
│                  │    │  └───────────────┘  │    │  │ │
└──────────────────┘    └────────────────────┘    │  │ │
                                                   │  │ │
                                              ┌────┘  │ │
                                              ▼       │ │
                                     ┌──────────────┐ │ │
                                     │Elasticsearch │ │ │
                                     │(Search Index)│ │ │
                                     └──────────────┘ │ │
                                                      │ │
                                              ┌───────┘ │
                                              ▼         │
                                     ┌──────────────┐   │
                                     │   Auth0      │   │
                                     │   (AuthN)    │   │
                                     └──────────────┘   │
                                                ┌───────┘
                                                ▼
                                     ┌──────────────┐
                                     │  Snowflake   │
                                     │ (Analytics)  │
                                     │  (Optional)  │
                                     └──────────────┘
```

### 3.2 Data Flow — The Journey of a vCon

This is the end-to-end path a conversation takes through the VCONIC platform:

```
Step 1: INGESTION
   A call is recorded by the customer's PBX or recording system.
   The audio file (WAV/MP3) is submitted to the Conserver API.
        │
        ▼
Step 2: QUEUING
   The Conserver API stores the vCon in Redis and places its UUID
   on an ingress queue. Multiple ingress queues can exist for
   different data sources (e.g., "support_calls", "sales_calls").
        │
        ▼
Step 3: PROCESSING (Chain Execution)
   A worker picks up the UUID from the queue and executes the
   configured processing chain:

   a. TRANSCRIPTION — Audio is sent to a speech-to-text service
      (Groq, Deepgram, or local model). The transcript is added
      to the vCon as a dialog entry.

   b. ANALYSIS — The transcript is sent to an LLM (OpenAI, local
      model) for summarization, sentiment analysis, categorization,
      or custom analysis. Results are added as analysis entries.

   c. TRACING (optional) — Audit records are created for compliance
      and integrity verification (JLINC, SCITT, DataTrails).
        │
        ▼
Step 4: STORAGE
   The fully processed vCon is written to one or more storage
   backends simultaneously:
   - PostgreSQL (primary relational store)
   - Elasticsearch (full-text search index)
   - S3 (object storage / archival)
   - Milvus (vector embeddings for semantic search)
        │
        ▼
Step 5: ACCESS — via MCP Server
   AI assistants connect to the MCP Server, which provides 31 tools
   for searching, retrieving, and analyzing vCons stored in
   PostgreSQL. Supports keyword, semantic, and hybrid search.
        │
        ▼
Step 6: ACCESS — via Portal
   Users log in to the Portal web application to:
   - Search conversations by keyword, date, participant
   - Chat with an AI assistant about their conversation data
   - Receive automated signal alerts based on patterns
   - Administer users, tenants, and system configuration
```

### 3.3 Deployment Topology — Single Host

For a typical single-host deployment (most VAR installations):

```
┌─────────────────── Host Server ──────────────────────┐
│                                                       │
│  Docker Engine                                        │
│  ┌─────────────────────────────────────────────────┐  │
│  │                                                 │  │
│  │  ┌───────────┐  ┌───────────┐  ┌────────────┐  │  │
│  │  │ Conserver │  │ Conserver │  │ Conserver  │  │  │
│  │  │ API :8000 │  │ Worker 1  │  │ Worker N   │  │  │
│  │  └───────────┘  └───────────┘  └────────────┘  │  │
│  │                                                 │  │
│  │  ┌───────────┐  ┌───────────┐  ┌────────────┐  │  │
│  │  │ Redis     │  │PostgreSQL │  │Elasticsrch │  │  │
│  │  │ :6379     │  │ :5432     │  │ :9200      │  │  │
│  │  └───────────┘  └───────────┘  └────────────┘  │  │
│  │                                                 │  │
│  │  ┌───────────┐  ┌───────────┐                   │  │
│  │  │ MCP Server│  │  Portal   │                   │  │
│  │  │ :3000     │  │  :3004    │                   │  │
│  │  └───────────┘  └───────────┘                   │  │
│  │                                                 │  │
│  │  ┌───────────┐                                  │  │
│  │  │  nginx    │ ◄── External HTTPS traffic       │  │
│  │  │  :443     │                                  │  │
│  │  └───────────┘                                  │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

## 4. Network Requirements

### 4.1 Internal Ports (Container-to-Container)

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Conserver API | 8000 | HTTP | vCon submission and management |
| Redis | 6379 | TCP | Queue and cache |
| Redis Insight | 8001 | HTTP | Redis management UI |
| PostgreSQL | 5432 | TCP | Database |
| Elasticsearch | 9200 | HTTP | Search engine |
| MCP Server | 3000 | HTTP/SSE | AI tool integration |
| Portal | 3004 | HTTP | Web application |

### 4.2 External Ports (Firewall Rules)

Only these ports need to be exposed externally:

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 443 | HTTPS | Inbound | Portal web UI, Conserver API (via nginx) |
| 80 | HTTP | Inbound | Redirect to HTTPS (optional) |

### 4.3 Outbound Connections Required

| Destination | Port | Purpose |
|-------------|------|---------|
| OpenAI API (api.openai.com) | 443 | LLM analysis, embeddings |
| Groq API (api.groq.com) | 443 | Speech-to-text transcription |
| Deepgram API (api.deepgram.com) | 443 | Speech-to-text (alternative) |
| Auth0 (*.auth0.com) | 443 | User authentication |
| Supabase (*.supabase.co) | 443 | MCP Server database (if using hosted Supabase) |
| SendGrid/Mailgun | 443 | Email notifications (Portal) |
| Docker Hub / ECR | 443 | Docker image pulls |

> **NOTE:** If the deployment is air-gapped or behind a strict firewall, local/on-premises alternatives exist for transcription and LLM services. Contact VCONIC engineering for guidance.

---

## 5. Product Interdependencies

### 5.1 Dependency Matrix

| Product | Depends On | Required? |
|---------|-----------|-----------|
| **Conserver** | Redis | Yes — queue and cache |
| **Conserver** | PostgreSQL | Yes — primary vCon storage |
| **Conserver** | Elasticsearch | Optional — search indexing |
| **Conserver** | OpenAI / Groq / Deepgram | Yes — transcription and analysis |
| **MCP Server** | PostgreSQL (Supabase) | Yes — vCon data access |
| **MCP Server** | Redis | Optional — caching layer |
| **Portal** | PostgreSQL | Yes — application database |
| **Portal** | PostgreSQL (Conserver DB) | Yes — read-only access to vCon data |
| **Portal** | Elasticsearch | Yes — conversation search |
| **Portal** | Auth0 | Yes — user authentication |
| **Portal** | OpenAI / Azure OpenAI / LiteLLM | Yes — AI chat features |

### 5.2 Installation Order

Install the products in this order:

```
1. PostgreSQL (shared database server)
      │
      ▼
2. Redis
      │
      ▼
3. Elasticsearch
      │
      ├──────────────────────┐
      ▼                      ▼
4. VCONIC Conserver     5. VCONIC MCP Server
      │                      │
      └──────────┬───────────┘
                 ▼
         6. VCONIC Portal
```

---

## 6. Security Architecture

### 6.1 Authentication & Authorization

| Layer | Mechanism | Notes |
|-------|-----------|-------|
| Conserver API | API token (header: `x-conserver-api-token`) | Shared secret per client |
| Conserver External Ingress | Per-ingress API keys (config.yml) | Scoped per data source |
| MCP Server | API key (header: `Authorization: Bearer <key>`) | Configurable keys |
| MCP Server | Tool profiles | Restrict which tools are available |
| Portal | Auth0 (OAuth 2.0 / OIDC) | SSO-capable |
| Portal | Role-based access (7 roles) | Hierarchical: Super Admin → Tenant Staff |
| Database | Connection string credentials | Standard PostgreSQL auth |

### 6.2 Data Protection

| Concern | Implementation |
|---------|---------------|
| Data in transit | TLS 1.2+ via nginx reverse proxy |
| Data at rest | PostgreSQL encryption, volume encryption at OS level |
| API authentication | Token-based, per-service |
| Multi-tenancy | Row-level security (RLS) in MCP Server; organization/tenant hierarchy in Portal |
| Audit trail | JLINC zero-knowledge auditing, SCITT signed statements (optional) |
| PII handling | Demo mode with PII redaction available in Portal |

### 6.3 Network Segmentation Recommendations

```
┌─── Public Zone (DMZ) ───┐
│  nginx :443              │
└──────────┬───────────────┘
           │
┌──────────▼───────────────┐
│  Application Zone        │
│  Conserver API :8000     │
│  MCP Server :3000        │
│  Portal :3004            │
└──────────┬───────────────┘
           │
┌──────────▼───────────────┐
│  Data Zone               │
│  PostgreSQL :5432        │
│  Redis :6379             │
│  Elasticsearch :9200     │
└──────────────────────────┘
```

> **CAUTION:** Never expose Redis, PostgreSQL, or Elasticsearch ports directly to the public internet. All external access should go through nginx with TLS termination.

---

## 7. Hardware Requirements

### 7.1 Minimum (Small Deployment — up to 1,000 conversations/day)

| Resource | Specification |
|----------|--------------|
| CPU | 4 cores |
| RAM | 16 GB |
| Storage | 100 GB SSD |
| Network | 100 Mbps |
| OS | Linux (Ubuntu 22.04+ or RHEL 8+) |
| Docker | Docker Engine 24+ with Compose V2 |

### 7.2 Recommended (Medium Deployment — up to 10,000 conversations/day)

| Resource | Specification |
|----------|--------------|
| CPU | 8 cores |
| RAM | 32 GB |
| Storage | 500 GB SSD (NVMe preferred) |
| Network | 1 Gbps |
| OS | Linux (Ubuntu 22.04+ or RHEL 8+) |
| Docker | Docker Engine 24+ with Compose V2 |

### 7.3 Storage Sizing Estimates

| Data Type | Approximate Size per Conversation |
|-----------|----------------------------------|
| Raw audio (WAV, 5 min call) | 5–50 MB |
| vCon JSON (with transcript + analysis) | 10–100 KB |
| Elasticsearch index entry | 5–50 KB |
| Vector embedding | 1–5 KB |

> **NOTE:** Audio files are typically stored externally (S3, NAS) with URLs referenced in the vCon. Only metadata, transcripts, and analysis are stored in PostgreSQL.

---

## 8. Glossary

| Term | Definition |
|------|-----------|
| **vCon** | Virtual Conversation — an IETF standard JSON format for representing conversation data |
| **Conserver** | The VCONIC processing engine that ingests, transcribes, analyzes, and stores vCons |
| **MCP** | Model Context Protocol — an open standard for connecting AI assistants to external data sources and tools |
| **Chain** | A configured sequence of processing steps (links → tracers → storages) in the Conserver |
| **Link** | A single processing step in a chain (e.g., transcribe, analyze, summarize) |
| **Tracer** | An audit/integrity module that runs after links in a chain |
| **Ingress Queue** | A Redis queue where new vCon UUIDs are placed for processing |
| **Egress Queue** | A Redis queue where processed vCon UUIDs are placed after chain completion |
| **DLQ** | Dead Letter Queue — where failed vCons are placed for investigation |
| **VAR** | Value Added Reseller — a third-party company that installs, configures, and supports vendor equipment for end customers |
| **RLS** | Row-Level Security — database-level access control that restricts which rows a user can see |
| **Signal** | An automated alert in the Portal triggered by conversation patterns |

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | April 2026 | VCONIC Engineering | Initial release |
