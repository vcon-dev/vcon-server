"""Module for submitting a SCITT signed statement to a
   SCRAPI-compatible Transparency Service (e.g. SCITTLEs)
   and returning the entry ID and receipt."""

import logging
from time import sleep as time_sleep

import requests

# all timeouts and durations are in seconds
REQUEST_TIMEOUT = 30
POLL_TIMEOUT = 60
POLL_INTERVAL = 10

logger = logging.getLogger(__name__)


def register_statement(scrapi_url: str, signed_statement: bytes) -> dict:
    """
    Register a COSE Sign1 signed statement via SCRAPI.

    Posts the signed statement to the /entries endpoint and handles
    both synchronous (201) and asynchronous (303) responses.

    Args:
        scrapi_url: Base URL of the SCRAPI service (e.g. http://scittles:8000)
        signed_statement: CBOR-encoded COSE Sign1 bytes

    Returns:
        dict with "entry_id" (str) and "receipt" (bytes)

    Raises:
        requests.HTTPError: If the registration request fails
        TimeoutError: If async registration doesn't complete in time
    """
    response = requests.post(
        f"{scrapi_url}/entries",
        data=signed_statement,
        headers={"Content-Type": "application/cose"},
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 201:
        # Synchronous registration — receipt in body, entry_id in Location header
        entry_id = response.headers.get("Location", "").rsplit("/", 1)[-1]
        return {"entry_id": entry_id, "receipt": response.content}

    elif response.status_code == 303:
        # Asynchronous registration — poll for completion
        location = response.headers["Location"]
        entry_id = wait_for_entry_id(scrapi_url, location)
        receipt = get_receipt(scrapi_url, entry_id)
        return {"entry_id": entry_id, "receipt": receipt}

    else:
        response.raise_for_status()


def wait_for_entry_id(scrapi_url: str, operation_location: str) -> str:
    """
    Poll for an async registration operation to complete.

    Args:
        scrapi_url: Base URL of the SCRAPI service
        operation_location: Location header value from the 303 response

    Returns:
        The entry_id once registration succeeds

    Raises:
        TimeoutError: If the operation doesn't complete within POLL_TIMEOUT
    """
    poll_attempts = int(POLL_TIMEOUT / POLL_INTERVAL)

    # Resolve relative or absolute URL
    if operation_location.startswith("http"):
        poll_url = operation_location
    else:
        poll_url = f"{scrapi_url}{operation_location}"

    logger.info("Polling for registration completion at %s", poll_url)

    for _ in range(poll_attempts):
        try:
            response = requests.get(poll_url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                # Operation complete — extract entry_id
                data = response.json()
                if "entryID" in data:
                    return data["entryID"]
                elif "entry_id" in data:
                    return data["entry_id"]
                # Fall back to extracting from URL
                return poll_url.rsplit("/", 1)[-1]
            elif response.status_code == 202:
                # Still processing
                logger.debug("Registration still pending...")
        except requests.RequestException as e:
            logger.debug("Failed polling operation status: %s", e)

        time_sleep(POLL_INTERVAL)

    raise TimeoutError("Signed statement not registered within polling duration")


def get_receipt(scrapi_url: str, entry_id: str) -> bytes:
    """
    Fetch the COSE receipt for a registered entry.

    Args:
        scrapi_url: Base URL of the SCRAPI service
        entry_id: The entry identifier

    Returns:
        COSE receipt bytes
    """
    response = requests.get(
        f"{scrapi_url}/entries/{entry_id}",
        headers={"Accept": "application/cose"},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.content
