"""
Unit tests for the analyze link in the Vcon server.

These tests cover the analysis functionality, including:
- Analysis generation with customizable system prompts
- OpenAI API integration for text analysis
- Handling of missing transcripts, API errors, and sampling logic
- Ensuring correct analysis addition to vCon objects

Environment variables are loaded from .env using python-dotenv.
"""
import os
import pytest
from unittest.mock import Mock, patch
from server.links.analyze import (
    generate_analysis,
    run,
    default_options,
    navigate_dict,
    get_analysis_for_type,
)
from server.vcon import Vcon
from dotenv import load_dotenv

# Load environment variables from .env file for API keys, etc.
load_dotenv()

# Use a specific environment variable to control whether to run the real API tests
RUN_API_TESTS = os.environ.get("RUN_OPENAI_ANALYZE_TESTS", "0").lower() in ("1", "true", "yes")

# If tests should be run, make sure we have an API key
API_KEY = os.environ.get("OPENAI_API_KEY", "test_api_key_for_testing_only")


@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('server.links.analyze.VconRedis', autospec=True) as mock:
        yield mock


@pytest.fixture
def sample_vcon():
    """Create a sample vCon with transcript analysis for testing"""
    vcon = Mock(spec=Vcon)
    vcon.uuid = "test-uuid"
    
    # Create mock dialog
    mock_dialog = Mock()
    mock_dialog.uuid = "dialog-uuid"
    mock_dialog.type = "dialog"
    vcon.dialog = [mock_dialog]
    
    # Create mock analysis with transcript
    transcript_analysis = {
        "dialog": 0,
        "type": "transcript",
        "body": {
            "paragraphs": {
                "transcript": (
                    "Customer: Hi, I'm calling about my recent bill. I think there's an error. "
                    "Agent: I apologize for the issue. Let me check that for you. "
                    "Customer: I was charged twice for the same service on March 15th. "
                    "Agent: You're right, I see the duplicate charge. "
                    "I'll process a refund right away. Customer: Thank you, I appreciate that."
                )
            }
        }
    }
    
    vcon.analysis = [transcript_analysis]
    vcon.add_analysis = Mock()
    
    return vcon


@pytest.fixture
def mock_redis_with_vcon(mock_vcon_redis, sample_vcon):
    """Mock VconRedis with a sample vCon"""
    mock_instance = Mock()
    mock_instance.get_vcon.return_value = sample_vcon
    mock_instance.store_vcon = Mock()
    mock_vcon_redis.return_value = mock_instance
    return mock_instance


class TestNavigateDict:
    """Test the navigate_dict utility function"""
    
    def test_navigate_dict_simple(self):
        """Test navigating a simple dictionary path"""
        test_dict = {"a": {"b": {"c": "value"}}}
        result = navigate_dict(test_dict, "a.b.c")
        assert result == "value"
    
    def test_navigate_dict_missing_key(self):
        """Test navigating to a missing key"""
        test_dict = {"a": {"b": {"c": "value"}}}
        result = navigate_dict(test_dict, "a.b.d")
        assert result is None
    
    def test_navigate_dict_empty_path(self):
        """Test navigating with empty path"""
        test_dict = {"a": "value"}
        result = navigate_dict(test_dict, "")
        assert result is None  # Empty path should return None
    
    def test_navigate_dict_none_input(self):
        """Test navigating with None input"""
        result = navigate_dict(None, "a.b.c")
        assert result is None


class TestGetAnalysisForType:
    """Test the get_analysis_for_type function"""
    
    def test_get_analysis_for_type_found(self):
        """Test finding an analysis of the correct type"""
        vcon = Mock()
        vcon.analysis = [
            {"dialog": 0, "type": "transcript", "body": "test1"},
            {"dialog": 1, "type": "transcript", "body": "test2"},
            {"dialog": 0, "type": "summary", "body": "test3"},
        ]
        
        result = get_analysis_for_type(vcon, 0, "transcript")
        assert result == {"dialog": 0, "type": "transcript", "body": "test1"}
    
    def test_get_analysis_for_type_not_found(self):
        """Test when analysis type is not found"""
        vcon = Mock()
        vcon.analysis = [
            {"dialog": 0, "type": "transcript", "body": "test1"},
        ]
        
        result = get_analysis_for_type(vcon, 0, "summary")
        assert result is None


