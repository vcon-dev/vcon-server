"""Tests for lib.vcon_compat.normalize_legacy_fields."""

from lib.vcon_compat import normalize_legacy_fields


def test_top_level_appended_to_amended():
    v = {"uuid": "u", "appended": {"uuid": "previous"}}
    normalize_legacy_fields(v)
    assert "appended" not in v
    assert v["amended"] == {"uuid": "previous"}


def test_top_level_must_support_to_critical():
    v = {"uuid": "u", "must_support": ["lawful_basis"]}
    normalize_legacy_fields(v)
    assert "must_support" not in v
    assert v["critical"] == ["lawful_basis"]


def test_spec_field_already_present_drops_legacy():
    v = {"uuid": "u", "appended": {"a": 1}, "amended": {"b": 2}}
    normalize_legacy_fields(v)
    assert "appended" not in v
    assert v["amended"] == {"b": 2}


def test_analysis_schema_version_to_schema():
    v = {
        "uuid": "u",
        "analysis": [
            {"type": "summary", "vendor": "openai", "schema_version": "v1"}
        ],
    }
    normalize_legacy_fields(v)
    a = v["analysis"][0]
    assert "schema_version" not in a
    assert a["schema"] == "v1"


def test_dialog_mimetype_to_mediatype():
    v = {
        "uuid": "u",
        "dialog": [{"type": "recording", "mimetype": "audio/wav"}],
    }
    normalize_legacy_fields(v)
    d = v["dialog"][0]
    assert "mimetype" not in d
    assert d["mediatype"] == "audio/wav"


def test_attachment_type_to_purpose_when_missing():
    v = {
        "uuid": "u",
        "attachments": [{"type": "tags", "body": []}],
    }
    normalize_legacy_fields(v)
    att = v["attachments"][0]
    assert att.get("purpose") == "tags"
    assert "type" not in att


def test_attachment_lawful_basis_keeps_type_when_purpose_present():
    """lawful_basis attachments legitimately carry both fields.

    The extension uses ``type: "lawful_basis"`` as the purpose value,
    but writers that follow the speckit will also set ``purpose``. If
    ``purpose`` is already populated, we must not clobber it.
    """
    v = {
        "uuid": "u",
        "attachments": [
            {"type": "lawful_basis", "purpose": "lawful_basis", "body": "{}"}
        ],
    }
    normalize_legacy_fields(v)
    att = v["attachments"][0]
    assert att["purpose"] == "lawful_basis"
    # ``type`` is retained because purpose was already set — drift between
    # the two is not our problem here.
    assert att["type"] == "lawful_basis"


def test_must_support_inside_attachment_to_critical():
    v = {
        "uuid": "u",
        "attachments": [{"purpose": "x", "must_support": True}],
    }
    normalize_legacy_fields(v)
    att = v["attachments"][0]
    assert "must_support" not in att
    assert att["critical"] is True


def test_empty_or_missing_fields_safe():
    # No-ops should not blow up.
    normalize_legacy_fields({})
    normalize_legacy_fields({"uuid": "u"})
    normalize_legacy_fields({"uuid": "u", "analysis": None, "dialog": None})


def test_returns_same_dict():
    v = {"uuid": "u"}
    assert normalize_legacy_fields(v) is v
