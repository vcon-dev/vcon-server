import logging
from settings import LOGGING_CONFIG_FILE
import logging.config

logging.config.fileConfig(LOGGING_CONFIG_FILE)

try:
    # Stamp otelTraceID and otelSpanID on every log record so the JSON formatter can emit
    # trace_id and span_id. set_logging_format=False leaves our own format alone.
    from opentelemetry.instrumentation.logging import LoggingInstrumentor

    LoggingInstrumentor().instrument(set_logging_format=False)
except Exception:  # pragma: no cover - logging must never fail to start
    logging.getLogger(__name__).warning("OpenTelemetry log correlation unavailable", exc_info=True)


def init_logger(name):
    return logging.getLogger(name)
