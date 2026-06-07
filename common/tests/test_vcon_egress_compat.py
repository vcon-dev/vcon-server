"""Tests for lib.vcon_egress_compat.to_legacy (CON-581).

Covers each field delta, the lawful_basis caveat, non-mutation of the input,
unsupported-version rejection, a round-trip against the forward normalizer
(drift guard), and validation against the derived 0.0.1 schema.
"""

import copy
import json
import os
from unittest.mock import patch

import pytest

from lib.vcon_compat import normalize_legacy_fields
from lib.vcon_egress_compat import SUPPORTED_VERSIONS, to_configured_legacy, to_legacy

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schemas", "vcon-0.0.1.schema.json")


def _canonical_vcon():
    """A spec-current (0.4.0) vCon mirroring the production shape."""
    return {
        "vcon": "0.4.0",
        "uuid": "0190a0e0-0000-8000-8000-000000000000",
        "created_at": "2026-06-05T00:00:00+00:00",
        "subject": None,
        "amended": {"uuid": "previous"},
        "critical": ["lawful_basis"],
        "parties": [{"tel": "+15551234567", "name": "Alice", "role": "customer"}],
        "dialog": [
            {
                "type": "recording",
                "start": "2026-06-05T00:00:00+00:00",
                "parties": [0],
                "mediatype": "audio/wav",
                "url": "https://example.com/a.wav",
            }
        ],
        "analysis": [
            {
                "type": "summary",
                "dialog": 0,
                "vendor": "openai",
                "body": "a summary",
                "encoding": "none",
                "schema": "v1",
            }
        ],
        "attachments": [
            {"purpose": "tags", "body": ["category:1"], "encoding": "none"},
            # lawful_basis legitimately carries a `type` value — must survive.
            {"type": "lawful_basis", "body": "consent", "encoding": "none"},
        ],
        "meta": {"tenant_id": 42},
    }


def test_version_is_stamped():
    out = to_legacy(_canonical_vcon(), "0.0.1")
    assert out["vcon"] == "0.0.1"


def test_top_level_renames():
    out = to_legacy(_canonical_vcon(), "0.0.1")
    assert "amended" not in out and out["appended"] == {"uuid": "previous"}
    assert "critical" not in out and out["must_support"] == ["lawful_basis"]


def test_attachment_purpose_to_type():
    out = to_legacy(_canonical_vcon(), "0.0.1")
    tags = out["attachments"][0]
    assert tags.get("type") == "tags"
    assert "purpose" not in tags


def test_attachment_lawful_basis_type_preserved():
    out = to_legacy(_canonical_vcon(), "0.0.1")
    lb = out["attachments"][1]
    assert lb["type"] == "lawful_basis"
    assert "purpose" not in lb


def test_dialog_mediatype_to_mimetype():
    out = to_legacy(_canonical_vcon(), "0.0.1")
    d = out["dialog"][0]
    assert d.get("mimetype") == "audio/wav"
    assert "mediatype" not in d


def test_analysis_schema_to_schema_version():
    out = to_legacy(_canonical_vcon(), "0.0.1")
    a = out["analysis"][0]
    assert a.get("schema_version") == "v1"
    assert "schema" not in a


def test_json_string_body_inflated_to_native():
    """Reverse VconRedis._stringify_json_body: encoding 'json' string body
    becomes a native object/array with encoding 'none'."""
    canonical = _canonical_vcon()
    canonical["attachments"] = [
        {"purpose": "tags", "body": '["source:crexendo", "direction:out"]', "encoding": "json"},
        {"purpose": "tenant", "body": '{"id": 385}', "encoding": "json"},
    ]
    canonical["analysis"] = [
        {"type": "transcript", "dialog": 0, "vendor": "x", "body": '{"transcript": "hi"}', "encoding": "json"},
    ]
    out = to_legacy(canonical, "0.0.1")
    assert out["attachments"][0]["body"] == ["source:crexendo", "direction:out"]
    assert out["attachments"][0]["encoding"] == "none"
    assert out["attachments"][1]["body"] == {"id": 385}
    assert out["analysis"][0]["body"] == {"transcript": "hi"}
    assert out["analysis"][0]["encoding"] == "none"


