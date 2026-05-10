"""Tests for the unified transcribe dispatcher."""

import sys
import types
from unittest.mock import patch

import pytest

from links.transcribe import run as transcribe_run, _VENDOR_MODULES


def _install_fake_vendor(monkeypatch, module_path: str, return_value="vcon-uuid"):
    """Install a fake vendor module that records its ``run`` arguments."""
    fake = types.ModuleType(module_path)
    calls = []

    def fake_run(vcon_uuid, link_name, opts):
        calls.append({"vcon_uuid": vcon_uuid, "link_name": link_name, "opts": opts})
        return return_value

    fake.run = fake_run
    monkeypatch.setitem(sys.modules, module_path, fake)
    return calls


def test_dispatch_to_openai(monkeypatch):
    calls = _install_fake_vendor(monkeypatch, _VENDOR_MODULES["openai"])
    result = transcribe_run(
        "uuid-1",
        "my_link",
        {"vendor": "openai", "vendor_options": {"api_key": "secret", "model": "whisper-1"}},
    )
    assert result == "vcon-uuid"
    assert len(calls) == 1
    assert calls[0]["vcon_uuid"] == "uuid-1"
    assert calls[0]["opts"] == {"api_key": "secret", "model": "whisper-1"}


def test_dispatch_to_groq(monkeypatch):
    calls = _install_fake_vendor(monkeypatch, _VENDOR_MODULES["groq"])
    transcribe_run("u", "l", {"vendor": "groq", "vendor_options": {"k": "v"}})
    assert calls[0]["opts"] == {"k": "v"}


def test_dispatch_to_hugging_face(monkeypatch):
    calls = _install_fake_vendor(monkeypatch, _VENDOR_MODULES["hugging_face"])
    transcribe_run("u", "l", {"vendor": "hugging_face", "vendor_options": {}})
    assert len(calls) == 1


def test_dispatch_to_deepgram(monkeypatch):
    calls = _install_fake_vendor(monkeypatch, _VENDOR_MODULES["deepgram"])
    transcribe_run("u", "l", {"vendor": "deepgram", "vendor_options": {}})
    assert len(calls) == 1


def test_unknown_vendor_raises():
    with pytest.raises(ValueError, match="unknown vendor"):
        transcribe_run("u", "l", {"vendor": "nonsense"})


def test_default_vendor_is_whisper_builtin(monkeypatch):
    """A missing ``vendor:`` falls back to the historical built-in behavior.

    We verify by patching VconRedis and the Vcon object so the call path
    is exercised without touching real Whisper.
    """
    with patch("links.transcribe.VconRedis") as mock_redis_cls:
        instance = mock_redis_cls.return_value
        vcon_obj = instance.get_vcon.return_value
        # Simulate "no new analysis added" so store_vcon is skipped.
        vcon_obj.analysis = []
        vcon_obj.transcribe.return_value = vcon_obj  # same object back

        result = transcribe_run("u", "l", {"transcribe_options": {"model_size": "tiny"}})
        assert result == "u"
        vcon_obj.transcribe.assert_called_once_with(model_size="tiny")
        instance.store_vcon.assert_not_called()


def test_whisper_builtin_stores_when_new_analysis(monkeypatch):
    from unittest.mock import MagicMock
    with patch("links.transcribe.VconRedis") as mock_redis_cls:
        instance = mock_redis_cls.return_value
        vcon_obj = MagicMock()
        # Before transcribe(): no analysis. After: one entry.
        vcon_obj.analysis = []
        instance.get_vcon.return_value = vcon_obj
        annotated = MagicMock()
        annotated.analysis = [{"type": "transcript"}]
        vcon_obj.transcribe.return_value = annotated

        transcribe_run("u", "l", {"vendor": "whisper_builtin", "vendor_options": {}})
        instance.store_vcon.assert_called_once()
