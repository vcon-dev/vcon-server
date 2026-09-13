"""Redaction of link options before they leave the process.

Links record their `opts` into `analysis[].vendor_schema` and into logs. Those opts
carry provider credentials. Each link used to keep its own allowlist of names to drop,
which fails the moment a new credential option is added: a provider key reached every
transcribed vCon that way. Match by pattern instead, so an unknown credential is dropped
by default.
"""

from typing import Any, Dict

# ponytail: substring match on the name. Cheap, and it fails closed on new options.
SENSITIVE_NAME_PARTS = (
    "key",
    "token",
    "secret",
    "password",
    "passwd",
    "credential",
    "proxy_url",
)


# Not credentials, but internal endpoints that must not be recorded into stored vCons.
# `policy_url` and the like are public links and stay.
SENSITIVE_NAMES = {"send_ai_usage_data_to_url"}


def is_sensitive_name(name: str) -> bool:
    lowered = (name or "").lower()
    return lowered in SENSITIVE_NAMES or any(part in lowered for part in SENSITIVE_NAME_PARTS)


def safe_opts(opts: Dict[str, Any]) -> Dict[str, Any]:
    """Return opts with every credential-shaped option removed."""
    return {k: v for k, v in (opts or {}).items() if not is_sensitive_name(k)}
