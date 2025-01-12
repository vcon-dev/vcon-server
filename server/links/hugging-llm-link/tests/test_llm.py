"""Tests for the HuggingFace LLM vCon link."""

import sys
from pathlib import Path

# Add parent directory to path to allow importing the package
sys.path.append(str(Path(__file__).parent.parent))

import pytest
from unittest.mock import MagicMock, patch
from hugging_llm_link import (
    LLMConfig,
    HuggingFaceLLM,
    VConLLMProcessor,
)


@pytest.fixture
def config():
    """Fixture for LLMConfig with test values."""
    return LLMConfig(huggingface_api_key="test-key")


@pytest.fixture
def llm(config):
    """Fixture for HuggingFaceLLM instance."""
    return HuggingFaceLLM(config)


@pytest.fixture
def processor(config):
    """Fixture for VConLLMProcessor instance."""
    processor = VConLLMProcessor(config)
    processor.vcon_redis = MagicMock()
    return processor


def test_config_from_dict_with_defaults():
    """Test creating config from empty dict uses defaults."""
    config = LLMConfig.from_dict({})
    assert config.model == "meta-llama/Llama-2-70b-chat-hf"
    assert config.use_local_model is False
    assert config.max_length == 1000
    assert config.temperature == 0.7
    assert config.huggingface_api_key is None


def test_config_from_dict_with_values():
    """Test creating config with custom values."""
    config_dict = {
        "HUGGINGFACE_API_KEY": "test-key",
        "model": "test-model",
        "use_local_model": True,
        "max_length": 500,
        "temperature": 0.5,
    }
    config = LLMConfig.from_dict(config_dict)
    assert config.huggingface_api_key == "test-key"
    assert config.model == "test-model"
    assert config.use_local_model is True
    assert config.max_length == 500
    assert config.temperature == 0.5


@pytest.mark.anyio
async def test_analyze_success(llm):
    """Test successful API analysis."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"generated_text": "test analysis"}]
        mock_post.return_value = mock_response

        result = await llm.analyze("test text")

        assert result["analysis"] == "test analysis"
        assert result["model"] == llm.config.model
        assert result["parameters"] == {
            "max_length": llm.config.max_length,
            "temperature": llm.config.temperature,
        }


@pytest.mark.anyio
async def test_analyze_api_error(llm):
    """Test API error handling."""
    with patch("requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "API Error"
        mock_post.return_value = mock_response

        with pytest.raises(Exception) as exc_info:
            await llm.analyze("test text")
        assert "Hugging Face API error" in str(exc_info.value)


def test_get_transcript_text(processor):
    """Test transcript text extraction."""
    mock_vcon = MagicMock()
    mock_vcon.analysis = [
        {
            "type": "transcript",
            "body": {"transcript": "test transcript 1"},
        },
        {
            "type": "transcript",
            "body": {"transcript": "test transcript 2"},
        },
    ]

    result = processor._get_transcript_text(mock_vcon)
    assert result == "test transcript 1\ntest transcript 2"


def test_get_llm_analysis_exists(processor):
    """Test retrieving existing LLM analysis."""
    mock_vcon = MagicMock()
    mock_analysis = {"type": "llm_analysis", "body": {"test": "data"}}
    mock_vcon.analysis = [mock_analysis]

    result = processor._get_llm_analysis(mock_vcon)
    assert result == mock_analysis


def test_get_llm_analysis_not_exists(processor):
    """Test when no LLM analysis exists."""
    mock_vcon = MagicMock()
    mock_vcon.analysis = []

    result = processor._get_llm_analysis(mock_vcon)
    assert result is None
