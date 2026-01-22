"""Unit tests for LLM client abstraction."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

from lib.llm_client import (
    LLMConfig,
    LLMResponse,
    LLMClient,
    OpenAIProvider,
    AnthropicProvider,
    LiteLLMProvider,
    detect_provider,
    create_llm_client,
    set_global_llm_config,
    get_global_llm_config,
    get_vendor_from_response,
)


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_default_values(self):
        """Test config creation with defaults."""
        config = LLMConfig()
        assert config.model == "gpt-3.5-turbo"
        assert config.temperature == 0.0
        assert config.max_tokens is None
        assert config.timeout == 120.0

    def test_from_options_with_defaults(self):
        """Test config creation from options with defaults."""
        opts = {"model": "gpt-4"}
        config = LLMConfig.from_options(opts)
        assert config.model == "gpt-4"
        assert config.temperature == 0.0  # default

    def test_from_options_with_global_defaults(self):
        """Test config merges with global defaults."""
        global_config = LLMConfig(model="claude-3-opus", temperature=0.5)
        opts = {"model": "gpt-4"}  # Override model only
        config = LLMConfig.from_options(opts, global_config)
        assert config.model == "gpt-4"
        assert config.temperature == 0.5  # From global

    def test_credential_mapping_openai(self):
        """Test OpenAI credential mapping from options."""
        opts = {
            "OPENAI_API_KEY": "test-openai-key",
        }
        config = LLMConfig.from_options(opts)
        assert config.openai_api_key == "test-openai-key"

    def test_credential_mapping_azure(self):
        """Test Azure OpenAI credential mapping from options."""
        opts = {
            "AZURE_OPENAI_API_KEY": "azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.azure.com",
            "AZURE_OPENAI_API_VERSION": "2024-02-15",
        }
        config = LLMConfig.from_options(opts)
        assert config.azure_api_key == "azure-key"
        assert config.azure_api_base == "https://test.azure.com"
        assert config.azure_api_version == "2024-02-15"

    def test_credential_mapping_anthropic(self):
        """Test Anthropic credential mapping from options."""
        opts = {
            "ANTHROPIC_API_KEY": "test-anthropic-key",
        }
        config = LLMConfig.from_options(opts)
        assert config.anthropic_api_key == "test-anthropic-key"

    def test_extra_params_passthrough(self):
        """Test extra params are passed through."""
        opts = {
            "llm_extra_params": {"top_p": 0.9, "presence_penalty": 0.5}
        }
        config = LLMConfig.from_options(opts)
        assert config.extra_params == {"top_p": 0.9, "presence_penalty": 0.5}


class TestProviderDetection:
    """Tests for provider detection from model names."""

    def test_detect_openai_gpt_models(self):
        """Test detection of GPT models."""
        assert detect_provider("gpt-4") == "openai"
        assert detect_provider("gpt-3.5-turbo") == "openai"
        assert detect_provider("gpt-4o") == "openai"
        assert detect_provider("gpt-4-turbo") == "openai"
        assert detect_provider("GPT-4") == "openai"  # Case insensitive

    def test_detect_openai_o1_models(self):
        """Test detection of O1 reasoning models."""
        assert detect_provider("o1-preview") == "openai"
        assert detect_provider("o1-mini") == "openai"
        assert detect_provider("o3-mini") == "openai"

    def test_detect_azure_models(self):
        """Test detection of Azure deployment models."""
        assert detect_provider("azure/my-deployment") == "openai"
        assert detect_provider("azure/gpt-4-deployment") == "openai"

    def test_detect_anthropic_models(self):
        """Test detection of Claude models."""
        assert detect_provider("claude-3-opus-20240229") == "anthropic"
        assert detect_provider("claude-3-sonnet-20240229") == "anthropic"
        assert detect_provider("claude-3-haiku-20240307") == "anthropic"
        assert detect_provider("claude-2") == "anthropic"
        assert detect_provider("Claude-3-opus") == "anthropic"  # Case insensitive

    def test_detect_litellm_fallback(self):
        """Test fallback to LiteLLM for other models."""
        assert detect_provider("command-r-plus") == "litellm"
        assert detect_provider("gemini/gemini-pro") == "litellm"
        assert detect_provider("together_ai/llama-3-70b") == "litellm"
        assert detect_provider("mistral/mistral-large") == "litellm"
        assert detect_provider("unknown-model") == "litellm"


class TestOpenAIProvider:
    """Tests for OpenAI provider implementation."""

    @patch('lib.llm_client.OpenAI')
    def test_complete_basic(self, mock_openai_class):
        """Test basic completion call."""
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.model = "gpt-3.5-turbo"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_client.chat.completions.create.return_value = mock_response

        config = LLMConfig(model="gpt-3.5-turbo", openai_api_key="test-openai-key")
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.complete(messages, config)

        assert response.content == "Test response"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 20
        assert response.provider == "openai"
        mock_client.chat.completions.create.assert_called_once()

    @patch('lib.llm_client.OpenAI')
    def test_complete_with_json_response_format(self, mock_openai_class):
        """Test completion with JSON response format."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"result": true}'
        mock_response.model = "gpt-4"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        config = LLMConfig(
            model="gpt-4",
            response_format={"type": "json_object"},
            openai_api_key="test-openai-key"
        )
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Return JSON"}]
        response = provider.complete(messages, config)

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @patch('lib.llm_client.AzureOpenAI')
    def test_uses_azure_client_when_configured(self, mock_azure_class):
        """Test that Azure client is used when Azure credentials are provided."""
        mock_client = Mock()
        mock_azure_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Azure response"
        mock_response.model = "gpt-4"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_client.chat.completions.create.return_value = mock_response

        config = LLMConfig(
            model="gpt-4",
            azure_api_key="azure-key",
            azure_api_base="https://test.azure.com",
            azure_api_version="2024-02-15"
        )
        provider = OpenAIProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.complete(messages, config)

        mock_azure_class.assert_called_once()
        assert response.content == "Azure response"


