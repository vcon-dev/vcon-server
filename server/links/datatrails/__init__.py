import os
import requests
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from starlette.status import HTTP_404_NOT_FOUND
from vcon import Vcon

logger = init_logger(__name__)

# Increment for any API/attribute changes
link_version = "0.1.0.0"

# NOTE: Once DataTrails removes the dependency for assets, 
#       "asset_attributes" will be removed

# NOTE: droid_id is a temporary placeholder to associate an
#       asset with a collection of events
#       once Assets are no longer required, droid_id will be removed
#       droid_id was used, to avoid conflicts with past or future
#       real id's that could be confusing
#       Why droid_id: "these are not the droids your're looking for"

# datatrails_client_id, datatrails_client_secret noted here for reference only
# Set the datatrails_client_id, datatrails_client_secret in the vcon_server/config.yml
default_options = {
    "api_url": "https://app.datatrails.ai/archivist/v2/",
    "auth_url": "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
    "datatrails_client_id": "<set-in-config.yml>",
    "datatrails_client_secret": "<set-in-config.yml>",
    "asset_attributes": {
        "arc_display_type": "vcon_droid",
        "conserver_link_version": link_version
    },
    "event_attributes": {
        "arc_display_type": "vcon",
        "conserver_link_version": link_version,
        "payload_hash_alg": "SHA-256",
        "preimage_content_type": "application/vcon"
    }
}

class DataTrailsAuth:
    """
    Handles authentication for DataTrails API, including token management and refresh.
    """

    def __init__(self, auth_url, datatrails_client_id, datatrails_client_secret):
        """
        Initialize the DataTrailsAuth object

        Args:
            auth_url (str): URL for the authentication endpoint
            datatrails_client_id (str): Client ID for DataTrails API
            datatrails_client_secret (str): Client Secret for DataTrails API
        """
        self.auth_url = auth_url
        self.datatrails_client_id = datatrails_client_id
        self.datatrails_client_secret = datatrails_client_secret
        self.token = None
        self.token_expiry = None

    def get_token(self):
        """
        Get a valid authentication token, refreshing if necessary

        Returns:
            str: A valid authentication token.
        """
        if self.token is None or datetime.now() >= self.token_expiry:
            self._refresh_token()
        return self.token

    def _refresh_token(self):
        """
        Refresh the authentication token and update the token file
        """
        data = {
            "grant_type": "client_credentials",
            "client_id": self.datatrails_client_id,
            "client_secret": self.datatrails_client_secret,
        }
        response = requests.post(self.auth_url, data=data)
        response.raise_for_status()
        token_data = response.json()

        self.token = token_data["access_token"]
        # Set token expiry to 5 minutes before actual expiry for safety
        self.token_expiry = datetime.now() + timedelta(
            seconds=token_data["expires_in"] - 300
        )

