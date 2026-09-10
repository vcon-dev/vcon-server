"""GET /vcon must survive a sorted set holding both member shapes.

`add_vcon_to_set` had two kinds of caller: the ingress paths passed a
"vcon:<uuid>" key, while `sync_vcon_from_storage` passed a bare uuid. The
reader split on ":" and took index 1, so a single bare member raised
IndexError and 500'd the whole list endpoint.
"""

from unittest.mock import AsyncMock, MagicMock

import api
import pytest
from fastapi.testclient import TestClient
from settings import CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME

TEST_API_TOKEN = CONSERVER_API_TOKEN or "test-api-token"
UUID_A = "01a08cd3-f607-8b5d-9dd8-dd37220d739c"
UUID_B = "01a08cd0-88c9-87f9-9dd8-dd37220d739c"


@pytest.mark.asyncio
@pytest.mark.parametrize("passed", [UUID_A, f"vcon:{UUID_A}"])
async def test_add_vcon_to_set_normalizes_member(passed):
    """Either caller shape lands in the set as one prefixed member."""
    mock_redis = MagicMock()
    mock_redis.zadd = AsyncMock()
    api.redis_async = mock_redis
    try:
        await api.add_vcon_to_set(passed, 1789069096)
    finally:
        api.redis_async = None

    mock_redis.zadd.assert_awaited_once()
    _, members = mock_redis.zadd.await_args.args
    assert members == {f"vcon:{UUID_A}": 1789069096}


def test_list_tolerates_legacy_bare_members():
    """A set already poisoned with bare members still lists, not 500s."""
    mock_redis = MagicMock()
    # What the live conserver actually held: one of each shape.
    mock_redis.zrevrangebyscore = AsyncMock(return_value=[f"vcon:{UUID_A}", UUID_B])
    api.redis_async = mock_redis
    try:
        client = TestClient(api.app, headers={CONSERVER_HEADER_NAME: TEST_API_TOKEN})
        response = client.get("/vcon?page=1&size=5")
    finally:
        api.redis_async = None

    assert response.status_code == 200
    assert response.json() == [UUID_A, UUID_B]


def test_get_vcons_with_no_uuids_returns_empty():
    """No uuids is an empty result, not a TypeError on None."""
    client = TestClient(api.app, headers={CONSERVER_HEADER_NAME: TEST_API_TOKEN})
    response = client.get("/vcons")

    assert response.status_code == 200
    assert response.json() == []
