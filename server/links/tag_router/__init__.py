from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
from redis_mgr import redis

logger = init_logger(__name__)

default_options = {
    # Dictionary mapping tags to target Redis lists
    # e.g., {"important": "important_vcons", "urgent": "urgent_vcons"}
    "tag_routes": {},
    # Whether to continue normal processing after routing
    "forward_original": True,
}

def run(vcon_uuid, link_name, opts=default_options):
    """Tag Router link that routes vCons to different Redis lists based on tags in attachments.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance
        opts: Link options containing:
            tag_routes: Dictionary mapping tags to target Redis lists
            forward_original: Whether to continue normal processing after routing
            
    Returns:
        vcon_uuid if the vCon should continue normal processing, None otherwise
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

    # Check if there are any tag routes configured
    if not opts.get("tag_routes"):
        logger.warning(f"No tag routes configured for {link_name}, skipping")
        return vcon_uuid

    # Extract all tags from attachments
    tags = []
    for attachment in vcon.attachments:
        # Handle only plural "tags" format
        if attachment['type'] == "tags" and 'body' in attachment:
            if isinstance(attachment['body'], list):
                # Process each tag string in the list
                for tag_str in attachment['body']:
                    if isinstance(tag_str, str) and ":" in tag_str:
                        # Split on first colon to get tag name
                        tag_name = tag_str.split(":", 1)[0]
                        if tag_name:
                            tags.append(tag_name)
            elif isinstance(attachment['body'], dict):
                # If body is a dict, use the keys as tags
                for tag_name in attachment['body'].keys():
                    if tag_name:
                        tags.append(tag_name)
    
    if not tags:
        logger.debug(f"No tags found in vCon {vcon_uuid}")
        return vcon_uuid if opts.get("forward_original") else None

    # Route the vCon to the appropriate Redis lists based on tags
    routed = False
    for tag in tags:
        if tag in opts["tag_routes"]:
            target_list = opts["tag_routes"][tag]
            logger.info(f"Routing vCon {vcon_uuid} to list '{target_list}' based on tag '{tag}'")
            # Push the vCon UUID to the target Redis list
            redis.rpush(target_list, str(vcon_uuid))
            routed = True
        else:
            logger.debug(f"No route configured for tag '{tag}'")
    
    if routed:
        logger.info(f"Successfully routed vCon {vcon_uuid} based on tags")
    else:
        logger.info(f"No applicable routes found for vCon {vcon_uuid}")
    
    # Return based on forward_original setting
    return vcon_uuid if opts.get("forward_original") else None
