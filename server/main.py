"""Main server module for vCon processing.

This module handles the core vCon processing pipeline, including chain management,
link processing, and storage operations. It implements a Redis-based queue system
for processing vCons through configured processing chains.

Supports multi-worker mode for parallel vCon processing and concurrent storage
operations for improved throughput with I/O-bound workloads.
"""

import importlib
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, TypedDict

import follower
import redis_mgr

from config import get_config, get_worker_count, is_parallel_storage_enabled, get_start_method
from version import get_version_string, get_version_info
from dlq_utils import get_ingress_list_dlq_name
from settings import VCON_DLQ_EXPIRY
from lib.context_utils import retrieve_context, store_context_sync, extract_otel_trace_context
from lib.error_tracking import init_error_tracker
from lib.metrics import record_histogram, increment_counter
from storage.base import Storage

# OpenTelemetry trace context propagation
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, SpanContext, TraceFlags, Link

logger = logging.getLogger("main")
shutdown_requested = False

# Track worker processes for graceful shutdown
worker_processes: List[multiprocessing.Process] = []


class ChainConfig(TypedDict):
    """Configuration type for a vCon processing chain.

    Attributes:
        name: The name of the chain
        links: Optional list of processing link names
        storages: Optional list of storage backend names
        ingress_lists: List of input queue names
        egress_lists: Optional list of output queue names
        enabled: Whether the chain is enabled (1) or disabled (0)
        timeout: Optional processing timeout in seconds
    """
    name: str
    links: Optional[List[str]]
    storages: Optional[List[str]]
    ingress_lists: List[str]
    egress_lists: Optional[List[str]]
    enabled: int
    timeout: Optional[int]


IngressChainMap = Dict[str, ChainConfig]


config: Optional[Dict] = None


def signal_handler(signum: int, frame: Optional[object]) -> None:
    """Handle SIGTERM/SIGINT signal for graceful shutdown.
    
    In multi-worker mode, this signals all worker processes to shut down.
    Each worker will complete its current vCon processing before exiting.
    
    Args:
        signum: Signal number
        frame: Current stack frame (unused)
    """
    signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    logger.info("%s received, initiating graceful shutdown...", signal_name)
    global shutdown_requested
    shutdown_requested = True
    
    # In main process, signal all workers to shut down
    for worker in worker_processes:
        if worker.is_alive():
            logger.info("Signaling worker %s (PID %s) to shut down", worker.name, worker.pid)
            try:
                os.kill(worker.pid, signal.SIGTERM)
            except (ProcessLookupError, OSError):
                # Worker already terminated
                pass


def import_or_install(module_name: str, pip_name: Optional[str] = None) -> object:
    """Import a module, installing it via pip if not found.

    Args:
        module_name: The name of the module to import
        pip_name: Optional pip package name (defaults to module_name)

    Returns:
        The imported module

    Raises:
        Exception: If module installation or import fails
    """
    if pip_name is None:
        pip_name = module_name

    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        logger.info(
            "Module %s not found, attempting to install %s", module_name, pip_name
        )
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
            logger.info("Successfully installed %s", pip_name)
            return importlib.import_module(module_name)
        except subprocess.CalledProcessError as e:
            logger.error("Failed to install %s: %s", pip_name, str(e))
            raise
        except Exception as e:
            logger.error(
                "Error importing %s after installation: %s", module_name, str(e)
            )
            raise


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

init_error_tracker()
imported_modules: Dict[str, object] = {}

# Initialize Redis client
r = redis_mgr.get_client()


