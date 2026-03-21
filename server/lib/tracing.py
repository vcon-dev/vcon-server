import logging

logger = logging.getLogger(__name__)


def init_tracing():
    """Instrument OpenAI calls with LLM-specific OTEL spans.

    Adds model name, token counts, and message content to traces so that
    any configured OTEL exporter (via OTEL_EXPORTER_OTLP_ENDPOINT) receives
    full LLM span data. Routing to specific backends (SigNoz, Arize, etc.)
    is handled by the OTEL Collector — not here.
    """
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor

        OpenAIInstrumentor().instrument()
        logger.info("OpenAI instrumentation enabled (LLM spans active)")
    except ImportError:
        logger.warning(
            "openinference-instrumentation-openai not installed; "
            "OpenAI calls will not produce LLM spans"
        )
    except Exception as e:
        logger.warning("Failed to instrument OpenAI: %s", e)
