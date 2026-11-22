"""Metrics over OTLP/HTTP, protocol selection, and the per-process tracer provider."""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import MagicMock, patch

import pytest


class _Collector:
    """A bare HTTP endpoint that records the paths OTLP/HTTP posts to."""

    def __init__(self):
        self.paths = []
        self.bodies = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                outer.bodies.append(self.rfile.read(length))
                outer.paths.append(self.path)
                self.send_response(200)
                self.send_header("Content-Type", "application/x-protobuf")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def _reset_metrics(metrics):
    metrics._otel_initialized_pid = None
    metrics.meter = None
    metrics._meter_provider = None
    for cache in (
        metrics.counter_metrics,
        metrics.histogram_metrics,
        metrics.updown_counter_metrics,
        metrics.observable_gauges,
    ):
        cache.clear()


def test_metrics_export_over_http_protobuf(monkeypatch):
    """CON-1407: OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf must send OTLP/HTTP, not gRPC."""
    from lib import metrics

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", raising=False)
    _reset_metrics(metrics)
    try:
        with (
            _Collector() as collector,
            patch("lib.metrics.atexit.register"),
            patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", collector.url),
        ):
            metrics.increment_counter("o6.test.counter", attributes={"chain.name": "c"})
            assert metrics._meter_provider is not None
            metrics._meter_provider.force_flush()
            metrics._meter_provider.shutdown()
        assert set(collector.paths) == {"/v1/metrics"}
        assert b"o6.test.counter" in collector.bodies[0]
    finally:
        _reset_metrics(metrics)


def test_metrics_default_protocol_is_grpc(monkeypatch):
    from lib import metrics

    monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", raising=False)
    _reset_metrics(metrics)
    try:
        with (
            patch("lib.metrics.OTLPMetricExporter") as grpc_exp,
            patch("lib.metrics.OTLPHttpMetricExporter") as http_exp,
            patch("lib.metrics.MeterProvider"),
            patch("lib.metrics.atexit.register"),
            patch.object(metrics, "OTEL_EXPORTER_OTLP_ENDPOINT", "http://fake:4317"),
        ):
            metrics._init_otel_metrics()
        grpc_exp.assert_called_once_with(endpoint="http://fake:4317")
        assert not http_exp.called
    finally:
        _reset_metrics(metrics)


def test_unknown_protocol_falls_back_to_grpc(monkeypatch):
    from lib.otlp_config import otlp_protocol

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/json")
    assert otlp_protocol("metrics") == "grpc"
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL", "http/protobuf")
    assert otlp_protocol("metrics") == "http/protobuf"
    assert otlp_protocol("traces") == "grpc"


@pytest.fixture
def tracing_module():
    from lib import tracing

    tracing._tracer_provider = None
    tracing._tracer_provider_pid = None
    yield tracing
    tracing._tracer_provider = None
    tracing._tracer_provider_pid = None


def test_tracer_provider_not_built_without_endpoint(tracing_module, monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert tracing_module.init_tracer_provider() is None
    assert tracing_module._tracer_provider_pid == os.getpid()


def test_tracer_provider_exports_over_http_protobuf(tracing_module, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    with (
        patch("lib.tracing.OTLPHttpSpanExporter") as http_exp,
        patch("lib.tracing.OTLPSpanExporter") as grpc_exp,
        patch("lib.tracing.BatchSpanProcessor"),
    ):
        tracing_module.init_tracer_provider()
    http_exp.assert_called_once_with(endpoint="http://collector:4318/v1/traces")
    assert not grpc_exp.called


def test_tracer_provider_is_rebuilt_in_a_forked_child(tracing_module, monkeypatch):
    """A child that inherits the parent's pid marker must build its own provider and instance id."""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_PROTOCOL", raising=False)
    tracing_module._tracer_provider = MagicMock(name="parent_provider")
    tracing_module._tracer_provider_pid = os.getpid() + 1000

    with patch("lib.tracing.OTLPSpanExporter"), patch("lib.tracing.BatchSpanProcessor"):
        provider = tracing_module.init_tracer_provider()

    assert provider is tracing_module._tracer_provider
    assert not isinstance(provider, MagicMock)
    assert dict(provider.resource.attributes)["service.instance.id"].endswith(f"-pid-{os.getpid()}")
    assert tracing_module._tracer_provider_pid == os.getpid()

    # Same pid again: no rebuild.
    assert tracing_module.init_tracer_provider() is provider


def test_get_tracer_uses_process_provider(tracing_module, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    with patch("lib.tracing.OTLPSpanExporter"), patch("lib.tracing.BatchSpanProcessor"):
        tracer = tracing_module.get_tracer("x")
        assert tracer is not None
        assert tracing_module._tracer_provider is not None