class VconChainRequest:
    """Handles the processing of a single vCon through a configured chain.

    This class manages the execution of processing links, storage operations,
    and egress handling for a vCon as it moves through its processing chain.

    Attributes:
        vcon_id: Unique identifier for the vCon being processed
        chain_details: Configuration details for the processing chain
        context: Optional context data propagated from the API
    """

    def __init__(self, chain_details: ChainConfig, vcon_id: str, context: Optional[Dict] = None) -> None:
        """Initialize a new vCon chain processing request.

        Args:
            chain_details: Configuration for the processing chain
            vcon_id: Unique identifier for the vCon
            context: Optional context data propagated from the API (contains trace_id, span_id, etc.)
        """
        self.vcon_id = vcon_id
        self.chain_details = chain_details
        self.context = context
        self._span = None
        self._span_context_manager = None

    def process(self) -> None:
        """Process the vCon through all configured chain links.

        Executes each link in sequence, handles timing metrics, and manages
        the overall processing flow. Will stop processing if any link indicates
        the chain should not continue.
        
        Creates a new span from context if available for trace propagation (POC).
        """
        # Create span from context if available (POC) - use as context manager
        if self.context:
            self._span_context_manager = self._create_span_from_context()
            if self._span_context_manager:
                # Enter the context manager to make the span current
                # This links the span to the parent trace
                self._span = self._span_context_manager.__enter__()
                # Verify trace linkage
                if self._span:
                    span_ctx = self._span.get_span_context()
                    parent_trace_id = self.context.get("trace_id", "")
                    logger.info(
                        f"Span activated for vCon {self.vcon_id}: "
                        f"trace_id={format(span_ctx.trace_id, '032x')}, "
                        f"span_id={format(span_ctx.span_id, '016x')}, "
                        f"expected_trace_id={parent_trace_id}, "
                        f"match={format(span_ctx.trace_id, '032x') == parent_trace_id}"
                    )
            else:
                self._span = None
                self._span_context_manager = None
        else:
            self._span = None
            self._span_context_manager = None
        
        vcon_started = time.time()
        logger.info(
            "Started processing vCon %s with chain %s",
            self.vcon_id,
            self.chain_details["name"]
        )

        should_continue_chain = self.vcon_id
        for i in range(len(self.chain_details["links"])):
            should_continue_chain = self._process_link(self.chain_details["links"], i)
            if not should_continue_chain:
                logger.info(
                    "Link %s halted chain processing for vCon %s",
                    self.chain_details["links"][i],
                    self.vcon_id,
                )
                break
            if should_continue_chain != self.vcon_id:
                logger.info(
                    "Link %s updated vCon %s to %s",
                    self.chain_details["links"][i],
                    self.vcon_id,
                    should_continue_chain,
                )
                self.vcon_id = should_continue_chain

        if should_continue_chain:
            self._wrap_up()
        vcon_processing_time = round(time.time() - vcon_started, 3)
        logger.info(
            "Completed processing vCon %s in %s seconds - Chain: %s",
            self.vcon_id,
            vcon_processing_time,
            self.chain_details["name"],
            extra={
                "vcon_processing_time": vcon_processing_time,
                "chain_name": self.chain_details["name"]
            }
        )
        record_histogram("conserver.main_loop.vcon_processing_time", vcon_processing_time)
        increment_counter("conserver.main_loop.count_vcons_processed")
        
        # End span if created - exit the context manager
        if self._span_context_manager:
            try:
                current_span = trace.get_current_span()
                if current_span:
                    current_span.set_status(Status(StatusCode.OK))
                # Exit the context manager which will end the span
                self._span_context_manager.__exit__(None, None, None)
            except Exception as e:
                logger.debug(f"Failed to end span: {e}")

    def _create_span_from_context(self):
        """Create a new span from propagated trace context using span links.
        
        Since vCon processing is asynchronous (queued and processed later),
        we use span links instead of parent-child relationships to represent
        the causal relationship between the API request and the async processing.
        
        Returns:
            The span context manager, or None if creation failed
        """
        if not self.context:
            return None
        
        try:
            tracer = trace.get_tracer(__name__)
            
            # Extract trace context from stored context
            trace_id = int(self.context.get("trace_id", "0"), 16)
            span_id = int(self.context.get("span_id", "0"), 16)
            trace_flags = self.context.get("trace_flags", 0)
            
            # Create span context from the propagated values
            parent_span_context = SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                is_remote=True,
                trace_flags=TraceFlags(trace_flags)
            )
            
            # Create a new span with a link to the parent span context
            # This represents an async relationship rather than a parent-child relationship
            # The span will be in the same trace but linked rather than nested
            span_context_manager = tracer.start_as_current_span(
                f"vcon_processing.{self.chain_details['name']}",
                links=[Link(parent_span_context)],
                attributes={
                    "vcon_id": self.vcon_id,
                    "chain_name": self.chain_details["name"],
                    "vcon.uuid": self.vcon_id
                }
            )
            
            logger.debug(
                f"Created linked span for vCon {self.vcon_id}: "
                f"linked_trace_id={format(trace_id, '032x')}, linked_span_id={format(span_id, '016x')}"
            )
            
            return span_context_manager
        except Exception as e:
            logger.warning(f"Failed to create span from context for vCon {self.vcon_id}: {e}")
            return None

    def _wrap_up(self) -> None:
        """Handle post-processing operations for the vCon.

        Manages egress queue placement and storage operations after
        chain processing is complete. Storage operations can run in parallel
        when CONSERVER_PARALLEL_STORAGE is enabled.
        """
        egress_lists = self.chain_details.get("egress_lists", [])
        if egress_lists:
            logger.info(
                "Forwarding vCon %s to egress lists: %s",
                self.vcon_id,
                ", ".join(egress_lists)
            )
            # Extract current trace context to propagate to next chain
            context = extract_otel_trace_context()
            for egress_list in egress_lists:
                # Store context BEFORE adding to egress list to avoid race condition
                # The conserver might pick up the vCon before context is stored
                if context:
                    store_context_sync(r, egress_list, self.vcon_id, context)
                r.lpush(egress_list, self.vcon_id)

        storage_backends = self.chain_details.get("storages", [])
        if storage_backends:
            logger.info(
                "Saving vCon %s to storage backends: %s",
                self.vcon_id,
                ", ".join(storage_backends)
            )
            
            if is_parallel_storage_enabled() and len(storage_backends) > 1:
                # Parallel storage writes using ThreadPoolExecutor
                self._process_storage_parallel(storage_backends)
            else:
                # Sequential storage writes (original behavior)
                for storage_name in storage_backends:
                    self._process_storage(storage_name)

        logger.info(
            "Completed chain %s processing for vCon: %s",
            self.chain_details["name"],
            self.vcon_id,
        )

    def _process_storage(self, storage_name: str) -> None:
        """Save vCon to a specified storage backend.

        Args:
            storage_name: Name of the storage backend to use
        """
        # Create a span for this storage operation - automatically inherits parent span context
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            f"storage.{storage_name}",
            attributes={
                "vcon_id": self.vcon_id,
                "storage_name": storage_name,
                "chain_name": self.chain_details["name"]
            }
        ):
            try:
                logger.debug("Saving vCon %s to storage %s", self.vcon_id, storage_name)
                Storage(storage_name).save(self.vcon_id)
            except Exception as e:
                # Record exception in the span
                current_span = trace.get_current_span()
                if current_span:
                    current_span.set_status(Status(StatusCode.ERROR, str(e)))
                    current_span.record_exception(e)
                logger.error(
                    "Failed to save vCon %s to storage %s: %s",
                    self.vcon_id,
                    storage_name,
                    str(e),
                    exc_info=True
                )

    def _process_storage_parallel(self, storage_backends: List[str]) -> None:
        """Save vCon to multiple storage backends concurrently.
        
        Uses ThreadPoolExecutor to write to all storage backends in parallel,
        which significantly improves throughput when multiple I/O-bound storage
        operations are configured (e.g., S3 + MongoDB + PostgreSQL).

        Args:
            storage_backends: List of storage backend names to write to
        """
        storage_started = time.time()
        logger.debug(
            "Starting parallel storage writes for vCon %s to %d backends",
            self.vcon_id,
            len(storage_backends)
        )
        
        with ThreadPoolExecutor(max_workers=len(storage_backends)) as executor:
            # Submit all storage operations concurrently
            future_to_storage = {
                executor.submit(self._process_storage, storage_name): storage_name
                for storage_name in storage_backends
            }
            
            # Wait for all operations to complete and handle results
            for future in as_completed(future_to_storage):
                storage_name = future_to_storage[future]
                try:
                    future.result()
                except Exception as e:
                    # Error already logged in _process_storage, but log again for parallel context
                    logger.error(
                        "Parallel storage operation failed for %s on vCon %s: %s",
                        storage_name,
                        self.vcon_id,
                        str(e)
                    )
        
        storage_time = round(time.time() - storage_started, 3)
        logger.info(
            "Completed parallel storage writes for vCon %s in %s seconds (%d backends)",
            self.vcon_id,
            storage_time,
            len(storage_backends),
            extra={
                "parallel_storage_time": storage_time,
                "storage_backend_count": len(storage_backends)
            }
        )

    def _process_tracers(self, in_vcon_uuid, out_vcon_uuid, links: list[str], link_index: int) -> bool:
        if "tracers" in config:
            for tracer_name in config["tracers"]:
                tracer = config["tracers"][tracer_name]
                tracer_options = tracer.get("options")
                try:
                    tracer_started = time.time()
                    logger.info("Processing tracer %s for vCon: %s", tracer_name, self.vcon_id)
                    tracer_module_name = tracer["module"]
                    if tracer_module_name not in imported_modules:
                        logger.debug("Importing module %s for tracer %s", tracer_module_name, tracer_name)
                        tracer_pip_name = tracer.get("pip_name")  # Optional pip package name from config
                        imported_modules[tracer_module_name] = import_or_install(tracer_module_name, tracer_pip_name)
                    tracer_module = imported_modules[tracer_module_name]
                    tracer_module.run(in_vcon_uuid, out_vcon_uuid, tracer_name, links, link_index, tracer_options)
                    tracer_processing_time = round(time.time() - tracer_started, 3)
                    logger.info(
                        "Completed tracer %s (module: %s) for vCon: %s in %s seconds",
                        tracer_name,
                        tracer_module_name,
                        out_vcon_uuid,
                        tracer_processing_time,
                        extra={
                            "tracer_processing_time": tracer_processing_time,
                            "tracer_name": tracer_name,
                            "tracer_module_name": tracer_module_name
                        }
                    )
                except Exception as e:
                    logger.error(
                        "Error in tracer %s (module: %s) for vCon %s: %s",
                        tracer_name,
                        tracer_module_name,
                        out_vcon_uuid,
                        str(e),
                        exc_info=True
                    )
                    if "dlq_vcon_on_error" in tracer_options and tracer_options["dlq_vcon_on_error"]:
                        raise

    def _process_link(self, links: list[str], link_index: int) -> bool:
        """Process a single link in the chain.

        Args:
            links: The list of links that can be run
            link_index: Which link to run

        Returns:
            bool: Whether the chain should continue processing
        """
        link_name = links[link_index]
        logger.info("Processing link %s for vCon: %s", link_name, self.vcon_id)
        link = config["links"][link_name]
