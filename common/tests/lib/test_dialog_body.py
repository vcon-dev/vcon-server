import base64

import pytest

from lib.dialog_body import decode_inline_dialog_body


def test_base64url_without_padding_round_trips():
    raw = b"hello world, this is audio-ish binary data"
    body = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    assert decode_inline_dialog_body({"encoding": "base64url", "body": body}) == raw


def test_base64url_with_padding_round_trips():
    raw = b"hello world, this is audio-ish binary dat"  # len % 3 != 0 -> padded
    body = base64.urlsafe_b64encode(raw).decode("ascii")
    assert body.endswith("=")
    assert decode_inline_dialog_body({"encoding": "base64url", "body": body}) == raw


def test_legacy_base64_round_trips():
    raw = b"legacy audio bytes"
    body = base64.b64encode(raw).decode("ascii")
    assert decode_inline_dialog_body({"encoding": "base64", "body": body}) == raw


def test_missing_encoding_treated_as_legacy_base64():
    raw = b"vcon stored before encoding was mandatory"
    body = base64.b64encode(raw).decode("ascii")
    assert decode_inline_dialog_body({"body": body}) == raw


def test_bytes_that_encode_to_dash_and_underscore_in_base64url_round_trip_exactly():
    # 0xFB -> "-" and 0xFF -> "_" only in the URL-safe alphabet ("+"/"/" in
    # standard base64). Plain base64.b64decode in its default, non-validating
    # mode silently drops "-"/"_" instead of raising, which is exactly the
    # silent-corruption failure mode this helper exists to prevent.
    raw = bytes([0xFB, 0xFF, 0x00, 0x10, 0x83, 0xFB, 0xFF])
    body = base64.urlsafe_b64encode(raw).decode("ascii")
    assert "-" in body or "_" in body
    unpadded = body.rstrip("=")

    decoded = decode_inline_dialog_body({"encoding": "base64url", "body": unpadded})
    assert decoded == raw

    # Prove the corruption this guards against: plain b64decode on the
    # same (padded) base64url text does NOT raise and does NOT return the
    # original bytes.
    corrupted = base64.b64decode(body)
    assert corrupted != raw


def test_none_encoding_raises_instead_of_returning_string_as_audio():
    with pytest.raises(ValueError):
        decode_inline_dialog_body({"encoding": "none", "body": "just text"})


def test_unrecognized_encoding_raises():
    with pytest.raises(ValueError):
        decode_inline_dialog_body({"encoding": "json", "body": "{}"})


def test_invalid_base64url_body_raises():
    with pytest.raises(ValueError):
        decode_inline_dialog_body({"encoding": "base64url", "body": "not valid base64!!"})


def test_invalid_legacy_base64_body_raises():
    with pytest.raises(ValueError):
        decode_inline_dialog_body({"body": "not valid base64!!"})
