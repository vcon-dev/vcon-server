import os
import pytest
import tempfile
import hashlib
from unittest.mock import patch, MagicMock, mock_open
import base64

from server.links.groq_whisper import run, transcribe_groq_whisper, get_file_content, get_transcription
from server.vcon import Vcon

# Set environment variable for testing
os.environ["GROQ_API_KEY"] = "test_api_key_for_testing"

@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('server.links.groq_whisper.VconRedis') as mock:
        yield mock

@pytest.fixture
def sample_vcon():
    """Create a sample vCon with recording dialog for testing"""
    vcon = Vcon.build_new()
    # Add a recording dialog for testing
    vcon.add_dialog({
        "type": "recording",
        "duration": 60,  # 60 seconds duration (more than minimum)
        "body": base64.b64encode(b"test audio content").decode('utf-8'),  # Simulated audio content
        "mime": "audio/flac"
    })
    return vcon

@pytest.fixture
def sample_vcon_with_url():
    """Create a sample vCon with recording dialog using URL reference"""
    vcon = Vcon.build_new()
    # Add a recording dialog for testing with URL reference
    vcon.add_dialog({
        "type": "recording",
        "duration": 60,
        "url": "https://example.com/audio.flac",
        "mime": "audio/flac"
    })
    return vcon

@pytest.fixture
def sample_vcon_with_existing_transcript():
    """Create a sample vCon with existing transcript analysis"""
    vcon = Vcon.build_new()
    # Add a recording dialog
    vcon.add_dialog({
        "type": "recording",
        "duration": 60,
        "body": base64.b64encode(b"test audio content").decode('utf-8'),
        "mime": "audio/flac"
    })
    # Add an existing transcript for this dialog
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="groq_whisper",
        body={"text": "Existing transcript"}
    )
    return vcon

@pytest.fixture
def mock_redis_with_vcon(mock_vcon_redis, sample_vcon):
    """Set up mock Redis with sample vCon"""
    mock_instance = MagicMock()
    mock_instance.get_vcon.return_value = sample_vcon
    mock_vcon_redis.return_value = mock_instance
    return mock_instance

@pytest.fixture
def mock_groq_client():
    """Mock the Groq client"""
    with patch('server.links.groq_whisper.Groq') as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        # Create mock transcriptions service
        mock_transcriptions = MagicMock()
        mock_client.audio.transcriptions = mock_transcriptions
        
        # Mock the create method to return a successful response
        mock_response = MagicMock()
        mock_response.text = "This is a test transcription"
        mock_response.model_dump.return_value = {
            "text": "This is a test transcription",
            "chunks": [{"text": "This is a test transcription"}],
            "language": "en"
        }
        mock_transcriptions.create.return_value = mock_response
        
        yield mock_client

def test_get_transcription(sample_vcon_with_existing_transcript):
    """Test retrieving an existing transcription"""
    # Check that we can find the existing transcript
    transcript = get_transcription(sample_vcon_with_existing_transcript, 0)
    assert transcript is not None
    assert transcript["type"] == "transcript"
    assert transcript["dialog"] == 0
    assert transcript["body"]["text"] == "Existing transcript"
    
    # Check non-existent transcription
    transcript = get_transcription(sample_vcon_with_existing_transcript, 1)  # No dialog at index 1
    assert transcript is None

def test_get_file_content_from_body():
    """Test extracting file content from dialog body"""
    dialog = {
        "body": base64.b64encode(b"test audio content").decode('utf-8')
    }
    content = get_file_content(dialog)
    assert content == b"test audio content"

@patch('server.links.groq_whisper.requests.get')
def test_get_file_content_from_url(mock_get):
    """Test extracting file content from URL reference"""
    # Set up mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"test audio content from url"
    mock_get.return_value = mock_response
    
    dialog = {
        "url": "https://example.com/audio.flac"
    }
    content = get_file_content(dialog)
    assert content == b"test audio content from url"
    mock_get.assert_called_once_with("https://example.com/audio.flac", verify=True)

@patch('server.links.groq_whisper.requests.get')
def test_get_file_content_with_signature_verification(mock_get):
    """Test file content extraction with signature verification"""
    # Content that will produce a predictable SHA-512 hash
    test_content = b"test content for signature verification"
    
    # Calculate the expected signature (SHA-512 hash in base64url format)
    file_hash = base64.urlsafe_b64encode(
        hashlib.sha512(test_content).digest()
    ).decode('utf-8')
    
    # Set up mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = test_content
    mock_get.return_value = mock_response
    
    dialog = {
        "url": "https://example.com/audio.flac",
        "signature": file_hash,
        "alg": "SHA-512"
    }
    
    # This should pass verification
    content = get_file_content(dialog)
    assert content == test_content

def test_get_file_content_error_handling():
    """Test error handling in get_file_content"""
    # Test dialog with neither body nor URL
    dialog = {"type": "recording"}
    with pytest.raises(Exception) as excinfo:
        get_file_content(dialog)
    assert "Dialog contains neither inline body nor external URL" in str(excinfo.value)

