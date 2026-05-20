"""Observable gauges emitting Redis-derived conserver health metrics.

Two gauges are exported on every metric-export tick:

  ``conserver.ingress_list.length`` — one observation per
    ``(ingress_list, kind)`` combination, sampled via ``LLEN``. The
    ``ingress_list`` attribute carries the configured name (e.g.
    ``"transcribe"``); ``kind`` is ``"ingress"`` for the live queue and
    ``"dlq"`` for the derived dead-letter queue. The ingress-list set is
    re-read from configuration on every tick, so chain config changes
    propagate without a conserver restart.

  ``conserver.redis.memory_used_bytes`` — current ``used_memory`` from
    ``INFO memory``. Single series per pod (no per-key attributes); the
    pod identity already lives on the resource attributes.
"""

from opentelemetry.metrics import Observation

from dlq_utils import get_ingress_list_dlq_name
from lib.logging_utils import init_logger
from lib.metrics import register_observable_gauge

logger = init_logger(__name__)


def _get_configured_ingress_lists():
    """Return the set of ingress list names from the live chain config.

    Imported lazily so test fixtures that monkey-patch ``Configuration``
    see the patched value. Returns an empty list on any config-read
    failure so the gauge degrades to "no series" rather than crashing
    the export tick.
    """
    try:
        from config import Configuration

        chains = Configuration.get_config().get("chains", {}) or {}
        names = set()
        for chain_config in chains.values():
            for name in chain_config.get("ingress_lists", []) or []:
                if name:
                    names.add(name)
        return sorted(names)
    except Exception as e:
        logger.warning("Failed to read ingress list config for gauge: %s", e)
        return []


def _build_callback(client):
    """Return a zero-arg callback that yields one Observation per
    ``(ingress_list, kind)`` combination.

    Each call performs one LLEN per series — typically a handful of cheap
    Redis round-trips per export interval. Errors on individual LLENs are
    logged and skipped; the export tick still publishes the series that
    succeeded.
    """

    def _callback():
        observations = []
        for ingress_list in _get_configured_ingress_lists():
            for kind, key in (
                ("ingress", ingress_list),
                ("dlq", get_ingress_list_dlq_name(ingress_list)),
            ):
                try:
                    length = client.llen(key)
                except Exception as e:
                    logger.warning(
                        "LLEN failed for %s (ingress_list=%s, kind=%s): %s",
                        key, ingress_list, kind, e,
                    )
                    continue
                observations.append(
                    Observation(
                        value=length,
                        attributes={"ingress_list": ingress_list, "kind": kind},
                    )
                )
        return observations

    return _callback


def register_ingress_list_length_gauge(client):
    """Register the ``conserver.ingress_list.length`` observable gauge.

    Idempotent — safe to call multiple times per process. The callback
    captures ``client`` by reference, so the same gauge instance follows
    any Redis client swap done via the same ``client`` object.

    Args:
        client: A Redis client with an ``llen(key)`` method. In production
            this is the worker's ``redis_mgr`` client; in tests, a
            ``MagicMock``.
    """
    register_observable_gauge(
        metric_name="conserver.ingress_list.length",
        callback=_build_callback(client),
        description=(
            "Current Redis LLEN for each configured ingress list and its "
            "derived DLQ. Attributes: ingress_list (configured name), "
            "kind (ingress|dlq)."
        ),
    )


def _build_redis_memory_callback(client):
    """Return a zero-arg callback that yields one Observation for
    ``conserver.redis.memory_used_bytes`` per export tick.

    Reads ``used_memory`` from ``INFO memory``. One round-trip per tick;
    negligible cost. Returns an empty list on any failure so the export
    tick still publishes everything else cleanly.
    """

    def _callback():
        try:
            info = client.info(section="memory")
        except Exception as e:
            logger.warning("Redis INFO memory failed: %s", e)
            return []

        used = info.get("used_memory") if isinstance(info, dict) else None
        if used is None:
            return []

        try:
            value = int(used)
        except (TypeError, ValueError):
            logger.warning("Redis INFO memory used_memory not int-coercible: %r", used)
            return []

        return [Observation(value=value, attributes={})]

    return _callback


def register_redis_memory_gauge(client):
    """Register the ``conserver.redis.memory_used_bytes`` observable gauge.

    Idempotent — safe to call multiple times per process. Restores the
    Redis memory signal that monitoring stacks previously got from a
    separately-deployed Redis exporter.

    Args:
        client: A Redis client with an ``info(section=...)`` method.
    """
    register_observable_gauge(
        metric_name="conserver.redis.memory_used_bytes",
        callback=_build_redis_memory_callback(client),
        description=(
            "Current Redis memory usage in bytes (used_memory from INFO memory). "
            "One series per conserver pod."
        ),
    )
