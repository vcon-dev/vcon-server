# add python path
import sys
import os
sys.path.append("server")
sys.path.append("server/lib")

import traceback
from datetime import datetime
from typing import Dict, List, Union, Optional
from uuid import UUID
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yaml
from server.config import Configuration
from storage.base import Storage
from peewee import CharField, Model
from playhouse.postgres_ext import (
    BinaryJSONField,
    DateTimeField,
    PostgresqlExtDatabase,
    UUIDField,
)
from pydantic import BaseModel
from dlq_utils import get_ingress_list_dlq_name
from settings import VCON_SORTED_SET_NAME, VCON_STORAGE, CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME, CONSERVER_API_TOKEN_FILE
from fastapi.security.api_key import APIKeyHeader
from fastapi import APIRouter
from fastapi import Security
from starlette.status import HTTP_403_FORBIDDEN
from uuid import UUID
from lib.logging_utils import init_logger
import redis_mgr


logger = init_logger(__name__)
logger.info("Api starting up")


app = FastAPI()
api_key_header = APIKeyHeader(name=CONSERVER_HEADER_NAME, auto_error=False)

api_keys = []
if CONSERVER_API_TOKEN:
    api_keys.append(CONSERVER_API_TOKEN)
    logger.info("Adding CONSERVER_API_TOKEN to api_keys")   
    
if CONSERVER_API_TOKEN_FILE:
    logger.info("Adding CONSERVER_API_TOKEN_FILE to api_keys")
    # read the api keys from the file, one key per line
    with open(CONSERVER_API_TOKEN_FILE, 'r') as file:
        for line in file:
            api_keys.append(line.strip())
                    
if api_keys == []:
    logger.info("No api keys found, skipping authentication")

async def get_api_key(api_key_header: str = Security(api_key_header)):
    # If the api_keys are empty, then we don't need to authenticate.
    if api_keys == []:
        logger.info("Skipping authentication")
        return

    if api_key_header not in api_keys:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Invalid API Key"
        )
    return api_key_header


async def on_startup():
    global redis_async
    redis_async = await redis_mgr.get_async_client()


async def on_shutdown():
    await redis_async.close()

app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api_router = APIRouter()


class Vcon(BaseModel):
    vcon: str
    uuid: UUID
    created_at: Union[int, str, datetime]
    subject: Optional[str] = None
    redacted: dict = {}
    appended: Optional[dict] = None
    group: List[Dict] = []
    parties: List[Dict] = []
    dialog: List[Dict] = []
    analysis: List[Dict] = []
    attachments: List[Dict] = []
    meta: Optional[dict] = {}


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


async def add_vcon_to_set(vcon_uuid: UUID, timestamp: int):
    await redis_async.zadd(VCON_SORTED_SET_NAME, {vcon_uuid: timestamp})


# These are the vCon data models
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
async def get_vcons_uuids(
    page: int = 1, size: int = 50, since: datetime = None, until: datetime = None
):
    # Redis is storing the vCons. Use the vcons sorted set to get the vCon UUIDs
    """
    Gets a list of vCon UUIDs.

    This endpoint enables pagination of vCon UUIDs. You can use the page and size
    parameters to paginate the results. You can also filter by date with the since and
    until parameters.

    Parameters:

    - `page`: The page number to retrieve, defaults to 1.
    - `size`: The number of items per page, defaults to 50.
    - `since`: The earliest date to retrieve vCons from, in ISO 8601 format.
    - `until`: The latest date to retrieve vCons up to, in ISO 8601 format.

    Returns:

    - A list of vCon UUIDs as strings.
    """
    until_timestamp = "+inf"
    since_timestamp = "-inf"

    # We can either use the page and offset, or the since and until parameters
    if since:
        since_timestamp = int(since.timestamp())
    if until:
        until_timestamp = int(until.timestamp())
    offset = (page - 1) * size
    vcon_uuids = await redis_async.zrevrangebyscore(
        VCON_SORTED_SET_NAME,
        until_timestamp,
        since_timestamp,
        start=offset,
        num=size,
    )
    logger.info("Returning vcon_uuids: {}".format(vcon_uuids))

    # Convert the vcon_uuids to strings and strip the vcon: prefix
    vcon_uuids = [vcon.split(":")[1] for vcon in vcon_uuids]
    return vcon_uuids


