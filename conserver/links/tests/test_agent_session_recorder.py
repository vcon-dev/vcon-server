"""Unit tests for lib.agent_session_recorder.

Exercises the recorder against a real vcon-lib Vcon (no mock), since the whole
point is to validate the wire shape produced by vcon-lib's primitives matches
draft-howe-vcon-agent-session.
"""

import json
import logging

import pytest
from vcon import Vcon

from lib.agent_session_recorder import (
    EXTENSION_NAME,
    GLOBAL_ENV_VAR,
    VAC_SCHEMA_URL,
    record_agent_trace,
)


@pytest.fixture(autouse=True)
def _enable_recording(monkeypatch):
    """Recording is off by default in production; turn it on for these tests."""
    monkeypatch.setenv(GLOBAL_ENV_VAR, "true")


def _make_vcon_with_dialog() -> Vcon:
    vcon = Vcon.build_new()
    vcon.vcon_dict["dialog"].append(
        {
            "type": "text",
            "start": "2026-05-18T10:00:00Z",
            "parties": [0],
            "body": "hello",
            "encoding": "none",
        }
    )
    return vcon


def test_adds_agent_trace_analysis():
    vcon = _make_vcon_with_dialog()

    record_agent_trace(
        vcon,
        dialog_indices=0,
        model_id="gpt-4-turbo",
        provider="openai",
        system_prompt="You are helpful.",
        user_prompt="Summarize this call.",
        assistant_response="The customer requested a refund.",
        link_name="analyze",
    )

    assert len(vcon.analysis) == 1
    entry = vcon.analysis[0]
    assert entry["type"] == "agent_trace"
    assert entry["dialog"] == 0
    assert entry["vendor"] == "openai"
    assert entry["product"] == "gpt-4-turbo"
    assert entry["schema"] == VAC_SCHEMA_URL
    assert entry["encoding"] == "json"

    body = json.loads(entry["body"])
    assert body["version"] == "1.0"
    assert body["session-trace"]["agent-meta"]["model-id"] == "gpt-4-turbo"
    assert body["session-trace"]["agent-meta"]["provider"] == "openai"

    entries = body["session-trace"]["entries"]
    assert len(entries) == 2
    assert entries[0]["type"] == "user"
    assert "Summarize this call." in entries[0]["content"]
    assert "You are helpful." in entries[0]["content"]
    assert entries[1]["type"] == "assistant"
    assert entries[1]["content"] == "The customer requested a refund."
    assert entries[1]["parent-id"] == "e0"


def test_user_entry_omits_system_block_when_no_system_prompt():
    vcon = _make_vcon_with_dialog()

    record_agent_trace(
        vcon,
        dialog_indices=0,
        model_id="gpt-4.1",
        provider="openai",
        system_prompt=None,
        user_prompt="just the user",
        assistant_response="ok",
        link_name="detect_engagement",
    )

    body = json.loads(vcon.analysis[0]["body"])
    user_content = body["session-trace"]["entries"][0]["content"]
    assert user_content == "just the user"
    assert "[system]" not in user_content


def test_dedupes_agent_party_for_same_model_and_provider():
    vcon = _make_vcon_with_dialog()

    for _ in range(2):
        record_agent_trace(
            vcon,
            dialog_indices=0,
            model_id="gpt-4-turbo",
            provider="openai",
            system_prompt=None,
            user_prompt="hi",
            assistant_response="hello",
            link_name="analyze",
        )

    agent_parties = [p for p in vcon.parties if p.get("role") == "agent"]
    assert len(agent_parties) == 1
    assert agent_parties[0]["meta"]["agent_session"]["model_id"] == "gpt-4-turbo"
    assert agent_parties[0]["meta"]["agent_session"]["provider"] == "openai"
    assert agent_parties[0]["meta"]["agent_session"]["recording_agent"] == "conserver/analyze"
    assert len(vcon.analysis) == 2


def test_different_model_creates_second_party():
    vcon = _make_vcon_with_dialog()

    record_agent_trace(
        vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
        system_prompt=None, user_prompt="hi", assistant_response="hello",
        link_name="analyze",
    )
    record_agent_trace(
        vcon, dialog_indices=0, model_id="claude-opus-4-6", provider="anthropic",
        system_prompt=None, user_prompt="hi", assistant_response="hello",
        link_name="analyze",
    )

    agent_parties = [p for p in vcon.parties if p.get("role") == "agent"]
    assert len(agent_parties) == 2