# Create a span for this link - automatically inherits parent span context
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            f"link.{link_name}",
            attributes={
                "vcon_id": self.vcon_id,
                "link_name": link_name,
                "link_index": link_index,
                "chain_name": self.chain_details["name"]
            }
        ):
            module_name = link["module"]
            if module_name not in imported_modules:
                logger.debug("Importing module %s for link %s", module_name, link_name)
                pip_name = link.get("pip_name")  # Optional pip package name from config
                imported_modules[module_name] = import_or_install(module_name, pip_name)
            module = imported_modules[module_name]
            options = link.get("options")

            try:
                if link_index == 0:
                    self._process_tracers(self.vcon_id, self.vcon_id, links, -1)
                started = time.time()
                should_continue_chain = module.run(self.vcon_id, link_name, options)
                link_processing_time = round(time.time() - started, 3)
                logger.info(
                    "Completed link %s (module: %s) for vCon: %s in %s seconds",
                    link_name,
                    module_name,
                    self.vcon_id,
                    link_processing_time,
                    extra={
                        "link_processing_time": link_processing_time,
                        "link_name": link_name,
                        "module_name": module_name
                    }
                )
                if should_continue_chain:
                    self._process_tracers(should_continue_chain, self.vcon_id, links, link_index)
                else:
                    self._process_tracers(self.vcon_id, self.vcon_id, links, link_index)
                return should_continue_chain
            except Exception as e:
                # Record exception in the span
                current_span = trace.get_current_span()
                if current_span:
                    current_span.set_status(Status(StatusCode.ERROR, str(e)))
                    current_span.record_exception(e)
                logger.error(
                    "Error in link %s (module: %s) for vCon %s: %s",
                    link_name,
                    module_name,
                    self.vcon_id,
                    str(e),
                    exc_info=True
                )
                raise


