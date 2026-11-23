"""Traceparent at the API, trace ids in JSON logs, and chain span attributes.

The vCons built here are minimal fixtures with a tenant attachment and a tag. They carry no
lawful_basis attachment: nothing in these tests reads or depends on one.
"""

import io
import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from lib.span_attributes import vcon_correlation_attributes

TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
TRACEPARENT = f"00-{TRACE_ID}-b7ad6b7169203331-01"

TENANT_ID = 4242
SESSION_ID = "session-abc-123"


def _vcon_dict():
    return {
        "uuid": "0192f0f0-0000-7000-8000-000000000001",
        "vcon": "0.4.0",
        "attachments": [
            {"purpose": "tenant", "encoding": "json", "body": {"id": TENANT_ID}},
            {
                "purpose": "tags",
                "encoding": "json",
                "body": [f"telnyx_call_session_id:{SESSION_ID}", "other:x"],
            },
        ],
        "dialog": [{"type": "text", "body": "SECRET DIALOG TEXT"}],
        "analysis": [],
    }


@pytest.fixture(autouse=True)
def keep_loggers_enabled():
    """Importing lib.logging_utils or main runs fileConfig, which disables loggers that already
    exist. Put them back so other test modules still see their log output."""
    manager = logging.root.manager
    before = {name: getattr(lg, "disabled", False) for name, lg in manager.loggerDict.items()}
    yield
    for name, disabled in before.items():
        manager.loggerDict[name].disabled = disabled


@pytest.fixture
def log_correlation():
    import lib.logging_utils  # noqa: F401  fileConfig plus the OTel log record factory

    yield


@pytest.fixture
def span_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield exporter, provider
    provider.shutdown()


# --- traceparent at the API -----------------------------------------------------------------


def test_api_honors_incoming_traceparent(span_exporter):
    from fastapi.testclient import TestClient
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    import api

    exporter, provider = span_exporter
    # Another test may already have served a request, which builds and caches the middleware stack.
    api.app.middleware_stack = None
    FastAPIInstrumentor.instrument_app(api.app, tracer_provider=provider)
    try:
        response = TestClient(api.app).get("/health", headers={"traceparent": TRACEPARENT})
        assert response.status_code == 200
    finally:
        FastAPIInstrumentor.uninstrument_app(api.app)
        api.app.middleware_stack = None

    server_spans = [s for s in exporter.get_finished_spans() if s.kind == trace.SpanKind.SERVER]
    assert server_spans, "no server span recorded"
    assert all(format(s.context.trace_id, "032x") == TRACE_ID for s in server_spans)
    assert format(server_spans[0].parent.span_id, "016x") == "b7ad6b7169203331"


# --- trace ids in JSON logs -----------------------------------------------------------------


