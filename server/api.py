"""FastAPI server implementation for the vCon API.

This module implements a REST API for managing vCon (Voice Conversation) records.
It provides endpoints for CRUD operations on vCons, chain management, configuration,
and dead letter queue (DLQ) handling. The API uses Redis for primary storage and
supports PostgreSQL as a secondary storage option.

The API includes features for:
- vCon management (create, read, update, delete)
- Chain ingress/egress operations
- Configuration management
- Dead letter queue handling
- Search functionality for vCons by various criteria

Redis Caching Behavior:
When a vCon is not found in Redis but exists in a configured storage backend,
the API will automatically store it back in Redis with a configurable expiration time
(VCON_REDIS_EXPIRY, default 1 hour). This improves performance for subsequent requests
for the same vCon, as they'll be served from Redis instead of having to query the
storage backend again.
"""

import os
import traceback
from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime

import yaml
from fastapi import FastAPI, HTTPException, Query, Security, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from peewee import CharField, Model
from playhouse.postgres_ext import (
    BinaryJSONField,
    DateTimeField,
    PostgresqlExtDatabase,
    UUIDField,
)
from pydantic import BaseModel, ConfigDict
from starlette.status import HTTP_403_FORBIDDEN

from config import Configuration
from dlq_utils import get_ingress_list_dlq_name
from lib.logging_utils import init_logger
import redis_mgr
from settings import (
    VCON_SORTED_SET_NAME,
    VCON_STORAGE,
    CONSERVER_API_TOKEN,
    CONSERVER_HEADER_NAME,
    CONSERVER_API_TOKEN_FILE,
    API_ROOT_PATH,
    VCON_INDEX_EXPIRY,
    VCON_REDIS_EXPIRY,
)
from storage.base import Storage

# Initialize logging
logger = init_logger(__name__)
logger.info("API starting up")

# Initialize FastAPI app with CORS middleware
app = FastAPI(root_path=API_ROOT_PATH)
api_key_header = APIKeyHeader(name=CONSERVER_HEADER_NAME, auto_error=False)

# Setup API key authentication
api_keys = []
if CONSERVER_API_TOKEN:
    api_keys.append(CONSERVER_API_TOKEN)
    logger.info("Adding CONSERVER_API_TOKEN to api_keys")

if CONSERVER_API_TOKEN_FILE:
    logger.info("Adding CONSERVER_API_TOKEN_FILE to api_keys")
    # Read the API keys from file, one key per line
    with open(CONSERVER_API_TOKEN_FILE, 'r') as file:
        for line in file:
            api_keys.append(line.strip())
                    
if not api_keys:
    logger.info("No API keys found, skipping authentication")


async def get_api_key(api_key_header: str = Security(api_key_header)) -> Optional[str]:
    """Validate the API key from the request header.
    
    Args:
        api_key_header: The API key from the request header
        
    Returns:
        The validated API key if valid
        
    Raises:
        HTTPException: If the API key is invalid
    """
    # If no API keys configured, skip authentication
    if not api_keys:
        logger.info("Skipping authentication")
        return None

    if api_key_header not in api_keys:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API Key")
    return api_key_header


def validate_ingress_api_key(
    ingress_list: str, api_key_header: str
) -> str:
    """Validate the API key for a specific ingress list.

    Args:
        ingress_list: Name of the ingress list to validate access for
        api_key_header: The API key from the request header

    Returns:
        The validated API key if valid for the ingress list

    Raises:
        HTTPException: If the API key is invalid or not authorized for the ingress list
    """
    if not api_key_header:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="API Key required")

    # Get ingress-specific API key configuration
    ingress_auth = Configuration.get_ingress_auth()

    if not ingress_auth:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="No ingress authentication configured",
        )

    # Check if the ingress list is configured
    if ingress_list not in ingress_auth:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail=f"Ingress list '{ingress_list}' not configured",
        )

    # Get allowed API keys for this ingress list - can be a string or list
    allowed_keys = ingress_auth[ingress_list]

    # Convert single string to list for consistent processing
    if isinstance(allowed_keys, str):
        allowed_keys = [allowed_keys]
    elif not isinstance(allowed_keys, list):
        logger.error(
            f"Invalid API key configuration for ingress list '{ingress_list}'. Expected string or list."
        )
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail=f"Invalid configuration for ingress list '{ingress_list}'",
        )

    # Validate the API key against all allowed keys for this ingress list
    if api_key_header not in allowed_keys:
        logger.warning(f"Invalid API key for ingress list '{ingress_list}'")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail=f"Invalid API Key for ingress list '{ingress_list}'",
        )

    logger.debug(f"Valid API key provided for ingress list '{ingress_list}'")
    return api_key_header


