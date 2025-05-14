import pytest
from unittest.mock import Mock, patch
from server.vcon import Vcon
from . import run, generate_analysis, get_analysys_for_type, navigate_dict


@pytest.fixture
def mock_vcon():
    """Create a sample vCon with transcript analysis for testing"""
    vcon = Vcon.build_new()
    # Add a dialog
    vcon.add_dialog({
        "type": "text",
        "body": "Hello world"
    })
    # Add a transcript analysis
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={
            "paragraphs": {
                "transcript": "This is a sample transcript that discusses customer service issues. "
                "The customer was very upset about a billing error that charged them "
                "twice for the same service. The representative apologized and offered "
                "a refund, which the customer accepted."
            }
        }
    )
    return vcon


@pytest.fixture
def mock_openai_response():
    message = {"content": "Test analysis", "role": "assistant"}
    choice = {"finish_reason": "stop", "index": 0, "message": message}
    return type('ChatCompletion', (), {
        'id': "test",
        'choices': [type('Choice', (), choice)()],
        'model': "gpt-3.5-turbo",
        'object': "chat.completion"
    })()


def test_get_analysys_for_type(mock_vcon):
    # Test finding existing analysis
    result = get_analysys_for_type(mock_vcon, 0, "transcript")
    assert result is not None
    assert result["type"] == "transcript"

    # Test non-existent analysis
    result = get_analysys_for_type(mock_vcon, 0, "non-existent")
    assert result is None

def test_navigate_dict():
    test_dict = {"a": {"b": {"c": "value"}}}
    
    assert navigate_dict(test_dict, "a.b.c") == "value"
    assert navigate_dict(test_dict, "a.b.d") is None
    assert navigate_dict(test_dict, "x.y.z") is None

@patch('openai.OpenAI')
def test_generate_analysis(mock_openai_client, mock_openai_response):
    client = Mock()
    client.chat.completions.create.return_value = mock_openai_response
    mock_openai_client.return_value = client

    result = generate_analysis(
        transcript="Test transcript",
        prompt="Test prompt",
        model="gpt-3.5-turbo",
        temperature=0,
        client=client
    )

    assert result == "Test analysis"
    client.chat.completions.create.assert_called_once()

@patch('lib.vcon_redis.VconRedis')
@patch('openai.OpenAI')
def test_run_happy_path(mock_openai_client, mock_redis, mock_vcon, mock_openai_response):
    # Setup mocks
    redis_instance = Mock()
    redis_instance.get_vcon.return_value = mock_vcon
    mock_redis.return_value = redis_instance

    client = Mock()
    client.chat.completions.create.return_value = mock_openai_response
    mock_openai_client.return_value = client

    # Test options
    test_opts = {
        "OPENAI_API_KEY": "test-key",
        "prompt": "Test prompt",
        "analysis_type": "summary",
        "model": "gpt-3.5-turbo",
        "sampling_rate": 1,
        "temperature": 0,
        "source": {
            "analysis_type": "transcript",
            "text_location": "body.paragraphs.transcript",
        },
    }

    # Run the function
    result = run("test-uuid", "test-link", test_opts)

    # Verify results
    assert result == "test-uuid"
    assert len(mock_vcon.analysis) == 2  # Original transcript + new analysis
    assert mock_vcon.analysis[-1]["type"] == "summary"
    redis_instance.store_vcon.assert_called_once_with(mock_vcon)

@patch('lib.vcon_redis.VconRedis')
def test_run_with_existing_analysis(mock_redis, mock_vcon):
    # Add existing analysis
    mock_vcon.analysis.append({
        "dialog": 0,
        "type": "summary",
        "body": "Existing summary"
    })
    
    redis_instance = Mock()
    redis_instance.get_vcon.return_value = mock_vcon
    mock_redis.return_value = redis_instance

    test_opts = {
        "OPENAI_API_KEY": "test-key",
        "analysis_type": "summary",
        "sampling_rate": 1,
    }

    result = run("test-uuid", "test-link", test_opts)

    assert result == "test-uuid"
    # Verify no new analysis was added
    assert len(mock_vcon.analysis) == 2
    redis_instance.store_vcon.assert_called_once_with(mock_vcon)

def test_run_with_sampling():
    test_opts = {"sampling_rate": 0}  # Should always skip
    result = run("test-uuid", "test-link", test_opts)
    assert result == "test-uuid"
