import pytest
import warnings
from vcon import Vcon
import json

"""
This covers testing the main methods of the Vcon class, including:

Building from JSON
Building a new instance
Adding and retrieving tags
Adding and finding attachments
Adding and finding analysis
Adding parties and dialogs
Serializing to JSON
Generating a UUID8 based on a domain name


"""
def test_build_from_json():
    json_string = '{"uuid": "12345", "vcon": "0.0.1", "created_at": "2023-05-02T12:00:00+00:00", "redacted": {}, "group": [], "parties": [], "dialog": [], "attachments": [], "analysis": []}'
    vcon = Vcon.build_from_json(json_string)
    assert vcon.uuid == "12345"
    assert vcon.vcon == "0.0.1"
    assert vcon.created_at == "2023-05-02T12:00:00+00:00"


def test_build_new():
    vcon = Vcon.build_new()
    assert vcon.uuid is not None
    assert vcon.vcon == "0.0.1"
    assert vcon.created_at is not None


def test_tags():
    vcon = Vcon.build_new()
    assert vcon.tags is None
    
    vcon.add_tag("test_tag", "test_value")
    assert vcon.get_tag("test_tag") == "test_value"


def test_add_attachment():
    vcon = Vcon.build_new()
    vcon.add_attachment(body={"key": "value"}, type="test_type")
    attachment = vcon.find_attachment_by_purpose("test_type")
    # Per spec body is always String — a dict input is JSON-encoded at the
    # boundary and ``encoding`` is forced to ``json``. The original Python
    # value round-trips via Vcon.decoded_body.
    assert attachment["body"] == json.dumps({"key": "value"})
    assert attachment["encoding"] == "json"
    assert Vcon.decoded_body(attachment) == {"key": "value"}


def test_add_attachment_keeps_freeform_string_body_unchanged():
    vcon = Vcon.build_new()
    vcon.add_attachment(body="just text", type="note", encoding="none")
    attachment = vcon.find_attachment_by_purpose("note")
    assert attachment == {"type": "note", "body": "just text", "encoding": "none"}


def test_add_analysis():
    vcon = Vcon.build_new()
    vcon.add_analysis(type="test_type", dialog=[1, 2], vendor="test_vendor", body={"key": "value"})
    analysis = vcon.find_analysis_by_type("test_type")
    assert analysis["body"] == json.dumps({"key": "value"})
    assert analysis["encoding"] == "json"
    assert analysis["dialog"] == [1, 2]
    assert analysis["vendor"] == "test_vendor"
    assert Vcon.decoded_body(analysis) == {"key": "value"}


def test_add_party():
    vcon = Vcon.build_new()
    vcon.add_party({"id": "party1"})
    assert vcon.find_party_index("id", "party1") == 0


def test_add_dialog():
    vcon = Vcon.build_new()
    vcon.add_dialog({"id": "dialog1"})
    assert vcon.find_dialog("id", "dialog1") == {"id": "dialog1"}


def test_to_json():
    vcon = Vcon.build_new()
    json_string = vcon.to_json()
    assert json.loads(json_string) == vcon.to_dict()


def test_uuid8_domain_name():
    uuid8 = Vcon.uuid8_domain_name("test.com")
    assert uuid8[14] == "8"  # check version is 8


def test_get_tag():
    vcon = Vcon.build_new()
    vcon.add_tag("test_tag", "test_value")
    assert vcon.get_tag("test_tag") == "test_value"
    assert vcon.get_tag("nonexistent_tag") is None


def test_find_attachment_by_type():
    # Deprecated alias — still works for callers written against pre-0.4.0
    # vCon shape, finding attachments stored with the legacy `type` key.
    vcon = Vcon.build_new()
    vcon.add_attachment(body={"key": "value"}, type="test_type")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        assert vcon.find_attachment_by_type("test_type") == {
            "type": "test_type",
            "body": json.dumps({"key": "value"}),
            "encoding": "json",
        }
        assert vcon.find_attachment_by_type("nonexistent_type") is None


