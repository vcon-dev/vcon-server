import pytest
from unittest.mock import Mock, patch
from server.vcon import Vcon
from server.links.llama_link import run, default_options

# Mock response from llama-cpp-python
MOCK_LLM_RESPONSE = {
    "choices": [
        {
            "text": "This conversation shows good customer service skills. The agent was patient and helpful.",
            "finish_reason": "stop",
        }
    ]
}

# Sample transcript for testing
SAMPLE_TRANSCRIPT = "Customer: Hi, I need help with my account.\nAgent: I'll be happy to help you with that."


@pytest.fixture
def mock_vcon():
    """Create a mock vCon with a transcript dialog"""
    vcon = Vcon()
    vcon.uuid = "test-uuid"
    vcon.dialog = [
        {
            "type": "transcript",
            "body": {"text": SAMPLE_TRANSCRIPT},
        }
    ]
    vcon.analysis = []
    return vcon


@pytest.fixture
def mock_vcon_redis():
    """Create a mock VconRedis instance"""
    with patch("server.links.llama_link.VconRedis") as mock:
        redis_instance = Mock()
        mock.return_value = redis_instance
        yield redis_instance


@pytest.fixture
def mock_llama():
    """Create a mock Llama instance"""
    with patch("server.links.llama_link.Llama") as mock:
        llama_instance = Mock()
        llama_instance.return_value = MOCK_LLM_RESPONSE
        mock.return_value = llama_instance
        yield llama_instance


def test_run_successful_analysis(mock_vcon, mock_vcon_redis, mock_llama):
    """Test successful analysis of a transcript"""
    # Setup
    mock_vcon_redis.get_vcon.return_value = mock_vcon
    mock_llama.return_value = MOCK_LLM_RESPONSE

    # Run the link
    result = run("test-uuid", "test-link")

    # Verify
    assert result == "test-uuid"
    assert mock_vcon_redis.store_vcon.called
    stored_vcon = mock_vcon_redis.store_vcon.call_args[0][0]

    # Check analysis was added
    assert len(stored_vcon.analysis) == 1
    analysis = stored_vcon.analysis[0]
    assert analysis["type"] == "llm_analysis"
    assert analysis["vendor"] == "llama_cpp"
    assert analysis["dialog"] == 0
    assert analysis["body"] == MOCK_LLM_RESPONSE["choices"][0]["text"]


def test_run_model_initialization_failure(mock_vcon_redis, mock_llama):
    """Test handling of model initialization failure"""
    # Setup
    mock_llama.side_effect = Exception("Model initialization failed")

    # Run the link
    result = run("test-uuid", "test-link")

    # Verify
    assert result == "test-uuid"
    assert not mock_vcon_redis.store_vcon.called


def test_run_empty_transcript(mock_vcon, mock_vcon_redis, mock_llama):
    """Test handling of empty transcript"""
    # Setup
    mock_vcon.dialog[0]["body"]["text"] = ""
    mock_vcon_redis.get_vcon.return_value = mock_vcon

    # Run the link
    result = run("test-uuid", "test-link")

    # Verify
    assert result == "test-uuid"
    assert mock_vcon_redis.store_vcon.called
    assert len(mock_vcon.analysis) == 0


def test_run_non_transcript_dialog(mock_vcon, mock_vcon_redis, mock_llama):
    """Test handling of non-transcript dialog"""
    # Setup
    mock_vcon.dialog[0]["type"] = "recording"
    mock_vcon_redis.get_vcon.return_value = mock_vcon

    # Run the link
    result = run("test-uuid", "test-link")

    # Verify
    assert result == "test-uuid"
    assert mock_vcon_redis.store_vcon.called
    assert len(mock_vcon.analysis) == 0


def test_run_existing_analysis(mock_vcon, mock_vcon_redis, mock_llama):
    """Test handling of dialog that already has analysis"""
    # Setup
    mock_vcon.analysis = [{"type": "llm_analysis", "vendor": "llama_cpp", "dialog": 0, "body": "Existing analysis"}]
    mock_vcon_redis.get_vcon.return_value = mock_vcon

    # Run the link
    result = run("test-uuid", "test-link")

    # Verify
    assert result == "test-uuid"
    assert mock_vcon_redis.store_vcon.called
    assert len(mock_vcon.analysis) == 1
    assert mock_vcon.analysis[0]["body"] == "Existing analysis"


def test_run_with_custom_options(mock_vcon, mock_vcon_redis, mock_llama):
    """Test running with custom options"""
    # Setup
    custom_opts = {
        "model_path": "/custom/path/model.gguf",
        "max_tokens": 1000,
        "temperature": 0.5,
        "prompt_template": "Custom prompt: {text}",
    }
    mock_vcon_redis.get_vcon.return_value = mock_vcon

    # Run the link
    result = run("test-uuid", "test-link", custom_opts)

    # Verify
    assert result == "test-uuid"
    mock_llama.assert_called_with(
        model_path=custom_opts["model_path"],
        n_ctx=default_options["context_window"],
        n_gpu_layers=default_options["n_gpu_layers"],
    )


def test_run_analysis_generation_failure(mock_vcon, mock_vcon_redis, mock_llama):
    """Test handling of analysis generation failure"""
    # Setup
    mock_vcon_redis.get_vcon.return_value = mock_vcon
    mock_llama.return_value.side_effect = Exception("Analysis generation failed")

    # Run the link
    result = run("test-uuid", "test-link")

    # Verify
    assert result == "test-uuid"
    assert mock_vcon_redis.store_vcon.called
    assert len(mock_vcon.analysis) == 0
