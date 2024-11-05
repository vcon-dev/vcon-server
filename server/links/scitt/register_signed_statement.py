""" Module for submitting a SCITT signed statement to the
    DataTrails Transparency Service and optionally returning
    a Transparent Statement """

import argparse
import logging
import os
import sys
import datetime
from time import sleep as time_sleep

from pycose.messages import Sign1Message
import requests

# Increment for any API/attribute changes
link_version = "0.1.0"

# CWT header label comes from version 4 of the scitt architecture document
# https://www.ietf.org/archive/id/draft-ietf-scitt-architecture-04.html#name-issuer-identity
HEADER_LABEL_CWT = 13

# Various CWT header labels come from:
# https://www.rfc-editor.org/rfc/rfc8392.html#section-3.1
HEADER_LABEL_CWT_ISSUER = 1
HEADER_LABEL_CWT_SUBJECT = 2

# CWT CNF header labels come from:
# https://datatracker.ietf.org/doc/html/rfc8747#name-confirmation-claim
HEADER_LABEL_CWT_CNF = 8
HEADER_LABEL_CNF_COSE_KEY = 1

# all timeouts and durations are in seconds
REQUEST_TIMEOUT = 30
POLL_TIMEOUT = 60
POLL_INTERVAL = 10

logger = logging.getLogger("check operation status")
logging.basicConfig(level=logging.getLevelName("INFO"))

class OIDC_Auth:
    """
    Handles authentication for SCRAPI API, including token management and refresh.
    """

    def __init__(self, opts:dict):
        """
        Initialize the OIDC Auth object

        Args:
            opts (dict) containing
            auth_url, client_id, client_secret
            for the OIDC API
        """
        
        self.auth_url = opts["auth_url"]
        self.client_id = opts["client_id"]
        self.client_secret = opts["client_secret"]
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
        response = requests.post(
            self.auth_url,
            data=data,
            timeout=REQUEST_TIMEOUT
        )
        if response.status_code != 200:
            logger.error("FAILED to acquire bearer token")
            logger.debug(response)
            sys.exit(1)
        response.raise_for_status()

        token_data = response.json()
        self.token = token_data["access_token"]
        # Set token expiry to 5 minutes before actual expiry for safety
        self.token_expiry = datetime.now() + timedelta(
            seconds=token_data["expires_in"] - 300
        )

