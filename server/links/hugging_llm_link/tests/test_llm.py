# """Tests for the HuggingFace LLM vCon link."""

# import sys
# from pathlib import Path
# import pytest
# from unittest.mock import MagicMock, patch
# from tenacity import retry, wait_exponential, stop_after_attempt, RetryError

# # Add the server directory to the Python path
# server_dir = str(Path(__file__).parent.parent.parent.parent)
# if server_dir not in sys.path:
#     sys.path.append(server_dir)

# from links.hugging_llm_link import (  # noqa: E402
#     LLMConfig,
#     HuggingFaceLLM,
#     VConLLMProcessor,
# )


# @pytest.fixture
# def config():
#     """Fixture for LLMConfig with test values."""
#     return LLMConfig(huggingface_api_key="test-key")


# @pytest.fixture
# def llm(config):
#     """Fixture for HuggingFaceLLM instance."""
#     return HuggingFaceLLM(config)


# @pytest.fixture
# def processor(config):
#     """Fixture for VConLLMProcessor instance."""
#     processor = VConLLMProcessor(config)
#     processor.vcon_redis = MagicMock()
#     return processor


# @pytest.fixture
# def local_config():
#     """Fixture for LLMConfig with local model settings."""
#     return LLMConfig(
#         model="gpt2",  # Using the default GPT-2 model
#         use_local_model=True,
#         max_length=100,  # Smaller output for testing
#         temperature=0.7,
#     )


# def test_config_from_dict_with_defaults():
#     """Test creating config from empty dict uses defaults."""
#     config = LLMConfig.from_dict({})
#     assert config.model == "meta-llama/Llama-2-70b-chat-hf"
#     assert config.use_local_model is False
#     assert config.max_length == 1000
#     assert config.temperature == 0.7
#     assert config.huggingface_api_key is None


# def test_config_from_dict_with_values():
#     """Test creating config with custom values."""
#     config_dict = {
#         "HUGGINGFACE_API_KEY": "test-key",
#         "model": "test-model",
#         "use_local_model": True,
#         "max_length": 500,
#         "temperature": 0.5,
#     }
#     config = LLMConfig.from_dict(config_dict)
#     assert config.huggingface_api_key == "test-key"
#     assert config.model == "test-model"
#     assert config.use_local_model is True
#     assert config.max_length == 500
#     assert config.temperature == 0.5


# @pytest.mark.anyio
# async def test_analyze_success(llm):
#     """Test successful API analysis."""
#     with patch("requests.post") as mock_post:
#         mock_response = MagicMock()
#         mock_response.status_code = 200
#         mock_response.json.return_value = [{"generated_text": "test analysis"}]
#         mock_post.return_value = mock_response

#         result = await llm.analyze("test text")

#         assert result["analysis"] == "test analysis"
#         assert result["model"] == llm.config.model
#         assert result["parameters"] == {
#             "max_length": llm.config.max_length,
#             "temperature": llm.config.temperature,
#         }


# @pytest.mark.anyio
# async def test_analyze_api_error(llm):
#     """Test API error handling."""
#     # Override retry settings for faster tests
#     llm.analyze.retry.wait = wait_exponential(multiplier=0.1, min=0.1, max=0.3)
#     llm.analyze.retry.stop = stop_after_attempt(3)

#     with patch("requests.post") as mock_post:
#         mock_response = MagicMock()
#         mock_response.status_code = 400
#         mock_response.text = "API Error"
#         mock_post.return_value = mock_response

#         with pytest.raises(RetryError) as exc_info:
#             await llm.analyze("test text")
#         # The original error should be wrapped in the RetryError
#         assert isinstance(exc_info.value.last_attempt.exception(), Exception)
#         assert "Hugging Face API error" in str(exc_info.value.last_attempt.exception())


# def test_get_transcript_text(processor):
#     """Test transcript text extraction."""
#     mock_vcon = MagicMock()
#     mock_vcon.analysis = [
#         {
#             "type": "transcript",
#             "body": {"transcript": "test transcript 1"},
#         },
#         {
#             "type": "transcript",
#             "body": {"transcript": "test transcript 2"},
#         },
#     ]

#     result = processor._get_transcript_text(mock_vcon)
#     assert result == "test transcript 1\ntest transcript 2"


# def test_get_llm_analysis_exists(processor):
#     """Test retrieving existing LLM analysis."""
#     mock_vcon = MagicMock()
#     mock_analysis = {"type": "llm_analysis", "body": {"test": "data"}}
#     mock_vcon.analysis = [mock_analysis]

#     result = processor._get_llm_analysis(mock_vcon)
#     assert result == mock_analysis


# def test_get_llm_analysis_not_exists(processor):
#     """Test when no LLM analysis exists."""
#     mock_vcon = MagicMock()
#     mock_vcon.analysis = []

#     result = processor._get_llm_analysis(mock_vcon)
#     assert result is None


# def test_local_llm_analysis(local_config, caplog, monkeypatch):
#     """Test local LLM analysis with a real vCon file."""
#     import logging
#     from huggingface_hub import HfFolder

#     # Set up offline mode by setting an invalid token
#     monkeypatch.setattr(HfFolder, "get_token", lambda: "invalid_token")

#     # Set up detailed logging
#     caplog.set_level(logging.DEBUG)

#     # Create a mock vCon with test data
#     mock_vcon = MagicMock()
#     mock_vcon.analysis = [
#         {
#             "type": "transcript",
#             "body": {
#                 "transcript": "Hello! This is a test conversation.\nHow are you today?\nI'm doing well, thank you!"
#             },
#         }
#     ]
#     mock_vcon.add_analysis = MagicMock()

#     # Initialize processor with local config
#     @retry(wait=wait_exponential(multiplier=1, min=4, max=10), stop=stop_after_attempt(3))
#     def init_processor():
#         processor = VConLLMProcessor(local_config)
#         processor.vcon_redis.get_vcon = MagicMock(return_value=mock_vcon)
#         processor.vcon_redis.store_vcon = MagicMock()
#         return processor

#     # Process the vCon with retry
#     logging.info("Starting local LLM analysis test")
#     processor = init_processor()
#     result = processor.process_vcon("test-uuid", "test-link")

#     # Verify the results
#     assert result == "test-uuid"
#     mock_vcon.add_analysis.assert_called_once()

#     # Check if local model was used
#     assert any("Using local model" in record.message for record in caplog.records)
#     assert any("gpt2" in record.message for record in caplog.records)
