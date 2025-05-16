import json
from typing import Optional
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
import boto3
from datetime import datetime

logger = init_logger(__name__)


default_options = {}


def save(
    vcon_uuid,
    opts=default_options,
):
    logger.info("Starting the S3 storage for vCon: %s", vcon_uuid)
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        s3 = boto3.client(
            "s3",
            aws_access_key_id=opts["aws_access_key_id"],
            aws_secret_access_key=opts["aws_secret_access_key"],
        )

        s3_path = opts.get("s3_path")
        created_at = datetime.fromisoformat(vcon.created_at)
        timestamp = created_at.strftime("%Y/%m/%d")
        key = vcon_uuid + ".vcon"
        destination_directory = f"{timestamp}/{key}"
        if s3_path:
            destination_directory = s3_path + "/" + destination_directory
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
        s3 = boto3.client(
            "s3",
            aws_access_key_id=opts["aws_access_key_id"],
            aws_secret_access_key=opts["aws_secret_access_key"],
        )
        
        s3_path = opts.get("s3_path", "")
        key = f"{s3_path}/{vcon_uuid}.vcon" if s3_path else f"{vcon_uuid}.vcon"
        
        response = s3.get_object(Bucket=opts["aws_bucket"], Key=key)
        return json.loads(response['Body'].read().decode('utf-8'))
        
    except Exception as e:
        logger.error(f"s3 storage plugin: failed to get vCon: {vcon_uuid}, error: {e}")
        return None
