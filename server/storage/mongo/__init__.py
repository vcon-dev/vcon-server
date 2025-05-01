import pymongo
from datetime import datetime
from typing import Dict, Any

from lib.logging_utils import init_logger
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

<<<<<<< HEAD
def convert_mongo_date_to_string(date_obj) -> str:
    """
    Convert datetime object to ISO 8601 string format.
    """
    if not isinstance(date_obj, datetime):
        return date_obj
    return date_obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def prepare_vcon_for_mongo(vcon: Vcon) -> dict:
=======
def prepare_vcon_for_mongo(vcon: Vcon) -> Dict[str, Any]:
    """
    Prepare a Vcon object for MongoDB storage by converting dates to datetime objects.
    
    Args:
        vcon (Vcon): The Vcon object to prepare
        
    Returns:
        Dict[str, Any]: MongoDB-ready dictionary representation of the Vcon
    """
    logger.debug(f"Preparing vCon {vcon.uuid} for MongoDB storage")
>>>>>>> main
    clean_vcon = vcon.to_dict()
    clean_vcon["_id"] = vcon.uuid
    clean_vcon["created_at"] = convert_date_to_mongo_date(clean_vcon["created_at"])
    for dialog in clean_vcon["dialog"]:
        dialog["start"] = convert_date_to_mongo_date(dialog["start"])
    return clean_vcon

def prepare_mongo_for_vcon(mongo_doc) -> dict:
    """
    Convert MongoDB document back to vCon format by converting dates to ISO strings.
    """
    if not mongo_doc:
        return None
    
    # Create a copy to avoid modifying the original
    vcon_dict = mongo_doc.copy()
    
    # Convert MongoDB ObjectId to string if present
    if "_id" in vcon_dict:
        vcon_dict["uuid"] = str(vcon_dict["_id"])
        del vcon_dict["_id"]
    
    # Convert created_at date
    if "created_at" in vcon_dict and isinstance(vcon_dict["created_at"], datetime):
        vcon_dict["created_at"] = convert_mongo_date_to_string(vcon_dict["created_at"])
    
    # Convert dialog start dates
    if "dialog" in vcon_dict:
        for dialog in vcon_dict["dialog"]:
            if "start" in dialog and isinstance(dialog["start"], datetime):
                dialog["start"] = convert_mongo_date_to_string(dialog["start"])
    
    return vcon_dict


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
        if vcon is None:
            raise ValueError(f"vCon with UUID {vcon_uuid} not found in Redis")
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
<<<<<<< HEAD
        raise e


def read(
    vcon_uuid,
    opts=default_options,
) -> Vcon:
    """
    Retrieve a vCon from MongoDB by its UUID.
    
    Args:
        vcon_uuid: The UUID of the vCon to retrieve
        opts: MongoDB connection options
        
    Returns:
        Vcon object if found, None otherwise
    """
    logger.info(f"Reading vCon {vcon_uuid} from MongoDB")
    client = pymongo.MongoClient(opts["url"])
    
    try:
        db = client[opts["database"]]
        collection = db[opts["collection"]]
        
        # Find the document by _id (which is the vcon_uuid)
        mongo_doc = collection.find_one({"_id": vcon_uuid})
        
        if not mongo_doc:
            logger.warning(f"vCon with UUID {vcon_uuid} not found in MongoDB")
            return None
        
        # Convert MongoDB document to vCon format
        vcon_dict = prepare_mongo_for_vcon(mongo_doc)
        
        # Create and return a Vcon object
        vcon = Vcon(vcon_dict)
        logger.info(f"Successfully retrieved vCon {vcon_uuid} from MongoDB")
        return vcon
        
    except Exception as e:
        logger.error(f"Failed to read vCon {vcon_uuid} from MongoDB: {e}")
        raise e
    finally:
        client.close()
=======
        raise

>>>>>>> main
