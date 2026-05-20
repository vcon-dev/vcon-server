"""Unit tests for ``conserver.dlq.count`` emission from ``VconQueue.enqueue_dlq``.

The counter is the only signal external monitoring (SignOz alert
``vCons routed to DLQ``) has that vCons are failing the chain.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.queue import VconQueue


class TestEnqueueDlqEmitsCounter:
    def test_emits_counter_with_queue_name_attribute(self):
        """``enqueue_dlq`` emits ``conserver.dlq.count`` with the resolved DLQ
        name as the ``queue_name`` attribute (not the bare ingress list)."""
        mock_client = MagicMock()
        mock_client.rpush.return_value = 1
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter") as inc:
            q.enqueue_dlq("transcribe", "vcon-uuid-1234")

        inc.assert_called_once_with(
            "conserver.dlq.count",
            attributes={"queue_name": "DLQ:transcribe"},
        )

    def test_rpush_is_called_before_counter(self):
        """If the RPUSH itself raises (e.g. Redis dead), the counter must
        NOT increment — we only want to count actual DLQ entries."""
        mock_client = MagicMock()
        mock_client.rpush.side_effect = RuntimeError("redis down")
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter") as inc:
            with pytest.raises(RuntimeError):
                q.enqueue_dlq("transcribe", "vcon-uuid-1234")

        inc.assert_not_called()

    def test_returns_rpush_result(self):
        """The new code path must preserve the existing return value
        contract (the new list length, per redis-py ``rpush``)."""
        mock_client = MagicMock()
        mock_client.rpush.return_value = 42
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter"):
            assert q.enqueue_dlq("transcribe", "vcon-uuid-1234") == 42

    def test_counter_uses_dlq_name_for_each_ingress(self):
        """Different ingress lists must produce different ``queue_name``
        attributes, so the SignOz alert can group by ingress."""
        mock_client = MagicMock()
        mock_client.rpush.return_value = 1
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter") as inc:
            q.enqueue_dlq("transcribe", "v1")
            q.enqueue_dlq("default", "v2")
            q.enqueue_dlq("scitt_backfill", "v3")

        assert inc.call_count == 3
        seen = {call.kwargs["attributes"]["queue_name"] for call in inc.call_args_list}
        assert seen == {"DLQ:transcribe", "DLQ:default", "DLQ:scitt_backfill"}
