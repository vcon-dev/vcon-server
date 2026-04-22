"""Unit tests for POST vCon expiry behavior.

These tests verify that vCons created via POST endpoints are stored and
indexed. As of the optimize-ingest-indexing change, default VCON_REDIS_EXPIRY
TTL is no longer set on newly stored vCons; retention is controlled by
storage backends or explicit TTL. Indexing (index_vcon_parties) still uses
Redis sadd/expire for party index keys.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import api
from fastapi.testclient import TestClient
from settings import CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME, VCON_REDIS_EXPIRY
from vcon_fixture import generate_mock_vcon

# Use the configured API token or a default for testing
TEST_API_TOKEN = CONSERVER_API_TOKEN or "test-api-token"


class TestPostVconExpiry:
    """Test cases for POST /vcon endpoint expiry behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(api.app, headers={CONSERVER_HEADER_NAME: TEST_API_TOKEN})
        self.test_vcon = generate_mock_vcon()

    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon_parties")
    def test_post_vcon_stores_without_default_expiry(
        self, mock_index_vcon_parties, mock_add_vcon_to_set
    ):
        """Test that POST /vcon stores vCon and indexes parties; no default vcon TTL."""
        # Mock Redis client (sadd/expire used by index_vcon_parties when not patched)
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.rpush = AsyncMock()

        api.redis_async = mock_redis

        try:
            response = self.client.post(
                "/vcon",
                json=self.test_vcon,
            )

            if response.status_code != 201:
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")

            assert response.status_code == 201
            mock_json.set.assert_called_once()
            # No default TTL on vcon key: expire is only used for index keys by index_vcon_parties
            vcon_key = f"vcon:{self.test_vcon['uuid']}"
            vcon_expire_calls = [
                c for c in mock_redis.expire.call_args_list
                if c[0][0] == vcon_key and c[0][1] == VCON_REDIS_EXPIRY
            ]
            assert len(vcon_expire_calls) == 0, "vCon key should not get default VCON_REDIS_EXPIRY TTL"

        finally:
            api.redis_async = None

    def test_post_vcon_expiry_value_is_3600(self):
        """Test that the default expiry value is 3600 seconds (1 hour)."""
        # Verify the configured value
        assert VCON_REDIS_EXPIRY == 3600, "Default VCON_REDIS_EXPIRY should be 3600 seconds"

    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon_parties")
    def test_post_vcon_with_ingress_list_stores_without_default_expiry(
        self, mock_index_vcon_parties, mock_add_vcon_to_set
    ):
        """Test that POST /vcon with ingress_lists stores and adds to list; no default vcon TTL."""
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.rpush = AsyncMock()

        api.redis_async = mock_redis

        try:
            response = self.client.post(
                "/vcon?ingress_lists=test_ingress",
                json=self.test_vcon,
            )

            assert response.status_code == 201
            # No default TTL on vcon key
            vcon_key = f"vcon:{self.test_vcon['uuid']}"
            vcon_expire_calls = [
                c for c in mock_redis.expire.call_args_list
                if c[0][0] == vcon_key and c[0][1] == VCON_REDIS_EXPIRY
            ]
            assert len(vcon_expire_calls) == 0
            mock_redis.rpush.assert_called_once_with("test_ingress", self.test_vcon["uuid"])

        finally:
            api.redis_async = None


class TestExternalIngressExpiry:
    """Test cases for POST /vcon/external-ingress endpoint expiry behavior."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(api.app)
        self.test_vcon = generate_mock_vcon()
        self.ingress_list = "test_external_ingress"
        self.valid_api_key = "external-partner-key-123"

    @patch("config.Configuration.get_ingress_auth")
    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon_parties")
    def test_external_ingress_stores_without_default_expiry(
        self, mock_index_vcon_parties, mock_add_vcon_to_set, mock_get_ingress_auth
    ):
        """Test that POST /vcon/external-ingress stores vCon; no default VCON_REDIS_EXPIRY on vcon key."""
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.rpush = AsyncMock()

        api.redis_async = mock_redis

        try:
            response = self.client.post(
                f"/vcon/external-ingress?ingress_list={self.ingress_list}",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: self.valid_api_key},
            )

            if response.status_code != 204:
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")

            assert response.status_code == 204
            vcon_key = f"vcon:{self.test_vcon['uuid']}"
            vcon_expire_calls = [
                c for c in mock_redis.expire.call_args_list
                if c[0][0] == vcon_key and c[0][1] == VCON_REDIS_EXPIRY
            ]
            assert len(vcon_expire_calls) == 0, "vCon key should not get default VCON_REDIS_EXPIRY TTL"

        finally:
            api.redis_async = None

    @patch("config.Configuration.get_ingress_auth")
    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon_parties")
    def test_external_ingress_adds_to_ingress_list(
        self, mock_index_vcon_parties, mock_add_vcon_to_set, mock_get_ingress_auth
    ):
        """Test that external ingress stores vCon and adds to ingress list."""
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.rpush = AsyncMock()

        api.redis_async = mock_redis

        try:
            response = self.client.post(
                f"/vcon/external-ingress?ingress_list={self.ingress_list}",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: self.valid_api_key},
            )

            assert response.status_code == 204
            mock_redis.rpush.assert_called_once_with(self.ingress_list, self.test_vcon["uuid"])

        finally:
            api.redis_async = None


class TestExpiryConfigurationValue:
    """Tests for the VCON_REDIS_EXPIRY configuration value."""

    def test_vcon_redis_expiry_default_value(self):
        """Verify VCON_REDIS_EXPIRY defaults to 3600 seconds."""
        assert VCON_REDIS_EXPIRY == 3600

    def test_vcon_redis_expiry_is_integer(self):
        """Verify VCON_REDIS_EXPIRY is an integer."""
        assert isinstance(VCON_REDIS_EXPIRY, int)

    def test_vcon_redis_expiry_is_positive(self):
        """Verify VCON_REDIS_EXPIRY is a positive value."""
        assert VCON_REDIS_EXPIRY > 0
