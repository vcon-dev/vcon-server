from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
from lib.metrics import increment_counter
import jq

logger = init_logger(__name__)

default_options = {
    # jq filter expression to evaluate
    "filter": ".",
    # if True, forward vCons that match the filter
    # if False, forward vCons that don't match the filter
    "forward_matches": True,
}


def _filter_body_arrays_to_strings(value):
    """Drop non-string items from ``body`` arrays for string-based jq filters.

    Legacy vCons can still carry mixed-type attachment/analysis bodies. jq
    string functions like ``startswith()`` raise when they hit an int/dict in
    ``.body[]``. For those cases, retrying with string-only body arrays preserves
    the common "scan tags in body" use case without changing the first-pass
    semantics for valid filters.
    """
    if isinstance(value, dict):
        sanitized = {}
        for key, child in value.items():
            if key == "body" and isinstance(child, list):
                sanitized[key] = [item for item in child if isinstance(item, str)]
            else:
                sanitized[key] = _filter_body_arrays_to_strings(child)
        return sanitized

    if isinstance(value, list):
        return [_filter_body_arrays_to_strings(item) for item in value]

    return value


def _is_string_input_type_error(error):
    return "requires string inputs" in str(error)

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
    attrs = {"link.name": link_name, "vcon.uuid": vcon_uuid}

    try:
        # Apply the jq filter
        # Compile and run the jq program
        logger.debug(f"Applying jq filter '{opts['filter']}' to vCon {vcon_uuid}")
        program = jq.compile(opts["filter"])
        try:
            results = list(program.input(vcon_dict))
        except Exception as runtime_error:
            if not _is_string_input_type_error(runtime_error):
                raise

            increment_counter("conserver.link.jq.string_body_array_retries", attributes=attrs)
            logger.warning(
                f"Retrying jq filter '{opts['filter']}' for vCon {vcon_uuid} "
                f"with string-only body arrays after type error: {runtime_error}"
            )
            results = list(program.input(_filter_body_arrays_to_strings(vcon_dict)))

        # Handle empty results
        if not results:
            logger.debug(f"JQ filter returned no results for vCon {vcon_uuid}")
            matches = False
        else:
            matches = bool(results[0])

        logger.debug(f"JQ filter results: {results}")
    except Exception as e:
        increment_counter("conserver.link.jq.filter_errors", attributes=attrs)
        logger.error(f"Error applying jq filter '{opts['filter']}' to vCon {vcon_uuid}: {e}")
        logger.debug(f"vCon content: {vcon_dict}")
        return None

    # Forward based on matches and forward_matches setting
    should_forward = matches == opts["forward_matches"]

    if should_forward:
        logger.info(f"vCon {vcon_uuid} {'' if matches else 'did not '}match filter - forwarding")
        return vcon_uuid
    else:
        increment_counter("conserver.link.jq.vcon_filtered_out", attributes=attrs)
        logger.info(f"vCon {vcon_uuid} {'' if matches else 'did not '}match filter - filtering out")
        return None