class TestAnthropicProvider:
    """Tests for Anthropic provider implementation."""

    @patch('lib.llm_client.anthropic.Anthropic')
    def test_complete_basic(self, mock_anthropic_class):
        """Test basic Anthropic completion."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Claude response")]
        mock_response.model = "claude-3-opus-20240229"
        mock_response.usage.input_tokens = 15
        mock_response.usage.output_tokens = 25
        mock_client.messages.create.return_value = mock_response

        config = LLMConfig(model="claude-3-opus-20240229", anthropic_api_key="test-anthropic-key")
        provider = AnthropicProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.complete(messages, config)

        assert response.content == "Claude response"
        assert response.prompt_tokens == 15
        assert response.completion_tokens == 25
        assert response.provider == "anthropic"

    @patch('lib.llm_client.anthropic.Anthropic')
    def test_message_format_conversion(self, mock_anthropic_class):
        """Test OpenAI format to Anthropic format conversion."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Response")]
        mock_response.model = "claude-3-opus"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 10
        mock_client.messages.create.return_value = mock_response

        config = LLMConfig(model="claude-3-opus", anthropic_api_key="test-anthropic-key")
        provider = AnthropicProvider(config)

        # OpenAI format messages with system
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        provider.complete(messages, config)

        call_kwargs = mock_client.messages.create.call_args[1]
        # System should be extracted
        assert call_kwargs["system"] == "You are helpful."
        # Only user message should be in messages
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"