# Create an endpoint to pop vcon IDs from one or more redis lists
@api_router.get(
    "/vcon/egress",
    status_code=204,
    summary="Removes one or more vCon UUIDs from the output of a chain (egress)",
    description="Removes one or more vCon UUIDs from the output of a chain (egress)",
    tags=["chain"],
)
async def get_vcon_egress(egress_list: str, limit: int = 1) -> JSONResponse:
    """
    Removes one or more vCon UUIDs from the output of a chain (egress)

    If limit is not provided, defaults to 1.

    Returns:

    - A JSONResponse containing a list of vCon UUIDs as strings.
    """
    try:
        vcon_uuids = []
        for i in range(limit):
            vcon_uuid = await redis_async.rpop(egress_list)
            if vcon_uuid:
                vcon_uuids.append(vcon_uuid)
        return JSONResponse(content=vcon_uuids)

    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


@api_router.get(
    "/vcon/{vcon_uuid}",
    response_model=Vcon,
    summary="Gets a particular vCon by UUID",
    description="How to get a particular vCon by UUID",
    tags=["vcon"],
)
async def get_vcon(vcon_uuid: UUID):
    """
    Gets a particular vCon by UUID

    This endpoint attempts to retrieve a vCon by it's UUID from redis. If the vCon is not found in redis, it will loop through all the configured storages and attempt to retrieve the vCon. If it finds the vCon in any of the storages, it will return the vCon, otherwise it will return a 404 status code.

    Args:
        vcon_uuid (str): The UUID of the vCon to retrieve.

    Returns:
        JSONResponse: A JSONResponse containing the vCon as a JSON object if the vCon is found, otherwise a 404 status code.
    """
    
    vcon = await redis_async.json().get(f"vcon:{str(vcon_uuid)}")
    if not vcon:
        # Fallback to the storages if the vcon is not found in redis
        for storage_name in Configuration.get_storages():
            vcon = Storage(storage_name=storage_name).get(vcon_uuid)
            if vcon:
                break

    return JSONResponse(content=vcon, status_code=200 if vcon else 404)


@api_router.get(
    "/vcons",
    response_model=Vcon,
    summary="Gets vCons by UUIDs",
    description="Get multiple vCons by UUIDs",
    tags=["vcon"],
)
        
async def get_vcons(vcon_uuids: str = Query(None)):
    """
    Gets multiple vCons by UUIDs

    This endpoint attempts to retrieve multiple vCons by their UUIDs from redis. If any of the vCons are not found in redis, it will loop through all the configured storages and attempt to retrieve the vCons. If it finds the vCons in any of the storages, it will return the vCons, otherwise it will return a 404 status code.

    Args:
        vcon_uuids (List[UUID], optional): The UUIDs of the vCons to retrieve. Defaults to None.

    Returns:
        JSONResponse: A JSONResponse containing a list of vCons as JSON objects if the vCons are found, otherwise a 404 status code.
    """ 
    vcon_uuids = vcon_uuids.split(",")
    keys = [f"vcon:{vcon_uuid}" for vcon_uuid in vcon_uuids]
    vcons = await redis_async.json().mget(keys=keys, path=".")

    results = []
    for vcon_uuid, vcon in zip(vcon_uuids, vcons):
        if not vcon:
            # Fallback to the storages if the vcon is not found in redis
            for storage_name in Configuration.get_storages():
                vcon = Storage(storage_name=storage_name).get(vcon_uuid)
                if vcon:
                    break
        results.append(vcon)

    return JSONResponse(content=results, status_code=200)
