import pytest
import json
from unittest.mock import patch, MagicMock, ANY

from server.lib.vcon_redis import VconRedis
from server.vcon import Vcon
from server.storage.dataverse import (
    save,
    get,
    get_access_token,
    create_dataverse_session
)


# Sample vCon for testing
@pytest.fixture
def sample_vcon():
    vcon = Vcon.build_new()
    
    # Add metadata
    vcon.vcon_dict["metadata"] = {
        "title": "Test Call",
        "description": "This is a test call",
        "created_at": "2023-01-01T12:00:00.000Z"
    }
    
    # Add parties
    vcon.add_party({
        "name": "John Doe",
        "role": "agent",
        "tel": "+1234567890"
    })
    vcon.add_party({
        "name": "Jane Smith",
        "role": "customer"
    })
    
    # Add dialogs
    vcon.add_dialog({
        "type": "text",
        "body": "Hello, how can I help you today?"
    })
    
    # Add analysis - transcript
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={"text": "This is a transcript of the conversation."}
    )
    
    return vcon


# Mock Redis
@pytest.fixture
def mock_vcon_redis(sample_vcon):
    with patch('server.lib.vcon_redis.VconRedis') as MockVconRedis:
        mock_redis = MagicMock()
        mock_redis.get_vcon.return_value = sample_vcon
        MockVconRedis.return_value = mock_redis
        yield MockVconRedis


# Mock MSAL
@pytest.fixture
def mock_msal():
    with patch('server.storage.dataverse.msal') as mock_msal:
        mock_client_app = MagicMock()
        mock_msal.ConfidentialClientApplication.return_value = mock_client_app
        
        # Setup token response
        mock_token_response = {
            "access_token": "mock-access-token",
            "expires_in": 3600
        }
        mock_client_app.acquire_token_for_client.return_value = mock_token_response
        
        yield mock_msal


# Mock Requests
@pytest.fixture
def mock_requests():
    with patch('server.storage.dataverse.requests') as mock_requests:
        mock_session = MagicMock()
        mock_requests.Session.return_value = mock_session
        
        # Mock responses
        mock_get_response = MagicMock()
        mock_post_response = MagicMock()
        mock_patch_response = MagicMock()
        
        mock_session.get.return_value = mock_get_response
        mock_session.post.return_value = mock_post_response
        mock_session.patch.return_value = mock_patch_response
        
        # Default to successful responses
        mock_get_response.raise_for_status.return_value = None
        mock_post_response.raise_for_status.return_value = None
        mock_patch_response.raise_for_status.return_value = None
        
        # Mock JSON responses
        mock_get_response.json.return_value = {"value": []}
        
        yield mock_requests


def test_get_access_token(mock_msal):
    """Test the token acquisition process."""
    options = {
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "url": "https://test.crm.dynamics.com"
    }
    
    # Test successful token acquisition
    token = get_access_token(options)
    assert token == "mock-access-token"
    
    # Verify MSAL was called correctly
    mock_msal.ConfidentialClientApplication.assert_called_with(
        client_id="test-client",
        client_credential="test-secret",
        authority="https://login.microsoftonline.com/test-tenant"
    )
    
    # Test with failed token acquisition
    mock_msal.ConfidentialClientApplication.return_value.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Invalid client credentials"
    }
    
    token = get_access_token(options)
    assert token is None


def test_create_dataverse_session(mock_msal, mock_requests):
    """Test creation of a requests session with proper headers."""
    options = {
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret",
        "url": "https://test.crm.dynamics.com"
    }
    
    # Test successful session creation
    session = create_dataverse_session(options)
    assert session is not None
    
    # Verify headers
    headers = mock_requests.Session.return_value.headers
    headers.update.assert_called_with({
        "Authorization": "Bearer mock-access-token",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "odata.include-annotations=*"
    })
    
    # Test with failed token acquisition
    mock_msal.ConfidentialClientApplication.return_value.acquire_token_for_client.return_value = {
        "error": "invalid_client"
    }
    
    session = create_dataverse_session(options)
    assert session is None