class TestLiteLLMProvider:
    """Tests for LiteLLM provider implementation."""

    @patch('lib.llm_client.litellm.completion')
    def test_complete_basic(self, mock_completion):
        """Test basic LiteLLM completion."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "LiteLLM response"
        mock_response.model = "command-r-plus"
        mock_response.usage.prompt_tokens = 20
        mock_response.usage.completion_tokens = 30
        mock_response.usage.total_tokens = 50
        mock_completion.return_value = mock_response

        config = LLMConfig(model="command-r-plus")
        provider = LiteLLMProvider(config)

        messages = [{"role": "user", "content": "Hello"}]
        response = provider.complete(messages, config)

        assert response.content == "LiteLLM response"
        assert response.provider == "litellm"
        mock_completion.assert_called_once()


class TestLLMClient:
    """Tests for high-level LLM client."""

    @patch('lib.llm_client.OpenAI')
    def test_routes_to_openai_provider(self, mock_openai_class):
        """Test that GPT models route to OpenAI provider."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "OpenAI response"
        mock_response.model = "gpt-4"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_client.chat.completions.create.return_value = mock_response

        config = LLMConfig(model="gpt-4", openai_api_key="test-openai-key")
        client = LLMClient(config)

        assert client.provider_name == "openai"

        messages = [{"role": "user", "content": "Hello"}]
        response = client.complete(messages)
        assert response.provider == "openai"

    @patch('lib.llm_client.anthropic.Anthropic')
    def test_routes_to_anthropic_provider(self, mock_anthropic_class):
        """Test that Claude models route to Anthropic provider."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Anthropic response")]
        mock_response.model = "claude-3-opus"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_response

        config = LLMConfig(model="claude-3-opus", anthropic_api_key="test-anthropic-key")
        client = LLMClient(config)

        assert client.provider_name == "anthropic"

        messages = [{"role": "user", "content": "Hello"}]
        response = client.complete(messages)
        assert response.provider == "anthropic"

    @patch('lib.llm_client.litellm.completion')
    def test_routes_to_litellm_provider(self, mock_completion):
        """Test that unknown models route to LiteLLM provider."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "LiteLLM response"
        mock_response.model = "command-r-plus"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_completion.return_value = mock_response

        config = LLMConfig(model="command-r-plus")
        client = LLMClient(config)

        assert client.provider_name == "litellm"

        messages = [{"role": "user", "content": "Hello"}]
        response = client.complete(messages)
        assert response.provider == "litellm"

    @patch('lib.llm_client.send_ai_usage_data_for_tracking')
    @patch('lib.llm_client.OpenAI')
    def test_complete_with_tracking(self, mock_openai_class, mock_tracking):
        """Test completion with usage tracking."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Tracked response"
        mock_response.model = "gpt-3.5-turbo"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        mock_client.chat.completions.create.return_value = mock_response

        config = LLMConfig(model="gpt-3.5-turbo", openai_api_key="test-openai-key")
        client = LLMClient(config)

        tracking_opts = {
            "send_ai_usage_data_to_url": "https://tracking.example.com",
            "ai_usage_api_token": "token123"
        }

        response = client.complete_with_tracking(
            messages=[{"role": "user", "content": "Test"}],
            vcon_uuid="test-uuid",
            tracking_opts=tracking_opts,
            sub_type="ANALYZE"
        )

        mock_tracking.assert_called_once_with(
            vcon_uuid="test-uuid",
            input_units=100,
            output_units=50,
            unit_type="tokens",
            type="VCON_PROCESSING",
            send_ai_usage_data_to_url="https://tracking.example.com",
            ai_usage_api_token="token123",
            model="gpt-3.5-turbo",
            sub_type="ANALYZE"
        )

    @patch('lib.llm_client.send_ai_usage_data_for_tracking')
    @patch('lib.llm_client.anthropic.Anthropic')
    def test_complete_with_tracking_strips_response_format_for_anthropic(
        self, mock_anthropic_class, mock_tracking
    ):
        """Ensure OpenAI-only kwargs are not forwarded to Anthropic SDK calls."""
        mock_client = Mock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="Claude response")]
        mock_response.model = "claude-3-opus"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_response

        config = LLMConfig(model="claude-3-opus", anthropic_api_key="test-anthropic-key")
        client = LLMClient(config)

        client.complete_with_tracking(
            messages=[{"role": "user", "content": "Return JSON"}],
            vcon_uuid="test-uuid",
            tracking_opts={},
            sub_type="TEST",
            response_format={"type": "json_object"},
        )

        call_kwargs = mock_client.messages.create.call_args[1]
        assert "response_format" not in call_kwargs

    @patch('lib.llm_client.litellm.completion')
    def test_litellm_does_not_forward_response_format(self, mock_completion):
        """Ensure response_format is not sent to LiteLLM models."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "LiteLLM response"
        mock_response.model = "command-r-plus"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 30
        mock_completion.return_value = mock_response

        config = LLMConfig(model="command-r-plus", response_format={"type": "json_object"})
        client = LLMClient(config)

        client.complete([{"role": "user", "content": "Hello"}])

        call_kwargs = mock_completion.call_args[1]
        assert "response_format" not in call_kwargs


class TestGlobalConfig:
    """Tests for global configuration management."""

    def test_set_and_get_global_config(self):
        """Test global config management."""
        config = LLMConfig(model="claude-3-opus")
        set_global_llm_config(config)

        retrieved = get_global_llm_config()
        assert retrieved.model == "claude-3-opus"

    @patch('lib.llm_client.OpenAI')
    def test_create_llm_client_uses_global_defaults(self, mock_openai_class):
        """Test factory uses global defaults."""
        global_config = LLMConfig(
            model="gpt-4",
            temperature=0.7,
            openai_api_key="global-key"
        )
        set_global_llm_config(global_config)

        # Create client with no overrides
        client = create_llm_client({})
        assert client.config.model == "gpt-4"
        assert client.config.temperature == 0.7

        # Create client with overrides
        client2 = create_llm_client({"model": "gpt-3.5-turbo"})
        assert client2.config.model == "gpt-3.5-turbo"
        assert client2.config.temperature == 0.7  # Still from global


class TestGetVendorFromResponse:
    """Tests for vendor detection from response."""

    def test_openai_vendor(self):
        """Test OpenAI vendor detection."""
        response = LLMResponse(
            content="test",
            model="gpt-4",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            raw_response=None,
            provider="openai"
        )
        assert get_vendor_from_response(response) == "openai"

    def test_anthropic_vendor(self):
        """Test Anthropic vendor detection."""
        response = LLMResponse(
            content="test",
            model="claude-3-opus",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            raw_response=None,
            provider="anthropic"
        )
        assert get_vendor_from_response(response) == "anthropic"

    def test_litellm_vendor(self):
        """Test LiteLLM vendor detection."""
        response = LLMResponse(
            content="test",
            model="command-r-plus",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            raw_response=None,
            provider="litellm"
        )
        assert get_vendor_from_response(response) == "litellm"
