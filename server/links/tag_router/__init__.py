import json
from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
from redis_mgr import redis

logger = init_logger(__name__)

default_options = {
    # Dictionary mapping tags to target Redis lists (OR logic: route if vcon has any of these tags)
    # e.g., {"important": "important_vcons", "urgent": "urgent_vcons"}
    "tag_routes": {},
    # Optional: list of rules that require ALL listed tags (AND logic). Each rule: {"tags": [...], "target_list": "list_name"}
    # Tags can be name only (e.g. "category") or full "name:value" (e.g. "category:action") for exact match.
    # e.g., [{"tags": ["tag1:value1", "tag2:value2"], "target_list": "target_ingress"}]
    "tag_route_rules": [],
    # Whether to continue normal processing after routing
    "forward_original": True,
}

def run(vcon_uuid, link_name, opts=default_options):
    """Tag Router link that routes vCons to different Redis lists based on tags in attachments.
    
    Supports two routing modes:
    - tag_routes: OR logic — route if the vcon has any of the mapped tags.
    - tag_route_rules: AND logic — route only when the vcon has ALL tags in a rule's "tags" list.
    
    Tags in config can be name-only (e.g. "category") or full "name:value" (e.g. "category:action")
    for exact match. A name-only key matches any tag with that name; a full "name:value" key matches only that exact tag.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance
        opts: Link options containing:
            tag_routes: Dict mapping tag name or "name:value" to target Redis lists (OR logic)
            tag_route_rules: List of {"tags": [...], "target_list": "..."} for AND logic
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

    # Check if there are any tag routes or rules configured
    has_tag_routes = bool(opts.get("tag_routes"))
    has_route_rules = bool(opts.get("tag_route_rules"))
    if not has_tag_routes and not has_route_rules:
        logger.warning(f"No tag routes configured for {link_name}, skipping")
        return vcon_uuid

    # Build tags list and match_set: tag names (name-only match) and full "name:value" (exact match).
    # So "tag1:value1" adds both "tag1" and "tag1:value1"; config can use either.
    # Body may be list/dict or a JSON string after storage round-trip.
    tags = []
    match_set = set()
    for attachment in vcon.attachments:
        if attachment.get("type") != "tags" or "body" not in attachment:
            continue
        body = attachment["body"]
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(body, list):
            for tag_str in body:
                if isinstance(tag_str, str) and ":" in tag_str:
                    tag_name = tag_str.split(":", 1)[0]
                    if tag_name:
                        tags.append(tag_name)
                        match_set.add(tag_name)
                        match_set.add(tag_str)
        elif isinstance(body, dict):
            for tag_name in body.keys():
                if tag_name:
                    tags.append(tag_name)
                    match_set.add(tag_name)
    
    if not tags:
        logger.debug(f"No tags found in vCon {vcon_uuid}")
        return vcon_uuid if opts.get("forward_original") else None

    routed = False

    # AND logic: route when vcon has ALL tags in a rule (each tag can be name or "name:value")
    for rule in opts.get("tag_route_rules") or []:
        raw_tags = rule.get("tags") or []
        required = {str(t).strip() for t in raw_tags if t}
        target_list = rule.get("target_list")
        if not required or not target_list:
            continue
        if required.issubset(match_set):
            logger.info(
                f"Routing vCon {vcon_uuid} to list '{target_list}' (has all required tags: {sorted(required)})"
            )
            redis.rpush(target_list, str(vcon_uuid))
            routed = True

    # OR logic: route when vcon's match_set contains a key from tag_routes (key can be name or "name:value")
    for route_key, target_list in opts["tag_routes"].items():
        if route_key in match_set:
            logger.info(f"Routing vCon {vcon_uuid} to list '{target_list}' based on tag '{route_key}'")
            redis.rpush(target_list, str(vcon_uuid))
            routed = True
        else:
            logger.debug(f"No match for route key '{route_key}'")
    
    if routed:
        logger.info(f"Successfully routed vCon {vcon_uuid} based on tags")
    else:
        logger.info(f"No applicable routes found for vCon {vcon_uuid}")
        logger.debug(
            f"vCon {vcon_uuid} match_set (tags found): {sorted(match_set)}; "
            f"tag_route_rules count: {len(opts.get('tag_route_rules') or [])}"
        )
    
    # Return based on forward_original setting
    return vcon_uuid if opts.get("forward_original") else None