@api_router.get(
    "/vcons/search",
    response_model=List[UUID],
    summary="Search vCons based on various parameters",
    description="Search for vCons using personal identifiers and metadata.",
    tags=["vcon"],
)
async def search_vcons(
    tel: Optional[str] = Query(None, description="Phone number to search for"),
    mailto: Optional[str] = Query(None, description="Email address to search for"),
    name: Optional[str] = Query(None, description="Name of the party to search for"),
):
    """
    Search for vCons using personal identifiers and metadata.

    Parameters:
        tel (str): Phone number to search for.
        mailto (str): Email address to search for.
        name (str): Name of the party to search for.

    Returns:
        a list of vCon UUIDs that match the search criteria.
    """
    if tel is None and mailto is None and name is None:
        raise HTTPException(
            status_code=400, detail="At least one search parameter must be provided"
        )
            
    try:
        tel_keys = set()
        mailto_keys = set()
        name_keys = set()
        search_terms = 0
        
        if tel:
            search_terms += 1
            tel_key = f"tel:{tel}"
            uuids = await redis_async.smembers(tel_key)
            tel_keys.update(f"vcon:{uuid}" for uuid in uuids)

        if mailto:
            search_terms += 1
            mailto_key = f"mailto:{mailto}"
            uuids = await redis_async.smembers(mailto_key)
            mailto_keys.update(f"vcon:{uuid}" for uuid in uuids)            

        if name:
            search_terms += 1
            name_key = f"name:{name}"
            uuids = await redis_async.smembers(name_key)
            name_keys.update(f"vcon:{uuid}" for uuid in uuids)

        if search_terms > 1:
            # Filter out None and empty sets
            logger.info(f"Search terms: {tel}, {mailto}, {name}")
            named_sets = []
            if name:
                logger.info("Name set: " + str(name_keys))
                named_sets.append(name_keys)
            if tel:
                logger.info("Tel set: " + str(tel_keys))
                named_sets.append(tel_keys)
            if mailto:
                logger.info("Mailto set: " + str(mailto_keys))
                named_sets.append(mailto_keys)
                
            logger.info(f"Named sets: {named_sets}")
                       
            # Take the intersection of all valid sets
            keys = set.intersection(*named_sets)
            logger.info(f"Keys: {keys}")
                    
        else:
            # If there is only one search term, return the corresponding set
            keys = tel_keys | mailto_keys | name_keys
            
         
        if not keys:
            return []   

        # Return the list of uuids as a list, stripping the vcon: prefix
        return [key.split(":")[1] for key in keys]
    
 
    except Exception as e:
        logger.error(f"Error in search_vcons: {str(e)}")
        raise HTTPException(
            status_code=500, detail="An error occurred during the search"
        )


@api_router.post(
    "/vcon",
    response_model=Vcon,
    summary="Inserts a vCon into the database",
    description="How to insert a vCon into the database.",
    tags=["vcon"],
)
async def post_vcon(inbound_vcon: Vcon):
    """
    Inserts a vCon into the database.

    This API endpoint takes a vCon JSON object and stores it in the Redis database.
    It also adds the vCon to the sorted set of all vCons, sorted by the timestamp of
    the vCon.

    The vCon object is expected to contain the following keys:
    - `uuid`: a unique identifier for the vCon
    - `created_at`: the timestamp of the vCon
    - `subject`: the subject of the vCon
    - `parties`: a list of parties, each containing the following keys:
        - `name`: the name of the party
        - `email`: the email address of the party

    The response will be a JSON object with the following keys:
    - `uuid`: the uuid of the vCon
    - `created_at`: the timestamp of the vCon
    - `subject`: the subject of the vCon
    - `parties`: the list of parties

    The response will be a JSON object with a status code of 201 if the vCon
    was successfully inserted into the database.

    If an error occurs, the response will be a JSON object with a status code
    of 500 and a detail key containing the error message.
    """
    try:
        print(type(inbound_vcon))
        dict_vcon = inbound_vcon.model_dump()
        dict_vcon["uuid"] = str(inbound_vcon.uuid)
        key = f"vcon:{str(dict_vcon['uuid'])}"
        created_at = datetime.fromisoformat(dict_vcon["created_at"])
        timestamp = int(created_at.timestamp())

        # Store the vcon in redis
        logger.debug(
            "Posting vcon  {} len {}".format(inbound_vcon.uuid, len(dict_vcon))
        )
        await redis_async.json().set(key, "$", dict_vcon)
        # Add the vcon to the sorted set
        logger.debug("Adding vcon {} to sorted set".format(inbound_vcon.uuid))
        await add_vcon_to_set(key, timestamp)

        # Index the parties
        logger.debug("Adding vcon {} to parties sets".format(inbound_vcon.uuid))
        await index_vcon(inbound_vcon.uuid)

    except Exception:
        # Print all of the details of the exception
        logger.info(traceback.format_exc())
        return None
    logger.debug("Posted vcon  {} len {}".format(inbound_vcon.uuid, len(dict_vcon)))
    return JSONResponse(content=dict_vcon, status_code=201)


