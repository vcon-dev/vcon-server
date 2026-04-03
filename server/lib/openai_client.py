"""
Shared OpenAI/Azure/LiteLLM client for vcon-server.

When LITELLM_PROXY_URL and LITELLM_MASTER_KEY are set in opts,
returns an OpenAI client configured to use the LiteLLM proxy. Otherwise uses
direct OpenAI or Azure OpenAI credentials from opts.

All links and storage that call OpenAI should use get_openai_client(opts) so
LLM provider and proxy can be switched in one place.
"""
from openai import OpenAI, AzureOpenAI, AsyncOpenAI, AsyncAzureOpenAI

from lib.logging_utils import init_logger

logger = init_logger(__name__)

# Default Azure API version when not specified
DEFAULT_AZURE_OPENAI_API_VERSION = "2024-10-21"


def get_openai_client(opts=None):
    """
    Return an OpenAI-compatible client (OpenAI or AzureOpenAI).
    Same client is used for chat and embeddings; LiteLLM proxy supports both.

    opts: dict of options. All values are read from opts only.

    Supported keys in opts:
      - LITELLM_PROXY_URL, LITELLM_MASTER_KEY  -> use LiteLLM proxy (chat + embeddings)
      - AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION -> Azure
      - OPENAI_API_KEY or openai_api_key or api_key -> OpenAI
      - organization / organization_key, project / project_key (optional)
    """
    opts = opts or {}

    litellm_url = (opts.get("LITELLM_PROXY_URL") or "").strip().rstrip("/")
    litellm_key = (opts.get("LITELLM_MASTER_KEY") or "").strip()

    if litellm_url and litellm_key:
        logger.info("Using LiteLLM proxy at %s", litellm_url)
        organization = opts.get("organization") or opts.get("organization_key")
        project = opts.get("project") or opts.get("project_key")
        return OpenAI(
            api_key=litellm_key,
            base_url=litellm_url,
            organization=organization if organization else None,
            project=project if project else None,
            timeout=120.0,
            max_retries=0,
        )

    azure_endpoint = (opts.get("AZURE_OPENAI_ENDPOINT") or "").strip()
    azure_api_key = (opts.get("AZURE_OPENAI_API_KEY") or "").strip()
    azure_api_version = opts.get("AZURE_OPENAI_API_VERSION") or DEFAULT_AZURE_OPENAI_API_VERSION

    if azure_endpoint and azure_api_key:
        logger.info("Using Azure OpenAI client at endpoint: %s", azure_endpoint)
        return AzureOpenAI(
            api_key=azure_api_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_api_version,
            timeout=120.0,
            max_retries=0,
        )

    openai_api_key = (
        opts.get("OPENAI_API_KEY")
        or opts.get("openai_api_key")
        or opts.get("api_key")
    )
    if openai_api_key:
        logger.info("Using public OpenAI client")
        organization = opts.get("organization") or opts.get("organization_key")
        project = opts.get("project") or opts.get("project_key")
        return OpenAI(
            api_key=openai_api_key,
            organization=organization if organization else None,
            project=project if project else None,
            timeout=120.0,
            max_retries=0,
        )

    raise ValueError(
        "Set LITELLM_PROXY_URL + LITELLM_MASTER_KEY, or "
        "AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY, or OPENAI_API_KEY (or api_key)"
    )


def get_vendor_from_opts(opts=None):
    """
    Determine the AI vendor string from opts.

    When using LiteLLM, tries to infer the actual provider from the model
    name in opts (e.g. "claude-*" -> "anthropic"). Falls back to "litellm"
    if the model name doesn't match a known pattern.

    Returns one of: "openai", "azure", "anthropic", "google", "mistral",
    "meta", "cohere", or "litellm".
    """
    opts = opts or {}
    litellm_url = (opts.get("LITELLM_PROXY_URL") or "").strip()
    litellm_key = (opts.get("LITELLM_MASTER_KEY") or "").strip()
    if litellm_url and litellm_key:
        model = opts.get("model") or ""
        inferred = _infer_vendor_from_model_name(model)
        return inferred if inferred else "litellm"

    azure_endpoint = (opts.get("AZURE_OPENAI_ENDPOINT") or "").strip()
    azure_api_key = (opts.get("AZURE_OPENAI_API_KEY") or "").strip()
    if azure_endpoint and azure_api_key:
        return "azure"

    return "openai"


def _infer_vendor_from_model_name(model_name):
    """Infer vendor from a model name string. Returns None if unknown.

    Handles LiteLLM provider-prefixed names (e.g. "azure/gpt-4o",
    "anthropic/claude-3") as well as bare model names (e.g. "gpt-4o-mini").
    """
    if not model_name:
        return None
    parts = model_name.lower().split("/")
    # If a provider prefix is present, use it directly
    if len(parts) > 1:
        prefix_map = {
            "openai": "openai",
            "azure": "azure",
            "anthropic": "anthropic",
            "google": "google",
            "vertex_ai": "google",
            "mistral": "mistral",
            "meta": "meta",
            "cohere": "cohere",
            "groq": "groq",
            "bedrock": "bedrock",
        }
        if parts[0] in prefix_map:
            return prefix_map[parts[0]]
    # Fall back to model name pattern matching on the last segment
    m = parts[-1]
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gpt-") or m.startswith("o1") or m.startswith("o3") or m.startswith("chatgpt"):
        return "openai"
    if m.startswith("gemini"):
        return "google"
    if m.startswith("mistral") or m.startswith("mixtral"):
        return "mistral"
    if m.startswith("llama") or m.startswith("meta-llama"):
        return "meta"
    if m.startswith("command"):
        return "cohere"
    return None


def get_async_openai_client(opts=None):
    """
    Return an async OpenAI-compatible client. Same opts semantics as get_openai_client.
    LiteLLM proxy is used for both chat and embeddings when configured.
    """
    opts = opts or {}

    litellm_url = (opts.get("LITELLM_PROXY_URL") or "").strip().rstrip("/")
    litellm_key = (opts.get("LITELLM_MASTER_KEY") or "").strip()
    if litellm_url and litellm_key:
        logger.info("Using LiteLLM proxy at %s (async)", litellm_url)
        return AsyncOpenAI(
            api_key=litellm_key,
            base_url=litellm_url + "/v1",
            timeout=120.0,
            max_retries=0,
        )

    azure_endpoint = (opts.get("AZURE_OPENAI_ENDPOINT") or "").strip()
    azure_api_key = (opts.get("AZURE_OPENAI_API_KEY") or "").strip()
    azure_api_version = opts.get("AZURE_OPENAI_API_VERSION") or DEFAULT_AZURE_OPENAI_API_VERSION
    if azure_endpoint and azure_api_key:
        logger.info("Using Azure OpenAI client at endpoint: %s (async)", azure_endpoint)
        return AsyncAzureOpenAI(
            api_key=azure_api_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_api_version,
            timeout=120.0,
            max_retries=0,
        )

    openai_api_key = (
        opts.get("OPENAI_API_KEY")
        or opts.get("openai_api_key")
        or opts.get("api_key")
    )
    if openai_api_key:
        logger.info("Using public OpenAI client (async)")
        return AsyncOpenAI(api_key=openai_api_key, timeout=120.0, max_retries=0)

    raise ValueError(
        "Set LITELLM_PROXY_URL + LITELLM_MASTER_KEY, or "
        "AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY, or OPENAI_API_KEY (or api_key)"
    )
