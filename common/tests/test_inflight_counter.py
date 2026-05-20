"""Unit tests for ``add_updown_counter`` and the ``conserver.vcons.inflight``
wiring in ``_handle_vcon``.

The UpDownCounter must increment on entry to ``_handle_vcon`` and
decrement in the ``finally``, including when the chain raises (vCon
routed to DLQ) and when ``before_processing`` returns falsy (early
return).
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestUpDownCounterHelper:
    """``add_updown_counter`` is the lazy-init OTel wrapper. Verify that
    it creates the underlying instrument once and add() is called with
    the right value/attributes."""

    def test_first_call_creates_instrument(self):
        from lib import metrics
        # Reset module state so this test runs against a fresh meter
        metrics.updown_counter_metrics.clear()

        fake_instr = MagicMock()
        fake_meter = MagicMock()
        fake_meter.create_up_down_counter.return_value = fake_instr

        with patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317"), \
             patch.object(metrics, "_otel_initialized_pid", os.getpid()), \
             patch.object(metrics, "meter", fake_meter):
            metrics.add_updown_counter("conserver.vcons.inflight", 1,
                                       attributes={"chain.name": "main"})

        fake_meter.create_up_down_counter.assert_called_once_with(
            name="conserver.vcons.inflight",
            description="UpDownCounter metric for conserver.vcons.inflight",
        )
        fake_instr.add.assert_called_once_with(1, attributes={"chain.name": "main"})

    def test_second_call_reuses_instrument(self):
        from lib import metrics
        metrics.updown_counter_metrics.clear()

        fake_instr = MagicMock()
        fake_meter = MagicMock()
        fake_meter.create_up_down_counter.return_value = fake_instr

        with patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317"), \
             patch.object(metrics, "_otel_initialized_pid", os.getpid()), \
             patch.object(metrics, "meter", fake_meter):
            metrics.add_updown_counter("conserver.vcons.inflight", 1)
            metrics.add_updown_counter("conserver.vcons.inflight", -1)

        # Created once, added twice.
        assert fake_meter.create_up_down_counter.call_count == 1
        assert fake_instr.add.call_count == 2
        # Values 1 then -1, attributes default to {} (not None).
        assert fake_instr.add.call_args_list[0].args == (1,)
        assert fake_instr.add.call_args_list[0].kwargs == {"attributes": {}}
        assert fake_instr.add.call_args_list[1].args == (-1,)

    def test_no_op_when_endpoint_unset(self):
        from lib import metrics
        metrics.updown_counter_metrics.clear()

        with patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", None), \
             patch.object(metrics, "meter", None):
            # Should be a silent no-op; no exception raised.
            metrics.add_updown_counter("conserver.vcons.inflight", 1)

        assert "conserver.vcons.inflight" not in metrics.updown_counter_metrics


class TestHandleVconInflightTracking:
    """``_handle_vcon`` wraps the chain run in +1/-1 updown_counter calls.
    All exit paths (success, raise, early-return) must decrement."""

    def _patches(self):
        """Common patches: stub Redis-bound helpers, the hook, and the
        chain-request class so we can drive ``_handle_vcon`` in isolation."""
        # We patch where the names are LOOKED UP — i.e. in conserver.main —
        # not where they're defined.
        return {
            "retrieve_context": patch("main.retrieve_context", return_value={}),
            "log_llen": patch("main.log_llen"),
            "queue": patch("main.queue"),
            "VconChainRequest": patch("main.VconChainRequest"),
            "hook": patch("main.hook"),
        }

    def _run_handle_vcon(self, before_processing_returns=True,
                        chain_raises=None):
        from main import _handle_vcon

        with self._patches()["retrieve_context"], \
             self._patches()["log_llen"], \
             self._patches()["queue"] as mock_queue, \
             self._patches()["VconChainRequest"] as mock_req_cls, \
             self._patches()["hook"] as mock_hook, \
             patch("main.add_updown_counter") as mock_inflight:

            mock_hook.before_processing.return_value = before_processing_returns
            req = MagicMock()
            req.vcon_id = "vc1"
            if chain_raises is not None:
                req.process.side_effect = chain_raises
            mock_req_cls.return_value = req

            try:
                _handle_vcon(
                    worker_name="Worker-1",
                    ingress_list="transcribe",
                    vcon_id="vc1",
                    chain_details={"name": "transcription_chain", "links": []},
                )
            except Exception:
                # _handle_vcon's outer try/except/finally is supposed to
                # swallow chain errors, but we don't want a test crash to
                # mask the inflight calls
                pass

            return mock_inflight

    def test_inflight_incremented_then_decremented_on_success(self):
        mock_inflight = self._run_handle_vcon(before_processing_returns=True)

        assert mock_inflight.call_count == 2
        # First call: +1
        assert mock_inflight.call_args_list[0].args[:2] == ("conserver.vcons.inflight", 1)
        # Second call: -1
        assert mock_inflight.call_args_list[1].args[:2] == ("conserver.vcons.inflight", -1)
        # Same chain.name attribute on both
        attrs1 = mock_inflight.call_args_list[0].kwargs["attributes"]
        attrs2 = mock_inflight.call_args_list[1].kwargs["attributes"]
        assert attrs1 == attrs2 == {"chain.name": "transcription_chain"}

    def test_inflight_decremented_when_before_processing_returns_falsy(self):
        """Early-return (license fail, etc.) must still decrement."""
        mock_inflight = self._run_handle_vcon(before_processing_returns=False)

        assert mock_inflight.call_count == 2
        assert mock_inflight.call_args_list[0].args[:2] == ("conserver.vcons.inflight", 1)
        assert mock_inflight.call_args_list[1].args[:2] == ("conserver.vcons.inflight", -1)

    def test_inflight_decremented_when_chain_raises(self):
        """Chain throwing must still decrement (DLQ path)."""
        mock_inflight = self._run_handle_vcon(
            before_processing_returns=True,
            chain_raises=RuntimeError("link blew up"),
        )

        assert mock_inflight.call_count == 2
        assert mock_inflight.call_args_list[0].args[:2] == ("conserver.vcons.inflight", 1)
        assert mock_inflight.call_args_list[1].args[:2] == ("conserver.vcons.inflight", -1)