def test_find_attachment_by_type_emits_deprecation_warning():
    vcon = Vcon.build_new()
    vcon.add_attachment(body={"k": "v"}, type="x")
    with pytest.warns(DeprecationWarning, match="find_attachment_by_purpose"):
        vcon.find_attachment_by_type("x")


@pytest.fixture
def vcon_logger_propagates():
    # ``common/logging.conf`` sets ``[logger_vcon] propagate = 0`` so log
    # records go straight to the project's JSON stdout handler and bypass
    # the root logger that ``caplog`` attaches to. Force propagation for
    # the duration of the test so ``caplog.records`` actually sees the
    # records, then restore the original setting.
    import logging
    logger = logging.getLogger("vcon")
    saved_propagate = logger.propagate
    saved_disabled = logger.disabled
    logger.propagate = True
    logger.disabled = False
    try:
        yield logger
    finally:
        logger.propagate = saved_propagate
        logger.disabled = saved_disabled


def test_init_coerces_json_string_arg_and_logs_caller(caplog, vcon_logger_propagates):
    # Production logs show callers occasionally pass a JSON-encoded string
    # instead of a dict. Pre-fix, json.loads(json.dumps(str)) silently
    # round-trips and leaves vcon_dict as a str — every downstream method
    # then crashes with TypeError: string indices must be integers.
    # Post-fix, __init__ must coerce the string back to a dict and emit
    # an ERROR log with a caller stack so the originating call site is
    # findable.
    payload = '{"uuid": "abc", "vcon": "0.0.1", "attachments": [{"purpose": "tags", "body": "[]", "encoding": "json"}], "parties": [], "dialog": [], "analysis": [], "group": [], "redacted": {}}'
    with caplog.at_level("ERROR", logger="vcon"):
        v = Vcon(payload)
    assert isinstance(v.vcon_dict, dict)
    assert v.vcon_dict["uuid"] == "abc"
    # add_tag would otherwise raise TypeError here pre-fix
    v.add_tag("k", "v")
    assert any("received a str" in rec.message for rec in caplog.records)
    assert any(rec.stack_info for rec in caplog.records if "received a str" in rec.message)


def test_init_bails_to_empty_dict_for_non_json_string(caplog, vcon_logger_propagates):
    # If the bad input is not even valid JSON, fall through to an empty
    # vcon_dict rather than leaving a poisoned string. Caller stack must
    # still be logged so the broken caller is findable.
    with caplog.at_level("ERROR", logger="vcon"):
        v = Vcon("not even json")
    assert v.vcon_dict == {}
    assert any("received a str" in rec.message for rec in caplog.records)


def test_find_attachment_by_purpose_matches_purpose_key():
    # IETF vCon spec 0.4.0 renamed `type` → `purpose` on attachments. The
    # canonical lookup must find attachments authored by spec-current writers.
    vcon = Vcon.build_new()
    vcon.vcon_dict["attachments"].append(
        {"purpose": "spec_current", "body": {"k": "v"}, "encoding": "none"}
    )
    found = vcon.find_attachment_by_purpose("spec_current")
    assert found is not None
    assert found.get("purpose") == "spec_current"


def test_find_attachment_by_purpose_matches_legacy_type_key():
    # Back-compat: an attachment stored under the old `type` key must still be
    # discoverable via the new canonical lookup name. Mirrors how the Redis
    # storage layer tolerates both shapes.
    vcon = Vcon.build_new()
    vcon.add_attachment(body={"k": "v"}, type="legacy")
    assert vcon.find_attachment_by_purpose("legacy") is not None


