"""Tests for VconRedis TTL (Time-To-Live) functionality.

This module tests the TTL-related methods added to the VconRedis class,
including setting expiry on store, getting TTL, and updating expiry.
"""

import json
import os
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import vcon

from lib.vcon_redis import VconRedis


# Sample vCon data for testing - use absolute path relative to this file
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_VCON_PATH = os.path.join(_TEST_DIR, "..", "dataset", "1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json")


@pytest.fixture
def vcon_redis():
    """Create a VconRedis instance for testing."""
    return VconRedis()


@pytest.fixture
def sample_vcon_dict():
    """Load sample vCon dictionary from test dataset."""
    with open(SAMPLE_VCON_PATH) as f:
        return json.load(f)


@pytest.fixture
def sample_vcon_obj(sample_vcon_dict):
    """Create a vCon object from sample data."""
    return vcon.Vcon(sample_vcon_dict)


class TestVconRedisDefaultTTL:
    """Tests for the DEFAULT_TTL class attribute."""

    def test_default_ttl_is_set(self, vcon_redis):
        """Verify that DEFAULT_TTL is set from VCON_REDIS_EXPIRY setting."""
        # Default should be 3600 seconds (1 hour)
        assert VconRedis.DEFAULT_TTL == 3600


class TestStoreVconWithTTL:
    """Tests for store_vcon method with TTL parameter."""

    @patch('lib.vcon_redis.redis')
    def test_store_vcon_without_ttl(self, mock_redis, vcon_redis, sample_vcon_obj):
        """Verify store_vcon without TTL does not set expiry."""
        mock_json = MagicMock()
        mock_redis.json.return_value = mock_json

        vcon_redis.store_vcon(sample_vcon_obj)

        # Verify JSON was set
        mock_json.set.assert_called_once()
        # Verify expire was NOT called
        mock_redis.expire.assert_not_called()

    @patch('lib.vcon_redis.redis')
    def test_store_vcon_with_custom_ttl(self, mock_redis, vcon_redis, sample_vcon_obj):
        """Verify store_vcon with TTL sets the expiry."""
        mock_json = MagicMock()
        mock_redis.json.return_value = mock_json

        custom_ttl = 7200  # 2 hours
        vcon_redis.store_vcon(sample_vcon_obj, ttl=custom_ttl)

        # Verify JSON was set
        mock_json.set.assert_called_once()
        # Verify expire was called with correct TTL
        expected_key = f"vcon:{sample_vcon_obj.uuid}"
        mock_redis.expire.assert_called_once_with(expected_key, custom_ttl)

    @patch('lib.vcon_redis.redis')
    def test_store_vcon_with_default_ttl(self, mock_redis, vcon_redis, sample_vcon_obj):
        """Verify store_vcon with DEFAULT_TTL sets the correct expiry."""
        mock_json = MagicMock()
        mock_redis.json.return_value = mock_json

        vcon_redis.store_vcon(sample_vcon_obj, ttl=VconRedis.DEFAULT_TTL)

        expected_key = f"vcon:{sample_vcon_obj.uuid}"
        mock_redis.expire.assert_called_once_with(expected_key, 3600)


class TestStoreVconDictWithTTL:
    """Tests for store_vcon_dict method with TTL parameter."""

    @patch('lib.vcon_redis.redis')
    def test_store_vcon_dict_without_ttl(self, mock_redis, vcon_redis, sample_vcon_dict):
        """Verify store_vcon_dict without TTL does not set expiry."""
        mock_json = MagicMock()
        mock_redis.json.return_value = mock_json

        vcon_redis.store_vcon_dict(sample_vcon_dict)

        mock_json.set.assert_called_once()
        mock_redis.expire.assert_not_called()

    @patch('lib.vcon_redis.redis')
    def test_store_vcon_dict_with_ttl(self, mock_redis, vcon_redis, sample_vcon_dict):
        """Verify store_vcon_dict with TTL sets the expiry."""
        mock_json = MagicMock()
        mock_redis.json.return_value = mock_json

        custom_ttl = 1800  # 30 minutes
        vcon_redis.store_vcon_dict(sample_vcon_dict, ttl=custom_ttl)

        expected_key = f"vcon:{sample_vcon_dict['uuid']}"
        mock_redis.expire.assert_called_once_with(expected_key, custom_ttl)


class TestSetExpiry:
    """Tests for set_expiry method."""

    @patch('lib.vcon_redis.redis')
    def test_set_expiry_success(self, mock_redis, vcon_redis, sample_vcon_dict):
        """Verify set_expiry returns True when key exists."""
        mock_redis.expire.return_value = 1  # Redis returns 1 on success

        result = vcon_redis.set_expiry(sample_vcon_dict['uuid'], 3600)

        assert result is True
        expected_key = f"vcon:{sample_vcon_dict['uuid']}"
        mock_redis.expire.assert_called_once_with(expected_key, 3600)

    @patch('lib.vcon_redis.redis')
    def test_set_expiry_key_not_found(self, mock_redis, vcon_redis):
        """Verify set_expiry returns False when key doesn't exist."""
        mock_redis.expire.return_value = 0  # Redis returns 0 when key doesn't exist

        result = vcon_redis.set_expiry("nonexistent-uuid", 3600)

        assert result is False


