import os
import requests
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from starlette.status import HTTP_404_NOT_FOUND, HTTP_501_NOT_IMPLEMENTED
from vcon import Vcon

logger = init_logger(__name__)

# Increment for any API/attribute changes
link_type = "DataTrails"
link_version = "0.2.0"

# NOTE: Once DataTrails removes the dependency for assets,
#       "asset_attributes" will be removed

# NOTE: droid_id is a temporary placeholder to associate an
#       asset with a collection of events
#       once Assets are no longer required, droid_id will be removed
#       droid_id was used, to avoid conflicts with past or future
#       real id's that could be confusing
#       Why droid_id: "these are not the droids your're looking for"

default_options = {
    "api_url": "https://app.datatrails.ai/archivist/v2",
    "auth_url": "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
    "asset_attributes": {"arc_display_type": "vcon_droid", "conserver_link_version": link_version},
}


class DataTrailsAuth:
    """
    Handles authentication for DataTrails API, including token management and refresh.
    """

    def __init__(self, auth_url, client_id, client_secret):
        """
        Initialize the DataTrailsAuth object

        Args:
            auth_url (str): URL for the authentication endpoint
            client_id (str): Client ID for DataTrails API
            client_secret (str): Client Secret for DataTrails API
        """
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
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
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        response = requests.post(self.auth_url, data=data)
        response.raise_for_status()
        token_data = response.json()

        self.token = token_data["access_token"]
        # Set token expiry to 5 minutes before actual expiry for safety
        self.token_expiry = datetime.now() + timedelta(seconds=token_data["expires_in"] - 300)


#    NOTE: Once DataTrails removes the dependency for assets,
#    this method can be removed
def get_asset_by_attributes(opts: dict, auth: DataTrailsAuth, attributes: dict) -> dict:
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
        opts (dict): including the base URL for the DataTrails API
        auth (DataTrailsAuth): Authentication object for DataTrails API
        attributes (dict): a dictionary of attributes to search for

    Returns:
        dict: Data of the found asset

    Raises:
        requests.HTTPError: If the API request fails
    """
    api_url = opts["api_url"]
    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "DataTrails-User-Agent": f"oss/conserverlink/{link_version}",
        "DataTrails-Partner-ID": opts["partner_id"],
        "Content-Type": "application/json",
    }

    # Searching DataTrails Assets by attributes requires
    # each attribute to be prepended with "attribute."
    params = {}
    for param in attributes:
        params.update({f"attributes.{param}": f"{attributes[param]}"})

    response = requests.get(f"{api_url}/assets", params=params, headers=headers)
    response.raise_for_status()
    return response.json()


#    NOTE: Once DataTrails removes the dependency for assets,
#    this method can be removed
def create_asset(opts: dict, auth: DataTrailsAuth, attributes: dict) -> dict:
    """
    Create a new DataTrails Asset
    Note: Assets have minimal information as a temporary anchor
    for a collection of events.
    Over time, the DataTrails Asset will be deprecated,
    in lieu of a collection of Events

    NOTE: Once DataTrails removes the dependency for assets,
    this method can be removed

    Args:
        opts (dict): Including the base URL for the DataTrails API
        auth (DataTrailsAuth): Authentication object for DataTrails API
        attributes (dict): Attributes of the asset to be created

    Returns:
        dict: Data of the created asset

    Raises:
        requests.HTTPError: If the API request fails
    """
    api_url = opts["api_url"]
    logger.info(f"DataTrails: Creating Asset: {attributes}")

    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "DataTrails-User-Agent": "oss/conserverlink/" + link_version,
        "DataTrails-Partner-ID": opts["partner_id"],
        "Content-Type": "application/json",
    }
    payload = {
        "behaviours": ["RecordEvidence"],
        "attributes": {"arc_display_type": "Publish", **attributes},
        "public": False,
    }
    response = requests.post(f"{api_url}/assets", headers=headers, json=payload)
    if response.status_code == 429:
        logger.info(f"response.raw: {response.raw}")

    response.raise_for_status()
    return response.json()


def create_event(opts: dict, asset_id: str, auth: DataTrailsAuth, event_attributes: dict) -> dict:
    """
    Create a new DataTrails Event, mapping to a SCITT Envelope

    Args:
        opts (dict): Configuration, including the base URL for the DataTrails API.
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
        "DataTrails-User-Agent": "oss/conserverlink/" + link_version,
        "DataTrails-Partner-ID": opts["partner_id"],
        "Content-Type": "application/json",
    }
    api_url = opts["api_url"]
    # event_attributes will map to SCITT headers and
    # a cose-meta-map draft (https://github.com/SteveLasker/draft-lasker-cose-meta-map)
    payload = {"operation": "Record", "behaviour": "RecordEvidence", "event_attributes": {**event_attributes}}
    # logger.info(f"payload: {payload}")
    response = requests.post(f"{api_url}/{asset_id}/events", headers=headers, json=payload)

    response.raise_for_status()
    return response.json()


