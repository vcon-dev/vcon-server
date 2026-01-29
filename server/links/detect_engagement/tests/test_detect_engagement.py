"""
Unit tests for the detect_engagement link in the Vcon server.

These tests cover the engagement detection logic, including:
- Analysis extraction and navigation
- LLM client integration for engagement detection (supports OpenAI, Anthropic, LiteLLM)
- Handling of missing transcripts, API errors, and sampling logic
- Ensuring correct tagging and analysis addition

Environment variables are loaded from .env using python-dotenv.
"""
import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from server.links.detect_engagement import (
    check_engagement,
    get_analysis_for_type,
    navigate_dict,
    run,
    default_options,
)
from lib.llm_client import LLMResponse, create_llm_client
from dotenv import load_dotenv

# Load environment variables from .env file for API keys, etc.
load_dotenv()

# ----------------------
# Test Data Definitions
# ----------------------

# A sample transcript with both agent and customer speaking (should be considered engaged)
MOCK_TRANSCRIPT = """
Agent: Hello, how can I help you today?
Customer: Hi, I'm having trouble with my account.
Agent: I'd be happy to help. Could you tell me more about the issue?
Customer: Yes, I can't log in to my account.
"""

# A transcript with only the agent speaking (should be considered not engaged)
MOCK_ONE_SIDED_TRANSCRIPT = """
Agent: Hello, how can I help you today?
Agent: Is anyone there?
Agent: I'll wait a moment for your response.
"""

@pytest.fixture
def mock_vcon():
    """
    Returns a mock Vcon object with minimal attributes and methods for testing.
    """
    vcon = Mock()
    vcon.uuid = "test-uuid"
    # Create a mock dialog with necessary attributes
    mock_dialog = Mock()
    mock_dialog.uuid = "dialog-uuid"
    mock_dialog.type = "dialog"
    vcon.dialog = [mock_dialog]
    vcon.analysis = []
    vcon.add_analysis = Mock()
    vcon.add_tag = Mock()
    return vcon

@pytest.fixture
def mock_redis(mock_vcon):
    """
    Patches VconRedis to return the mock Vcon object for testing.
    """
    with patch("server.links.detect_engagement.VconRedis") as mock:
        redis = Mock()
        redis.get_vcon.return_value = mock_vcon
        mock.return_value = redis
        yield redis

def test_get_analysis_for_type():
    """
    Test that get_analysis_for_type returns the correct analysis dict for a given type and dialog index.
    """
    analysis = {"dialog": 0, "type": "test_type", "body": "test"}
    vcon = Mock()
    vcon.analysis = [analysis]
    
    result = get_analysis_for_type(vcon, 0, "test_type")
    assert result == analysis
    
    # Should return None if type does not exist
    result = get_analysis_for_type(vcon, 0, "nonexistent")
    assert result is None

def test_navigate_dict():
    """
    Test that navigate_dict can traverse nested dictionaries using dot notation.
    """
    test_dict = {
        "level1": {
            "level2": {
                "level3": "value"
            }
        }
    }
    # Should return the value at the nested path
    assert navigate_dict(test_dict, "level1.level2.level3") == "value"
    # Should return None for a non-existent path
    assert navigate_dict(test_dict, "level1.nonexistent") is None
    assert navigate_dict(test_dict, "nonexistent") is None

