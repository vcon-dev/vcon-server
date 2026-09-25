"""Tests for VconRedis._enforce_spec_on_write."""

from lib.vcon_redis import VconRedis


def test_sets_missing_syntax_param():
    d = {"uuid": "u"}
    VconRedis._enforce_spec_on_write(d)
    assert d["vcon"] == "0.4.0"


def test_keeps_existing_syntax_param():
    d = {"uuid": "u", "vcon": "0.4.0"}
    VconRedis._enforce_spec_on_write(d)
    assert d["vcon"] == "0.4.0"


def test_upgrades_legacy_syntax_param():
    # A stale legacy version is stamped to the current spec, since the field
    # names are normalized up to that spec on the same pass.
    d = {"uuid": "u", "vcon": "0.0.1"}
    VconRedis._enforce_spec_on_write(d)
    assert d["vcon"] == "0.4.0"


def test_strips_empty_group():
    d = {"uuid": "u", "group": []}
    VconRedis._enforce_spec_on_write(d)
    assert "group" not in d


def test_strips_empty_redacted():
    d = {"uuid": "u", "redacted": {}}
    VconRedis._enforce_spec_on_write(d)
    assert "redacted" not in d


def test_keeps_non_empty_group_and_redacted():
    d = {
        "uuid": "u",
        "group": [{"uuid": "g1"}],
        "redacted": {"uuid": "previous"},
    }
    VconRedis._enforce_spec_on_write(d)
    assert d["group"] == [{"uuid": "g1"}]
    assert d["redacted"] == {"uuid": "previous"}


def test_returns_same_dict():
    d = {"uuid": "u"}
    assert VconRedis._enforce_spec_on_write(d) is d


def test_keeps_dict_analysis_body_raw_and_fixes_encoding():
    # draft-ietf-vcon-vcon-core-04 §2.3.2: encoding "json" bodies are the
    # JSON value itself. A dict body that arrived with encoding "none" is a
    # real mismatch — fix the encoding, but never stringify the value.
    d = {
        "uuid": "u",
        "analysis": [
            {
                "type": "summary",
                "vendor": "openai",
                "body": {"k": "v"},
                "encoding": "none",
            }
        ],
    }
    VconRedis._enforce_spec_on_write(d)
    a = d["analysis"][0]
    assert a["body"] == {"k": "v"}
    assert a["encoding"] == "json"


def test_keeps_list_analysis_body_raw_and_fixes_encoding():
    d = {
        "uuid": "u",
        "analysis": [
            {
                "type": "scitt_receipt",
                "vendor": "scittles",
                "body": [{"entry_id": "abc"}],
                "encoding": "none",
            }
        ],
    }
    VconRedis._enforce_spec_on_write(d)
    a = d["analysis"][0]
    assert a["body"] == [{"entry_id": "abc"}]
    assert a["encoding"] == "json"


def test_keeps_dict_body_raw_when_encoding_already_json():
    # Adapters now emit raw values directly with encoding already "json" —
    # no mismatch to fix, value must be untouched.
    d = {
        "uuid": "u",
        "analysis": [
            {
                "type": "summary",
                "vendor": "openai",
                "body": {"k": "v"},
                "encoding": "json",
            }
        ],
    }
    VconRedis._enforce_spec_on_write(d)
    a = d["analysis"][0]
    assert a["body"] == {"k": "v"}
    assert a["encoding"] == "json"


def test_leaves_string_body_alone():
    d = {
        "uuid": "u",
        "analysis": [
            {
                "type": "transcript",
                "vendor": "openai",
                "body": "hello world",
                "encoding": "none",
            }
        ],
    }
    VconRedis._enforce_spec_on_write(d)
    a = d["analysis"][0]
    assert a["body"] == "hello world"
    assert a["encoding"] == "none"


def test_leaves_legacy_stringified_json_body_alone():
    # A str body already carrying encoding "json" is the legacy -02 shape.
    # It must not be re-parsed or otherwise mutated on write.
    d = {
        "uuid": "u",
        "analysis": [
            {
                "type": "summary",
                "vendor": "openai",
                "body": '{"k": "v"}',
                "encoding": "json",
            }
        ],
    }
    VconRedis._enforce_spec_on_write(d)
    a = d["analysis"][0]
    assert a["body"] == '{"k": "v"}'
    assert a["encoding"] == "json"


def test_keeps_dict_attachment_body_raw_and_fixes_encoding():
    d = {
        "uuid": "u",
        "attachments": [
            {"purpose": "tags", "party": 0, "dialog": 0, "body": {"tag": "x"}}
        ],
    }
    VconRedis._enforce_spec_on_write(d)
    att = d["attachments"][0]
    assert att["body"] == {"tag": "x"}
    assert att["encoding"] == "json"


def test_renames_legacy_attachment_type_to_purpose():
    d = {
        "uuid": "u",
        "attachments": [
            {"type": "tags", "party": 0, "dialog": 0, "body": "x"}
        ],
    }
    VconRedis._enforce_spec_on_write(d)
    att = d["attachments"][0]
    assert "type" not in att
    assert att["purpose"] == "tags"


def test_renames_top_level_appended_to_amended():
    d = {"uuid": "u", "appended": [{"uuid": "prev"}]}
    VconRedis._enforce_spec_on_write(d)
    assert "appended" not in d
    assert d["amended"] == [{"uuid": "prev"}]