class TestGetTTL:
    """Tests for get_ttl method."""

    @patch('lib.vcon_redis.redis')
    def test_get_ttl_with_expiry(self, mock_redis, vcon_redis, sample_vcon_dict):
        """Verify get_ttl returns remaining TTL when set."""
        mock_redis.ttl.return_value = 1800  # 30 minutes remaining

        result = vcon_redis.get_ttl(sample_vcon_dict['uuid'])

        assert result == 1800
        expected_key = f"vcon:{sample_vcon_dict['uuid']}"
        mock_redis.ttl.assert_called_once_with(expected_key)

    @patch('lib.vcon_redis.redis')
    def test_get_ttl_no_expiry(self, mock_redis, vcon_redis, sample_vcon_dict):
        """Verify get_ttl returns -1 when no expiry is set."""
        mock_redis.ttl.return_value = -1

        result = vcon_redis.get_ttl(sample_vcon_dict['uuid'])

        assert result == -1

    @patch('lib.vcon_redis.redis')
    def test_get_ttl_key_not_found(self, mock_redis, vcon_redis):
        """Verify get_ttl returns -2 when key doesn't exist."""
        mock_redis.ttl.return_value = -2

        result = vcon_redis.get_ttl("nonexistent-uuid")

        assert result == -2


class TestRemoveExpiry:
    """Tests for remove_expiry method."""

    @patch('lib.vcon_redis.redis')
    def test_remove_expiry_success(self, mock_redis, vcon_redis, sample_vcon_dict):
        """Verify remove_expiry returns True when expiry is removed."""
        mock_redis.persist.return_value = 1

        result = vcon_redis.remove_expiry(sample_vcon_dict['uuid'])

        assert result is True
        expected_key = f"vcon:{sample_vcon_dict['uuid']}"
        mock_redis.persist.assert_called_once_with(expected_key)

    @patch('lib.vcon_redis.redis')
    def test_remove_expiry_no_expiry(self, mock_redis, vcon_redis, sample_vcon_dict):
        """Verify remove_expiry returns False when no expiry was set."""
        mock_redis.persist.return_value = 0

        result = vcon_redis.remove_expiry(sample_vcon_dict['uuid'])

        assert result is False


class TestAsyncStoreVconWithTTL:
    """Tests for async store_vcon_async method."""

    @pytest.mark.asyncio
    async def test_store_vcon_async_without_ttl(self, vcon_redis, sample_vcon_obj):
        """Verify store_vcon_async without TTL does not set expiry."""
        mock_redis_async = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis_async.json.return_value = mock_json
        mock_redis_async.expire = AsyncMock()

        await vcon_redis.store_vcon_async(mock_redis_async, sample_vcon_obj)

        mock_json.set.assert_called_once()
        mock_redis_async.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_store_vcon_async_with_ttl(self, vcon_redis, sample_vcon_obj):
        """Verify store_vcon_async with TTL sets the expiry."""
        mock_redis_async = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis_async.json.return_value = mock_json
        mock_redis_async.expire = AsyncMock()

        custom_ttl = 7200
        await vcon_redis.store_vcon_async(mock_redis_async, sample_vcon_obj, ttl=custom_ttl)

        mock_json.set.assert_called_once()
        expected_key = f"vcon:{sample_vcon_obj.uuid}"
        mock_redis_async.expire.assert_called_once_with(expected_key, custom_ttl)


class TestAsyncStoreVconDictWithTTL:
    """Tests for async store_vcon_dict_async method."""

    @pytest.mark.asyncio
    async def test_store_vcon_dict_async_with_ttl(self, vcon_redis, sample_vcon_dict):
        """Verify store_vcon_dict_async with TTL sets the expiry."""
        mock_redis_async = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis_async.json.return_value = mock_json
        mock_redis_async.expire = AsyncMock()

        custom_ttl = 1800
        await vcon_redis.store_vcon_dict_async(mock_redis_async, sample_vcon_dict, ttl=custom_ttl)

        expected_key = f"vcon:{sample_vcon_dict['uuid']}"
        mock_redis_async.expire.assert_called_once_with(expected_key, custom_ttl)


