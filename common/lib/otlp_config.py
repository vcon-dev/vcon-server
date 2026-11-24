"""Shared OTLP settings for the metrics and trace exporters."""

import logging
import os
import threading

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


# Bounds on telemetry work at exit. A dead collector must not hold a worker for the SDK defaults,
# which add up to about a minute (30 s trace shutdown plus the metrics export timeout).
EXPORT_TIMEOUT_S = 2
TRACE_SHUTDOWN_BUDGET_S = 3.0
METRIC_SHUTDOWN_BUDGET_S = 2.0


def run_bounded(fn, budget_s, what):
    """Run ``fn`` on a daemon thread and give up waiting after ``budget_s`` seconds.

    Returns True when ``fn`` finished in time. A late thread is abandoned: it is a daemon, so it
    cannot keep the process alive, and whatever it had not exported is dropped.
    """
    error = []

    def target():
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            error.append(e)

    thread = threading.Thread(target=target, name=f"otel-shutdown-{what}", daemon=True)
    thread.start()
    thread.join(budget_s)
    if thread.is_alive():
        logger.warning("OpenTelemetry %s shutdown still running after %.1f s, abandoning it", what, budget_s)
        return False
    if error:
        logger.warning("Failed to shut down OpenTelemetry %s: %s", what, error[0])
    return True
