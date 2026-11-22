"""Shared OTLP settings for the metrics and trace exporters."""

import logging
import os

logger = logging.getLogger(__name__)

GRPC = "grpc"
HTTP_PROTOBUF = "http/protobuf"


def otlp_protocol(signal):
    """Return ``grpc`` or ``http/protobuf`` for ``signal`` (``metrics`` or ``traces``).

    Reads ``OTEL_EXPORTER_OTLP_<SIGNAL>_PROTOCOL`` first, then ``OTEL_EXPORTER_OTLP_PROTOCOL``.
    Unset keeps the historic gRPC default. Any other value (``http/json``) falls back to gRPC
    with a warning, since no exporter for it is installed.
    """
    specific = {
        "metrics": os.environ.get("OTEL_EXPORTER_OTLP_METRICS_PROTOCOL"),
        "traces": os.environ.get("OTEL_EXPORTER_OTLP_TRACES_PROTOCOL"),
    }[signal]
    raw = specific or os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL")
    value = (raw or GRPC).strip().lower()
    if value in (GRPC, HTTP_PROTOBUF):
        return value
    logger.warning("Unsupported OTEL_EXPORTER_OTLP_PROTOCOL %r for %s, using grpc", raw, signal)
    return GRPC


def http_signal_url(signal, base_endpoint):
    """Full OTLP/HTTP URL for ``signal``.

    An explicit endpoint passed to an HTTP exporter is used as given, with no path added, so the
    ``/v1/<signal>`` suffix has to be appended here. A per-signal endpoint variable is used as is.
    """
    specific = {
        "metrics": os.environ.get("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT"),
        "traces": os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
    }[signal]
    if specific:
        return specific
    return f"{base_endpoint.rstrip('/')}/v1/{signal}"
