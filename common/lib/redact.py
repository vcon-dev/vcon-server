"""Credential redaction for link option dicts (Refactor #3).

Used wherever options (from chain config) are logged or persisted on a vCon
(audit trails, vendor_schema attachments, etc.). Drops known-sensitive keys
so we never leak API tokens in logs or stored artifacts.

Extend the default list by passing `extra_keys` or via the module-level
`register_sensitive_keys(...)` helper if you own a new secret-bearing field.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


# Keys that always indicate a secret. Conservative by design: adding to this
# set never breaks callers, only hides more fields. Literal match (not substring).
_DEFAULT_SENSITIVE: set[str] = {
    # Vendor API tokens
    "DEEPGRAM_KEY",
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "ANTHROPIC_API_KEY",
    "API_KEY",
    "api_key",
    # Gateway credentials
    "LITELLM_PROXY_URL",
    "LITELLM_MASTER_KEY",
    # In-house usage telemetry
    "ai_usage_api_token",
    "send_ai_usage_data_to_url",
    # SCITT signing material
    "SCITT_PRIVATE_KEY",
    "SCITT_PRIVATE_KEY_PEM",
    # AWS
    "aws_access_key_id",
    "aws_secret_access_key",
    # Webhook/HTTP auth
    "webhook_secret",
    "authorization",
    "Authorization",
}


def register_sensitive_keys(*keys: str) -> None:
    """Add additional keys to the module-level default block-list.

    Call this from a plugin's top-level code if it introduces a new
    secret-bearing field that other logs/utilities should redact too.
    """
    _DEFAULT_SENSITIVE.update(keys)


def redact(opts: Any, extra_keys: Iterable[str] = ()) -> Any:
    """Return a shallow copy of ``opts`` with sensitive keys removed.

    - If ``opts`` is not a dict, it is returned unchanged.
    - Only top-level keys are considered; nested dicts are **not** recursed.
    - Uses the module-level default list plus ``extra_keys``.

    Example:
        >>> redact({"DEEPGRAM_KEY": "sk-xxx", "minimum_duration": 60})
        {'minimum_duration': 60}
    """
    if not isinstance(opts, Mapping):
        return opts
    blocklist = _DEFAULT_SENSITIVE | set(extra_keys)
    return {k: v for k, v in opts.items() if k not in blocklist}
