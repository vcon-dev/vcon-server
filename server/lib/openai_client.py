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
