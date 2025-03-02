import pymongo

from lib.logging_utils import init_logger

from datetime import datetime
from server.lib.vcon_redis import VconRedis
from vcon import Vcon

logger = init_logger(__name__)


default_options = {
    "name": "mongo", 
    "database": "conserver", 
    "collection": "vcons",
    "url": "mongodb://localhost:27017/"
}

def convert_date_to_mongo_date(date_str) -> datetime:
    """
    Convert ISO 8601 date string to datetime object.
    Handles both 'Z' UTC indicator and explicit timezone offsets like '+00:00'.
    """
    try:
        # Try the format with 'Z' at the end
        return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        try:
            # Try the format with timezone offset like '+00:00'
            # Python's %z doesn't handle the colon in "+00:00", so we need to use dateutil
            from dateutil import parser
            return parser.parse(date_str)
        except Exception as e:
            logger.error(f"Failed to parse date: {date_str}, error: {e}")
            raise

def prepare_vcon_for_mongo(vcon: Vcon) -> dict:
    clean_vcon = vcon.to_dict()
    clean_vcon["_id"] = vcon.uuid
    clean_vcon["created_at"] = convert_date_to_mongo_date(clean_vcon["created_at"])
    for dialog in clean_vcon["dialog"]:
        dialog["start"] = convert_date_to_mongo_date(dialog["start"])
    return clean_vcon


def save(
    vcon_uuid,
    opts=default_options,
):
    logger.info("Starting the mongo storage")
    client = pymongo.MongoClient(opts["url"])
    logger.info(f"mongo storage plugin: connected to {opts['url']}")
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        if vcon is None:
            raise ValueError(f"vCon with UUID {vcon_uuid} not found in Redis")
        db = client[opts["database"]]
        collection = db[opts["collection"]]
        # upsert this vCon
        results = collection.update_one(
            {"_id": vcon_uuid}, {"$set": prepare_vcon_for_mongo(vcon)}, upsert=True
        )
        logger.info(
            f"mongo storage plugin: inserted vCon: {vcon_uuid}, results: {results} "
        )
    except Exception as e:
        logger.error(
            f"mongo storage plugin: failed to insert vCon: {vcon_uuid}, error: {e} "
        )
        raise e
