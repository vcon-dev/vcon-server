"""VconRedis: sync/async wrappers around Redis operations on vCon objects.

Refactor #7: the constructor now accepts an optional ``redis_client`` so
callers can inject a sync client (for testing or per-worker pooling). When
unspecified, each operation uses the module-level ``redis`` singleton — this
preserves the existing ``VconRedis()`` call pattern and keeps
``@patch('lib.vcon_redis.redis')`` working in the test suite.
"""
from typing import Optional

from redis.commands.json.path import Path

import vcon
from lib.logging_utils import init_logger
from lib.metrics import increment_counter
from redis_mgr import redis
from settings import VCON_REDIS_EXPIRY


logger = init_logger(__name__)


class VconRedis:
    """Encapsulate vcon redis operations with optional TTL support.

    Attributes:
        DEFAULT_TTL: Default TTL in seconds from VCON_REDIS_EXPIRY setting.

    Args:
        redis_client: Optional sync Redis client to use instead of the
            module-level singleton. Useful for testing (inject a mock) or
            for giving a worker its own client. When None, every method
            falls back to the module-level ``redis`` via :meth:`_client`.
    """

    DEFAULT_TTL = VCON_REDIS_EXPIRY

    def __init__(self, redis_client=None):
        self._redis = redis_client

    def _client(self):
        """Resolve the sync Redis client — injected, or module-level fallback.

        Looking up ``redis`` at call time (not at __init__) means tests that
        do ``@patch('lib.vcon_redis.redis')`` affect every VconRedis instance
        that was constructed without an explicit client, which is what every
        existing caller does.
        """
        return self._redis if self._redis is not None else redis

    def store_vcon(self, vCon: vcon.Vcon, ttl: Optional[int] = None) -> None:
        """Stores the vcon into redis with optional TTL."""
        key = f"vcon:{vCon.uuid}"
        cleanvCon = vCon.to_dict()
        client = self._client()
        client.json().set(key, Path.root_path(), cleanvCon)
        if ttl is not None:
            client.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vCon.uuid}")

    def get_vcon(self, vcon_id: str) -> Optional[vcon.Vcon]:
        """Retrieves the vcon from redis for given vcon_id."""
        vcon_dict = self._client().json().get(f"vcon:{vcon_id}", Path.root_path())
        if not vcon_dict:
            increment_counter("conserver.lib.vcon_redis.get_vcon_not_found")
            return None
        return vcon.Vcon(vcon_dict)

    def store_vcon_dict(self, vcon_dict: dict, ttl: Optional[int] = None) -> None:
        """Stores a vcon dictionary into redis with optional TTL."""
        key = f"vcon:{vcon_dict['uuid']}"
        client = self._client()
        client.json().set(key, Path.root_path(), vcon_dict)
        if ttl is not None:
            client.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vcon_dict['uuid']}")

    def get_vcon_dict(self, vcon_id: str) -> Optional[dict]:
        """Retrieves a vcon dictionary from redis."""
        return self._client().json().get(f"vcon:{vcon_id}", Path.root_path())

    def set_expiry(self, vcon_id: str, ttl: int) -> bool:
        """Sets or updates the TTL on an existing vCon."""
        key = f"vcon:{vcon_id}"
        result = self._client().expire(key, ttl)
        if result:
            logger.debug(f"Updated TTL to {ttl}s on vCon {vcon_id}")
        return bool(result)

    def get_ttl(self, vcon_id: str) -> int:
        """Gets the remaining TTL on a vCon."""
        return self._client().ttl(f"vcon:{vcon_id}")

    def remove_expiry(self, vcon_id: str) -> bool:
        """Removes the TTL from a vCon, making it persistent."""
        key = f"vcon:{vcon_id}"
        result = self._client().persist(key)
        if result:
            logger.debug(f"Removed TTL from vCon {vcon_id}")
        return bool(result)

    async def store_vcon_async(
        self,
        redis_async,
        vCon: vcon.Vcon,
        ttl: Optional[int] = None,
    ) -> None:
        """Asynchronously stores the vcon into redis with optional TTL."""
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
        ttl: Optional[int] = None,
    ) -> None:
        """Asynchronously stores a vcon dictionary into redis with optional TTL."""
        key = f"vcon:{vcon_dict['uuid']}"
        await redis_async.json().set(key, "$", vcon_dict)
        if ttl is not None:
            await redis_async.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vcon_dict['uuid']}")

    async def set_expiry_async(self, redis_async, vcon_id: str, ttl: int) -> bool:
        """Asynchronously sets or updates the TTL on an existing vCon."""
        key = f"vcon:{vcon_id}"
        result = await redis_async.expire(key, ttl)
        if result:
            logger.debug(f"Updated TTL to {ttl}s on vCon {vcon_id}")
        return bool(result)

    async def get_ttl_async(self, redis_async, vcon_id: str) -> int:
        """Asynchronously gets the remaining TTL on a vCon."""
        return await redis_async.ttl(f"vcon:{vcon_id}")
