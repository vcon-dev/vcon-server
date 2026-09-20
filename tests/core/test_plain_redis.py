"""Storage contract against a disposable Redis without RedisJSON.

Start a private Unix-socket server, never use the configured REDIS_URL.
"""
import json
import shutil
import subprocess
import time
import tempfile
from uuid import uuid4

import pytest
from redis import Redis
from redis.exceptions import ConnectionError
from redis.asyncio import Redis as AsyncRedis

import redis_mgr
from lib import vcon_redis


@pytest.fixture(scope="module")
def plain_redis(tmp_path_factory):
    executable = shutil.which("redis-server")
    if executable is None:
        pytest.fail("redis-server is required for the plain Redis contract tests")
    directory = tempfile.TemporaryDirectory(prefix="redis-", dir="/tmp")
    socket = directory.name + "/redis.sock"
    process = subprocess.Popen(
        [executable, "--port", "0", "--unixsocket", socket,
         "--save", "", "--appendonly", "no"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    client = Redis(unix_socket_path=socket, decode_responses=True)
    try:
        for _ in range(100):
            try:
                client.ping()
                break
            except ConnectionError:
                time.sleep(0.02)
            except Exception:
                if process.poll() is not None:
                    pytest.fail(process.stderr.read().decode())
                time.sleep(0.02)
        else:
            pytest.fail("Private Redis did not start")
        assert not any(m["name"].lower() in {"rejson", "json"} for m in client.module_list())
        yield client, socket
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
        process.stderr.close()
        directory.cleanup()


@pytest.fixture
def client(plain_redis, monkeypatch):
    client, _ = plain_redis
    monkeypatch.setattr(redis_mgr, "redis", client)
    monkeypatch.setattr(vcon_redis, "redis", client)
    return client


def test_manager_roundtrip_and_delete(client):
    key = f"test:{uuid4()}"
    value = {"unicode": "café", "nested": [None, False, {"body": '{"a": 1}'}]}
    assert redis_mgr.get_key(key) is None
    assert redis_mgr.set_key(key, value)
    assert redis_mgr.get_key(key) == value
    assert client.type(key) == "string"
    assert redis_mgr.delete_key(key) == 1
    assert redis_mgr.delete_key(key) == 0


@pytest.mark.parametrize("ttl", [None, 60, 0, -1])
def test_vcon_ttl_on_overwrite(client, ttl):
    identifier = str(uuid4())
    key = f"vcon:{identifier}"
    value = {"uuid": identifier, "vcon": "0.4.0", "attachments": []}
    store = vcon_redis.VconRedis()
    store.store_vcon_dict(value, ttl=120)
    store.store_vcon_dict(value, ttl=ttl)
    if ttl is not None and ttl <= 0:
        assert client.exists(key) == 0
    else:
        remaining = client.ttl(key)
        assert 0 < remaining <= (120 if ttl is None else ttl)
        assert json.loads(client.get(key))["uuid"] == identifier


@pytest.mark.asyncio
async def test_async_store_preserves_expiry(client, plain_redis):
    _, socket = plain_redis
    async_client = AsyncRedis(unix_socket_path=socket, decode_responses=True)
    identifier = str(uuid4())
    key = f"vcon:{identifier}"
    value = {"uuid": identifier, "vcon": "0.4.0", "attachments": []}
    try:
        store = vcon_redis.VconRedis()
        await store.store_vcon_dict_async(async_client, value, ttl=120)
        await store.store_vcon_dict_async(async_client, value)
        assert 0 < client.ttl(key) <= 120
        assert json.loads(client.get(key))["uuid"] == identifier
    finally:
        await async_client.close()


def test_new_key_is_persistent_and_bad_json_is_an_error(client):
    key = f"test:{uuid4()}"
    redis_mgr.set_key(key, {"data": []})
    assert client.ttl(key) == -1
    client.set(key, "invalid JSON")
    with pytest.raises(json.JSONDecodeError):
        redis_mgr.get_key(key)


@pytest.mark.asyncio
async def test_async_batch_preserves_order_duplicates_and_missing(client, plain_redis):
    _, socket = plain_redis
    async_client = AsyncRedis(unix_socket_path=socket, decode_responses=True)
    key = f"test:{uuid4()}"
    value = {"body": '{"text": "café"}'}
    try:
        await redis_mgr.json_set_async(async_client, key, value)
        assert await redis_mgr.json_get_async(async_client, key) == value
        assert await redis_mgr.json_get_async(async_client, key + ":missing") is None
        assert await redis_mgr.json_mget_async(async_client, [key, key + ":missing", key]) == [value, None, value]
        assert await redis_mgr.json_mget_async(async_client, []) == []
        client.set(key, "invalid JSON")
        with pytest.raises(json.JSONDecodeError):
            await redis_mgr.json_mget_async(async_client, [key])
    finally:
        await async_client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("ttl", [0, -1, 60])
async def test_async_explicit_ttl(client, plain_redis, ttl):
    _, socket = plain_redis
    async_client = AsyncRedis(unix_socket_path=socket, decode_responses=True)
    key = f"test:{uuid4()}"
    try:
        await redis_mgr.json_set_async(async_client, key, {}, ttl=ttl)
        if ttl <= 0:
            assert client.exists(key) == 0
        else:
            assert 0 < client.ttl(key) <= ttl
    finally:
        await async_client.close()
