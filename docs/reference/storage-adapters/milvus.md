# milvus

Stores vCons as vector embeddings in Milvus for semantic similarity search. Text is extracted from the vCon (transcripts, summaries, party info, dialog), converted to an embedding vector via the OpenAI Embeddings API, and inserted into a Milvus collection.

## Prerequisites

- A running Milvus instance (v2.x)
- An OpenAI API key (or a LiteLLM proxy) for generating embeddings
- The `pymilvus` and `openai` Python packages

```
pip install pymilvus openai
```

## Configuration

```yaml
storages:
  milvus:
    module: storage.milvus
    options:
      host: localhost
      port: "19530"
      collection_name: vcons
      api_key: ${OPENAI_API_KEY}
      embedding_model: text-embedding-3-small
      embedding_dim: 1536
      create_collection_if_missing: false
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `host` | string | `localhost` | Milvus server hostname |
| `port` | string | `19530` | Milvus server port |
| `collection_name` | string | `vcons` | Milvus collection to store vCons in |
| `embedding_model` | string | `text-embedding-3-small` | OpenAI embedding model used to generate vectors |
| `embedding_dim` | integer | `1536` | Vector dimension — must match the chosen model output |
| `api_key` | string | `None` | OpenAI API key |
| `organization` | string | `None` | OpenAI organization ID |
| `create_collection_if_missing` | boolean | `false` | Create the collection automatically if it does not exist |
| `skip_if_exists` | boolean | `true` | Skip storing if the vCon UUID already exists in the collection |
| `index_type` | string | `IVF_FLAT` | Vector index type: `IVF_FLAT`, `IVF_SQ8`, `IVF_PQ`, `HNSW`, `ANNOY`, `FLAT` |
| `metric_type` | string | `L2` | Distance metric: `L2` (Euclidean), `IP` (Inner Product), `COSINE` |
| `nlist` | integer | `128` | Number of clusters for IVF-family indexes |
| `m` | integer | `16` | HNSW: number of edges per node |
| `ef_construction` | integer | `200` | HNSW: dynamic candidate list size during index construction |

## Collection Schema

When `create_collection_if_missing: true` the adapter creates a collection with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `id` | INT64 (auto) | Primary key |
| `vcon_uuid` | VARCHAR(100) | vCon UUID |
| `party_id` | VARCHAR(100) | Extracted party identifier |
| `text` | VARCHAR(65535) | Extracted text used for embedding |
| `embedding` | FLOAT_VECTOR | Embedding vector |
| `created_at` | VARCHAR(30) | vCon creation timestamp |
| `updated_at` | VARCHAR(30) | vCon update timestamp |
| `subject` | VARCHAR(255) | vCon subject |
| `metadata_title` | VARCHAR(255) | Title from vCon metadata |
| `has_transcript` | BOOL | Whether a transcript is present |
| `has_summary` | BOOL | Whether a summary analysis is present |
| `party_count` | INT16 | Number of parties |
| `embedding_model` | VARCHAR(50) | Model used to generate the embedding |
| `embedding_version` | VARCHAR(20) | Embedding schema version |

## Example

### Basic Setup

```yaml
storages:
  milvus:
    module: storage.milvus
    options:
      host: milvus
      port: "19530"
      collection_name: vcons
      api_key: ${OPENAI_API_KEY}
      embedding_model: text-embedding-3-small
      embedding_dim: 1536
      create_collection_if_missing: true
      skip_if_exists: true

chains:
  main:
    links:
      - transcribe
      - summarize
    storages:
      - milvus
    ingress_lists:
      - default
    enabled: 1
```

### HNSW Index

```yaml
storages:
  milvus:
    module: storage.milvus
    options:
      host: milvus
      port: "19530"
      collection_name: vcons_hnsw
      api_key: ${OPENAI_API_KEY}
      embedding_model: text-embedding-3-small
      embedding_dim: 1536
      create_collection_if_missing: true
      index_type: HNSW
      metric_type: COSINE
      m: 16
      ef_construction: 200
```

## Notes

- vCons with no extractable text are silently skipped.
- The embedding dimension must match the model: `text-embedding-3-small` produces 1536-dimensional vectors, `text-embedding-3-large` produces 3072.
- The `get` function returns only the indexed fields (`uuid`, `text`, `embedding`, `party_id`) — the full vCon is not stored in Milvus and must be retrieved from another storage backend.
