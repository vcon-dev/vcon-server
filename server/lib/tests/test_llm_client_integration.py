"""Integration tests for LLM client abstraction.

These tests require actual API keys and make real API calls.
They are skipped if the required environment variables are not set.

Run with: pytest -m integration server/lib/tests/test_llm_client_integration.py
"""
import pytest
import os

from lib.llm_client import (
    LLMConfig,
    LLMClient,
    create_llm_client,
    detect_provider,
)


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
class TestOpenAIIntegration:
    """Integration tests for OpenAI provider."""

    def test_real_completion_gpt35(self):
        """Test real completion with GPT-3.5."""
        config = LLMConfig(
            model="gpt-3.5-turbo",
            temperature=0,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Say 'hello' and nothing else."}]
        response = client.complete(messages)

        assert response.content is not None
        assert "hello" in response.content.lower()
        assert response.provider == "openai"
        assert response.prompt_tokens > 0
        assert response.completion_tokens > 0

    def test_real_completion_gpt4(self):
        """Test real completion with GPT-4."""
        config = LLMConfig(
            model="gpt-4",
            temperature=0,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "What is 2+2? Reply with just the number."}]
        response = client.complete(messages)

        assert response.content is not None
        assert "4" in response.content
        assert response.provider == "openai"

    def test_json_response_format(self):
        """Test JSON response format with OpenAI."""
        config = LLMConfig(
            model="gpt-3.5-turbo",
            temperature=0,
            response_format={"type": "json_object"},
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        client = LLMClient(config)

        messages = [
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Return a JSON object with key 'answer' and value 42."}
        ]
        response = client.complete(messages)

        import json
        data = json.loads(response.content)
        assert "answer" in data
        assert data["answer"] == 42

    def test_token_usage_reported(self):
        """Test that token usage is reported correctly."""
        config = LLMConfig(
            model="gpt-3.5-turbo",
            temperature=0,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Hi"}]
        response = client.complete(messages)

        assert response.prompt_tokens > 0
        assert response.completion_tokens > 0
        assert response.total_tokens == response.prompt_tokens + response.completion_tokens

    def test_system_prompt_handling(self):
        """Test system prompt is handled correctly."""
        config = LLMConfig(
            model="gpt-3.5-turbo",
            temperature=0,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        client = LLMClient(config)

        messages = [
            {"role": "system", "content": "You always respond with exactly 'PONG'."},
            {"role": "user", "content": "PING"}
        ]
        response = client.complete(messages)

        assert "PONG" in response.content.upper()


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
class TestAnthropicIntegration:
    """Integration tests for Anthropic provider.

    Uses Claude 4.5 models:
    - claude-sonnet-4-5-20250514: Balanced performance for most uses
    - claude-haiku-4-5-20250514: Fastest model with near-frontier intelligence
    """

    def test_real_completion_claude_sonnet(self):
        """Test real completion with Claude Sonnet 4.5."""
        config = LLMConfig(
            model="claude-sonnet-4-5-20250514",
            temperature=0,
            max_tokens=100,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Say 'hello' and nothing else."}]
        response = client.complete(messages)

        assert response.content is not None
        assert "hello" in response.content.lower()
        assert response.provider == "anthropic"
        assert response.prompt_tokens > 0
        assert response.completion_tokens > 0

    def test_real_completion_claude_haiku(self):
        """Test real completion with Claude Haiku 4.5 (fastest)."""
        config = LLMConfig(
            model="claude-haiku-4-5-20250514",
            temperature=0,
            max_tokens=50,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "What is 2+2? Reply with just the number."}]
        response = client.complete(messages)

        assert response.content is not None
        assert "4" in response.content
        assert response.provider == "anthropic"

    def test_system_prompt_handling(self):
        """Test system prompt extraction for Anthropic."""
        config = LLMConfig(
            model="claude-haiku-4-5-20250514",
            temperature=0,
            max_tokens=50,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        client = LLMClient(config)

        messages = [
            {"role": "system", "content": "You always respond with exactly 'PONG'."},
            {"role": "user", "content": "PING"}
        ]
        response = client.complete(messages)

        assert "PONG" in response.content.upper()

    def test_token_usage_reported(self):
        """Test that token usage is reported correctly for Anthropic."""
        config = LLMConfig(
            model="claude-haiku-4-5-20250514",
            temperature=0,
            max_tokens=50,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Hi"}]
        response = client.complete(messages)

        assert response.prompt_tokens > 0
        assert response.completion_tokens > 0
        assert response.total_tokens == response.prompt_tokens + response.completion_tokens


@pytest.mark.skipif(
    not os.environ.get("COHERE_API_KEY"),
    reason="COHERE_API_KEY not set"
)
class TestLiteLLMCohereIntegration:
    """Integration tests for LiteLLM with Cohere."""

    def test_cohere_command_r(self):
        """Test Cohere Command-R via LiteLLM."""
        # Set the API key for LiteLLM
        os.environ["COHERE_API_KEY"] = os.environ.get("COHERE_API_KEY", "")

        config = LLMConfig(
            model="command-r",
            temperature=0,
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Say 'hello' and nothing else."}]
        response = client.complete(messages)

        assert response.content is not None
        assert response.provider == "litellm"


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") or not os.environ.get("ANTHROPIC_API_KEY"),
    reason="Both OPENAI_API_KEY and ANTHROPIC_API_KEY required"
)
class TestMultiProviderIntegration:
    """Integration tests comparing multiple providers."""

    def test_same_question_different_providers(self):
        """Test same question across OpenAI and Anthropic."""
        question = "What is the capital of France? Reply with just the city name."

        # OpenAI
        openai_config = LLMConfig(
            model="gpt-3.5-turbo",
            temperature=0,
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        openai_client = LLMClient(openai_config)
        openai_response = openai_client.complete([{"role": "user", "content": question}])

        # Anthropic
        anthropic_config = LLMConfig(
            model="claude-haiku-4-5-20250514",
            temperature=0,
            max_tokens=50,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        anthropic_client = LLMClient(anthropic_config)
        anthropic_response = anthropic_client.complete([{"role": "user", "content": question}])

        # Both should mention Paris
        assert "paris" in openai_response.content.lower()
        assert "paris" in anthropic_response.content.lower()

        # Providers should be different
        assert openai_response.provider == "openai"
        assert anthropic_response.provider == "anthropic"

    def test_provider_auto_detection_from_model(self):
        """Test that provider is auto-detected from model name."""
        assert detect_provider("gpt-4") == "openai"
        assert detect_provider("claude-3-opus") == "anthropic"
        assert detect_provider("command-r") == "litellm"


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
class TestCreateLLMClientIntegration:
    """Integration tests for create_llm_client factory."""

    def test_create_client_from_link_options(self):
        """Test creating client from typical link options."""
        opts = {
            "model": "gpt-3.5-turbo",
            "temperature": 0,
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        }

        client = create_llm_client(opts)
        assert client.provider_name == "openai"

        messages = [{"role": "user", "content": "Say 'test' and nothing else."}]
        response = client.complete(messages)

        assert response.content is not None
        assert response.provider == "openai"

    def test_tracking_integration(self):
        """Test complete_with_tracking works in real scenario."""
        opts = {
            "model": "gpt-3.5-turbo",
            "temperature": 0,
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            # No tracking URL - should still work, just not send data
        }

        client = create_llm_client(opts)

        messages = [{"role": "user", "content": "Say 'tracked' and nothing else."}]
        response = client.complete_with_tracking(
            messages=messages,
            vcon_uuid="test-uuid-12345",
            tracking_opts=opts,
            sub_type="TEST"
        )

        assert response.content is not None
        assert "tracked" in response.content.lower()


@pytest.mark.skipif(
    not os.environ.get("AZURE_OPENAI_API_KEY") or not os.environ.get("AZURE_OPENAI_ENDPOINT"),
    reason="Azure OpenAI credentials not set"
)
class TestAzureOpenAIIntegration:
    """Integration tests for Azure OpenAI."""

    def test_azure_completion(self):
        """Test completion via Azure OpenAI."""
        config = LLMConfig(
            model="gpt-35-turbo",  # Azure deployment name
            temperature=0,
            azure_api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            azure_api_base=os.environ.get("AZURE_OPENAI_ENDPOINT"),
            azure_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        )
        client = LLMClient(config)

        messages = [{"role": "user", "content": "Say 'azure' and nothing else."}]
        response = client.complete(messages)

        assert response.content is not None
        assert response.provider == "openai"