def test_find_attachment_by_purpose_tolerates_missing_keys():
    # Some attachments in the wild are missing both `type` and `purpose`
    # (e.g. encoding-only payloads from older link versions). Lookup must not
    # raise KeyError — previously it did `a["type"]` and crashed the chain.
    vcon = Vcon.build_new()
    vcon.vcon_dict["attachments"].append({"body": "no key", "encoding": "none"})
    vcon.add_attachment(body={"k": "v"}, type="findable")
    assert vcon.find_attachment_by_purpose("findable") is not None
    assert vcon.find_attachment_by_purpose("nonexistent") is None


def test_find_analysis_by_type():
    vcon = Vcon.build_new()
    vcon.add_analysis(type="test_type", dialog=[1, 2], vendor="test_vendor", body={"key": "value"})
    assert vcon.find_analysis_by_type("test_type") == {
        "type": "test_type",
        "dialog": [1, 2],
        "vendor": "test_vendor",
        "body": json.dumps({"key": "value"}),
        "encoding": "json",
    }
    assert vcon.find_analysis_by_type("nonexistent_type") is None


def test_find_party_index():
    vcon = Vcon.build_new()
    vcon.add_party({"id": "party1"})
    assert vcon.find_party_index("id", "party1") == 0
    assert vcon.find_party_index("id", "nonexistent_party") is None


def test_find_dialog():
    vcon = Vcon.build_new()
    vcon.add_dialog({"id": "dialog1"})
    assert vcon.find_dialog("id", "dialog1") == {"id": "dialog1"}
    assert vcon.find_dialog("id", "nonexistent_dialog") is None


def test_properties():
    json_string = '{"uuid": "12345", "vcon": "0.0.1", "created_at": "2023-05-02T12:00:00+00:00", "redacted": {"key": "value"}, "group": [1, 2], "parties": [{"id": "party1"}], "dialog": [{"id": "dialog1"}], "attachments": [{"type": "test_type", "encoding":"none", "body": {"key": "value"}}], "analysis": [{"type": "test_type", "dialog": [1, 2], "vendor": "test_vendor", "body": {"key": "value"}}]}'
    vcon = Vcon.build_from_json(json_string)
    assert vcon.uuid == "12345"
    assert vcon.vcon == "0.0.1"
    assert vcon.created_at == "2023-05-02T12:00:00+00:00"
    assert vcon.redacted == {"key": "value"}
    assert vcon.group == [1, 2]
    assert vcon.parties == [{"id": "party1"}]
    assert vcon.dialog == [{"id": "dialog1"}]
    assert vcon.attachments == [{"type": "test_type", "encoding":"none", "body": {"key": "value"}}]
    assert vcon.analysis == [{"type": "test_type", "dialog": [1, 2], "vendor": "test_vendor", "body": {"key": "value"}}]


def test_to_dict():
    vcon = Vcon.build_new()
    vcon_dict = vcon.to_dict()
    assert isinstance(vcon_dict, dict)
    assert vcon_dict == json.loads(vcon.to_json())


def test_dumps():
    vcon = Vcon.build_new()
    json_string = vcon.dumps()
    assert isinstance(json_string, str)
    assert json_string == vcon.to_json()


def test_error_handling():
    with pytest.raises(json.JSONDecodeError):
        Vcon.build_from_json("invalid_json")


# ---------------------------------------------------------------------------
# Body decoding regression coverage. The Redis store path
# (VconRedis._enforce_spec_on_write) stringifies dict/list bodies to JSON and
# rewrites encoding to "json" per draft-ietf-vcon-vcon-core-02. Read-side
# callers must round-trip through Vcon.decoded_body so they don't see a string
# where they used to see a dict/list.
# ---------------------------------------------------------------------------


def test_decoded_body_parses_json_encoded_string():
    entry = {"body": json.dumps({"k": "v"}), "encoding": "json"}
    assert Vcon.decoded_body(entry) == {"k": "v"}


def test_decoded_body_returns_freeform_string_for_encoding_none():
    # encoding=none means body is a freeform string, no parsing.
    entry = {"body": "NEEDS REVIEW: trailing context", "encoding": "none"}
    assert Vcon.decoded_body(entry) == "NEEDS REVIEW: trailing context"


