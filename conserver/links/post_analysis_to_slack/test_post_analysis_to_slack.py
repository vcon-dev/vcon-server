from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from links.post_analysis_to_slack import (
    build_details_url,
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


def test_helper_functions_resolve_spec_current_purpose_key():
    # draft-ietf-vcon-vcon-core-02 renamed attachment ``type`` → ``purpose``.
    # get_team / get_dealer must resolve attachments authored under the new
    # key as well as the legacy one.
    vcon = SimpleNamespace(
        attachments=[
            {
                "purpose": "strolid_dealer",
                "body": {"name": "Dealer Two", "team": {"name": "Beta Honda"}},
            }
        ],
        analysis=[],
    )

    assert get_team(vcon) == "beta"
    assert get_dealer(vcon) == "Dealer Two"


def test_build_details_url_legacy_appends_quoted_query_param():
    # Old config style with no placeholder — keep the legacy Hex-shaped suffix.
    assert (
        build_details_url("https://details.test", "test-uuid")
        == 'https://details.test?_vcon_id="test-uuid"'
    )


def test_build_details_url_hex_placeholder_quotes_uuid():
    # Hex still expects the uuid wrapped in double quotes; the template owns the quoting.
    template = 'https://app.hex.tech/x/app/y/latest?_vcon_id="{vcon_id}"'
    assert (
        build_details_url(template, "abc-123")
        == 'https://app.hex.tech/x/app/y/latest?_vcon_id="abc-123"'
    )


def test_build_details_url_portal_placeholder_embeds_raw_uuid():
    # Portal embeds the uuid directly in the path, no quotes.
    template = "https://portal.strolidcxm.com/app/conversations/{vcon_id}"
    assert (
        build_details_url(template, "abc-123")
        == "https://portal.strolidcxm.com/app/conversations/abc-123"
    )


def test_build_details_url_leaves_unrelated_braces_alone():
    # Unrelated ``{...}`` segments in the template must NOT raise — only
    # ``{vcon_id}`` is substituted.
    template = "https://app.example.com/users/{user_id}/conversations/{vcon_id}"
    assert (
        build_details_url(template, "abc-123")
        == "https://app.example.com/users/{user_id}/conversations/abc-123"
    )


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