@patch('server.storage.dataverse.create_dataverse_session')
def test_save_new_entity(mock_create_session, mock_requests, mock_vcon_redis, sample_vcon):
    """Test saving a new vCon entity to Dataverse."""
    # Setup mocks
    mock_session = mock_requests.Session.return_value
    mock_create_session.return_value = mock_session
    
    # Configure mock Redis to return sample_vcon for test-uuid
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = sample_vcon
    
    # Mock that entity doesn't exist (empty response)
    mock_session.get.return_value.json.return_value = {"value": []}
    
    # Test options
    test_options = {
        "url": "https://test.crm.dynamics.com",
        "api_version": "9.2",
        "entity_name": "vcon_storage",
        "uuid_field": "vcon_uuid",
        "data_field": "vcon_data",
        "subject_field": "vcon_subject",
        "created_at_field": "vcon_created_at"
    }
    
    # Call save
    with patch('server.storage.dataverse.VconRedis', return_value=mock_instance):
        save("test-uuid", test_options)
    
    # Verify entity was created (POST request)
    mock_session.post.assert_called()
    post_url = mock_session.post.call_args[0][0]
    assert post_url == "https://test.crm.dynamics.com/api/data/v9.2/vcon_storage"
    
    # Verify data in POST request
    post_data = mock_session.post.call_args[1]["json"]
    assert post_data["vcon_uuid"] == "test-uuid"
    assert post_data["vcon_subject"] == sample_vcon.subject
    assert "vcon_data" in post_data
    assert "vcon_created_at" in post_data


@patch('server.storage.dataverse.create_dataverse_session')
def test_save_existing_entity(mock_create_session, mock_requests, mock_vcon_redis, sample_vcon):
    """Test updating an existing vCon entity in Dataverse."""
    # Setup mocks
    mock_session = mock_requests.Session.return_value
    mock_create_session.return_value = mock_session
    
    # Configure mock Redis to return sample_vcon for test-uuid
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = sample_vcon
    
    # Mock that entity exists
    mock_session.get.return_value.json.return_value = {
        "value": [{
            "id": "entity-id-123",
            "vcon_uuid": "test-uuid"
        }]
    }
    
    # Test options
    test_options = {
        "url": "https://test.crm.dynamics.com",
        "api_version": "9.2",
        "entity_name": "vcon_storage",
        "uuid_field": "vcon_uuid",
        "data_field": "vcon_data",
        "subject_field": "vcon_subject",
        "created_at_field": "vcon_created_at"
    }
    
    # Call save
    with patch('server.storage.dataverse.VconRedis', return_value=mock_instance):
        save("test-uuid", test_options)
    
    # Verify entity was updated (PATCH request)
    mock_session.patch.assert_called()
    patch_url = mock_session.patch.call_args[0][0]
    assert patch_url == "https://test.crm.dynamics.com/api/data/v9.2/vcon_storage(entity-id-123)"
    
    # Verify data in PATCH request
    patch_data = mock_session.patch.call_args[1]["json"]
    assert patch_data["vcon_uuid"] == "test-uuid"
    assert patch_data["vcon_subject"] == sample_vcon.subject
    assert "vcon_data" in patch_data
    assert "vcon_created_at" in patch_data


@patch('server.storage.dataverse.create_dataverse_session')
def test_get_vcon(mock_create_session, mock_requests):
    """Test retrieving a vCon from Dataverse."""
    # Setup mocks
    mock_session = mock_requests.Session.return_value
    mock_create_session.return_value = mock_session
    
    # Mock entity exists with vCon data
    mock_vcon_data = {
        "uuid": "test-uuid",
        "metadata": {"title": "Test vCon"},
        "parties": [{"name": "John Doe"}]
    }
    mock_session.get.return_value.json.return_value = {
        "value": [{
            "id": "entity-id-123",
            "vcon_uuid": "test-uuid",
            "vcon_data": json.dumps(mock_vcon_data),
            "vcon_subject": "Test Subject"
        }]
    }
    
    # Test options
    test_options = {
        "url": "https://test.crm.dynamics.com",
        "api_version": "9.2",
        "entity_name": "vcon_storage",
        "uuid_field": "vcon_uuid",
        "data_field": "vcon_data",
        "subject_field": "vcon_subject",
        "created_at_field": "vcon_created_at"
    }
    
    # Call get
    result = get("test-uuid", test_options)
    
    # Verify results
    assert result is not None
    assert result["uuid"] == "test-uuid"
    assert result["metadata"]["title"] == "Test vCon"
    
    # Test entity not found
    mock_session.get.return_value.json.return_value = {"value": []}
    result = get("not-found-uuid", test_options)
    assert result is None


@patch('server.storage.dataverse.create_dataverse_session')
def test_get_vcon_error_handling(mock_create_session, mock_requests):
    """Test error handling when retrieving a vCon."""
    # Setup mocks
    mock_session = mock_requests.Session.return_value
    mock_create_session.return_value = mock_session
    
    # Mock request exception
    mock_session.get.side_effect = Exception("Connection error")
    
    # Call get - should return None on error
    result = get("test-uuid")
    assert result is None
    
    # Test with invalid JSON
    mock_session.get.side_effect = None
    mock_session.get.return_value.json.return_value = {
        "value": [{
            "vcon_uuid": "test-uuid",
            "vcon_data": "invalid-json{"
        }]
    }
    
    result = get("test-uuid")
    assert result is None