def test_extensions_list_includes_agent_session():
    vcon = _make_vcon_with_dialog()

    record_agent_trace(
        vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
        system_prompt=None, user_prompt="hi", assistant_response="hello",
        link_name="analyze",
    )

    assert EXTENSION_NAME in vcon.vcon_dict.get("extensions", [])


def test_opt_out_disables_recording():
    vcon = _make_vcon_with_dialog()

    record_agent_trace(
        vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
        system_prompt=None, user_prompt="hi", assistant_response="hello",
        link_name="analyze",
        opts={"record_agent_session": False},
    )

    assert vcon.analysis == []
    assert [p for p in vcon.parties if p.get("role") == "agent"] == []
    assert EXTENSION_NAME not in vcon.vcon_dict.get("extensions", [])


def test_global_env_disabled_explicitly(monkeypatch):
    vcon = _make_vcon_with_dialog()
    monkeypatch.setenv(GLOBAL_ENV_VAR, "false")

    record_agent_trace(
        vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
        system_prompt=None, user_prompt="hi", assistant_response="hello",
        link_name="analyze",
        opts={"record_agent_session": True},
    )

    assert vcon.analysis == []
    assert [p for p in vcon.parties if p.get("role") == "agent"] == []


def test_global_env_off_by_default_when_unset(monkeypatch):
    vcon = _make_vcon_with_dialog()
    monkeypatch.delenv(GLOBAL_ENV_VAR, raising=False)

    record_agent_trace(
        vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
        system_prompt=None, user_prompt="hi", assistant_response="hello",
        link_name="analyze",
        opts={"record_agent_session": True},
    )

    assert vcon.analysis == []
    assert [p for p in vcon.parties if p.get("role") == "agent"] == []


def test_missing_lawful_basis_logs_warning(caplog):
    vcon = _make_vcon_with_dialog()

    with caplog.at_level(logging.WARNING):
        record_agent_trace(
            vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
            system_prompt=None, user_prompt="hi", assistant_response="hello",
            link_name="analyze",
        )

    assert any("no lawful_basis attachment" in r.message for r in caplog.records)


def test_present_lawful_basis_suppresses_warning(caplog):
    vcon = _make_vcon_with_dialog()
    # The legacy common.vcon.Vcon.add_attachment uses (type, body, encoding);
    # body must be a JSON string when encoding="json" because the lib re-parses it.
    vcon.add_attachment(
        type="lawful_basis",
        body=json.dumps({"lawful_basis": "contract", "purpose_grants": []}),
        encoding="json",
    )

    with caplog.at_level(logging.WARNING):
        record_agent_trace(
            vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
            system_prompt=None, user_prompt="hi", assistant_response="hello",
            link_name="analyze",
        )

    assert not any("no lawful_basis attachment" in r.message for r in caplog.records)


def test_assistant_response_dict_is_json_serialized():
    vcon = _make_vcon_with_dialog()

    record_agent_trace(
        vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
        system_prompt=None, user_prompt="hi",
        assistant_response={"labels": ["billing", "refund"]},
        link_name="analyze_and_label",
    )

    body = json.loads(vcon.analysis[0]["body"])
    assistant_content = body["session-trace"]["entries"][1]["content"]
    assert json.loads(assistant_content) == {"labels": ["billing", "refund"]}


def test_extra_entries_spliced_between_user_and_assistant():
    vcon = _make_vcon_with_dialog()

    record_agent_trace(
        vcon, dialog_indices=0, model_id="gpt-4-turbo", provider="openai",
        system_prompt=None, user_prompt="hi", assistant_response="bye",
        link_name="analyze",
        extra_entries=[
            {"id": "tc1", "type": "tool-call", "name": "lookup", "arguments": {}},
            {"id": "tr1", "type": "tool-result", "parent-id": "tc1", "status": "ok"},
        ],
    )

    body = json.loads(vcon.analysis[0]["body"])
    entries = body["session-trace"]["entries"]
    assert [e["type"] for e in entries] == ["user", "tool-call", "tool-result", "assistant"]
