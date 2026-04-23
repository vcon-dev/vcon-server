"""Redis client factories and lifespan helpers (Refactor #7).

Previously: a module-level ``redis = Redis.from_url(...)`` global plus an
async ``get_async_client()`` that built a fresh client on every call. This
meant:

1. The async api (FastAPI) had no single-instance lifecycle — each caller
   risked holding stale clients bound to dead event loops.
2. Code throughout the repo reached directly for the sync global, with no
   path to inject a test double or a per-worker pool.

Now:

- :data:`redis` is still exposed (backward compat for ``from redis_mgr
  import redis`` and module-level test patches).
- :func:`get_client` returns that singleton sync client.
- :func:`get_async_client` returns a module-level singleton async client
  instead of creating a fresh one each call. Still ``async`` for api
  backward compatibility.
- :func:`close_async_client` closes the singleton — call on FastAPI
  shutdown.

VconRedis (lib/vcon_redis.py) now accepts an optional ``redis_client``
argument in its constructor so callers can inject a sync client for
testing or per-worker pooling, while existing ``VconRedis()`` call sites
keep working via the module global.
"""
from __future__ import annotations

from typing import Optional

from redis import Redis
from redis.asyncio import Redis as RedisAsync

from lib.logging_utils import init_logger
from settings import REDIS_URL

logger = init_logger(__name__)

# Singleton sync client. Kept as a module-level attribute for backward
# compatibility: existing code does ``from redis_mgr import redis`` and tests
# do ``@patch('lib.vcon_redis.redis')``. Do not rebind at runtime.
redis: Redis = Redis.from_url(REDIS_URL, decode_responses=True)

# Singleton async client, created lazily on first call so it binds to the
# correct event loop.
_async_client: Optional[RedisAsync] = None


def get_client() -> Redis:
    """Return the singleton sync Redis client."""
    return redis


async def get_async_client() -> RedisAsync:
    """Return the singleton async Redis client (creating it on first call).

    Kept ``async`` for call-site backward compat (api/api.py::on_startup
    awaits this). The client itself is synchronous to construct; we keep
    the coroutine so callers don't change.
    """
    global _async_client
    if _async_client is None:
        _async_client = RedisAsync.from_url(REDIS_URL, decode_responses=True)
    return _async_client


async def close_async_client() -> None:
    """Close the singleton async Redis client if one was created."""
    global _async_client
    if _async_client is not None:
        try:
            await _async_client.aclose()
        except Exception:
            logger.warning("Error closing async redis client", exc_info=True)
        _async_client = None


# ── Small synchronous helpers kept for backward compatibility ─────────────

def set_key(key, value):
    result = redis.json().set(key, "$", value)
    return result


def get_key(key):
    result = redis.json().get(key)
    return result


def delete_key(key):
    result = redis.delete(key)
    return result


def show_keys(pattern):
    result = redis.keys(pattern)
    return result
