# Milvus storage adapter

Stores an embedding of a vCon's text in a Milvus collection for similarity search. It does not store the vCon.

Module: `storage.milvus`. Needs `pymilvus` and `openai`, from the `storage-milvus` dependency group. Only `docker/Dockerfile` installs that group. See [the image table](index.md#install-the-adapter-packages).

## Configure the adapter

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
      api_key: sk-example
      create_collection_if_missing: true
```

## Set the options

The adapter merges your options over the defaults.

| Option | Type | Default | Description |
|---|---|---|---|
| `host` | string | `localhost` | Milvus host |
| `port` | string | `19530` | Milvus port |
| `collection_name` | string | `vcons` | Collection to use |
| `embedding_model` | string | `text-embedding-3-small` | Model for the embedding call |
| `embedding_dim` | integer | `1536` | Expected vector size. `save` raises `ValueError` on a mismatch |
| `api_key` | string | none | OpenAI API key |
| `organization` | string | none | OpenAI organization |
| `create_collection_if_missing` | boolean | `false` | Create the collection and its index on first use. When false, a missing collection raises `ValueError` |
| `skip_if_exists` | boolean | `true` | Skip a vCon already in the collection |
| `index_type` | string | `IVF_FLAT` | `IVF_FLAT`, `IVF_SQ8`, `IVF_PQ`, `HNSW`, `ANNOY` or `FLAT`. Anything else logs a warning and uses `IVF_FLAT` |
| `metric_type` | string | `L2` | Distance metric, passed to Milvus |
| `nlist` | integer | `128` | Cluster count for IVF indexes |
| `m` | integer | `16` | Edges per node for `HNSW` |
| `ef_construction` | integer | `200` | `efConstruction` for `HNSW` |

The adapter also reads these keys when it creates the collection. They are not in `default_options`:

| Option | Type | Fallback | Description |
|---|---|---|---|
| `pq_m` | integer | `8` | `m` for `IVF_PQ` |
| `pq_nbits` | integer | `8` | `nbits` for `IVF_PQ` |
| `n_trees` | integer | `50` | Tree count for `ANNOY` |

Index options apply only when the adapter creates the collection. The client comes from `get_openai_client`, so the LiteLLM and Azure keys in `common/lib/openai_client.py` work here too.

## Save a vCon

1. Connect to Milvus and check the collection.
2. Read the vCon through `VconRedis`. A missing vCon raises `ValueError`.
3. With `skip_if_exists` on, return if a row has this `vcon_uuid`.
4. Build the text from `transcript`, analysis of type `transcript` and `summary`, party details, `metadata` and text dialogs. If the text is empty, log a warning and return.
5. Pick a party identifier and get the embedding.
6. Insert one row and flush.

The collection has these fields:

| Field | Type | Source |
|---|---|---|
| `id` | INT64, primary key, auto | Milvus |
| `vcon_uuid` | VARCHAR(100) | vCon UUID |
| `party_id` | VARCHAR(100) | First usable party identifier |
| `text` | VARCHAR(65535) | Extracted text. The adapter does not truncate it |
| `embedding` | FLOAT_VECTOR | Embedding |
| `created_at`, `updated_at` | VARCHAR(30) | `metadata.created_at` and `metadata.updated_at`, not the top-level `created_at` |
| `subject` | VARCHAR(255) | vCon subject |
| `metadata_title` | VARCHAR(255) | `metadata.title` |
| `has_transcript`, `has_summary` | BOOL | Content flags |
| `party_count` | INT16 | Party count |
| `embedding_model` | VARCHAR(50) | `embedding_model` option |
| `embedding_version` | VARCHAR(20) | Always `1.0` |

The insert is not an upsert. With `skip_if_exists` off, each `save` adds a row. With it on, a changed vCon keeps its first embedding.

## Read a vCon

`get` returns a partial record, not a vCon:

```json
{"uuid": "...", "text": "...", "embedding": [0.1], "party_id": "..."}
```

It returns `None` when the row or collection is missing, or on an error.

!!! warning "Keep milvus behind adapters that hold the full vCon"
    The storage fallback treats any truthy result as the vCon. If `milvus` answers first, this partial record is cached in Redis as `vcon:<uuid>`, and the API read path then fails on the missing `created_at`. See [Read a vCon back from storage](index.md#read-a-vcon-back-from-storage).

## Delete a vCon

The adapter has no `delete`. Rows stay in Milvus after `DELETE /vcon/{uuid}`.

## Handle a failed write

Connection, collection, dimension and insert failures raise, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). Failures inside the main block also increment `conserver.storage.milvus.storage_failures`.

The embedding client retries transient errors with `max_retries=3`. If the embedding call still fails, `get_embedding` logs it, increments `conserver.storage.milvus.embedding_failures` and returns a zero vector of the default 1536 dimensions. With `embedding_dim` at 1536 the row is stored with that zero vector and `save` succeeds. With another size the dimension check raises.

A replay is safe with `skip_if_exists` on. See the [metrics reference](../metrics.md) for the adapter's other metrics.