class TestAsyncSetExpiry:
    """Tests for async set_expiry_async method."""

    @pytest.mark.asyncio
    async def test_set_expiry_async_success(self, vcon_redis, sample_vcon_dict):
        """Verify set_expiry_async returns True when key exists."""
        mock_redis_async = MagicMock()
        mock_redis_async.expire = AsyncMock(return_value=1)

        result = await vcon_redis.set_expiry_async(mock_redis_async, sample_vcon_dict['uuid'], 3600)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_expiry_async_key_not_found(self, vcon_redis):
        """Verify set_expiry_async returns False when key doesn't exist."""
        mock_redis_async = MagicMock()
        mock_redis_async.expire = AsyncMock(return_value=0)

        result = await vcon_redis.set_expiry_async(mock_redis_async, "nonexistent-uuid", 3600)

        assert result is False


class TestAsyncGetTTL:
    """Tests for async get_ttl_async method."""

    @pytest.mark.asyncio
    async def test_get_ttl_async_with_expiry(self, vcon_redis, sample_vcon_dict):
        """Verify get_ttl_async returns remaining TTL when set."""
        mock_redis_async = MagicMock()
        mock_redis_async.ttl = AsyncMock(return_value=1800)

        result = await vcon_redis.get_ttl_async(mock_redis_async, sample_vcon_dict['uuid'])

        assert result == 1800

    @pytest.mark.asyncio
    async def test_get_ttl_async_no_expiry(self, vcon_redis, sample_vcon_dict):
        """Verify get_ttl_async returns -1 when no expiry is set."""
        mock_redis_async = MagicMock()
        mock_redis_async.ttl = AsyncMock(return_value=-1)

        result = await vcon_redis.get_ttl_async(mock_redis_async, sample_vcon_dict['uuid'])

        assert result == -1


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("REDIS_URL", "").startswith("redis://redis:"),
    reason="Integration tests require local Redis (not docker redis)"
)
class TestIntegrationWithRealRedis:
    """Integration tests using real Redis connection.
    
    These tests require a running Redis instance and test the actual
    TTL behavior with real Redis operations.
    
    Run with: pytest -m integration (requires local Redis at localhost:6379)
    Skip with: pytest -m "not integration"
    """

    @pytest.fixture(autouse=True)
    def check_redis_and_cleanup(self, vcon_redis, sample_vcon_obj):
        """Skip integration tests if Redis is not available, and clean up test keys."""
        try:
            from redis_mgr import redis
            redis.ping()
            # Clean up any existing test key before each test
            redis.delete(f"vcon:{sample_vcon_obj.uuid}")
        except Exception:
            pytest.skip("Redis not available for integration tests")
        
        yield
        
        # Clean up after test
        try:
            from redis_mgr import redis
            redis.delete(f"vcon:{sample_vcon_obj.uuid}")
        except Exception:
            pass

    def test_store_vcon_with_ttl_integration(self, vcon_redis, sample_vcon_obj):
        """Integration test: store vCon with TTL and verify expiry is set."""
        # Store with short TTL for testing
        test_ttl = 60  # 1 minute
        vcon_redis.store_vcon(sample_vcon_obj, ttl=test_ttl)

        # Verify TTL is set (should be close to test_ttl)
        remaining_ttl = vcon_redis.get_ttl(sample_vcon_obj.uuid)
        assert 0 < remaining_ttl <= test_ttl

    def test_store_vcon_without_ttl_integration(self, vcon_redis, sample_vcon_obj):
        """Integration test: store vCon without TTL and verify no expiry."""
        vcon_redis.store_vcon(sample_vcon_obj)

        # Verify no TTL is set (-1 means no expiry)
        remaining_ttl = vcon_redis.get_ttl(sample_vcon_obj.uuid)
        assert remaining_ttl == -1

    def test_set_expiry_integration(self, vcon_redis, sample_vcon_obj):
        """Integration test: set expiry on existing vCon."""
        # First store without TTL
        vcon_redis.store_vcon(sample_vcon_obj)
        assert vcon_redis.get_ttl(sample_vcon_obj.uuid) == -1

        # Then set expiry
        test_ttl = 120
        result = vcon_redis.set_expiry(sample_vcon_obj.uuid, test_ttl)
        assert result is True

        # Verify TTL is now set
        remaining_ttl = vcon_redis.get_ttl(sample_vcon_obj.uuid)
        assert 0 < remaining_ttl <= test_ttl

    def test_remove_expiry_integration(self, vcon_redis, sample_vcon_obj):
        """Integration test: remove expiry from vCon."""
        # Store with TTL
        vcon_redis.store_vcon(sample_vcon_obj, ttl=60)
        assert vcon_redis.get_ttl(sample_vcon_obj.uuid) > 0

        # Remove expiry
        result = vcon_redis.remove_expiry(sample_vcon_obj.uuid)
        assert result is True

        # Verify TTL is removed
        assert vcon_redis.get_ttl(sample_vcon_obj.uuid) == -1
