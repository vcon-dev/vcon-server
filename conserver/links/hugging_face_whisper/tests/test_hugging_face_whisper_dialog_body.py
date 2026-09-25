"""get_file_content() decode coverage for CON-1112.

The rest of this link's test suite (test_hugging_face_whisper.py,
test_hugging_face_whisper_integration.py) is commented out pending an HF API
key, but get_file_content() itself is pure and needs no network or model
call, so it is covered here unconditionally.
"""

import base64

import pytest

from links.hugging_face_whisper import get_file_content


def test_get_file_content_from_legacy_base64_body():
    dialog = {"body": base64.b64encode(b"test audio content").decode("utf-8")}
    assert get_file_content(dialog) == b"test audio content"


def test_get_file_content_from_base64url_body_without_padding():
    """base64url dialogs (no padding, per draft-ietf-vcon-vcon-core-04) decode
    to the original bytes, not the corrupted/raised result plain b64decode gives."""
    raw = b"test audio content, base64url, no padding"
    dialog = {
        "encoding": "base64url",
        "body": base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("="),
    }
    assert get_file_content(dialog) == raw


def test_get_file_content_from_base64url_body_with_padding():
    raw = b"test audio content, base64url, padded"
    dialog = {
        "encoding": "base64url",
        "body": base64.urlsafe_b64encode(raw).decode("utf-8"),
    }
    assert get_file_content(dialog) == raw


def test_get_file_content_none_encoding_raises():
    dialog = {"encoding": "none", "body": "just text, not audio"}
    with pytest.raises(ValueError):
        get_file_content(dialog)