class TestGenerateAnalysis:
    """Test the generate_analysis function"""
    
    @patch('server.links.analyze.send_ai_usage_data_for_tracking')
    @patch('server.links.analyze.OpenAI')
    def test_generate_analysis_basic(self, mock_openai, mock_send_usage):
        """Test basic analysis generation with mocked client"""
        # Setup mock client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a test analysis."
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        opts = {
            "prompt": "Summarize this",
            "model": "gpt-3.5-turbo",
            "temperature": 0,
            "system_prompt": "You are a helpful assistant.",
        }
        
        result = generate_analysis(
            transcript="Test transcript",
            client=mock_client,
            vcon_uuid="test-uuid",
            opts=opts
        )
        
        assert result == "This is a test analysis."
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('server.links.analyze.send_ai_usage_data_for_tracking')
    @patch('server.links.analyze.OpenAI')
    def test_generate_analysis_with_custom_system_prompt(self, mock_openai, mock_send_usage):
        """Test analysis generation with custom system prompt"""
        # Setup mock client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Custom analysis."
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        custom_system_prompt = "You are a specialized financial analyst."
        
        opts = {
            "prompt": "Analyze this financial data",
            "model": "gpt-3.5-turbo",
            "temperature": 0,
            "system_prompt": custom_system_prompt,
        }
        
        result = generate_analysis(
            transcript="Test transcript",
            client=mock_client,
            vcon_uuid="test-uuid",
            opts=opts
        )
        
        assert result == "Custom analysis."
        
        # Verify the system prompt was used correctly
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        assert messages[0]['role'] == 'system'
        assert messages[0]['content'] == custom_system_prompt
        assert messages[1]['role'] == 'user'
        assert 'Analyze this financial data' in messages[1]['content']
    
    @patch('server.links.analyze.send_ai_usage_data_for_tracking')
    @patch('server.links.analyze.OpenAI')
    def test_generate_analysis_with_empty_prompt(self, mock_openai, mock_send_usage):
        """Test analysis generation with empty prompt"""
        # Setup mock client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Analysis with empty prompt."
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        opts = {
            "prompt": "",
            "model": "gpt-3.5-turbo",
            "temperature": 0,
            "system_prompt": "You are a helpful assistant.",
        }
        
        result = generate_analysis(
            transcript="Test transcript",
            client=mock_client,
            vcon_uuid="test-uuid",
            opts=opts
        )
        
        assert result == "Analysis with empty prompt."
        
        # Verify the user message contains only the transcript
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        assert messages[1]['content'] == "\n\nTest transcript"
    
    @patch('server.links.analyze.send_ai_usage_data_for_tracking')
    @patch('server.links.analyze.OpenAI')
    def test_generate_analysis_with_default_system_prompt(self, mock_openai, mock_send_usage):
        """Test analysis generation uses default system prompt when not provided"""
        # Setup mock client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Default analysis."
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        opts = {
            "prompt": "Test prompt",
            "model": "gpt-3.5-turbo",
            "temperature": 0,
        }
        
        generate_analysis(
            transcript="Test transcript",
            client=mock_client,
            vcon_uuid="test-uuid",
            opts=opts
        )
        
        # Verify the default system prompt was used
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]['messages']
        assert messages[0]['content'] == "You are a helpful assistant."


class TestDefaultOptions:
    """Test the default options configuration"""
    
    def test_default_options_structure(self):
        """Test that default options have the expected structure"""
        assert "prompt" in default_options
        assert "analysis_type" in default_options
        assert "model" in default_options
        assert "sampling_rate" in default_options
        assert "temperature" in default_options
        assert "system_prompt" in default_options
        assert "source" in default_options
    
    def test_default_options_values(self):
        """Test that default options have the expected default values"""
        assert default_options["prompt"] == ""
        assert default_options["analysis_type"] == "summary"
        assert default_options["model"] == "gpt-3.5-turbo-16k"
        assert default_options["sampling_rate"] == 1
        assert default_options["temperature"] == 0
        assert default_options["system_prompt"] == "You are a helpful assistant."
        assert default_options["source"]["analysis_type"] == "transcript"
        assert default_options["source"]["text_location"] == "body.paragraphs.transcript"


