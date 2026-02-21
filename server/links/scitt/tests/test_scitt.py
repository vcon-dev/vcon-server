"""
Unit tests for the SCITT link — SCRAPI-based lifecycle registration.

Tests cover:
- register_signed_statement: SCRAPI POST /entries (sync 201, async 303, errors)
- __init__.run: full link flow with mocked Redis and SCRAPI
- Receipt storage as scitt_receipt analysis entries

NOTE on mock paths: The conserver's __init__.py uses a relative import
(``from links.scitt import register_signed_statement``), which registers
the module under ``links.scitt.register_signed_statement`` in sys.modules.
All @patch targets must use this path — NOT the ``server.links.scitt.…``
path that the test file's own imports resolve to — otherwise the mock is
applied to a duplicate module object and the production code never sees it.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from requests import Response

from server.links.scitt import register_signed_statement
from server.links.scitt import run, default_options

# Use a non-routable URL (RFC 6761) so if mocks fail, tests get a
# ConnectionError instead of hitting the live SCITTLEs container.
SCRAPI_URL = "http://scrapi.test.invalid:9999"

# The __init__.py does ``from links.scitt import register_signed_statement``,
# so the actual submodules are registered under these paths in sys.modules.
# Patching attributes on these module objects works for both ``links.scitt``
# and ``server.links.scitt`` callers because they share the same objects.
_RSM = "links.scitt.register_signed_statement"
_CHSS = "links.scitt.create_hashed_signed_statement"


# ----------------------------
# register_signed_statement tests
# ----------------------------

class TestRegisterStatement:
    """Tests for register_signed_statement.register_statement()"""

    def _make_response(self, status_code, content=b"", headers=None):
        resp = Response()
        resp.status_code = status_code
        resp._content = content
        if headers:
            resp.headers.update(headers)
        return resp

    @patch(f"{_RSM}.requests.post")
    def test_sync_201_returns_entry_id_and_receipt(self, mock_post):
        """201 Created: entry_id from Location header, receipt from body."""
        mock_post.return_value = self._make_response(
            201,
            content=b"\xd2\x84\x43",  # fake COSE bytes
            headers={"Location": "/entries/abc123def456"},
        )

        result = register_signed_statement.register_statement(
            SCRAPI_URL, b"\xd2\x84"
        )

        assert result["entry_id"] == "abc123def456"
        assert result["receipt"] == b"\xd2\x84\x43"
        mock_post.assert_called_once_with(
            f"{SCRAPI_URL}/entries",
            data=b"\xd2\x84",
            headers={"Content-Type": "application/cose"},
            timeout=register_signed_statement.REQUEST_TIMEOUT,
        )

    @patch(f"{_RSM}.time_sleep")
    @patch(f"{_RSM}.requests.get")
    @patch(f"{_RSM}.requests.post")
    def test_async_303_polls_and_fetches_receipt(self, mock_post, mock_get, mock_sleep):
        """303 See Other: poll for entry_id, then fetch receipt."""
        mock_post.return_value = self._make_response(
            303,
            headers={"Location": "/operations/op-789"},
        )

        # First GET: poll returns 200 with entry_id
        resp_poll = Mock()
        resp_poll.status_code = 200
        resp_poll.json.return_value = {"entryID": "entry-xyz"}

        # Second GET: receipt fetch
        resp_receipt = Mock()
        resp_receipt.status_code = 200
        resp_receipt.content = b"\xd2\x84\x44"
        resp_receipt.raise_for_status = Mock()

        mock_get.side_effect = [resp_poll, resp_receipt]

        result = register_signed_statement.register_statement(
            SCRAPI_URL, b"\xd2\x84"
        )

        assert result["entry_id"] == "entry-xyz"
        assert result["receipt"] == b"\xd2\x84\x44"
        # Verify sleep was NOT called (poll succeeded on first attempt)
        mock_sleep.assert_not_called()

    @patch(f"{_RSM}.requests.post")
    def test_error_status_raises(self, mock_post):
        """Non-201/303 responses raise HTTPError."""
        resp = self._make_response(400, content=b"Bad Request")
        resp.url = f"{SCRAPI_URL}/entries"
        mock_post.return_value = resp

        with pytest.raises(Exception):
            register_signed_statement.register_statement(
                SCRAPI_URL, b"\xd2\x84"
            )


class TestWaitForEntryId:
    """Tests for register_signed_statement.wait_for_entry_id()"""

    @patch(f"{_RSM}.time_sleep")
    @patch(f"{_RSM}.requests.get")
    def test_polls_until_200(self, mock_get, mock_sleep):
        """Returns entry_id when poll returns 200 with entryID."""
        resp_pending = Mock()
        resp_pending.status_code = 202

        resp_done = Mock()
        resp_done.status_code = 200
        resp_done.json.return_value = {"entryID": "final-entry-id"}

        mock_get.side_effect = [resp_pending, resp_pending, resp_done]

        result = register_signed_statement.wait_for_entry_id(
            SCRAPI_URL, "/operations/op-1"
        )

        assert result == "final-entry-id"
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2

    @patch(f"{_RSM}.time_sleep")
    @patch(f"{_RSM}.requests.get")
    def test_timeout_raises(self, mock_get, mock_sleep):
        """Raises TimeoutError if polling exhausts all attempts."""
        resp_pending = Mock()
        resp_pending.status_code = 202
        mock_get.return_value = resp_pending

        with pytest.raises(TimeoutError, match="not registered"):
            register_signed_statement.wait_for_entry_id(
                SCRAPI_URL, "/operations/op-1"
            )

    @patch(f"{_RSM}.time_sleep")
    @patch(f"{_RSM}.requests.get")
    def test_handles_absolute_url(self, mock_get, mock_sleep):
        """Supports absolute URLs in the Location header."""
        resp = Mock()
        resp.status_code = 200
        resp.json.return_value = {"entry_id": "abs-entry"}
        mock_get.return_value = resp

        result = register_signed_statement.wait_for_entry_id(
            SCRAPI_URL, f"{SCRAPI_URL}/operations/op-1"
        )

        assert result == "abs-entry"
        mock_get.assert_called_once_with(
            f"{SCRAPI_URL}/operations/op-1",
            timeout=register_signed_statement.REQUEST_TIMEOUT,
        )


class TestGetReceipt:
    """Tests for register_signed_statement.get_receipt()"""

    @patch(f"{_RSM}.requests.get")
    def test_returns_receipt_bytes(self, mock_get):
        resp = Mock()
        resp.status_code = 200
        resp.content = b"\xd2receipt"
        resp.raise_for_status = Mock()
        mock_get.return_value = resp

        result = register_signed_statement.get_receipt(SCRAPI_URL, "entry-1")

        assert result == b"\xd2receipt"
        mock_get.assert_called_once_with(
            f"{SCRAPI_URL}/entries/entry-1",
            headers={"Accept": "application/cose"},
            timeout=register_signed_statement.REQUEST_TIMEOUT,
        )


# ----------------------------
# SCITT link run() tests
# ----------------------------

# Patching run() dependencies requires two different prefixes due to a
# dual-module situation:  __init__.py is loaded as BOTH ``server.links.scitt``
# (via pytest's test imports) and ``links.scitt`` (via the conserver's internal
# relative import ``from links.scitt import …``).
#
# - Submodule *attributes* (e.g. register_signed_statement.register_statement)
#   can be patched via _RSM because the submodule object is shared — both
#   module entries hold a reference to the same object.
# - Names imported directly into __init__.py (e.g. VconRedis) must be patched
#   on ``server.links.scitt`` because that's the module whose __dict__ the
#   ``run()`` function resolves globals from.
_SCITT_INIT = "server.links.scitt"


class TestScittLinkRun:
    """Tests for the SCITT link run() function."""

    @pytest.fixture
    def mock_vcon(self):
        vcon = Mock()
        vcon.uuid = "test-uuid-1234"
        vcon.subject = "tel:+15551234567"
        vcon.hash = "a1b2c3d4e5f6abcdef1234567890abcdef1234567890abcdef1234567890abcd"
        vcon.add_analysis = Mock()
        return vcon

    @pytest.fixture
    def mock_redis(self, mock_vcon):
        with patch(f"{_SCITT_INIT}.VconRedis") as mock_cls:
            redis_inst = Mock()
            redis_inst.get_vcon.return_value = mock_vcon
            mock_cls.return_value = redis_inst
            yield redis_inst

    @patch(f"{_RSM}.register_statement")
    @patch(f"{_CHSS}.create_hashed_signed_statement")
    @patch(f"{_CHSS}.open_signing_key")
    def test_run_registers_and_stores_receipt(
        self, mock_open_key, mock_create_stmt, mock_register, mock_redis, mock_vcon
    ):
        """Full run: creates signed statement, registers, stores receipt."""
        mock_open_key.return_value = Mock()
        mock_create_stmt.return_value = b"\xd2signed"
        mock_register.return_value = {
            "entry_id": "entry-abc123",
            "receipt": b"\xd2receipt",
        }

        opts = {
            "scrapi_url": SCRAPI_URL,
            "signing_key_path": "/etc/scitt/signing-key.pem",
            "issuer": "conserver",
            "key_id": "conserver-key-1",
            "vcon_operation": "vcon_created",
            "store_receipt": True,
        }

        result = run("test-uuid-1234", "scitt_created", opts)

        assert result == "test-uuid-1234"

        # Verify signed statement was created with correct args
        mock_create_stmt.assert_called_once()
        call_kwargs = mock_create_stmt.call_args
        assert call_kwargs.kwargs["issuer"] == "conserver"
        assert call_kwargs.kwargs["subject"] == "tel:+15551234567"
        assert call_kwargs.kwargs["meta_map"] == {"vcon_operation": "vcon_created"}
        assert call_kwargs.kwargs["pre_image_content_type"] == "application/vcon+json"

        # Verify registration
        mock_register.assert_called_once_with(SCRAPI_URL, b"\xd2signed")

        # Verify receipt stored as analysis
        mock_vcon.add_analysis.assert_called_once_with(
            type="scitt_receipt",
            dialog=0,
            vendor="scittles",
            body={
                "entry_id": "entry-abc123",
                "vcon_operation": "vcon_created",
                "vcon_hash": mock_vcon.hash,
                "scrapi_url": SCRAPI_URL,
            },
        )

        # Verify vCon saved back to Redis
        mock_redis.store_vcon.assert_called_once_with(mock_vcon)

    @patch(f"{_RSM}.register_statement")
    @patch(f"{_CHSS}.create_hashed_signed_statement")
    @patch(f"{_CHSS}.open_signing_key")
    def test_run_skips_receipt_storage_when_disabled(
        self, mock_open_key, mock_create_stmt, mock_register, mock_redis, mock_vcon
    ):
        """When store_receipt is False, don't add analysis or save."""
        mock_open_key.return_value = Mock()
        mock_create_stmt.return_value = b"\xd2signed"
        mock_register.return_value = {"entry_id": "entry-1", "receipt": b""}

        opts = {**default_options, "store_receipt": False}
        result = run("test-uuid-1234", "scitt_created", opts)

        assert result == "test-uuid-1234"
        mock_vcon.add_analysis.assert_not_called()
        mock_redis.store_vcon.assert_not_called()

    @patch(f"{_RSM}.register_statement")
    @patch(f"{_CHSS}.create_hashed_signed_statement")
    @patch(f"{_CHSS}.open_signing_key")
    def test_run_with_vcon_enhanced_operation(
        self, mock_open_key, mock_create_stmt, mock_register, mock_redis, mock_vcon
    ):
        """vcon_enhanced operation uses the correct meta_map value."""
        mock_open_key.return_value = Mock()
        mock_create_stmt.return_value = b"\xd2signed"
        mock_register.return_value = {"entry_id": "entry-enh", "receipt": b""}

        opts = {**default_options, "vcon_operation": "vcon_enhanced"}
        run("test-uuid-1234", "scitt_enhanced", opts)

        call_kwargs = mock_create_stmt.call_args
        assert call_kwargs.kwargs["meta_map"] == {"vcon_operation": "vcon_enhanced"}

        mock_vcon.add_analysis.assert_called_once()
        analysis_body = mock_vcon.add_analysis.call_args.kwargs["body"]
        assert analysis_body["vcon_operation"] == "vcon_enhanced"

    def test_run_raises_on_missing_vcon(self, mock_redis):
        """Raises HTTPException when vCon not found in Redis."""
        mock_redis.get_vcon.return_value = None

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            run("nonexistent-uuid", "scitt_created", default_options)
        assert exc_info.value.status_code == 404

    @patch(f"{_RSM}.register_statement")
    @patch(f"{_CHSS}.create_hashed_signed_statement")
    @patch(f"{_CHSS}.open_signing_key")
    def test_run_uses_fallback_subject(
        self, mock_open_key, mock_create_stmt, mock_register, mock_redis, mock_vcon
    ):
        """When vcon.subject is None, uses vcon:// URI as subject."""
        mock_vcon.subject = None
        mock_open_key.return_value = Mock()
        mock_create_stmt.return_value = b"\xd2signed"
        mock_register.return_value = {"entry_id": "entry-1", "receipt": b""}

        run("test-uuid-1234", "scitt_created", default_options)

        call_kwargs = mock_create_stmt.call_args
        assert call_kwargs.kwargs["subject"] == "vcon://test-uuid-1234"