async def on_startup() -> None:
    """Initialize Redis client on application startup."""
    global redis_async
    redis_async = await redis_mgr.get_async_client()


async def on_shutdown() -> None:
    """Close Redis client on application shutdown."""
    await redis_async.close()


# Register startup/shutdown handlers
app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

api_router = APIRouter()
external_router = APIRouter()


class Vcon(BaseModel):
    """Pydantic model representing a vCon (Voice Conversation) record.
    
    Attributes:
        vcon: The vCon version identifier
        uuid: Unique identifier for the vCon
        created_at: Timestamp when the vCon was created
        subject: Optional subject/title of the conversation
        redacted: Dictionary of redacted content
        appended: Optional dictionary of appended content
        group: List of group metadata
        parties: List of conversation participants
        dialog: List of conversation entries
        analysis: List of analysis results
        attachments: List of attached files/content
    """
    model_config = ConfigDict(extra='allow')
    vcon: str
    uuid: UUID
    created_at: datetime
    subject: Optional[str] = None
    redacted: dict = {}
    appended: Optional[dict] = None
    group: List[Dict] = []
    parties: List[Dict] = []
    dialog: List[Dict] = []
    analysis: List[Dict] = []
    attachments: List[Dict] = []


if VCON_STORAGE:
    class VConPeeWee(Model):
        """Peewee model for PostgreSQL storage of vCons.
        
        Attributes:
            id: Primary key UUID
            vcon: vCon version identifier
            uuid: vCon UUID
            created_at: Creation timestamp
            updated_at: Last update timestamp
            subject: Conversation subject
            vcon_json: Full vCon JSON content
            type: vCon type identifier
        """
        id = UUIDField(primary_key=True)
        vcon = CharField()
        uuid = UUIDField()
        created_at = DateTimeField()
        updated_at = DateTimeField(null=True)
        subject = CharField(null=True)
        vcon_json = BinaryJSONField(null=True)
        type = CharField(null=True)

        class Meta:
            table_name = "vcons"
            database = PostgresqlExtDatabase(VCON_STORAGE)


async def add_vcon_to_set(vcon_uuid: str, timestamp: int) -> None:
    """Add a vCon to the sorted set in Redis.
    
    Args:
        vcon_uuid: UUID string of the vCon to add
        timestamp: Unix timestamp to use as score
    """
    await redis_async.zadd(VCON_SORTED_SET_NAME, {vcon_uuid: timestamp})


async def ensure_vcon_in_redis(vcon_uuid: UUID) -> Optional[dict]:
    """Ensure a vCon exists in Redis, syncing from storage if necessary.
    
    First checks if the vCon exists in Redis. If not found, attempts to retrieve
    it from configured storage backends and syncs it back to Redis with proper
    indexing and expiration.
    
    Args:
        vcon_uuid: UUID of the vCon to ensure is in Redis
        
    Returns:
        The vCon data if found, None if not found in any storage
    """
    # First check if vCon exists in Redis
    vcon = await redis_async.json().get(f"vcon:{str(vcon_uuid)}")
    if vcon:
        return vcon
    
    # If not in Redis, try to sync from storage backends
    return await sync_vcon_from_storage(vcon_uuid)


