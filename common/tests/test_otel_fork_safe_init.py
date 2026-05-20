"""Unit tests for the fork-safe ``_init_otel_metrics`` behavior in
``common/lib/metrics.py``.

The function tracks the pid that last initialized the OTel SDK in this
process. A different pid (i.e. we're in a forked child) triggers
re-initialization with a fresh ``service.instance.id``, a fresh meter,
and an emptied instrument cache.
"""

import os
from unittest.mock import MagicMock, patch

import pytest


def _reset_module_state(metrics_module):
    """Put lib.metrics back into a pristine 'not yet initialized' state
    so each test runs against the same baseline."""
    metrics_module._otel_initialized_pid = None
    metrics_module.meter = None
    metrics_module.counter_metrics.clear()
    metrics_module.histogram_metrics.clear()
    metrics_module.updown_counter_metrics.clear()
    metrics_module.observable_gauges.clear()


class TestInitOtelMetricsForkSafe:
    def test_first_call_in_a_process_initializes(self):
        from lib import metrics
        _reset_module_state(metrics)

        with patch("lib.metrics.OTLPMetricExporter") as mock_exp, \
             patch("lib.metrics.MeterProvider") as mock_mp, \
             patch("lib.metrics.metrics.set_meter_provider") as mock_set, \
             patch("lib.metrics.metrics.get_meter", return_value=MagicMock()), \
             patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317"):

            metrics._init_otel_metrics()

        # MeterProvider was built, set globally, and we recorded the pid.
        assert mock_mp.called
        assert mock_set.called
        assert metrics._otel_initialized_pid == os.getpid()

    def test_second_call_in_same_pid_is_a_no_op(self):
        from lib import metrics
        _reset_module_state(metrics)

        # Mark this pid as already initialized.
        metrics._otel_initialized_pid = os.getpid()

        with patch("lib.metrics.MeterProvider") as mock_mp, \
             patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317"):
            metrics._init_otel_metrics()

        # Skipped entirely — no new MeterProvider construction.
        assert not mock_mp.called

    def test_different_pid_triggers_reinit(self):
        """When a forked child inherits ``_otel_initialized_pid`` from
        the parent, ``_init_otel_metrics`` MUST detect the pid mismatch
        and rebuild the MeterProvider in the child's address space."""
        from lib import metrics
        _reset_module_state(metrics)

        # Simulate having been initialized in a different (parent) pid.
        metrics._otel_initialized_pid = os.getpid() + 1000  # any other pid
        # Also seed the instrument caches as the parent would have.
        metrics.counter_metrics["dummy"] = MagicMock()
        metrics.updown_counter_metrics["dummy"] = MagicMock()

        with patch("lib.metrics.OTLPMetricExporter") as mock_exp, \
             patch("lib.metrics.MeterProvider") as mock_mp, \
             patch("lib.metrics.metrics.set_meter_provider") as mock_set, \
             patch("lib.metrics.metrics.get_meter", return_value=MagicMock()), \
             patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317"):

            metrics._init_otel_metrics()

        # Fresh provider built in this process.
        assert mock_mp.called
        # Resource passed to MeterProvider contains a service.instance.id
        # built from host + this pid.
        kwargs = mock_mp.call_args.kwargs
        resource = kwargs["resource"]
        attrs = dict(resource.attributes)
        assert attrs["service.instance.id"] == f"{metrics.host_name}-pid-{os.getpid()}"
        assert attrs["host.name"] == metrics.host_name

        # Instrument caches inherited from the "parent" were cleared so
        # they get rebuilt against the new MeterProvider.
        assert metrics.counter_metrics == {}
        assert metrics.updown_counter_metrics == {}

        # New pid is recorded.
        assert metrics._otel_initialized_pid == os.getpid()

    def test_no_endpoint_recorded_as_initialized(self):
        """If OTLP endpoint is not configured we still record the pid
        as initialized, so subsequent calls bail without re-checking."""
        from lib import metrics
        _reset_module_state(metrics)

        with patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", None):
            metrics._init_otel_metrics()

        assert metrics._otel_initialized_pid == os.getpid()
        assert metrics.meter is None  # never created

    def test_exporter_failure_still_marks_pid_initialized(self):
        """If MeterProvider construction throws, we should still mark
        this pid as 'tried' so we don't hot-loop trying every call."""
        from lib import metrics
        _reset_module_state(metrics)

        with patch("lib.metrics.OTLPMetricExporter",
                   side_effect=RuntimeError("connection refused")), \
             patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317"):
            metrics._init_otel_metrics()

        assert metrics._otel_initialized_pid == os.getpid()
