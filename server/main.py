"""Main server module for vCon processing.

This module handles the core vCon processing pipeline, including chain management,
link processing, and storage operations. It implements a Redis-based queue system
for processing vCons through configured processing chains.
"""

import importlib
import logging
import signal
import time
from typing import Dict, List, Optional, TypedDict

import follower
import redis_mgr

from config import get_config
from dlq_utils import get_ingress_list_dlq_name
from lib.error_tracking import init_error_tracker
from lib.metrics import init_metrics, stats_count, stats_gauge
from storage.base import Storage

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


# Register the signal handler for SIGTERM
signal.signal(signal.SIGTERM, signal_handler)

init_error_tracker()
init_metrics()
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
    """

    def __init__(self, chain_details: ChainConfig, vcon_id: str) -> None:
        """Initialize a new vCon chain processing request.

        Args:
            chain_details: Configuration for the processing chain
            vcon_id: Unique identifier for the vCon
        """
        self.vcon_id = vcon_id
        self.chain_details = chain_details

    def process(self) -> None:
        """Process the vCon through all configured chain links.

        Executes each link in sequence, handles timing metrics, and manages
        the overall processing flow. Will stop processing if any link indicates
        the chain should not continue.
        """
        vcon_started = time.time()
        logger.info(
            "Started processing vCon %s with chain %s",
            self.vcon_id,
            self.chain_details["name"]
        )

        for link_name in self.chain_details["links"]:
            should_continue_chain = self._process_link(link_name)
            if not should_continue_chain:
                logger.info(
                    "Link %s halted chain processing for vCon %s",
                    link_name,
                    self.vcon_id,
                )
                break

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
        stats_gauge("conserver.main_loop.vcon_processing_time", vcon_processing_time)
        stats_count("conserver.main_loop.count_vcons_processed")

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

    def _process_link(self, link_name: str) -> bool:
        """Process a single link in the chain.

        Args:
            link_name: Name of the link to process

        Returns:
            bool: Whether the chain should continue processing
        """
        logger.info("Processing link %s for vCon: %s", link_name, self.vcon_id)
        link = config["links"][link_name]

        module_name = link["module"]
        if module_name not in imported_modules:
            logger.debug("Importing module %s for link %s", module_name, link_name)
            imported_modules[module_name] = importlib.import_module(module_name)
        module = imported_modules[module_name]
        options = link.get("options")
        
        started = time.time()
        try:
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
    for module_name, module_path in imports.items():
        try:
            logger.info("Importing module %s from %s", module_name, module_path)
            imported_modules[module_name] = importlib.import_module(module_path)
            logger.debug("Successfully imported module %s", module_name)
        except Exception as e:
            logger.error(
                "Failed to import module %s from %s: %s",
                module_name,
                module_path,
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
        
        vcon_chain_request = VconChainRequest(chain_details, vcon_id)
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
