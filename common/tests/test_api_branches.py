import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch
from uuid import uuid4

import pytest

import api


@pytest.fixture
def redis_async(monkeypatch):
    redis = Mock()
    redis_json = Mock()
    redis_json.get = AsyncMock()
    redis_json.mget = AsyncMock()
    redis_json.set = AsyncMock()
    redis_json.delete = AsyncMock()
    redis.json = Mock(return_value=redis_json)
    redis.expire = AsyncMock()
    redis.zrevrangebyscore = AsyncMock()
    redis.rpop = AsyncMock()
    redis.rpush = AsyncMock()
    redis.llen = AsyncMock()
    redis.smembers = AsyncMock()
    redis.sadd = AsyncMock()
    redis.lrange = AsyncMock()
    redis.keys = AsyncMock()
    monkeypatch.setattr(api, "redis_async", redis, raising=False)
    return redis


@pytest.mark.asyncio
async def test_ensure_vcon_in_redis_returns_cached_vcon(redis_async):
    vcon_uuid = uuid4()
    redis_async.json.return_value.get.return_value = {"uuid": str(vcon_uuid)}

    with patch.object(api, "sync_vcon_from_storage", AsyncMock()) as mock_sync:
        result = await api.ensure_vcon_in_redis(vcon_uuid)

    assert result == {"uuid": str(vcon_uuid)}
    mock_sync.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_vcon_in_redis_falls_back_to_storage_sync(redis_async):
    vcon_uuid = uuid4()
    redis_async.json.return_value.get.return_value = None

    with patch.object(api, "sync_vcon_from_storage", AsyncMock(return_value={"uuid": str(vcon_uuid)})) as mock_sync:
        result = await api.ensure_vcon_in_redis(vcon_uuid)

    assert result == {"uuid": str(vcon_uuid)}
    mock_sync.assert_awaited_once_with(vcon_uuid)


@pytest.mark.asyncio
async def test_sync_vcon_from_storage_restores_to_redis_and_indexes(redis_async):
    vcon_uuid = uuid4()
    vcon = {"uuid": str(vcon_uuid), "created_at": "2024-01-01T12:00:00"}
    storage_a = Mock(get=Mock(return_value=None))
    storage_b = Mock(get=Mock(return_value=vcon))

    with patch.object(api.Configuration, "get_storages", return_value=["a", "b"]), patch.object(
        api, "Storage", side_effect=[storage_a, storage_b]
    ), patch.object(api, "add_vcon_to_set", AsyncMock()) as mock_add_to_set:
        result = await api.sync_vcon_from_storage(vcon_uuid)

    assert result == vcon
    redis_async.json.return_value.set.assert_awaited_once_with(f"vcon:{vcon_uuid}", "$", vcon)
    redis_async.expire.assert_awaited_once_with(f"vcon:{vcon_uuid}", api.VCON_REDIS_EXPIRY)
    mock_add_to_set.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_vcon_from_storage_returns_none_when_not_found(redis_async):
    with patch.object(api.Configuration, "get_storages", return_value=["a"]), patch.object(
        api, "Storage", return_value=Mock(get=Mock(return_value=None))
    ):
        assert await api.sync_vcon_from_storage(uuid4()) is None

    redis_async.json.return_value.set.assert_not_called()


@pytest.mark.asyncio
async def test_get_vcons_uuids_uses_date_filters_and_strips_prefix(redis_async):
    redis_async.zrevrangebyscore.return_value = ["vcon:one", "vcon:two"]
    since = datetime(2024, 1, 1, 0, 0, 0)
    until = datetime(2024, 1, 2, 0, 0, 0)

    result = await api.get_vcons_uuids(page=2, size=3, since=since, until=until)

    assert result == ["one", "two"]
    redis_async.zrevrangebyscore.assert_awaited_once_with(
        api.VCON_SORTED_SET_NAME,
        int(until.timestamp()),
        int(since.timestamp()),
        start=3,
        num=3,
    )


