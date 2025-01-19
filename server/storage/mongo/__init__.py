import pymongo
from datetime import datetime
from typing import Dict, Any

from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
from vcon import Vcon

logger = init_logger(__name__)


default_options = {"name": "mongo", "database": "conserver", "collection_name": "vcons"}


def prepare_vcon_for_mongo(vcon: Vcon) -> Dict[str, Any]:
    """
    Prepare a Vcon object for MongoDB storage by converting dates to datetime objects.
    
    Args:
        vcon (Vcon): The Vcon object to prepare
        
    Returns:
        Dict[str, Any]: MongoDB-ready dictionary representation of the Vcon
    """
    logger.debug(f"Preparing vCon {vcon.uuid} for MongoDB storage")
    clean_vcon = vcon.to_dict()
    clean_vcon["_id"] = vcon.uuid
    clean_vcon["created_at"] = datetime.fromisoformat(clean_vcon["created_at"])
    for dialog in clean_vcon["dialog"]:
        dialog["start"] = datetime.fromisoformat(dialog["start"])
    logger.debug(f"Successfully prepared vCon {vcon.uuid} for MongoDB storage")
    return clean_vcon


def save(
    vcon_uuid: str,
    opts: Dict[str, str] = default_options,
) -> None:
    """
    Save a vCon to MongoDB storage.
    
    Args:
        vcon_uuid (str): UUID of the vCon to save
        opts (Dict[str, str]): MongoDB connection options including:
            - url: MongoDB connection URL
            - database: Database name
            - collection: Collection name
            
    Raises:
        Exception: If there's an error connecting to MongoDB or saving the vCon
    """
    logger.info(f"Starting MongoDB storage operation for vCon: {vcon_uuid}")
    logger.info(f"Options: {opts}")
    
    if "url" not in opts:
        msg = "MongoDB URL not provided in options"
        logger.error(msg)
        raise ValueError(msg)
        
    try:
        client = pymongo.MongoClient(opts["url"])
        logger.debug(f"Successfully connected to MongoDB at {opts['url']}")
        
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        logger.debug(f"Retrieved vCon {vcon_uuid} from Redis")
        
        db = client[opts["database"]]
        collection = db[opts["collection"]]
        
        mongo_vcon = prepare_vcon_for_mongo(vcon)
        results = collection.update_one(
            {"_id": vcon_uuid}, {"$set": mongo_vcon}, upsert=True
        )
        
        logger.info(
            f"Successfully saved vCon {vcon_uuid} to MongoDB. "
            f"Modified: {results.modified_count}, Upserted: {results.upserted_id is not None}"
        )
        
    except Exception as e:
        logger.error(
            f"Failed to save vCon {vcon_uuid} to MongoDB: {str(e)}",
            exc_info=True
        )
        raise


def fetch(vcon_uuid: str, opts: Dict[str, str] = default_options) -> Vcon:
    """
    Fetch a vCon from MongoDB storage by its UUID.
    
    Args:
        vcon_uuid (str): UUID of the vCon to fetch
        opts (Dict[str, str]): MongoDB connection options including:
            - url: MongoDB connection URL
            - database: Database name
            - collection: Collection name
            
    Returns:
        Vcon: The fetched vCon object, or None if not found
    """
    logger.info(f"Fetching vCon {vcon_uuid} from MongoDB")
    
    if "url" not in opts:
        msg = "MongoDB URL not provided in options"
        logger.error(msg)
        raise ValueError(msg)
    
    try:
        client = pymongo.MongoClient(opts["url"])
        logger.debug(f"Successfully connected to MongoDB at {opts['url']}")
        
        db = client[opts["database"]]
        collection = db[opts["collection"]]
        
        result = collection.find_one({"_id": vcon_uuid})
        if result:
            logger.info(f"vCon {vcon_uuid} found in MongoDB")
            return Vcon.from_dict(result)
        else:
            logger.info(f"vCon {vcon_uuid} not found in MongoDB")
            return None
        
    except Exception as e:
        logger.error(
            f"Failed to fetch vCon {vcon_uuid} from MongoDB: {str(e)}",
            exc_info=True
        )
        raise


def exists(vcon_uuid: str, opts: Dict[str, str] = default_options) -> bool:
    """
    Check if a vCon exists in MongoDB storage by its UUID.
    
    Args:
        vcon_uuid (str): UUID of the vCon to check
        opts (Dict[str, str]): MongoDB connection options including:
            - url: MongoDB connection URL
            - database: Database name
            - collection: Collection name
            
    Returns:
        bool: True if the vCon exists, False otherwise
    """
    logger.info(f"Checking existence of vCon {vcon_uuid} in MongoDB")
    
    if "url" not in opts:
        msg = "MongoDB URL not provided in options"
        logger.error(msg)
        raise ValueError(msg)
    
    try:
        client = pymongo.MongoClient(opts["url"])
        logger.debug(f"Successfully connected to MongoDB at {opts['url']}")
        
        db = client[opts["database"]]
        collection = db[opts["collection"]]
        
        exists = collection.count_documents({"_id": vcon_uuid}, limit=1) > 0
        logger.info(f"vCon {vcon_uuid} existence: {exists}")
        return exists
        
    except Exception as e:
        logger.error(
            f"Failed to check existence of vCon {vcon_uuid} in MongoDB: {str(e)}",
            exc_info=True
        )
        raise

