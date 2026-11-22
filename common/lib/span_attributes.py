"""Span attributes that tie a chain run to a tenant and a call.

These go on spans only. A per-call value on a metric creates one series per call.
"""

from typing import Optional

from vcon import Vcon

TELNYX_SESSION_TAG = "telnyx_call_session_id"
_MAX_LEN = 128


def _clean(value) -> Optional[str]:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    return text[:_MAX_LEN] if text else None


def vcon_correlation_attributes(vcon_dict: Optional[dict]) -> dict:
    """Return ``tenant.id`` and ``call.session_id`` for a vCon dict, leaving out what is absent.

    ``tenant.id`` is the ``id`` in the body of the ``tenant`` attachment. ``call.session_id`` is
    the value of the ``telnyx_call_session_id`` tag. Nothing else from the vCon is read, so no
    dialog, transcript or other body content can reach a span through here.
    """
    if not vcon_dict:
        return {}
    vcon = Vcon(vcon_dict)
    attrs = {}

    try:
        tenant_body = Vcon.decoded_body(vcon.find_attachment_by_purpose("tenant"))
    except Exception:
        tenant_body = None
    if isinstance(tenant_body, dict):
        tenant_id = _clean(tenant_body.get("id"))
        if tenant_id:
            attrs["tenant.id"] = tenant_id

    try:
        session_id = _clean(vcon.get_tag(TELNYX_SESSION_TAG))
    except Exception:
        session_id = None
    if session_id:
        attrs["call.session_id"] = session_id

    return attrs