@pytest.mark.asyncio
async def test_get_vcon_egress_pops_multiple_items_and_handles_errors(redis_async):
    redis_async.rpop.side_effect = ["one", None, "two"]

    response = await api.get_vcon_egress("egress", limit=3)

    assert json.loads(response.body) == ["one", "two"]

    redis_async.rpop.side_effect = RuntimeError("redis down")
    with pytest.raises(api.HTTPException, match="Failed to pop from egress list"):
        await api.get_vcon_egress("egress", limit=1)


@pytest.mark.asyncio
async def test_get_vcons_uses_mget_and_storage_fallback(redis_async):
    first_uuid = uuid4()
    second_uuid = uuid4()
    redis_async.json.return_value.mget.return_value = [{"uuid": str(first_uuid)}, None]

    with patch.object(
        api, "sync_vcon_from_storage", AsyncMock(return_value={"uuid": str(second_uuid)})
    ) as mock_sync:
        response = await api.get_vcons([first_uuid, second_uuid])

    assert json.loads(response.body) == [{"uuid": str(first_uuid)}, {"uuid": str(second_uuid)}]
    mock_sync.assert_awaited_once_with(second_uuid)


@pytest.mark.asyncio
async def test_search_vcons_validates_params_and_supports_union_intersection_and_errors(redis_async):
    with pytest.raises(api.HTTPException, match="At least one search parameter"):
        await api.search_vcons(tel=None, mailto=None, name=None)

    redis_async.smembers.side_effect = [["a", "b"], ["b"], ["b", "c"]]
    assert sorted(await api.search_vcons(tel="123", mailto=None, name=None)) == ["a", "b"]
    assert await api.search_vcons(tel="123", mailto=None, name="Alice") == ["b"]

    redis_async.smembers.side_effect = RuntimeError("smembers failed")
    with pytest.raises(api.HTTPException, match="An error occurred during the search"):
        await api.search_vcons(tel=None, mailto="person@example.com", name=None)


@pytest.mark.asyncio
async def test_delete_vcon_continues_through_partial_failures(redis_async):
    vcon_uuid = uuid4()
    redis_async.json.return_value.delete.side_effect = RuntimeError("redis delete failed")
    storage_a = Mock(delete=Mock(return_value=False))
    storage_b = Mock(delete=Mock(side_effect=RuntimeError("storage failed")))

    with patch.object(api.Configuration, "get_storages", return_value=["a", "b"]), patch.object(
        api, "Storage", side_effect=[storage_a, storage_b]
    ), patch.object(api.vcon_hook, "on_vcon_deleted", side_effect=RuntimeError("hook failed")):
        await api.delete_vcon(vcon_uuid)

    redis_async.json.return_value.delete.assert_awaited_once_with(f"vcon:{vcon_uuid}")


@pytest.mark.asyncio
async def test_post_vcon_ingress_adds_only_valid_vcons_and_stores_context(redis_async):
    first_uuid = uuid4()
    second_uuid = uuid4()
    third_uuid = uuid4()
    redis_async.json.return_value.mget.return_value = [None, {"uuid": str(second_uuid)}, None]

    with patch.object(
        api,
        "sync_vcon_from_storage",
        AsyncMock(side_effect=[{"uuid": str(first_uuid)}, None]),
    ), patch.object(api, "extract_otel_trace_context", return_value={"traceparent": "abc"}), patch.object(
        api, "store_context_async", AsyncMock()
    ) as mock_store_context:
        await api.post_vcon_ingress([first_uuid, second_uuid, third_uuid], ingress_list="ingress-a")

    mock_store_context.assert_has_awaits(
        [
            call(redis_async, "ingress-a", str(first_uuid), {"traceparent": "abc"}),
            call(redis_async, "ingress-a", str(second_uuid), {"traceparent": "abc"}),
        ]
    )
    redis_async.rpush.assert_awaited_once_with("ingress-a", str(first_uuid), str(second_uuid))


