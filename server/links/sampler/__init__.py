import random
import time
import hashlib

default_options = {"method": "percentage", "value": 50, "seed": None}


def run(vcon_uuid: str, link_name: str, opts: dict = default_options) -> str | None:
    """
    Sample incoming vCons based on the specified method and parameters.

    This function decides whether to keep or filter out a vCon based on the
    sampling method and its associated value. If the vCon passes the sampling
    criteria, its UUID is returned. Otherwise, None is returned, effectively
    filtering out the vCon.

    Args:
        vcon_uuid (str): The UUID of the incoming vCon.
        link_name (str): The name of the link (unused in this function, but required for compatibility).
        opts (dict): A dictionary of options for the sampling method. Defaults to default_options.

    Returns:
        str | None: The vCon UUID if it passes the sampling criteria, None otherwise.

    Raises:
        ValueError: If an unknown sampling method is specified.

    Example:
        result = run("some-vcon-uuid", "sampling-link", {"method": "percentage", "value": 30})
        if result:
            print("vCon passed sampling")
        else:
            print("vCon filtered out")
    """
    options = {**default_options, **opts}

    if options["seed"] is not None:
        random.seed(options["seed"])

    method = options["method"]
    value = options["value"]

    if method == "percentage":
        return _percentage_sampling(vcon_uuid, value)
    elif method == "rate":
        return _rate_sampling(vcon_uuid, value)
    elif method == "modulo":
        return _modulo_sampling(vcon_uuid, value)
    elif method == "time_based":
        return _time_based_sampling(vcon_uuid, value)
    else:
        raise ValueError(f"Unknown sampling method: {method}")


def _percentage_sampling(vcon_uuid: str, percentage: float) -> str | None:
    """
    Perform percentage-based sampling.

    Args:
        vcon_uuid (str): The UUID of the vCon.
        percentage (float): The percentage of vCons to keep (0-100).

    Returns:
        str | None: The vCon UUID if it passes the sampling, None otherwise.
    """
    if random.uniform(0, 100) <= percentage:
        return vcon_uuid
    return None


def _rate_sampling(vcon_uuid: str, rate: float) -> str | None:
    """
    Perform rate-based sampling.

    Args:
        vcon_uuid (str): The UUID of the vCon.
        rate (float): The average number of seconds between samples.

    Returns:
        str | None: The vCon UUID if it passes the sampling, None otherwise.
    """
    if random.expovariate(1.0 / rate) <= 1:
        return vcon_uuid
    return None


def _modulo_sampling(vcon_uuid: str, modulo: int) -> str | None:
    """
    Perform modulo-based sampling.

    Args:
        vcon_uuid (str): The UUID of the vCon.
        modulo (int): A positive integer n, where every nth vCon is kept.

    Returns:
        str | None: The vCon UUID if it passes the sampling, None otherwise.
    """
    # Use SHA-256 for consistent hashing
    hash_value = hashlib.sha256(vcon_uuid.encode()).hexdigest()
    # Convert first 8 characters of hash to integer
    hash_int = int(hash_value[:8], 16)
    if hash_int % modulo == 0:
        return vcon_uuid
    return None


def _time_based_sampling(vcon_uuid: str, interval: int) -> str | None:
    """
    Perform time-based sampling.

    Args:
        vcon_uuid (str): The UUID of the vCon.
        interval (int): A positive integer n, where vCons are kept every n seconds.

    Returns:
        str | None: The vCon UUID if it passes the sampling, None otherwise.
    """
    current_time = int(time.time())
    if current_time % interval == 0:
        return vcon_uuid
    return None
