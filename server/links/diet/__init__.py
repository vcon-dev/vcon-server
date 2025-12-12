from redis_mgr import redis
from lib.logging_utils import init_logger
import json
import requests
import uuid
import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Any, Optional

logger = init_logger(__name__)
logger.info("MDO THIS SHOULD PRINT")

_REDACTED = "[REDACTED]"


def _redact_option_value(key: str, value: Any) -> Any:
    """
    Redact sensitive option values before logging.

    This prevents leaking secrets (for example AWS credentials) into logs.
    """
    key_l = (key or "").lower()
    if (
        key_l == "aws_secret_access_key"
        or "secret" in key_l
        or "password" in key_l
        or "token" in key_l
        or key_l.endswith("_secret")
    ):
        return _REDACTED
    return value


# Default options that control which elements to remove
default_options = {
    "remove_dialog_body": False,  # Remove body content from dialogs
    "post_media_to_url": "",      # URL endpoint to store media (if empty, media is just removed)
    "remove_analysis": False,     # Remove all analysis data
    "remove_attachment_types": [], # List of attachment types to remove (e.g., ["image/jpeg", "audio/mp3"])
    "remove_system_prompts": False, # Remove system_prompt keys to prevent LLM instruction insertion
    # S3 storage options for dialog bodies
    "s3_bucket": "",              # S3 bucket name for storing dialog bodies
    "s3_path": "",                # Optional path prefix within the bucket
    "aws_access_key_id": "",      # AWS access key ID
    "aws_secret_access_key": "",  # AWS secret access key
    "aws_region": "us-east-1",    # AWS region (default: us-east-1)
    "presigned_url_expiration": None,  # Presigned URL expiration in seconds (None = no expiration/default 1 hour)
}


def _get_s3_client(options: Dict[str, Any]):
    """Create and return an S3 client with the provided credentials."""
    return boto3.client(
        "s3",
        aws_access_key_id=options["aws_access_key_id"],
        aws_secret_access_key=options["aws_secret_access_key"],
        region_name=options.get("aws_region", "us-east-1"),
    )


def _upload_to_s3_and_get_presigned_url(
    content: str,
    vcon_uuid: str,
    dialog_id: str,
    options: Dict[str, Any]
) -> Optional[str]:
    """
    Upload dialog body content to S3 and return a presigned URL.

    Args:
        content: The dialog body content to upload
        vcon_uuid: The vCon UUID
        dialog_id: The dialog ID
        options: Configuration options including S3 credentials and bucket info

    Returns:
        Presigned URL to access the uploaded content, or None if upload fails
    """
    try:
        s3 = _get_s3_client(options)

        # Generate a unique key for this dialog body
        unique_id = str(uuid.uuid4())
        key = f"{dialog_id}_{unique_id}.txt" if dialog_id else f"{unique_id}.txt"

        # Add vcon_uuid as a directory level
        key = f"{vcon_uuid}/{key}"

        # Add optional path prefix
        if options.get("s3_path"):
            key = f"{options['s3_path']}/{key}"

        bucket = options["s3_bucket"]

        # Upload the content
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode("utf-8") if isinstance(content, str) else content,
            ContentType="text/plain",
        )

        logger.info(f"Successfully uploaded dialog body to s3://{bucket}/{key}")

        # Generate presigned URL
        expiration = options.get("presigned_url_expiration")
        if expiration is None:
            # Default to 1 hour (3600 seconds) if not specified
            expiration = 3600

        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )

        logger.info(f"Generated presigned URL with expiration {expiration}s")
        return presigned_url

    except ClientError as e:
        logger.error(f"S3 client error uploading dialog body: {e}")
        return None
    except Exception as e:
        logger.error(f"Exception uploading dialog body to S3: {e}")
        return None


