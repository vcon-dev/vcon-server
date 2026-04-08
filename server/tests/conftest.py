import pytest
from unittest.mock import patch
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader


@pytest.fixture
def metric_reader():
    """Injects an in-memory OTEL meter into lib.metrics for validation tests.

    Yields the InMemoryMetricReader so tests can assert on emitted metrics.
    Each test gets a fresh meter with no prior state.
    """
    reader = InMemoryMetricReader()
    provider = MeterProvider(metric_readers=[reader])
    test_meter = provider.get_meter("vcon-server-test")

    with patch.multiple(
        "lib.metrics",
        meter=test_meter,
        _otel_initialized=True,
        OTEL_EXPORTER_OTLP_ENDPOINT="http://test-collector:4317",
        counter_metrics={},
        histogram_metrics={},
    ):
        yield reader

    provider.shutdown()
