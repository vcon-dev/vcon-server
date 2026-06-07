import json
from datetime import datetime
from typing import Any, Optional
from config import Configuration
from lib.logging_utils import init_logger
from lib.metrics import increment_counter
from lib.vcon_compat import normalize_legacy_fields
from redis.commands.json.path import Path
from redis_mgr import redis
from settings import (
    VCON_REDIS_EXPIRY,
    VCON_SORTED_SET_NAME,
    VCON_STORAGE_FALLBACK_ENABLED,
)
from storage.base import Storage
import vcon

logger = init_logger(__name__)


class VconRedis:
    """vCon access layer backed by Redis with optional storage fallback.

    Reads go through Redis first (hot cache). On a miss, ``get_vcon`` /
    ``get_vcon_dict`` fall back to the configured storage backends (see
    ``Configuration.get_storages()``) and re-cache the first hit back into
    Redis with TTL ``VCON_REDIS_EXPIRY``. The fallback is on by default and
    can be disabled with ``VCON_STORAGE_FALLBACK_ENABLED=false``.

    Writes go to Redis only; persistence to the storage backends is the
    responsibility of the storage chain (e.g. via the ``Storage`` link).

    Attributes:
        DEFAULT_TTL: Default TTL in seconds from VCON_REDIS_EXPIRY setting (3600s).
    """
    
    DEFAULT_TTL = VCON_REDIS_EXPIRY

    @staticmethod
    def _stringify_json_body(entry: Any) -> None:
        """Force ``body`` to be a string + correct ``encoding`` per speckit.

        The speckit non-negotiable: analysis/attachment bodies are
        strings. JSON content pairs ``body: json.dumps(...)`` with
        ``encoding: "json"``. vcon-lib's ``add_analysis`` currently
        emits dict/list bodies with ``encoding: "none"``, which we
        normalize on the way out so storage is spec-correct.
        """
        if not isinstance(entry, dict):
            return
        body = entry.get("body")
        if isinstance(body, (dict, list)):
            entry["body"] = json.dumps(body)
            entry["encoding"] = "json"

    @classmethod
    def _enforce_spec_on_write(cls, vcon_dict: dict) -> dict:
        """Ensure a vCon dict is spec-compliant before persistence.

        vcon-lib 0.9.2 produces spec-correct output from ``build_new()``
        but a ``Vcon(legacy_dict)`` round-trip can still surface empty
        ``group``/``redacted`` defaults or a missing top-level syntax
        param. Normalize defensively here so storage is always clean —
        including legacy field renames (e.g. attachment ``type`` →
        ``purpose``, top-level ``appended`` → ``amended``,
        ``must_support`` → ``critical``) that mirror what
        :func:`normalize_legacy_fields` applies on the read path.
        """
        # Rename legacy field names before the rest of the enforcement
        # so subsequent loops operate on spec-named entries.
        normalize_legacy_fields(vcon_dict)
        # draft-ietf-vcon-vcon-core-02 §4.1.1 — syntax param. The renames above
        # bring field names up to the current spec, so stamp the matching
        # version unconditionally. A missing value, or a stale legacy value
        # (e.g. "0.0.1" from a legacy producer or an egress-converted storage
        # payload loaded back on a Redis miss), would otherwise misdescribe the
        # now-canonical data.
        vcon_dict["vcon"] = "0.4.0"
        # speckit: ``group`` is reserved and must not be emitted empty.
        if vcon_dict.get("group") == []:
            vcon_dict.pop("group", None)
        # speckit: empty ``redacted: {}`` should be omitted.
        if vcon_dict.get("redacted") == {}:
            vcon_dict.pop("redacted", None)
        # speckit: analysis/attachment bodies are strings.
        for entry in vcon_dict.get("analysis", []) or []:
            cls._stringify_json_body(entry)
        for entry in vcon_dict.get("attachments", []) or []:
            cls._stringify_json_body(entry)
        return vcon_dict

    def store_vcon(self, vCon: vcon.Vcon, ttl: Optional[int] = None) -> None:
        """Stores the vcon into redis with optional TTL.

        Args:
            vCon (vcon.Vcon): The vCon to store in redis.
            ttl (Optional[int]): Time-to-live in seconds. If None, no expiry is set.
                Use DEFAULT_TTL for the configured default expiry.
        """
        key = f"vcon:{vCon.uuid}"
        cleanvCon = self._enforce_spec_on_write(vCon.to_dict())
        redis.json().set(key, Path.root_path(), cleanvCon)
        if ttl is not None:
            redis.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vCon.uuid}")

    @staticmethod
    def _load_from_storage(vcon_id: str) -> Optional[dict]:
        """Try each configured storage backend in turn; return the first hit.

        Returns None if the fallback is disabled by setting, no storages are
        configured, or none of them have the vCon. Per-backend errors are
        logged but do not abort the loop — a later backend may succeed.
        """
        if not VCON_STORAGE_FALLBACK_ENABLED:
            return None
        storages = Configuration.get_storages()
        if not storages:
            return None
        for storage_name in storages:
            try:
                vcon_dict = Storage(storage_name=storage_name).get(vcon_id)
            except Exception as e:
                logger.warning(
                    "Storage fallback %s raised while loading vCon %s: %s",
                    storage_name, vcon_id, e,
                )
                continue
            if vcon_dict:
                logger.info(
                    "vCon %s missed Redis but recovered from storage %s",
                    vcon_id, storage_name,
                )
                return vcon_dict
        return None

    def _cache_back_to_redis(self, vcon_id: str, vcon_dict: dict) -> None:
        """Re-cache a storage-loaded vCon into Redis with the standard TTL and
        re-add it to the sorted set so subsequent listings see it.

        Reuses ``store_vcon_dict`` for the set+expire combo (which also runs
        the spec-enforcement pass), then mirrors ``api.api.add_vcon_to_set``
        synchronously. Any error is swallowed — the caller still gets the
        vCon back.
        """
        try:
            self.store_vcon_dict(vcon_dict, ttl=VCON_REDIS_EXPIRY)
        except Exception as e:
            logger.warning("Failed to re-cache vCon %s into Redis: %s", vcon_id, e)
            return
        created_at = vcon_dict.get("created_at")
        if not created_at:
            return
        try:
            timestamp = int(datetime.fromisoformat(str(created_at)).timestamp())
            redis.zadd(VCON_SORTED_SET_NAME, {vcon_id: timestamp})
        except (ValueError, TypeError) as e:
            logger.debug(
                "Skipping sorted-set add for vCon %s (created_at=%r): %s",
                vcon_id, created_at, e,
            )

    def get_vcon(self, vcon_id: str) -> Optional[vcon.Vcon]:
        """Retrieve a vCon by id, falling back to storage on a Redis miss.

        Thin wrapper around :meth:`get_vcon_dict` that wraps the result in a
        ``vcon.Vcon`` object. See :meth:`get_vcon_dict` for lookup semantics.

        Returns:
            The vCon if found in Redis or any storage, otherwise ``None``.
            ``None`` is the contract for "halt the chain" in conserver links.
        """
        vcon_dict = self.get_vcon_dict(vcon_id)
        if vcon_dict is None:
            return None
        return vcon.Vcon(vcon_dict)

    def store_vcon_dict(self, vcon_dict: dict, ttl: Optional[int] = None) -> None:
        """Stores a vcon dictionary into redis with optional TTL.
        
        Args:
            vcon_dict (dict): The vCon as a dictionary to store.
            ttl (Optional[int]): Time-to-live in seconds. If None, no expiry is set.
                Use DEFAULT_TTL for the configured default expiry.
        """
        key = f"vcon:{vcon_dict['uuid']}"
        self._enforce_spec_on_write(vcon_dict)
        redis.json().set(key, Path.root_path(), vcon_dict)
        if ttl is not None:
            redis.expire(key, ttl)
            logger.debug(f"Set TTL of {ttl}s on vCon {vcon_dict['uuid']}")

    def get_vcon_dict(self, vcon_id: str) -> Optional[dict]:
        """Retrieve a vCon dict by id, falling back to storage on a Redis miss.

        Lookup order:
          1. Redis (hot cache) — fast path.
          2. Configured storage backends, in iteration order; on first hit
             the vCon is re-cached into Redis with ``VCON_REDIS_EXPIRY``.

        Legacy field names from older writers are normalized so callers
        always see spec-compliant data.

        Args:
            vcon_id: The vCon UUID.

        Returns:
            The vCon as a dictionary if found, otherwise ``None``.
        """
        vcon_dict = redis.json().get(
            f"vcon:{vcon_id}", Path.root_path()
        )
        if not vcon_dict:
            increment_counter("conserver.lib.vcon_redis.get_vcon_redis_miss")
            vcon_dict = self._load_from_storage(vcon_id)
            if not vcon_dict:
                increment_counter("conserver.lib.vcon_redis.get_vcon_not_found")
                return None
            increment_counter("conserver.lib.vcon_redis.get_vcon_storage_hit")
            self._cache_back_to_redis(vcon_id, vcon_dict)
        normalize_legacy_fields(vcon_dict)
        return vcon_dict

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
        cleanvCon = self._enforce_spec_on_write(vCon.to_dict())
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
        self._enforce_spec_on_write(vcon_dict)
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
