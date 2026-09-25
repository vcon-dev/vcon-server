"""Decoding for inline dialog bodies.

draft-ietf-vcon-vcon-core-04 allows exactly three values for a dialog's
``encoding``: ``"base64url"``, ``"json"`` or ``"none"``. Telephony adapters
are moving to ``base64url`` *without* padding for inline audio bodies.

Standard ``base64.b64decode`` chokes on that: with ``validate=True`` it
raises on the missing padding, and in its default (non-validating) mode it
silently drops the ``-``/``_`` characters that are only valid in the
URL-safe alphabet and hands back corrupted audio instead of raising.

:func:`decode_inline_dialog_body` is the one place that should turn a
dialog's inline ``body`` into raw bytes. It dispatches on ``encoding``
instead of guessing, so a body encoded in a way we do not understand raises
rather than silently returning garbage.
"""

import base64
import binascii
from typing import Any, Dict


def _restore_base64url_padding(body: str) -> str:
    """Pad a base64url string out to a multiple of 4 characters.

    Adapters that emit base64url without padding are a valid rendering of
    the same bytes -- padding is only there to make the length a multiple
    of 4, and ``-``/``_`` already disambiguate the alphabet, so restoring
    it here is lossless.
    """
    return body + "=" * (-len(body) % 4)


def decode_inline_dialog_body(dialog: Dict[str, Any]) -> bytes:
    """Decode a dialog's inline ``body`` per its ``encoding`` field.

    Args:
        dialog: A vCon dialog object carrying an inline ``body`` (as opposed
            to a ``url``-referenced one).

    Returns:
        The decoded raw bytes.

    Raises:
        ValueError: ``encoding`` is missing/legacy and the body is not valid
            base64; ``encoding`` is ``"none"`` (the body is already a plain
            string, not encoded audio bytes); or ``encoding`` is some other,
            unrecognized value.
        KeyError: ``dialog`` has no ``body``.
    """
    body = dialog["body"]
    encoding = dialog.get("encoding")

    if encoding == "base64url":
        if not isinstance(body, str):
            raise ValueError(f"Cannot decode base64url dialog body of type {type(body).__name__}; expected str")
        try:
            padded = _restore_base64url_padding(body)
            # base64.urlsafe_b64decode() just translates "-"/"_" to "+"/"/"
            # and calls b64decode() *without* validate=True, so it silently
            # drops any other out-of-alphabet character instead of raising.
            # Translate ourselves and validate explicitly to fail loudly on
            # garbage input rather than return corrupted audio.
            standard = padded.translate({ord("-"): "+", ord("_"): "/"})
            return base64.b64decode(standard, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"Invalid base64url dialog body: {e}") from e

    if encoding == "base64" or encoding is None:
        # Legacy: vCons stored before the encoding field was spec-mandated,
        # or producers that never adopted base64url, use plain base64.
        if not isinstance(body, str):
            raise ValueError(f"Cannot decode base64 dialog body of type {type(body).__name__}; expected str")
        try:
            return base64.b64decode(body, validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError(f"Invalid base64 dialog body: {e}") from e

    if encoding == "none":
        raise ValueError("Dialog body encoding is 'none' (a plain string), not audio bytes")

    raise ValueError(f"Unrecognized dialog body encoding: {encoding!r}")