def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> str:
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
        ValueError: If client_id or client_secret is not provided in the options.
    """
    logger.info(f"DataTrails: Starting Link for vCon: {vcon_uuid}")

    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    try:
        auth_type = opts["auth"]["type"]
    except:
        raise HTTPException(
            status_code=HTTP_501_NOT_IMPLEMENTED, detail='Auth improperly configured. Unable to find opt["auth"]'
        )
    if auth_type.lower() == "oidc-client-credentials":
        auth = DataTrailsAuth(opts["auth"]["token_endpoint"], opts["auth"]["client_id"], opts["auth"]["client_secret"])
    else:
        raise HTTPException(
            status_code=HTTP_501_NOT_IMPLEMENTED, detail=f"Auth type not currently supported: {auth_type}"
        )

    # Get the vCon from Redis
    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    # TODO:
    # need better vcon retrieval error handling,
    # as an invalid vCon can be recovered,
    # allowing the subsequent code to continue
    # with a malformed vcon object
    # logger.info(f"vcon: {vcon.to_json()}")
    if not vcon:
        logger.info(f"DataTrails: vCon not found: {vcon_uuid}")
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail=f"vCon not found: {vcon_uuid}")

    # Set the subject to the vcon identifier
    subject = f"vcon://{vcon_uuid}"

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
    asset_attributes.update({"droid_id": droid_id})

    # Search for an existing Asset, using
    #   - arc_display_type
    #   - conserver_link_version
    #   - droid_id
    response = get_asset_by_attributes(opts, auth, asset_attributes)
    # Should only be a single asset found
    # if more than one is found, grab the first
    # as assets are still a placeholder
    if len(response["assets"]) > 0:
        asset_id = response["assets"][0]["identity"]
    else:
        asset_id = None

    # Check if asset exists, create if it doesn't
    if not asset_id:
        logger.info(f"DataTrails: Asset not found: {asset_id}")

        # Prepare attributes
        asset_attributes = opts["asset_attributes"].copy()
        asset_attributes.update({"droid_id": droid_id})

        asset = create_asset(opts, auth, asset_attributes)
        asset_id = asset["identity"]

    else:
        logger.info(f"DataTrails: Asset found: {asset_id}")

    #####################
    # ASSET REMOVAL_END
    #####################

    ###########################
    # Create a DataTrails Event
    ###########################

    # payload_hash_alg, payload_preimage_content_type are consistent with
    # cose-hash-envelope: https://datatracker.ietf.org/doc/draft-steele-cose-hash-envelope

    # additional metadata properties, consistent with
    # cose-draft-lasker-meta-map: https://github.com/SteveLasker/cose-draft-lasker-meta-map

    operation = opts["vcon_operation"] or "vcon"
    # default to "vcon_" prefix, assuring no duplicates, or alternates with "-"
    vcon_operation = "vcon_" + operation.lower().removeprefix("vcon_").lower().removeprefix("vcon-")

    event_attributes = {
        "arc_display_type": vcon_operation,
        "conserver_link": link_type,
        "conserver_link_name": link_name,
        "conserver_link_version": link_version,
        "payload": vcon.hash,
        "payload_hash_alg": "SHA-256",
        "payload_preimage_content_type": "application/vcon+json",
        "subject": subject,
        "timestamp_declared": vcon.updated_at or vcon.created_at,
        "vcon_draft_version": "01",
        "vcon_operation": vcon_operation,
    }

    # TODO: Should we set the public url for the vCon
    #       from https://datatracker.ietf.org/doc/draft-steele-cose-hash-envelope
    # if vcon_location:
    # event_attributes.update(
    #     {
    #         "payload_location": vcon_location
    #     }
    # )

    event = create_event(opts, asset_id, auth, event_attributes)
    event_id = event["identity"]
    logger.info(f"DataTrails: Event Created: {event_id}")

    # TODO: may want to store the receipt/transparent statement in the vCon, in the future

    return vcon_uuid
