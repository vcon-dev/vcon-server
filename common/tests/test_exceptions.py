"""Tests for the domain exception hierarchy + error envelope (Refactor #8)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from exceptions import (
    AuthError,
    ConfigError,
    LinkError,
    StorageError,
    VconError,
    VconNotFoundError,
    VconValidationError,
)
from middleware.errors import vcon_error_handler


@pytest.mark.parametrize(
    "exc_cls,expected_code,expected_status",
    [
        (ConfigError, "config_error", 500),
        (VconNotFoundError, "vcon_not_found", 404),
        (VconValidationError, "vcon_invalid", 422),
        (StorageError, "storage_error", 500),
        (LinkError, "link_error", 500),
        (AuthError, "auth_error", 403),
    ],
)
def test_subclasses_have_code_and_status(exc_cls, expected_code, expected_status):
    assert exc_cls.code == expected_code
    assert exc_cls.http_status == expected_status
    assert issubclass(exc_cls, VconError)


def _app_with_handler(exc_to_raise):
    app = FastAPI()
    app.add_exception_handler(VconError, vcon_error_handler)

    @app.get("/boom")
    def boom():
        raise exc_to_raise

    return app


def test_envelope_shape_for_vcon_not_found():
    app = _app_with_handler(VconNotFoundError("vcon abc-123 not found"))
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/boom")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "VconNotFoundError"
    assert body["code"] == "vcon_not_found"
    assert body["detail"] == "vcon abc-123 not found"
    assert "trace_id" in body  # may be None when no OTel span is active


def test_envelope_shape_for_storage_error_preserves_status():
    app = _app_with_handler(StorageError("s3: access denied"))
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "storage_error"


def test_regular_httpexception_unchanged():
    """HTTPException is NOT a VconError — the handler must not touch it."""
    app = FastAPI()
    app.add_exception_handler(VconError, vcon_error_handler)

    @app.get("/http_boom")
    def http_boom():
        raise HTTPException(status_code=403, detail="nope")

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/http_boom")
    assert resp.status_code == 403
    assert resp.json() == {"detail": "nope"}  # unchanged FastAPI default shape
