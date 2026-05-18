"""Recorder for the `agent_session` vCon extension.

Implements draft-howe-vcon-agent-session by emitting a `type: agent_trace`
analysis entry (and dedicated agent party) on a vCon whenever a conserver link
invokes an LLM. The trace body conforms to the Verifiable Agent Conversations
(VAC) schema referenced by the draft.

Operates on the conserver's `common.vcon.Vcon` class (which shadows the
installed `vcon` library by virtue of being earlier on the pythonpath). The
custom class lacks vcon-lib's richer API, so we use its `add_analysis`,
`add_party`, and direct `vcon_dict` manipulation for fields it does not
expose.
"""

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any, Optional, Union

from lib.logging_utils import init_logger

logger = init_logger(__name__)

VAC_SCHEMA_URL = "https://datatracker.ietf.org/doc/draft-birkholz-verifiable-agent-conversations/"
EXTENSION_NAME = "agent_session"
GLOBAL_ENV_VAR = "CONSERVER_RECORD_AGENT_SESSION"

_TRUTHY = ("true", "1", "yes", "on")


def _recording_globally_enabled() -> bool:
    # Off by default: operators must explicitly opt in via the env var.
    return os.getenv(GLOBAL_ENV_VAR, "").lower() in _TRUTHY


def _now_rfc3339() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _find_agent_party_index(vcon, model_id: str, provider: str) -> Optional[int]:
    for i, party in enumerate(vcon.parties):
        if party.get("role") != "agent":
            continue
        meta = party.get("meta") or {}
        session = meta.get("agent_session") or {}
        if session.get("model_id") == model_id and session.get("provider") == provider:
            return i
    return None


def _has_lawful_basis(vcon) -> bool:
    for att in vcon.attachments:
        # Conserver's legacy attachment shape uses `type`; the lawful_basis
        # extension itself also writes `type: lawful_basis` per the draft.
        if att.get("type") == "lawful_basis" or att.get("purpose") == "lawful_basis":
            return True
        body = att.get("body")
        if isinstance(body, dict) and "lawful_basis" in body:
            return True
    return False


def _ensure_extension(vcon, name: str) -> None:
    extensions = vcon.vcon_dict.setdefault("extensions", [])
    if name not in extensions:
        extensions.append(name)


def _build_vac_entries(
    *,
    system_prompt: Optional[str],
    user_prompt: str,
    assistant_response: str,
    timestamp: str,
    extra_entries: Optional[list[dict]],
) -> list[dict]:
    if system_prompt:
        user_content = f"[system]\n{system_prompt}\n\n[user]\n{user_prompt}"
    else:
        user_content = user_prompt

    user_entry = {
        "id": "e0",
        "type": "user",
        "timestamp": timestamp,
        "content": user_content,
    }
    assistant_entry = {
        "id": "e1",
        "type": "assistant",
        "parent-id": "e0",
        "timestamp": timestamp,
        "content": assistant_response,
    }

    entries = [user_entry]
    if extra_entries:
        entries.extend(extra_entries)
    entries.append(assistant_entry)
    return entries


def record_agent_trace(
    vcon,
    *,
    dialog_indices: Union[list[int], int],
    model_id: str,
    provider: str,
    system_prompt: Optional[str],
    user_prompt: str,
    assistant_response: Any,
    link_name: str,
    recording_agent: Optional[str] = None,
    opts: Optional[dict] = None,
    extra_entries: Optional[list[dict]] = None,
) -> None:
    """Append an `agent_trace` analysis entry (and supporting party) to a vCon.

    Args:
        vcon: Conserver Vcon instance to mutate.
        dialog_indices: Dialog index/indices the agent session pertains to.
        model_id: Vendor identifier for the model (e.g. "gpt-4-turbo").
        provider: Organization providing the model (e.g. "openai", "anthropic").
        system_prompt: Optional system prompt sent to the model.
        user_prompt: User-facing prompt sent to the model.
        assistant_response: Model's response. Coerced to string if non-string.
        link_name: Conserver link name (used for session id and recording-agent default).
        recording_agent: Override for the recording-agent identifier.
        opts: Link options dict. Consulted for `record_agent_session` (default True).
        extra_entries: Optional VAC entries spliced between the user and assistant
            entries (e.g. tool-call / tool-result / reasoning entries for future
            tool-using links).
    """
    if not _recording_globally_enabled():
        logger.debug("agent_session recording disabled by %s env var", GLOBAL_ENV_VAR)
        return

    if opts is not None and not opts.get("record_agent_session", True):
        logger.debug("agent_session recording disabled by per-link opt for %s", link_name)
        return

    recording_agent = recording_agent or f"conserver/{link_name}"

    party_idx = _find_agent_party_index(vcon, model_id, provider)
    if party_idx is None:
        party_dict = {
            "name": f"{provider} {model_id}",
            "role": "agent",
            "validation": "system",
            "meta": {
                "agent_session": {
                    "model_id": model_id,
                    "provider": provider,
                    "recording_agent": recording_agent,
                }
            },
        }
        vcon.add_party(party_dict)
        party_idx = len(vcon.parties) - 1

    timestamp = _now_rfc3339()
    response_text = assistant_response if isinstance(assistant_response, str) else json.dumps(assistant_response)

    entries = _build_vac_entries(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        assistant_response=response_text,
        timestamp=timestamp,
        extra_entries=extra_entries,
    )

    vac_record = {
        "version": "1.0",
        "id": f"{vcon.uuid}-{link_name}-{int(time.time() * 1000)}",
        "session-trace": {
            "agent-meta": {
                "model-id": model_id,
                "provider": provider,
                "party": party_idx,
            },
            "recording-agent": recording_agent,
            "entries": entries,
        },
    }

    # The conserver Vcon's add_analysis lacks product/schema as named params,
    # so route them through extra (which becomes top-level via `**extra`).
    vcon.add_analysis(
        type="agent_trace",
        dialog=dialog_indices,
        vendor=provider,
        body=json.dumps(vac_record),
        encoding="json",
        extra={
            "product": model_id,
            "schema": VAC_SCHEMA_URL,
        },
    )

    _ensure_extension(vcon, EXTENSION_NAME)

    if not _has_lawful_basis(vcon):
        logger.warning(
            "vCon %s has no lawful_basis attachment but agent_session is being recorded by link '%s'. "
            "Operators are responsible for setting consent upstream.",
            vcon.uuid,
            link_name,
        )