def get_ingress_chain_map() -> IngressChainMap:
    """Build a mapping of ingress lists to their chain configurations.

    Returns:
        Dict mapping ingress list names to their chain configurations
    """
    chains = config.get("chains", {})
    ingress_details = {}
    for chain_name, chain_config in chains.items():
        for ingress_list in chain_config.get("ingress_lists", []):
            ingress_details[ingress_list] = {"name": chain_name, **chain_config}
    return ingress_details


def log_llen(list_name: str) -> None:
    """Log the current length of a Redis list.

    Args:
        list_name: Name of the Redis list to check
    """
    llen = r.llen(list_name)
    logger.info(
        "Queue status: %s has %s pending items",
        list_name,
        llen,
        extra={"queue_length": llen, "queue_name": list_name},
    )


def worker_loop(worker_id: int) -> None:
    """Worker process main loop for vCon processing.
    
    Each worker independently polls Redis queues and processes vCons.
    Multiple workers can run concurrently, with Redis BLPOP providing
    atomic distribution of work items.
    
    Module imports are done here (rather than in main()) to reduce memory
    when using 'spawn' start method, as each worker only loads what it needs.

    Args:
        worker_id: Unique identifier for this worker (1-based)
    """
    global config, shutdown_requested, r, imported_modules
    
    # Initialize error tracking in this worker process
    init_error_tracker()
    
    # Re-initialize Redis client in worker process
    r = redis_mgr.get_client()
    
    # Re-register signal handler in worker process
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    worker_name = f"Worker-{worker_id}"
    logger.info("%s started (PID %s)", worker_name, os.getpid())
    
    # Load config-specified modules in this worker process
    # This defers heavy imports until worker starts, reducing memory with 'spawn'
    config = get_config()
    imports = config.get("imports", {})
    if imports:
        logger.info("[%s] Loading %d required modules", worker_name, len(imports))
        for import_name, import_config in imports.items():
            try:
                # Support both old string format and new dict format
                if isinstance(import_config, str):
                    module_name = import_config
                    pip_name = None
                else:
                    module_name = import_config["module"]
                    pip_name = import_config.get("pip_name")
                
                if module_name not in imported_modules:
                    imported_modules[module_name] = import_or_install(module_name, pip_name)
                    logger.debug("[%s] Imported module %s", worker_name, module_name)
            except Exception as e:
                logger.error(
                    "[%s] Failed to import module %s: %s",
                    worker_name,
                    module_name,
                    str(e),
                    exc_info=True
                )
                raise
    
    while not shutdown_requested:
        # Refresh configuration on each iteration
        config = get_config()
        logger.debug("[%s] Refreshed configuration", worker_name)
        
        ingress_chain_map = get_ingress_chain_map()
        all_ingress_lists = list(ingress_chain_map.keys())
        logger.debug("[%s] Monitoring ingress lists: %s", worker_name, all_ingress_lists)
        
        logger.debug("[%s] Waiting for vCon on ingress lists (timeout: 15s)", worker_name)
        popped_item = r.blpop(all_ingress_lists, timeout=15)
        if not popped_item:
            if shutdown_requested:
                logger.info("[%s] Shutdown requested, exiting", worker_name)
                break
            logger.debug("[%s] No items received within timeout period", worker_name)
            continue

        ingress_list, vcon_id = popped_item
        logger.debug("[%s] Received vCon %s from ingress list %s", worker_name, vcon_id, ingress_list)
        
        if shutdown_requested:
            logger.info(
                "[%s] Shutdown requested, returning vCon %s to queue %s",
                worker_name,
                vcon_id,
                ingress_list
            )
            r.lpush(ingress_list, vcon_id)
            break

        # Retrieve context data if available
        context = retrieve_context(r, ingress_list, vcon_id)
        if context:
            logger.debug(
                "[%s] Retrieved context for vCon %s from ingress list %s: %s",
                worker_name,
                vcon_id,
                ingress_list,
                context
            )
        else:
            logger.debug("[%s] No context found for vCon %s from ingress list %s", worker_name, vcon_id, ingress_list)

        log_llen(ingress_list)
        chain_details = ingress_chain_map[ingress_list]
        logger.debug(
            "[%s] Processing vCon %s with chain configuration: %s",
            worker_name,
            vcon_id,
            {
                "chain_name": chain_details["name"],
                "links": chain_details.get("links", []),
                "storages": chain_details.get("storages", []),
                "egress_lists": chain_details.get("egress_lists", []),
                "timeout": chain_details.get("timeout")
            }
        )
        
        vcon_chain_request = VconChainRequest(chain_details, vcon_id, context)
        try:
            vcon_chain_request.process()
        except Exception as e:
            logger.error(
                "[%s] Critical error processing vCon %s: %s - Moving to DLQ",
                worker_name,
                vcon_id,
                str(e),
                exc_info=True
            )
            dlq_name = get_ingress_list_dlq_name(ingress_list)
            logger.info("[%s] Moving vCon %s to DLQ: %s", worker_name, vcon_id, dlq_name)
            logger.debug(
                "[%s] DLQ details for vCon %s: original_queue=%s, dlq=%s, error=%s",
                worker_name,
                vcon_id,
                ingress_list,
                dlq_name,
                str(e)
            )
            r.lpush(dlq_name, vcon_id)
            
            # Extend vCon TTL to ensure it persists while in DLQ for investigation
            # This prevents the vCon from expiring before operators can review it
            if VCON_DLQ_EXPIRY > 0:
                vcon_key = f"vcon:{vcon_id}"
                r.expire(vcon_key, VCON_DLQ_EXPIRY)
                logger.debug(
                    "[%s] Extended TTL on vCon %s to %ds for DLQ retention",
                    worker_name,
                    vcon_id,
                    VCON_DLQ_EXPIRY
                )
    
    logger.info("%s exiting", worker_name)


