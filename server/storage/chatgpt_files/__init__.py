from lib.logging_utils import init_logger
import json
import os
import tempfile
from typing import Dict, Any, Optional
from server.lib.vcon_redis import VconRedis
from openai import OpenAI

logger = init_logger(__name__)

# OpenAI default options
default_options = {
    "organization_key": "org-xxxxx",
    "project_key": "proj_xxxxxxx",
    "api_key": "sk-proj-xxxxxx",
    "vector_store_id": "xxxxxx",
    "purpose": "assistants",
}


def save(vcon_uuid: str, options: Dict[str, str] = None) -> str:
    """Save a vCon to ChatGPT files and add it to a vector store.

    Args:
        vcon_uuid (str): The UUID of the vCon to be saved.
        options (Dict[str, str], optional): Dictionary containing configuration options:
            - organization_key: OpenAI organization identifier
            - project_key: OpenAI project identifier
            - api_key: OpenAI API key
            - vector_store_id: ID of the vector store to use
            - purpose: Purpose of the file (typically "assistants")
            Defaults to None, which will use default_options.

    Returns:
        str: The ID of the created file in OpenAI

    Raises:
        ValueError: If vcon_uuid is invalid or vCon data cannot be retrieved
        RuntimeError: If there's an error during file creation or vector store operation
        Exception: For any other unexpected errors
    """
    if options is None:
        options = default_options.copy()
    
    logger.info(f"Starting to save vCon {vcon_uuid} to ChatGPT files")
    
    # Validate input
    if not vcon_uuid or not isinstance(vcon_uuid, str):
        error_msg = f"Invalid vCon UUID: {vcon_uuid}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        # Get vCon data using the established VconRedis pattern
        logger.debug(f"Retrieving vCon data for {vcon_uuid} from Redis")
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        if vcon is None:
            error_msg = f"vCon with UUID {vcon_uuid} not found in Redis"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.debug(f"Successfully retrieved vCon data for {vcon_uuid}")
        
        # Convert vCon object to dictionary
        vcon_dict = vcon.to_dict()
        
        # Create a temporary file for the vCon data - explicitly using text mode
        with tempfile.NamedTemporaryFile(mode='w', suffix='.vcon.json', delete=False) as temp_file:
            file_path = temp_file.name
            logger.debug(f"Writing vCon data to temporary file: {file_path}")
            json.dump(vcon_dict, temp_file)
        
        try:
            # Initialize OpenAI client
            logger.debug("Initializing OpenAI client")
            client = OpenAI(
                organization=options["organization_key"],
                project=options["project_key"],
                api_key=options["api_key"],
            )
            
            # Upload file to OpenAI
            logger.info(f"Uploading vCon file to OpenAI with purpose: {options['purpose']}")
            with open(file_path, "rb") as file_data:
                file_response = client.files.create(
                    file=file_data, 
                    purpose=options["purpose"]
                )
            
            file_id = file_response.id
            logger.info(f"File uploaded successfully with ID: {file_id}")
            
            # Add file to vector store
            logger.info(f"Adding file to vector store: {options['vector_store_id']}")
            client.beta.vector_stores.files.create(
                vector_store_id=options["vector_store_id"], 
                file_id=file_id
            )
            
            logger.info(f"Successfully added file {file_id} to vector store")
            return file_id
            
        except Exception as api_error:
            error_msg = f"Error during OpenAI API operations: {str(api_error)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from api_error
            
        finally:
            # Clean up temporary file
            if os.path.exists(file_path):
                logger.debug(f"Removing temporary file: {file_path}")
                os.remove(file_path)
                
    except ValueError as ve:
        # Re-raise ValueError exceptions
        raise
    except RuntimeError as re:
        # Re-raise RuntimeError exceptions
        raise
    except Exception as error:
        error_msg = f"Unexpected error saving vCon {vcon_uuid} to ChatGPT files: {str(error)}"
        logger.error(error_msg)
        raise Exception(error_msg) from error
