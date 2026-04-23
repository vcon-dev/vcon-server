"""Shared vCon ingest logic for api routes (Refactor #5).

Extracted from api/api.py::post_vcon and api/api.py::external_ingress_vcon,
which previously duplicated ~35 lines of store + index + enqueue code. Both
endpoints now delegate to :func:`store_and_enqueue` so a behavior divergence
between the authenticated and external ingress paths cannot silently happen.

This module takes the async Redis client as an argument rather than reading a
module-level global — that's the prerequisite for Refactor #7 (Redis DI) and
also makes unit tests straightforward.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Optional, Sequence


async def store_and_enqueue(
    *,
    inbound_vcon: Any,
    redis_async,
    ingress_lists: Optional[Sequence[str]] = None,
    context: Optional[Mapping[str, Any]] = None,
    add_vcon_to_set,
    index_vcon_parties,
    store_context_async,
) -> dict:
    """Persist a vCon to Redis, index it, and optionally enqueue for processing.

    Args:
        inbound_vcon: The Pydantic Vcon model received from the request body.
        redis_async: Async Redis client to use for all Redis operations.
        ingress_lists: Optional list of ingress list names to enqueue the
            vCon UUID on. Each gets the OTel context stored *before* the
            rpush to avoid a race where a worker picks up the UUID before
            the context lands.
        context: Optional OTel trace context dict (from extract_otel_trace_context).
        add_vcon_to_set: Callback that adds (key, timestamp) to the sorted set.
        index_vcon_parties: Callback that indexes party fields (tel/mailto/name).
        store_context_async: Callback that writes the OTel context to Redis
            keyed by (ingress_list, vcon_uuid).

    Returns:
        The normalized vCon dict that was stored (UUID stringified, created_at
        ISO-formatted). Caller decides how to shape the HTTP response.

    The function deliberately accepts helper callbacks rather than importing
    them, because those helpers live in api/api.py and import would be
    circular. Once Refactor #7 lands (Redis + helpers behind a service
    boundary), this signature will simplify.
    """
    dict_vcon = inbound_vcon.model_dump()
    dict_vcon["uuid"] = str(inbound_vcon.uuid)
    key = f"vcon:{dict_vcon['uuid']}"
    created_at = datetime.fromisoformat(str(dict_vcon["created_at"]))
    dict_vcon["created_at"] = created_at.isoformat()
    timestamp = int(created_at.timestamp())

    await redis_async.json().set(key, "$", dict_vcon)
    await add_vcon_to_set(key, timestamp)
    await index_vcon_parties(dict_vcon["uuid"], dict_vcon["parties"])

    if ingress_lists:
        vcon_uuid_str = dict_vcon["uuid"]
        for ingress_list in ingress_lists:
            # Store context BEFORE adding to ingress list to avoid a race
            # where the conserver picks up the vCon before its context lands.
            if context:
                await store_context_async(
                    redis_async, ingress_list, vcon_uuid_str, context
                )
            await redis_async.rpush(ingress_list, vcon_uuid_str)

    return dict_vcon