async def sync_vcon_from_storage(vcon_uuid: UUID) -> Optional[dict]:
    """Sync a vCon from storage backends to Redis.
    
    Attempts to retrieve the vCon from configured storage backends and syncs it
    back to Redis with proper indexing and expiration. This is useful when you
    already know the vCon is not in Redis (e.g., after a batch mget operation).
    
    Args:
        vcon_uuid: UUID of the vCon to sync from storage
        
    Returns:
        The vCon data if found in storage, None if not found
    """
    # Try to get from storage backends
    for storage_name in Configuration.get_storages():
        vcon = Storage(storage_name=storage_name).get(str(vcon_uuid))
        if vcon:
            # Store the vCon back in Redis with expiration
            await redis_async.json().set(f"vcon:{str(vcon_uuid)}", "$", vcon)
            await redis_async.expire(f"vcon:{str(vcon_uuid)}", VCON_REDIS_EXPIRY)
            # Add to sorted set for timestamp-based retrieval
            created_at = datetime.fromisoformat(vcon["created_at"])
            timestamp = int(created_at.timestamp())
            await add_vcon_to_set(str(vcon_uuid), timestamp)
            return vcon
    
    return None


@api_router.get(
    "/vcon",
    response_model=List[str],
    summary="Gets a list of vCon UUIDs",
    description=(
        "Retrieves a list of vCon UUIDs. You can use the page and size query "
        "parameters to paginate the results. You can also filter the results "
        "by date using the since and until query parameters. The results are "
        "sorted in descending order by timestamp. "
    ),
    tags=["vcon"],
)
async def get_vcons_uuids(
    page: int = Query(1, description="Page number for pagination"),
    size: int = Query(50, description="Number of items per page"),
    since: Optional[datetime] = Query(None, description="Filter vCons created after this date"),
    until: Optional[datetime] = Query(None, description="Filter vCons created before this date")
) -> List[str]:
    """Get a paginated list of vCon UUIDs with optional date filtering.

    Args:
        page: The page number to retrieve (1-indexed)
        size: Number of items per page
        since: Optional datetime to filter vCons created after
        until: Optional datetime to filter vCons created before

    Returns:
        List of vCon UUIDs as strings

    Note:
        Results are sorted in descending order by timestamp
    """
    until_timestamp = "+inf"
    since_timestamp = "-inf"

    if since:
        since_timestamp = int(since.timestamp())
    if until:
        until_timestamp = int(until.timestamp())
    
    offset = (page - 1) * size
    vcon_uuids = await redis_async.zrevrangebyscore(
        VCON_SORTED_SET_NAME,
        until_timestamp,
        since_timestamp,
        start=offset,
        num=size,
    )
    logger.info(f"Returning {len(vcon_uuids)} vcon_uuids")

    # Convert the vcon_uuids to strings and strip the vcon: prefix
    return [vcon.split(":")[1] for vcon in vcon_uuids]


@api_router.get(
    "/vcon/egress",
    status_code=204,
    summary="Removes vCon UUIDs from a chain output",
    description="Removes one or more vCon UUIDs from the output of a chain (egress)",
    tags=["chain"],
)
async def get_vcon_egress(
    egress_list: str = Query(..., description="Name of the egress list to pop from"),
    limit: int = Query(1, description="Maximum number of UUIDs to remove")
) -> JSONResponse:
    """Remove and return vCon UUIDs from a chain's egress list.

    Args:
        egress_list: Name of the Redis list to pop from
        limit: Maximum number of UUIDs to remove (defaults to 1)

    Returns:
        JSONResponse containing list of removed vCon UUIDs

    Raises:
        HTTPException: If there is an error accessing Redis
    """
    try:
        vcon_uuids = []
        for _ in range(limit):
            vcon_uuid = await redis_async.rpop(egress_list)
            if vcon_uuid:
                vcon_uuids.append(vcon_uuid)
        return JSONResponse(content=vcon_uuids)

    except Exception as e:
        logger.error(f"Error in get_vcon_egress: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to pop from egress list")


