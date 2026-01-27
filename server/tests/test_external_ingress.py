"""Unit tests for the external ingress API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import api
from fastapi.testclient import TestClient
from settings import CONSERVER_HEADER_NAME
from vcon_fixture import generate_mock_vcon


class TestExternalIngress:
    """Test cases for the /vcon/external-ingress endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(api.app)
        self.test_vcon = generate_mock_vcon()
        self.ingress_list = "test_external_ingress"
        self.valid_api_key = "external-partner-key-123"
        self.invalid_api_key = "invalid-key"

    def test_validate_ingress_api_key_function(self):
        """Test the validate_ingress_api_key function directly."""

        with patch("config.Configuration.get_ingress_auth") as mock_get_ingress_auth:
            # Test successful validation with single API key
            mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

            result = api.validate_ingress_api_key(self.ingress_list, self.valid_api_key)
            assert result == self.valid_api_key

            # Test successful validation with multiple API keys
            mock_get_ingress_auth.return_value = {
                self.ingress_list: [self.valid_api_key, "other-key"]
            }

            result = api.validate_ingress_api_key(self.ingress_list, self.valid_api_key)
            assert result == self.valid_api_key

    @patch("config.Configuration.get_ingress_auth")
    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon")
    def test_successful_submission_single_api_key(
        self, mock_index_vcon, mock_add_vcon_to_set, mock_get_ingress_auth
    ):
        """Test successful vCon submission with single API key configuration."""
        # Configure mocks
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        # Mock Redis client properly
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
                f"/vcon/external-ingress?ingress_list={self.ingress_list}",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: self.valid_api_key},
            )

            # Debug the response if it fails
            if response.status_code != 204:
                print(f"Status: {response.status_code}")
                print(f"Response: {response.json()}")

            # Assertions
            assert response.status_code == 204
            assert response.content == b""  # No content returned

            # Verify Redis operations were called
            mock_json.set.assert_called_once()
            mock_redis.expire.assert_called_once()  # Verify expiry was set
            mock_redis.rpush.assert_called_once_with(
                self.ingress_list, self.test_vcon["uuid"]
            )
            mock_add_vcon_to_set.assert_called_once()
            mock_index_vcon.assert_called_once()

        finally:
            # Clean up the global variable
            api.redis_async = None

    @patch("config.Configuration.get_ingress_auth")
    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon")
    def test_successful_submission_multiple_api_keys(
        self, mock_index_vcon, mock_add_vcon_to_set, mock_get_ingress_auth
    ):
        """Test successful vCon submission with multiple API keys for same ingress."""
        # Configure mocks - multiple API keys for same ingress list
        mock_get_ingress_auth.return_value = {
            self.ingress_list: ["partner-1-key", self.valid_api_key, "partner-3-key"]
        }

        # Mock Redis client properly
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.rpush = AsyncMock()

        # Set the global redis_async directly in the api module
        api.redis_async = mock_redis

        try:
            # Make request with one of the valid keys
            response = self.client.post(
                f"/vcon/external-ingress?ingress_list={self.ingress_list}",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: self.valid_api_key},
            )

            # Assertions
            assert response.status_code == 204
            mock_redis.rpush.assert_called_once_with(
                self.ingress_list, self.test_vcon["uuid"]
            )

        finally:
            # Clean up the global variable
            api.redis_async = None

    @patch("config.Configuration.get_ingress_auth")
    def test_invalid_api_key_single_config(self, mock_get_ingress_auth):
        """Test rejection with invalid API key for single key configuration."""
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        response = self.client.post(
            f"/vcon/external-ingress?ingress_list={self.ingress_list}",
            json=self.test_vcon,
            headers={CONSERVER_HEADER_NAME: self.invalid_api_key},
        )

        assert response.status_code == 403
        assert "Invalid API Key" in response.json()["detail"]

    @patch("config.Configuration.get_ingress_auth")
    def test_invalid_api_key_multiple_config(self, mock_get_ingress_auth):
        """Test rejection with invalid API key for multiple key configuration."""
        mock_get_ingress_auth.return_value = {
            self.ingress_list: ["key1", "key2", "key3"]
        }

        response = self.client.post(
            f"/vcon/external-ingress?ingress_list={self.ingress_list}",
            json=self.test_vcon,
            headers={CONSERVER_HEADER_NAME: self.invalid_api_key},
        )

        assert response.status_code == 403
        assert "Invalid API Key" in response.json()["detail"]

    @patch("config.Configuration.get_ingress_auth")
    def test_unauthorized_ingress_list(self, mock_get_ingress_auth):
        """Test rejection when API key is valid but not for requested ingress list."""
        mock_get_ingress_auth.return_value = {
            "authorized_ingress": self.valid_api_key,
            "other_ingress": "other-key",
        }

        response = self.client.post(
            f"/vcon/external-ingress?ingress_list=unauthorized_ingress",
            json=self.test_vcon,
            headers={CONSERVER_HEADER_NAME: self.valid_api_key},
        )

        assert response.status_code == 403
        assert "not configured" in response.json()["detail"]

    @patch("config.Configuration.get_ingress_auth")
    def test_missing_api_key(self, mock_get_ingress_auth):
        """Test rejection when no API key is provided."""
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        response = self.client.post(
            f"/vcon/external-ingress?ingress_list={self.ingress_list}",
            json=self.test_vcon,
            # No API key header
        )

        assert response.status_code == 403
        # The actual error message when no API key is provided
        error_detail = response.json()["detail"]
        assert "Invalid API Key" in error_detail or "API Key required" in error_detail

    @patch("config.Configuration.get_ingress_auth")
    def test_no_ingress_auth_configured(self, mock_get_ingress_auth):
        """Test rejection when no ingress authentication is configured."""
        mock_get_ingress_auth.return_value = {}

        response = self.client.post(
            f"/vcon/external-ingress?ingress_list={self.ingress_list}",
            json=self.test_vcon,
            headers={CONSERVER_HEADER_NAME: self.valid_api_key},
        )

        assert response.status_code == 403
        assert "No ingress authentication configured" in response.json()["detail"]

    @patch("config.Configuration.get_ingress_auth")
    def test_invalid_config_format(self, mock_get_ingress_auth):
        """Test handling of invalid configuration format (not string or list)."""
        mock_get_ingress_auth.return_value = {
            self.ingress_list: {"invalid": "format"}  # Neither string nor list
        }

        response = self.client.post(
            f"/vcon/external-ingress?ingress_list={self.ingress_list}",
            json=self.test_vcon,
            headers={CONSERVER_HEADER_NAME: self.valid_api_key},
        )

        assert response.status_code == 403
        assert "Invalid configuration" in response.json()["detail"]

    @patch("config.Configuration.get_ingress_auth")
    def test_redis_failure_handling(self, mock_get_ingress_auth):
        """Test error handling when Redis operations fail."""
        mock_get_ingress_auth.return_value = {self.ingress_list: self.valid_api_key}

        # Mock Redis client that fails (use MagicMock to avoid coroutine issues)
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.rpush = AsyncMock()

        # Set the global redis_async directly in the api module
        api.redis_async = mock_redis

        try:
            response = self.client.post(
                f"/vcon/external-ingress?ingress_list={self.ingress_list}",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: self.valid_api_key},
            )

            assert response.status_code == 500
            assert "Failed to store vCon" in response.json()["detail"]

        finally:
            # Clean up the global variable
            api.redis_async = None

    @patch("config.Configuration.get_ingress_auth")
    @patch("api.add_vcon_to_set")
    @patch("api.index_vcon")
    def test_multiple_ingress_lists_isolation(
        self, mock_index_vcon, mock_add_vcon_to_set, mock_get_ingress_auth
    ):
        """Test that API keys are properly isolated between ingress lists."""
        # Configure different API keys for different ingress lists
        mock_get_ingress_auth.return_value = {
            "partner_a_ingress": "partner-a-key",
            "partner_b_ingress": ["partner-b-key-1", "partner-b-key-2"],
            "shared_ingress": ["partner-a-key", "partner-b-key-1", "shared-key"],
        }

        # Mock Redis client properly
        mock_redis = MagicMock()
        mock_json = MagicMock()
        mock_json.set = AsyncMock()
        mock_redis.json.return_value = mock_json
        mock_redis.expire = AsyncMock()
        mock_redis.rpush = AsyncMock()

        # Set the global redis_async directly in the api module
        api.redis_async = mock_redis

        try:
            # Test partner A can access their ingress
            response = self.client.post(
                "/vcon/external-ingress?ingress_list=partner_a_ingress",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: "partner-a-key"},
            )
            assert response.status_code == 204

            # Test partner A cannot access partner B's ingress
            response = self.client.post(
                "/vcon/external-ingress?ingress_list=partner_b_ingress",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: "partner-a-key"},
            )
            assert response.status_code == 403

            # Test partner B can access shared ingress
            response = self.client.post(
                "/vcon/external-ingress?ingress_list=shared_ingress",
                json=self.test_vcon,
                headers={CONSERVER_HEADER_NAME: "partner-b-key-1"},
            )
            assert response.status_code == 204

        finally:
            # Clean up the global variable
            api.redis_async = None

    def test_missing_ingress_list_parameter(self):
        """Test rejection when ingress_list parameter is missing."""
        response = self.client.post(
            "/vcon/external-ingress",  # No ingress_list parameter
            json=self.test_vcon,
            headers={CONSERVER_HEADER_NAME: self.valid_api_key},
        )

        assert response.status_code == 422  # FastAPI validation error
        assert "field required" in response.text.lower()

    def test_invalid_vcon_data(self):
        """Test rejection with invalid vCon data."""
        invalid_vcon = {"invalid": "data"}

        response = self.client.post(
            f"/vcon/external-ingress?ingress_list={self.ingress_list}",
            json=invalid_vcon,
            headers={CONSERVER_HEADER_NAME: self.valid_api_key},
        )

        assert response.status_code == 422  # FastAPI validation error