def test_plain_string_body_untouched():
    """A non-JSON body (encoding != 'json') is left exactly as-is."""
    canonical = _canonical_vcon()
    canonical["analysis"] = [
        {"type": "summary", "dialog": 0, "vendor": "openai", "body": "a sentence", "encoding": "none"},
    ]
    out = to_legacy(canonical, "0.0.1")
    assert out["analysis"][0]["body"] == "a sentence"
    assert out["analysis"][0]["encoding"] == "none"


def test_invalid_json_body_left_as_is():
    """encoding 'json' but unparseable body is not mangled."""
    canonical = _canonical_vcon()
    canonical["attachments"] = [{"purpose": "x", "body": "{not json", "encoding": "json"}]
    out = to_legacy(canonical, "0.0.1")
    assert out["attachments"][0]["body"] == "{not json"
    assert out["attachments"][0]["encoding"] == "json"


def test_dialog_body_not_inflated():
    """Dialog bodies are not stringified on write, so they must not be touched."""
    canonical = _canonical_vcon()
    canonical["dialog"] = [
        {"type": "text", "start": "t", "body": '{"parts": []}', "encoding": "json"},
    ]
    out = to_legacy(canonical, "0.0.1")
    # Unchanged: still the JSON string with encoding json.
    assert out["dialog"][0]["body"] == '{"parts": []}'
    assert out["dialog"][0]["encoding"] == "json"


def test_legacy_top_level_keys_present_when_dropped():
    canonical = _canonical_vcon()
    # 0.4.0 lib drops empty group/redacted entirely.
    canonical.pop("group", None)
    canonical.pop("redacted", None)
    out = to_legacy(canonical, "0.0.1")
    assert out["group"] == []
    assert out["redacted"] == {}
    assert "appended" in out


def test_input_is_not_mutated():
    canonical = _canonical_vcon()
    before = copy.deepcopy(canonical)
    to_legacy(canonical, "0.0.1")
    assert canonical == before


def test_unsupported_version_raises():
    with pytest.raises(ValueError):
        to_legacy(_canonical_vcon(), "9.9.9")


def test_supported_versions_contains_001():
    assert "0.0.1" in SUPPORTED_VERSIONS


def test_round_trip_restores_spec_form():
    """Downgrading then re-normalizing must restore the spec field names.

    This guards against to_legacy drifting from vcon_compat.normalize_legacy_fields.
    """
    legacy = to_legacy(_canonical_vcon(), "0.0.1")
    renorm = normalize_legacy_fields(copy.deepcopy(legacy))
    assert renorm["amended"] == {"uuid": "previous"}
    assert renorm["critical"] == ["lawful_basis"]
    assert renorm["attachments"][0]["purpose"] == "tags"
    assert renorm["dialog"][0]["mediatype"] == "audio/wav"
    assert renorm["analysis"][0]["schema"] == "v1"


# --- schema validation -----------------------------------------------------

def _schema():
    with open(SCHEMA_PATH) as fh:
        return json.load(fh)


def test_downgraded_payload_validates_against_legacy_schema():
    jsonschema = pytest.importorskip("jsonschema")
    out = to_legacy(_canonical_vcon(), "0.0.1")
    jsonschema.validate(instance=out, schema=_schema())


def test_canonical_payload_fails_legacy_schema():
    jsonschema = pytest.importorskip("jsonschema")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=_canonical_vcon(), schema=_schema())


# --- to_configured_legacy (reads the EGRESS_FORMAT_VERSION setting) --------

def test_to_configured_legacy_applies_when_set():
    with patch("settings.EGRESS_FORMAT_VERSION", "0.0.1"):
        out = to_configured_legacy(_canonical_vcon())
    assert out["vcon"] == "0.0.1"
    assert out["attachments"][0].get("type") == "tags"


def test_to_configured_legacy_noop_when_unset():
    original = _canonical_vcon()
    with patch("settings.EGRESS_FORMAT_VERSION", None):
        out = to_configured_legacy(original)
    # Unset → returned unchanged (same object, current spec).
    assert out is original
    assert out["vcon"] == "0.4.0"
