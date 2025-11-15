"""Main server module for vCon processing.

This module handles the core vCon processing pipeline, including chain management,
link processing, and storage operations. It implements a Redis-based queue system
for processing vCons through configured processing chains.
"""

import importlib
import logging
import signal
import subprocess
import sys
import time
from typing import Dict, List, Optional, TypedDict

import follower
import redis_mgr

from config import get_config
from dlq_utils import get_ingress_list_dlq_name
from lib.context_utils import retrieve_context
from lib.error_tracking import init_error_tracker
from lib.metrics import record_histogram, increment_counter
from storage.base import Storage

# OpenTelemetry trace context propagation
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, SpanContext, TraceFlags, NonRecordingSpan

logger = logging.getLogger("main")
shutdown_requested = False


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
    """Handle SIGTERM signal for graceful shutdown.
    
    Args:
        signum: Signal number
        frame: Current stack frame (unused)
    """
    logger.info("SIGTERM received, initiating graceful shutdown...")
    global shutdown_requested
    shutdown_requested = True


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


# Register the signal handler for SIGTERM
signal.signal(signal.SIGTERM, signal_handler)

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
        """Create a new span from propagated trace context (POC).
        
        This demonstrates how to create a span from the context retrieved
        from Redis, allowing trace propagation through the processing pipeline.
        
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
            
            # Create a new span as a child of the propagated context
            # Use NonRecordingSpan to represent the remote parent span context
            # This allows OpenTelemetry to link the new span to the parent trace
            parent_span = NonRecordingSpan(parent_span_context)
            parent_context = trace.set_span_in_context(parent_span)
            
            # Use start_as_current_span with the parent context
            # This will create a child span linked to the parent trace
            span_context_manager = tracer.start_as_current_span(
                f"vcon_processing.{self.chain_details['name']}",
                context=parent_context,
                attributes={
                    "vcon_id": self.vcon_id,
                    "chain_name": self.chain_details["name"],
                    "vcon.uuid": self.vcon_id
                }
            )
            
            logger.debug(
                f"Created span context manager for vCon {self.vcon_id}: "
                f"parent_trace_id={format(trace_id, '032x')}, parent_span_id={format(span_id, '016x')}"
            )
            
            return span_context_manager
        except Exception as e:
            logger.warning(f"Failed to create span from context for vCon {self.vcon_id}: {e}")
            return None

    def _wrap_up(self) -> None:
        """Handle post-processing operations for the vCon.

        Manages egress queue placement and storage operations after
        chain processing is complete.
        """
        egress_lists = self.chain_details.get("egress_lists", [])
        if egress_lists:
            logger.info(
                "Forwarding vCon %s to egress lists: %s",
                self.vcon_id,
                ", ".join(egress_lists)
            )
            for egress_list in egress_lists:
                r.lpush(egress_list, self.vcon_id)

        storage_backends = self.chain_details.get("storages", [])
        if storage_backends:
            logger.info(
                "Saving vCon %s to storage backends: %s",
                self.vcon_id,
                ", ".join(storage_backends)
            )
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
        try:
            logger.debug("Saving vCon %s to storage %s", self.vcon_id, storage_name)
            Storage(storage_name).save(self.vcon_id)
        except Exception as e:
            logger.error(
                "Failed to save vCon %s to storage %s: %s",
                self.vcon_id,
                storage_name,
                str(e),
                exc_info=True
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


def main() -> None:
    """Main server loop for vCon processing.

    Initializes the server, imports required modules, and runs the main
    processing loop that pulls vCons from ingress queues and processes
    them through their configured chains.
    """
    logger.info("Initializing vCon server")
    global config
    config = get_config()
    logger.debug(
        "Loaded initial configuration: %s",
        {k: v for k, v in config.items() if k not in ['links', 'chains']}
    )
    
    logger.info("Loading required modules")
    imports = config.get("imports", {})
    logger.debug("Modules to import: %s", list(imports.keys()))
    for import_name, import_config in imports.items():
        try:
            # Support both old string format and new dict format
            if isinstance(import_config, str):
                # Old format: imports: { module_name: "module_path" }
                module_name = import_config
                pip_name = None
                logger.info("Importing module %s (legacy format)", module_name)
            else:
                # New format: imports: { import_name: { module: "module_name", pip_name: "package" } }
                module_name = import_config["module"]
                pip_name = import_config.get("pip_name")
                logger.info("Importing module %s for import %s", module_name, import_name)
            
            imported_modules[module_name] = import_or_install(module_name, pip_name)
            logger.debug("Successfully imported module %s", module_name)
        except Exception as e:
            logger.error(
                "Failed to import module %s for import %s: %s",
                module_name,
                import_name,
                str(e),
                exc_info=True
            )
            raise

    follower.start_followers()
    logger.info("Server initialization complete, starting main processing loop")
   
    while not shutdown_requested:
        # Refresh configuration on each iteration
        config = get_config()
        logger.debug("Refreshed configuration, checking for changes")
        
        ingress_chain_map = get_ingress_chain_map()
        all_ingress_lists = list(ingress_chain_map.keys())
        logger.debug("Monitoring ingress lists: %s", all_ingress_lists)
        
        logger.debug("Waiting for vCon on ingress lists (timeout: 15s)")
        popped_item = r.blpop(all_ingress_lists, timeout=15)
        if not popped_item:
            if shutdown_requested:
                logger.info("Shutdown requested, exiting main loop")
                break
            logger.debug("No items received within timeout period")
            continue

        ingress_list, vcon_id = popped_item
        logger.debug("Received vCon %s from ingress list %s", vcon_id, ingress_list)
        
        if shutdown_requested:
            logger.info(
                "Shutdown requested, returning vCon %s to queue %s",
                vcon_id,
                ingress_list
            )
            r.lpush(ingress_list, vcon_id)
            break

        # Retrieve context data if available
        context = retrieve_context(r, ingress_list, vcon_id)
        if context:
            logger.debug(
                "Retrieved context for vCon %s from ingress list %s: %s",
                vcon_id,
                ingress_list,
                context
            )
        else:
            logger.debug("No context found for vCon %s from ingress list %s", vcon_id, ingress_list)

        log_llen(ingress_list)
        chain_details = ingress_chain_map[ingress_list]
        logger.debug(
            "Processing vCon %s with chain configuration: %s",
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
                "Critical error processing vCon %s: %s - Moving to DLQ",
                vcon_id,
                str(e),
                exc_info=True
            )
            dlq_name = get_ingress_list_dlq_name(ingress_list)
            logger.info("Moving vCon %s to DLQ: %s", vcon_id, dlq_name)
            logger.debug(
                "DLQ details for vCon %s: original_queue=%s, dlq=%s, error=%s",
                vcon_id,
                ingress_list,
                dlq_name,
                str(e)
            )
            r.lpush(dlq_name, vcon_id)


if __name__ == "__main__":
    main()