class TestRunFunction:
    """Test the main run function"""
    
    @patch('server.links.analyze.generate_analysis')
    @patch('server.links.analyze.is_included', return_value=True)
    @patch('server.links.analyze.randomly_execute_with_sampling', return_value=True)
    def test_run_basic(self, mock_sampling, mock_is_included, mock_generate_analysis, mock_redis_with_vcon, sample_vcon):
        """Test the basic run functionality with mocked analysis generation"""
        # Set up mock to return analysis
        mock_generate_analysis.return_value = "This is a test analysis."
        
        # Set up the mock Redis instance to return our sample vCon
        mock_instance = mock_redis_with_vcon
        mock_instance.get_vcon.return_value = sample_vcon
        
        # Run with default options but add API key
        opts = {"OPENAI_API_KEY": API_KEY}
        
        result = run("test-uuid", "analyze", opts)
        
        # Check that vCon was processed and returned
        assert result == "test-uuid"
        
        # Verify analysis generation was called
        mock_generate_analysis.assert_called_once()
        
        # Verify vCon was updated and stored
        mock_redis_with_vcon.store_vcon.assert_called_once()
        
        # Check the vCon has an analysis
        sample_vcon.add_analysis.assert_called_once()
    
    @patch('server.links.analyze.generate_analysis')
    @patch('server.links.analyze.is_included', return_value=True)
    @patch('server.links.analyze.randomly_execute_with_sampling', return_value=True)
    def test_run_with_custom_system_prompt(
        self, mock_sampling, mock_is_included, mock_generate_analysis, 
        mock_redis_with_vcon, sample_vcon
    ):
        """Test run function with custom system prompt"""
        # Set up mock to return analysis
        mock_generate_analysis.return_value = "Custom analysis with custom system prompt."
        
        # Set up the mock Redis instance to return our sample vCon
        mock_instance = mock_redis_with_vcon
        mock_instance.get_vcon.return_value = sample_vcon
        
        # Run with custom system prompt
        opts = {
            "OPENAI_API_KEY": API_KEY,
            "system_prompt": "You are a specialized customer service analyst.",
            "prompt": "Analyze this customer interaction."
        }
        
        result = run("test-uuid", "analyze", opts)
        
        # Check that vCon was processed and returned
        assert result == "test-uuid"
        
        # Verify analysis generation was called with opts containing custom system prompt
        mock_generate_analysis.assert_called_once()
        call_args = mock_generate_analysis.call_args
        assert call_args[1]['opts']['system_prompt'] == "You are a specialized customer service analyst."
        assert call_args[1]['opts']['prompt'] == "Analyze this customer interaction."
    
    @patch('server.links.analyze.is_included', return_value=False)
    def test_run_skipped_due_to_filters(self, mock_is_included, mock_redis_with_vcon):
        """Test that run is skipped when filters exclude the vCon"""
        # Set up the mock Redis instance to return a sample vCon
        sample_vcon = Mock()
        mock_redis_with_vcon.get_vcon.return_value = sample_vcon
        
        result = run("test-uuid", "analyze", {"OPENAI_API_KEY": API_KEY})
        
        # Should return the vcon_uuid without processing
        assert result == "test-uuid"
        
        # Should have called get_vcon but then skipped due to filters
        mock_redis_with_vcon.get_vcon.assert_called_once_with("test-uuid")
    
    @patch('server.links.analyze.is_included', return_value=True)
    @patch('server.links.analyze.randomly_execute_with_sampling', return_value=False)
    def test_run_skipped_due_to_sampling(self, mock_sampling, mock_is_included, mock_redis_with_vcon):
        """Test that run is skipped when sampling excludes the vCon"""
        # Set up the mock Redis instance to return a sample vCon
        sample_vcon = Mock()
        mock_redis_with_vcon.get_vcon.return_value = sample_vcon
        
        result = run("test-uuid", "analyze", {"OPENAI_API_KEY": API_KEY})
        
        # Should return the vcon_uuid without processing
        assert result == "test-uuid"
        
        # Should have called get_vcon but then skipped due to sampling
        mock_redis_with_vcon.get_vcon.assert_called_once_with("test-uuid")
    
    @patch('server.links.analyze.generate_analysis')
    @patch('server.links.analyze.is_included', return_value=True)
    @patch('server.links.analyze.randomly_execute_with_sampling', return_value=True)
    def test_run_with_azure_openai(
        self, mock_sampling, mock_is_included, mock_generate_analysis,
        mock_redis_with_vcon, sample_vcon
    ):
        """Test run function with Azure OpenAI credentials"""
        # Set up mock to return analysis
        mock_generate_analysis.return_value = "Azure OpenAI analysis."
        
        # Set up the mock Redis instance to return our sample vCon
        mock_instance = mock_redis_with_vcon
        mock_instance.get_vcon.return_value = sample_vcon
        
        # Run with Azure OpenAI credentials
        opts = {
            "AZURE_OPENAI_API_KEY": "azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://azure-endpoint.com",
            "AZURE_OPENAI_API_VERSION": "2023-12-01-preview"
        }
        
        with patch('server.links.analyze.AzureOpenAI') as mock_azure:
            mock_azure_instance = Mock()
            mock_azure.return_value = mock_azure_instance
            
            result = run("test-uuid", "analyze", opts)
            
            # Check that vCon was processed and returned
            assert result == "test-uuid"
            
            # Verify Azure OpenAI was used
            mock_azure.assert_called_once()
    
    def test_run_missing_credentials(self, mock_redis_with_vcon):
        """Test that run raises error when no credentials are provided"""
        error_msg = "OpenAI or Azure OpenAI credentials not provided"
        with pytest.raises(ValueError, match=error_msg):
            run("test-uuid", "analyze", {})
    
    @patch('server.links.analyze.generate_analysis')
    @patch('server.links.analyze.is_included', return_value=True)
    @patch('server.links.analyze.randomly_execute_with_sampling', return_value=True)
    def test_run_already_has_analysis(
        self, mock_sampling, mock_is_included, mock_generate_analysis,
        mock_redis_with_vcon, sample_vcon
    ):
        """Test that run skips when analysis already exists"""
        # Add existing analysis to the vCon
        existing_analysis = {
            "dialog": 0,
            "type": "summary",
            "body": "Existing analysis"
        }
        sample_vcon.analysis.append(existing_analysis)
        
        # Set up the mock Redis instance to return our sample vCon
        mock_instance = mock_redis_with_vcon
        mock_instance.get_vcon.return_value = sample_vcon
        
        result = run("test-uuid", "analyze", {"OPENAI_API_KEY": API_KEY})
        
        # Should return without generating new analysis
        assert result == "test-uuid"
        mock_generate_analysis.assert_not_called()
    
    @patch('server.links.analyze.generate_analysis')
    @patch('server.links.analyze.is_included', return_value=True)
    @patch('server.links.analyze.randomly_execute_with_sampling', return_value=True)
    def test_run_analysis_failure(
        self, mock_sampling, mock_is_included, mock_generate_analysis,
        mock_redis_with_vcon, sample_vcon
    ):
        """Test that run handles analysis generation failures"""
        # Set up mock to raise exception
        mock_generate_analysis.side_effect = Exception("API Error")
        
        # Set up the mock Redis instance to return our sample vCon
        mock_instance = mock_redis_with_vcon
        mock_instance.get_vcon.return_value = sample_vcon
        
        with pytest.raises(Exception, match="API Error"):
            run("test-uuid", "analyze", {"OPENAI_API_KEY": API_KEY})


