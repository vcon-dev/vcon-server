import logging
import os
import socket

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
OTEL_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "vcon-server")
OTEL_METRIC_EXPORT_INTERVAL = int(os.environ.get("OTEL_METRIC_EXPORT_INTERVAL", "5000"))

meter = None
counter_metrics = {}
histogram_metrics = {}
observable_gauges = {}
updown_counter_metrics = {}
_otel_initialized = False

logger = logging.getLogger(__name__)

# Get the host name
host_name = socket.gethostname()


def init_metrics():
    logger.warning("This function is deprecated, use increment_counter or record_histogram instead")


def stats_gauge(metric_name, value, tags=[]):
    logger.warning("This function is deprecated, use increment_counter or record_histogram instead")


def stats_count(metric_name, value=1, tags=[]):
    logger.warning("This function is deprecated, use increment_counter or record_histogram instead")


def _init_otel_metrics():
    """Lazy initialization of OpenTelemetry metrics.
    
    This function is called automatically when OpenTelemetry metric methods
    are first used. It only initializes if the endpoint is configured.
    """
    global meter, _otel_initialized
    
    # Return early if already initialized or endpoint not configured
    if _otel_initialized or not OTEL_EXPORTER_OTLP_ENDPOINT:
        return
    
    try:
        # Create resource with service name and host
        resource = Resource.create({
            "service.name": OTEL_SERVICE_NAME,
            "host.name": host_name,
        })
        
        # Create OTLP gRPC exporter
        otlp_exporter = OTLPMetricExporter(
            endpoint=OTEL_EXPORTER_OTLP_ENDPOINT,
        )
        
        # Create metric reader with exporter
        reader = PeriodicExportingMetricReader(
            exporter=otlp_exporter,
            export_interval_millis=OTEL_METRIC_EXPORT_INTERVAL,
        )
        
        # Create meter provider
        provider = MeterProvider(
            resource=resource,
            metric_readers=[reader],
        )
        
        # Set global meter provider
        metrics.set_meter_provider(provider)
        
        # Get meter
        meter = metrics.get_meter(__name__)
        _otel_initialized = True
    except Exception as e:
        # Log error but don't fail initialization
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to initialize OpenTelemetry metrics: {e}")
        _otel_initialized = True  # Mark as initialized to avoid repeated attempts


def increment_counter(metric_name, value=1, attributes=None):
    """Increment a counter metric in OpenTelemetry.
    
    Only publishes if OpenTelemetry endpoint is configured.
    Initializes OpenTelemetry automatically on first call if not already initialized.
    
    Args:
        metric_name: Name of the metric
        value: Counter increment value (default: 1)
        attributes: Dictionary of attributes/labels (default: None)
    """
    # Lazy initialization on first use
    _init_otel_metrics()
    
    if not OTEL_EXPORTER_OTLP_ENDPOINT or not meter:
        return
    
    try:
        # Prepare attributes (host is already in resource, no need to add here)
        if attributes is None:
            attributes = {}
        else:
            attributes = attributes.copy()
        
        # Get or create counter metric
        if metric_name not in counter_metrics:
            counter_metrics[metric_name] = meter.create_counter(
                name=metric_name,
                description=f"Counter metric for {metric_name}",
            )
        
        # Record the increment
        counter_metrics[metric_name].add(value, attributes=attributes)
    except Exception as e:
        logger.warning(f"Failed to publish counter metric to OpenTelemetry: {e}")


def add_updown_counter(metric_name, value=1, attributes=None):
    """Add (positive or negative) to an OpenTelemetry UpDownCounter.

    Unlike ``increment_counter`` (monotonic), an UpDownCounter can go down.
    Use for "currently active" or "in-flight" gauges where increment on
    entry and decrement on exit is paired in a try/finally.

    Only publishes if OpenTelemetry endpoint is configured. Initializes
    OpenTelemetry automatically on first call.

    Args:
        metric_name: Name of the metric (e.g. ``"conserver.vcons.inflight"``)
        value: Amount to add (positive or negative). Default: 1.
        attributes: Dictionary of attributes/labels (default: None)
    """
    _init_otel_metrics()

    if not OTEL_EXPORTER_OTLP_ENDPOINT or not meter:
        return

    try:
        if attributes is None:
            attributes = {}
        else:
            attributes = attributes.copy()

        if metric_name not in updown_counter_metrics:
            updown_counter_metrics[metric_name] = meter.create_up_down_counter(
                name=metric_name,
                description=f"UpDownCounter metric for {metric_name}",
            )

        updown_counter_metrics[metric_name].add(value, attributes=attributes)
    except Exception as e:
        logger.warning(f"Failed to publish up_down_counter metric to OpenTelemetry: {e}")


def register_observable_gauge(metric_name, callback, description=None):
    """Register an OpenTelemetry observable gauge.

    The callback is invoked by the OTel SDK on each metric-export tick
    (interval governed by ``OTEL_METRIC_EXPORT_INTERVAL``). It receives a
    single ``options`` argument (unused by callers here) and must return
    an iterable of ``opentelemetry.metrics.Observation`` instances — one
    per dimension combination.

    No-op when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is unset (tests, dev) or when
    a gauge of the same name has already been registered in this process.

    Args:
        metric_name: Name of the metric (e.g. ``"conserver.ingress_list.length"``)
        callback: Zero-arg callable returning an iterable of ``Observation``
        description: Optional description; defaults to a generic string
    """
    # Lazy initialization on first use
    _init_otel_metrics()

    if not OTEL_EXPORTER_OTLP_ENDPOINT or not meter:
        return

    # Idempotent: a gauge is process-lifetime, so subsequent calls are no-ops.
    if metric_name in observable_gauges:
        return

    try:
        observable_gauges[metric_name] = meter.create_observable_gauge(
            name=metric_name,
            callbacks=[lambda _options: callback()],
            description=description or f"Observable gauge for {metric_name}",
        )
    except Exception as e:
        logger.warning(f"Failed to register OpenTelemetry observable gauge {metric_name!r}: {e}")


def record_histogram(metric_name, value, attributes=None):
    """Record a value in a histogram metric in OpenTelemetry.
    
    Only publishes if OpenTelemetry endpoint is configured.
    Initializes OpenTelemetry automatically on first call if not already initialized.
    
    Args:
        metric_name: Name of the metric
        value: Value to record in the histogram
        attributes: Dictionary of attributes/labels (default: None)
    """
    # Lazy initialization on first use
    _init_otel_metrics()

    if not OTEL_EXPORTER_OTLP_ENDPOINT or not meter:
        return
    
    try:
        # Prepare attributes (host is already in resource, no need to add here)
        if attributes is None:
            attributes = {}
        else:
            attributes = attributes.copy()
        
        # Get or create histogram metric
        if metric_name not in histogram_metrics:
            histogram_metrics[metric_name] = meter.create_histogram(
                name=metric_name,
                description=f"Histogram metric for {metric_name}",
            )
        
        # Record the value
        histogram_metrics[metric_name].record(value, attributes=attributes)
    except Exception as e:
        logger.warning(f"Failed to publish histogram metric to OpenTelemetry: {e}")
