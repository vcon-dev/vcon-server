from typing import Any, Generator
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import json

# Import the functions and classes we want to test
from . import (
    DataTrailsAuth,
    get_asset,
    create_asset,
    update_asset,
    run
)

# Mock VconRedis class
class MockVconRedis:
    def get_vcon(self, vcon_uuid):
        return Mock(
            get_tag=Mock(side_effect=lambda x: {
                "datatrails_asset_id": "asset123" if x == "datatrails_asset_id" else None,
                "asset_name": "Test Asset" if x == "asset_name" else None,
                "datatrails_event_type": "TestEvent" if x == "datatrails_event_type" else None,
                "datatrails_event_attributes": '{"test": "event"}' if x == "datatrails_event_attributes" else "{}",
                "datatrails_asset_attributes": '{"test": "asset"}' if x == "datatrails_asset_attributes" else "{}"
            }.get(x)),
            subject="Test Subject",
            add_tag=Mock()
        )
    
    def store_vcon(self, vcon):
        pass

@pytest.fixture
def mock_auth() -> Generator[DataTrailsAuth, Any, None]:
    with patch('server.links.datatrails.requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "access_token": "test_token",
            "expires_in": 3600
        }
        auth = DataTrailsAuth("http://test.com", "test_id", "test_secret")
        yield auth

def test_datatrails_auth_get_token(mock_auth):
    token = mock_auth.get_token()
    assert token == "test_token"
    assert mock_auth.token_expiry > datetime.now()

def test_datatrails_auth_refresh_token(mock_auth):
    mock_auth.token_expiry = datetime.now() - timedelta(minutes=5)
    token = mock_auth.get_token()
    assert token == "test_token"
    assert mock_auth.token_expiry > datetime.now()

@pytest.mark.parametrize("status_code,expected_result", [
    (200, {"id": "asset123"}),
    (404, None)
])
def test_get_asset(mock_auth, status_code, expected_result):
    with patch('server.links.datatrails.requests.get') as mock_get:
        mock_get.return_value.status_code = status_code
        mock_get.return_value.json.return_value = expected_result
        result = get_asset("http://test.com", "asset123", mock_auth)
        assert result == expected_result


def test_create_asset(mock_auth):
    with patch('server.links.datatrails.requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "id": "new_asset",
            "access_token": "test_token",
            "expires_in": 3600
        }
        result = create_asset("http://test.com", mock_auth, {"name": "Test"}, ["Behaviour1"])
        assert result == {
            "id": "new_asset",
            "access_token": "test_token",
            "expires_in": 3600
        }
        mock_post.assert_called()

def test_update_asset(mock_auth):
    with patch('server.links.datatrails.requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "id": "new_asset",
            "access_token": "test_token",
            "expires_in": 3600
        }
        result = update_asset("http://test.com", "asset123", mock_auth, "TestEvent", {"test": "event"}, {"test": "asset"})
        assert result == {
            "id": "new_asset",
            "access_token": "test_token",
            "expires_in": 3600
        }
        mock_post.assert_called()