@api_router.get(
    "/vcon/{vcon_uuid}",
    response_model=Vcon,
    summary="Gets a vCon by UUID",
    description="Retrieve a specific vCon by its UUID",
    tags=["vcon"],
)
async def get_vcon(vcon_uuid: UUID) -> JSONResponse:
    """Get a specific vCon by its UUID.

    First attempts to retrieve from Redis, then falls back to configured storages
    if not found in Redis. If found in storage, it will be stored back in Redis
    with a configurable expiration time (VCON_REDIS_EXPIRY, default 1 hour).

    Args:
        vcon_uuid: UUID of the vCon to retrieve

    Returns:
        JSONResponse containing the vCon data if found

    Raises:
        HTTPException: If vCon is not found (404)
    """
    vcon = await ensure_vcon_in_redis(vcon_uuid)
    
    if not vcon:
        raise HTTPException(status_code=404, detail="vCon not found")
        
    return JSONResponse(content=vcon)


@api_router.get(
    "/vcons",
    response_model=List[Vcon],
    summary="Gets multiple vCons by UUIDs",
    description="Retrieve multiple vCons by their UUIDs",
    tags=["vcon"],
)
async def get_vcons(
    vcon_uuids: List[UUID] = Query(None, description="List of vCon UUIDs to retrieve")
) -> JSONResponse:
    """Get multiple vCons by their UUIDs.

    First attempts to retrieve from Redis using efficient batch operation (mget),
    then falls back to configured storages for any vCons not found in Redis.
    If found in storage, they will be stored back in Redis with a configurable
    expiration time (VCON_REDIS_EXPIRY, default 1 hour).

    Args:
        vcon_uuids: List of UUIDs of the vCons to retrieve

    Returns:
        JSONResponse containing a list of found vCons
    """
    # Use mget for efficient batch retrieval from Redis
    keys = [f"vcon:{vcon_uuid}" for vcon_uuid in vcon_uuids]
    vcons = await redis_async.json().mget(keys=keys, path=".")

    results = []
    for vcon_uuid, vcon in zip(vcon_uuids, vcons):
        if not vcon:
            # Only sync from storage if not found in Redis (avoids redundant Redis check)
            vcon = await sync_vcon_from_storage(vcon_uuid)
        results.append(vcon)

    return JSONResponse(content=results, status_code=200)


@api_router.get(
    "/vcons/search",
    response_model=List[UUID],
    summary="Search vCons by metadata",
    description="Search for vCons using personal identifiers and metadata",
    tags=["vcon"],
)
async def search_vcons(
    tel: Optional[str] = Query(None, description="Phone number to search for"),
    mailto: Optional[str] = Query(None, description="Email address to search for"),
    name: Optional[str] = Query(None, description="Name of the party to search for"),
) -> List[str]:
    """Search for vCons using personal identifiers and metadata.

    At least one search parameter must be provided. If multiple parameters are provided,
    results will include only vCons that match all criteria (AND operation).

    Args:
        tel: Phone number to search for
        mailto: Email address to search for
        name: Name of party to search for

    Returns:
        List of matching vCon UUIDs

    Raises:
        HTTPException: If no search parameters are provided
    """
    if tel is None and mailto is None and name is None:
        raise HTTPException(status_code=400, detail="At least one search parameter must be provided")

    try:
        tel_keys = set()
        mailto_keys = set()
        name_keys = set()
        search_terms = 0

        if tel:
            search_terms += 1
            tel_key = f"tel:{tel}"
            uuids = await redis_async.smembers(tel_key)
            tel_keys.update(f"vcon:{uuid}" for uuid in uuids)

        if mailto:
            search_terms += 1
            mailto_key = f"mailto:{mailto}"
            uuids = await redis_async.smembers(mailto_key)
            mailto_keys.update(f"vcon:{uuid}" for uuid in uuids)

        if name:
            search_terms += 1
            name_key = f"name:{name}"
            uuids = await redis_async.smembers(name_key)
            name_keys.update(f"vcon:{uuid}" for uuid in uuids)

        if search_terms > 1:
            # Take intersection of all non-empty sets
            logger.debug(f"Search terms: tel={tel}, mailto={mailto}, name={name}")
            named_sets = [s for s in [name_keys, tel_keys, mailto_keys] if s]
            logger.debug(f"Named sets: {named_sets}")
            keys = set.intersection(*named_sets)
            logger.debug(f"Intersection result: {len(keys)} matches")
        else:
            # Single search term - use the one non-empty set
            keys = tel_keys | mailto_keys | name_keys
            
        if not keys:
            return []   

        # Strip vcon: prefix from keys
        return [key.split(":")[1] for key in keys]
    
    except Exception as e:
        logger.error("Error in search_vcons: %s", str(e))
        raise HTTPException(status_code=500, detail="An error occurred during the search")


