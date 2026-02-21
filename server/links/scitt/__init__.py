import os
from links.scitt import create_hashed_signed_statement, register_signed_statement
from fastapi import HTTPException
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from starlette.status import HTTP_404_NOT_FOUND

logger = init_logger(__name__)

# Increment for any API/attribute changes
link_version = "0.2.0"

default_options = {
    "scrapi_url": "http://scittles:8000",
    "signing_key_path": "/etc/scitt/signing-key.pem",
    "issuer": "conserver",
    "key_id": "conserver-key-1",
    "vcon_operation": "vcon_created",
    "store_receipt": True,
}

def run(
    vcon_uuid: str,
    link_name: str,
    opts: dict = default_options
) -> str:
    """
    SCITT lifecycle registration link.

    Creates a COSE Sign1 signed statement from the vCon hash and registers
    it on a SCRAPI-compatible Transparency Service (SCITTLEs).

    The vcon_operation option controls the lifecycle event type:
    - "vcon_created": registered before transcription
    - "vcon_enhanced": registered after transcription

    Args:
        vcon_uuid: UUID of the vCon to process.
        link_name: Name of the link instance (for logging).
        opts: Configuration options.

    Returns:
        The UUID of the processed vCon.
    """
    module_name = __name__.split(".")[-1]
    logger.info(f"Starting {module_name}: {link_name} for: {vcon_uuid}")
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    # Get the vCon from Redis
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    if not vcon:
        logger.info(f"{link_name}: vCon not found: {vcon_uuid}")
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"vCon not found: {vcon_uuid}"
        )

    # Build the COSE Sign1 signed statement
    subject = vcon.subject or f"vcon://{vcon_uuid}"
    meta_map = {
        "vcon_operation": opts["vcon_operation"],
    }
    payload = vcon.hash
    payload_hash_alg = "SHA-256"
    payload_location = ""

    signing_key_path = opts["signing_key_path"]
    signing_key = create_hashed_signed_statement.open_signing_key(signing_key_path)

    signed_statement = create_hashed_signed_statement.create_hashed_signed_statement(
        issuer=opts["issuer"],
        signing_key=signing_key,
        subject=subject,
        kid=opts["key_id"].encode("utf-8"),
        meta_map=meta_map,
        payload=payload.encode("utf-8"),
        payload_hash_alg=payload_hash_alg,
        payload_location=payload_location,
        pre_image_content_type="application/vcon+json",
    )
    logger.info(f"{link_name}: Created signed statement for {vcon_uuid} ({opts['vcon_operation']})")

    # Register via SCRAPI
    scrapi_url = opts["scrapi_url"]
    result = register_signed_statement.register_statement(scrapi_url, signed_statement)
    logger.info(f"{link_name}: Registered entry_id={result['entry_id']} for {vcon_uuid}")

    # Store receipt as analysis entry on the vCon
    if opts.get("store_receipt", True):
        vcon.add_analysis(
            type="scitt_receipt",
            dialog=0,
            vendor="scittles",
            body={
                "entry_id": result["entry_id"],
                "vcon_operation": opts["vcon_operation"],
                "vcon_hash": payload,
                "scrapi_url": scrapi_url,
            },
        )
        vcon_redis.store_vcon(vcon)
        logger.info(f"{link_name}: Stored SCITT receipt for {vcon_uuid}")

    return vcon_uuid
