"""Tests for _build_groq_client (Refactor #4).

The previous implementation monkey-patched httpx.Client at module import and
deleted proxy env vars process-wide. The replacement gives the Groq client its
own httpx.Client(trust_env=False) so only Groq ignores env proxy vars.
"""
from __future__ import annotations

from unittest.mock import patch

import httpx

from links.groq_whisper import _build_groq_client


def test_build_groq_client_uses_trust_env_false():
    """The Groq client must receive an httpx.Client with trust_env=False."""
    captured = {}

    class _CapturedClient(httpx.Client):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    with patch("links.groq_whisper.httpx.Client", _CapturedClient):
        client = _build_groq_client("fake-key")

    assert captured.get("trust_env") is False, (
        f"expected trust_env=False to be passed to httpx.Client; got {captured}"
    )
    # Sanity: we really constructed a Groq instance.
    assert client.__class__.__name__ == "Groq"


def test_build_groq_client_does_not_mutate_global_httpx_client():
    """Refactor #4 must not alter httpx.Client globally — that was the bug."""
    original_name = httpx.Client.__name__
    _build_groq_client("fake-key")
    assert httpx.Client.__name__ == original_name, (
        "httpx.Client must not be monkey-patched; only the per-Groq instance"
        " should be constructed with trust_env=False"
    )
