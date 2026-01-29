from typing import Optional
from lib.logging_utils import init_logger
from redis.commands.json.path import Path
from redis_mgr import redis
from settings import VCON_REDIS_EXPIRY
import vcon

logger = init_logger(__name__)


class VconRedis:
    """Encapsulate vcon redis operations with optional TTL support.
    
    This class provides both synchronous and asynchronous methods for storing
    and retrieving vCon objects from Redis. TTL (Time-To-Live) can be set
    on stored vCons to enable automatic expiration.
    
    Attributes:
        DEFAULT_TTL: Default TTL in seconds from VCON_REDIS_EXPIRY setting (3600s).
    """
    
    DEFAULT_TTL = VCON_REDIS_EXPIRY

    def store_vcon(self, vCon: vcon.Vcon, ttl: Optional[int] = None) -> None:
        """Stores the vcon into redis with optional TTL.

        Args:
            vCon (vcon.Vcon): The vCon to store in redis.
            ttl (Optional[int]): Time-to-live in seconds. If None, no expiry is set.
                Use DEFAULT_TTL for the configured default expiry.
        """
        key = f"vcon:{vCon.uuid}"
        cleanvCon = vCon.to_dict()
        redis.json().set(key, Path.root_path(), cleanvCon)
        if ttl is not None:
            redis.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vCon.uuid}")

    def get_vcon(self, vcon_id: str) -> Optional[vcon.Vcon]:
        """Retrieves the vcon from redis for given vcon_id.

        Args:
            vcon_id (str): vcon id

        Returns:
            Optional[vcon.Vcon]: Returns vcon for given vcon id or None if vcon is not present.
        """
        vcon_dict = redis.json().get(
            f"vcon:{vcon_id}", Path.root_path()
        )
        if not vcon_dict:
            return None
        _vcon = vcon.Vcon(vcon_dict)
        return _vcon

    def store_vcon_dict(self, vcon_dict: dict, ttl: Optional[int] = None) -> None:
        """Stores a vcon dictionary into redis with optional TTL.
        
        Args:
            vcon_dict (dict): The vCon as a dictionary to store.
            ttl (Optional[int]): Time-to-live in seconds. If None, no expiry is set.
                Use DEFAULT_TTL for the configured default expiry.
        """
        key = f"vcon:{vcon_dict['uuid']}"
        redis.json().set(key, Path.root_path(), vcon_dict)
        if ttl is not None:
            redis.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vcon_dict['uuid']}")

    def get_vcon_dict(self, vcon_id: str) -> Optional[dict]:
        """Retrieves a vcon dictionary from redis.
        
        Args:
            vcon_id (str): The vCon UUID.
            
        Returns:
            Optional[dict]: The vCon as a dictionary, or None if not found.
        """
        return redis.json().get(
            f"vcon:{vcon_id}", Path.root_path()
        )

    def set_expiry(self, vcon_id: str, ttl: int) -> bool:
        """Sets or updates the TTL on an existing vCon.
        
        Args:
            vcon_id (str): The vCon UUID.
            ttl (int): Time-to-live in seconds.
            
        Returns:
            bool: True if the expiry was set, False if the key doesn't exist.
        """
        key = f"vcon:{vcon_id}"
        result = redis.expire(key, ttl)
        if result:
            logger.debug(f"Updated TTL to {ttl}s on vCon {vcon_id}")
        return bool(result)

    def get_ttl(self, vcon_id: str) -> int:
        """Gets the remaining TTL on a vCon.
        
        Args:
            vcon_id (str): The vCon UUID.
            
        Returns:
            int: Remaining TTL in seconds, -1 if no expiry is set,
                 -2 if the key doesn't exist.
        """
        key = f"vcon:{vcon_id}"
        return redis.ttl(key)

    def remove_expiry(self, vcon_id: str) -> bool:
        """Removes the TTL from a vCon, making it persistent.
        
        Args:
            vcon_id (str): The vCon UUID.
            
        Returns:
            bool: True if the expiry was removed, False if the key doesn't exist
                  or had no expiry.
        """
        key = f"vcon:{vcon_id}"
        result = redis.persist(key)
        if result:
            logger.debug(f"Removed TTL from vCon {vcon_id}")
        return bool(result)

    async def store_vcon_async(
        self, 
        redis_async, 
        vCon: vcon.Vcon, 
        ttl: Optional[int] = None
    ) -> None:
        """Asynchronously stores the vcon into redis with optional TTL.

        Args:
            redis_async: Async Redis client instance.
            vCon (vcon.Vcon): The vCon to store in redis.
            ttl (Optional[int]): Time-to-live in seconds. If None, no expiry is set.
                Use DEFAULT_TTL for the configured default expiry.
        """
        key = f"vcon:{vCon.uuid}"
        cleanvCon = vCon.to_dict()
        await redis_async.json().set(key, "$", cleanvCon)
        if ttl is not None:
            await redis_async.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vCon.uuid}")

    async def store_vcon_dict_async(
        self, 
        redis_async, 
        vcon_dict: dict, 
        ttl: Optional[int] = None
    ) -> None:
        """Asynchronously stores a vcon dictionary into redis with optional TTL.
        
        Args:
            redis_async: Async Redis client instance.
            vcon_dict (dict): The vCon as a dictionary to store.
            ttl (Optional[int]): Time-to-live in seconds. If None, no expiry is set.
                Use DEFAULT_TTL for the configured default expiry.
        """
        key = f"vcon:{vcon_dict['uuid']}"
        await redis_async.json().set(key, "$", vcon_dict)
        if ttl is not None:
            await redis_async.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vcon_dict['uuid']}")

    async def set_expiry_async(self, redis_async, vcon_id: str, ttl: int) -> bool:
        """Asynchronously sets or updates the TTL on an existing vCon.
        
        Args:
            redis_async: Async Redis client instance.
            vcon_id (str): The vCon UUID.
            ttl (int): Time-to-live in seconds.
            
        Returns:
            bool: True if the expiry was set, False if the key doesn't exist.
        """
        key = f"vcon:{vcon_id}"
        result = await redis_async.expire(key, ttl)
        if result:
            logger.debug(f"Updated TTL to {ttl}s on vCon {vcon_id}")
        return bool(result)

    async def get_ttl_async(self, redis_async, vcon_id: str) -> int:
        """Asynchronously gets the remaining TTL on a vCon.
        
        Args:
            redis_async: Async Redis client instance.
            vcon_id (str): The vCon UUID.
            
        Returns:
            int: Remaining TTL in seconds, -1 if no expiry is set,
                 -2 if the key doesn't exist.
        """
        key = f"vcon:{vcon_id}"
        return await redis_async.ttl(key)
