"""Utility functions for context propagation between API and conserver.

This module provides functions to store and retrieve context data associated
with vCon UUIDs when they are added to ingress lists. Context data is stored
separately from the ingress list to maintain backward compatibility while
enabling context propagation.
"""

import json
from typing import Dict, Optional, Any
from redis import Redis
from redis.asyncio import Redis as RedisAsync
from lib.logging_utils import init_logger
from settings import VCON_CONTEXT_EXPIRY

logger = init_logger(__name__)


def get_context_key(ingress_list: str, vcon_uuid: str) -> str:
    """Generate the Redis key for storing context data.
    
    Args:
        ingress_list: Name of the ingress list
        vcon_uuid: UUID of the vCon
        
    Returns:
        Redis key string in format: context:{ingress_list}:{vcon_uuid}
    """
    return f"context:{ingress_list}:{vcon_uuid}"


async def store_context_async(
    redis_client: RedisAsync,
    ingress_list: str,
    vcon_uuid: str,
    context: Dict[str, Any]
) -> None:
    """Store context data for a vCon UUID in an ingress list.
    
    Context data is stored as a list in Redis, allowing multiple context
    entries for the same vCon UUID (since it can be added multiple times).
    The list will expire after VCON_CONTEXT_EXPIRY seconds.
    
    Args:
        redis_client: Async Redis client
        ingress_list: Name of the ingress list
        vcon_uuid: UUID of the vCon
        context: Dictionary containing context data to store
    """
    if not context:
        logger.debug(f"No context data provided for vCon {vcon_uuid} in ingress list {ingress_list}")
        return
    
    try:
        key = get_context_key(ingress_list, vcon_uuid)
        context_json = json.dumps(context)
        await redis_client.rpush(key, context_json)
        # Set expiration on the list (will apply to all items)
        await redis_client.expire(key, VCON_CONTEXT_EXPIRY)
        logger.debug(
            f"Stored context for vCon {vcon_uuid} in ingress list {ingress_list}: {context}"
        )
    except Exception as e:
        logger.warning(
            f"Failed to store context for vCon {vcon_uuid} in ingress list {ingress_list}: {e}"
        )


def store_context_sync(
    redis_client: Redis,
    ingress_list: str,
    vcon_uuid: str,
    context: Dict[str, Any]
) -> None:
    """Store context data for a vCon UUID in an ingress list (synchronous version).
    
    Context data is stored as a list in Redis, allowing multiple context
    entries for the same vCon UUID (since it can be added multiple times).
    The list will expire after VCON_CONTEXT_EXPIRY seconds.
    
    Args:
        redis_client: Synchronous Redis client
        ingress_list: Name of the ingress list
        vcon_uuid: UUID of the vCon
        context: Dictionary containing context data to store
    """
    if not context:
        logger.debug(f"No context data provided for vCon {vcon_uuid} in ingress list {ingress_list}")
        return
    
    try:
        key = get_context_key(ingress_list, vcon_uuid)
        context_json = json.dumps(context)
        redis_client.rpush(key, context_json)
        # Set expiration on the list (will apply to all items)
        redis_client.expire(key, VCON_CONTEXT_EXPIRY)
        logger.debug(
            f"Stored context for vCon {vcon_uuid} in ingress list {ingress_list}: {context}"
        )
    except Exception as e:
        logger.warning(
            f"Failed to store context for vCon {vcon_uuid} in ingress list {ingress_list}: {e}"
        )


def retrieve_context(
    redis_client: Redis,
    ingress_list: str,
    vcon_uuid: str
) -> Optional[Dict[str, Any]]:
    """Retrieve the oldest context data for a vCon UUID from an ingress list.
    
    Since the same vCon UUID can be added multiple times, this function retrieves
    the oldest context entry (leftmost item in the list, which is the first
    one added) using FIFO queue behavior. The context entry is removed from
    the list after retrieval.
    
    Args:
        redis_client: Synchronous Redis client
        ingress_list: Name of the ingress list
        vcon_uuid: UUID of the vCon
        
    Returns:
        Dictionary containing context data, or None if no context is found
    """
    try:
        key = get_context_key(ingress_list, vcon_uuid)
        # Pop the leftmost (oldest) context entry for FIFO queue behavior
        context_json = redis_client.lpop(key)
        if not context_json:
            logger.debug(
                f"No context found for vCon {vcon_uuid} in ingress list {ingress_list}"
            )
            return None
        
        context = json.loads(context_json)
        logger.debug(
            f"Retrieved context for vCon {vcon_uuid} from ingress list {ingress_list}: {context}"
        )
        return context
    except json.JSONDecodeError as e:
        logger.warning(
            f"Failed to parse context JSON for vCon {vcon_uuid} in ingress list {ingress_list}: {e}"
        )
        return None
    except Exception as e:
        logger.warning(
            f"Failed to retrieve context for vCon {vcon_uuid} in ingress list {ingress_list}: {e}"
        )
        return None