def run(vcon_uuid, link_name, opts=default_options):
    logger.info("Starting diet::run")
    
    # Merge provided options with defaults
    options = {**default_options, **opts}
    
    for key, value in options.items():
        logger.info("diet::%s: %s", key, _redact_option_value(key, value))

    # Load vCon from Redis using JSON.GET
    vcon = redis.json().get(f"vcon:{vcon_uuid}")
    if not vcon:
        logger.error(f"vCon {vcon_uuid} not found in Redis")
        return vcon_uuid
    
    # No need for json.loads since JSON.GET returns Python objects directly

    # Process dialogs
    if "dialog" in vcon:
        logger.info("diet::got dialogs")
        for dialog in vcon["dialog"]:
            logger.info("diet::got dialog")
            if options["remove_dialog_body"] and "body" in dialog:
                logger.info("diet::remove_dialog_body AND body")
                dialog_body = dialog.get("body")
                dialog_id = dialog.get("id", "")

                # Check if S3 storage is configured
                if options.get("s3_bucket") and dialog_body:
                    logger.info("diet::uploading to S3")
                    presigned_url = _upload_to_s3_and_get_presigned_url(
                        dialog_body, vcon_uuid, dialog_id, options
                    )
                    if presigned_url:
                        dialog["body"] = presigned_url
                        dialog["body_type"] = "url"
                    else:
                        logger.error("Failed to upload to S3, removing body")
                        dialog["body"] = ""
                elif options["post_media_to_url"] and dialog_body:
                    try:
                        # Post the body content to the specified URL
                        response = requests.post(
                            options["post_media_to_url"],
                            json={"content": dialog_body, "vcon_uuid": vcon_uuid, "dialog_id": dialog_id}
                        )
                        if response.status_code == 200:
                            # Replace body with the URL to the stored content
                            media_url = response.json().get("url")
                            if media_url:
                                dialog["body"] = media_url
                                dialog["body_type"] = "url"
                            else:
                                dialog["body"] = ""
                        else:
                            logger.error(f"Failed to post media: {response.status_code}")
                            dialog["body"] = ""
                    except Exception as e:
                        logger.error(f"Exception posting media: {e}")
                        dialog["body"] = ""
                else:
                    logger.info("diet::REMOVING BODY ONLY")
                    dialog["body"] = ""
    
    # Remove analysis if specified
    if options["remove_analysis"] and "analysis" in vcon:
        del vcon["analysis"]
    
    # Remove attachments by type
    if options["remove_attachment_types"] and "attachments" in vcon:
        if len(options["remove_attachment_types"]) > 0:
            vcon["attachments"] = [
                attachment for attachment in vcon["attachments"]
                if attachment.get("mime_type") not in options["remove_attachment_types"]
            ]
    
    # Remove system_prompt keys to prevent LLM instruction insertion
    if options["remove_system_prompts"]:
        remove_system_prompts_recursive(vcon)
    
    # Save the modified vCon back to Redis using JSON.SET
    redis.json().set(f"vcon:{vcon_uuid}", "$", vcon)
    logger.info(f"Successfully applied diet to vCon {vcon_uuid}")
    
    return vcon_uuid

def remove_system_prompts_recursive(obj):
    """
    Recursively search through an object and remove any "system_prompt" keys.
    Works on both dictionaries and lists.
    
    This function traverses the entire object structure (dictionaries and lists)
    to find and remove any keys named "system_prompt". This is a security measure
    to prevent potential LLM instruction injection attacks.
    
    Args:
        obj: The object to process. Can be a dictionary or list, potentially
             containing nested dictionaries and lists.
    
    Returns:
        None: The function modifies the input object in-place.
    
    Note:
        This function operates recursively and modifies the object in-place.
        It only processes dictionaries and lists, ignoring other data types.
    """
    if isinstance(obj, dict):
        # Remove the system_prompt key if it exists
        if "system_prompt" in obj:
            del obj["system_prompt"]
        
        # Recursively process all values in the dictionary
        for key in list(obj.keys()):
            # We use list(obj.keys()) to create a copy of the keys list
            # This prevents issues if the dictionary is modified during iteration
            if isinstance(obj[key], (dict, list)):
                remove_system_prompts_recursive(obj[key])
    
    elif isinstance(obj, list):
        # Recursively process all items in the list
        for index, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                remove_system_prompts_recursive(item)
