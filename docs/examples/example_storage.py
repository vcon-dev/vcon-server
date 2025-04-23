"""Example Storage Module for vcon-server

This module demonstrates the basic structure of a storage module.
It stores vCons as JSON files in a local filesystem directory.
"""

import os
import json
from datetime import datetime
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

# Initialize logger
logger = init_logger(__name__)

# Default options
default_options = {
    "storage_dir": "/tmp/vcons",    # Directory to store vCons
    "use_date_folders": True,       # Organize vCons in date-based folders
    "pretty_print": False,          # Whether to format JSON for readability
}

def save(vcon_uuid, opts=default_options):
    """Save a vCon to the filesystem as JSON.
    
    Args:
        vcon_uuid: UUID of the vCon to save
        opts: Storage configuration options
        
    Raises:
        Exception: If saving fails
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    logger.info(f"Starting filesystem storage for vCon: {vcon_uuid}")
    
    try:
        # Get vCon from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Determine the storage path
        base_dir = opts["storage_dir"]
        
        # Create date-based directory structure if enabled
        if opts["use_date_folders"]:
            current_date = datetime.now()
            date_path = current_date.strftime("%Y/%m/%d")
            storage_path = os.path.join(base_dir, date_path)
        else:
            storage_path = base_dir
            
        # Create directory if it doesn't exist
        os.makedirs(storage_path, exist_ok=True)
        
        # Determine the file path
        file_path = os.path.join(storage_path, f"{vcon_uuid}.json")
        
        # Convert vCon to JSON
        if opts["pretty_print"]:
            json_data = json.dumps(vcon.to_dict(), indent=2)
        else:
            json_data = json.dumps(vcon.to_dict())
            
        # Save to file
        with open(file_path, 'w') as f:
            f.write(json_data)
            
        logger.info(f"Successfully saved vCon {vcon_uuid} to {file_path}")
        
    except Exception as e:
        logger.error(f"Failed to save vCon {vcon_uuid} to filesystem: {e}")
        raise e
        
def get(vcon_uuid, opts=default_options):
    """Retrieve a vCon from filesystem storage.
    
    Args:
        vcon_uuid: UUID of the vCon to retrieve
        opts: Storage configuration options
        
    Returns:
        dict or None: vCon data if found, None otherwise
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    logger.info(f"Retrieving vCon {vcon_uuid} from filesystem")
    
    try:
        # Check the base directory
        base_dir = opts["storage_dir"]
        
        # If date folders are used, we need to search for the file
        if opts["use_date_folders"]:
            # We don't know the date, so we need to search for the file
            for root, _, files in os.walk(base_dir):
                file_name = f"{vcon_uuid}.json"
                if file_name in files:
                    file_path = os.path.join(root, file_name)
                    break
            else:
                # File not found
                logger.warning(f"vCon {vcon_uuid} not found in filesystem")
                return None
        else:
            # Check the direct path
            file_path = os.path.join(base_dir, f"{vcon_uuid}.json")
            if not os.path.exists(file_path):
                logger.warning(f"vCon {vcon_uuid} not found at {file_path}")
                return None
                
        # Read the file
        with open(file_path, 'r') as f:
            vcon_data = json.load(f)
            
        logger.info(f"Successfully retrieved vCon {vcon_uuid} from {file_path}")
        return vcon_data
        
    except Exception as e:
        logger.error(f"Error retrieving vCon {vcon_uuid} from filesystem: {e}")
        return None