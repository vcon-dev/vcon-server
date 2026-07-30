"""Tests for the storage dead-letter path (CON-714).

A failed storage write used to be logged and dropped: the vCon never reached
the backend, nothing queued it, and the chain reported success. On BDS that
meant a ~100s outage of one backend silently lost every vCon written during it.

These tests pin the two halves of the fix: failures land on a per-backend DLQ
with the vCon body kept alive long enough to replay, and the vcon-mcp client
retries the failures that are worth retrying.
"""

from unittest.mock import MagicMock, patch

import pytest

from lib.queue import VconQueue


class TestEnqueueStorageDlq:
    def test_emits_counter_with_storage_dlq_name(self):
        """Reuses ``conserver.dlq.count`` so an existing alert on that metric
        covers storage failures without a new rule."""
        mock_client = MagicMock()
        mock_client.rpush.return_value = 1
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter") as inc:
            q.enqueue_storage_dlq("vcon_mcp", "vcon-uuid-1234")

        mock_client.rpush.assert_called_once_with("DLQ:storage:vcon_mcp", "vcon-uuid-1234")
        inc.assert_called_once_with(
            "conserver.dlq.count",
            attributes={"queue_name": "DLQ:storage:vcon_mcp"},
        )

    def test_storage_dlq_is_distinct_from_ingress_dlq(self):
        """A storage failure must not land on the ingress DLQ: replaying from
        there re-runs the whole chain, including transcription."""
        mock_client = MagicMock()
        mock_client.rpush.return_value = 1
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter"):
            q.enqueue_storage_dlq("vcon_mcp", "v1")
            q.enqueue_dlq("vcon_mcp", "v1")

        pushed = [call.args[0] for call in mock_client.rpush.call_args_list]
        assert pushed == ["DLQ:storage:vcon_mcp", "DLQ:vcon_mcp"]

    def test_no_counter_when_rpush_fails(self):
        """Only count entries that actually landed."""
        mock_client = MagicMock()
        mock_client.rpush.side_effect = RuntimeError("redis down")
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter") as inc:
            with pytest.raises(RuntimeError):
                q.enqueue_storage_dlq("vcon_mcp", "v1")

        inc.assert_not_called()

    def test_returns_rpush_result(self):
        mock_client = MagicMock()
        mock_client.rpush.return_value = 42
        q = VconQueue(client=mock_client)

        with patch("lib.queue.increment_counter"):
            assert q.enqueue_storage_dlq("vcon_mcp", "v1") == 42


class TestProcessStorageDeadLetters:
    """``_process_storage`` must dead-letter on failure instead of dropping."""

    def _make_request(self):
        from main import VconChainRequest

        return VconChainRequest(
            chain_details={"name": "test_chain", "links": [], "storages": ["vcon_mcp"]},
            vcon_id="vcon-uuid-1234",
        )

    def test_failed_write_is_dead_lettered_and_ttl_extended(self):
        req = self._make_request()

        with patch("main.Storage") as mock_storage, \
             patch("main.queue") as mock_queue, \
             patch("main.VCON_DLQ_EXPIRY", 604800):
            mock_storage.return_value.save.side_effect = RuntimeError("401 Unauthorized")
            req._process_storage("vcon_mcp")

        mock_queue.enqueue_storage_dlq.assert_called_once_with("vcon_mcp", "vcon-uuid-1234")
        mock_queue.set_vcon_ttl.assert_called_once_with("vcon-uuid-1234", 604800)

    def test_successful_write_is_not_dead_lettered(self):
        req = self._make_request()

        with patch("main.Storage"), patch("main.queue") as mock_queue:
            req._process_storage("vcon_mcp")

        mock_queue.enqueue_storage_dlq.assert_not_called()

    def test_process_storage_still_does_not_raise(self):
        """The chain must keep going when one backend fails; other backends
        and egress still need to run."""
        req = self._make_request()

        with patch("main.Storage") as mock_storage, patch("main.queue"):
            mock_storage.return_value.save.side_effect = RuntimeError("boom")
            req._process_storage("vcon_mcp")  # must not raise

    def test_ttl_not_extended_when_expiry_disabled(self):
        req = self._make_request()

        with patch("main.Storage") as mock_storage, \
             patch("main.queue") as mock_queue, \
             patch("main.VCON_DLQ_EXPIRY", 0):
            mock_storage.return_value.save.side_effect = RuntimeError("boom")
            req._process_storage("vcon_mcp")

        mock_queue.enqueue_storage_dlq.assert_called_once()
        mock_queue.set_vcon_ttl.assert_not_called()

    def test_redis_failure_while_dead_lettering_does_not_propagate(self):
        """If Redis is down too the vCon is genuinely lost, but that must not
        also take down the chain."""
        req = self._make_request()

        with patch("main.Storage") as mock_storage, patch("main.queue") as mock_queue:
            mock_storage.return_value.save.side_effect = RuntimeError("boom")
            mock_queue.enqueue_storage_dlq.side_effect = RuntimeError("redis down")
            req._process_storage("vcon_mcp")  # must not raise


