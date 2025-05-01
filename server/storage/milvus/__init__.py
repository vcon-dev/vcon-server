"""
Milvus storage module for vcon-server

This module provides integration with the Milvus vector database
for storing vCons as vector embeddings for semantic search.
"""
import logging
import tempfile
from typing import List, Dict, Any, Optional, Union
import time

from lib.logging_utils import init_logger
from lib.metrics import stats_gauge, stats_count
from server.lib.vcon_redis import VconRedis

try:
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
    from openai import OpenAI
except ImportError:
    logging.error("Required packages not found. Install with: pip install pymilvus openai")
    raise

logger = init_logger(__name__)

# Default configuration
default_options = {
    "host": "localhost",  # Milvus server hostname
    "port": "19530",      # Milvus server port
    "collection_name": "vcons",  # Default collection name
    "embedding_model": "text-embedding-3-small",  # OpenAI embedding model to use
    "embedding_dim": 1536,  # Dimensions for text-embedding-3-small
    "api_key": None,  # OpenAI API key
    "organization": None,  # OpenAI organization ID
    "create_collection_if_missing": False,  # Whether to create collection if it doesn't exist
    "skip_if_exists": True,  # Skip storing vCons that already exist in Milvus
    "index_type": "IVF_FLAT",  # Vector index type: IVF_FLAT, IVF_SQ8, IVF_PQ, HNSW, ANNOY, etc.
    "metric_type": "L2",   # Distance metric: L2 (Euclidean), IP (Inner Product), COSINE
    "nlist": 128,          # Number of clusters for IVF indexes
    "m": 16,               # HNSW parameter: number of edges per node
    "ef_construction": 200, # HNSW parameter: size of the dynamic candidate list during construction
}

def ensure_milvus_connection(host: str, port: str) -> bool:
    """
    Ensure connection to Milvus server is established.
    
    Args:
        host: Milvus server hostname
        port: Milvus server port
        
    Returns:
        bool: Whether connection is successful
    """
    try:
        # Check if connection exists by attempting a simple operation
        utility.list_collections()
    except Exception as e:
        logger.warning(f"Reconnecting to Milvus: {e}")
        try:
            # Attempt to disconnect first in case there's a stale connection
            try:
                connections.disconnect("default")
            except:
                pass
            # Connect to Milvus
            connections.connect(host=host, port=port)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            return False
    return True

def get_embedding(text: str, openai_client, model: str) -> List[float]:
    """
    Get embedding vector from OpenAI for the given text.
    
    Args:
        text: The text to embed
        openai_client: Initialized OpenAI client
        model: The embedding model to use
        
    Returns:
        List[float]: The embedding vector
    """
    start_time = time.time()
    
    # Handle empty text
    if not text:
        logger.warning("Empty text provided for embedding, returning zero vector")
        return [0] * default_options["embedding_dim"]
    
    try:
        response = openai_client.embeddings.create(
            input=text,
            model=model
        )
        embedding_time = time.time() - start_time
        stats_gauge("conserver.storage.milvus.embedding_time", embedding_time)
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Failed to get embedding: {e}")
        stats_count("conserver.storage.milvus.embedding_failures")
        # Return zero vector as fallback
        return [0] * default_options["embedding_dim"]