def get_dt_auth_header() -> str:
    """
    Get DataTrails bearer token from OIDC credentials in env
    """
    # Pick up credentials from env
    client_id = os.environ.get("DATATRAILS_CLIENT_ID")
    client_secret = os.environ.get("DATATRAILS_CLIENT_SECRET")

    if client_id is None or client_secret is None:
        logger.error(
            "Please configure your DataTrails credentials in the shell environment"
        )
        sys.exit(1)

    # Get token from the auth endpoint
    response = requests.post(
        "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        logger.error("FAILED to acquire bearer token")
        logger.debug(response)
        sys.exit(1)

    # Format as a request header
    res = response.json()
    return f'{res["token_type"]} {res["access_token"]}'


def register_statement(
    opts: dict,
    auth: OIDC_Auth, 
    signed_statement: bytes
) -> str:
    """
    Register the SCITT Signed Statement

    Args:
        opts (dict): Configuration, including the base URL for the DataTrails API.
        auth (DataTrailsAuth): Authentication object for DataTrails API.
        signed_statement (str): The contents of the signed statement to be posted

    Returns:
        str: The operation ID to poll for completion, and receipts

    Raises:
        requests.HTTPError: If the API request fails
    """

    logger.info("in register_statement")

    headers = {
        "Authorization": f"Bearer {auth.get_token()}",
        "DataTrails-User-Agent": "oss/conserverlink/" + link_version,
        "DataTrails-Partner-ID": opts["partner_id"],
        "Content-Type": "application/json",
    }
    api_url = opts["api_url"]

    # Make the POST request
    response = requests.post(
        url=api_url,
        headers=headers,
        data=signed_statement,
        timeout=REQUEST_TIMEOUT
    )
    if response.status_code != 200:
        logger.error("FAILED to submit statement")
        logger.debug(response)
        sys.exit(1)

    response.raise_for_status()

    res = response.json()
    if not "operationID" in res:
        logger.error("FAILED No OperationID locator in response")
        logger.debug(res)
        sys.exit(1)

    return res["operationID"]


def get_operation_status(operation_id: str, headers: dict) -> dict:
    """
    Gets the status of a long-running registration operation
    """
    response = requests.get(
        f"https://app.datatrails.ai/archivist/v1/publicscitt/operations/{operation_id}",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def wait_for_entry_id(operation_id: str, headers: dict) -> str:
    """
    Polls for the operation status to be 'succeeded'.
    """

    poll_attempts: int = int(POLL_TIMEOUT / POLL_INTERVAL)
    if not logger:
        print("logger not set")

    logger.info("starting to poll for operation status 'succeeded'")

    for _ in range(poll_attempts):

        try:
            operation_status = get_operation_status(operation_id, headers)

            # pylint: disable=fixme
            # TODO: ensure get_operation_status handles error cases from the rest request
            if (
                "status" in operation_status
                and operation_status["status"] == "succeeded"
            ):
                return operation_status["entryID"]

        except requests.HTTPError as e:
            logger.debug("failed getting operation status, error: %s", e)

        time_sleep(POLL_INTERVAL)

    raise TimeoutError("signed statement not registered within polling duration")


def attach_receipt(
    entry_id: str,
    signed_statement_filepath: str,
    transparent_statement_file_path: str,
    headers: dict
):
    """
    Given a Signed Statement and a corresponding Entry ID, fetch a Receipt from
    the Transparency Service and write out a complete Transparent Statement
    """
    # Get the receipt
    response = requests.get(
        f"https://app.datatrails.ai/archivist/v1/publicscitt/entries/{entry_id}/receipt",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        logger.error("FAILED to get receipt")
        logger.debug(response)
        sys.exit(1)

    logger.debug(response.content)

    # Open up the signed statement
    with open(signed_statement_filepath, "rb") as data_file:
        data = data_file.read()
        message = Sign1Message.decode(data)
        logger.debug(message)

    # Add receipt to the unprotected header and re-encode
    message.uhdr["receipts"] = [response.content]
    ts = message.encode(sign=False)

    # Write out the updated Transparent Statement
    with open(transparent_statement_file_path, "wb") as file:
        file.write(ts)
        logger.info("File saved successfully")


def main():
    """Creates a Transparent Statement"""

    parser = argparse.ArgumentParser(description="Create a signed statement.")

    # Signed Statement file
    parser.add_argument(
        "--signed-statement-file",
        type=str,
        help="filepath to the Signed Statement to be registered.",
        default="signed-statement.cbor",
    )

    # Output file
    parser.add_argument(
        "--output-file",
        type=str,
        help="output file to store the Transparent Statement (leave blank to skip saving).",
        default="",
    )

    # log level
    parser.add_argument(
        "--log-level",
        type=str,
        help="log level. for any individual poll errors use DEBUG, defaults to WARNING",
        default="WARNING",
    )

    args = parser.parse_args()

    # logger = logging.getLogger("check operation status")
    # logging.basicConfig(level=logging.getLevelName(args.log_level))

    # Submit Signed Statement to DataTrails

    op_id = register_statement(args.signed_statement_file)
    logger.info("Successfully submitted with Operation ID %s", op_id)

    # If the client wants the Transparent Statement, wait for it
    if args.output_file != "":
        logger.info("Now waiting for registration to complete")

        # Wait for the registration to complete
        try:
            entry_id = wait_for_entry_id(op_id, auth_headers)
        except TimeoutError as e:
            logger.error(e)
            sys.exit(1)

        logger.info("Fully Registered with Entry ID %s", entry_id)

        # Attach the receipt
        attach_receipt(
            entry_id, args.signed_statement_file, args.output_file, auth_headers
        )


if __name__ == "__main__":
    main()
