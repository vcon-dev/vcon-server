import requests
import os
import json
from datetime import datetime, timedelta
from lib.vcon_redis import VconRedis
from vcon import Vcon
from lib.logging_utils import init_logger

logger = init_logger(__name__)

default_options = {
    "api_url": "https://app.datatrails.ai/archivist/v2/",
    "auth_url": "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
    "client_id": "DATATRAILS_CLIENT_ID",
    "client_secret": "DATATRAILS_CLIENT_SECRET",
    "behaviours": ["RecordEvidence"],
    "asset_attributes": {
        "arc_description": "DataTrails Conserver Link",
    },
    "event_attributes": {
        "arc_description": "DataTrails Conserver Link",
        "document_hash_alg": "SHA-256",
    },
    "event_type": "Update",
}


class DataTrailsAuth:
    """
    Handles authentication for DataTrails API, including token management and refresh.
    """

    def __init__(self, auth_url, client_id, client_secret):
        """
        Initialize the DataTrailsAuth object.

        Args:
            auth_url (str): URL for the authentication endpoint.
            client_id (str): Client ID for DataTrails API.
            client_secret (str): Client secret for DataTrails API.
        """
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None
        self.token_expiry = None

    def get_token(self):
        """
        Get a valid authentication token, refreshing if necessary.

        Returns:
            str: A valid authentication token.
        """
        if self.token is None or datetime.now() >= self.token_expiry:
            self._refresh_token()
        return self.token

    def _refresh_token(self):
        """
        Refresh the authentication token and update the token file.
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
        self.token_expiry = datetime.now() + timedelta(
            seconds=token_data["expires_in"] - 300
        )

        # Save token to file
        datatrails_dir = os.path.expanduser("~/.datatrails")
        os.makedirs(datatrails_dir, exist_ok=True)
        os.chmod(datatrails_dir, 0o700)
        with open(os.path.join(datatrails_dir, "bearer-token.txt"), "w") as f:
            f.write(f"Authorization: Bearer {self.token}")

        logger.info("DataTrails auth token refreshed and saved to file")


def get_asset(api_url: str, asset_id: str, auth: DataTrailsAuth) -> dict:
    """
    Retrieve an asset from DataTrails API.

    Args:
        api_url (str): Base URL for the DataTrails API.
        asset_id (str): ID of the asset to retrieve.
        auth (DataTrailsAuth): Authentication object for DataTrails API.

    Returns:
        dict: Asset data if found, None if not found.

    Raises:
        requests.HTTPError: If the API request fails for reasons other than a 404.
    """
    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "Content-Type": "application/json",
    }
    response = requests.get(f"{api_url}/{asset_id}", headers=headers)
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return None
    else:
        response.raise_for_status()


def create_asset(
    api_url: str, auth: DataTrailsAuth, attributes: dict, behaviours: list
) -> dict:
    """
    Create a new DataTrails Asset

    Args:
        api_url (str): Base URL for the DataTrails API.
        auth (DataTrailsAuth): Authentication object for DataTrails API.
        attributes (dict): Attributes of the asset to be created.
        behaviours (list): Behaviours to be associated with the asset.

    Returns:
        dict: Data of the created asset.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "behaviours": behaviours,
        "attributes": {"arc_display_type": "Publish", **attributes},
        "public": True,
    }
    response = requests.post(f"{api_url}/assets", headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def create_event(
    api_url: str,
    asset_id: str,
    auth: DataTrailsAuth,
    event_type: str,
    event_attributes: dict,
    behaviours: list
) -> dict:
    """
    Create a new DataTrails Event

    Args:
        api_url (str): Base URL for the DataTrails API.
        asset_id (str): ID of the asset to associate the Event with.
        auth (DataTrailsAuth): Authentication object for DataTrails API.
        event_type (str): Type of the event to be created.
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
    payload = {
        "operation": "Record",
        "behaviour": "RecordEvidence",
        "event_attributes": {"arc_display_type": "vCon", **event_attributes}
    }
    logger.info(f"POST: {api_url}{asset_id}/events")
    response = requests.post(f"{api_url}{asset_id}/events", headers=headers, json=payload)
    logger.info(f"Asset: {asset_id}")
    logger.info(f"Event: " + json.dumps(payload))

    response.raise_for_status()
    event_id = response["identity"]
    logger.info(f"DataTrails Event created: {event_id}")
    return response.json()


def update_asset(
    api_url: str,
    asset_id: str,
    auth: DataTrailsAuth,
    event_type: str,
    event_attributes: dict,
    asset_attributes: dict,
) -> dict:
    """
    Update an existing asset in DataTrails by creating a new event.

    Args:
        api_url (str): Base URL for the DataTrails API.
        asset_id (str): ID of the asset to update.
        auth (DataTrailsAuth): Authentication object for DataTrails API.
        event_type (str): Type of the event to be created.
        event_attributes (dict): Attributes of the event.
        asset_attributes (dict): Updated attributes of the asset.

    Returns:
        dict: Data of the created event.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "Content-Type": "application/json",
    }
    payload = {
        "operation": "Record",
        "behaviour": "RecordEvidence",
        "event_attributes": {"arc_display_type": event_type, **event_attributes},
        "asset_attributes": asset_attributes,
    }
    response = requests.post(
        f"{api_url}/{asset_id}/events", headers=headers, json=payload
    )
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
    logger.info(f"Starting DataTrails asset link for vCon: {vcon_uuid}")

    merged_opts = default_options.copy()
    merged_opts.update(opts)
    opts = merged_opts

    if not opts["client_id"] or not opts["client_secret"]:
        raise ValueError("DataTrails client ID and client secret must be provided")

    auth = DataTrailsAuth(opts["auth_url"], opts["client_id"], opts["client_secret"])
    vcon_redis = VconRedis()
    v = vcon_redis.get_vcon(vcon_uuid)

    # Extract relevant information from vCon
    asset_id = v.get_tag("datatrails_asset_id")

    # Create the SHA256 hash of the vcon
    # This is used to record what version of the vcon
    asset_name = v.subject or f"vcon:{vcon_uuid}"
    original_vcon_hash = v.hash

    # Verify a single Asset exists for the vcon_uuid
    #asset = get_asset(opts["api_url"], asset_id, auth)

    # Check if asset exists, create if it doesn't
    if not asset_id:
        logger.info(f"Asset doesn't exist: {asset_id}")

        # Prepare attributes
        asset_attributes = opts["asset_attributes"].copy()
        asset_attributes.update(
            {
                "arc_display_name": asset_name,
                "document_hash_value": original_vcon_hash,
                "document_version": v.updated_at or v.created_at,
                "subject": vcon_uuid,
                "vcon_uuid": vcon_uuid,
            }
        )

        logger.info(f"Creating new DataTrails asset for vCon: {vcon_uuid}")
        asset = create_asset(
            opts["api_url"], auth, asset_attributes, opts["behaviours"]
        )
        asset_id = asset["identity"]

        v.add_tag("datatrails_asset_id", asset_id)
        v.add_tag("datatrails_asset_name", asset_name)

        # Could set the public url here
    else:
        logger.info(f"DataTrails Asset found: {asset_id}")

    # Create a DataTrails Event

    # Get the clean attributes
    event_attributes = opts["event_attributes"].copy()

    # We might have to update the hash value of the vcon
    # TODO: Only add original_hash_value if the hash's are different
    event_attributes.update(
        {
            "document_hash_value": v.hash,
            "document_original_hash_value": original_vcon_hash,
            "document_version": v.updated_at or v.created_at,
            "subject": vcon_uuid,
            "vcon_uuid": vcon_uuid,
        }
    )

    # Prepare event details, based on the opts
    event_type = opts.get("event_type") or "Update"

    # Update the asset with new event
    # update_asset(
    #     opts["api_url"], asset_id, auth, event_type, event_attributes, asset_attributes
    # )

    event = create_event(
        opts["api_url"], asset_id, auth, event_type, event_attributes, opts["behaviours"]
    )

    # DataTrails Events can be found based on the vcon_uuid, or the DataTrails Asset
    # We may want to store the receipt/transparent statement in the vCon, in the future

    # Store updated vCon
    vcon_redis.store_vcon(v)
    logger.info(f"Finished DataTrails asset link for vCon: {vcon_uuid}")
    return vcon_uuid