def extract_text_from_vcon(vcon: dict) -> str:
    """
    Extract searchable text content from a vCon.
    
    Args:
        vcon: The vCon object
        
    Returns:
        str: Extracted text
    """
    start_time = time.time()
    vcon_id = vcon.get("uuid", "unknown")
    logger.info(f"Extracting text from vCon {vcon_id}")
    
    text = ""
    extracted_components = []
    
    # Extract transcript if available
    if "transcript" in vcon:
        transcript_length = len(vcon.get("transcript", []))
        if transcript_length > 0:
            text += " ".join([item.get("text", "") for item in vcon.get("transcript", []) if "text" in item]) + " "
            extracted_components.append(f"transcript ({transcript_length} entries)")
            logger.debug(f"Extracted transcript with {transcript_length} entries from vCon {vcon_id}")
    
    # Extract analysis with type "transcript"
    if "analysis" in vcon:
        transcript_analyses = [a for a in vcon["analysis"] if a.get("type") == "transcript"]
        for analysis in transcript_analyses:
            if "body" in analysis and "text" in analysis["body"]:
                text += analysis["body"]["text"] + " "
                extracted_components.append(f"transcript analysis")
                logger.debug(f"Extracted transcript analysis from vCon {vcon_id}")
    
    # Extract summary analysis
    if "analysis" in vcon:
        summary_analyses = [a for a in vcon["analysis"] if a.get("type") == "summary"]
        for analysis in summary_analyses:
            if "body" in analysis and isinstance(analysis["body"], str):
                text += analysis["body"] + " "
                extracted_components.append(f"summary analysis")
                logger.debug(f"Extracted summary analysis from vCon {vcon_id}")
            elif "body" in analysis and isinstance(analysis["body"], dict) and "text" in analysis["body"]:
                text += analysis["body"]["text"] + " "
                extracted_components.append(f"summary analysis")
                logger.debug(f"Extracted summary analysis from vCon {vcon_id}")
    
    # Extract party information
    party_count = 0
    if "parties" in vcon and vcon["parties"]:
        for party in vcon["parties"]:
            party_name = party.get("name", "")
            party_role = party.get("role", "")
            party_id = party.get("partyId", "")
            if party_name or party_id or party_role:
                text += f"Party: {party_role + ' ' if party_role else ''}{party_name or party_id}. "
                party_count += 1
        if party_count > 0:
            extracted_components.append(f"parties ({party_count})")
            logger.debug(f"Extracted {party_count} parties from vCon {vcon_id}")
    
    # Extract metadata
    metadata_fields = []
    if "metadata" in vcon:
        if "title" in vcon["metadata"]:
            text += f"Title: {vcon['metadata']['title']}. "
            metadata_fields.append("title")
        if "description" in vcon["metadata"]:
            text += f"Description: {vcon['metadata']['description']}. "
            metadata_fields.append("description")
        if "created" in vcon["metadata"]:
            text += f"Created: {vcon['metadata']['created']}. "
            metadata_fields.append("created")
        
        if metadata_fields:
            extracted_components.append(f"metadata ({', '.join(metadata_fields)})")
            logger.debug(f"Extracted metadata fields: {', '.join(metadata_fields)} from vCon {vcon_id}")
    
    # Extract dialog text content
    dialog_count = 0
    if "dialog" in vcon and vcon["dialog"]:
        for dialog in vcon["dialog"]:
            if dialog.get("type") == "text" and "body" in dialog:
                text += f"{dialog.get('body', '')} "
                dialog_count += 1
        if dialog_count > 0:
            extracted_components.append(f"dialog texts ({dialog_count})")
            logger.debug(f"Extracted {dialog_count} text dialogs from vCon {vcon_id}")
    
    raw_text = text.strip()
    raw_text_length = len(raw_text)
    
    # Log what we found
    if extracted_components:
        logger.info(f"Extracted components from vCon {vcon_id}: {', '.join(extracted_components)}")
    else:
        logger.warning(f"No text content extracted from vCon {vcon_id}")
    
    logger.info(f"Raw text length: {raw_text_length} characters")
    
    extraction_time = time.time() - start_time
    stats_gauge("conserver.storage.milvus.text_extraction_time", extraction_time)
    return raw_text

def extract_party_id(vcon: dict) -> str:
    """
    Extract a meaningful party identifier from a vCon.
    
    Args:
        vcon: The vCon object
        
    Returns:
        str: Party identifier
    """
    logger.debug(f"Extracting party ID from vCon {vcon.get('uuid', 'unknown')}")
    
    if not vcon.get("parties"):
        logger.debug("No parties array found in vCon")
        # Try alternative fields if parties is not available
        if vcon.get("metadata", {}).get("creator"):
            return vcon["metadata"]["creator"]
        return "no_party_info"
    
    # Try to find a non-empty party ID from any party in the array
    for party in vcon["parties"]:
        # First priority: UUID as it's unique
        if party.get("uuid"):
            logger.debug(f"Using party UUID: {party['uuid']}")
            return party["uuid"]
        
        # Second priority: Contact methods (tel, mailto)
        if party.get("tel"):
            logger.debug(f"Using party telephone: {party['tel']}")
            return f"tel:{party['tel']}"
        
        if party.get("mailto"):
            logger.debug(f"Using party email: {party['mailto']}")
            return f"mailto:{party['mailto']}"
        
        # Third priority: Name and role combined
        if party.get("name") and party.get("role"):
            combined = f"{party['role']}:{party['name']}"
            logger.debug(f"Using party role+name: {combined}")
            return combined
        
        # Fourth priority: Just name or role
        if party.get("name"):
            logger.debug(f"Using party name: {party['name']}")
            return party["name"]
        
        if party.get("role"):
            logger.debug(f"Using party role: {party['role']}")
            return party["role"]
        
        # Fifth priority: Any other unique identifier in the party object
        for field in ["partyId", "PartyId", "party_id", "id", "userID", "userId"]:
            if party.get(field):
                logger.debug(f"Found non-standard ID {party[field]} using field {field}")
                return party[field]
    
    # If we got here but have parties, use the first party's index as identifier
    if vcon["parties"]:
        logger.debug("No explicit identifiers found, using party index")
        return f"party_index:0"
    
    logger.debug("No usable party identifier found")
    return "unknown_party"

