"""Unit tests for POST vCon default expiry functionality.

These tests verify that vCons created via POST endpoints are stored with
the default VCON_REDIS_EXPIRY TTL (3600 seconds by default).
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
    @patch("api.index_vcon")
    def test_post_vcon_sets_default_expiry(
        self, mock_index_vcon, mock_add_vcon_to_set
    ):
        """Test that POST /vcon sets the default VCON_REDIS_EXPIRY TTL."""
        # Mock Redis client
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.rpush = AsyncMock()

        # Set the global redis_async directly in the api module
        api.redis_async = mock_redis

        try:
            # Make request
            response = self.client.post(
                "/vcon",
                json=self.test_vcon,
            )

            # Debug the response if it fails
            if response.status_code != 201:
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")

            # Assertions
            assert response.status_code == 201

            # Verify Redis JSON set was called
            mock_json.set.assert_called_once()

            # Verify expire was called with the default VCON_REDIS_EXPIRY
            expected_key = f"vcon:{self.test_vcon['uuid']}"
            mock_redis.expire.assert_called_once_with(expected_key, VCON_REDIS_EXPIRY)

        finally:
            # Clean up the global variable
            api.redis_async = None

    def test_post_vcon_expiry_value_is_3600(self):
        """Test that the default expiry value is 3600 seconds (1 hour)."""
        # Verify the configured value
        assert VCON_REDIS_EXPIRY == 3600, "Default VCON_REDIS_EXPIRY should be 3600 seconds"

    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon")
    def test_post_vcon_with_ingress_list_sets_expiry(
        self, mock_index_vcon, mock_add_vcon_to_set
    ):
        """Test that POST /vcon with ingress_lists still sets expiry."""
        # Mock Redis client
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.rpush = AsyncMock()

        api.redis_async = mock_redis

        try:
            # Make request with ingress_lists parameter
            response = self.client.post(
                "/vcon?ingress_lists=test_ingress",
                json=self.test_vcon,
            )

            assert response.status_code == 201

            # Verify expire was still called
            expected_key = f"vcon:{self.test_vcon['uuid']}"
            mock_redis.expire.assert_called_once_with(expected_key, VCON_REDIS_EXPIRY)

            # Verify ingress list was also populated
            mock_redis.rpush.assert_called_once_with("test_ingress", self.test_vcon['uuid'])

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
    @patch("api.index_vcon")
    def test_external_ingress_sets_default_expiry(
        self, mock_index_vcon, mock_add_vcon_to_set, mock_get_ingress_auth
    ):
        """Test that POST /vcon/external-ingress sets the default VCON_REDIS_EXPIRY TTL."""
        # Configure ingress auth mock
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        # Mock Redis client
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.rpush = AsyncMock()

        api.redis_async = mock_redis

        try:
            # Make request
            response = self.client.post(
                f"/vcon/external-ingress?ingress_list={self.ingress_list}",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: self.valid_api_key},
            )

            # Debug the response if it fails
            if response.status_code != 204:
                print(f"Status: {response.status_code}")
                print(f"Response: {response.text}")

            # Assertions
            assert response.status_code == 204

            # Verify expire was called with the default VCON_REDIS_EXPIRY
            expected_key = f"vcon:{self.test_vcon['uuid']}"
            mock_redis.expire.assert_called_once_with(expected_key, VCON_REDIS_EXPIRY)

        finally:
            api.redis_async = None

    @patch("config.Configuration.get_ingress_auth")
    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon")
    def test_external_ingress_expire_called_before_rpush(
        self, mock_index_vcon, mock_add_vcon_to_set, mock_get_ingress_auth
    ):
        """Test that expire is called before adding to ingress list."""
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        # Mock Redis client with call order tracking
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        
        call_order = []
        
        async def track_expire(key, ttl):
            call_order.append(('expire', key, ttl))
        
        async def track_rpush(list_name, uuid):
            call_order.append(('rpush', list_name, uuid))
        
        mock_redis.expire = AsyncMock(side_effect=track_expire)
        mock_redis.rpush = AsyncMock(side_effect=track_rpush)

        api.redis_async = mock_redis

        try:
            response = self.client.post(
                f"/vcon/external-ingress?ingress_list={self.ingress_list}",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: self.valid_api_key},
            )

            assert response.status_code == 204

            # Verify call order: expire should come before rpush
            assert len(call_order) >= 2
            expire_index = next(i for i, c in enumerate(call_order) if c[0] == 'expire')
            rpush_index = next(i for i, c in enumerate(call_order) if c[0] == 'rpush')
            assert expire_index < rpush_index, "expire should be called before rpush"

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
