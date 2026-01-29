"""
LLM client abstraction for vcon-server.

Provides a unified interface to multiple LLM providers:
- Native OpenAI SDK for gpt-* and azure/* models
- Native Anthropic SDK for claude-* models
- LiteLLM fallback for all other providers (100+)

Supports global defaults with per-link override configuration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import logging

from openai import OpenAI, AzureOpenAI
import anthropic
import litellm
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from lib.logging_utils import init_logger
from lib.ai_usage import send_ai_usage_data_for_tracking

logger = init_logger(__name__)


@dataclass
class LLMConfig:
    """Configuration for LLM client.

    Attributes:
        model: Model identifier (e.g., "gpt-4", "claude-3-opus-20240229")
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        response_format: Optional response format (e.g., {"type": "json_object"})
        timeout: Request timeout in seconds

        # Provider credentials (auto-selected based on model prefix)
        openai_api_key: OpenAI API key
        azure_api_key: Azure OpenAI API key
        azure_api_base: Azure OpenAI endpoint
        azure_api_version: Azure API version
        anthropic_api_key: Anthropic API key

        # Additional provider-specific settings
        extra_params: Additional parameters passed to completion calls
    """
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    response_format: Optional[Dict[str, Any]] = None
    timeout: float = 120.0

    # Credentials
    openai_api_key: Optional[str] = None
    azure_api_key: Optional[str] = None
    azure_api_base: Optional[str] = None
    azure_api_version: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # System prompt (for providers that handle it differently)
    system_prompt: Optional[str] = None

    # Extra parameters
    extra_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_options(cls, opts: Dict[str, Any], defaults: Optional['LLMConfig'] = None) -> 'LLMConfig':
        """Create config from link options with optional defaults.

        Priority: opts > defaults > class defaults
        """
        base = defaults or cls()
        return cls(
            model=opts.get("model", base.model),
            temperature=opts.get("temperature", base.temperature),
            max_tokens=opts.get("max_tokens", base.max_tokens),
            response_format=opts.get("response_format", base.response_format),
            timeout=opts.get("timeout", base.timeout),
            openai_api_key=opts.get("OPENAI_API_KEY", base.openai_api_key),
            azure_api_key=opts.get("AZURE_OPENAI_API_KEY", base.azure_api_key),
            azure_api_base=opts.get("AZURE_OPENAI_ENDPOINT", base.azure_api_base),
            azure_api_version=opts.get("AZURE_OPENAI_API_VERSION", base.azure_api_version),
            anthropic_api_key=opts.get("ANTHROPIC_API_KEY", base.anthropic_api_key),
            system_prompt=opts.get("system_prompt", base.system_prompt),
            extra_params=opts.get("llm_extra_params", base.extra_params),
        )


@dataclass
class LLMResponse:
    """Standardized response from LLM completion."""
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    raw_response: Any  # Original provider response
    provider: str  # "openai", "anthropic", or "litellm"


def detect_provider(model: str) -> str:
    """Detect the appropriate provider based on model name.

    Args:
        model: Model identifier string

    Returns:
        Provider name: "openai", "anthropic", or "litellm"
    """
    model_lower = model.lower()

    # OpenAI models
    if model_lower.startswith(("gpt-", "o1", "o3", "azure/")):
        return "openai"

    # Anthropic models
    if model_lower.startswith("claude"):
        return "anthropic"

    # Everything else goes through LiteLLM
    return "litellm"


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        **kwargs
    ) -> LLMResponse:
        """Execute a chat completion request."""
        pass


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI and Azure OpenAI models."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[OpenAI] = None
        self._is_azure = False

    def _get_client(self) -> OpenAI:
        """Get or create the OpenAI client."""
        if self._client is None:
            if self.config.azure_api_key and self.config.azure_api_base:
                self._client = AzureOpenAI(
                    api_key=self.config.azure_api_key,
                    azure_endpoint=self.config.azure_api_base,
                    api_version=self.config.azure_api_version or "2024-02-15-preview",
                )
                self._is_azure = True
                logger.debug(f"Using Azure OpenAI client at {self.config.azure_api_base}")
            elif self.config.openai_api_key:
                self._client = OpenAI(
                    api_key=self.config.openai_api_key,
                    timeout=self.config.timeout,
                    max_retries=0,  # We handle retries with tenacity
                )
                logger.debug("Using OpenAI client")
            else:
                raise ValueError(
                    "OpenAI credentials not provided. "
                    "Need OPENAI_API_KEY or AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT"
                )
        return self._client

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=65),
        stop=stop_after_attempt(6),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    def complete(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        **kwargs
    ) -> LLMResponse:
        """Execute OpenAI chat completion."""
        client = self._get_client()

        params = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature,
        }

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens

        if config.response_format:
            params["response_format"] = config.response_format

        # Merge extra params and kwargs
        params.update(config.extra_params)
        params.update(kwargs)

        response = client.chat.completions.create(**params)

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            raw_response=response,
            provider="openai",
        )


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude models."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client: Optional[anthropic.Anthropic] = None

    def _get_client(self) -> anthropic.Anthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            if not self.config.anthropic_api_key:
                raise ValueError("Anthropic API key not provided. Need ANTHROPIC_API_KEY")
            self._client = anthropic.Anthropic(
                api_key=self.config.anthropic_api_key,
                timeout=self.config.timeout,
            )
            logger.debug("Using Anthropic client")
        return self._client

    def _convert_messages(
        self,
        messages: List[Dict[str, str]]
    ) -> tuple[Optional[str], List[Dict[str, str]]]:
        """Convert OpenAI message format to Anthropic format.

        Anthropic requires system message to be passed separately.

        Returns:
            Tuple of (system_message, converted_messages)
        """
        system_message = None
        converted = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                converted.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        return system_message, converted

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=65),
        stop=stop_after_attempt(6),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    def complete(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        **kwargs
    ) -> LLMResponse:
        """Execute Anthropic chat completion."""
        client = self._get_client()

        system_message, converted_messages = self._convert_messages(messages)

        # Use system from config if not in messages
        if not system_message and config.system_prompt:
            system_message = config.system_prompt

        params = {
            "model": config.model,
            "messages": converted_messages,
            "max_tokens": config.max_tokens or 4096,  # Anthropic requires max_tokens
        }

        if system_message:
            params["system"] = system_message

        if config.temperature > 0:
            params["temperature"] = config.temperature

        # Merge extra params and kwargs
        params.update(config.extra_params)
        params.update(kwargs)

        response = client.messages.create(**params)

        # Extract text from content blocks
        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        return LLMResponse(
            content=content,
            model=response.model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            raw_response=response,
            provider="anthropic",
        )


class LiteLLMProvider(BaseProvider):
    """Provider for all other models via LiteLLM."""

    def __init__(self, config: LLMConfig):
        self.config = config

    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=65),
        stop=stop_after_attempt(6),
        before_sleep=before_sleep_log(logger, logging.INFO),
    )
    def complete(
        self,
        messages: List[Dict[str, str]],
        config: LLMConfig,
        **kwargs
    ) -> LLMResponse:
        """Execute LiteLLM completion."""
        params = {
            "model": config.model,
            "messages": messages,
            "temperature": config.temperature,
            "timeout": config.timeout,
        }

        if config.max_tokens:
            params["max_tokens"] = config.max_tokens

        # Pass API keys if configured
        if config.openai_api_key:
            params["api_key"] = config.openai_api_key
        if config.anthropic_api_key:
            litellm.anthropic_key = config.anthropic_api_key

        # Merge extra params and kwargs
        params.update(config.extra_params)
        params.update(kwargs)

        logger.debug(f"LiteLLM completion request: model={config.model}")

        response = litellm.completion(**params)

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            raw_response=response,
            provider="litellm",
        )


class LLMClient:
    """Unified LLM client that routes to appropriate provider."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._provider_name = detect_provider(config.model)
        self._provider: Optional[BaseProvider] = None

    def _get_provider(self) -> BaseProvider:
        """Get or create the appropriate provider."""
        if self._provider is None:
            if self._provider_name == "openai":
                self._provider = OpenAIProvider(self.config)
            elif self._provider_name == "anthropic":
                self._provider = AnthropicProvider(self.config)
            else:
                self._provider = LiteLLMProvider(self.config)
            logger.info(f"Using {self._provider_name} provider for model {self.config.model}")
        return self._provider

    def complete(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """Execute a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            **kwargs: Additional parameters to override config

        Returns:
            LLMResponse with content and usage information
        """
        # Guardrail: some kwargs are provider-specific (e.g. OpenAI's response_format).
        # Strip anything unsupported by the active provider before we forward into SDK calls.
        if self._provider_name != "openai":
            kwargs.pop("response_format", None)
        provider = self._get_provider()
        return provider.complete(messages, self.config, **kwargs)

    def complete_with_tracking(
        self,
        messages: List[Dict[str, str]],
        vcon_uuid: str,
        tracking_opts: Dict[str, Any],
        sub_type: str = "ANALYZE",
        **kwargs
    ) -> LLMResponse:
        """Execute completion and send AI usage tracking data.

        Args:
            messages: Chat messages
            vcon_uuid: UUID of the vCon being processed
            tracking_opts: Dict containing send_ai_usage_data_to_url and ai_usage_api_token
            sub_type: Tracking sub-type (e.g., "ANALYZE", "CHECK_AND_TAG")
            **kwargs: Additional completion parameters

        Returns:
            LLMResponse with content and usage
        """
        response = self.complete(messages, **kwargs)

        send_ai_usage_data_for_tracking(
            vcon_uuid=vcon_uuid,
            input_units=response.prompt_tokens,
            output_units=response.completion_tokens,
            unit_type="tokens",
            type="VCON_PROCESSING",
            send_ai_usage_data_to_url=tracking_opts.get("send_ai_usage_data_to_url", ""),
            ai_usage_api_token=tracking_opts.get("ai_usage_api_token", ""),
            model=response.model,
            sub_type=sub_type,
        )

        return response

    @property
    def provider_name(self) -> str:
        """Get the name of the provider being used."""
        return self._provider_name


# Global default configuration (can be set at startup)
_global_default_config: Optional[LLMConfig] = None


def set_global_llm_config(config: LLMConfig) -> None:
    """Set the global default LLM configuration."""
    global _global_default_config
    _global_default_config = config
    logger.info(f"Global LLM config set: model={config.model}")


def get_global_llm_config() -> Optional[LLMConfig]:
    """Get the global default LLM configuration."""
    return _global_default_config


def create_llm_client(opts: Dict[str, Any]) -> LLMClient:
    """Factory function to create an LLM client with merged configuration.

    Merges: global defaults < link defaults < runtime options

    Args:
        opts: Link options dictionary

    Returns:
        Configured LLMClient instance
    """
    config = LLMConfig.from_options(opts, _global_default_config)
    return LLMClient(config)


def get_vendor_from_response(response: LLMResponse) -> str:
    """Determine vendor name for vCon analysis from response.

    Args:
        response: LLMResponse from completion

    Returns:
        Vendor string for use in vCon.add_analysis()
    """
    model_lower = response.model.lower()

    if "gpt" in model_lower or response.provider == "openai":
        return "openai"
    elif "claude" in model_lower or response.provider == "anthropic":
        return "anthropic"
    else:
        # Use provider as vendor, or extract from model name
        return response.provider
