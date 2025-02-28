from server.lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger

import requests

logger = init_logger(__name__)

default_options = {
    "webhook-urls": ["https://eo91qivu6evxsty.m.pipedream.net"],
    "auth_header": "Bearer ThompsonsClamBar",
    "api_token": "default-api-token",
}


def run(
    vcon_uuid,
    link_name,
    opts=default_options,
):
    logger.debug("Starting transcribe::run")

    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    # The webhook needs a stringified JSON version.
    json_dict = vCon.to_dict()

    # Post this to each webhook url
    for url in opts["webhook-urls"]:
        logger.info(
            f"webhook plugin: posting vcon {vcon_uuid} to webhook url: {url}"
        )
        headers = {
            "Authorization": opts.get("auth_header"),
            "x-conserver-api-token": opts.get("api_token"),
        }
        resp = requests.post(url, json=json_dict, headers=headers)
        logger.info(
            f"webhook plugin response for {vcon_uuid}: {resp.status_code} {resp.text}"
        )
    # Return the vcon_uuid down the chain.
    # If you want the vCon processing to stop (if you are filtering them, for instance)
    # send None
    return vcon_uuid
