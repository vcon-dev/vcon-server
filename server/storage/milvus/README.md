# Milvus Storage Module for vCon Server

This storage module enables storing vCons in a Milvus vector database for semantic search capabilities.

## Description

The Milvus storage module:
- Extracts text content from vCons (transcripts, summaries, metadata, etc.)
- Generates embeddings using OpenAI's embedding models
- Stores the embeddings in Milvus along with related metadata
- Enables semantic search across vCon content

## Requirements

- Milvus 2.0+ running and accessible
- OpenAI API key for generating embeddings
- Additional Python packages:
  ```
  pymilvus>=2.3.0
  openai>=1.0.0
  ```

## Configuration

Add the following to your config.yml file:

```yaml
storages:
  milvus:
    module: storage.milvus
    options:
      # Connection settings
      host: "localhost"                  # Milvus server host
      port: "19530"                      # Milvus server port
      collection_name: "vcons"           # Name of the collection in Milvus
      
      # Embedding settings
      embedding_model: "text-embedding-3-small"  # OpenAI embedding model
      embedding_dim: 1536                # Dimensions for the chosen model
      api_key: "your-openai-api-key"     # Your OpenAI API key
      organization: "your-org-id"        # Optional: Your OpenAI organization ID
      
      # Operation settings
      create_collection_if_missing: true # Whether to create collection if it doesn't exist
      skip_if_exists: true               # Skip storing vCons that already exist
      
      # Vector index settings (optional, shown are defaults)
      index_type: "IVF_FLAT"             # Vector index type
      metric_type: "L2"                  # Distance metric type
      nlist: 128                         # Number of clusters for IVF indexes
```

### Vector Index Types

The module supports different vector index types with appropriate parameters:

#### IVF_FLAT (Default)
Good balance of search accuracy and speed. Uses more storage but gives exact results within each cluster.

```yaml
index_type: "IVF_FLAT"  
metric_type: "L2"       # Or "IP" for inner product, or "COSINE"
nlist: 128              # Number of clusters, higher values = faster search but less accurate
```

#### IVF_SQ8
Similar to IVF_FLAT but with scalar quantization (8-bit) to reduce memory usage. Good for large datasets.

```yaml
index_type: "IVF_SQ8"
metric_type: "L2"
nlist: 128
```

#### IVF_PQ
Product Quantization for maximum memory optimization. Sacrifices some accuracy for much smaller index size.

```yaml
index_type: "IVF_PQ"
metric_type: "L2"
nlist: 128
pq_m: 8                 # Number of sub-quantizers
pq_nbits: 8             # Bit depth per quantizer
```

#### HNSW
Hierarchical Navigable Small World graph index. Very fast for searching, especially with smaller datasets.

```yaml
index_type: "HNSW"
metric_type: "L2"
m: 16                   # Number of edges per node
ef_construction: 200    # Size of the dynamic candidate list during construction
```

#### FLAT
The simplest index that compares to every vector. Most accurate but slowest for large datasets.

```yaml
index_type: "FLAT"
metric_type: "L2"
```

### Distance Metrics

- `L2`: Euclidean distance (default). Good for most embeddings including OpenAI embeddings.
- `IP`: Inner product. Use when vectors are normalized and you want to measure closeness.
- `COSINE`: Cosine similarity. Good for measuring the angle between vectors regardless of magnitude.

## Searching vCons in Milvus

While not part of the storage module itself, you can search vCons in Milvus using the pymilvus client:

```python
from pymilvus import connections, Collection

# Connect to Milvus
connections.connect(host="localhost", port="19530")

# Load collection
collection = Collection("vcons")
collection.load()

# Get embedding for search query (using same OpenAI client as storage module)
from openai import OpenAI
client = OpenAI(api_key="your-api-key")
response = client.embeddings.create(input="your search query", model="text-embedding-3-small")
query_embedding = response.data[0].embedding

# Search parameters
search_params = {
    "metric_type": "L2",
    "params": {"nprobe": 10}
}

# Search vCons
results = collection.search(
    data=[query_embedding],
    anns_field="embedding",
    param=search_params,
    limit=5,
    output_fields=["vcon_uuid", "party_id", "text", "metadata_title"]
)

# Process results
for hits in results:
    for hit in hits:
        print(f"vCon UUID: {hit.entity.get('vcon_uuid')}")
        print(f"Score: {hit.score}")
        print(f"Title: {hit.entity.get('metadata_title')}")
```

## Notes

- Vector dimensions must match the embedding model used (1536 for text-embedding-3-small)
- For larger vCon datasets, consider configuring Milvus index parameters for better performance
- Milvus collections created by this module include a L2 vector index for similarity search