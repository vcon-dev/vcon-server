from unittest.mock import Mock, patch

import pytest

from lib.openai_client import (
    DEFAULT_AZURE_OPENAI_API_VERSION,
    _infer_vendor_from_model_name,
    get_async_openai_client,
    get_openai_client,
    get_vendor_from_opts,
)


@patch("lib.openai_client.OpenAI")
def test_get_openai_client_prefers_litellm_proxy(mock_openai):
    client = Mock()
    mock_openai.return_value = client

    result = get_openai_client(
        {
            "LITELLM_PROXY_URL": "https://proxy.test/ ",
            "LITELLM_MASTER_KEY": "secret",
            "organization_key": "org-1",
            "project_key": "proj-1",
        }
    )

    assert result is client
    mock_openai.assert_called_once_with(
        api_key="secret",
        base_url="https://proxy.test",
        organization="org-1",
        project="proj-1",
        timeout=120.0,
        max_retries=0,
    )


@patch("lib.openai_client.AzureOpenAI")
def test_get_openai_client_uses_azure_defaults(mock_azure_openai):
    client = Mock()
    mock_azure_openai.return_value = client

    result = get_openai_client(
        {
            "AZURE_OPENAI_ENDPOINT": "https://azure.test",
            "AZURE_OPENAI_API_KEY": "azure-key",
        }
    )

    assert result is client
    mock_azure_openai.assert_called_once_with(
        api_key="azure-key",
        azure_endpoint="https://azure.test",
        api_version=DEFAULT_AZURE_OPENAI_API_VERSION,
        timeout=120.0,
        max_retries=0,
    )


@patch("lib.openai_client.OpenAI")
def test_get_openai_client_uses_public_openai_aliases(mock_openai):
    client = Mock()
    mock_openai.return_value = client

    result = get_openai_client(
        {
            "api_key": "public-key",
            "organization": "org-2",
            "project": "proj-2",
        }
    )

    assert result is client
    mock_openai.assert_called_once_with(
        api_key="public-key",
        organization="org-2",
        project="proj-2",
        timeout=120.0,
        max_retries=0,
    )


@patch("lib.openai_client.AsyncOpenAI")
def test_get_async_openai_client_appends_v1_for_litellm(mock_async_openai):
    client = Mock()
    mock_async_openai.return_value = client

    result = get_async_openai_client(
        {
            "LITELLM_PROXY_URL": "https://proxy.test/",
            "LITELLM_MASTER_KEY": "secret",
        }
    )

    assert result is client
    mock_async_openai.assert_called_once_with(
        api_key="secret",
        base_url="https://proxy.test/v1",
        timeout=120.0,
        max_retries=0,
    )


@pytest.mark.parametrize(
    ("model_name", "expected_vendor"),
    [
        ("anthropic/claude-3", "anthropic"),
        ("vertex_ai/gemini-1.5", "google"),
        ("gpt-4o-mini", "openai"),
        ("mixtral-8x7b", "mistral"),
        ("meta-llama/llama-3", "meta"),
        ("command-r", "cohere"),
    ],
)
def test_infer_vendor_from_model_name(model_name, expected_vendor):
    assert _infer_vendor_from_model_name(model_name) == expected_vendor


def test_get_vendor_from_opts_prefers_inferred_litellm_vendor():
    assert get_vendor_from_opts(
        {
            "LITELLM_PROXY_URL": "https://proxy.test",
            "LITELLM_MASTER_KEY": "secret",
            "model": "anthropic/claude-3-5-sonnet",
        }
    ) == "anthropic"


def test_get_openai_client_requires_credentials():
    with pytest.raises(ValueError, match="Set LITELLM_PROXY_URL"):
        get_openai_client({})
