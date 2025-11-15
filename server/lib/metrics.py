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
_otel_initialized = False

logger = logging.getLogger(__name__)

# Get the host name
host_name = socket.gethostname()


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
    
    logger.info(f"Record histogram metric {metric_name} to OpenTelemetry to {OTEL_EXPORTER_OTLP_ENDPOINT}, initialized: {_otel_initialized}, value: {value}")
    if not OTEL_EXPORTER_OTLP_ENDPOINT or not meter:
        logger.info(f"Failed to record histogram metric {metric_name} to OpenTelemetry to {OTEL_EXPORTER_OTLP_ENDPOINT}")
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
        logger.info("Recorded histogram metric data to OpenTelemetry")
    except Exception as e:
        logger.warning(f"Failed to publish histogram metric to OpenTelemetry: {e}")
