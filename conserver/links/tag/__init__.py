from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "tags": ["iron", "maiden"],
}

def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    logger.debug("Starting tag::run")

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)
    tags = opts.get("tags", [])
    if isinstance(tags, dict):
        # dict-form options: {name: value} (CON-737)
        pairs = list(tags.items())
    else:
        # list-form options: "name:value" strings, or bare names.
        pairs = []
        for tag in tags:
            if isinstance(tag, str) and ":" in tag:
                name, value = tag.split(":", 1)
            else:
                name = value = tag
            pairs.append((name, value))
    for name, value in pairs:
        vCon.add_tag(tag_name=name, tag_value=value)
    vcon_redis.store_vcon(vCon)

    # Return the vcon_uuid down the chain.
    # If you want the vCon processing to stop (if you are filtering them, for instance)
    # send None
    return vcon_uuid
