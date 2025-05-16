import os
import pytest
from unittest.mock import Mock, patch
import json
from tenacity import RetryError
from server.links.detect_engagement import (
    check_engagement,
    get_analysis_for_type,
    navigate_dict,
    run,
    default_options,
)
import openai
from openai import OpenAI

# Test data
MOCK_TRANSCRIPT = """
Agent: Hello, how can I help you today?
Customer: Hi, I'm having trouble with my account.
Agent: I'd be happy to help. Could you tell me more about the issue?
Customer: Yes, I can't log in to my account.
"""

MOCK_ONE_SIDED_TRANSCRIPT = """
Agent: Hello, how can I help you today?
Agent: Is anyone there?
Agent: I'll wait a moment for your response.
"""

@pytest.fixture
def mock_vcon():
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
    with patch("server.links.detect_engagement.VconRedis") as mock:
        redis = Mock()
        redis.get_vcon.return_value = mock_vcon
        mock.return_value = redis
        yield redis

def test_get_analysis_for_type():
    analysis = {"dialog": 0, "type": "test_type", "body": "test"}
    vcon = Mock()
    vcon.analysis = [analysis]
    
    result = get_analysis_for_type(vcon, 0, "test_type")
    assert result == analysis
    
    result = get_analysis_for_type(vcon, 0, "nonexistent")
    assert result is None

def test_navigate_dict():
    test_dict = {
        "level1": {
            "level2": {
                "level3": "value"
            }
        }
    }
    
    assert navigate_dict(test_dict, "level1.level2.level3") == "value"
    assert navigate_dict(test_dict, "level1.nonexistent") is None
    assert navigate_dict(test_dict, "nonexistent") is None

def skip_if_no_openai_key():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set in environment, skipping test.")

@pytest.mark.asyncio
async def test_check_engagement_engaged():
    skip_if_no_openai_key()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    result = check_engagement(
        MOCK_TRANSCRIPT,
        default_options["prompt"],
        default_options["model"],
        default_options["temperature"],
        client
    )
    assert result is True

@pytest.mark.asyncio
async def test_check_engagement_not_engaged():
    skip_if_no_openai_key()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    result = check_engagement(
        MOCK_ONE_SIDED_TRANSCRIPT,
        default_options["prompt"],
        default_options["model"],
        default_options["temperature"],
        client
    )
    assert result is False

def test_run_skips_if_no_transcript(mock_redis, mock_vcon):
    mock_redis.get_vcon.return_value = mock_vcon
    mock_vcon.analysis = []
    result = run("test-uuid", "test-link", {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "test-key")})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_not_called()
    mock_vcon.add_tag.assert_not_called()

def test_run_processes_transcript(mock_redis, mock_vcon):
    skip_if_no_openai_key()
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
    result = run("test-uuid", "test-link", {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_called_once()
    mock_vcon.add_tag.assert_called_once_with(tag_name="engagement", tag_value="true")

def test_run_handles_api_error(mock_redis, mock_vcon):
    skip_if_no_openai_key()
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
    # Intentionally pass an invalid API key to trigger an error
    with pytest.raises(Exception):
        run("test-uuid", "test-link", {"OPENAI_API_KEY": "invalid-key"})
    mock_vcon.add_analysis.assert_not_called()
    mock_vcon.add_tag.assert_not_called()

def test_run_respects_sampling_rate(mock_redis, mock_vcon):
    skip_if_no_openai_key()
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
    with patch("server.links.detect_engagement.randomly_execute_with_sampling", return_value=False):
        result = run("test-uuid", "test-link", {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"), "sampling_rate": 0})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_not_called()

def test_run_skips_existing_analysis(mock_redis, mock_vcon):
    skip_if_no_openai_key()
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
    result = run("test-uuid", "test-link", {"OPENAI_API_KEY": os.getenv("OPENAI_API_KEY")})
    assert result == "test-uuid"
    mock_vcon.add_analysis.assert_not_called()
    mock_vcon.add_tag.assert_not_called() 