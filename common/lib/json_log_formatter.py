"""JSON log formatter that carries the active trace and span ids."""

import os

from pythonjsonlogger.jsonlogger import JsonFormatter


def _is_set(hex_id):
    """The instrumentation writes "0" (or all zeros) when no span is active."""
    try:
        return bool(hex_id) and int(hex_id, 16) != 0
    except (TypeError, ValueError):
        return False


class TraceJsonFormatter(JsonFormatter):
    """JsonFormatter plus ``trace_id`` and ``span_id``.

    The ids come from the OpenTelemetry logging instrumentation, which stamps ``otelTraceID`` and
    ``otelSpanID`` on every record (see ``lib.logging_utils``). Outside a span, with no
    OTEL_EXPORTER_OTLP_ENDPOINT set, or with the instrumentation off, the two fields are left out and every other field is unchanged.
    """

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        trace_id = getattr(record, "otelTraceID", None)
        span_id = getattr(record, "otelSpanID", None)
        # The instrumentation's own attributes would otherwise appear as extra keys.
        for key in ("otelTraceID", "otelSpanID", "otelTraceSampled", "otelServiceName"):
            log_record.pop(key, None)
        # Telemetry off (no endpoint) leaves the log format exactly as it was.
        if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") and _is_set(trace_id) and _is_set(span_id):
            log_record["trace_id"] = trace_id
            log_record["span_id"] = span_id