@pytest.mark.skipif(not RUN_API_TESTS, reason="Skipping API tests. Set RUN_OPENAI_ANALYZE_TESTS=1 to run")
class TestRealAPIIntegration:
    """Test with real OpenAI API (optional)"""
    
    def test_generate_analysis_real_api(self):
        """Test the generate_analysis function with the real OpenAI API"""
        # Skip if no API key is provided
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("No OpenAI API key provided via OPENAI_API_KEY environment variable")
        
        from openai import OpenAI
        
        # Sample transcript
        transcript = (
            "Customer: Hi, I'm calling about my recent bill. I think there's an error. "
            "Agent: I apologize for the issue. Let me check that for you. "
            "Customer: I was charged twice for the same service on March 15th. "
            "Agent: You're right, I see the duplicate charge. I'll process a refund right away. "
            "Customer: Thank you, I appreciate that."
        )
        
        # Create real client
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        
        # Prepare opts
        opts = {
            "prompt": "Summarize this customer service interaction in one sentence.",
            "model": "gpt-3.5-turbo",  # Use cheaper model for tests
            "temperature": 0,
            "system_prompt": "You are a helpful assistant.",
        }
        
        # Call the function
        result = generate_analysis(
            transcript=transcript,
            client=client,
            vcon_uuid="test-uuid",
            opts=opts
        )
        
        # Check that we get a valid response
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_generate_analysis_real_api_custom_system_prompt(self):
        """Test the generate_analysis function with custom system prompt using real API"""
        # Skip if no API key is provided
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("No OpenAI API key provided via OPENAI_API_KEY environment variable")
        
        from openai import OpenAI
        
        # Sample transcript
        transcript = "The customer called about a billing issue and was very upset."
        
        # Create real client
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        
        # Prepare opts with custom system prompt
        opts = {
            "prompt": "Analyze the customer's emotional state.",
            "model": "gpt-3.5-turbo",
            "temperature": 0,
            "system_prompt": "You are a customer service expert specializing in emotional analysis.",
        }
        
        # Call the function with custom system prompt
        result = generate_analysis(
            transcript=transcript,
            client=client,
            vcon_uuid="test-uuid",
            opts=opts
        )
        
        # Check that we get a valid response
        assert isinstance(result, str)
        assert len(result) > 0