@api_router.post(
    "/vcon",
    response_model=Vcon,
    status_code=201,
    summary="Create a new vCon",
    description="Store a new vCon in the system",
    tags=["vcon"],
)
async def post_vcon(
    inbound_vcon: Vcon,
    ingress_lists: Optional[List[str]] = Query(None, description="Optional list of ingress queues to add the vCon to")
) -> JSONResponse:
    """Store a new vCon in the system.

    Stores the vCon in Redis and indexes it for searching. The vCon is added to a sorted
    set for timestamp-based retrieval and indexed by party information for searching.
    Optionally adds the vCon UUID to specified ingress lists for immediate processing.

    Args:
        inbound_vcon: The vCon to store
        ingress_lists: Optional list of ingress queue names to add the vCon to

    Returns:
        JSONResponse containing the stored vCon data

    Raises:
        HTTPException: If there is an error storing the vCon
    """
    try:
        dict_vcon = inbound_vcon.model_dump()
        dict_vcon["uuid"] = str(inbound_vcon.uuid)
        key = f"vcon:{str(dict_vcon['uuid'])}"
        created_at = datetime.fromisoformat(str(dict_vcon["created_at"]))
        dict_vcon["created_at"] = created_at.isoformat()
        timestamp = int(created_at.timestamp())

        logger.debug(f"Storing vCon {inbound_vcon.uuid} ({len(dict_vcon)} bytes)")
        await redis_async.json().set(key, "$", dict_vcon)
        
        logger.debug(f"Adding vCon {inbound_vcon.uuid} to sorted set")
        await add_vcon_to_set(key, timestamp)

        logger.debug(f"Indexing vCon {inbound_vcon.uuid}")
        await index_vcon(inbound_vcon.uuid)

        # Add to ingress lists if specified
        if ingress_lists:
            for ingress_list in ingress_lists:
                logger.debug(f"Adding vCon {inbound_vcon.uuid} to ingress list {ingress_list}")
                await redis_async.rpush(ingress_list, str(inbound_vcon.uuid))

        return JSONResponse(content=dict_vcon, status_code=201)

    except Exception as e:
        logger.error(f"Error storing vCon: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to store vCon")