class TestStorageDlqReprocessEndpoint:
    """``POST /dlq/storage/reprocess`` replays the write, not the chain."""

    def _call(self, dlq_items, save_side_effect=None, count=1000):
        import asyncio

        import api as api_module

        popped = list(dlq_items)

        async def fake_pop(_redis, _storage_name):
            return popped.pop(0) if popped else None

        mock_queue = MagicMock()
        mock_queue.dequeue_storage_dlq_async = fake_pop
        mock_storage = MagicMock()
        if save_side_effect is not None:
            mock_storage.return_value.save.side_effect = save_side_effect

        # ``redis_async`` is bound by the app's lifespan startup, so it does not
        # exist when the endpoint is called directly.
        with patch.object(api_module, "queue", mock_queue), \
             patch.object(api_module, "Storage", mock_storage), \
             patch.object(api_module, "redis_async", MagicMock(), create=True):
            response = asyncio.run(
                api_module.post_storage_dlq_reprocess(storage_name="vcon_mcp", count=count)
            )
        return response, mock_storage, mock_queue

    def test_replays_each_vcon_through_storage_save(self):
        response, mock_storage, _ = self._call(["v1", "v2", "v3"])

        assert response.body == b"3"
        saved = [call.args[0] for call in mock_storage.return_value.save.call_args_list]
        assert saved == ["v1", "v2", "v3"]

    def test_stops_and_requeues_when_backend_still_down(self):
        """A still-broken backend must not drain the DLQ into nothing."""
        response, mock_storage, mock_queue = self._call(
            ["v1", "v2", "v3"], save_side_effect=RuntimeError("still 401")
        )

        assert response.body == b"0"
        # First item is put back, and we stop rather than popping the rest.
        mock_queue.enqueue_storage_dlq.assert_called_once_with("vcon_mcp", "v1")
        assert mock_storage.return_value.save.call_count == 1

    def test_empty_dlq_returns_zero(self):
        response, mock_storage, _ = self._call([])

        assert response.body == b"0"
        mock_storage.return_value.save.assert_not_called()

    def test_count_bounds_the_work(self):
        """Mirrors the CON-575 fix on /dlq/reprocess: bounded per call."""
        response, mock_storage, _ = self._call(["v1", "v2", "v3"], count=2)

        assert response.body == b"2"
        assert mock_storage.return_value.save.call_count == 2


class TestVconMcpRetries:
    """Transient failures should be retried before the vCon is dead-lettered."""

    def _adapter(self, opts=None):
        from storage.vcon_mcp import _session, default_options

        session = _session(opts if opts is not None else default_options)
        return session.get_adapter("http://example.com")

    def test_retries_transient_statuses_only(self):
        retry = self._adapter().max_retries

        assert set(retry.status_forcelist) == {429, 502, 503, 504}
        # A 401 or 400 is a decision the server already made; retrying it only
        # delays the dead-letter.
        assert 401 not in retry.status_forcelist
        assert 400 not in retry.status_forcelist

    def test_post_is_retryable_because_vcon_mcp_upserts(self):
        """urllib3 excludes POST by default. vcon-mcp upserts on the vCon uuid,
        so a retried create converges instead of duplicating."""
        retry = self._adapter().max_retries

        assert "POST" in retry.allowed_methods

    def test_defaults_match_documented_options(self):
        retry = self._adapter().max_retries

        assert retry.total == 3
        assert retry.backoff_factor == 0.5
        assert retry.respect_retry_after_header is True

    def test_options_override_defaults(self):
        retry = self._adapter(
            {"transient_retries": 7, "transient_backoff_base_s": 1.5}
        ).max_retries

        assert retry.total == 7
        assert retry.backoff_factor == 1.5
