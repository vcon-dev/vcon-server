from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
import jq

logger = init_logger(__name__)

default_options = {
    # jq filter expression to evaluate
    "filter": ".",
    # if True, forward vCons that match the filter
    # if False, forward vCons that don't match the filter
    "forward_matches": True,
}

def run(vcon_uuid, link_name, opts=default_options):
    """JQ Filter link that uses jq expressions to filter vCons.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance
        opts: Link options containing:
            filter: jq filter expression to evaluate
            forward_matches: If True, forward matching vCons, if False forward non-matching ones
            
    Returns:
        vcon_uuid if the vCon should be forwarded, None if it should be filtered out
    """
    logger.debug(f"Starting {__name__}::run")

    # Merge options
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    # Get the vCon
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    if not vcon:
        logger.error(f"Could not find vCon {vcon_uuid}")
        return None

    # Convert vCon to dict for jq
    vcon_dict = vcon.to_dict()

    try:
        # Apply the jq filter
        # Compile and run the jq program
        logger.debug(f"Applying jq filter '{opts['filter']}' to vCon {vcon_uuid}")
        program = jq.compile(opts["filter"])
        results = list(program.input(vcon_dict))
        
        # Handle empty results
        if not results:
            logger.debug(f"JQ filter returned no results for vCon {vcon_uuid}")
            matches = False
        else:
            matches = bool(results[0])
            
        logger.debug(f"JQ filter results: {results}")
    except Exception as e:
        logger.error(f"Error applying jq filter '{opts['filter']}' to vCon {vcon_uuid}: {e}")
        logger.debug(f"vCon content: {vcon_dict}")
        return None

    # Forward based on matches and forward_matches setting
    should_forward = matches == opts["forward_matches"]
    
    if should_forward:
        logger.info(f"vCon {vcon_uuid} {'' if matches else 'did not '}match filter - forwarding")
        return vcon_uuid
    else:
        logger.info(f"vCon {vcon_uuid} {'' if matches else 'did not '}match filter - filtering out")
        return None