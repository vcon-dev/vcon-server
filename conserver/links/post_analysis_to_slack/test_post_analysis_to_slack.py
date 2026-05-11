from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from links.post_analysis_to_slack import (
    get_dealer,
    get_summary,
    get_team,
    post_blocks_to_channel,
    run,
)


def _build_vcon():
    return SimpleNamespace(
        uuid="test-uuid",
        attachments=[
            {
                "type": "strolid_dealer",
                "body": {
                    "name": "Dealer One",
                    "team": {"name": "Acme Toyota"},
                },
            }
        ],
        analysis=[
            {
                "dialog": 0,
                "type": "customer_frustration",
                "body": "Customer is angry and NEEDS REVIEW immediately",
            },
            {
                "dialog": 0,
                "type": "summary",
                "body": "Summary for Slack",
            },
        ],
    )


def test_helper_functions_extract_team_dealer_and_summary():
    vcon = _build_vcon()

    assert get_team(vcon) == "acme"
    assert get_dealer(vcon) == "Dealer One"
    assert get_summary(vcon, 0)["body"] == "Summary for Slack"
    assert get_summary(vcon, 1) is None


@patch("links.post_analysis_to_slack.increment_counter")
@patch("links.post_analysis_to_slack.WebClient")
def test_post_blocks_to_channel_falls_back_and_reraises(mock_web_client, mock_increment_counter):
    client = MagicMock()
    client.chat_postMessage.side_effect = [Exception("missing channel"), None]
    mock_web_client.return_value = client

    with pytest.raises(Exception, match="missing channel"):
        post_blocks_to_channel(
            token="test-token",
            channel_name="team-acme-alerts",
            abstract="summary",
            url="https://details.test",
            opts={"default_channel_name": "fallback-alerts"},
            attrs={"link.name": "post_analysis_to_slack", "vcon.uuid": "test-uuid"},
        )

    mock_increment_counter.assert_called_once_with(
        "conserver.link.slack.fallback_channel_used",
        attributes={"link.name": "post_analysis_to_slack", "vcon.uuid": "test-uuid"},
    )
    assert client.chat_postMessage.call_args_list == [
        call(
            channel="team-acme-alerts",
            blocks=ANY,
            text="summary",
        ),
        call(
            channel="fallback-alerts",
            text="The channel name doesn't exist - team-acme-alerts",
        ),
    ]


@patch("links.post_analysis_to_slack.post_blocks_to_channel")
@patch("links.post_analysis_to_slack.VconRedis")
def test_run_posts_to_team_and_default_channels_and_marks_analysis(mock_vcon_redis, mock_post_blocks):
    vcon = _build_vcon()
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    result = run(
        "test-uuid",
        "post_analysis_to_slack",
        opts={
            "token": "test-token",
            "default_channel_name": "default-alerts",
            "url": "https://details.test",
        },
    )

    assert result == "test-uuid"
    assert mock_post_blocks.call_args_list == [
        call(
            "test-token",
            "team-acme-alerts",
            "Summary for Slack #Dealer One",
            'https://details.test?_vcon_id="test-uuid"',
            {
                "token": "test-token",
                "channel_name": None,
                "url": "https://details.test",
                "analysis_to_post": "summary",
                "only_if": {"analysis_type": "customer_frustration", "includes": "NEEDS REVIEW"},
                "default_channel_name": "default-alerts",
            },
            attrs={"link.name": "post_analysis_to_slack", "vcon.uuid": "test-uuid"},
        ),
        call(
            "test-token",
            "default-alerts",
            "Summary for Slack #Dealer One",
            'https://details.test?_vcon_id="test-uuid"',
            {
                "token": "test-token",
                "channel_name": None,
                "url": "https://details.test",
                "analysis_to_post": "summary",
                "only_if": {"analysis_type": "customer_frustration", "includes": "NEEDS REVIEW"},
                "default_channel_name": "default-alerts",
            },
            attrs={"link.name": "post_analysis_to_slack", "vcon.uuid": "test-uuid"},
        ),
    ]
    assert vcon.analysis[0]["was_posted_to_slack"] is True
    mock_instance.store_vcon.assert_called_once_with(vcon)


@patch("links.post_analysis_to_slack.post_blocks_to_channel")
@patch("links.post_analysis_to_slack.VconRedis")
def test_run_skips_already_posted_analyses(mock_vcon_redis, mock_post_blocks):
    vcon = _build_vcon()
    vcon.analysis[0]["was_posted_to_slack"] = True
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    result = run(
        "test-uuid",
        "post_analysis_to_slack",
        opts={
            "token": "test-token",
            "default_channel_name": "default-alerts",
            "url": "https://details.test",
        },
    )

    assert result == "test-uuid"
    mock_post_blocks.assert_not_called()
    mock_instance.store_vcon.assert_called_once_with(vcon)
