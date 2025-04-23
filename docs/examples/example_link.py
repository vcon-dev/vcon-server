"""Example Link Module for vcon-server

This module demonstrates the basic structure of a link module.
It acts as a simple filter that forwards vCons based on a configurable condition.
"""

from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

# Initialize logger
logger = init_logger(__name__)

# Default options
default_options = {
    "field_path": "metadata.title",  # Dot path to the field to check
    "contains": None,                # String to look for
    "matches_regex": None,           # Regex pattern to match
    "exists": True,                  # Whether the field should exist
    "forward_matches": True,         # Forward if condition is met, otherwise drop
}

def _get_field_value(vcon_dict, field_path):
    """Get a field value from a nested dictionary using dot notation.
    
    Args:
        vcon_dict: vCon as dictionary
        field_path: Path to the field using dot notation (e.g., "metadata.title")
        
    Returns:
        The field value or None if not found
    """
    parts = field_path.split('.')
    current = vcon_dict
    
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    
    return current

def run(vcon_uuid, link_name, opts=default_options):
    """Example link that filters vCons based on field criteria.
    
    Args:
        vcon_uuid: UUID of the vCon to process
        link_name: Name of this link instance
        opts: Options from config.yml
        
    Returns:
        vcon_uuid if processing should continue, None to stop chain
    """
    # Merge provided options with defaults
    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts
    
    logger.info(f"Starting example link {link_name} for vCon: {vcon_uuid}")
    
    try:
        # Get vCon from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        vcon_dict = vcon.to_dict()
        
        # Get the field value
        field_value = _get_field_value(vcon_dict, opts["field_path"])
        
        # Check conditions
        matches = False
        
        # Check if field exists
        if opts["exists"] is not None:
            field_exists = field_value is not None
            if field_exists != opts["exists"]:
                matches = False
                logger.info(f"Field {opts['field_path']} exists={field_exists}, expected={opts['exists']}")
            else:
                matches = True
        
        # Check for specific content if the field exists
        if field_value is not None:
            # String contains check
            if opts["contains"] is not None:
                if isinstance(field_value, str) and opts["contains"] in field_value:
                    matches = True
                    logger.info(f"Field {opts['field_path']} contains '{opts['contains']}'")
                else:
                    matches = False
            
            # Regex match check
            if opts["matches_regex"] is not None:
                import re
                if isinstance(field_value, str) and re.search(opts["matches_regex"], field_value):
                    matches = True
                    logger.info(f"Field {opts['field_path']} matches regex '{opts['matches_regex']}'")
                else:
                    matches = False
        
        # Determine whether to forward
        should_forward = matches if opts["forward_matches"] else not matches
        
        if should_forward:
            logger.info(f"vCon {vcon_uuid} matches criteria, forwarding")
            return vcon_uuid
        else:
            logger.info(f"vCon {vcon_uuid} does not match criteria, stopping chain")
            return None
            
    except Exception as e:
        logger.error(f"Error processing vCon {vcon_uuid} with example link: {e}")
        return None  # Stop chain processing on error