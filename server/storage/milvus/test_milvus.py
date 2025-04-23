import pytest
from unittest.mock import patch, MagicMock, mock_open

from server.lib.vcon_redis import VconRedis
from server.vcon import Vcon
from server.storage.milvus import (
    save, 
    get,
    extract_text_from_vcon,
    extract_party_id,
    get_embedding,
    ensure_milvus_connection,
    check_vcon_exists
)

# Sample vCon for testing
@pytest.fixture
def sample_vcon():
    vcon = Vcon.build_new()
    
    # Add metadata
    vcon.metadata = {
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
        vendor="test",
        body={"text": "This is a transcript of the conversation."}
    )
    
    # Add analysis - summary
    vcon.add_analysis(
        type="summary",
        vendor="test",
        body="This is a summary of the call between an agent and a customer."
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

# Mock Milvus connections and utility
@pytest.fixture
def mock_milvus():
    with patch('server.storage.milvus.connections') as mock_connections, \
         patch('server.storage.milvus.utility') as mock_utility, \
         patch('server.storage.milvus.Collection') as mock_collection_class:
        
        # Setup utility mocks
        mock_utility.has_collection.return_value = True
        mock_utility.list_collections.return_value = ["vcons"]
        
        # Setup collection mock
        mock_collection = MagicMock()
        mock_collection_class.return_value = mock_collection
        mock_collection.query.return_value = []  # No existing vCons by default
        
        yield {
            'connections': mock_connections,
            'utility': mock_utility,
            'collection_class': mock_collection_class,
            'collection': mock_collection
        }

# Mock OpenAI client
@pytest.fixture
def mock_openai():
    with patch('server.storage.milvus.OpenAI') as mock_openai_class:
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        # Mock embeddings response
        mock_response = MagicMock()
        mock_data = MagicMock()
        mock_data.embedding = [0.1] * 1536  # 1536-dimensional embedding
        mock_response.data = [mock_data]
        mock_client.embeddings.create.return_value = mock_response
        
        yield mock_client

def test_extract_text_from_vcon(sample_vcon):
    """Test that text extraction from vCon works correctly."""
    vcon_dict = sample_vcon.to_dict()
    text = extract_text_from_vcon(vcon_dict)
    
    # Check that text contains important components
    assert "This is a transcript of the conversation" in text
    assert "This is a summary of the call" in text
    assert "Hello, how can I help you" in text
    assert "Party: agent John Doe" in text or "Party: John Doe" in text
    assert "Title: Test Call" in text

def test_extract_party_id(sample_vcon):
    """Test extraction of party ID from vCon."""
    vcon_dict = sample_vcon.to_dict()
    party_id = extract_party_id(vcon_dict)
    
    # Should extract tel from first party
    assert party_id == "tel:+1234567890"
    
    # Test with no tel
    vcon_dict["parties"][0].pop("tel", None)
    party_id = extract_party_id(vcon_dict)
    assert "agent:John Doe" in party_id or "John Doe" in party_id
    
    # Test with no parties
    vcon_dict["parties"] = []
    party_id = extract_party_id(vcon_dict)
    assert party_id == "no_party_info"

def test_ensure_milvus_connection(mock_milvus):
    """Test Milvus connection handling."""
    # Test successful connection
    assert ensure_milvus_connection("localhost", "19530") is True
    
    # Test handling reconnection
    mock_milvus['utility'].list_collections.side_effect = [Exception("Connection error"), None]
    assert ensure_milvus_connection("localhost", "19530") is True
    assert mock_milvus['connections'].disconnect.called
    assert mock_milvus['connections'].connect.called

def test_get_embedding(mock_openai):
    """Test embedding generation."""
    embedding = get_embedding("Test text", mock_openai, "text-embedding-3-small")
    assert len(embedding) == 1536
    mock_openai.embeddings.create.assert_called_with(
        input="Test text",
        model="text-embedding-3-small"
    )
    
    # Test empty text handling
    embedding = get_embedding("", mock_openai, "text-embedding-3-small")
    assert len(embedding) == 1536
    assert embedding.count(0) == 1536  # Should be a zero vector

def test_check_vcon_exists(mock_milvus):
    """Test checking if vCon exists in Milvus."""
    # Test not exists
    mock_milvus['collection'].query.return_value = []
    assert check_vcon_exists(mock_milvus['collection'], "test-uuid") is False
    
    # Test exists
    mock_milvus['collection'].query.return_value = [{"vcon_uuid": "test-uuid"}]
    assert check_vcon_exists(mock_milvus['collection'], "test-uuid") is True

@patch('server.storage.milvus.extract_text_from_vcon')
@patch('server.storage.milvus.extract_party_id')
@patch('server.storage.milvus.get_embedding')
def test_save(mock_get_embedding, mock_extract_party_id, mock_extract_text, 
              mock_vcon_redis, mock_milvus, mock_openai, sample_vcon):
    """Test saving a vCon to Milvus."""
    # Setup mocks
    mock_extract_text.return_value = "Extracted text content"
    mock_extract_party_id.return_value = "tel:+1234567890"
    mock_get_embedding.return_value = [0.1] * 1536
    
    # Test options
    test_options = {
        "host": "localhost",
        "port": "19530",
        "collection_name": "vcons",
        "embedding_model": "text-embedding-3-small",
        "embedding_dim": 1536,
        "api_key": "test-api-key",
        "organization": "test-org"
    }
    
    # Call save
    save("test-uuid", test_options)
    
    # Verify milvus operations
    mock_milvus['collection'].load.assert_called()
    mock_milvus['collection'].insert.assert_called()
    mock_milvus['collection'].flush.assert_called()
    
    # Verify data passed to insert
    insert_args = mock_milvus['collection'].insert.call_args[0][0]
    assert len(insert_args) == 1
    assert insert_args[0]["vcon_uuid"] == "test-uuid"
    assert insert_args[0]["party_id"] == "tel:+1234567890"
    assert insert_args[0]["text"] == "Extracted text content"
    assert len(insert_args[0]["embedding"]) == 1536
    
@patch('server.storage.milvus.ensure_milvus_connection')
def test_get_vcon_from_milvus(mock_ensure_connection, mock_milvus):
    """Test retrieving a vCon from Milvus."""
    # Setup mocks
    mock_ensure_connection.return_value = True
    mock_milvus['collection'].query.return_value = [{
        "vcon_uuid": "test-uuid",
        "text": "Test text content",
        "embedding": [0.1] * 1536,
        "party_id": "tel:+1234567890"
    }]
    
    # Call get
    result = get("test-uuid")
    
    # Verify result
    assert result is not None
    assert result["uuid"] == "test-uuid"
    assert result["text"] == "Test text content"
    assert len(result["embedding"]) == 1536
    assert result["party_id"] == "tel:+1234567890"
    
    # Test not found
    mock_milvus['collection'].query.return_value = []
    result = get("not-found-uuid")
    assert result is None