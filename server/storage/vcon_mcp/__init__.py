"""
vCon-MCP REST storage module for vcon-server

This module provides integration with the vcon-mcp project via its REST API.
It implements the storage interface (save, get, delete) by calling vcon-mcp
endpoints so that vCons are stored and retrieved through the MCP service.

Endpoints used:
- POST   {base_url}/vcons        - Create/ingest a vCon
- GET    {base_url}/vcons/:uuid   - Get a vCon by UUID
- DELETE {base_url}/vcons/:uuid  - Delete a vCon by UUID

Configuration options:
- base_url: Base URL of vcon-mcp REST API (e.g. http://localhost:3000/api/v1)
- api_key: Optional. API key for Authorization: Bearer <api_key>
- timeout: Optional. Request timeout in seconds (default: 30)
"""

from typing import Optional, Dict, Any
import requests
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options: Dict[str, Any] = {
    "base_url": "http://127.0.0.1:3000/api/v1",
    "api_key": "",
    "timeout": 30,
}


def _headers(opts: Dict[str, Any]) -> Dict[str, str]:
    """Build request headers, including optional Bearer token."""
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    api_key = opts.get("api_key") or ""
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


def _url(opts: Dict[str, Any], path: str) -> str:
    """Build full URL for the given path (no leading slash)."""
    base = (opts.get("base_url") or default_options["base_url"]).rstrip("/")
    return f"{base}/{path.lstrip('/')}"


def save(vcon_uuid: str, opts: Dict[str, Any] = None) -> None:
    """
    Save a vCon to vcon-mcp via REST API.

    Fetches the vCon from Redis, then POSTs it to vcon-mcp /vcons endpoint.

    Args:
        vcon_uuid: UUID of the vCon to save
        opts: Options (base_url, api_key, timeout). Defaults to default_options.

        Exception: If vCon cannot be read from Redis or vcon-mcp request fails.
    """
    opts = opts or default_options
    logger.info("Starting vcon-mcp storage save for vCon: %s", vcon_uuid)
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        if not vcon:
            raise ValueError(f"vCon {vcon_uuid} not found in Redis")
        payload = vcon.to_dict()
        url = _url(opts, "vcons")
        timeout = opts.get("timeout", default_options["timeout"])
        resp = requests.post(
            url,
            json=payload,
            headers=_headers(opts),
            timeout=timeout,
        )
        resp.raise_for_status()
        logger.info("Finished vcon-mcp storage save for vCon: %s", vcon_uuid)
    except requests.RequestException as e:
        logger.error(
            "vcon-mcp storage: failed to save vCon: %s, error: %s",
            vcon_uuid,
            e,
        )
        raise
    except Exception as e:
        logger.error(
            "vcon-mcp storage: failed to save vCon: %s, error: %s",
            vcon_uuid,
            e,
        )
        raise


def get(vcon_uuid: str, opts: Dict[str, Any] = None) -> Optional[dict]:
    """
    Get a vCon from vcon-mcp by UUID via REST API.

    Args:
        vcon_uuid: UUID of the vCon to retrieve
        opts: Options (base_url, api_key, timeout). Defaults to default_options.

    Returns:
        The vCon as a dict if found, None if not found or on error.
    """
    opts = opts or default_options
    logger.info("Starting vcon-mcp storage get for vCon: %s", vcon_uuid)
    try:
        url = _url(opts, f"vcons/{vcon_uuid}")
        timeout = opts.get("timeout", default_options["timeout"])
        resp = requests.get(
            url,
            headers=_headers(opts),
            timeout=timeout,
        )
        if resp.status_code == 404:
            logger.info("vCon %s not found in vcon-mcp storage", vcon_uuid)
            return None
        resp.raise_for_status()
        data = resp.json()
        vcon = data.get("vcon") if isinstance(data, dict) else None
        if vcon is not None:
            logger.info("Finished vcon-mcp storage get for vCon: %s", vcon_uuid)
        return vcon
    except requests.RequestException as e:
        logger.error(
            "vcon-mcp storage: failed to get vCon: %s, error: %s", vcon_uuid, e
        )
        return None


def delete(vcon_uuid: str, opts: Dict[str, Any] = None) -> bool:
    """
    Delete a vCon from vcon-mcp by UUID via REST API.

    Args:
        vcon_uuid: UUID of the vCon to delete
        opts: Options (base_url, api_key, timeout). Defaults to default_options.

    Returns:
        True if the vCon was deleted, False if it was not found.

    Raises:
        Exception: On request errors other than 404.
    """
    opts = opts or default_options
    logger.info("Starting vcon-mcp storage delete for vCon: %s", vcon_uuid)
    try:
        url = _url(opts, f"vcons/{vcon_uuid}")
        timeout = opts.get("timeout", default_options["timeout"])
        resp = requests.delete(
            url,
            headers=_headers(opts),
            timeout=timeout,
        )
        if resp.status_code == 404:
            logger.info("vCon %s not found in vcon-mcp storage", vcon_uuid)
            return False
        resp.raise_for_status()
        logger.info(
            "Successfully deleted vCon %s from vcon-mcp storage", vcon_uuid
        )
        return True
    except requests.RequestException as e:
        logger.error(
            "vcon-mcp storage: failed to delete vCon: %s, error: %s",
            vcon_uuid,
            e,
        )
        raise
