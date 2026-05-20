"""Observable gauge emitting current ingress-list and DLQ depths.

The gauge ``conserver.ingress_list.length`` is sampled on every metric-export
tick. Each observation carries:

  - ``ingress_list`` — the configured ingress list name as it appears in the
    chain config (e.g. ``"transcribe"``)
  - ``kind`` — ``"ingress"`` for the live queue, ``"dlq"`` for the derived
    dead-letter queue

Splitting ``kind`` into its own attribute (rather than baking ``DLQ:`` into
the value) lets monitoring queries select live vs DLQ depth without regex
parsing the metric label.

The ingress-list set is re-read from configuration on every tick, so chain
config changes propagate without a conserver restart.
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
