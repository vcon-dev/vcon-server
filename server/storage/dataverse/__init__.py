"""
Microsoft Dataverse storage module for vcon-server

This module provides integration with Microsoft Dataverse for storing vCons. It uses
the Dataverse Web API with MSAL authentication to store vCons as entities in a
Microsoft Dataverse environment.

The module supports:
- Storing complete vCon objects as JSON in a custom entity
- Authentication via Azure AD with MSAL
- Error handling and automatic token refresh
- Configurable entity name and field mappings
"""

from typing import Optional, Dict, Any, List
import json
import uuid
import requests
import msal
from datetime import datetime

from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

# Default configuration for Dataverse connection
default_options = {
    "name": "dataverse",
    "url": "https://org.crm.dynamics.com",  # Dynamics 365/Dataverse URL
    "api_version": "9.2",                   # Dataverse API version
    "tenant_id": "",                        # Azure AD tenant ID
    "client_id": "",                        # Azure AD application (client) ID
    "client_secret": "",                    # Azure AD client secret
    "entity_name": "vcon_storage",          # Custom entity name in Dataverse
    "uuid_field": "vcon_uuid",              # Field name for vCon UUID
    "data_field": "vcon_data",              # Field name for vCon JSON data
    "subject_field": "vcon_subject",        # Field name for vCon subject
    "created_at_field": "vcon_created_at",  # Field name for vCon creation date
}

def get_access_token(opts: Dict[str, Any]) -> Optional[str]:
    """
    Acquire an access token for Dataverse API using MSAL.
    
    Args:
        opts: Dictionary containing authentication parameters
        
    Returns:
        Optional[str]: Access token if successful, None otherwise
        
    Raises:
        Exception: If authentication parameters are invalid
    """
    try:
        # Create a ConfidentialClientApplication
        app = msal.ConfidentialClientApplication(
            client_id=opts["client_id"],
            client_credential=opts["client_secret"],
            authority=f"https://login.microsoftonline.com/{opts['tenant_id']}"
        )

        # Acquire token for client
        scopes = [f"{opts['url']}/.default"]
        result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" in result:
            logger.debug("Successfully acquired token for Dataverse API")
            return result["access_token"]
        else:
            logger.error(f"Failed to acquire token: {result.get('error')}: {result.get('error_description')}")
            return None
    except Exception as e:
        logger.error(f"Error acquiring access token: {str(e)}")
        return None

def create_dataverse_session(opts: Dict[str, Any]) -> Optional[requests.Session]:
    """
    Create a requests session with authentication headers for Dataverse API.
    
    Args:
        opts: Dictionary containing authentication parameters
        
    Returns:
        Optional[requests.Session]: Configured session if successful, None otherwise
    """
    token = get_access_token(opts)
    if not token:
        return None
    
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "OData-MaxVersion": "4.0",
        "OData-Version": "4.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Prefer": "odata.include-annotations=*"
    })
    
    return session

def save(
    vcon_uuid: str,
    opts: Dict[str, Any] = default_options,
) -> None:
    """
    Save a vCon to Microsoft Dataverse storage.
    
    Args:
        vcon_uuid: UUID of the vCon to save
        opts: Dictionary containing Dataverse connection parameters
        
    Raises:
        Exception: If there's an error saving the vCon
    """
    logger.info(f"Starting the Dataverse storage for vCon: {vcon_uuid}")
    session = None
    
    try:
        # Get vCon data from Redis
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Create Dataverse session
        session = create_dataverse_session(opts)
        if not session:
            raise Exception("Failed to create Dataverse session with valid token")
        
        # Check if entity already exists
        entity_exists = False
        entity_id = None
        
        try:
            # Query for existing entity
            filter_query = f"${opts['uuid_field']} eq '{vcon_uuid}'"
            url = f"{opts['url']}/api/data/v{opts['api_version']}/{opts['entity_name']}?$filter={filter_query}"
            response = session.get(url)
            response.raise_for_status()
            
            data = response.json()
            entities = data.get('value', [])
            
            if entities:
                entity_exists = True
                entity_id = entities[0].get('id')
                logger.debug(f"Found existing entity for vCon {vcon_uuid} with ID {entity_id}")
        except Exception as e:
            logger.debug(f"Error checking for existing entity: {str(e)}")
            # Continue with create operation
        
        # Prepare vCon data for Dataverse
        vcon_dict = vcon.to_dict()
        vcon_json = json.dumps(vcon_dict)
        
        # Use the created_at timestamp from vCon or current time as fallback
        created_at = vcon.created_at if vcon.created_at else datetime.now().isoformat()
        
        # Prepare entity data
        entity_data = {
            opts['uuid_field']: vcon_uuid,
            opts['data_field']: vcon_json,
            opts['subject_field']: vcon.subject,
            opts['created_at_field']: created_at
        }
        
        if entity_exists and entity_id:
            # Update existing entity
            url = f"{opts['url']}/api/data/v{opts['api_version']}/{opts['entity_name']}({entity_id})"
            response = session.patch(url, json=entity_data)
        else:
            # Create new entity
            url = f"{opts['url']}/api/data/v{opts['api_version']}/{opts['entity_name']}"
            response = session.post(url, json=entity_data)
        
        response.raise_for_status()
        logger.info(f"Successfully saved vCon {vcon_uuid} to Dataverse")
        
    except Exception as e:
        logger.error(f"Dataverse storage plugin: failed to insert vCon: {vcon_uuid}, error: {str(e)}")
        raise e

def get(
    vcon_uuid: str,
    opts: Dict[str, Any] = default_options,
) -> Optional[dict]:
    """
    Get a vCon from Microsoft Dataverse storage by UUID.
    
    Args:
        vcon_uuid: UUID of the vCon to retrieve
        opts: Dictionary containing Dataverse connection parameters
        
    Returns:
        Optional[dict]: The vCon data as a dictionary if found, None otherwise
    """
    logger.info(f"Starting the Dataverse storage get for vCon: {vcon_uuid}")
    session = None
    
    try:
        # Create Dataverse session
        session = create_dataverse_session(opts)
        if not session:
            logger.error("Failed to create Dataverse session with valid token")
            return None
        
        # Query for entity by UUID
        filter_query = f"${opts['uuid_field']} eq '{vcon_uuid}'"
        url = f"{opts['url']}/api/data/v{opts['api_version']}/{opts['entity_name']}?$filter={filter_query}"
        
        response = session.get(url)
        response.raise_for_status()
        
        data = response.json()
        entities = data.get('value', [])
        
        if not entities:
            logger.info(f"vCon {vcon_uuid} not found in Dataverse storage")
            return None
        
        # Get the vCon data from the entity
        entity = entities[0]
        vcon_data_json = entity.get(opts['data_field'])
        
        if not vcon_data_json:
            logger.warning(f"Entity found for vCon {vcon_uuid} but no vCon data")
            return None
        
        try:
            # Parse the vCon data from JSON
            vcon_data = json.loads(vcon_data_json)
            return vcon_data
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding vCon JSON data: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Dataverse storage plugin: failed to get vCon: {vcon_uuid}, error: {str(e)}")
        return None