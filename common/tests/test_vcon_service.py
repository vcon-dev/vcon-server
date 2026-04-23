"""Tests for api/services/vcon_service.py (Refactor #5).

Verifies that store_and_enqueue() persists, indexes, and enqueues the vCon
using the callbacks and redis client the caller passes in. Also verifies the
race-avoidance contract: OTel context must be stored BEFORE rpush so a worker
cannot pick up the vCon before its context lands.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

# vcon_service is under api/services/; pytest.ini adds `api` to pythonpath.
from services.vcon_service import store_and_enqueue


class _Vcon:
    """Minimal Pydantic-style stand-in: .uuid and .model_dump()."""

    def __init__(self, uuid: str, created_at: str = "2026-01-01T00:00:00+00:00"):
        self.uuid = uuid
        self._data = {
            "uuid": uuid,
            "vcon": "0.0.1",
            "created_at": created_at,
            "parties": [{"tel": "+15551112222"}],
        }

    def model_dump(self) -> dict:
        return dict(self._data)


@pytest.mark.asyncio
async def test_store_and_enqueue_writes_indexes_and_rpushes():
    redis_async = MagicMock()
    redis_async.json.return_value.set = AsyncMock()
    redis_async.rpush = AsyncMock()
    add_vcon_to_set = AsyncMock()
    index_vcon_parties = AsyncMock()
    store_context_async = AsyncMock()

    out = await store_and_enqueue(
        inbound_vcon=_Vcon("vcon-1"),
        redis_async=redis_async,
        ingress_lists=["q1", "q2"],
        context={"trace_id": "abc"},
        add_vcon_to_set=add_vcon_to_set,
        index_vcon_parties=index_vcon_parties,
        store_context_async=store_context_async,
    )

    assert out["uuid"] == "vcon-1"
    redis_async.json().set.assert_awaited_once_with("vcon:vcon-1", "$", out)
    add_vcon_to_set.assert_awaited_once()
    index_vcon_parties.assert_awaited_once()
    # Each ingress list received a context write + an rpush.
    assert store_context_async.await_count == 2
    assert redis_async.rpush.await_args_list == [
        call("q1", "vcon-1"),
        call("q2", "vcon-1"),
    ]


@pytest.mark.asyncio
async def test_store_context_called_before_rpush():
    """Order matters: the context write must precede the rpush so workers
    never see a queued vCon whose context hasn't been stored yet."""
    events: list[tuple[str, str]] = []
    redis_async = MagicMock()
    redis_async.json.return_value.set = AsyncMock()

    async def rpush(list_name, uuid):
        events.append(("rpush", list_name))

    redis_async.rpush = rpush

    async def context_write(r, list_name, uuid, ctx):
        events.append(("context", list_name))

    await store_and_enqueue(
        inbound_vcon=_Vcon("vcon-2"),
        redis_async=redis_async,
        ingress_lists=["q1"],
        context={"trace_id": "x"},
        add_vcon_to_set=AsyncMock(),
        index_vcon_parties=AsyncMock(),
        store_context_async=context_write,
    )
    assert events == [("context", "q1"), ("rpush", "q1")]


@pytest.mark.asyncio
async def test_no_ingress_lists_skips_enqueue():
    redis_async = MagicMock()
    redis_async.json.return_value.set = AsyncMock()
    redis_async.rpush = AsyncMock()
    store_context_async = AsyncMock()

    await store_and_enqueue(
        inbound_vcon=_Vcon("vcon-3"),
        redis_async=redis_async,
        ingress_lists=None,
        context={"trace_id": "x"},
        add_vcon_to_set=AsyncMock(),
        index_vcon_parties=AsyncMock(),
        store_context_async=store_context_async,
    )
    redis_async.rpush.assert_not_awaited()
    store_context_async.assert_not_awaited()