def main() -> None:
    """Main server entry point for vCon processing.

    Initializes the server and either runs the processing loop directly 
    (single worker) or spawns multiple worker processes (multi-worker mode)
    based on CONSERVER_WORKERS setting.
    
    Multi-worker mode enables parallel processing of vCons across multiple
    processes, improving throughput for I/O-bound workloads.
    
    Module imports are deferred to worker_loop() to reduce memory usage
    when using the 'spawn' start method.
    """
    global worker_processes
    
    # Print version information on startup
    version_info = get_version_info()
    logger.info(
        "Starting %s",
        get_version_string(),
        extra={"version_info": version_info}
    )
    logger.info(
        "Version: %s | Commit: %s | Built: %s",
        version_info["version"],
        version_info["git_commit"],
        version_info["build_time"]
    )
    
    worker_count = get_worker_count()
    parallel_storage = is_parallel_storage_enabled()
    start_method = get_start_method()
    
    # Configure multiprocessing start method if specified
    if start_method and worker_count > 1:
        try:
            multiprocessing.set_start_method(start_method, force=True)
            logger.info("Multiprocessing start method set to: %s", start_method)
        except RuntimeError as e:
            logger.warning(
                "Could not set start method to %s (may already be set): %s",
                start_method,
                str(e)
            )
    
    current_start_method = multiprocessing.get_start_method()
    logger.info(
        "Worker configuration: workers=%d, parallel_storage=%s, start_method=%s",
        worker_count,
        parallel_storage,
        current_start_method
    )
    
    logger.info("Initializing vCon server")
    global config
    config = get_config()
    logger.debug(
        "Loaded initial configuration: %s",
        {k: v for k, v in config.items() if k not in ['links', 'chains']}
    )

    follower.start_followers()
    
    if worker_count > 1:
        # Multi-worker mode: spawn worker processes
        logger.info("Starting %d worker processes", worker_count)
        
        for i in range(worker_count):
            worker_id = i + 1
            process = multiprocessing.Process(
                target=worker_loop,
                args=(worker_id,),
                name=f"vcon-worker-{worker_id}"
            )
            process.start()
            worker_processes.append(process)
            logger.info("Started Worker-%d (PID %s)", worker_id, process.pid)
        
        logger.info("All %d workers started, main process monitoring", worker_count)
        
        # Main process waits for all workers to complete
        try:
            while not shutdown_requested:
                # Check worker health periodically
                time.sleep(5)
                
                for i, process in enumerate(worker_processes):
                    if not process.is_alive() and not shutdown_requested:
                        worker_id = i + 1
                        logger.warning(
                            "Worker-%d (PID %s) died unexpectedly, restarting",
                            worker_id,
                            process.pid
                        )
                        # Restart the worker
                        new_process = multiprocessing.Process(
                            target=worker_loop,
                            args=(worker_id,),
                            name=f"vcon-worker-{worker_id}"
                        )
                        new_process.start()
                        worker_processes[i] = new_process
                        logger.info("Restarted Worker-%d (new PID %s)", worker_id, new_process.pid)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down workers")
            signal_handler(signal.SIGINT, None)
        
        # Wait for all workers to finish
        logger.info("Waiting for workers to finish...")
        for process in worker_processes:
            process.join(timeout=30)
            if process.is_alive():
                logger.warning("Worker %s did not exit gracefully, terminating", process.name)
                process.terminate()
                process.join(timeout=5)
        
        logger.info("All workers stopped")
    else:
        # Single-worker mode: run directly in main process
        logger.info("Server initialization complete, starting main processing loop (single worker)")
        worker_loop(1)


if __name__ == "__main__":
    main()
