import atexit
import logging
import os
import socket
import threading

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from lib.otlp_config import (
    EXPORT_TIMEOUT_S,
    HTTP_PROTOBUF,
    TRACE_SHUTDOWN_BUDGET_S,
    http_signal_url,
    otlp_protocol,
    run_bounded,
)

logger = logging.getLogger(__name__)

# The provider is tracked by pid, like the meter provider in lib.metrics. A forked worker inherits
# the parent's module state, including a span exporter whose threads and channels did not survive
# the fork, so it builds its own provider with its own service.instance.id.
_tracer_provider = None
_tracer_provider_pid = None
_init_lock = threading.Lock()


def init_tracer_provider():
    """Build this process's TracerProvider once per pid, when an OTLP endpoint is set.

    The provider is not installed as the global one: ``set_tracer_provider`` is single-call and
    ``opentelemetry-instrument`` has usually set it already. Spans the server opens by hand come
    from ``get_tracer`` and export through this provider. Auto-instrumented spans (FastAPI, Redis,
    httpx) keep using the global one. Both share the active span context, so they join one trace.

    The pid marker is set only after the build, under a lock, so a second thread waits for the
    provider instead of seeing "initialized" with nothing built.
    """
    global _tracer_provider, _tracer_provider_pid
    pid = os.getpid()
    if _tracer_provider_pid == pid:
        return _tracer_provider
    with _init_lock:
        if _tracer_provider_pid == pid:
            return _tracer_provider
        provider = None
        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if endpoint:
            try:
                host = socket.gethostname()
                resource = Resource.create(
                    {
                        "service.name": os.environ.get("OTEL_SERVICE_NAME", "vcon-server"),
                        "host.name": host,
                        "service.instance.id": f"{host}-pid-{pid}",
                    }
                )
                if otlp_protocol("traces") == HTTP_PROTOBUF:
                    exporter = OTLPHttpSpanExporter(
                        endpoint=http_signal_url("traces", endpoint), timeout=EXPORT_TIMEOUT_S
                    )
                else:
                    exporter = OTLPSpanExporter(endpoint=endpoint, timeout=EXPORT_TIMEOUT_S)
                # shutdown_on_exit=False: the SDK's own atexit hook can block for 30 s on a dead
                # collector. shutdown_tracer_provider (registered below) does it with a time bound.
                provider = TracerProvider(resource=resource, shutdown_on_exit=False)
                provider.add_span_processor(BatchSpanProcessor(exporter, export_timeout_millis=EXPORT_TIMEOUT_S * 1000))
                _register_atexit_once()
                logger.info("OpenTelemetry tracing initialized: pid=%d", pid)
            except Exception as e:
                provider = None
                logger.warning("Failed to initialize OpenTelemetry tracing: %s", e)
        _tracer_provider = provider
        _tracer_provider_pid = pid
        return provider


def tracing_enabled():
    """True when an export endpoint is configured and this process has its own provider."""
    return init_tracer_provider() is not None


_atexit_registered = False


def _register_atexit_once():
    global _atexit_registered
    if not _atexit_registered:
        _atexit_registered = True
        atexit.register(shutdown_tracer_provider)


def shutdown_tracer_provider():
    """Flush and shut down this process's own provider, waiting at most a few seconds.

    A forked multiprocessing child leaves through ``os._exit``, which skips ``atexit``, so a worker
    calls this itself before it returns. A provider inherited from another pid is left alone. With
    the collector down the wait is capped, and spans still queued are dropped.
    """
    global _tracer_provider
    provider = _tracer_provider
    if provider is not None and _tracer_provider_pid == os.getpid():
        _tracer_provider = None
        run_bounded(provider.shutdown, TRACE_SHUTDOWN_BUDGET_S, "tracing")


def get_tracer(name):
    """Tracer for the server's own spans: this process's provider when set, else the global one."""
    provider = init_tracer_provider()
    if provider is not None:
        return provider.get_tracer(name)
    return trace.get_tracer(name)


def init_tracing(build_provider=True):
    """Prepare tracing in this process.

    Builds the per-process tracer provider unless ``build_provider`` is false (the multi-worker
    parent skips it, since each worker builds its own), then instruments OpenAI through openinference when that
    package is installed. It is not a project dependency, so by default this does nothing more.
    When it is installed, prompt and reply content stays off the spans: inputs, outputs, message
    text and embeddings are hidden. Model name and token counts remain.
    """
    if build_provider:
        init_tracer_provider()
    try:
        from openinference.instrumentation import TraceConfig
        from openinference.instrumentation.openai import OpenAIInstrumentor

        config = TraceConfig(
            hide_inputs=True,
            hide_outputs=True,
            hide_input_messages=True,
            hide_output_messages=True,
            hide_input_text=True,
            hide_output_text=True,
            hide_embedding_vectors=True,
        )
        OpenAIInstrumentor().instrument(config=config)
        logger.info("OpenAI instrumentation enabled (LLM spans active, content hidden)")
    except ImportError:
        logger.warning("openinference-instrumentation-openai not installed; " "OpenAI calls will not produce LLM spans")
    except Exception as e:
        logger.warning("Failed to instrument OpenAI: %s", e)
