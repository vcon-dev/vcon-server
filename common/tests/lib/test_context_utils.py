import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry import trace

from lib.context_utils import (
    extract_otel_trace_context,
    get_context_key,
    retrieve_context,
    store_context_async,
    store_context_sync,
)
from settings import VCON_CONTEXT_EXPIRY


def test_get_context_key_formats_key():
    assert get_context_key("ingress-a", "uuid-123") == "context:ingress-a:uuid-123"


@pytest.mark.asyncio
async def test_store_context_async_pushes_json_and_sets_expiry():
    redis_client = MagicMock()
    redis_client.rpush = AsyncMock()
    redis_client.expire = AsyncMock()

    await store_context_async(
        redis_client,
        "ingress-a",
        "uuid-123",
        {"trace_id": "abc", "is_sampled": True},
    )

    redis_client.rpush.assert_awaited_once_with(
        "context:ingress-a:uuid-123",
        json.dumps({"trace_id": "abc", "is_sampled": True}),
    )
    redis_client.expire.assert_awaited_once_with(
        "context:ingress-a:uuid-123",
        VCON_CONTEXT_EXPIRY,
    )


def test_store_context_sync_noops_for_empty_context():
    redis_client = MagicMock()

    store_context_sync(redis_client, "ingress-a", "uuid-123", {})

    redis_client.rpush.assert_not_called()
    redis_client.expire.assert_not_called()


def test_retrieve_context_returns_oldest_json_payload():
    redis_client = MagicMock()
    redis_client.lpop.return_value = json.dumps({"trace_id": "abc"})

    result = retrieve_context(redis_client, "ingress-a", "uuid-123")

    assert result == {"trace_id": "abc"}
    redis_client.lpop.assert_called_once_with("context:ingress-a:uuid-123")


def test_retrieve_context_returns_none_for_invalid_json():
    redis_client = MagicMock()
    redis_client.lpop.return_value = "{bad json"

    assert retrieve_context(redis_client, "ingress-a", "uuid-123") is None


@patch("lib.context_utils.trace.get_current_span")
def test_extract_otel_trace_context_returns_formatted_ids(mock_get_current_span):
    span_context = MagicMock()
    span_context.is_valid = True
    span_context.trace_id = 0x1234
    span_context.span_id = 0x5678
    span_context.trace_flags = int(trace.TraceFlags.SAMPLED)

    span = MagicMock()
    span.get_span_context.return_value = span_context
    mock_get_current_span.return_value = span

    context = extract_otel_trace_context()

    assert context == {
        "trace_id": "00000000000000000000000000001234",
        "span_id": "0000000000005678",
        "trace_flags": 1,
        "is_sampled": True,
    }


@patch("lib.context_utils.trace.get_current_span")
def test_extract_otel_trace_context_returns_none_for_invalid_span(mock_get_current_span):
    span_context = MagicMock()
    span_context.is_valid = False

    span = MagicMock()
    span.get_span_context.return_value = span_context
    mock_get_current_span.return_value = span

    assert extract_otel_trace_context() is None
