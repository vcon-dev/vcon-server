from lib.logging_utils import init_logger
from lib.queue import VconQueue

logger = init_logger(__name__)

default_options = {"seconds": 60 * 60 * 24}


def run(vcon_uuid, link_name, opts=default_options):
    logger.debug("Starting expire_vcon::run")
    VconQueue().set_vcon_ttl(vcon_uuid, opts["seconds"])
    logger.info(f"expire_vcon plugin: set expire for {vcon_uuid}")
    return vcon_uuid
