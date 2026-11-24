from lib.redaction import safe_opts


def test_drops_credential_shaped_options():
    opts = {
        "model": "distil-whisper/distil-large-v2",
        "language": "en",
        "OPENAI_API_KEY": "sk-live",
        "LITELLM_MASTER_KEY": "sk-litellm",
        "LITELLM_PROXY_URL": "https://proxy.invalid",
        "ai_usage_api_token": "t",
        "aws_secret_access_key": "s",
        "db_password": "p",
        "send_ai_usage_data_to_url": "https://usage.internal",
    }
    assert safe_opts(opts) == {"model": "distil-whisper/distil-large-v2", "language": "en"}


def test_unknown_credential_option_is_dropped_too():
    # the bug: an allowlist misses the next key that gets added
    assert safe_opts({"SOME_NEW_PROVIDER_KEY": "x"}) == {}


def test_public_urls_are_kept():
    assert safe_opts({"policy_url": "https://example.com/dpa"}) == {"policy_url": "https://example.com/dpa"}


def test_handles_empty():
    assert safe_opts({}) == {}
    assert safe_opts(None) == {}
