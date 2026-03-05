import os
import pytest
import tempfile
import hashlib
from unittest.mock import patch, MagicMock, mock_open
import base64
import io
import wave
import math
import importlib.util
import sys

# Clear any proxy environment variables that might interfere with the Groq client
def clear_proxy_env_vars():
    """Clear all proxy-related environment variables to prevent issues with the Groq client."""
    proxy_vars = [
        'HTTP_PROXY', 'HTTPS_PROXY', 'NO_PROXY', 
        'http_proxy', 'https_proxy', 'no_proxy'
    ]
    for var in proxy_vars:
        if var in os.environ:
            print(f"Removing proxy environment variable: {var}")
            del os.environ[var]

# Clear proxy settings before importing
clear_proxy_env_vars()

from server.links.groq_whisper import run, transcribe_groq_whisper, get_file_content, get_transcription
from server.vcon import Vcon

# Print current API key status (for debugging)
print(f"\nCurrent API key status at module import time:")
print(f"Raw env value: {os.environ.get('GROQ_API_KEY', 'Not set')[:4]}...")
print(f"Will integration tests run? {'No' if os.environ.get('GROQ_API_KEY', '') in ['', 'test_api_key_for_testing', 'YOUR_GROQ_API_KEY'] else 'Yes'}")
print()

# Check if pyttsx3 is available for text-to-speech
PYTTSX3_AVAILABLE = importlib.util.find_spec("pyttsx3") is not None

# Only set a test API key if one isn't already provided
if os.environ.get("GROQ_API_KEY", "") not in ["", "YOUR_GROQ_API_KEY"]:
    # Use the existing API key (might be a real one)
    print(f"Using provided GROQ_API_KEY: {os.environ.get('GROQ_API_KEY')[:4]}...")
else:
    # Set environment variable for testing
    os.environ["GROQ_API_KEY"] = "test_api_key_for_testing"
    print("Using test API key (integration tests will be skipped)")

# Check if we should run the real integration tests
# Integration tests are skipped if:
# - No GROQ_API_KEY environment variable is set
# - GROQ_API_KEY is empty
# - GROQ_API_KEY is the test placeholder
SKIP_INTEGRATION_TESTS = os.environ.get("GROQ_API_KEY", "") in ["", "test_api_key_for_testing", "YOUR_GROQ_API_KEY"]

"""
INTEGRATION TESTING GUIDE
-------------------------
This test file contains two types of tests:
1. Unit tests (using mocks) - Always run
2. Integration tests (real API calls) - Only run with valid API key

To run only unit tests:
  poetry run pytest server/links/groq_whisper/test_groq_whisper.py -k "not TestGroqWhisperIntegration"

To run integration tests:
  GROQ_API_KEY=your_api_key poetry run python -m server.links.groq_whisper.test_groq_whisper

To run all tests:
  GROQ_API_KEY=your_api_key poetry run pytest server/links/groq_whisper/test_groq_whisper.py -v

IMPORTANT: Integration tests make real API calls and may incur charges!
"""

# Function to create a small audio file for testing
def create_test_audio_file(filename, duration=2):
    """Create a small WAV file with duration in seconds"""
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # Generate silence with some noise (to avoid empty audio detection)
        frames = b'\x01\x00' * int(16000 * duration)
        wf.writeframes(frames)
    
    # Convert WAV to bytes for vCon
    with open(filename, 'rb') as f:
        return f.read()

