""" 
Package to manage Redis connection pool and clients

Setup of redis clients cannot be done globally in each module as it will 
bind to a asyncio loop which may be started and stopped.  In which case
redis will be bound to an old loop which will no longer work

The redis connection pool must be shutdown and restarted when FASTApi does.
"""

import json

from lib.logging_utils import init_logger
from redis import Redis
from redis.asyncio import Redis as RedisAsync
# from redis.asyncio.connection import ConnectionPool
# from redis.asyncio.client import Redis
from settings import REDIS_URL

logger = init_logger(__name__)

redis = Redis.from_url(REDIS_URL, decode_responses=True)


def get_client():
    return redis


def set_key(key, value):
    result = json_set(redis, key, value)
    return result


def get_key(key):
    result = json_get(redis, key)
    return result


def delete_key(key):
    result = redis.delete(key)
    return result


def show_keys(pattern):
    result = redis.keys(pattern)
    return result


async def get_async_client():
    return await RedisAsync.from_url(REDIS_URL, decode_responses=True)


def json_set(client, key, value, ttl=None):
    """Store a whole document, retaining an existing expiry unless overridden."""
    payload = json.dumps(value)
    if ttl is None:
        return client.set(key, payload, keepttl=True)
    if ttl > 0:
        return client.set(key, payload, ex=ttl)
    # EX rejects nonpositive values; preserve the previous SET + EXPIRE contract.
    with client.pipeline(transaction=True) as pipe:
        return pipe.set(key, payload).expire(key, ttl).execute()[0]


def json_get(client, key):
    raw = client.get(key)
    return json.loads(raw) if raw is not None else None


async def json_set_async(client, key, value, ttl=None):
    """Async counterpart of json_set using the caller's client/event loop."""
    payload = json.dumps(value)
    if ttl is None:
        return await client.set(key, payload, keepttl=True)
    if ttl > 0:
        return await client.set(key, payload, ex=ttl)
    async with client.pipeline(transaction=True) as pipe:
        return (await pipe.set(key, payload).expire(key, ttl).execute())[0]


async def json_get_async(client, key):
    raw = await client.get(key)
    return json.loads(raw) if raw is not None else None


async def json_mget_async(client, keys):
    if not keys:
        return []
    raws = await client.mget(keys)
    return [json.loads(raw) if raw is not None else None for raw in raws]
