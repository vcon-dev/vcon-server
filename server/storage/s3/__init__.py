import json
from datetime import datetime
from typing import Optional
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
import boto3

logger = init_logger(__name__)


default_options = {}


def _create_s3_client(opts: dict):
    """Create an S3 client with the provided options.

    Required options:
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key

    Optional options:
        aws_region: AWS region (e.g., 'us-east-1', 'us-west-2')
        endpoint_url: Custom endpoint URL for S3-compatible services
    """
    client_kwargs = {
        "aws_access_key_id": opts["aws_access_key_id"],
        "aws_secret_access_key": opts["aws_secret_access_key"],
    }

    if opts.get("aws_region"):
        client_kwargs["region_name"] = opts["aws_region"]

    if opts.get("endpoint_url"):
        client_kwargs["endpoint_url"] = opts["endpoint_url"]

    return boto3.client("s3", **client_kwargs)


def _date_prefix(created_at: str) -> str:
    """Return the YYYY/MM/DD folder prefix derived from an ISO timestamp."""
    return datetime.fromisoformat(created_at).strftime("%Y/%m/%d")


def _build_lookup_key(vcon_uuid: str, s3_path: Optional[str] = None) -> str:
    """Build the S3 key for the lookup pointer file.

    Args:
        vcon_uuid: The vCon UUID
        s3_path: Optional prefix path in the S3 bucket

    Returns:
        S3 key in format: [s3_path/]lookup/<uuid>
    """
    key = f"lookup/{vcon_uuid}.txt"
    if not s3_path:
        return key
    return f"{s3_path.rstrip('/')}/{key}"


def _build_s3_key(vcon_uuid: str, date_path: Optional[str] = None, s3_path: Optional[str] = None) -> str:
    """Build the S3 object key for a vCon.

    Args:
        vcon_uuid: The vCon UUID
        date_path: Pre-computed YYYY/MM/DD prefix (from _date_prefix).
                   If provided, creates date-based folder structure.
        s3_path: Optional prefix path in the S3 bucket

    Returns:
        S3 key in format: [s3_path/][YYYY/MM/DD/]uuid.vcon
    """
    key = f"{date_path}/{vcon_uuid}.vcon" if date_path else f"{vcon_uuid}.vcon"
    if not s3_path:
        return key
    return f"{s3_path.rstrip('/')}/{key}"


def save(
    vcon_uuid,
    opts=default_options,
):
    logger.info("Starting the S3 storage for vCon: %s", vcon_uuid)
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        s3 = _create_s3_client(opts)

        date_path = _date_prefix(vcon.created_at)
        destination_directory = _build_s3_key(vcon_uuid, date_path, opts.get("s3_path"))
        s3.put_object(
            Bucket=opts["aws_bucket"], Key=destination_directory, Body=vcon.dumps()
        )

        lookup_key = _build_lookup_key(vcon_uuid, opts.get("s3_path"))
        s3.put_object(
            Bucket=opts["aws_bucket"], Key=lookup_key, Body=date_path.encode()
        )
        logger.info(f"Finished S3 storage for vCon: {vcon_uuid}")
    except Exception as e:
        logger.error(
            f"s3 storage plugin: failed to insert vCon: {vcon_uuid}, error: {e}"
        )
        raise e

def get(vcon_uuid: str, opts=default_options) -> Optional[dict]:
    """Get a vCon from S3 by UUID.

    Uses a lookup pointer file (lookup/<uuid>) to resolve the date-based path
    before fetching the actual vCon object.
    """
    try:
        s3 = _create_s3_client(opts)

        lookup_key = _build_lookup_key(vcon_uuid, opts.get("s3_path"))
        lookup_response = s3.get_object(Bucket=opts["aws_bucket"], Key=lookup_key)
        date_path = lookup_response['Body'].read().decode('utf-8').strip()

        key = _build_s3_key(vcon_uuid, date_path, opts.get("s3_path"))

        response = s3.get_object(Bucket=opts["aws_bucket"], Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))

    except Exception as e:
        logger.error(f"s3 storage plugin: failed to get vCon: {vcon_uuid}, error: {e}")
        return None


def delete(vcon_uuid: str, opts=default_options) -> bool:
    """Delete a vCon and its lookup pointer from S3.

    Returns True if deleted, False if not found or on error.
    """
    try:
        s3 = _create_s3_client(opts)
        bucket = opts["aws_bucket"]
        s3_path = opts.get("s3_path")

        lookup_key = _build_lookup_key(vcon_uuid, s3_path)
        lookup_response = s3.get_object(Bucket=bucket, Key=lookup_key)
        date_path = lookup_response['Body'].read().decode('utf-8').strip()

        vcon_key = _build_s3_key(vcon_uuid, date_path, s3_path)
        s3.delete_object(Bucket=bucket, Key=vcon_key)
        s3.delete_object(Bucket=bucket, Key=lookup_key)

        logger.info(f"s3 storage plugin: deleted vCon {vcon_uuid}")
        return True

    except Exception as e:
        logger.error(f"s3 storage plugin: failed to delete vCon: {vcon_uuid}, error: {e}")
        return False
