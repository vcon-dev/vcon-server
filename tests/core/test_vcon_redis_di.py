"""Tests for VconRedis dependency injection (Refactor #7)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lib.vcon_redis import VconRedis
import redis_mgr


@pytest.fixture(autouse=True)
def _reset_async_singleton():
    """Make sure each test sees a clean async-client singleton."""
    redis_mgr._async_client = None
    yield
    redis_mgr._async_client = None


def test_vcon_redis_uses_injected_client_when_provided():
    """A client passed to the constructor is used instead of the module global."""
    mock_client = MagicMock()
    mock_client.json.return_value.get.return_value = None
    vr = VconRedis(redis_client=mock_client)

    vr.get_vcon("missing")
    mock_client.json().get.assert_called_once()


def test_vcon_redis_falls_back_to_module_global_when_no_client():
    """No-arg construction uses the module-level redis attribute.

    This is the code path tests like test_vcon_redis_ttl.py rely on via
    ``@patch('lib.vcon_redis.redis')``.
    """
    with patch("lib.vcon_redis.redis") as mock_redis:
        mock_redis.json.return_value.get.return_value = None
        vr = VconRedis()
        vr.get_vcon("abc")
    mock_redis.json().get.assert_called_once()


@pytest.mark.asyncio
async def test_get_async_client_returns_same_singleton():
    """Subsequent calls should return the same instance (not create new clients)."""
    first = await redis_mgr.get_async_client()
    second = await redis_mgr.get_async_client()
    assert first is second


@pytest.mark.asyncio
async def test_close_async_client_resets_singleton():
    """After close, next get_async_client() creates a fresh singleton."""
    first = await redis_mgr.get_async_client()
    await redis_mgr.close_async_client()
    second = await redis_mgr.get_async_client()
    assert first is not second