def _json_logger(name):
    from lib.json_log_formatter import TraceJsonFormatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(TraceJsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log = logging.getLogger(name)
    log.handlers[:] = [handler]
    log.propagate = False
    log.setLevel(logging.INFO)
    return log, stream


def test_json_log_record_carries_trace_and_span_ids(span_exporter, log_correlation, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    _, provider = span_exporter
    log, stream = _json_logger("o6.test.logs.inside")
    tracer = provider.get_tracer("t")
    with tracer.start_as_current_span("work") as span:
        log.info("hello", extra={"vcon_processing_time": 1.5})
        ctx = span.get_span_context()

    record = json.loads(stream.getvalue())
    assert record["trace_id"] == format(ctx.trace_id, "032x")
    assert record["span_id"] == format(ctx.span_id, "016x")
    # Existing fields are unchanged.
    assert record["message"] == "hello"
    assert record["levelname"] == "INFO"
    assert record["name"] == "o6.test.logs.inside"
    assert "asctime" in record
    assert record["vcon_processing_time"] == 1.5
    assert not [k for k in record if k.startswith("otel")]


def test_json_log_record_outside_a_span_has_no_ids(log_correlation, monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317")
    log, stream = _json_logger("o6.test.logs.outside")
    log.info("no span")
    record = json.loads(stream.getvalue())
    assert "trace_id" not in record and "span_id" not in record
    assert record["message"] == "no span"


def test_logging_conf_uses_the_trace_formatter():
    import configparser
    from pathlib import Path

    conf = configparser.ConfigParser()
    conf.read(Path(__file__).parent.parent / "logging.conf")
    assert conf["formatter_json"]["class"] == "lib.json_log_formatter.TraceJsonFormatter"


# --- chain span attributes ------------------------------------------------------------------


def test_correlation_attributes_from_vcon():
    assert vcon_correlation_attributes(_vcon_dict()) == {
        "tenant.id": str(TENANT_ID),
        "call.session_id": SESSION_ID,
    }


def test_correlation_attributes_absent_when_not_in_vcon():
    assert vcon_correlation_attributes({"uuid": "u", "attachments": [], "dialog": []}) == {}
    assert vcon_correlation_attributes(None) == {}
    # A malformed tenant body gives nothing, and no body text is ever returned.
    bad = {"uuid": "u", "attachments": [{"purpose": "tenant", "body": "not json", "encoding": "none"}]}
    assert vcon_correlation_attributes(bad) == {}


VCON_UUID = "0192f0f0-0000-7000-8000-000000000001"


def _run_chain(span_provider, meter_reader, vcon_dict, tracing_on=True):
    """Run one chain with an in-memory span provider.

    Returns the mock standing in for ``main.VconRedis`` so tests can count reads, and the Redis
    client that ``main.r`` is patched to.
    """
    import os

    import main as main_module
    from main import VconChainRequest
    from vcon import Vcon

    chain = {"name": "o6_chain", "links": ["mock_link"], "storages": [], "egress_lists": []}
    main_module.config = {"links": {"mock_link": {"module": "mock_module", "options": {}}}}
    link_module = MagicMock()
    link_module.run.return_value = VCON_UUID
    vcon_redis_cls = MagicMock()
    vcon_redis_cls.return_value.get_vcon.return_value = Vcon(vcon_dict) if vcon_dict is not None else None
    redis_client = MagicMock()

    meter_provider = MeterProvider(metric_readers=[meter_reader])
    with (
        patch.dict("main.imported_modules", {"mock_module": link_module}),
        patch("main.get_tracer", side_effect=lambda name: span_provider.get_tracer(name)),
        patch("main.VconRedis", vcon_redis_cls),
        patch("main.r", redis_client),
        patch.multiple(
            "lib.metrics",
            meter=meter_provider.get_meter("t"),
            _otel_initialized_pid=os.getpid(),
            OTEL_EXPORTER_OTLP_ENDPOINT="http://x:4317",
            counter_metrics={},
            histogram_metrics={},
            updown_counter_metrics={},
            observable_gauges={},
        ),
        patch("main.tracing_enabled", return_value=tracing_on),
    ):
        VconChainRequest(chain, VCON_UUID, context=None).process()
    meter_provider.shutdown()
    return vcon_redis_cls, redis_client


def test_chain_span_has_tenant_and_session_but_metrics_do_not(span_exporter):
    exporter, provider = span_exporter
    reader = InMemoryMetricReader()
    _run_chain(provider, reader, _vcon_dict())

    chain_spans = [s for s in exporter.get_finished_spans() if s.name == "vcon_processing.o6_chain"]
    assert len(chain_spans) == 1
    attrs = dict(chain_spans[0].attributes)
    assert attrs["tenant.id"] == str(TENANT_ID)
    assert attrs["call.session_id"] == SESSION_ID
    # No vCon body content on any span.
    for span in exporter.get_finished_spans():
        assert "SECRET DIALOG TEXT" not in json.dumps(dict(span.attributes), default=str)

    data = reader.get_metrics_data()
    seen = 0
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                for point in metric.data.data_points:
                    seen += 1
                    keys = set(point.attributes)
                    assert "tenant.id" not in keys and "call.session_id" not in keys
                    assert str(TENANT_ID) not in map(str, point.attributes.values())
                    assert SESSION_ID not in map(str, point.attributes.values())
    assert seen > 0


def test_chain_span_without_tenant_or_tag_omits_both(span_exporter):
    exporter, provider = span_exporter
    plain = {"uuid": "0192f0f0-0000-7000-8000-000000000001", "attachments": [], "dialog": []}
    _run_chain(provider, InMemoryMetricReader(), plain)
    chain_span = next(s for s in exporter.get_finished_spans() if s.name == "vcon_processing.o6_chain")
    assert "tenant.id" not in chain_span.attributes
    assert "call.session_id" not in chain_span.attributes


# --- no extra read, and nothing unless an endpoint is configured ---------------------------


def test_chain_span_adds_no_vcon_read(span_exporter):
    """The attributes come from the vCon the link step already loads: one get_vcon per link, and no
    other Redis or storage call from the correlation code."""
    exporter, provider = span_exporter
    with (
        patch("lib.vcon_redis.VconRedis.get_vcon_dict") as get_dict,
        patch("lib.vcon_redis.VconRedis._load_from_storage") as storage,
    ):
        vcon_redis_cls, redis_client = _run_chain(provider, InMemoryMetricReader(), _vcon_dict())
    assert vcon_redis_cls.return_value.get_vcon.call_count == 1
    assert not redis_client.get.called
    assert not get_dict.called and not storage.called


def test_no_attributes_when_no_endpoint_is_configured(span_exporter, monkeypatch):
    """The distro's SDK provider records spans even with nothing exporting. With no endpoint the
    correlation attributes are not computed at all."""
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    import lib.tracing as tracing_lib

    monkeypatch.setattr(tracing_lib, "_tracer_provider", None)
    monkeypatch.setattr(tracing_lib, "_tracer_provider_pid", None)
    exporter, provider = span_exporter
    with patch("main.vcon_correlation_attributes") as attrs:
        _run_chain_real_gate(provider)
    assert not attrs.called
    span = next(s for s in exporter.get_finished_spans() if s.name == "vcon_processing.o6_chain")
    assert "tenant.id" not in span.attributes


def _run_chain_real_gate(provider):
    import main as main_module
    from main import VconChainRequest
    from vcon import Vcon

    chain = {"name": "o6_chain", "links": ["mock_link"], "storages": [], "egress_lists": []}
    main_module.config = {"links": {"mock_link": {"module": "mock_module", "options": {}}}}
    link_module = MagicMock()
    link_module.run.return_value = VCON_UUID
    vcon_redis_cls = MagicMock()
    vcon_redis_cls.return_value.get_vcon.return_value = Vcon(_vcon_dict())
    with (
        patch.dict("main.imported_modules", {"mock_module": link_module}),
        patch("main.get_tracer", side_effect=lambda n: provider.get_tracer(n)),
        patch("main.VconRedis", vcon_redis_cls),
    ):
        VconChainRequest(chain, VCON_UUID, context=None).process()


def test_missing_vcon_with_endpoint_set_is_harmless(span_exporter):
    exporter, provider = span_exporter
    with (
        patch("lib.vcon_redis.VconRedis._load_from_storage") as storage,
        patch("lib.vcon_redis.VconRedis._cache_back_to_redis") as cache_back,
    ):
        vcon_redis_cls, redis_client = _run_chain(provider, InMemoryMetricReader(), None, tracing_on=True)
    assert not redis_client.get.called and not storage.called and not cache_back.called
    span = next(s for s in exporter.get_finished_spans() if s.name == "vcon_processing.o6_chain")
    assert "tenant.id" not in span.attributes and "call.session_id" not in span.attributes


# --- log ids only when telemetry is on ---------------------------------------------------------


def test_json_log_has_no_ids_when_no_endpoint_is_set(span_exporter, log_correlation, monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    _, provider = span_exporter
    log, stream = _json_logger("o6.test.logs.off")
    with provider.get_tracer("t").start_as_current_span("work"):
        log.info("telemetry off")
    record = json.loads(stream.getvalue())
    assert "trace_id" not in record and "span_id" not in record
    assert not [k for k in record if k.startswith("otel")]
