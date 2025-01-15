import datetime
import logging
import os
import traceback
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader
from peewee import CharField, Model
from playhouse.postgres_ext import BinaryJSONField, DateTimeField, PostgresqlExtDatabase, UUIDField
from pydantic import BaseModel, ConfigDict
from starlette.status import HTTP_403_FORBIDDEN
import yaml

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

logger = init_logger(__name__)
logger.setLevel(logging.INFO)

logger.info("Api starting up")

app = FastAPI(root_path=API_ROOT_PATH)
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
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API Key")
    return api_key_header


async def on_startup():
    global redis_async
    redis_async = await redis_mgr.get_async_client()


async def on_shutdown():
    await redis_async.close()


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


async def add_vcon_to_set(vcon_uuid: UUID, timestamp: int):
    await redis_async.zadd(VCON_SORTED_SET_NAME, {vcon_uuid: timestamp})


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
    page: int = 1, size: int = 50, since: Optional[datetime.datetime] = None, until: Optional[datetime.datetime] = None
):
    until_timestamp = "+inf"
    since_timestamp = "-inf"

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

    vcon_uuids = [vcon.split(":")[1] for vcon in vcon_uuids]
    return vcon_uuids


@api_router.get(
    "/vcon/egress",
    status_code=204,
    summary="Removes one or more vCon UUIDs from the output of a chain (egress)",
    description="Removes one or more vCon UUIDs from the output of a chain (egress)",
    tags=["chain"],
)
async def get_vcon_egress(egress_list: str, limit: int = 1) -> JSONResponse:
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
    vcon = await redis_async.json().get(f"vcon:{str(vcon_uuid)}")
    if not vcon:
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
async def get_vcons(vcon_uuids: List[UUID] = Query(None)):
    keys = [f"vcon:{vcon_uuid}" for vcon_uuid in vcon_uuids]
    vcons = await redis_async.json().mget(keys=keys, path=".")

    results = []
    for vcon_uuid, vcon in zip(vcon_uuids, vcons):
        if not vcon:
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
    if tel is None and mailto is None and name is None:
        raise HTTPException(status_code=400, detail="At least one search parameter must be provided")

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

            keys = set.intersection(*named_sets)
            logger.info(f"Keys: {keys}")

        else:
            keys = tel_keys | mailto_keys | name_keys

        if not keys:
            return []

        return [key.split(":")[1] for key in keys]

    except Exception as e:
        logger.error("Error in search_vcons: %s", str(e))
        raise HTTPException(status_code=500, detail="An error occurred during the search")


@api_router.post(
    "/vcon",
    response_model=Vcon,
    summary="Inserts a vCon into the database",
    description="How to insert a vCon into the database.",
    tags=["vcon"],
)
async def post_vcon(inbound_vcon: Vcon, ingress_lists: Optional[List[str]] = Query(None)):
    try:
        print(type(inbound_vcon))
        dict_vcon = inbound_vcon.model_dump()
        dict_vcon["uuid"] = str(inbound_vcon.uuid)
        key = f"vcon:{str(dict_vcon['uuid'])}"
        created_at = datetime.datetime.fromisoformat(str(dict_vcon["created_at"]))
        dict_vcon["created_at"] = created_at.isoformat()
        timestamp = int(created_at.timestamp())

        logger.debug("Posting vcon %s len %d", inbound_vcon.uuid, len(dict_vcon))
        await redis_async.json().set(key, "$", dict_vcon)
        logger.debug("Adding vcon %s to sorted set", inbound_vcon.uuid)
        await add_vcon_to_set(key, timestamp)

        logger.debug("Adding vcon %s to parties sets", inbound_vcon.uuid)
        await index_vcon(inbound_vcon.uuid)

        if ingress_lists:
            for ingress_list in ingress_lists:
                await redis_async.rpush(ingress_list, str(inbound_vcon.uuid))
                logger.info(f"Inserted vCon ID {inbound_vcon.uuid} into ingress list {ingress_list}")

    except Exception:
        logger.info(traceback.format_exc())
        return None
    logger.debug("Posted vcon %s len %d", inbound_vcon.uuid, len(dict_vcon))
    return JSONResponse(content=dict_vcon, status_code=201)


@api_router.delete(
    "/vcon/{vcon_uuid}",
    status_code=204,
    summary="Deletes a particular vCon by UUID",
    description="How to remove a vCon from the conserver.",
    tags=["vcon"],
)
async def delete_vcon(vcon_uuid: UUID):
    try:
        await redis_async.json().delete(f"vcon:{str(vcon_uuid)}")
    except Exception:
        logger.info(traceback.format_exc())
        raise HTTPException(status_code=500)


@api_router.post(
    "/vcon/ingress",
    status_code=204,
    summary="Inserts a vCon UUID into one or more chains",
    description="Inserts a vCon UUID into one or more chains.",
    tags=["chain"],
)
async def post_vcon_ingress(vcon_uuids: List[str], ingress_list: str):
    try:
        for vcon_id in vcon_uuids:
            await redis_async.rpush(
                ingress_list,
                vcon_id,
            )
    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


@api_router.get(
    "/vcon/count",
    status_code=204,
    summary="Returns the number of vCons at the end of a chain",
    description="Returns the number of vCons at the end of a chain.",
    tags=["chain"],
)
async def get_vcon_count(egress_list: str):
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
    try:
        with open(os.getenv("CONSERVER_CONFIG_FILE"), "r") as f:
            config = yaml.safe_load(f)
        return JSONResponse(content=config)

    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


@api_router.post(
    "/config",
    status_code=204,
    summary="Updates the config file for the conserver",
    description="Updates the config file for the conserver",
    tags=["config"],
)
async def post_config(config: Dict):
    try:
        with open(os.getenv("CONSERVER_CONFIG_FILE"), "w") as f:
            yaml.dump(config, f)

    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


@api_router.post(
    "/dlq/reprocess",
    status_code=200,
    summary="Reprocess the dead letter queue",
    description="Move the dead letter queue vcons back to the ingress chain",
    tags=["dlq"],
)
async def post_dlq_reprocess(ingress_list: str):
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
    dlq_name = get_ingress_list_dlq_name(ingress_list)
    vcons = await redis_async.lrange(dlq_name, 0, -1)
    return JSONResponse(content=vcons)


async def index_vcon(uuid):
    key = "vcon:" + str(uuid)
    vcon = await redis_async.json().get(key)
    created_at = datetime.datetime.fromisoformat(vcon["created_at"])
    timestamp = int(created_at.timestamp())
    vcon_uuid = vcon["uuid"]
    await add_vcon_to_set(key, timestamp)

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
    try:
        vcon_keys = await redis_async.keys("vcon:*")
        for key in vcon_keys:
            uuid = key.split(":")[1]
            await index_vcon(uuid)

        return JSONResponse(content=len(vcon_keys))

    except Exception as e:
        logger.info("Error: {}".format(e))
        raise HTTPException(status_code=500)


app.include_router(api_router, dependencies=[Security(get_api_key, scopes=[])])
