"""FastAPI exception handler that renders VconError subclasses into a
consistent JSON envelope (Refactor #8).

Envelope shape::

    {
        "error": "VconNotFoundError",
        "code": "vcon_not_found",
        "detail": "vCon abc-123 not in Redis or any storage backend",
        "trace_id": "0123456789abcdef0123456789abcdef"  // or null
    }

Wire up at app startup (see api/api.py)::

    from exceptions import VconError
    from middleware.errors import vcon_error_handler

    app.add_exception_handler(VconError, vcon_error_handler)

Ad-hoc ``raise HTTPException(...)`` sites are not affected. The handler
only fires for :class:`~exceptions.VconError` subclasses; those are the
paths we're migrating toward.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from opentelemetry import trace

from exceptions import VconError


def _current_trace_id() -> Optional[str]:
    """Return the active OTel trace id as a hex string, or None."""
    span = trace.get_current_span()
    if span is None:
        return None
    ctx = span.get_span_context()
    if not ctx or not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x")


async def vcon_error_handler(request: Request, exc: VconError) -> JSONResponse:
    """Render a VconError subclass as the consistent error envelope."""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "error": type(exc).__name__,
            "code": exc.code,
            "detail": str(exc),
            "trace_id": _current_trace_id(),
        },
    )
