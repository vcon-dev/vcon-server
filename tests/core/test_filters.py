"""Regression tests for ``common/lib/links/filters.is_included``.

Per draft-ietf-vcon-vcon-core-02 §2.3.2 ``body`` is always a String, so the
filter substring-matches directly without decoding — except for the ``tags``
purpose, whose body is a JSON-encoded list of ``"name:value"`` strings.

Attachments also accept either the spec-current ``purpose`` key or the
legacy ``type`` key, matching how :meth:`Vcon.find_attachment_by_purpose`
already tolerates both.
"""
import json

from lib.links.filters import is_included
from vcon import Vcon


def _vcon_with_analysis(body, encoding="none"):
    v = Vcon.build_new()
    v.vcon_dict["analysis"].append(
        {"type": "summary", "dialog": 0, "vendor": "x", "body": body, "encoding": encoding}
    )
    return v


def _vcon_with_tags_attachment(body, encoding="json"):
    v = Vcon.build_new()
    v.vcon_dict["attachments"].append(
        {"type": "tags", "body": body, "encoding": encoding}
    )
    return v


def test_is_included_matches_string_analysis_body():
    v = _vcon_with_analysis("NEEDS REVIEW: customer escalated")
    options = {"only_if": {"section": "analysis", "type": "summary", "includes": "NEEDS REVIEW"}}
    assert is_included(options, v) is True


def test_is_included_substring_matches_json_encoded_body_as_string():
    # encoding=json means body is already a JSON-encoded *string* per spec;
    # substring-matching against the raw string is the spec-compliant behavior.
    v = _vcon_with_analysis(json.dumps({"text": "NEEDS REVIEW now"}), encoding="json")
    options = {"only_if": {"section": "analysis", "type": "summary", "includes": "NEEDS REVIEW"}}
    assert is_included(options, v) is True


def test_is_included_no_match():
    v = _vcon_with_analysis("everything fine")
    options = {"only_if": {"section": "analysis", "type": "summary", "includes": "NEEDS REVIEW"}}
    assert is_included(options, v) is False


def test_is_included_tags_against_json_stringified_list():
    v = _vcon_with_tags_attachment(json.dumps(["important:important", "vip:vip"]))
    options = {"only_if": {"section": "attachments", "type": "tags", "includes": "important:important"}}
    assert is_included(options, v) is True


def test_is_included_attachment_matched_via_spec_current_purpose_key():
    # Spec-0.4.0 writer: attachment uses ``purpose`` instead of ``type``.
    v = Vcon.build_new()
    v.vcon_dict["attachments"].append(
        {"purpose": "tags", "body": json.dumps(["vip:vip"]), "encoding": "json"}
    )
    options = {"only_if": {"section": "attachments", "type": "tags", "includes": "vip:vip"}}
    assert is_included(options, v) is True


def test_is_included_attachment_matched_via_legacy_type_key():
    # Pre-0.4.0 writer: attachment uses ``type``. Must still resolve.
    v = _vcon_with_tags_attachment(json.dumps(["vip:vip"]))
    options = {"only_if": {"section": "attachments", "type": "tags", "includes": "vip:vip"}}
    assert is_included(options, v) is True


def test_is_included_accepts_spec_current_purpose_key_in_filter():
    # Config written against spec 0.4.0 — uses ``purpose`` instead of ``type``.
    v = _vcon_with_tags_attachment(json.dumps(["vip:vip"]))
    options = {"only_if": {"section": "attachments", "purpose": "tags", "includes": "vip:vip"}}
    assert is_included(options, v) is True


def test_is_included_returns_true_when_no_only_if():
    v = Vcon.build_new()
    assert is_included({}, v) is True
    assert is_included(None, v) is True
