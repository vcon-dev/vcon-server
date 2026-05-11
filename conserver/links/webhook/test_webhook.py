from unittest.mock import MagicMock, call, patch

import pytest

from links.webhook import run


def _mock_vcon(payload=None):
    vcon = MagicMock()
    vcon.to_dict.return_value = payload or {"uuid": "test-uuid", "dialog": []}
    return vcon


@patch("links.webhook.increment_counter")
@patch("links.webhook.VconRedis")
def test_run_skips_when_no_webhook_urls(mock_vcon_redis, mock_increment_counter):
    mock_vcon_redis.return_value.get_vcon.return_value = _mock_vcon()

    result = run("test-uuid", "webhook", opts={})

    assert result == "test-uuid"
    mock_increment_counter.assert_called_once_with(
        "conserver.link.webhook.no_urls_configured",
        attributes={"link.name": "webhook", "vcon.uuid": "test-uuid"},
    )


@patch("links.webhook.requests.post")
@patch("links.webhook.VconRedis")
def test_run_posts_to_each_configured_webhook(mock_vcon_redis, mock_post):
    payload = {"uuid": "test-uuid", "dialog": [{"type": "text", "body": "hello"}]}
    mock_vcon_redis.return_value.get_vcon.return_value = _mock_vcon(payload)
    mock_post.return_value = MagicMock(status_code=200, text="ok")

    result = run(
        "test-uuid",
        "webhook",
        opts={
            "webhook-urls": ["https://example.test/a", "https://example.test/b"],
            "headers": {"Authorization": "Bearer token"},
        },
    )

    assert result == "test-uuid"
    assert mock_post.call_args_list == [
        call(
            "https://example.test/a",
            json=payload,
            headers={"Authorization": "Bearer token"},
        ),
        call(
            "https://example.test/b",
            json=payload,
            headers={"Authorization": "Bearer token"},
        ),
    ]


@patch("links.webhook.requests.post")
@patch("links.webhook.increment_counter")
@patch("links.webhook.VconRedis")
def test_run_raises_and_counts_post_failures(mock_vcon_redis, mock_increment_counter, mock_post):
    mock_vcon_redis.return_value.get_vcon.return_value = _mock_vcon()
    mock_post.side_effect = Exception("webhook failed")

    with pytest.raises(Exception, match="webhook failed"):
        run(
            "test-uuid",
            "webhook",
            opts={"webhook-urls": ["https://example.test/a"]},
        )

    mock_increment_counter.assert_called_once_with(
        "conserver.link.webhook.post_failures",
        attributes={"link.name": "webhook", "vcon.uuid": "test-uuid"},
    )


@patch("links.webhook.requests.post")
@patch("links.webhook.VconRedis")
def test_run_returns_uuid_even_for_non_2xx_response(mock_vcon_redis, mock_post):
    mock_vcon_redis.return_value.get_vcon.return_value = _mock_vcon()
    mock_post.return_value = MagicMock(status_code=500, text="bad gateway")

    result = run(
        "test-uuid",
        "webhook",
        opts={"webhook-urls": ["https://example.test/a"]},
    )

    assert result == "test-uuid"
