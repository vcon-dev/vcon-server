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


def test_json_log_record_carries_trace_and_span_ids(span_exporter, log_correlation):
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


def test_json_log_record_outside_a_span_has_no_ids(log_correlation):
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


def _run_chain(span_provider, meter_reader, vcon_dict):
    import main as main_module
    from main import VconChainRequest

    chain = {"name": "o6_chain", "links": ["mock_link"], "storages": [], "egress_lists": []}
    main_module.config = {"links": {"mock_link": {"module": "mock_module", "options": {}}}}
    link_module = MagicMock()
    link_module.run.return_value = "0192f0f0-0000-7000-8000-000000000001"
    redis_instance = MagicMock()
    redis_instance.get_vcon_dict.return_value = vcon_dict

    meter_provider = MeterProvider(metric_readers=[meter_reader])
    import os

    with (
        patch.dict("main.imported_modules", {"mock_module": link_module}),
        patch("main.get_tracer", side_effect=lambda name: span_provider.get_tracer(name)),
        patch("main.VconRedis", return_value=redis_instance),
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
    ):
        VconChainRequest(chain, "0192f0f0-0000-7000-8000-000000000001", context=None).process()
    meter_provider.shutdown()


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
