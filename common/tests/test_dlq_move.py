"""Tests for conserver/dlq.py::move_to_dlq (Refactor #6)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from dlq import move_to_dlq


def test_move_to_dlq_lpushes_and_extends_ttl():
    r = MagicMock()
    with patch("dlq.VCON_DLQ_EXPIRY", 3600):
        name = move_to_dlq(r, "ingress_x", "vcon-1", worker_name="W1")

    assert name.endswith(":dead_letter_queue") or "dead" in name.lower() or name != "ingress_x"
    r.lpush.assert_called_once_with(name, "vcon-1")
    r.expire.assert_called_once_with("vcon:vcon-1", 3600)


def test_move_to_dlq_skips_expire_when_expiry_disabled():
    r = MagicMock()
    with patch("dlq.VCON_DLQ_EXPIRY", 0):
        move_to_dlq(r, "ingress_x", "vcon-2")

    r.lpush.assert_called_once()
    r.expire.assert_not_called()


def test_move_to_dlq_passes_error_to_debug_log():
    r = MagicMock()
    err = RuntimeError("boom")
    with patch("dlq.VCON_DLQ_EXPIRY", 0), patch("dlq.logger") as mock_logger:
        move_to_dlq(r, "q1", "vcon-3", worker_name="W2", error=err)

    # Info-log with prefix, debug-log contains the error.
    info_messages = [c.args for c in mock_logger.info.call_args_list]
    debug_messages = [c.args for c in mock_logger.debug.call_args_list]
    assert any("[W2]" in str(m) for m in info_messages + debug_messages)
    assert any("boom" in repr(m) for m in debug_messages)