@external_router.post(
    "/vcon/external-ingress",
    status_code=204,
    summary="Submit external vCon from 3rd party systems",
    description=(
        "Endpoint for external partners and 3rd party systems to submit vCons "
        "with limited API access. Requires ingress-specific authentication for "
        "secure isolation."
    ),
    tags=["external"],
)
async def external_ingress_vcon(
    request: Request,
    inbound_vcon: Vcon,
    ingress_list: str = Query(
        ..., description="Name of the ingress list to add the vCon to"
    ),
) -> None:
    """Submit external vCons from 3rd party systems with limited API access.

    This endpoint is specifically designed for external partners and 3rd party systems
    to submit vCons to designated ingress queues. Each API key is scoped to specific
    ingress lists, providing secure isolation and preventing access to other system
    resources or ingress queues.

    Security Model:
    - Each API key grants access only to predefined ingress list(s)
    - No access to other API endpoints or system resources
    - API keys are configured per ingress list in CONSERVER_CONFIG_FILE under 'ingress_auth'
    - Multiple API keys can be configured for the same ingress list

    The submitted vCon is stored, indexed, and automatically queued for processing
    in the specified ingress list.

    Args:
        inbound_vcon: The vCon record to submit
        ingress_list: Target ingress queue name (must match configured access)

    Returns:
        None: HTTP 204 No Content on successful submission

    Raises:
        HTTPException:
            - 403: Invalid API key or unauthorized ingress list access
            - 500: Storage or processing error

    Example:
        POST /vcon/external-ingress?ingress_list=partner_data
        Headers: x-conserver-api-token: partner-specific-key
        Body: {vCon JSON data}
    """
    # Extract API key from request headers and validate for this specific ingress list
    api_key = request.headers.get(CONSERVER_HEADER_NAME)
    validate_ingress_api_key(ingress_list, api_key)

    try:
        dict_vcon = inbound_vcon.model_dump()
        dict_vcon["uuid"] = str(inbound_vcon.uuid)
        key = f"vcon:{str(dict_vcon['uuid'])}"
        created_at = datetime.fromisoformat(str(dict_vcon["created_at"]))
        dict_vcon["created_at"] = created_at.isoformat()
        timestamp = int(created_at.timestamp())

        logger.debug(
            f"Storing vCon {inbound_vcon.uuid} ({len(dict_vcon)} bytes) via external ingress"
        )
        await redis_async.json().set(key, "$", dict_vcon)

        logger.debug(f"Adding vCon {inbound_vcon.uuid} to sorted set")
        await add_vcon_to_set(key, timestamp)

        logger.debug(f"Indexing vCon {inbound_vcon.uuid}")
        await index_vcon(inbound_vcon.uuid)

        # Always add to the specified ingress list (required for this endpoint)
        logger.debug(f"Adding vCon {inbound_vcon.uuid} to ingress list {ingress_list}")
        await redis_async.rpush(ingress_list, str(inbound_vcon.uuid))

        logger.info(
            f"Successfully stored vCon {inbound_vcon.uuid} and added to ingress list {ingress_list}"
        )

        return None

    except Exception as e:
        logger.error(
            "Error storing vCon via external ingress", exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to store vCon") from e


@api_router.delete(
    "/vcon/{vcon_uuid}",
    status_code=204,
    summary="Delete a vCon",
    description="Remove a vCon from the system",
    tags=["vcon"],
)
async def delete_vcon(vcon_uuid: UUID) -> None:
    """Delete a vCon from the system.

    This function deletes the vCon from Redis and all configured storage backends.
    It will attempt to delete from all storages even if some fail, ensuring
    maximum cleanup of the vCon data.

    Args:
        vcon_uuid: UUID of the vCon to delete

    Raises:
        HTTPException: If there is an error deleting the vCon
    """
    errors = []
    
    # Delete from Redis
    try:
        await redis_async.json().delete(f"vcon:{str(vcon_uuid)}")
        logger.info(f"Successfully deleted vCon {vcon_uuid} from Redis")
    except Exception as e:
        logger.warning(f"Failed to delete vCon {vcon_uuid} from Redis: {e}")
        errors.append(f"Redis deletion failed: {e}")
    
    # Delete from all configured storage backends
    for storage_name in Configuration.get_storages():
        try:
            delete_result = Storage(storage_name=storage_name).delete(str(vcon_uuid))
            if not delete_result:
                logger.warning(
                    f"Delete operation for vCon {vcon_uuid} in storage {storage_name} "
                    f"did not succeed (returned {delete_result})."
                )
            else:
                logger.info(f"Successfully deleted vCon {vcon_uuid} from storage: {storage_name}")
        except Exception as e:
            logger.warning(f"Failed to delete vCon {vcon_uuid} from storage {storage_name}: {e}")
            errors.append(f"Storage {storage_name} deletion failed: {e}")
            # Continue with other storages even if one fails
    
    # Log completion - always return 200 for delete operations
    if errors:
        logger.warning(f"vCon {vcon_uuid} deletion completed with some failures: {'; '.join(errors)}")
    else:
        logger.info(f"vCon {vcon_uuid} deletion completed")


# Ingress and egress endpoints for vCon IDs
# Create an endpoint to push vcon IDs to one or more redis lists
@api_router.post(
    "/vcon/ingress",
    status_code=204,
    summary="Add vCons to a chain",
    description="Insert vCon UUIDs into a processing chain",
    tags=["chain"],
)
async def post_vcon_ingress(
    vcon_uuids: List[str],
    ingress_list: str = Query(..., description="Name of ingress list to add to")
) -> None:
    """Add vCon UUIDs to a processing chain's ingress list.

    Before adding vCon UUIDs to the ingress list, ensures each vCon exists in Redis
    by syncing from storage backends if necessary. Non-existent vCons are logged
    as warnings and skipped, maintaining the original behavior of not throwing
    exceptions for missing vCons.

    Args:
        vcon_uuids: List of vCon UUIDs to add
        ingress_list: Name of the Redis list to add the UUIDs to

    Raises:
        HTTPException: Only for Redis operation failures, not for missing vCons
    """
    try:
        for vcon_id in vcon_uuids:
            # Parse UUID and handle invalid format gracefully
            try:
                vcon_uuid = UUID(vcon_id)
            except ValueError:
                logger.warning(f"Invalid UUID format for vCon ID '{vcon_id}', skipping ingress list addition")
                continue
            
            # Ensure the vCon exists in Redis before adding to ingress list
            vcon = await ensure_vcon_in_redis(vcon_uuid)
            
            if not vcon:
                logger.warning(f"vCon {vcon_id} not found in any storage, skipping ingress list addition")
                continue
                
            await redis_async.rpush(ingress_list, vcon_id)
            logger.debug(f"Added vCon {vcon_id} to ingress list {ingress_list}")
                
    except Exception as e:
        logger.error(f"Error adding to ingress list: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add to ingress list")


@api_router.get(
    "/vcon/count",
    status_code=200,
    summary="Count vCons in chain",
    description="Count the number of vCons in a chain's output",
    tags=["chain"],
)
async def get_vcon_count(
    egress_list: str = Query(..., description="Name of egress list to count")
) -> JSONResponse:
    """Count the number of vCons in a chain's egress list.

    Args:
        egress_list: Name of the Redis list to count

    Returns:
        JSONResponse containing the count

    Raises:
        HTTPException: If there is an error accessing the list
    """
    try:
        count = await redis_async.llen(egress_list)
        return JSONResponse(content=count)
    except Exception as e:
        logger.error(f"Error counting egress list: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to count egress list")


@api_router.get(
    "/config",
    status_code=200,
    summary="Get system config",
    description="Get the current system configuration",
    tags=["config"],
)
async def get_config() -> JSONResponse:
    """Get the current system configuration.

    Reads and returns the configuration from the file specified in CONSERVER_CONFIG_FILE.

    Returns:
        JSONResponse containing the configuration

    Raises:
        HTTPException: If there is an error reading the config file
    """
    try:
        with open(os.getenv("CONSERVER_CONFIG_FILE"), "r") as f:
            config = yaml.safe_load(f)
        return JSONResponse(content=config)
    except Exception as e:
        logger.error(f"Error reading config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to read configuration")


@api_router.post(
    "/config",
    status_code=204,
    summary="Update system config",
    description="Update the system configuration",
    tags=["config"],
)
async def post_config(config: Dict) -> None:
    """Update the system configuration.

    Writes the provided configuration to the file specified in CONSERVER_CONFIG_FILE.

    Args:
        config: New configuration to store

    Raises:
        HTTPException: If there is an error writing the config file
    """
    try:
        with open(os.getenv("CONSERVER_CONFIG_FILE"), "w") as f:
            yaml.dump(config, f)
    except Exception as e:
        logger.error(f"Error writing config: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")


@api_router.post(
    "/dlq/reprocess",
    status_code=200,
    summary="Reprocess DLQ",
    description="Move items from dead letter queue back to ingress",
    tags=["dlq"],
)
async def post_dlq_reprocess(
    ingress_list: str = Query(..., description="Name of ingress list to reprocess to")
) -> JSONResponse:
    """Move items from a dead letter queue back to the ingress list.

    Args:
        ingress_list: Name of the ingress list to move items to

    Returns:
        JSONResponse containing count of items moved

    Raises:
        HTTPException: If there is an error reprocessing the DLQ
    """
    try:
        dlq_name = get_ingress_list_dlq_name(ingress_list)
        counter = 0
        while item := await redis_async.rpop(dlq_name):
            await redis_async.rpush(ingress_list, item)
            counter += 1
        return JSONResponse(content=counter)
    except Exception as e:
        logger.error(f"Error reprocessing DLQ: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reprocess DLQ")


@api_router.get(
    "/dlq",
    status_code=200,
    summary="Get DLQ contents",
    description="Get list of vCons in dead letter queue",
    tags=["dlq"],
)
async def get_dlq_vcons(
    ingress_list: str = Query(..., description="Name of ingress list to get DLQ for")
) -> JSONResponse:
    """Get all vCons from a dead letter queue.

    Args:
        ingress_list: Name of the ingress list whose DLQ to read

    Returns:
        JSONResponse containing list of vCons in the DLQ

    Raises:
        HTTPException: If there is an error reading the DLQ
    """
    try:
        dlq_name = get_ingress_list_dlq_name(ingress_list)
        vcons = await redis_async.lrange(dlq_name, 0, -1)
        return JSONResponse(content=vcons)
    except Exception as e:
        logger.error(f"Error reading DLQ: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to read DLQ")


async def index_vcon(uuid: UUID) -> None:
    """Index a vCon for searching.

    Adds the vCon to the sorted set and indexes it by party information
    (tel, mailto, name) for searching. All indexed keys will expire after
    VCON_INDEX_EXPIRY seconds.

    Args:
        uuid: UUID of the vCon to index
    """
    key = f"vcon:{uuid}"
    vcon = await redis_async.json().get(key)
    created_at = datetime.fromisoformat(vcon["created_at"])
    timestamp = int(created_at.timestamp())
    vcon_uuid = vcon["uuid"]
    await add_vcon_to_set(key, timestamp)

    # Index by party information with expiration
    for party in vcon["parties"]:
        if party.get("tel"):
            tel_key = f"tel:{party['tel']}"
            await redis_async.sadd(tel_key, vcon_uuid)
            await redis_async.expire(tel_key, VCON_INDEX_EXPIRY)
        if party.get("mailto"):
            mailto_key = f"mailto:{party['mailto']}"
            await redis_async.sadd(mailto_key, vcon_uuid)
            await redis_async.expire(mailto_key, VCON_INDEX_EXPIRY)
        if party.get("name"):
            name_key = f"name:{party['name']}"
            await redis_async.sadd(name_key, vcon_uuid)
            await redis_async.expire(name_key, VCON_INDEX_EXPIRY)


@api_router.get(
    "/index_vcons",
    status_code=200,
    summary="Rebuild search index",
    description="Rebuild the vCon search index",
    tags=["config"],
)
async def index_vcons() -> JSONResponse:
    """Rebuild the vCon search index.

    Iterates through all vCons and rebuilds their search indices.

    Returns:
        JSONResponse containing count of vCons indexed

    Raises:
        HTTPException: If there is an error rebuilding the index
    """
    try:
        vcon_keys = await redis_async.keys("vcon:*")
        for key in vcon_keys:
            uuid = key.split(":")[1]
            await index_vcon(uuid)
        return JSONResponse(content=len(vcon_keys))
    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)

app.include_router(
    api_router,
    dependencies=[Security(get_api_key, scopes=[])]
)

# Include external router without main API authentication
app.include_router(external_router)