def skip_if_no_openai_key():
    """
    Skip the test if OPENAI_API_KEY is not set in the environment.
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set in environment, skipping test.")


def test_check_engagement_engaged():
    """
    Test that check_engagement returns True for a transcript with both agent and customer speaking.
    Uses mocked LLM client.
    """
    # Set up mock LLM client
    mock_client = Mock()
    mock_response = LLMResponse(
        content="true",
        model="gpt-4.1",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response

    opts = {"prompt": default_options["prompt"]}
    is_engaged, response = check_engagement(
        MOCK_TRANSCRIPT,
        default_options["prompt"],
        mock_client,
        "test-uuid",
        opts
    )
    assert is_engaged is True
    assert response.content == "true"


def test_check_engagement_not_engaged():
    """
    Test that check_engagement returns False for a transcript with only the agent speaking.
    Uses mocked LLM client.
    """
    # Set up mock LLM client
    mock_client = Mock()
    mock_response = LLMResponse(
        content="false",
        model="gpt-4.1",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response

    opts = {"prompt": default_options["prompt"]}
    is_engaged, response = check_engagement(
        MOCK_ONE_SIDED_TRANSCRIPT,
        default_options["prompt"],
        mock_client,
        "test-uuid",
        opts
    )
    assert is_engaged is False
    assert response.content == "false"

def test_run_skips_if_no_transcript(mock_redis, mock_vcon):
    """
    Test that run does nothing if there is no transcript analysis present.
    Should not add analysis or tag.
    """
    mock_redis.get_vcon.return_value = mock_vcon
    mock_vcon.analysis = []
    result = run("test-uuid", "test-link", {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "test-key")})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_not_called()
    mock_vcon.add_tag.assert_not_called()


@patch('server.links.detect_engagement.create_llm_client')
def test_run_processes_transcript(mock_create_client, mock_redis, mock_vcon):
    """
    Test that run processes a valid transcript and adds analysis and tag if engagement is detected.
    """
    # Set up mock LLM client
    mock_client = Mock()
    mock_response = LLMResponse(
        content="true",
        model="gpt-4.1",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        raw_response=None,
        provider="openai"
    )
    mock_client.complete_with_tracking.return_value = mock_response
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    transcript_analysis = {
        "dialog": 0,
        "type": "transcript",
        "body": {
            "paragraphs": {
                "transcript": MOCK_TRANSCRIPT
            }
        }
    }
    mock_vcon.analysis = [transcript_analysis]
    result = run("test-uuid", "test-link", {"OPENAI_API_KEY": "test-key"})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_called_once()
    mock_vcon.add_tag.assert_called_once_with(tag_name="engagement", tag_value="true")


@patch('server.links.detect_engagement.create_llm_client')
def test_run_handles_api_error(mock_create_client, mock_redis, mock_vcon):
    """
    Test that run handles LLM API errors gracefully and does not add analysis or tag.
    """
    # Set up mock LLM client to raise exception
    mock_client = Mock()
    mock_client.complete_with_tracking.side_effect = Exception("API Error")
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    transcript_analysis = {
        "dialog": 0,
        "type": "transcript",
        "body": {
            "paragraphs": {
                "transcript": MOCK_TRANSCRIPT
            }
        }
    }
    mock_vcon.analysis = [transcript_analysis]
    with pytest.raises(Exception):
        run("test-uuid", "test-link", {"OPENAI_API_KEY": "test-key"})
    mock_vcon.add_analysis.assert_not_called()
    mock_vcon.add_tag.assert_not_called()


def test_run_respects_sampling_rate(mock_redis, mock_vcon):
    """
    Test that run respects the sampling rate and skips processing if randomly_execute_with_sampling returns False.
    """
    transcript_analysis = {
        "dialog": 0,
        "type": "transcript",
        "body": {
            "paragraphs": {
                "transcript": MOCK_TRANSCRIPT
            }
        }
    }
    mock_vcon.analysis = [transcript_analysis]
    # Patch randomly_execute_with_sampling to always return False (simulate skipping)
    with patch("server.links.detect_engagement.randomly_execute_with_sampling", return_value=False):
        result = run("test-uuid", "test-link", {"OPENAI_API_KEY": "test-key", "sampling_rate": 0})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_not_called()


@patch('server.links.detect_engagement.create_llm_client')
def test_run_skips_existing_analysis(mock_create_client, mock_redis, mock_vcon):
    """
    Test that run skips processing if engagement_analysis already exists for the dialog.
    """
    # Set up mock LLM client (should not be called)
    mock_client = Mock()
    mock_client.provider_name = "openai"
    mock_create_client.return_value = mock_client

    transcript_analysis = {
        "dialog": 0,
        "type": "transcript",
        "body": {
            "paragraphs": {
                "transcript": MOCK_TRANSCRIPT
            }
        }
    }
    existing_analysis = {
        "dialog": 0,
        "type": "engagement_analysis",
        "body": "true"
    }
    mock_vcon.analysis = [transcript_analysis, existing_analysis]
    result = run("test-uuid", "test-link", {"OPENAI_API_KEY": "test-key"})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_not_called()
    mock_vcon.add_tag.assert_not_called()
    mock_client.complete_with_tracking.assert_not_called()