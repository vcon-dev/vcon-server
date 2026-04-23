"""Dead-letter-queue handling for the conserver worker loop (Refactor #6).

Extracted from conserver/main.py::worker_loop where the DLQ branch used to
live inline as a 23-line except block (between other responsibilities like
tracing, metrics, and hook invocation). Lifting it into its own function:

- makes the DLQ policy testable in isolation
- makes the worker_loop shorter and easier to read
- gives operators a single place to change the policy (e.g. max retries,
  dead-letter fan-out) later without touching the worker loop

Behavior is unchanged vs. the previous inline block.
"""
from __future__ import annotations

import logging
from typing import Any

from dlq_utils import get_ingress_list_dlq_name
from settings import VCON_DLQ_EXPIRY


logger = logging.getLogger("conserver.dlq")


def move_to_dlq(
    redis_client: Any,
    ingress_list: str,
    vcon_id: str,
    *,
    worker_name: str = "",
    error: BaseException | None = None,
) -> str:
    """Move a failing vCon to its ingress-list-specific DLQ and extend its TTL.

    Args:
        redis_client: Redis sync client (has lpush, expire).
        ingress_list: Original ingress list the vCon was consumed from.
        vcon_id: vCon UUID.
        worker_name: Logical worker name for log context (e.g. "Worker-3").
        error: The original exception, used for log formatting only.

    Returns:
        The DLQ name the vCon was pushed onto.
    """
    dlq_name = get_ingress_list_dlq_name(ingress_list)
    prefix = f"[{worker_name}] " if worker_name else ""
    logger.info("%sMoving vCon %s to DLQ: %s", prefix, vcon_id, dlq_name)
    logger.debug(
        "%sDLQ details for vCon %s: original_queue=%s, dlq=%s, error=%s",
        prefix,
        vcon_id,
        ingress_list,
        dlq_name,
        str(error) if error is not None else "",
    )
    redis_client.lpush(dlq_name, vcon_id)

    # Extend vCon TTL so it persists while in DLQ for investigation. Without
    # this, a vCon moved to DLQ could age out before an operator can inspect
    # the failure.
    if VCON_DLQ_EXPIRY > 0:
        vcon_key = f"vcon:{vcon_id}"
        redis_client.expire(vcon_key, VCON_DLQ_EXPIRY)
        logger.debug(
            "%sExtended TTL on vCon %s to %ds for DLQ retention",
            prefix,
            vcon_id,
            VCON_DLQ_EXPIRY,
        )
    return dlq_name