@patch('server.links.groq_whisper.requests.get')
def test_get_file_content_download_failure(mock_get):
    """Test handling of download failure"""
    mock_response = MagicMock()
    mock_response.status_code = 404  # Not found
    mock_get.return_value = mock_response
    
    dialog = {"url": "https://example.com/nonexistent.flac"}
    with pytest.raises(Exception) as excinfo:
        get_file_content(dialog)
    assert "Failed to download file" in str(excinfo.value)

def test_transcribe_groq_whisper(mock_groq_client):
    """Test Groq Whisper transcription"""
    dialog = {
        "body": base64.b64encode(b"test audio content").decode('utf-8')
    }
    opts = {"API_KEY": os.environ["GROQ_API_KEY"]}
    
    # Use patch to mock the file operations
    with patch("builtins.open", mock_open(read_data=b"test audio content")):
        with patch("tempfile.NamedTemporaryFile"):
            result = transcribe_groq_whisper(dialog, opts)
            
            # Verify result
            assert result is not None
            assert result.text == "This is a test transcription"
            
            # Verify Groq client was called correctly
            mock_groq_client.audio.transcriptions.create.assert_called_once()
            call_args = mock_groq_client.audio.transcriptions.create.call_args
            assert call_args[1]["model"] == "distil-whisper-large-v3-en"
            assert call_args[1]["response_format"] == "verbose_json"

def test_run_with_env_variable(mock_redis_with_vcon, sample_vcon, mock_groq_client):
    """Test the main run function using environment variable for API key"""
    # Create test options that use the environment variable
    opts = {
        "API_KEY": os.environ["GROQ_API_KEY"],
        "minimum_duration": 30
    }
    
    # Mock temporary file and file operations
    with patch("builtins.open", mock_open(read_data=b"test audio content")):
        with patch("tempfile.NamedTemporaryFile"):
            result = run("test-uuid", "groq_whisper", opts)
            
            # Check that vCon was processed and returned
            assert result == "test-uuid"
            
            # Verify Groq client was called
            mock_groq_client.audio.transcriptions.create.assert_called_once()
            
            # Verify analysis was added to vCon
            mock_redis_with_vcon.store_vcon.assert_called_once()
            # Check the vCon has a transcript analysis
            assert any(
                a["type"] == "transcript" and a["vendor"] == "groq_whisper" 
                for a in sample_vcon.analysis
            )

def test_run_skip_existing_transcript(mock_redis_with_vcon, sample_vcon_with_existing_transcript, mock_groq_client):
    """Test that run skips dialogs with existing transcripts"""
    # Set up Redis mock to return vCon with existing transcript
    mock_redis_with_vcon.get_vcon.return_value = sample_vcon_with_existing_transcript
    
    result = run("test-uuid", "groq_whisper")
    
    # Run should succeed but Groq client should not be called
    assert result == "test-uuid"
    mock_groq_client.audio.transcriptions.create.assert_not_called()

def test_run_skip_short_recording(mock_redis_with_vcon, mock_groq_client):
    """Test that run skips recordings shorter than minimum duration"""
    # Create a vCon with a short recording
    vcon = Vcon.build_new()
    vcon.add_dialog({
        "type": "recording",
        "duration": 10,  # Less than minimum (default 30)
        "body": base64.b64encode(b"test audio content").decode('utf-8')
    })
    mock_redis_with_vcon.get_vcon.return_value = vcon
    
    result = run("test-uuid", "groq_whisper")
    
    # Run should succeed but Groq client should not be called
    assert result == "test-uuid"
    mock_groq_client.audio.transcriptions.create.assert_not_called()

def test_run_skip_non_recording(mock_redis_with_vcon, mock_groq_client):
    """Test that run skips non-recording dialogs"""
    # Create a vCon with a non-recording dialog
    vcon = Vcon.build_new()
    vcon.add_dialog({
        "type": "text",
        "body": "This is a text message"
    })
    mock_redis_with_vcon.get_vcon.return_value = vcon
    
    result = run("test-uuid", "groq_whisper")
    
    # Run should succeed but Groq client should not be called
    assert result == "test-uuid"
    mock_groq_client.audio.transcriptions.create.assert_not_called()

@patch('server.links.groq_whisper.transcribe_groq_whisper')
def test_run_transcription_failure(mock_transcribe, mock_redis_with_vcon, sample_vcon):
    """Test handling of transcription failure"""
    # Make transcription function raise an exception
    mock_transcribe.side_effect = Exception("Transcription failed")
    
    result = run("test-uuid", "groq_whisper")
    
    # Run should return the vCon UUID despite the transcription failure
    assert result == "test-uuid"
    
    # Check that no analysis was added
    assert not any(a["type"] == "transcript" and a["vendor"] == "groq_whisper" 
                  for a in sample_vcon.analysis) 