@api_router.delete(
    "/vcon/{vcon_uuid}",
    status_code=204,
    summary="Deletes a particular vCon by UUID",
    description="How to remove a vCon from the conserver.",
    tags=["vcon"],
)
async def delete_vcon(vcon_uuid: UUID):
    # FIX: support the VCON_STORAGE case
    """
    Deletes a particular vCon by UUID.

    This endpoint takes a UUID as an argument and
    deletes the corresponding vCon from the conserver.

    Args:
        vcon_uuid (UUID): The UUID of the vCon to delete.

    Returns:
        Empty response with a status code of 204.

    Raises:
        HTTPException: With a status code of 500 if any error occurs.
    """
    try:
        await redis_async.json().delete(f"vcon:{str(vcon_uuid)}")
    except Exception:
        # Print all of the details of the exception
        logger.info(traceback.format_exc())
        raise HTTPException(status_code=500)


# Ingress and egress endpoints for vCon IDs
# Create an endpoint to push vcon IDs to one or more redis lists
@api_router.post(
    "/vcon/ingress",
    status_code=204,
    summary="Inserts a vCon UUID into one or more chains",
    description="Inserts a vCon UUID into one or more chains.",
    tags=["chain"],
)
async def post_vcon_ingress(vcon_uuids: List[str], ingress_list: str):
    """
    Inserts a vCon UUID into one or more chains.

    This endpoint takes a list of vCon UUIDs and a Redis list name as arguments
    and inserts the vCon UUIDs into the Redis list.

    Args:
        vcon_uuids (List[str]): A list of vCon UUIDs to insert into the Redis list.
        ingress_list (str): The name of the Redis list to insert the vCon UUIDs into.

    Returns:
        Empty response with a status code of 204.

    Raises:
        HTTPException: With a status code of 500 if any error occurs.
    """
    try:
        for vcon_id in vcon_uuids:
            await redis_async.rpush(
                ingress_list,
                vcon_id,
            )
    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


# Create an endpoint to count the number of vCon UUIds in a redis list
@api_router.get(
    "/vcon/count",
    status_code=204,
    summary="Returns the number of vCons at the end of a chain",
    description="Returns the number of vCons at the end of a chain.",
    tags=["chain"],
)
async def get_vcon_count(egress_list: str):
    """
    Returns the number of vCons at the end of a chain.

    This endpoint takes a Redis list name as an argument and returns the
    number of elements in the Redis list.

    Args:
        egress_list (str): The name of the Redis list to count the elements of.

    Returns:
        A JSONResponse containing the count of elements in the Redis list.

    Raises:
        HTTPException: With a status code of 500 if any error occurs.
    """
    try:
        count = await redis_async.llen(egress_list)
        return JSONResponse(content=count)

    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


@api_router.get(
    "/config",
    status_code=200,
    summary="Returns the config file for the conserver",
    description="Returns the config file for the conserver",
    tags=["config"],
)
async def get_config():
    """
    Returns the config file for the conserver.

    This endpoint returns the config file stored in Redis.

    Returns:
        A JSONResponse containing the config file.

    Raises:
        HTTPException: With a status code of 500 if any error occurs.
    """
    try:
        # read the file from CONSERVER_CONFIG_FILE
        with open(os.getenv("CONSERVER_CONFIG_FILE"), "r") as f:
            config = yaml.safe_load(f)
        return JSONResponse(content=config)

    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