@pytest.mark.asyncio
async def test_post_vcon_ingress_raises_for_redis_errors(redis_async):
    redis_async.json.return_value.mget.side_effect = RuntimeError("mget failed")

    with pytest.raises(api.HTTPException, match="Failed to add to ingress list"):
        await api.post_vcon_ingress([uuid4()], ingress_list="ingress-a")


@pytest.mark.asyncio
async def test_get_vcon_count_get_config_and_dlq_endpoints_cover_success_and_error_paths(redis_async):
    redis_async.llen.return_value = 7
    count_response = await api.get_vcon_count("egress-a")
    assert json.loads(count_response.body) == 7

    redis_async.llen.side_effect = RuntimeError("llen failed")
    with pytest.raises(api.HTTPException, match="Failed to count egress list"):
        await api.get_vcon_count("egress-a")

    with patch.object(api.Configuration, "get_config", return_value={"foo": "bar"}):
        config_response = await api.get_config()
    assert json.loads(config_response.body) == {"foo": "bar"}

    with patch.object(api.Configuration, "get_config", side_effect=RuntimeError("config failed")):
        with pytest.raises(api.HTTPException, match="Failed to read configuration"):
            await api.get_config()

    redis_async.rpop.side_effect = ["a", "b", None]
    with patch.object(api, "get_ingress_list_dlq_name", return_value="ingress-a:dlq"):
        dlq_response = await api.post_dlq_reprocess("ingress-a")
    assert json.loads(dlq_response.body) == 2
    redis_async.rpush.assert_awaited_with("ingress-a", "b")

    redis_async.rpop.side_effect = RuntimeError("dlq failed")
    with patch.object(api, "get_ingress_list_dlq_name", return_value="ingress-a:dlq"):
        with pytest.raises(api.HTTPException, match="Failed to reprocess DLQ"):
            await api.post_dlq_reprocess("ingress-a")

    redis_async.lrange.return_value = ["x", "y"]
    with patch.object(api, "get_ingress_list_dlq_name", return_value="ingress-a:dlq"):
        get_dlq_response = await api.get_dlq_vcons("ingress-a")
    assert json.loads(get_dlq_response.body) == ["x", "y"]

    redis_async.lrange.side_effect = RuntimeError("lrange failed")
    with patch.object(api, "get_ingress_list_dlq_name", return_value="ingress-a:dlq"):
        with pytest.raises(api.HTTPException, match="Failed to read DLQ"):
            await api.get_dlq_vcons("ingress-a")


@pytest.mark.asyncio
async def test_index_helpers_cover_parties_single_vcon_and_bulk_reindex(redis_async):
    await api.index_vcon_parties(
        "vc-1",
        [{"tel": "+123", "mailto": "a@example.com", "name": "Alice"}, {"name": "Bob"}],
    )

    redis_async.sadd.assert_has_awaits(
        [
            call("tel:+123", "vc-1"),
            call("mailto:a@example.com", "vc-1"),
            call("name:Alice", "vc-1"),
            call("name:Bob", "vc-1"),
        ]
    )

    redis_async.json.return_value.get.return_value = {
        "uuid": "vc-2",
        "created_at": "2024-01-01T10:00:00",
        "parties": [{"name": "Alice"}],
    }
    with patch.object(api, "add_vcon_to_set", AsyncMock()) as mock_add_to_set, patch.object(
        api, "index_vcon_parties", AsyncMock()
    ) as mock_index_parties:
        await api.index_vcon("vc-2")

    mock_add_to_set.assert_awaited_once()
    mock_index_parties.assert_awaited_once_with("vc-2", [{"name": "Alice"}])

    redis_async.keys.return_value = ["vcon:one", "vcon:two"]
    with patch.object(api, "index_vcon", AsyncMock()) as mock_index_vcon:
        response = await api.index_vcons()
    assert json.loads(response.body) == 2
    mock_index_vcon.assert_has_awaits([call("one"), call("two")])

    redis_async.keys.side_effect = RuntimeError("keys failed")
    with pytest.raises(api.HTTPException):
        await api.index_vcons()