def create_collection(collection_name: str, embedding_dim: int, opts: dict) -> Union[Collection, None]:
    """
    Create a new Milvus collection for vCons.
    
    Args:
        collection_name: Name for the new collection
        embedding_dim: Dimension of the embedding vectors
        opts: Configuration options including index parameters
        
    Returns:
        Collection or None: The created collection or None if failed
    """
    try:
        # Define collection schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="vcon_uuid", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="party_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
            FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=30),
            FieldSchema(name="updated_at", dtype=DataType.VARCHAR, max_length=30),
            FieldSchema(name="subject", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="metadata_title", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="has_transcript", dtype=DataType.BOOL),
            FieldSchema(name="has_summary", dtype=DataType.BOOL),
            FieldSchema(name="party_count", dtype=DataType.INT16),
            FieldSchema(name="embedding_model", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="embedding_version", dtype=DataType.VARCHAR, max_length=20),
        ]
        
        schema = CollectionSchema(fields=fields, description="vCons collection for semantic search")
        
        # Create collection
        collection = Collection(name=collection_name, schema=schema)
        
        # Prepare index parameters based on the selected index type
        index_type = opts.get("index_type", "IVF_FLAT")
        metric_type = opts.get("metric_type", "L2")
        
        # Configure index parameters based on index type
        if index_type.startswith("IVF"):  # IVF_FLAT, IVF_SQ8, IVF_PQ
            params = {"nlist": opts.get("nlist", 128)}
            
            # Additional params for IVF_PQ
            if index_type == "IVF_PQ":
                # For PQ, m is typically set to 8 or 12
                params["m"] = opts.get("pq_m", 8)
                # nbits is typically 8
                params["nbits"] = opts.get("pq_nbits", 8)
                
        elif index_type == "HNSW":
            params = {
                "M": opts.get("m", 16),  # Number of edges per node
                "efConstruction": opts.get("ef_construction", 200)  # Size of the dynamic candidate list during construction
            }
            
        elif index_type == "ANNOY":
            params = {
                "n_trees": opts.get("n_trees", 50)  # Number of trees for ANNOY
            }
            
        elif index_type == "FLAT":
            # FLAT index doesn't need additional parameters
            params = {}
            
        else:
            # Default to IVF_FLAT if index type is not recognized
            logger.warning(f"Unrecognized index type {index_type}, defaulting to IVF_FLAT")
            index_type = "IVF_FLAT"
            params = {"nlist": opts.get("nlist", 128)}
        
        # Create the index
        index_params = {
            "metric_type": metric_type,
            "index_type": index_type,
            "params": params
        }
        
        logger.info(f"Creating index of type {index_type} with metric {metric_type}")
        collection.create_index(field_name="embedding", index_params=index_params)
        
        logger.info(f"Created collection '{collection_name}' successfully with {index_type} index")
        return collection
    except Exception as e:
        logger.error(f"Failed to create collection: {e}")
        return None

def check_vcon_exists(collection: Collection, vcon_uuid: str) -> bool:
    """
    Check if a vCon already exists in the Milvus collection.
    
    Args:
        collection: Milvus collection
        vcon_uuid: UUID of the vCon to check
        
    Returns:
        bool: Whether the vCon exists
    """
    try:
        collection.load()
        results = collection.query(
            expr=f"vcon_uuid == '{vcon_uuid}'",
            output_fields=["vcon_uuid"]
        )
        return len(results) > 0
    except Exception as e:
        logger.error(f"Error checking if vCon exists: {e}")
        return False

