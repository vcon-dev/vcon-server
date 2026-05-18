"""Thin abstraction over Redis queue operations used by the conserver.

Goal: give links, the conserver main loop, and the API a single chokepoint
for queue work so no module has to import ``redis_mgr.redis`` directly.
Redis remains the implementation; this is *not* a pluggable-backend
interface.

Naming follows standard queue semantics:

- ``enqueue(list_name, vcon_id)`` — RPUSH (append to tail). Pairs with
  ``dequeue`` (BLPOP from head) to give FIFO ordering.
- ``enqueue_front(list_name, vcon_id)`` — LPUSH (prepend to head). Use
  only when the next ``dequeue`` on this queue must see this vCon
  before anything else — e.g., a worker that has popped a vCon and is
  shutting down before processing it.
- ``dequeue(list_names, timeout)`` — BLPOP (blocking pop from head).
- ``enqueue_dlq(ingress_list, vcon_id)`` — RPUSH onto the DLQ derived
  from an ingress list name. Pairs with ``dequeue_dlq_async`` (LPOP)
  to give FIFO ordering on DLQ reprocess.
- ``set_vcon_ttl(vcon_id, seconds)`` — EXPIRE on the vCon JSON key.
- ``queue_length(list_name)`` — LLEN.

Async variants suffixed ``_async`` take the async Redis client as the
first argument; the rest of the signature mirrors the sync version.

The class is stateless. The sync constructor accepts an injectable
Redis client (default: shared sync client from ``redis_mgr``). Async
methods do not consult the bound client; pass the async client
explicitly so the same instance can serve both sync workers and the
async API.
"""

from typing import List, Optional, Tuple

from lib.logging_utils import init_logger

logger = init_logger(__name__)


def _vcon_key(vcon_id: str) -> str:
    return f"vcon:{vcon_id}"


class VconQueue:
    """Queue + TTL operations for vCons in Redis.

    Stateless. Holds a reference to a sync Redis client for sync
    operations; defaults to the shared client managed by ``redis_mgr``.
    Async operations take an async client explicitly.
    """

    def __init__(self, client=None) -> None:
        if client is None:
            # Lazy import so test fixtures that monkey-patch
            # ``redis_mgr.redis`` see the patched value.
            import redis_mgr

            client = redis_mgr.redis
        self._client = client

    # ---- Sync queue ops --------------------------------------------

    def enqueue(self, list_name: str, vcon_id: str) -> int:
        """RPUSH a vCon id onto the tail of a queue.

        Pairs with :meth:`dequeue` (BLPOP from head) to give FIFO order.
        """
        return self._client.rpush(list_name, vcon_id)

    def enqueue_front(self, list_name: str, vcon_id: str) -> int:
        """LPUSH a vCon id onto the head of a queue.

        Reserved for "must-be-next" scenarios — e.g., a worker that
        popped a vCon and is shutting down before it could process it,
        and needs to return the vCon so the next worker sees it first.
        For normal forwarding/fan-out use :meth:`enqueue`.
        """
        return self._client.lpush(list_name, vcon_id)

    def dequeue(
        self,
        list_names: List[str],
        timeout: int = 15,
    ) -> Optional[Tuple[str, str]]:
        """Block-pop from the head of the first non-empty queue.

        Returns ``(list_name, vcon_id)`` or ``None`` on timeout.
        """
        return self._client.blpop(list_names, timeout=timeout)

    def enqueue_dlq(self, ingress_list: str, vcon_id: str) -> int:
        """RPUSH a vCon onto the DLQ derived from its ingress list.

        Uses ``dlq_utils.get_ingress_list_dlq_name`` so the naming
        convention stays in one place. Pairs with
        :meth:`dequeue_dlq_async` (LPOP) for FIFO (oldest-failure-first)
        ordering when draining the DLQ back to its ingress queue.
        """
        # Lazy import: dlq_utils lives under conserver/, not common/.
        from dlq_utils import get_ingress_list_dlq_name

        dlq_name = get_ingress_list_dlq_name(ingress_list)
        return self._client.rpush(dlq_name, vcon_id)

    def queue_length(self, list_name: str) -> int:
        return self._client.llen(list_name)

    # ---- Sync vCon-key TTL ops -------------------------------------

    def set_vcon_ttl(self, vcon_id: str, seconds: int) -> bool:
        """Set TTL on the vCon JSON key. Returns True if key existed."""
        return bool(self._client.expire(_vcon_key(vcon_id), seconds))

    # ---- Async queue ops -------------------------------------------

    async def enqueue_async(
        self, redis_async, list_name: str, *vcon_ids: str
    ) -> int:
        """Async RPUSH one or more vCon ids onto the tail of a queue.

        Accepts ``*vcon_ids`` so batched ingestion paths (e.g., the
        ``post_vcon_ingress`` endpoint) land all items in a single
        RPUSH command.
        """
        return await redis_async.rpush(list_name, *vcon_ids)

    async def queue_length_async(self, redis_async, list_name: str) -> int:
        return await redis_async.llen(list_name)

    async def dequeue_dlq_async(self, redis_async, ingress_list: str):
        """Async LPOP one vCon id off the DLQ derived from its ingress list.

        Returns the popped vCon id, or ``None`` if the DLQ is empty.
        Pairs with :meth:`enqueue_dlq` (RPUSH) to give FIFO ordering
        when draining the DLQ back onto its ingress queue.
        """
        from dlq_utils import get_ingress_list_dlq_name

        dlq_name = get_ingress_list_dlq_name(ingress_list)
        return await redis_async.lpop(dlq_name)
