from redis_mgr import redis
from lib.logging_utils import init_logger
import json
import requests
from typing import Dict, List, Any, Optional

logger = init_logger(__name__)

# Default options that control which elements to remove
default_options = {
    "remove_dialog_body": False,  # Remove body content from dialogs
    "post_media_to_url": "",      # URL endpoint to store media (if empty, media is just removed)
    "remove_analysis": False,     # Remove all analysis data
    "remove_attachment_types": [], # List of attachment types to remove (e.g., ["image/jpeg", "audio/mp3"])
    "remove_system_prompts": False, # Remove system_prompt keys to prevent LLM instruction insertion
}

def run(vcon_uuid, link_name, opts=default_options):
    logger.debug("Starting diet::run")
    
    # Merge provided options with defaults
    options = {**default_options, **opts}
    
    # Load vCon from Redis using JSON.GET
    vcon = redis.json().get(f"vcon:{vcon_uuid}")
    if not vcon:
        logger.error(f"vCon {vcon_uuid} not found in Redis")
        return vcon_uuid
    
    # No need for json.loads since JSON.GET returns Python objects directly
    
    # Process dialogs
    if "dialogs" in vcon:
        for dialog in vcon["dialog"]:
            if options["remove_dialog_body"] and "body" in dialog:
                if options["post_media_to_url"] and dialog.get("body"):
                    try:
                        # Post the body content to the specified URL
                        response = requests.post(
                            options["post_media_to_url"],
                            json={"content": dialog["body"], "vcon_uuid": vcon_uuid, "dialog_id": dialog.get("id", "")}
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
