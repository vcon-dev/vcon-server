import os
import requests
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from links.scitt import create_hashed_signed_statement
from starlette.status import HTTP_404_NOT_FOUND
import hashlib
import json
import requests

logger = init_logger(__name__)

# Increment for any API/attribute changes
link_version = "0.1.0"

default_options = {
    "client_id": "<set-in-config.yml>",
    "client_secret": "<set-in-config.yml>",
    "scrapi_url": "https://app.datatrails.ai/archivist/v2",
    "auth_url": "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
    "signing_key_path": None,
    "message": None,
    "issuer": "ANONYMOUS CONSERVER",
}


def run(
    vcon_uuid: str,
    link_name: str,
    opts: dict = default_options
) -> str:
    """
    Main function to run the SCITT link.

    This function creates or updates an asset in DataTrails based on the vCon data,
    and records an event for the asset.

    Args:
        vcon_uuid (str): UUID of the vCon to process.
        link_name (str): Name of the link (for logging purposes).
        opts (dict): Options for the link, including API URLs and credentials.

    Returns:
        str: The UUID of the processed vCon.

    Raises:
        ValueError: If client_id or client_secret is not provided in the options.
    """
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}: {link_name} plugin for: {vcon_uuid}")
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    if not opts["client_id"] or not opts["client_secret"]:
        raise ValueError("DataTrails client ID and client secret must be provided")

    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    if not vcon:
        logger.info(f"{link_name}: vCon not found: {vcon_uuid}") 
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"vCon not found: {vcon_uuid}"
        )

    # Set the subject to the vcon identifier
    subject = vcon.subject or f"vcon://{vcon_uuid}"

    # SCITT metadata for the vCon
    meta_map = {
        "vcon_operation" : opts["vcon_operation"]
    }
    # Set the payload to the hash of the vCon
    # consistent with  
    # payload_hash_alg, payload_preimage_content_type are consistent with
    # cose-hash-envelope: https://datatracker.ietf.org/doc/draft-steele-cose-hash-envelope
    payload = vcon.hash
    # TODO: pull hash_alg from the vcon
    payload_hash_alg = "SHA-256"
    payload_preimage_content_type = "application/vcon+json"
    # TODO: pull the payload_location from the vcon.url
    # payload_location = vcon.url

    signing_key_path = os.path.join(opts["signing_key_path"])
    signing_key = create_hashed_signed_statement.open_signing_key(signing_key_path)
    signed_statement = create_hashed_signed_statement.create_hashed_signed_statement(
        issuer=opts["issuer"],
        signing_key=signing_key,
        subject=subject,
        kid=key_id,
        meta_map=meta_map,
        payload=payload_hash,
        payload_hash_alg=payload_hash_alg,
        payload_location=payload_location,
        pre_image_content_type="application/vcon+json"
    )

    # Get the token using the requests library
    token_response = requests.post(
        "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
        data={
            "grant_type": "client_credentials",
            "client_id": opts["client_id"],
            "client_secret": opts["client_secret"],
        },
    )
    token = token_response.json()["access_token"]

    headers = {"Content-Type": "text/plain", "Authorization": f"Bearer {token}"}

    response = requests.request(
        "POST",
        "https://app.datatrails.ai/archivist/v1/publicscitt/entries",
        headers=headers,
        data=signed_statement,
    )

    print("Response:", response.text)

    return vcon_uuid
