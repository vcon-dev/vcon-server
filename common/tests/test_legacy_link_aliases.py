"""Tests for the legacy link-module alias resolver in conserver/main.py.

The resolver is what lets chain configs that still say
``module: links.openai_transcribe`` keep working after the
transcribe-link consolidation. It rewrites the module to
``links.transcribe`` and injects the inferred ``vendor`` into options.
"""

from main import _resolve_link_module_and_options


def test_unknown_module_passthrough():
    mod, opts = _resolve_link_module_and_options("links.analyze", {"x": 1})
    assert mod == "links.analyze"
    assert opts == {"x": 1}


def test_none_options_passthrough_for_unknown_module():
    mod, opts = _resolve_link_module_and_options("links.summary", None)
    assert mod == "links.summary"
    assert opts is None


def test_openai_transcribe_rewrites_to_dispatcher():
    mod, opts = _resolve_link_module_and_options(
        "links.openai_transcribe",
        {"api_key": "secret", "model": "whisper-1"},
    )
    assert mod == "links.transcribe"
    assert opts == {
        "vendor": "openai",
        "vendor_options": {"api_key": "secret", "model": "whisper-1"},
    }


def test_groq_whisper_rewrites_to_dispatcher():
    mod, opts = _resolve_link_module_and_options("links.groq_whisper", {})
    assert mod == "links.transcribe"
    assert opts["vendor"] == "groq"


def test_hugging_face_whisper_rewrites_to_dispatcher():
    mod, _ = _resolve_link_module_and_options("links.hugging_face_whisper", {})
    assert mod == "links.transcribe"


def test_deepgram_link_rewrites_to_dispatcher():
    mod, opts = _resolve_link_module_and_options("links.deepgram_link", {"api_key": "x"})
    assert mod == "links.transcribe"
    assert opts == {"vendor": "deepgram", "vendor_options": {"api_key": "x"}}


def test_already_dispatcher_shaped_options_respected():
    """If a config already used vendor/vendor_options, don't double-wrap."""
    mod, opts = _resolve_link_module_and_options(
        "links.openai_transcribe",
        {"vendor": "openai", "vendor_options": {"api_key": "x"}},
    )
    assert mod == "links.transcribe"
    assert opts == {"vendor": "openai", "vendor_options": {"api_key": "x"}}


def test_legacy_options_with_none():
    mod, opts = _resolve_link_module_and_options("links.openai_transcribe", None)
    assert mod == "links.transcribe"
    assert opts == {"vendor": "openai", "vendor_options": {}}
