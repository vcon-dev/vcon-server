import redis_mgr
from lib.logging_utils import init_logger
from lib.error_tracking import init_error_tracker
from config import Configuration
import requests
import threading
from fastapi import FastAPI

from server import settings

app = FastAPI()
config: dict | None = None

init_error_tracker()
logger = init_logger(__name__)
imported_modules = {}

r = redis_mgr.get_client()


def follower_function(follower):
    logger.info("Starting follower function")
    endpoint = (
        follower["url"]
        + "/vcon/egress?egress_list="
        + follower["egress_list"]
        + "&limit="
        + str(follower["fetch_vcon_limit"])
    )
    headers = {
        "Content-Type": "application/json",
        settings.CONSERVER_HEADER_NAME: follower["auth_token"],
    }
    response = requests.request("GET", endpoint, headers=headers)
    vcons_to_process = response.json()
    logger.info("VCONs to process: %s", vcons_to_process)

    if not vcons_to_process:
        return

    for vcon_id in vcons_to_process:
        endpoint = follower["url"] + "/vcon/" + vcon_id
        response = requests.request("GET", endpoint, headers=headers)
        if response.status_code == 404:
            logger.error("Failed to get VCON: %s", vcon_id)
            continue
        vcon = response.json()
        # logger.info("VCON ID: %s", vcon_id)
        # logger.info("VCON: %s", vcon)
        redis_mgr.set_key(f"vcon:{vcon_id}", vcon)
        r.lpush(follower["follower_ingress_list"], vcon_id)


def repeat_function(interval, function, follower):
    follower_function(follower)
    threading.Timer(interval, repeat_function, [interval, function, follower]).start()


def start_followers():
    logger.info("Starting follower loop")
    global config
    config = Configuration.get_followers()
    # ingress_chain_map = get_ingress_chain_map()
    # all_ingress_lists = list(ingress_chain_map.keys())

    for follower_name, follower in config.items():
        logger.info("Follower: ", follower)
        repeat_function(follower["pulling_interval"], follower_function, follower)


app.router.add_event_handler("startup", start_followers)
