"""Thin abstraction over Redis queue operations used by the conserver.

Goal: give links and the main loop a single chokepoint for queue work so
no module has to import ``redis_mgr.redis`` directly. Redis remains the
implementation; this is *not* a pluggable-backend interface.

Operations exposed map 1:1 to the patterns already in use:

- ``enqueue(list_name, vcon_id)`` — ``LPUSH`` (head-insert, FIFO with BLPOP)
- ``route_to(list_name, vcon_id)`` — ``RPUSH`` (tail-insert, used by routers)
- ``dequeue(list_names, timeout)`` — ``BLPOP`` (blocking pop, worker loop)
- ``enqueue_dlq(ingress_list, vcon_id)`` — LPUSH onto the DLQ derived from
  an ingress list name (uses the existing ``dlq_utils`` naming convention).
- ``set_vcon_ttl(vcon_id, seconds)`` — ``EXPIRE`` on the vCon JSON key.
- ``queue_length(list_name)`` — ``LLEN``.

The class is intentionally stateless and accepts an injectable Redis client
to make unit testing easy. By default it resolves the shared client from
``redis_mgr`` so existing test fixtures that patch ``redis_mgr.redis``
continue to work unchanged.
"""

from typing import List, Optional, Tuple

from lib.logging_utils import init_logger

logger = init_logger(__name__)


def _vcon_key(vcon_id: str) -> str:
    return f"vcon:{vcon_id}"


class VconQueue:
    """Queue + TTL operations for vCons in Redis.

    Stateless. Holds a reference to a Redis client; defaults to the
    shared client managed by ``redis_mgr``.
    """

    def __init__(self, client=None) -> None:
        if client is None:
            # Lazy import so test fixtures that monkey-patch
            # ``redis_mgr.redis`` see the patched value.
            import redis_mgr

            client = redis_mgr.redis
        self._client = client

    # ---- Queue ops -------------------------------------------------

    def enqueue(self, list_name: str, vcon_id: str) -> int:
        """LPUSH a vCon id onto a queue. Pairs with ``dequeue`` (BLPOP)."""
        return self._client.lpush(list_name, vcon_id)

    def route_to(self, list_name: str, vcon_id: str) -> int:
        """RPUSH a vCon id onto a queue. Used by tag_router / fan-out."""
        return self._client.rpush(list_name, str(vcon_id))

    def dequeue(
        self,
        list_names: List[str],
        timeout: int = 15,
    ) -> Optional[Tuple[str, str]]:
        """Block-pop from the first non-empty queue.

        Returns ``(list_name, vcon_id)`` or ``None`` on timeout.
        """
        return self._client.blpop(list_names, timeout=timeout)

    def enqueue_dlq(self, ingress_list: str, vcon_id: str) -> int:
        """Push a vCon onto the DLQ derived from its ingress list.

        Uses ``dlq_utils.get_ingress_list_dlq_name`` so the naming
        convention stays in one place.
        """
        # Lazy import: dlq_utils lives under conserver/, not common/.
        from dlq_utils import get_ingress_list_dlq_name

        dlq_name = get_ingress_list_dlq_name(ingress_list)
        return self._client.lpush(dlq_name, vcon_id)

    def queue_length(self, list_name: str) -> int:
        return self._client.llen(list_name)

    # ---- vCon-key TTL ops -----------------------------------------

    def set_vcon_ttl(self, vcon_id: str, seconds: int) -> bool:
        """Set TTL on the vCon JSON key. Returns True if key existed."""
        return bool(self._client.expire(_vcon_key(vcon_id), seconds))
