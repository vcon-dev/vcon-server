import redis_mgr
from lib.logging_utils import init_logger
from lib.metrics import init_metrics
from lib.error_tracking import init_error_tracker
from config import Configuration
import requests
import threading
import time
from fastapi import FastAPI

app = FastAPI()
config: dict | None = None

init_error_tracker()
init_metrics()
logger = init_logger(__name__)
imported_modules = {}

r = redis_mgr.get_client()

def flush_egress(follower):
    # Estimate the rate of flushing the egress list
    # to be something like a Nyquist frequency
    if follower["flushing_rate"]:
        time.sleep(follower["flushing_rate"])
    else:
        time.sleep(follower["pulling_interval"] / 2)
    endpoint = (
        follower["url"]
        + "/vcon/egress?egress_list="
        + follower["egress_list"]
        + "&limit=" 
        + str(follower["fetch_vcon_limit"])
    ) 
    headers = {
        "Content-Type": "application/json",
        "x-conserver-api-token": follower["auth_token"],
    }
    while True:
        response = requests.request("GET", endpoint, headers=headers)
        vcon_uuids = response.json()
        if not vcon_uuids:
            break
        print(f"Flushing egress list of vcons: {len(vcon_uuids)}")
        time.sleep(5)

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
        "x-conserver-api-token": follower["auth_token"],
    }
    response = requests.request("GET", endpoint, headers=headers)
    vcons_to_process = response.json()
    logger.info(f"VCONs to process: {len(vcons_to_process)}")

    if not vcons_to_process:
        return

    for vcon_id in vcons_to_process:
        endpoint = follower["url"] + "/vcon/" + vcon_id
        headers = {
            "Content-Type": "application/json",
            "x-conserver-api-token": follower["auth_token"],
        }
        response = requests.request("GET", endpoint, headers=headers)
        if response.status_code == 404:
            logger.error(f"Failed to get VCON: {vcon_id}")
            logger.error(response.json())
            continue
        vcon = response.json()
        redis_mgr.set_key(f"vcon:{vcon_id}", vcon)
        r.lpush(follower["follower_ingress_list"], vcon_id)


def repeat_function(interval, function, follower):
    follower_function(follower)
    threading.Timer(interval, repeat_function, [interval, function, follower]).start()


def start_followers():
    logger.info("Starting follower loop")
    global config
    config = Configuration.get_followers()

    for follower_name, follower in config.items():
        logger.info("Follower: ", follower)
        
        # If the flush_first flag is set, make sure you flush the 
        # vCons ids from the egress redist list
        if follower.get("flush_first", False):
            logger.info("Flushing egress list of vcons")
            flush_egress(follower)
            
        repeat_function(follower["pulling_interval"], follower_function, follower)


app.router.add_event_handler("startup", start_followers)