# THis endpoint is used to update the config file, then calls
# the load_config endpoint to load the new config file into redis
@api_router.post(
    "/config",
    status_code=204,
    summary="Updates the config file for the conserver",
    description="Updates the config file for the conserver",
    tags=["config"],
)
async def post_config(config: Dict):
    """
    Updates the config file for the conserver.

    This endpoint takes a JSON representation of the config file and stores it in on Disk.

    Args:
        config (Dict): The JSON representation of the config file.

    Raises:
        HTTPException: With a status code of 500 if any error occurs.
    """
    try:
        # Write the config from CONSERVER_CONFIG_FILE to the config.yml file
        with open(os.getenv("CONSERVER_CONFIG_FILE"), "w") as f:
            yaml.dump(config, f)
 
    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


# Reprocess Dead Letter Queue
@api_router.post(
    "/dlq/reprocess",
    status_code=200,
    summary="Reprocess the dead letter queue",
    description="Move the dead letter queue vcons back to the ingress chain",
    tags=["dlq"],
)
async def post_dlq_reprocess(ingress_list: str):
    # Get all items from redis list and move them back to the ingress list
    """
    Reprocess the dead letter queue.

    This endpoint moves the dead letter queue vcons back to the ingress chain.

    Args:
        ingress_list (str): The name of the ingress list to move the vcons back to.

    Returns:
        JSONResponse: A JSON response with the number of vcons that were moved.
    """
    dlq_name = get_ingress_list_dlq_name(ingress_list)
    counter = 0
    while item := await redis_async.rpop(dlq_name):
        await redis_async.rpush(ingress_list, item)
        counter += 1
    return JSONResponse(content=counter)


@api_router.get(
    "/dlq",
    status_code=200,
    summary="Get Vcons list from the dead letter queue",
    description="Get Vcons list from the dead letter queue, returns array of vcons.",
    tags=["dlq"],
)
async def get_dlq_vcons(ingress_list: str):
    """Get all the vcons from the dead letter queue"""
    dlq_name = get_ingress_list_dlq_name(ingress_list)
    vcons = await redis_async.lrange(dlq_name, 0, -1)
    return JSONResponse(content=vcons)


async def index_vcon(uuid):
    """
    Index a vcon for search

    This function adds the vcon to the sorted set of vcons, and also adds the
    vcon uuid to the sets of uuids for each party's tel, mailto, and name.

    Args:
        uuid (str): The uuid of the vcon to index.
    """
    key = "vcon:" + str(uuid)
    vcon = await redis_async.json().get(key)
    created_at = datetime.fromisoformat(vcon["created_at"])
    timestamp = int(created_at.timestamp())
    vcon_uuid = vcon["uuid"]
    await add_vcon_to_set(key, timestamp)

    # We would also like to search vCons by the tel number in each dialog.
    for party in vcon["parties"]:
        if party.get("tel", None):
            tel = party["tel"]
            tel_key = f"tel:{tel}"
            await redis_async.sadd(tel_key, vcon_uuid)
        if party.get("mailto", None):
            mailto = party["mailto"]
            mailto_key = f"mailto:{mailto}"
            await redis_async.sadd(mailto_key, vcon_uuid)
        if party.get("name", None):
            name = party["name"]
            name_key = f"name:{name}"
            await redis_async.sadd(name_key, vcon_uuid)


@api_router.get(
    "/index_vcons",
    status_code=200,
    summary="Forces a reset of the vcon search list",
    description="Forces a reset of the vcon search list, returns the number of vCons indexed.",
    tags=["config"],
)
async def index_vcons():
    """
    Forces a reset of the vcon search list, returns the number of vCons indexed.
    
    This endpoint will iterate over all the vcon keys in redis, and call
    index_vcon for each one. This will add the vcon to the sorted set of vcons,
    and also add the vcon uuid to the sets of uuids for each party's tel, mailto,
    and name.
    
    Returns:
        JSONResponse: A JSONResponse containing the number of vcons indexed.
    """
    try:
        # Get all of the vcon keys, and add them to the sorted set
        vcon_keys = await redis_async.keys("vcon:*")
        for key in vcon_keys:
            uuid = key.split(":")[1]
            await index_vcon(uuid)

        # Get all of the vcon keys, and add them to the sorted set

        # Return the number of vcons indexed
        return JSONResponse(content=len(vcon_keys))

    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)

app.include_router(
    api_router,
    dependencies=[Security(get_api_key, scopes=[])]
)