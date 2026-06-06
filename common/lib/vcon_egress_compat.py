"""Spec→legacy vCon conversion for egress compatibility (CON-581).

This is the inverse of :func:`lib.vcon_compat.normalize_legacy_fields`.

The conserver normalizes every vCon *up* to the current spec (``vcon: "0.4.0"``)
on read and write. Downstream consumers built against an older schema (e.g.
``0.0.1``) break on the canonical shape — notably the ``type`` → ``purpose``
attachment rename and the write-path serialization of dict/list analysis and
attachment bodies into JSON strings (``encoding: "json"``). This module converts
an *outgoing* payload back to a legacy version — reversing the field renames and
re-inflating those JSON-string bodies to native objects with ``encoding: "none"``
— so those consumers keep working while a migration is planned.

It never mutates the canonical in-pipeline copy: callers pass ``vcon.to_dict()``
and receive a new, deep-copied, downgraded dict. Enable it per egress point via
the ``egress_format_version`` option on the webhook link and the
postgres / s3 / elasticsearch storage modules. When the option is unset, callers
skip this module entirely and behaviour is unchanged.

The rename tables below mirror ``lib.vcon_compat`` (in the opposite direction).
``test_vcon_egress_compat`` round-trips ``normalize_legacy_fields(to_legacy(x))``
to guard against the two drifting apart.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict

# Spec name → legacy name. Inverse of lib.vcon_compat._TOP_LEVEL_RENAMES.
_TOP_LEVEL_SPEC_TO_LEGACY = {
    "amended": "appended",
    "critical": "must_support",
}

# Spec name → legacy name for dialog / analysis / attachment entries.
# Inverse of the renames applied by lib.vcon_compat._normalize_entry.
_ENTRY_SPEC_TO_LEGACY = {
    "schema": "schema_version",
    "mediatype": "mimetype",
    "critical": "must_support",
}

# Legacy versions this module knows how to emit.
SUPPORTED_VERSIONS = {"0.0.1"}


def _rename(d: Dict[str, Any], old: str, new: str) -> None:
    """Move ``d[old]`` to ``d[new]`` unless ``d[new]`` is already set.

    Mirrors ``vcon_compat._rename``: if both are present the destination
    (legacy) field wins and the source is dropped.
    """
    if old not in d:
        return
    if new in d:
        d.pop(old, None)
        return
    d[new] = d.pop(old)


def _entry_to_legacy(entry: Dict[str, Any]) -> None:
    if not isinstance(entry, dict):
        return
    for spec, legacy in _ENTRY_SPEC_TO_LEGACY.items():
        _rename(entry, spec, legacy)


def _body_to_legacy(entry: Dict[str, Any]) -> None:
    """Inverse of ``VconRedis._stringify_json_body``.

    The spec write-path serializes dict/list ``body`` values to a JSON string
    and sets ``encoding: "json"``. The legacy 0.0.1 shape carries the native
    object/array with ``encoding: "none"``, so parse it back. Applied to
    analysis and attachment entries only — dialog bodies are not stringified on
    write. Left untouched if the body isn't valid JSON.
    """
    if not isinstance(entry, dict):
        return
    if entry.get("encoding") == "json" and isinstance(entry.get("body"), str):
        try:
            entry["body"] = json.loads(entry["body"])
        except (ValueError, TypeError):
            return
        entry["encoding"] = "none"


def _attachment_to_legacy(att: Dict[str, Any]) -> None:
    if not isinstance(att, dict):
        return
    _entry_to_legacy(att)
    # Spec uses ``purpose``; the legacy field was ``type``. Mirror the forward
    # normalizer's caveat: only migrate when ``type`` is absent, since the
    # ``lawful_basis`` extension legitimately uses ``type`` as its value.
    if "type" not in att and "purpose" in att:
        att["type"] = att.pop("purpose")


def to_legacy(vcon_dict: Dict[str, Any], target_version: str) -> Dict[str, Any]:
    """Return a deep-copied vCon dict converted to ``target_version``.

    :param vcon_dict: a spec-current (0.4.0) vCon dict, e.g. ``vcon.to_dict()``.
    :param target_version: legacy version to emit; must be in
        :data:`SUPPORTED_VERSIONS`.
    :raises ValueError: if ``target_version`` is not supported.

    The input is never mutated.
    """
    if target_version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported egress_format_version {target_version!r}; "
            f"supported: {sorted(SUPPORTED_VERSIONS)}"
        )
    if not isinstance(vcon_dict, dict):
        return vcon_dict

    out = copy.deepcopy(vcon_dict)

    for spec, legacy in _TOP_LEVEL_SPEC_TO_LEGACY.items():
        _rename(out, spec, legacy)

    for entry in out.get("dialog", []) or []:
        _entry_to_legacy(entry)
    for entry in out.get("analysis", []) or []:
        _entry_to_legacy(entry)
        _body_to_legacy(entry)
    for att in out.get("attachments", []) or []:
        _attachment_to_legacy(att)
        _body_to_legacy(att)

    # Legacy 0.0.1 always carries these top-level keys (matching the shape in
    # Strolid's store today); the 0.4.0 library drops empty group/redacted.
    out.setdefault("group", [])
    out.setdefault("redacted", {})
    out.setdefault("appended", None)

    out["vcon"] = target_version
    return out
