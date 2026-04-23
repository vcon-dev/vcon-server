"""Tests for shared retry + redact utilities (Refactor #3)."""
from __future__ import annotations

import pytest

from lib.redact import redact, register_sensitive_keys
from lib.retry import with_backoff


class _Attempts:
    def __init__(self, fail_count: int):
        self.fail_count = fail_count
        self.seen = 0

    def __call__(self):
        self.seen += 1
        if self.seen <= self.fail_count:
            raise RuntimeError(f"transient {self.seen}")
        return "ok"


def test_backoff_recovers_from_transient_failures():
    fn = _Attempts(fail_count=2)
    wrapped = with_backoff(max_attempts=5, multiplier=0, min_wait=0, max_wait=0)(fn)
    assert wrapped() == "ok"
    assert fn.seen == 3


def test_backoff_exhausts_and_reraises():
    fn = _Attempts(fail_count=10)
    wrapped = with_backoff(max_attempts=3, multiplier=0, min_wait=0, max_wait=0)(fn)
    with pytest.raises(RuntimeError):
        wrapped()
    assert fn.seen == 3


def test_backoff_retry_on_specific_type_only():
    class MyError(Exception):
        pass

    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise ValueError("never retry me")

    wrapped = with_backoff(
        max_attempts=5,
        multiplier=0,
        min_wait=0,
        max_wait=0,
        retry_on=(MyError,),
    )(fn)
    with pytest.raises(ValueError):
        wrapped()
    assert attempts["n"] == 1  # no retry for ValueError when retry_on=MyError


def test_redact_drops_default_sensitive_keys():
    opts = {
        "DEEPGRAM_KEY": "sk-1",
        "LITELLM_MASTER_KEY": "sk-2",
        "ai_usage_api_token": "tok",
        "minimum_duration": 60,
        "model": "nova-3",
    }
    safe = redact(opts)
    assert safe == {"minimum_duration": 60, "model": "nova-3"}


def test_redact_with_extra_keys():
    opts = {"custom_secret": "hush", "keep_me": "ok"}
    assert redact(opts, extra_keys=["custom_secret"]) == {"keep_me": "ok"}


def test_redact_passthrough_for_non_dict():
    assert redact("not-a-dict") == "not-a-dict"
    assert redact(None) is None
    assert redact([1, 2, 3]) == [1, 2, 3]


def test_register_sensitive_keys_persists():
    register_sensitive_keys("ONE_TIME_SECRET_TEST_KEY")
    try:
        out = redact({"ONE_TIME_SECRET_TEST_KEY": "x", "ok": 1})
        assert out == {"ok": 1}
    finally:
        # Clean up so this doesn't pollute other tests.
        from lib.redact import _DEFAULT_SENSITIVE

        _DEFAULT_SENSITIVE.discard("ONE_TIME_SECRET_TEST_KEY")
