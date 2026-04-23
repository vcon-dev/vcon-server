"""Domain exception hierarchy for vcon-server (Refactor #8).

Before this refactor the codebase caught ``except Exception`` ~120 times and
re-raised with no context or HTTP shape, and api/api.py produced a mix of
``raise HTTPException(500, "Failed to ...")`` and ad-hoc ``JSONResponse``
responses. Operators had no consistent shape to parse in logs or error
telemetry.

These exception classes are the shared vocabulary. Each one carries:

    - ``code``: a short, stable identifier suitable for log aggregation and
      client-side matching (e.g. ``vcon_not_found``).
    - ``http_status``: the HTTP status a FastAPI handler should return.

Raise the most specific subclass that applies. A single FastAPI exception
handler (:mod:`api.middleware.errors` in Refactor #8 part 2) maps any
:class:`VconError` to a consistent envelope so clients can stop parsing
ad-hoc error strings.

Usage::

    from exceptions import VconNotFoundError

    vcon = vcon_redis.get_vcon(uuid)
    if vcon is None:
        raise VconNotFoundError(f"vCon {uuid} not in Redis or any storage backend")

Scope note: migration of the ~120 existing bare ``except Exception`` blocks
is deliberately NOT part of this commit. That's a long-tail cleanup. Start
with the hot paths (api routes, worker_loop, Storage.save) as they're
touched for other reasons.
"""
from __future__ import annotations


class VconError(Exception):
    """Base class for all vcon-server domain exceptions."""

    #: Short, stable machine-readable code. Override in subclasses.
    code: str = "vcon_error"
    #: HTTP status suitable for a FastAPI handler to return.
    http_status: int = 500


class ConfigError(VconError):
    """The loaded configuration is malformed or references an undefined object."""

    code = "config_error"
    http_status = 500


class VconNotFoundError(VconError):
    """A vCon lookup returned nothing in Redis and every storage backend."""

    code = "vcon_not_found"
    http_status = 404


class VconValidationError(VconError):
    """A vCon failed structural/semantic validation before or during ingest."""

    code = "vcon_invalid"
    http_status = 422


class StorageError(VconError):
    """A storage backend (S3, MongoDB, Postgres, ...) failed to write/read/delete."""

    code = "storage_error"
    http_status = 500


class LinkError(VconError):
    """A chain link's run() raised. Usually wrapped in the worker loop before DLQ."""

    code = "link_error"
    http_status = 500


class AuthError(VconError):
    """API key missing, invalid, or not authorized for the requested ingress list."""

    code = "auth_error"
    http_status = 403
