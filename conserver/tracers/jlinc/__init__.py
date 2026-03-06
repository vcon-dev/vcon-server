from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis
import hashlib
import requests
import json
import re

logger = init_logger(__name__)

default_options = {
    "data_store_api_url": "http://jlinc-server:9090",
    "data_store_api_key": "",
    "archive_api_url": "http://jlinc-server:9090",
    "archive_api_key": "",
    "system_prefix": "VCONTest",
    "agreement_id": "00000000-0000-0000-0000-000000000000",
    "hash_event_data": True,
    "dlq_vcon_on_error": False,
}

domain = ""
system_short_name = ""
entities = []

def _sanitize(input):
    return re.sub(r'[^a-zA-Z0-9._-]', '_', input.lower())

def run(
    in_vcon_uuid,
    out_vcon_uuid,
    tracer_name,
    links,
    link_index,
    opts=default_options
):

    def _post_to_api(dir, payload):
        response = requests.post(
            f"{opts['data_store_api_url']}/api/v1/data/{dir}",
            headers={"Authorization": f"Bearer {opts['data_store_api_key']}"},
            json=payload
        )
        return response.json()

    def _set_entity(entity_short_name):
        global entities
        recipient = None
        if entity_short_name not in entities:
            logger.info(f"Getting {entity_short_name}")
            recipient = _post_to_api("entity/get", { "shortName": entity_short_name })
            if "didDoc" not in recipient:
                logger.info(f"Creating {entity_short_name}")
                recipient = _post_to_api("entity/create", { "shortName": entity_short_name })
            if recipient is None or "didDoc" not in recipient:
                raise Exception("No entity found or created")
            entities.append(entity_short_name)
        else:
            logger.info(f"Using cached {entity_short_name}")

    def _process_event(sender_short_name, recipient_short_name, in_vcon_uuid, out_vcon_uuid, payload):
        data = {
            "type": 'data',
            "senderShortName": sender_short_name,
            "recipientShortName": recipient_short_name,
            "agreementId": opts["agreement_id"],
            "data": payload,
            "meta": {
                "in_vcon_uuid": in_vcon_uuid,
                "out_vcon_uuid": out_vcon_uuid
            },
            "archive": {
                "url": opts["archive_api_url"],
                "key": opts["archive_api_key"],
            }
        }
        event = _post_to_api("event/produce", data)
        logger.info(f"Processed event {event['created']['eventId']} ({sender_short_name} => {recipient_short_name})")

    logger.info(f"Running {tracer_name} tracer on vCon {out_vcon_uuid}")
    
    # Get vCon data from Redis
    vcon_redis = VconRedis()
    vcon_obj = vcon_redis.get_vcon(out_vcon_uuid)
    if not vcon_obj:
        logger.error(f"Could not get vCon {out_vcon_uuid} from Redis")
        return False

    vcon_dict = vcon_obj.to_dict()

    try:
        logger.info(f"Processing vCon {out_vcon_uuid} through JLINC API at {opts['data_store_api_url']}")

        global domain, system_short_name
        if domain == "" or system_short_name == "":
            domains = _post_to_api("entity/domains/get", {})
            domain = domains[0]
            logger.info(f"Set domain to {domain}")
            system_short_name = f"{_sanitize(opts['system_prefix'])}-system@{domain}"
            _set_entity(system_short_name)

        sender_short_name = system_short_name
        recipient_short_name = system_short_name
        if link_index >= 0:
            sender_short_name = f"{_sanitize(opts['system_prefix'])}-{_sanitize(links[link_index-1])}@{domain}"
            _set_entity(sender_short_name)
        if link_index < len(links)-1:
            recipient_short_name = f"{_sanitize(opts['system_prefix'])}-{_sanitize(links[link_index+1])}@{domain}"
            _set_entity(recipient_short_name)

        payload = vcon_dict
        if "hash_event_data" in opts and opts["hash_event_data"]:
            payload = {
                "hash": hashlib.sha256(json.dumps(vcon_dict).encode('utf-8')).hexdigest()
            }
        _process_event(sender_short_name, recipient_short_name, in_vcon_uuid, out_vcon_uuid, payload)

    except Exception as e:
        logger.warning(f"Error connecting to JLINC API at {opts['data_store_api_url']}: {e}")

    # Successfully processed and audited
    logger.info(f"Successfully completed JLINC processing for vCon {out_vcon_uuid}")
    return True 