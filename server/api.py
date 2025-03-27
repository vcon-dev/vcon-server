import datetime
import logging
import os
import time
import traceback
from functools import wraps
from typing import Dict, List, Optional
from uuid import UUID

# Third-party imports
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from peewee import CharField, Model
from playhouse.postgres_ext import BinaryJSONField, DateTimeField, PostgresqlExtDatabase, UUIDField
from pydantic import BaseModel, ConfigDict
from starlette.status import HTTP_403_FORBIDDEN
import yaml

# Local imports
from config import Configuration
from dlq_utils import get_ingress_list_dlq_name
from lib.logging_utils import init_logger
import redis_mgr
from settings import (
    API_ROOT_PATH,
    CONSERVER_API_TOKEN,
    CONSERVER_API_TOKEN_FILE,
    CONSERVER_HEADER_NAME,
    VCON_SORTED_SET_NAME,
    VCON_STORAGE,
)
from storage.base import Storage

# Initialize logger
logger = init_logger(__name__)
logger.setLevel(logging.INFO)

# Log startup with version info if available
try:
    with open('VERSION', 'r') as f:
        version = f.read().strip()
    logger.info(f"API starting up - Version: {version}")
except (FileNotFoundError, IOError):
    logger.info("API starting up - Version info not available")

# Create performance logging decorator
def log_performance(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        logger.debug(f"ENTER: {func_name} - Args: {args}, Kwargs: {kwargs}")
        
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"EXIT: {func_name} - Execution time: {elapsed:.4f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"ERROR in {func_name}: {str(e)} - Execution time: {elapsed:.4f}s")
            logger.exception(e)
            raise
    
    return wrapper

app = FastAPI(root_path=API_ROOT_PATH)
api_key_header = APIKeyHeader(name=CONSERVER_HEADER_NAME, auto_error=False)

# Middleware for request/response logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(UUID())
    start_time = time.time()
    
    # Log request details
    logger.info(f"Request [{request_id}] - Method: {request.method} - Path: {request.url.path} - Client: {request.client.host if request.client else 'Unknown'}")
    
    # Process request
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log response details
        logger.info(f"Response [{request_id}] - Status: {response.status_code} - Time: {process_time:.4f}s")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Error [{request_id}] - Exception: {str(e)} - Time: {process_time:.4f}s")
        logger.exception(e)
        raise

api_keys = []
if CONSERVER_API_TOKEN:
    api_keys.append(CONSERVER_API_TOKEN)
    logger.info("Adding CONSERVER_API_TOKEN to api_keys")

if CONSERVER_API_TOKEN_FILE:
    logger.info(f"Loading API keys from file: {CONSERVER_API_TOKEN_FILE}")
    try:
        # read the api keys from the file, one key per line
        with open(CONSERVER_API_TOKEN_FILE, 'r') as file:
            for line in file:
                key = line.strip()
                if key:  # Only add non-empty keys
                    api_keys.append(key)
        logger.info(f"Successfully loaded {len(api_keys)} API keys from file")
    except Exception as e:
        logger.error(f"Failed to load API keys from file: {str(e)}")
        logger.exception(e)

if not api_keys:
    logger.warning("No API keys configured - authentication will be skipped")


async def get_api_key(api_key_header: str = Security(api_key_header)):
    # If the api_keys are empty, then we don't need to authenticate.
    if not api_keys:
        logger.debug("Authentication skipped - no API keys configured")
        return

    if api_key_header not in api_keys:
        logger.warning(f"Authentication failed - invalid API key attempt from client")
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API Key")
    
    logger.debug("Authentication successful")
    return api_key_header


async def on_startup():
    logger.info("Server starting up - initializing services")
    try:
        global redis_async
        redis_async = await redis_mgr.get_async_client()
        logger.info("Redis async client initialized successfully")
    except Exception as e:
        logger.critical(f"Failed to initialize Redis connection: {str(e)}")
        logger.exception(e)
        raise


async def on_shutdown():
    logger.info("Server shutting down - cleaning up resources")
    try:
        await redis_async.close()
        logger.info("Redis connection closed successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

api_router = APIRouter()


class Vcon(BaseModel):
    model_config = ConfigDict(extra='allow')
    vcon: str
    uuid: UUID
    created_at: datetime.datetime
    subject: Optional[str] = None
    redacted: dict = {}
    appended: Optional[dict] = None
    group: List[Dict] = []
    parties: List[Dict] = []
    dialog: List[Dict] = []
    analysis: List[Dict] = []
    attachments: List[Dict] = []


if VCON_STORAGE:

    class VConPeeWee(Model):
        id = UUIDField(primary_key=True)
        vcon = CharField()
        uuid = UUIDField()
        created_at = DateTimeField()
        updated_at = DateTimeField(null=True)
        subject = CharField(null=True)
        vcon_json = BinaryJSONField(null=True)
        type = CharField(null=True)

        class Meta:
            table_name = "vcons"
            database = PostgresqlExtDatabase(VCON_STORAGE)


@log_performance
async def add_vcon_to_set(vcon_uuid: UUID, timestamp: int):
    logger.debug(f"Adding vCon {vcon_uuid} to sorted set with timestamp {timestamp}")
    try:
        result = await redis_async.zadd(VCON_SORTED_SET_NAME, {vcon_uuid: timestamp})
        logger.debug(f"Added vCon {vcon_uuid} to sorted set: result={result}")
        return result
    except Exception as e:
        logger.error(f"Failed to add vCon {vcon_uuid} to sorted set: {str(e)}")
        raise


@api_router.get(
    "/vcon",
    response_model=List[str],
    summary="Gets a list of vCon UUIDs",
    description=(
        "Retrieves a list of vCon UUIDs. You can use the page and size query "
        "parameters to paginate the results. You can also filter the results "
        "by date using the since and until query parameters. The results are "
        "sorted in descending order by timestamp. "
    ),
    tags=["vcon"],
)
@log_performance
async def get_vcons_uuids(
    page: int = 1, size: int = 50, since: Optional[datetime.datetime] = None, until: Optional[datetime.datetime] = None
):
    logger.info(f"Getting vCon UUIDs - Page: {page}, Size: {size}, Since: {since}, Until: {until}")
    
    until_timestamp = "+inf"
    since_timestamp = "-inf"

    if since:
        since_timestamp = int(since.timestamp())
        logger.debug(f"Since timestamp: {since_timestamp}")
    if until:
        until_timestamp = int(until.timestamp())
        logger.debug(f"Until timestamp: {until_timestamp}")
        
    offset = (page - 1) * size
    logger.debug(f"Fetching vCons with offset: {offset}, limit: {size}")
    
    try:
        vcon_uuids = await redis_async.zrevrangebyscore(
            VCON_SORTED_SET_NAME,
            until_timestamp,
            since_timestamp,
            start=offset,
            num=size,
        )
        
        vcon_count = len(vcon_uuids)
        logger.info(f"Retrieved {vcon_count} vCon UUIDs")
        logger.debug(f"Retrieved vCon UUIDs: {vcon_uuids}")

        vcon_uuids = [vcon.split(":")[1] for vcon in vcon_uuids]
        return vcon_uuids
    except Exception as e:
        logger.error(f"Error retrieving vCon UUIDs: {str(e)}")
        logger.exception(e)
        raise


@api_router.get(
    "/vcon/egress",
    status_code=204,
    summary="Removes one or more vCon UUIDs from the output of a chain (egress)",
    description="Removes one or more vCon UUIDs from the output of a chain (egress)",
    tags=["chain"],
)
@log_performance
async def get_vcon_egress(egress_list: str, limit: int = 1) -> JSONResponse:
    logger.info(f"Processing egress for list '{egress_list}' with limit {limit}")
    
    try:
        vcon_uuids = []
        for i in range(limit):
            vcon_uuid = await redis_async.rpop(egress_list)
            if vcon_uuid:
                vcon_uuids.append(vcon_uuid)
                logger.debug(f"Popped vCon UUID: {vcon_uuid} from egress list '{egress_list}'")
            else:
                logger.debug(f"No more vCon UUIDs in egress list '{egress_list}'")
                break
                
        logger.info(f"Retrieved {len(vcon_uuids)} vCon UUIDs from egress list '{egress_list}'")
        return JSONResponse(content=vcon_uuids)

    except Exception as e:
        logger.error(f"Error processing egress for list '{egress_list}': {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error processing egress: {str(e)}")


@api_router.get(
    "/vcon/{vcon_uuid}",
    response_model=Vcon,
    summary="Gets a particular vCon by UUID",
    description="How to get a particular vCon by UUID",
    tags=["vcon"],
)
@log_performance
async def get_vcon(vcon_uuid: UUID):
    logger.info(f"Getting vCon with UUID: {vcon_uuid}")
    
    try:
        # First try from Redis
        key = f"vcon:{str(vcon_uuid)}"
        logger.debug(f"Trying to get vCon from Redis with key: {key}")
        vcon = await redis_async.json().get(key)
        
        # If not in Redis, try other storage backends
        if not vcon:
            logger.debug(f"vCon {vcon_uuid} not found in Redis, checking alternative storages")
            for storage_name in Configuration.get_storages():
                logger.debug(f"Trying to get vCon from storage: {storage_name}")
                try:
                    vcon = Storage(storage_name=storage_name).get(vcon_uuid)
                    if vcon:
                        logger.info(f"Found vCon {vcon_uuid} in storage: {storage_name}")
                        break
                except Exception as storage_e:
                    logger.error(f"Error retrieving vCon {vcon_uuid} from storage {storage_name}: {str(storage_e)}")
        
        status_code = 200 if vcon else 404
        if vcon:
            logger.info(f"Successfully retrieved vCon {vcon_uuid}")
        else:
            logger.warning(f"vCon {vcon_uuid} not found in any storage")
            
        return JSONResponse(content=vcon, status_code=status_code)
    except Exception as e:
        logger.error(f"Error retrieving vCon {vcon_uuid}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error retrieving vCon: {str(e)}")


@api_router.get(
    "/vcons",
    response_model=Vcon,
    summary="Gets vCons by UUIDs",
    description="Get multiple vCons by UUIDs",
    tags=["vcon"],
)
@log_performance
async def get_vcons(vcon_uuids: List[UUID] = Query(None)):
    if not vcon_uuids:
        logger.warning("get_vcons called with empty UUID list")
        return JSONResponse(content=[], status_code=200)
        
    logger.info(f"Getting multiple vCons - Count: {len(vcon_uuids)}")
    logger.debug(f"Requested vCon UUIDs: {vcon_uuids}")
    
    keys = [f"vcon:{vcon_uuid}" for vcon_uuid in vcon_uuids]
    try:
        logger.debug(f"Fetching vCons from Redis with keys: {keys}")
        vcons = await redis_async.json().mget(keys=keys, path=".")

        results = []
        not_found_count = 0
        storage_found_count = 0
        
        for vcon_uuid, vcon in zip(vcon_uuids, vcons):
            if not vcon:
                logger.debug(f"vCon {vcon_uuid} not found in Redis, checking alternative storages")
                found = False
                for storage_name in Configuration.get_storages():
                    try:
                        vcon = Storage(storage_name=storage_name).get(vcon_uuid)
                        if vcon:
                            logger.debug(f"Found vCon {vcon_uuid} in storage: {storage_name}")
                            storage_found_count += 1
                            found = True
                            break
                    except Exception as storage_e:
                        logger.error(f"Error accessing storage {storage_name} for vCon {vcon_uuid}: {str(storage_e)}")
                
                if not found:
                    not_found_count += 1
                    logger.warning(f"vCon {vcon_uuid} not found in any storage")
            
            results.append(vcon)
        
        logger.info(f"Retrieved {len(results) - not_found_count} vCons - {storage_found_count} from storage, {not_found_count} not found")
        return JSONResponse(content=results, status_code=200)
    except Exception as e:
        logger.error(f"Error retrieving multiple vCons: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error retrieving vCons: {str(e)}")


@api_router.get(
    "/vcons/search",
    response_model=List[UUID],
    summary="Search vCons based on various parameters",
    description="Search for vCons using personal identifiers and metadata.",
    tags=["vcon"],
)
@log_performance
async def search_vcons(
    tel: Optional[str] = Query(None, description="Phone number to search for"),
    mailto: Optional[str] = Query(None, description="Email address to search for"),
    name: Optional[str] = Query(None, description="Name of the party to search for"),
):
    search_params = {k: v for k, v in {'tel': tel, 'mailto': mailto, 'name': name}.items() if v is not None}
    logger.info(f"Searching vCons with parameters: {search_params}")
    
    if not search_params:
        logger.warning("Search operation attempted without search parameters")
        raise HTTPException(status_code=400, detail="At least one search parameter must be provided")

    try:
        tel_keys = set()
        mailto_keys = set()
        name_keys = set()
        search_terms = 0

        if tel:
            search_terms += 1
            tel_key = f"tel:{tel}"
            logger.debug(f"Getting vCons with telephone: {tel}")
            uuids = await redis_async.smembers(tel_key)
            tel_keys.update(f"vcon:{uuid}" for uuid in uuids)
            logger.debug(f"Found {len(tel_keys)} vCons with telephone: {tel}")

        if mailto:
            search_terms += 1
            mailto_key = f"mailto:{mailto}"
            logger.debug(f"Getting vCons with email: {mailto}")
            uuids = await redis_async.smembers(mailto_key)
            mailto_keys.update(f"vcon:{uuid}" for uuid in uuids)
            logger.debug(f"Found {len(mailto_keys)} vCons with email: {mailto}")

        if name:
            search_terms += 1
            name_key = f"name:{name}"
            logger.debug(f"Getting vCons with name: {name}")
            uuids = await redis_async.smembers(name_key)
            name_keys.update(f"vcon:{uuid}" for uuid in uuids)
            logger.debug(f"Found {len(name_keys)} vCons with name: {name}")

        # If multiple search criteria, perform intersection
        if search_terms > 1:
            logger.info(f"Performing intersection search with {search_terms} criteria")
            named_sets = []
            if name_keys:
                named_sets.append(name_keys)
            if tel_keys:
                named_sets.append(tel_keys)
            if mailto_keys:
                named_sets.append(mailto_keys)
            
            logger.debug(f"Intersection of {len(named_sets)} sets")
            keys = set.intersection(*named_sets)
            logger.info(f"Found {len(keys)} vCons matching all criteria")
        else:
            keys = tel_keys | mailto_keys | name_keys
            logger.info(f"Found {len(keys)} vCons matching single criterion")

        if not keys:
            logger.info("No vCons found matching search criteria")
            return []

        result = [key.split(":")[1] for key in keys]
        logger.debug(f"Returning vCon UUIDs: {result}")
        return result

    except Exception as e:
        logger.error(f"Error in search_vcons: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"An error occurred during the search: {str(e)}")


@api_router.post(
    "/vcon",
    response_model=Vcon,
    summary="Inserts a vCon into the database",
    description="How to insert a vCon into the database.",
    tags=["vcon"],
)
@log_performance
async def post_vcon(inbound_vcon: Vcon, ingress_lists: Optional[List[str]] = Query(None)):
    logger.info(f"Storing new vCon with UUID: {inbound_vcon.uuid}")
    if ingress_lists:
        logger.info(f"Will add vCon to ingress lists: {ingress_lists}")
    
    try:
        # Convert model to dictionary
        dict_vcon = inbound_vcon.model_dump()
        dict_vcon["uuid"] = str(inbound_vcon.uuid)
        key = f"vcon:{str(dict_vcon['uuid'])}"
        
        # Format timestamps
        created_at = datetime.datetime.fromisoformat(str(dict_vcon["created_at"]))
        dict_vcon["created_at"] = created_at.isoformat()
        timestamp = int(created_at.timestamp())
        
        # Store in Redis
        logger.debug(f"Storing vCon {inbound_vcon.uuid} in Redis, size: {len(str(dict_vcon))} bytes")
        await redis_async.json().set(key, "$", dict_vcon)
        
        # Add to sorted set for temporal querying
        logger.debug(f"Adding vCon {inbound_vcon.uuid} to sorted set with timestamp {timestamp}")
        await add_vcon_to_set(inbound_vcon.uuid, timestamp)
        
        # Index for search functionality
        logger.debug(f"Indexing vCon {inbound_vcon.uuid} for search")
        await index_vcon(inbound_vcon.uuid)
        
        # Add to specified ingress lists if provided
        if ingress_lists:
            for ingress_list in ingress_lists:
                logger.debug(f"Adding vCon {inbound_vcon.uuid} to ingress list: {ingress_list}")
                await redis_async.rpush(ingress_list, str(inbound_vcon.uuid))
                logger.info(f"Added vCon {inbound_vcon.uuid} to ingress list: {ingress_list}")

        logger.info(f"Successfully stored vCon {inbound_vcon.uuid}")
        return JSONResponse(content=dict_vcon, status_code=201)
    except Exception as e:
        logger.error(f"Error storing vCon {inbound_vcon.uuid}: {str(e)}")
        logger.exception(e)
        return None


@api_router.delete(
    "/vcon/{vcon_uuid}",
    status_code=204,
    summary="Deletes a particular vCon by UUID",
    description="How to remove a vCon from the conserver.",
    tags=["vcon"],
)
@log_performance
async def delete_vcon(vcon_uuid: UUID):
    logger.info(f"Deleting vCon with UUID: {vcon_uuid}")
    
    try:
        key = f"vcon:{str(vcon_uuid)}"
        
        # Check if vCon exists before deleting
        exists = await redis_async.exists(key)
        if not exists:
            logger.warning(f"Attempted to delete non-existent vCon: {vcon_uuid}")
            return Response(status_code=204)  # Return success even if it doesn't exist
            
        # Get vCon data for cleanup
        try:
            vcon_data = await redis_async.json().get(key)
            logger.debug(f"Retrieved vCon {vcon_uuid} data for cleanup")
        except Exception as e:
            logger.warning(f"Could not retrieve vCon {vcon_uuid} data for cleanup: {str(e)}")
            vcon_data = None
            
        # Delete vCon from Redis
        await redis_async.json().delete(key)
        logger.info(f"Deleted vCon {vcon_uuid} from Redis")
        
        # Clean up indices if we have the data
        if vcon_data and isinstance(vcon_data, dict):
            try:
                logger.debug(f"Cleaning up indices for vCon {vcon_uuid}")
                # Clean up sorted set
                await redis_async.zrem(VCON_SORTED_SET_NAME, key)
                
                # Clean up party indices
                for party in vcon_data.get("parties", []):
                    if party.get("tel"):
                        tel_key = f"tel:{party['tel']}"
                        await redis_async.srem(tel_key, str(vcon_uuid))
                    if party.get("mailto"):
                        mailto_key = f"mailto:{party['mailto']}"
                        await redis_async.srem(mailto_key, str(vcon_uuid))
                    if party.get("name"):
                        name_key = f"name:{party['name']}"
                        await redis_async.srem(name_key, str(vcon_uuid))
                logger.debug(f"Cleaned up indices for vCon {vcon_uuid}")
            except Exception as idx_e:
                logger.warning(f"Error cleaning up indices for vCon {vcon_uuid}: {str(idx_e)}")
        
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error deleting vCon {vcon_uuid}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error deleting vCon: {str(e)}")


@api_router.post(
    "/vcon/ingress",
    status_code=204,
    summary="Inserts a vCon UUID into one or more chains",
    description="Inserts a vCon UUID into one or more chains.",
    tags=["chain"],
)
@log_performance
async def post_vcon_ingress(vcon_uuids: List[str], ingress_list: str):
    logger.info(f"Adding {len(vcon_uuids)} vCon UUIDs to ingress list: {ingress_list}")
    logger.debug(f"vCon UUIDs: {vcon_uuids}")
    
    try:
        success_count = 0
        for vcon_id in vcon_uuids:
            try:
                await redis_async.rpush(ingress_list, vcon_id)
                success_count += 1
                logger.debug(f"Added vCon {vcon_id} to ingress list: {ingress_list}")
            except Exception as item_e:
                logger.error(f"Failed to add vCon {vcon_id} to ingress list {ingress_list}: {str(item_e)}")
        
        logger.info(f"Successfully added {success_count}/{len(vcon_uuids)} vCons to ingress list: {ingress_list}")
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error adding vCons to ingress list {ingress_list}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error adding vCons to ingress list: {str(e)}")


@api_router.get(
    "/vcon/count",
    status_code=204,
    summary="Returns the number of vCons at the end of a chain",
    description="Returns the number of vCons at the end of a chain.",
    tags=["chain"],
)
@log_performance
async def get_vcon_count(egress_list: str):
    logger.info(f"Getting vCon count for egress list: {egress_list}")
    
    try:
        count = await redis_async.llen(egress_list)
        logger.info(f"Found {count} vCons in egress list: {egress_list}")
        return JSONResponse(content=count)
    except Exception as e:
        logger.error(f"Error getting vCon count for egress list {egress_list}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error getting vCon count: {str(e)}")


@api_router.get(
    "/config",
    status_code=200,
    summary="Returns the config file for the conserver",
    description="Returns the config file for the conserver",
    tags=["config"],
)
@log_performance
async def get_config():
    config_path = os.getenv("CONSERVER_CONFIG_FILE")
    logger.info(f"Getting conserver config from: {config_path}")
    
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        logger.debug(f"Successfully loaded config with {len(config) if config else 0} entries")
        return JSONResponse(content=config)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        raise HTTPException(status_code=404, detail=f"Config file not found: {config_path}")
    except yaml.YAMLError as yaml_e:
        logger.error(f"Invalid YAML in config file {config_path}: {str(yaml_e)}")
        raise HTTPException(status_code=500, detail=f"Invalid YAML in config file: {str(yaml_e)}")
    except Exception as e:
        logger.error(f"Error getting config from {config_path}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error getting config: {str(e)}")


@api_router.post(
    "/config",
    status_code=204,
    summary="Updates the config file for the conserver",
    description="Updates the config file for the conserver",
    tags=["config"],
)
@log_performance
async def post_config(config: Dict):
    config_path = os.getenv("CONSERVER_CONFIG_FILE")
    logger.info(f"Updating conserver config at: {config_path}")
    logger.debug(f"New config has {len(config) if config else 0} entries")
    
    try:
        # Create backup of existing config
        if os.path.exists(config_path):
            backup_path = f"{config_path}.bak"
            os.rename(config_path, backup_path)
            logger.info(f"Created backup of existing config at: {backup_path}")
            
        # Write new config
        with open(config_path, "w") as f:
            yaml.dump(config, f)
            
        logger.info(f"Successfully updated config at: {config_path}")
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error updating config at {config_path}: {str(e)}")
        logger.exception(e)
        
        # Try to restore backup if available
        backup_path = f"{config_path}.bak"
        if os.path.exists(backup_path):
            try:
                os.rename(backup_path, config_path)
                logger.info(f"Restored config backup after failed update")
            except Exception as restore_e:
                logger.error(f"Failed to restore config backup: {str(restore_e)}")
                
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")


@api_router.post(
    "/dlq/reprocess",
    status_code=200,
    summary="Reprocess the dead letter queue",
    description="Move the dead letter queue vcons back to the ingress chain",
    tags=["dlq"],
)
@log_performance
async def post_dlq_reprocess(ingress_list: str):
    logger.info(f"Reprocessing dead letter queue for ingress list: {ingress_list}")
    
    dlq_name = get_ingress_list_dlq_name(ingress_list)
    logger.debug(f"DLQ name: {dlq_name}")
    
    try:
        counter = 0
        while item := await redis_async.rpop(dlq_name):
            await redis_async.rpush(ingress_list, item)
            counter += 1
            logger.debug(f"Moved item from DLQ to ingress list: {item}")
            
        logger.info(f"Reprocessed {counter} items from DLQ {dlq_name} to ingress list {ingress_list}")
        return JSONResponse(content=counter)
    except Exception as e:
        logger.error(f"Error reprocessing DLQ {dlq_name}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error reprocessing DLQ: {str(e)}")


@api_router.get(
    "/dlq",
    status_code=200,
    summary="Get Vcons list from the dead letter queue",
    description="Get Vcons list from the dead letter queue, returns array of vcons.",
    tags=["dlq"],
)
@log_performance
async def get_dlq_vcons(ingress_list: str):
    logger.info(f"Getting vCons from dead letter queue for ingress list: {ingress_list}")
    
    dlq_name = get_ingress_list_dlq_name(ingress_list)
    logger.debug(f"DLQ name: {dlq_name}")
    
    try:
        vcons = await redis_async.lrange(dlq_name, 0, -1)
        logger.info(f"Retrieved {len(vcons)} vCons from DLQ {dlq_name}")
        logger.debug(f"DLQ vCons: {vcons}")
        return JSONResponse(content=vcons)
    except Exception as e:
        logger.error(f"Error getting vCons from DLQ {dlq_name}: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error getting vCons from DLQ: {str(e)}")


@log_performance
async def index_vcon(uuid):
    """Index a vCon by its UUID, extract and store searchable attributes"""
    logger.info(f"Indexing vCon: {uuid}")
    
    key = "vcon:" + str(uuid)
    try:
        # Get vCon data
        vcon = await redis_async.json().get(key)
        if not vcon:
            logger.warning(f"vCon {uuid} not found in Redis")
            return
            
        logger.debug(f"Retrieved vCon {uuid} for indexing")
        
        # Parse creation time
        created_at = datetime.datetime.fromisoformat(vcon["created_at"])
        timestamp = int(created_at.timestamp())
        vcon_uuid = vcon["uuid"]
        
        # Add to sorted set
        await add_vcon_to_set(key, timestamp)
        
        # Index parties information
        indexed_fields = []
        for i, party in enumerate(vcon.get("parties", [])):
            party_indices = []
            
            if party.get("tel", None):
                tel = party["tel"]
                tel_key = f"tel:{tel}"
                await redis_async.sadd(tel_key, vcon_uuid)
                party_indices.append(f"tel:{tel}")
                
            if party.get("mailto", None):
                mailto = party["mailto"]
                mailto_key = f"mailto:{mailto}"
                await redis_async.sadd(mailto_key, vcon_uuid)
                party_indices.append(f"mailto:{mailto}")
                
            if party.get("name", None):
                name = party["name"]
                name_key = f"name:{name}"
                await redis_async.sadd(name_key, vcon_uuid)
                party_indices.append(f"name:{name}")
            
            if party_indices:
                indexed_fields.append(f"Party {i+1}: {', '.join(party_indices)}")
        
        if indexed_fields:
            logger.info(f"Indexed vCon {uuid} with fields: {'; '.join(indexed_fields)}")
        else:
            logger.warning(f"vCon {uuid} had no indexable party fields")
            
    except Exception as e:
        logger.error(f"Error indexing vCon {uuid}: {str(e)}")
        logger.exception(e)
        raise


@api_router.get(
    "/index_vcons",
    status_code=200,
    summary="Forces a reset of the vcon search list",
    description="Forces a reset of the vcon search list, returns the number of vCons indexed.",
    tags=["config"],
)
@log_performance
async def index_vcons():
    logger.info("Starting reindexing of all vCons")
    
    try:
        # Get all vCon keys
        vcon_keys = await redis_async.keys("vcon:*")
        logger.info(f"Found {len(vcon_keys)} vCons to reindex")
        
        success_count = 0
        error_count = 0
        
        # Process each vCon
        for key in vcon_keys:
            try:
                uuid = key.split(":")[1]
                logger.debug(f"Reindexing vCon: {uuid}")
                await index_vcon(uuid)
                success_count += 1
            except Exception as e:
                logger.error(f"Error reindexing vCon {key}: {str(e)}")
                error_count += 1
        
        logger.info(f"Reindexing completed - Total: {len(vcon_keys)}, Success: {success_count}, Failed: {error_count}")
        return JSONResponse(content=success_count)
    except Exception as e:
        logger.error(f"Error during vCon reindexing: {str(e)}")
        logger.exception(e)
        raise HTTPException(status_code=500, detail=f"Error during vCon reindexing: {str(e)}")


# Apply API router with API key security
app.include_router(api_router, dependencies=[Security(get_api_key, scopes=[])])

# Log that API is ready
logger.info("API router configured and ready to serve requests")