def test_decoded_body_passes_through_legacy_dict_body():
    # Legacy writers placed dict/list directly under body with encoding=none.
    # The helper returns it as-is so callers don't have to special-case.
    entry = {"body": {"k": "v"}, "encoding": "none"}
    assert Vcon.decoded_body(entry) == {"k": "v"}


def test_decoded_body_handles_none_entry():
    assert Vcon.decoded_body(None) is None
    assert Vcon.decoded_body({}) is None


def test_with_decoded_body_returns_shallow_copy_with_parsed_body():
    entry = {
        "type": "transcript",
        "dialog": 0,
        "body": json.dumps({"transcript": "hello"}),
        "encoding": "json",
    }
    decoded = Vcon.with_decoded_body(entry)

    assert decoded == {
        "type": "transcript",
        "dialog": 0,
        "body": {"transcript": "hello"},
        "encoding": "json",
    }
    # Source entry untouched — important for callers that don't want to
    # mutate the underlying vCon.
    assert entry["body"] == json.dumps({"transcript": "hello"})


def test_with_decoded_body_returns_none_for_empty_input():
    assert Vcon.with_decoded_body(None) is None
    assert Vcon.with_decoded_body({}) is None


def test_add_tag_writes_spec_correct_shape():
    # Per draft-ietf-vcon-vcon-core-02 §2.3.2 body is always a String. The
    # tags purpose carries a JSON-encoded list of "name:value" strings.
    vcon = Vcon.build_new()
    vcon.add_tag("first", "1")
    vcon.add_tag("second", "2")

    tags_attachment = vcon.find_attachment_by_purpose("tags")
    assert tags_attachment["encoding"] == "json"
    assert isinstance(tags_attachment["body"], str)
    assert json.loads(tags_attachment["body"]) == ["first:1", "second:2"]
    assert vcon.get_tag("first") == "1"
    assert vcon.get_tag("second") == "2"


def test_add_tag_appends_to_legacy_unstringified_body():
    # A tags attachment in the legacy shape (encoding=none, body is a Python
    # list) must still be appendable — add_tag decodes, appends, and rewrites
    # in the spec-correct shape.
    vcon = Vcon.build_new()
    vcon.vcon_dict["attachments"].append(
        {"type": "tags", "body": ["legacy:1"], "encoding": "none"}
    )

    vcon.add_tag("new", "2")

    tags_attachment = vcon.find_attachment_by_purpose("tags")
    assert tags_attachment["encoding"] == "json"
    assert json.loads(tags_attachment["body"]) == ["legacy:1", "new:2"]


def test_add_tag_appends_to_already_stringified_body():
    # Reproduces the reported crash path: a tags attachment carrying the
    # spec-correct shape (encoding=json + stringified list) must be
    # appendable without the previous AttributeError.
    vcon = Vcon.build_new()
    vcon.vcon_dict["attachments"].append(
        {"type": "tags", "body": json.dumps(["first:1"]), "encoding": "json"}
    )

    vcon.add_tag("second", "2")

    assert vcon.get_tag("first") == "1"
    assert vcon.get_tag("second") == "2"


def test_get_tag_reads_through_json_encoded_body():
    vcon = Vcon.build_new()
    vcon.vcon_dict["attachments"].append(
        {"type": "tags", "body": json.dumps(["alpha:a", "beta:b"]), "encoding": "json"}
    )
    assert vcon.get_tag("alpha") == "a"
    assert vcon.get_tag("beta") == "b"
    assert vcon.get_tag("missing") is None


def test_get_tag_preserves_colons_in_value():
    # split(":", 1) — values containing ':' must not be truncated.
    vcon = Vcon.build_new()
    vcon.add_tag("url", "https://example.com/path")
    assert vcon.get_tag("url") == "https://example.com/path"
