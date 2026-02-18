from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

import requests

logger = init_logger(__name__)

default_options = {
    "webhook-urls": [],
    "headers": {},
}


def save(vcon_uuid, opts=default_options):
    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    json_dict = vCon.to_dict()

    if json_dict.get("vcon") == "0.0.1" or "vcon" not in json_dict:
        json_dict["vcon"] = "0.3.0"

    headers = opts.get("headers", {})

    webhook_urls = opts.get("webhook-urls", [])
    if not webhook_urls:
        logger.warning(
            f"webhook storage: no webhook-urls configured for vcon {vcon_uuid}, skipping"
        )
        return

    for url in webhook_urls:
        logger.info(
            f"webhook storage: posting vcon {vcon_uuid} to webhook url: {url}"
        )
        resp = requests.post(url, json=json_dict, headers=headers)
        logger.info(
            f"webhook storage response for {vcon_uuid}: {resp.status_code} {resp.text}"
        )
