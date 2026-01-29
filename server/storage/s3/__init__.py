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


def _build_s3_key(vcon_uuid: str, created_at: Optional[str] = None, s3_path: Optional[str] = None) -> str:
    """Build the S3 object key for a vCon with date-based folder structure.
    
    Args:
        vcon_uuid: The vCon UUID
        created_at: ISO format timestamp from the vCon's created_at field.
                    If provided, creates date-based folder structure (YYYY/MM/DD).
        s3_path: Optional prefix path in the S3 bucket
    
    Returns:
        S3 key in format: [s3_path/][YYYY/MM/DD/]uuid.vcon
    """
    if created_at:
        timestamp = datetime.fromisoformat(created_at).strftime("%Y/%m/%d")
        key = f"{timestamp}/{vcon_uuid}.vcon"
    else:
        key = f"{vcon_uuid}.vcon"
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

        destination_directory = _build_s3_key(vcon_uuid, vcon.created_at, opts.get("s3_path"))
        s3.put_object(
            Bucket=opts["aws_bucket"], Key=destination_directory, Body=vcon.dumps()
        )
        logger.info(f"Finished S3 storage for vCon: {vcon_uuid}")
    except Exception as e:
        logger.error(
            f"s3 storage plugin: failed to insert vCon: {vcon_uuid}, error: {e}"
        )
        raise e

def get(vcon_uuid: str, opts=default_options) -> Optional[dict]:
    """Get a vCon from S3 by UUID."""
    try:
        s3 = _create_s3_client(opts)

        key = _build_s3_key(vcon_uuid, s3_path=opts.get("s3_path"))

        response = s3.get_object(Bucket=opts["aws_bucket"], Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
        
    except Exception as e:
        logger.error(f"s3 storage plugin: failed to get vCon: {vcon_uuid}, error: {e}")
        return None