#    NOTE: Once DataTrails removes the dependency for assets, 
#    this method can be removed
def get_asset_by_attributes(
    api_url: str, auth: DataTrailsAuth, attributes: dict
) -> dict:
    """
    Assets have minimal information as a temporary anchor 
    for a collection of events.
    Over time, the DataTrails Asset will be deprecated, 
    in lieu of a collection of Events, 
    aligning with a collection of SCITT statements
    In transition to eliminating DataTrails Assets, 
    we need an arbitrary asset to hang events off.
    To avoid creating a new asset for each event or each vCon,
    or thousands of vCons for a single Asset,
    a daily vCon Asset will be created.

    Args:
        api_url (str): Base URL for the DataTrails API
        auth (DataTrailsAuth): Authentication object for DataTrails API
        attributes (dic): a dictionary of attributes to search for

    Returns:
        dict: Data of the found asset

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "Content-Type": "application/json",
    }
    # Searching DataTrails Assets by attributes requires
    # each attribute to be prepended with "attribute."
    params = {}
    for param in attributes:
        params.update(
            {
                f"attributes.{param}": f"{attributes[param]}"
            }
        )

    response = requests.get(
        f"{api_url}/assets",
        params=params,
        headers=headers
    )
    response.raise_for_status()
    return response.json()


#    NOTE: Once DataTrails removes the dependency for assets, 
#    this method can be removed
def create_asset(
    api_url: str, auth: DataTrailsAuth, attributes: dict
) -> dict:
    """
    Create a new DataTrails Asset
    Note: Assets have minimal information as a temporary anchor 
    for a collection of events.
    Over time, the DataTrails Asset will be deprecated, 
    in lieu of a collection of Events

    NOTE: Once DataTrails removes the dependency for assets, 
    this method can be removed

    Args:
        api_url (str): Base URL for the DataTrails API
        auth (DataTrailsAuth): Authentication object for DataTrails API
        attributes (dict): Attributes of the asset to be created

    Returns:
        dict: Data of the created asset

    Raises:
        requests.HTTPError: If the API request fails
    """
    logger.info(f"DataTrails: Creating Asset: {attributes}")

    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "behaviours": ["RecordEvidence"],
        "attributes": {"arc_display_type": "Publish", **attributes},
        "public": False,
    }
    response = requests.post(
        f"{api_url}/assets",
        headers=headers, json=payload
    )
    response.raise_for_status()
    return response.json()


def create_event(
    api_url: str,
    asset_id: str,
    auth: DataTrailsAuth,
    event_attributes: dict
) -> dict:
    """
    Create a new DataTrails Event, mapping to a SCITT Envelope

    Args:
        api_url (str): Base URL for the DataTrails API.
        asset_id (str): ID of the asset to associate the Event with.
        auth (DataTrailsAuth): Authentication object for DataTrails API.
        event_attributes (dict): Attributes of the event.

    Returns:
        dict: Data of the created Event

    Raises:
        requests.HTTPError: If the API request fails
    """
    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "Content-Type": "application/json",
    }
    # event_attributes will map to SCITT headers and
    # a cose-meta-map draft (https://github.com/SteveLasker/draft-lasker-cose-meta-map)
    payload = {
        "operation": "Record",
        "behaviour": "RecordEvidence",
        "event_attributes": {**event_attributes}
    }
    response = requests.post(
        f"{api_url}/{asset_id}/events",
        headers=headers,
        json=payload
    )

    response.raise_for_status()
    return response.json()


def run(
    vcon_uuid: str,
    link_name: str,
    opts: dict = default_options
) -> str:
    """
    Main function to run the DataTrails asset link.

    This function creates or updates an asset in DataTrails based on the vCon data,
    and records an event for the asset.

    Args:
        vcon_uuid (str): UUID of the vCon to process.
        link_name (str): Name of the link (for logging purposes).
        opts (dict): Options for the link, including API URLs and credentials.

    Returns:
        str: The UUID of the processed vCon.

    Raises:
        ValueError: If datatrails_client_id or datatrails_client_secret is not provided in the options.
    """
    logger.info(f"DataTrails: Starting Link for vCon: {vcon_uuid}")

    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    if not opts["datatrails_client_id"] or not opts["datatrails_client_secret"]:
        raise ValueError("DataTrails client ID and client secret must be provided")

    auth = DataTrailsAuth(
        opts["auth_url"],
        opts["datatrails_client_id"],
        opts["datatrails_client_secret"]
        )

    # Get the vCon from Redis
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    if not vcon:
        logger.info(f"DataTrails: vCon not found: {vcon_uuid}") 
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail=f"vCon not found: {vcon_uuid}"
        )

    # Set the subject to the vcon identifier
    subject = vcon.subject or f"vcon://{vcon_uuid}"

    # Create the SHA256 hash of the vcon
    # This is used to record what version of the vcon
    original_vcon_hash = vcon.hash

    #####################
    # ASSET REMOVAL_BEGIN
    # Everything from here to ASSET REMOVAL_END 
    # will be removed once Assets are removed from the DataTrails API
    #####################

    # Get the base attributes
    asset_attributes = opts["asset_attributes"].copy()

    # An arbitrary ID to temporarily associate DataTrails Events with an Asset
    droid_id = datetime.now(timezone.utc).date().isoformat()

    # Add the temp id to associate a batch of events
    asset_attributes.update(
        {
            "droid_id": droid_id
        }
    )

    # Search for an existing Asset, using 
    #   - arc_display_type 
    #   - conserver_link_version
    #   - droid_id
    response = get_asset_by_attributes(
        opts["api_url"],
        auth,
        asset_attributes
    )
    # Should only be a single asset found
    # if more than one is found, grab the first 
    # as assets are still a placeholder
    if len(response["assets"]) > 0:
        asset_id = response["assets"][0]["identity"]
    else:
        asset_id = None

    # Check if asset exists, create if it doesn't
    if (not asset_id):
        logger.info(f"DataTrails: Asset not found: {asset_id}")

        # Prepare attributes
        asset_attributes = opts["asset_attributes"].copy()
        asset_attributes.update(
            {
                "droid_id": droid_id
            }
        )

        asset = create_asset(
            opts["api_url"],
            auth,
            asset_attributes
        )
        asset_id = asset["identity"]

    else:
        logger.info(f"DataTrails: Asset found: {asset_id}")

    #####################
    # ASSET REMOVAL_END
    #####################

    ###########################
    # Create a DataTrails Event
    ###########################

    # Get the default attributes
    event_attributes = opts["event_attributes"].copy()

    # payload_hash_value, preimage_content_type are consistent with
    # cose-hash-envelope: https://datatracker.ietf.org/doc/draft-steele-cose-hash-envelope

    # additional metadata properties, consistent with 
    # cose-draft-lasker-meta-map: https://github.com/SteveLasker/cose-draft-lasker-meta-map

    operation=opts["vcon_operation"] or opts["event_attributes"]["arc_display_type"]
    # default to "vcon_" prefix, assuring no duplicates, or alternates with "-"
    vcon_operation = ("vcon_" + operation.removeprefix("vcon_").removeprefix("vcon-"))

    event_attributes.update(
        {
            "arc_display_type": vcon_operation,
            "vcon_operation": vcon_operation,
            "payload_hash_value": vcon.hash,
            "payload_version": vcon.updated_at or vcon.created_at,
            "subject": subject,
        }
    )

    # If the vCon hash changed, record the historical version
    # good example for a key/value pair stored in a cose-meta-map
    if original_vcon_hash != vcon.hash:
        event_attributes.update(
            {
                "payload_original_hash_value": original_vcon_hash
            }
        )

    # TODO: Should we set the public url for the vCon
    #       from https://datatracker.ietf.org/doc/draft-steele-cose-hash-envelope
    # if vcon_location:
        # event_attributes.update(
        #     {
        #         "payload_location": vcon_location
        #     }
        # )

    event = create_event(
        opts["api_url"],
        asset_id,
        auth,
        event_attributes
    )
    event_id = event["identity"]
    logger.info(f"DataTrails: Event Created: {event_id}")

    # TODO: may want to store the receipt/transparent statement in the vCon, in the future

    # Store updated vCon
    vcon_redis.store_vcon(vcon)
    logger.info(f"DataTrails: Finished Link for vCon: {vcon_uuid}")
    return vcon_uuid
