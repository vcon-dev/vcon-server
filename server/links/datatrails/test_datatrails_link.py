from typing import Any, Generator
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import json

# Import the functions and classes we want to test
from . import (
    DataTrailsAuth,
    create_asset,
    create_event,
    run
)

# Mock VconRedis class
class MockVconRedis:
    def get_vcon(self, vcon_uuid):
        return Mock(
            get_tag=Mock(side_effect=lambda x: {
                "event_type": "vCon" if x == "event_type" else None,
                "event_attributes": '{"test": "event"}' if x == "event_attributes" else "{}",
                "asset_attributes": '{"test": "asset"}' if x == "asset_attributes" else "{}"
            }.get(x)),
            subject="vcon://abc123",
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

def test_create_asset(mock_auth):
    with patch('server.links.datatrails.requests.post') as mock_post:
        mock_post.return_value.json.return_value = {
            "id": "new_asset",
            "access_token": "test_token",
            "expires_in": 3600
        }
        result = create_asset(
            opts={"api_url":"http://test.com", "partner_id": "foo"}, 
            auth=mock_auth, 
            attributes={"name": "Test"}
        )
        assert result == {
            "id": "new_asset",
            "access_token": "test_token",
            "expires_in": 3600
        }
        mock_post.assert_called()
