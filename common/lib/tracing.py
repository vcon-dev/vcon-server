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

from lib.otlp_config import HTTP_PROTOBUF, http_signal_url, otlp_protocol

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
                    exporter = OTLPHttpSpanExporter(endpoint=http_signal_url("traces", endpoint))
                else:
                    exporter = OTLPSpanExporter(endpoint=endpoint)
                provider = TracerProvider(resource=resource)
                provider.add_span_processor(BatchSpanProcessor(exporter))
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


def shutdown_tracer_provider():
    """Flush and shut down this process's own provider.

    A forked multiprocessing child leaves through ``os._exit``, which skips ``atexit``, so a worker
    calls this itself before it returns. A provider inherited from another pid is left alone.
    """
    global _tracer_provider
    if _tracer_provider is not None and _tracer_provider_pid == os.getpid():
        try:
            _tracer_provider.shutdown()
        except Exception as e:
            logger.warning("Failed to shut down OpenTelemetry tracing: %s", e)
        _tracer_provider = None


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
