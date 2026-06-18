from lib.logging_utils import init_logger
import time

logger = init_logger(__name__)

AUDIT_META = {
    "third_party_service": "internal",
    "policy_url": None,
    "data_type": "none",
    "transformation": "Delayed chain processing by sleeping (test fixture)",
    "transformation_opts_key": "seconds",
    "safe_opts_keys": ["seconds"],
}

# Default: sleep 5 seconds. This link is a test fixture used to widen the
# per-vCon processing window so concurrent worker behaviour (see
# CONSERVER_VCON_CONCURRENCY) can be observed during QA.
default_options = {"seconds": 5}


def run(vcon_uuid, link_name, opts=default_options):
    """Sleep for ``opts["seconds"]`` then pass the vCon through unchanged.

    Purely a testing aid: it makes a chain take a predictable amount of wall
    time so parallel/concurrent processing can be exercised. The vCon itself
    is never read or modified. Returns ``vcon_uuid`` so the chain continues.
    """
    merged_opts = default_options.copy()
    merged_opts.update(opts or {})

    seconds = merged_opts["seconds"]
    if seconds < 0:
        logger.warning(
            "delay link '%s': negative seconds (%s) for vCon %s — clamping to 0",
            link_name,
            seconds,
            vcon_uuid,
        )
        seconds = 0

    logger.info(
        "delay link '%s': sleeping %ss for vCon %s", link_name, seconds, vcon_uuid
    )
    time.sleep(seconds)
    logger.info(
        "delay link '%s': resumed after %ss for vCon %s", link_name, seconds, vcon_uuid
    )
    return vcon_uuid