# Integration tests that actually call the Groq API
@pytest.mark.skipif(SKIP_INTEGRATION_TESTS, reason="Groq API key not configured")
class TestGroqWhisperIntegration:
    """Integration tests for Groq Whisper transcription service.
    These tests will be skipped if GROQ_API_KEY is not set to a valid key."""
    
    @pytest.fixture
    def audio_content(self):
        """Create a temporary audio file and return its content"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            audio_file = f.name
        
        try:
            content = create_test_audio_file(audio_file)
            yield content
        finally:
            # Clean up temporary file
            if os.path.exists(audio_file):
                os.remove(audio_file)

    @pytest.fixture
    def test_vcon_with_audio(self, audio_content):
        """Create a test vCon with audio recording"""
        vcon = Vcon.build_new()
        vcon.add_dialog({
            "type": "recording",
            "duration": 60,  # 60 seconds duration
            "body": base64.b64encode(audio_content).decode('utf-8'),
            "mime": "audio/wav"  # Wave format
        })
        return vcon

    @pytest.fixture
    def mock_vcon_redis_with_real_vcon(self, test_vcon_with_audio):
        """Set up a mock VconRedis that returns our test vCon but allows actual storage"""
        with patch('server.links.groq_whisper.VconRedis') as mock:
            mock_instance = MagicMock()
            mock_instance.get_vcon.return_value = test_vcon_with_audio
            # Allow real store_vcon to be tracked
            mock_instance.store_vcon = MagicMock()
            mock.return_value = mock_instance
            yield mock_instance, test_vcon_with_audio

    def test_real_transcription(self, audio_content):
        """Test actual transcription with real Groq API"""
        # Ensure all proxy env vars are cleared before test
        clear_proxy_env_vars()
        
        print("\n==== DEBUG INFO ====")
        print(f"Python version: {sys.version}")
        print(f"Proxy environment variables: {[(k, v) for k, v in os.environ.items() if 'proxy' in k.lower()]}")
        try:
            import httpx
            print(f"httpx version: {httpx.__version__}")
            # Verify our monkey patching is in effect
            print(f"httpx.Client patched: {httpx.Client.__name__ != 'Client'}")
        except ImportError:
            print("httpx not available")
        try:
            import groq
            print(f"groq version: {groq.__version__ if hasattr(groq, '__version__') else 'unknown'}")
        except ImportError:
            print("groq not available")
        print("====================\n")
            
        # Prepare real dialog and options
        dialog = {
            "body": base64.b64encode(audio_content).decode('utf-8')
        }
        
        # Use only the API key to avoid proxy issues
        api_key = os.environ["GROQ_API_KEY"]
        print(f"Using API key: {api_key[:4]}...")
        opts = {"API_KEY": api_key}
        
        # Call actual transcription function without mocks
        print("Calling transcribe_groq_whisper...")
        result = transcribe_groq_whisper(dialog, opts)
        
        # Verify results
        assert result is not None
        assert hasattr(result, 'text')
        print(f"Actual transcription result: {result.text}")
        
        # Test model_dump method works
        if hasattr(result, 'model_dump'):
            result_dict = result.model_dump()
            assert "text" in result_dict

    def test_run_with_real_api(self, mock_vcon_redis_with_real_vcon):
        """Test run function with real API integration"""
        mock_redis, vcon = mock_vcon_redis_with_real_vcon
        
        # Configure options with real API key
        opts = {
            "API_KEY": os.environ["GROQ_API_KEY"],
            "minimum_duration": 0  # Allow short recordings for testing
        }
        
        # Call run with the real API
        result = run("test-uuid", "groq_whisper", opts)
        
        # Verify results
        assert result == "test-uuid"
        
        # Verify vCon was modified and stored
        mock_redis.store_vcon.assert_called_once()
        
        # Verify transcript was added
        assert any(
            a["type"] == "transcript" and a["vendor"] == "groq_whisper" 
            for a in vcon.analysis
        )
        
        # Print actual transcription result
        transcript = next(
            (a for a in vcon.analysis if a["type"] == "transcript" and a["vendor"] == "groq_whisper"),
            None
        )
        if transcript:
            print(f"Integration test transcript: {transcript['body']['text']}")
            
    def test_speech_transcription(self):
        """Test transcription with a realistic speech sample 
        This test creates an audio file with a tone that changes frequency,
        simulating a basic speech pattern."""
        
        # Skip test if API key not configured
        if SKIP_INTEGRATION_TESTS:
            pytest.skip("Groq API key not configured")
            
        # Create a WAV file with changing tones to better simulate speech
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            audio_file = temp_file.name
            
        try:
            # Create a 3-second WAV file with changing frequency tones
            with wave.open(audio_file, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                
                # Generate changing tones to better test transcription
                frames = bytearray()
                for freq in [440, 880, 1320]:  # A4, A5, E6 notes
                    # Generate a sine wave tone for 1 second
                    for i in range(16000):
                        # Simple sine wave calculation with 16-bit amplitude
                        sample = int(10000 * math.sin(2 * math.pi * freq * i / 16000))
                        # Convert to 16-bit PCM
                        frames.extend(sample.to_bytes(2, byteorder='little', signed=True))
                
                wf.writeframes(bytes(frames))
            
            # Read the generated audio file
            with open(audio_file, 'rb') as f:
                audio_content = f.read()
                
            # Base64 encode for vCon
            encoded_audio = base64.b64encode(audio_content).decode('utf-8')
            
            # Create a dialog object for the test
            dialog = {
                "body": encoded_audio,
                "mime": "audio/wav"
            }
            
            # Transcribe using Groq Whisper
            opts = {"API_KEY": os.environ["GROQ_API_KEY"]}
            result = transcribe_groq_whisper(dialog, opts)
            
            # Verify results
            assert result is not None
            assert hasattr(result, 'text')
            
            # In a real transcription, there might not be much actual text recognized
            # from pure tones, but the API should still return something
            print(f"Speech sample transcription result: {result.text}")
            
        finally:
            # Clean up
            if os.path.exists(audio_file):
                os.remove(audio_file)

    @pytest.mark.skipif(not PYTTSX3_AVAILABLE or SKIP_INTEGRATION_TESTS, 
                       reason="Requires pyttsx3 and Groq API key")
    def test_text_to_speech_transcription(self):
        """Test transcription with real synthesized speech
        This test uses pyttsx3 to generate realistic speech audio."""
        
        import pyttsx3
        
        # Create a temporary file for the speech audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
            audio_file = temp_file.name
            
        try:
            # Text to transcribe
            test_text = "This is a test of the Groq Whisper transcription service. Testing one two three."
            
            # Initialize the TTS engine
            engine = pyttsx3.init()
            engine.setProperty('rate', 150)  # Speed of speech
            
            # Generate speech audio file
            engine.save_to_file(test_text, audio_file)
            engine.runAndWait()
            
            # Read the generated audio file
            with open(audio_file, 'rb') as f:
                audio_content = f.read()
                
            # Base64 encode for vCon
            encoded_audio = base64.b64encode(audio_content).decode('utf-8')
            
            # Create a dialog object for the test
            dialog = {
                "body": encoded_audio,
                "mime": "audio/wav"
            }
            
            # Transcribe using Groq Whisper
            opts = {"API_KEY": os.environ["GROQ_API_KEY"]}
            result = transcribe_groq_whisper(dialog, opts)
            
            # Verify results
            assert result is not None
            assert hasattr(result, 'text')
            
            # Print the result
            print(f"TTS transcription result: {result.text}")
            print(f"Original text: {test_text}")
            
            # Check for similarity with original text (not exact match due to TTS/transcription variations)
            # Convert to lowercase and remove punctuation for comparison
            import re
            clean_result = re.sub(r'[^\w\s]', '', result.text.lower())
            clean_original = re.sub(r'[^\w\s]', '', test_text.lower())
            
            # Check if key words are present
            key_words = ["test", "groq", "whisper", "transcription"]
            for word in key_words:
                if word in clean_original:
                    assert word in clean_result, f"Expected word '{word}' not found in transcription"
            
        finally:
            # Clean up
            if os.path.exists(audio_file):
                os.remove(audio_file)

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
    """Mock the Groq client for the audio transcription API"""
    with patch('server.links.groq_whisper.Groq') as mock_groq:
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        
        # Create mock audio service and transcriptions
        mock_audio = MagicMock()
        mock_client.audio = mock_audio
        
        mock_transcriptions = MagicMock()
        mock_audio.transcriptions = mock_transcriptions
        
        # Mock the create method to return a successful response
        mock_response = MagicMock()
        mock_response.text = "This is a test transcription"
        mock_response.model_dump = MagicMock(return_value={
            "text": "This is a test transcription",
            "chunks": [{"text": "This is a test transcription"}],
            "language": "en"
        })
        mock_transcriptions.create.return_value = mock_response
        
        # Setup logging for debugging
        print(f"Mocked Groq client structure: {mock_client}")
        print(f"Mocked audio.transcriptions: {mock_client.audio.transcriptions}")
        
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
        with patch("tempfile.NamedTemporaryFile", return_value=MagicMock(
            name="test_file.flac",
            __enter__=MagicMock(return_value=MagicMock(
                name="test_file.flac", 
                flush=MagicMock()
            ))
        )):
            result = transcribe_groq_whisper(dialog, opts)
            
            # Verify result
            assert result is not None
            assert hasattr(result, 'text')
            assert result.text == "This is a test transcription"
            
            # Verify Groq client was called correctly
            mock_groq_client.audio.transcriptions.create.assert_called_once()
            call_args = mock_groq_client.audio.transcriptions.create.call_args
            
            # First arg should be a tuple with filename and file content
            assert isinstance(call_args[1]["file"], tuple)
            assert call_args[1]["model"] in ["whisper-large-v3-turbo", "distil-whisper-large-v3-en"]
            assert call_args[1]["response_format"] in ["json", "verbose_json"]

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

# Add main block to allow running just the integration tests from command line
if __name__ == "__main__":
    # Check if just querying status
    if os.environ.get("CHECK_KEY_STATUS") == "1":
        print("\n======= API KEY STATUS CHECK =======")
        print(f"Raw env API key value: {os.environ.get('GROQ_API_KEY', 'Not set')[:4]}...")
        will_run = os.environ.get('GROQ_API_KEY', '') not in ['', 'test_api_key_for_testing', 'YOUR_GROQ_API_KEY']
        print(f"Will integration tests run? {'Yes' if will_run else 'No'}")
        print(f"SKIP_INTEGRATION_TESTS value: {SKIP_INTEGRATION_TESTS}")
        print("====================================\n")
        exit(0)
        
    # Check if a real GROQ_API_KEY is provided and valid
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or api_key in ["test_api_key_for_testing", "YOUR_GROQ_API_KEY"]:
        print("\n======================================================================")
        print("WARNING: No valid GROQ_API_KEY environment variable found.")
        print("Integration tests will be skipped.")
        print("\nTo run integration tests with a real API key:")
        print("GROQ_API_KEY=your_api_key poetry run python -m server.links.groq_whisper.test_groq_whisper")
        print("======================================================================\n")
        exit(1)
    
    # Run just the integration tests
    print(f"\n======================================================================")
    print(f"Running Groq Whisper integration tests with API key: {api_key[:4]}...")
    print(f"These tests will make REAL API calls to Groq and may incur charges!")
    print(f"======================================================================\n")
    pytest.main(["-xvs", __file__, "-k", "TestGroqWhisperIntegration"]) 