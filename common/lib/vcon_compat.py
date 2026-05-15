"""Legacy-field tolerance for vCons read from storage.

Older releases of vcon-mcp / vcon-lib / hand-rolled adapters wrote vCons
with field names that pre-date ``draft-ietf-vcon-vcon-core-02``. We want
links to keep processing those records, but we want every *write* to
land in spec-correct form.

This module exposes one function — :func:`normalize_legacy_fields` — that
maps legacy names to spec names on a vCon dict in place. It is intended
to be called at the read boundary (``VconRedis.get_vcon`` /
``get_vcon_dict``) so the rest of the codebase only ever sees
spec-compliant data.

Mappings applied:

- top-level ``appended`` → ``amended``
- attachment / analysis ``schema_version`` → ``schema``
- attachment ``type`` → ``purpose`` (per draft-02 §5.5, but **only** for
  attachments whose ``purpose`` slot isn't already populated; the
  ``lawful_basis`` extension legitimately uses ``type``, so we don't
  touch entries that already have a ``type`` *and* a ``purpose``)
- attachment / dialog ``mimetype`` → ``mediatype``
- extension/critical: ``must_support`` (top-level or in entries) →
  ``critical``

The function is conservative: if both the legacy and the spec field are
present, the spec field wins and the legacy field is dropped.
"""

from typing import Any, Dict, List


_TOP_LEVEL_RENAMES = {
    "appended": "amended",
    "must_support": "critical",
}


def _rename(d: Dict[str, Any], old: str, new: str) -> None:
    """Move ``d[old]`` to ``d[new]`` unless ``d[new]`` is already set."""
    if old not in d:
        return
    if new in d:
        # Spec field already there — drop the legacy one silently.
        d.pop(old, None)
        return
    d[new] = d.pop(old)


def _normalize_entry(entry: Dict[str, Any]) -> None:
    if not isinstance(entry, dict):
        return
    _rename(entry, "schema_version", "schema")
    _rename(entry, "mimetype", "mediatype")
    _rename(entry, "must_support", "critical")


def _normalize_attachment(att: Dict[str, Any]) -> None:
    """Normalize a single attachment dict.

    Per the speckit, attachments use ``purpose``. The legacy field was
    ``type``. Some extensions (notably ``lawful_basis``) re-use ``type``
    *as* their purpose value, so we only migrate when ``purpose`` is
    absent.
    """
    if not isinstance(att, dict):
        return
    _normalize_entry(att)
    if "purpose" not in att and "type" in att:
        att["purpose"] = att.pop("type")


def normalize_legacy_fields(vcon_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate ``vcon_dict`` in place, mapping legacy names to spec names.

    Returns the same dict for convenience.
    """
    if not isinstance(vcon_dict, dict):
        return vcon_dict

    for old, new in _TOP_LEVEL_RENAMES.items():
        _rename(vcon_dict, old, new)

    for entry in vcon_dict.get("dialog", []) or []:
        _normalize_entry(entry)

    for entry in vcon_dict.get("analysis", []) or []:
        _normalize_entry(entry)

    attachments: List[Dict[str, Any]] = vcon_dict.get("attachments", []) or []
    for att in attachments:
        _normalize_attachment(att)

    return vcon_dict
