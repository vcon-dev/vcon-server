import os
import pytest
from unittest.mock import patch
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader


@pytest.fixture
def metric_reader():
    """Injects an in-memory OTEL meter into lib.metrics for validation tests.

    Yields the InMemoryMetricReader so tests can assert on emitted metrics.
    Each test gets a fresh meter with no prior state.

    Patches ``_otel_initialized_pid`` to the current pid so the
    lazy-init helper bails out without trying to instantiate a real OTLP
    exporter (which would clobber the in-memory meter and try to dial
    a non-existent collector).
    """
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    test_meter = provider.get_meter("vcon-server-test")

    with patch.multiple(
        "lib.metrics",
        meter=test_meter,
        _otel_initialized_pid=os.getpid(),
        OTEL_EXPORTER_OTLP_ENDPOINT="http://test-collector:4317",
        counter_metrics={},
        histogram_metrics={},
        updown_counter_metrics={},
        observable_gauges={},
    ):
        yield reader

    provider.shutdown()
