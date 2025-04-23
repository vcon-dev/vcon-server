# Vector Storage Modules for vCon Server

This guide provides information on implementing and configuring vector storage modules for vcon-server, enabling semantic search capabilities across vCon content.

## Table of Contents

- [Introduction](#introduction)
- [Vector Storage Concepts](#vector-storage-concepts)
- [Available Vector Storage Modules](#available-vector-storage-modules)
- [Implementing a Vector Storage Module](#implementing-a-vector-storage-module)
  - [Key Components](#key-components)
  - [Step-by-Step Implementation](#step-by-step-implementation)
- [Vector Indexing Options](#vector-indexing-options)
- [Best Practices](#best-practices)

## Introduction

Vector storage modules in vcon-server extend the standard storage capabilities by:

1. **Extracting textual content** from vCons (transcripts, summaries, etc.)
2. **Converting text to vector embeddings** using ML models
3. **Storing these vectors** in specialized databases for semantic search
4. **Supporting similarity-based querying** to find related conversations

Unlike regular storage that preserves the complete vCon, vector storage focuses on enabling semantic search across your conversation data.

## Vector Storage Concepts

Vector storage relies on several key concepts:

- **Embeddings**: Dense vector representations of text that capture semantic meaning
- **Vector Databases**: Specialized databases optimized for storing and searching high-dimensional vectors
- **Vector Indexing**: Methods to efficiently organize and search vectors
- **Similarity Metrics**: Ways to measure how close vectors are to each other (e.g., Euclidean distance, cosine similarity)
- **Approximate Nearest Neighbor (ANN)**: Algorithms for finding similar vectors efficiently

## Available Vector Storage Modules

vcon-server includes support for:

- **Milvus**: High-performance vector database optimized for similarity search
- **Elasticsearch**: Full-text search engine with vector search capabilities

## Implementing a Vector Storage Module

### Key Components

A vector storage module typically includes:

1. **Text extraction**: Extracting searchable content from vCons
2. **Embedding generation**: Converting text to vector embeddings
3. **Vector storage**: Saving embeddings to a vector database
4. **Vector indexing**: Creating appropriate indexes for efficient searching
5. **Configuration options**: Supporting various indexing and search parameters

### Step-by-Step Implementation

Here's a step-by-step guide to implementing a new vector storage module:

#### 1. Set Up Module Structure

Create the module directory and basic files:

```
server/storage/my_vector_db/
├── __init__.py          # Main module implementation
├── README.md            # Documentation
└── test_my_vector_db.py # Tests
```

#### 2. Implement Basic Module Interface

Start with the standard storage module interface:

```python
"""
MyVectorDB storage module for vcon-server

This module provides vector storage for vCons in MyVectorDB,
enabling semantic search across conversation content.
"""
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

# Default configuration
default_options = {
    # Connection settings
    "host": "localhost",
    "port": "8765",
    "collection_name": "vcons",
    
    # Embedding settings
    "embedding_model": "sentence-transformers/all-mpnet-base-v2",
    "embedding_dim": 768,
    
    # Vector index settings
    "index_type": "HNSW",
    "metric_type": "COSINE",
    "index_params": {
        "M": 16,
        "ef_construction": 200
    }
}

def save(vcon_uuid, opts=default_options):
    """Save a vCon to vector storage.
    
    Args:
        vcon_uuid: UUID of the vCon to save
        opts: Configuration options
        
    Raises:
        Exception: If saving fails
    """
    # Implementation here...
    pass

def get(vcon_uuid, opts=default_options):
    """Get a vCon from vector storage.
    
    Args:
        vcon_uuid: UUID of the vCon to retrieve
        opts: Configuration options
        
    Returns:
        dict or None: Retrieved vCon data or None if not found
    """
    # Implementation here (optional)...
    pass
```

#### 3. Add Text Extraction

Add functions to extract text content from vCons:

```python
def extract_text_from_vcon(vcon: dict) -> str:
    """Extract searchable text content from a vCon.
    
    Args:
        vcon: The vCon object as a dictionary
        
    Returns:
        str: Extracted text content
    """
    text = ""
    
    # Extract transcript from analysis
    if "analysis" in vcon:
        transcript_analyses = [a for a in vcon["analysis"] if a.get("type") == "transcript"]
        for analysis in transcript_analyses:
            if "body" in analysis and "text" in analysis["body"]:
                text += analysis["body"]["text"] + " "
    
    # Extract summary from analysis
    if "analysis" in vcon:
        summary_analyses = [a for a in vcon["analysis"] if a.get("type") == "summary"]
        for analysis in summary_analyses:
            if "body" in analysis and isinstance(analysis["body"], str):
                text += analysis["body"] + " "
            elif "body" in analysis and isinstance(analysis["body"], dict) and "text" in analysis["body"]:
                text += analysis["body"]["text"] + " "
    
    # Extract dialog text
    if "dialog" in vcon:
        for dialog in vcon["dialog"]:
            if dialog.get("type") == "text" and "body" in dialog:
                text += dialog["body"] + " "
    
    # Add metadata
    if "metadata" in vcon:
        if "title" in vcon["metadata"]:
            text += f"Title: {vcon['metadata']['title']}. "
        if "description" in vcon["metadata"]:
            text += f"Description: {vcon['metadata']['description']}. "
    
    return text.strip()
```

#### 4. Add Embedding Generation

Implement functions to generate embeddings:

```python
def get_embedding(text: str, model_name: str) -> list:
    """Generate embedding vector for text.
    
    Args:
        text: The text to embed
        model_name: Name of the embedding model to use
        
    Returns:
        list: Embedding vector
    """
    # Implementation depends on your embedding library
    # Example using sentence-transformers:
    from sentence_transformers import SentenceTransformer
    
    model = SentenceTransformer(model_name)
    embedding = model.encode(text)
    
    return embedding.tolist()
```

#### 5. Implement Vector Database Integration

Add functions to interact with your vector database:

```python
def connect_to_db(host: str, port: str) -> Any:
    """Connect to vector database.
    
    Args:
        host: Database host
        port: Database port
        
    Returns:
        Connection object
    """
    # Implementation depends on your vector database
    import my_vector_db_client
    
    return my_vector_db_client.connect(host=host, port=port)

def create_collection(client, collection_name: str, dim: int, index_type: str, index_params: dict):
    """Create a new collection in the vector database.
    
    Args:
        client: Database client
        collection_name: Name for the collection
        dim: Dimension of embeddings
        index_type: Type of vector index
        index_params: Parameters for the index
        
    Returns:
        Collection object
    """
    # Implementation depends on your vector database
    # Example:
    schema = {
        "fields": [
            {"name": "id", "type": "String", "primaryKey": True},
            {"name": "vcon_uuid", "type": "String"},
            {"name": "text", "type": "String"},
            {"name": "embedding", "type": "FloatVector", "dimension": dim}
        ]
    }
    
    collection = client.create_collection(collection_name, schema)
    
    # Create index
    collection.create_index(
        field_name="embedding",
        index_type=index_type,
        params=index_params
    )
    
    return collection
```

#### 6. Complete the Save Function

Implement the full save function:

```python
def save(vcon_uuid, opts=default_options):
    """Save a vCon to vector storage.
    
    Args:
        vcon_uuid: UUID of the vCon to save
        opts: Configuration options
        
    Raises:
        Exception: If saving fails
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    logger.info(f"Starting vector storage for vCon: {vcon_uuid}")
    
    try:
        # Get vCon from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Extract text
        text = extract_text_from_vcon(vcon.to_dict())
        if not text:
            logger.warning(f"No text content extracted from vCon {vcon_uuid}")
            return
        
        # Generate embedding
        embedding = get_embedding(text, opts["embedding_model"])
        
        # Connect to database
        client = connect_to_db(opts["host"], opts["port"])
        
        # Get or create collection
        collection_name = opts["collection_name"]
        if not client.has_collection(collection_name):
            logger.info(f"Creating collection {collection_name}")
            collection = create_collection(
                client,
                collection_name,
                opts["embedding_dim"],
                opts["index_type"],
                opts["index_params"]
            )
        else:
            collection = client.get_collection(collection_name)
        
        # Insert data
        collection.insert([{
            "id": vcon_uuid,
            "vcon_uuid": vcon_uuid,
            "text": text,
            "embedding": embedding
        }])
        
        logger.info(f"Successfully saved vCon {vcon_uuid} to vector storage")
    except Exception as e:
        logger.error(f"Failed to save vCon {vcon_uuid} to vector storage: {e}")
        raise e
```

## Vector Indexing Options

Vector databases offer various indexing options, each with different trade-offs:

### IVF-based Indexes

- **IVF_FLAT**: Divides vectors into clusters, then does exact search within clusters
  - Good balance of speed and accuracy
  - Higher memory usage
  - Used for medium-sized datasets (~millions of vectors)

- **IVF_SQ8**: Similar to IVF_FLAT, but with scalar quantization to reduce memory
  - Smaller memory footprint
  - Slight decrease in accuracy
  - Good for larger datasets with memory constraints

- **IVF_PQ**: Product Quantization for maximum compression
  - Smallest memory footprint
  - More significant accuracy trade-off
  - Ideal for very large datasets

### Graph-based Indexes

- **HNSW** (Hierarchical Navigable Small World): Advanced graph-based algorithm
  - Very fast search, even with large datasets
  - Higher memory usage and build time
  - Great for applications where search speed is critical

### Brute Force

- **FLAT**: Exhaustive comparison with all vectors
  - 100% accurate results
  - Slowest performance, especially with large datasets
  - Use only for small datasets or when accuracy is critical

### Distance Metrics

- **L2**: Euclidean distance (straight-line distance in vector space)
  - Standard for most embeddings, including OpenAI embeddings
  - Simple and intuitive

- **COSINE**: Cosine similarity (angle between vectors)
  - Useful when vector magnitude isn't important
  - Normalized to be invariant to vector length
  - Good for text embeddings from many models

- **IP** (Inner Product): Dot product between vectors
  - Used with normalized vectors
  - Similar to cosine but slightly faster

## Best Practices

1. **Choose the right index type** based on your dataset size and requirements:
   - Small datasets (<100K vectors): FLAT or HNSW for maximum accuracy
   - Medium datasets (100K-10M vectors): HNSW or IVF_FLAT for balance
   - Large datasets (>10M vectors): IVF_SQ8 or IVF_PQ for efficiency

2. **Optimize index parameters** based on your data:
   - For IVF indexes: `nlist` should be approximately sqrt(N) where N is vector count
   - For HNSW: higher `M` means more connections and faster but more memory usage

3. **Choose the right embedding model**:
   - OpenAI models (text-embedding-3-small/large) provide excellent quality
   - Open-source models (sentence-transformers) can be used for local deployment

4. **Implement caching** for embedding generation to avoid unnecessary API calls

5. **Provide good defaults** in your module's `default_options`

6. **Add documentation** explaining index types and their trade-offs

7. **Add error handling** for edge cases like missing or empty vCons