def save(vcon_uuid: str, opts=default_options) -> None:
    """
    Save a vCon to Milvus as a vector embedding.
    
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
    
    logger.info(f"Starting Milvus storage for vCon: {vcon_uuid}")
    
    # Ensure connection to Milvus
    connection_status = ensure_milvus_connection(opts["host"], opts["port"])
    if not connection_status:
        error_msg = f"Failed to connect to Milvus at {opts['host']}:{opts['port']}"
        logger.error(error_msg)
        raise ConnectionError(error_msg)
    
    collection_name = opts["collection_name"]
    
    # Check if collection exists
    if not utility.has_collection(collection_name):
        if opts["create_collection_if_missing"]:
            logger.info(f"Collection {collection_name} does not exist, creating...")
            collection = create_collection(collection_name, opts["embedding_dim"], opts)
            if not collection:
                error_msg = f"Failed to create collection {collection_name}"
                logger.error(error_msg)
                raise ValueError(error_msg)
        else:
            error_msg = f"Collection {collection_name} does not exist"
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    # Get collection
    collection = Collection(collection_name)
    
    try:
        # Retrieve vCon from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        if vcon is None:
            error_msg = f"vCon with UUID {vcon_uuid} not found in Redis"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Convert vCon to dict if it's a Vcon object
        if hasattr(vcon, "to_dict"):
            vcon_dict = vcon.to_dict()
        else:
            vcon_dict = vcon
        
        # Skip if vCon already exists and skip_if_exists is True
        if opts["skip_if_exists"]:
            collection.load()
            if check_vcon_exists(collection, vcon_uuid):
                logger.info(f"vCon {vcon_uuid} already exists in Milvus collection {collection_name}, skipping")
                return
        
        # Initialize OpenAI client
        openai_client = OpenAI(
            api_key=opts["api_key"],
            organization=opts["organization"] if opts["organization"] else None
        )
        
        # Extract text content from vCon
        text = extract_text_from_vcon(vcon_dict)
        
        # Skip if no text content
        if not text:
            logger.warning(f"No text content extracted from vCon {vcon_uuid}, skipping")
            return
        
        # Get party identifier
        party_id = extract_party_id(vcon_dict)
        
        # Get embedding vector
        embedding = get_embedding(text, openai_client, opts["embedding_model"])
        
        # Validate embedding dimensions
        if len(embedding) != opts["embedding_dim"]:
            error_msg = f"Invalid embedding dimensions: got {len(embedding)}, expected {opts['embedding_dim']}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Extract metadata
        metadata = vcon_dict.get("metadata", {})
        created_at = str(metadata.get("created_at", "")) if metadata.get("created_at") is not None else ""
        updated_at = str(metadata.get("updated_at", "")) if metadata.get("updated_at") is not None else ""
        subject = str(vcon_dict.get("subject", "")) if vcon_dict.get("subject") is not None else ""
        title = str(metadata.get("title", "")) if metadata.get("title") is not None else ""
        
        # Content indicators
        has_transcript = bool("transcript" in vcon_dict or any(a.get("type") == "transcript" for a in vcon_dict.get("analysis", [])))
        has_summary = bool(any(a.get("type") == "summary" for a in vcon_dict.get("analysis", [])))
        party_count = len(vcon_dict.get("parties", []))
        
        # Prepare data for insertion
        data = [{
            "vcon_uuid": vcon_uuid,
            "party_id": party_id,
            "text": text,
            "embedding": embedding,
            "created_at": created_at,
            "updated_at": updated_at,
            "subject": subject,
            "metadata_title": title,
            "has_transcript": has_transcript,
            "has_summary": has_summary,
            "party_count": party_count,
            "embedding_model": opts["embedding_model"],
            "embedding_version": "1.0"
        }]
        
        # Insert data
        logger.debug(f"Inserting vCon {vcon_uuid} into Milvus collection {collection_name}")
        collection.insert(data)
        collection.flush()
        
        logger.info(f"Successfully saved vCon {vcon_uuid} to Milvus collection {collection_name}")
        stats_count("conserver.storage.milvus.vcons_stored")
        
    except Exception as e:
        logger.error(f"Failed to save vCon {vcon_uuid} to Milvus: {e}")
        stats_count("conserver.storage.milvus.storage_failures")
        raise e

def get(vcon_uuid: str, opts=default_options) -> Optional[dict]:
    """
    Get a vCon from Milvus collection.
    
    Note: Milvus doesn't store the complete vCon data.
    This function only returns the text and embedding data.
    
    Args:
        vcon_uuid: UUID of the vCon to retrieve
        opts: Configuration options
        
    Returns:
        Optional[dict]: Dict with text and embedding if found, None otherwise
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    logger.info(f"Retrieving vCon {vcon_uuid} from Milvus")
    
    # Ensure connection to Milvus
    connection_status = ensure_milvus_connection(opts["host"], opts["port"])
    if not connection_status:
        logger.error(f"Failed to connect to Milvus at {opts['host']}:{opts['port']}")
        return None
    
    collection_name = opts["collection_name"]
    
    # Check if collection exists
    if not utility.has_collection(collection_name):
        logger.error(f"Collection {collection_name} does not exist")
        return None
    
    # Get collection
    try:
        collection = Collection(collection_name)
        collection.load()
        
        # Query for the vCon
        results = collection.query(
            expr=f"vcon_uuid == '{vcon_uuid}'",
            output_fields=["vcon_uuid", "text", "embedding", "party_id"]
        )
        
        if not results:
            logger.warning(f"vCon {vcon_uuid} not found in Milvus collection {collection_name}")
            return None
        
        # Return the first result
        logger.info(f"Successfully retrieved vCon {vcon_uuid} from Milvus")
        return {
            "uuid": results[0]["vcon_uuid"],
            "text": results[0]["text"],
            "embedding": results[0]["embedding"],
            "party_id": results[0]["party_id"]
        }
        
    except Exception as e:
        logger.error(f"Error retrieving vCon {vcon_uuid} from Milvus: {e}")
        return None