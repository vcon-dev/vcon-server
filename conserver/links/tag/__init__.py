from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "tags": ["iron", "maiden"],
}


def _emit_tags(vCon, tags):
    """Apply tags to a vCon, supporting key:value tags as well as flat labels.

    Accepted shapes for `tags`:
      - dict:           {"source": "vkong", "pipeline": "vconic"}  -> name:value
      - list of dicts:  [{"source": "vkong"}, {"name": "x", "value": "y"}]
      - list of "k:v"/"k=v" strings: ["source:vkong"]              -> name:value
      - list of bare strings: ["vconic"]                            -> label (name==value)

    Previously every entry was written as add_tag(name=tag, value=tag), so a
    "source"/"vkong" tag was impossible (you only ever got "vconic:vconic").
    """
    def add(name, value):
        vCon.add_tag(tag_name=str(name), tag_value=str(value))

    if isinstance(tags, dict):
        for name, value in tags.items():
            add(name, value)
        return

    for tag in tags or []:
        if isinstance(tag, dict):
            if "name" in tag and "value" in tag:
                add(tag["name"], tag["value"])
            else:
                for name, value in tag.items():
                    add(name, value)
        elif isinstance(tag, str) and (":" in tag or "=" in tag):
            sep = ":" if ":" in tag else "="
            name, value = tag.split(sep, 1)
            add(name.strip(), value.strip())
        else:
            # Flat label, no explicit value: preserve legacy name==value behavior.
            add(tag, tag)


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    logger.debug("Starting tag::run")

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)
    _emit_tags(vCon, opts.get("tags", []))
    vcon_redis.store_vcon(vCon)

    # Return the vcon_uuid down the chain.
    # If you want the vCon processing to stop (if you are filtering them, for instance)
    # send None
    return vcon_uuid
