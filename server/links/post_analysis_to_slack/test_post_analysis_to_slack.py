import pytest
from unittest.mock import patch, MagicMock, call
from vcon import Vcon

from links.post_analysis_to_slack import run, get_team, get_dealer, get_summary, post_blocks_to_channel


# ============================================================================
# Shared fixtures
# ============================================================================

@pytest.fixture
def mock_vcon_redis():
    with patch("links.post_analysis_to_slack.VconRedis") as mock:
        yield mock


@pytest.fixture
def mock_web_client():
    with patch("links.post_analysis_to_slack.WebClient") as mock:
        yield mock


BASE_OPTS = {
    "token": "xoxb-test-token",
    "default_channel_name": "alerts",
    "url": "https://example.com/hex",
    "analysis_to_post": "summary",
    "only_if": {"analysis_type": "customer_frustration", "includes": "NEEDS REVIEW"},
}


def _make_vcon(*, uuid="test-uuid", analysis=None, attachments=None):
    return Vcon({
        "uuid": uuid,
        "vcon": "0.0.1",
        "meta": {"arc_display_name": "Test vCon"},
        "parties": [],
        "dialog": [],
        "analysis": analysis or [],
        "attachments": attachments or [],
        "redacted": {},
    })


def _frustration_analysis(dialog=0, body="NEEDS REVIEW - urgent", was_posted=False):
    a = {
        "type": "customer_frustration",
        "dialog": dialog,
        "body": body,
    }
    if was_posted:
        a["was_posted_to_slack"] = True
    return a


def _summary_analysis(dialog=0, body="Call summary text"):
    return {
        "type": "summary",
        "dialog": dialog,
        "body": body,
    }


def _dealer_attachment(dealer_name="Test Motors", team_name=None):
    body = {"name": dealer_name}
    if team_name:
        body["team"] = {"name": team_name}
    return {"type": "strolid_dealer", "body": body}


# ============================================================================
# Helper function unit tests
# ============================================================================

class TestGetTeam:
    def test_returns_first_word_lowercased(self):
        vcon = _make_vcon(attachments=[_dealer_attachment(team_name="Strolid CXM")])
        assert get_team(vcon) == "strolid"

    def test_returns_none_when_no_dealer_attachment(self):
        vcon = _make_vcon()
        assert get_team(vcon) is None

    def test_returns_none_when_dealer_has_no_team(self):
        vcon = _make_vcon(attachments=[_dealer_attachment()])
        assert get_team(vcon) is None

    def test_returns_none_when_team_name_is_empty(self):
        vcon = _make_vcon(attachments=[
            {"type": "strolid_dealer", "body": {"name": "Test Motors", "team": {"name": ""}}}
        ])
        assert get_team(vcon) is None


class TestGetDealer:
    def test_returns_dealer_name(self):
        vcon = _make_vcon(attachments=[_dealer_attachment(dealer_name="Example Auto")])
        assert get_dealer(vcon) == "Example Auto"

    def test_returns_none_when_no_dealer_attachment(self):
        vcon = _make_vcon()
        assert get_dealer(vcon) is None

    def test_returns_none_when_name_key_missing(self):
        vcon = _make_vcon(attachments=[{"type": "strolid_dealer", "body": {}}])
        assert get_dealer(vcon) is None


class TestGetSummary:
    def test_returns_matching_summary(self):
        analysis = [_frustration_analysis(dialog=0), _summary_analysis(dialog=0, body="The summary")]
        vcon = _make_vcon(analysis=analysis)
        result = get_summary(vcon, 0)
        assert result["body"] == "The summary"

    def test_returns_none_when_no_summary_for_dialog(self):
        vcon = _make_vcon(analysis=[_summary_analysis(dialog=1)])
        assert get_summary(vcon, 0) is None

    def test_returns_correct_summary_when_multiple_dialogs(self):
        analysis = [
            _summary_analysis(dialog=0, body="Dialog 0 summary"),
            _summary_analysis(dialog=1, body="Dialog 1 summary"),
        ]
        vcon = _make_vcon(analysis=analysis)
        assert get_summary(vcon, 1)["body"] == "Dialog 1 summary"


# ============================================================================
# post_blocks_to_channel unit tests
# ============================================================================

class TestPostBlocksToChannel:
    def test_includes_header_by_default(self, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        post_blocks_to_channel("token", "channel", "abstract text", "https://url", {})

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        blocks = kwargs["blocks"]
        assert any(
            b.get("text", {}).get("text", "").startswith("Check this out")
            for b in blocks
        )

    def test_omits_header_when_include_header_false(self, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        post_blocks_to_channel("token", "channel", "abstract text", "https://url", {}, include_header=False)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        blocks = kwargs["blocks"]
        assert not any(
            b.get("text", {}).get("text", "").startswith("Check this out")
            for b in blocks
        )

    def test_message_contains_abstract_and_url(self, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        post_blocks_to_channel("token", "channel", "my abstract", "https://details-url", {})

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        blocks = kwargs["blocks"]
        block_texts = str(blocks)
        assert "my abstract" in block_texts
        assert "https://details-url" in block_texts

    def test_error_fallback_posts_to_default_channel_and_reraises(self, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        original_error = Exception("channel not found")
        mock_client_instance.chat_postMessage.side_effect = [original_error, None]

        opts = {"default_channel_name": "alerts"}

        with pytest.raises(Exception, match="channel not found"):
            post_blocks_to_channel("token", "bad-channel", "abstract", "https://url", opts)

        assert mock_client_instance.chat_postMessage.call_count == 2
        fallback_call = mock_client_instance.chat_postMessage.call_args_list[1]
        assert fallback_call.kwargs["channel"] == "alerts"
        assert "bad-channel" in fallback_call.kwargs["text"]


# ============================================================================
# run() — simple notification mode
# ============================================================================

class TestRunSimpleNotificationMode:
    def _setup(self, mock_vcon_redis, vcon_id="test-uuid"):
        mock_instance = MagicMock()
        mock_instance.get_vcon.return_value = _make_vcon(uuid=vcon_id)
        mock_vcon_redis.return_value = mock_instance

    def test_returns_vcon_id(self, mock_vcon_redis, mock_web_client):
        self._setup(mock_vcon_redis)
        opts = {**BASE_OPTS, "url_template": "https://example.com/calls/{vcon_uuid}"}
        assert run("test-uuid", "test-link", opts) == "test-uuid"

    def test_substitutes_vcon_uuid_in_url(self, mock_vcon_redis, mock_web_client):
        self._setup(mock_vcon_redis, vcon_id="abc-123")
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        opts = {**BASE_OPTS, "url_template": "https://example.com/calls/{vcon_uuid}"}
        run("abc-123", "test-link", opts)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        blocks_str = str(kwargs["blocks"])
        assert "https://example.com/calls/abc-123" in blocks_str

    def test_posts_to_default_channel(self, mock_vcon_redis, mock_web_client):
        self._setup(mock_vcon_redis)
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        opts = {**BASE_OPTS, "url_template": "https://example.com/calls/{vcon_uuid}"}
        run("test-uuid", "test-link", opts)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        assert kwargs["channel"] == "alerts"

    def test_posts_exactly_once(self, mock_vcon_redis, mock_web_client):
        self._setup(mock_vcon_redis)
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        opts = {**BASE_OPTS, "url_template": "https://example.com/calls/{vcon_uuid}"}
        run("test-uuid", "test-link", opts)

        assert mock_client_instance.chat_postMessage.call_count == 1

    def test_uses_custom_message_text(self, mock_vcon_redis, mock_web_client):
        self._setup(mock_vcon_redis)
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        opts = {**BASE_OPTS, "url_template": "https://example.com/{vcon_uuid}", "message_text": "New callback!"}
        run("test-uuid", "test-link", opts)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        assert kwargs["text"] == "New callback!"

    def test_falls_back_to_default_message_text(self, mock_vcon_redis, mock_web_client):
        self._setup(mock_vcon_redis)
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        opts = {**BASE_OPTS, "url_template": "https://example.com/{vcon_uuid}"}
        run("test-uuid", "test-link", opts)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        assert kwargs["text"] == "Callback request"

    def test_omits_header_block(self, mock_vcon_redis, mock_web_client):
        self._setup(mock_vcon_redis)
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        opts = {**BASE_OPTS, "url_template": "https://example.com/{vcon_uuid}"}
        run("test-uuid", "test-link", opts)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        blocks = kwargs["blocks"]
        assert not any(
            b.get("text", {}).get("text", "").startswith("Check this out")
            for b in blocks
        )

    def test_does_not_store_vcon(self, mock_vcon_redis, mock_web_client):
        mock_instance = MagicMock()
        mock_instance.get_vcon.return_value = _make_vcon()
        mock_vcon_redis.return_value = mock_instance

        opts = {**BASE_OPTS, "url_template": "https://example.com/{vcon_uuid}"}
        run("test-uuid", "test-link", opts)

        mock_instance.store_vcon.assert_not_called()


# ============================================================================
# run() — analysis mode
# ============================================================================

class TestRunAnalysisMode:
    def _setup(self, mock_vcon_redis, vcon):
        mock_instance = MagicMock()
        mock_instance.get_vcon.return_value = vcon
        mock_vcon_redis.return_value = mock_instance
        return mock_instance

    def test_skips_analysis_with_wrong_type(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[
            {"type": "sentiment", "dialog": 0, "body": "NEEDS REVIEW"},
            _summary_analysis(dialog=0),
        ])
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)
        mock_client_instance.chat_postMessage.assert_not_called()

    def test_skips_analysis_when_includes_text_absent(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[
            _frustration_analysis(body="All good, no issues here"),
            _summary_analysis(dialog=0),
        ])
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)
        mock_client_instance.chat_postMessage.assert_not_called()

    def test_skips_already_posted_analysis(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[
            _frustration_analysis(was_posted=True),
            _summary_analysis(dialog=0),
        ])
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)
        mock_client_instance.chat_postMessage.assert_not_called()

    def test_posts_to_default_channel_when_no_team(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[
            _frustration_analysis(),
            _summary_analysis(body="Call summary"),
        ])
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        assert mock_client_instance.chat_postMessage.call_count == 1
        _, kwargs = mock_client_instance.chat_postMessage.call_args
        assert kwargs["channel"] == "alerts"

    def test_posts_to_team_channel_and_default_channel_when_team_is_not_strolid(
        self, mock_vcon_redis, mock_web_client
    ):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(
            analysis=[_frustration_analysis(), _summary_analysis(body="Summary")],
            attachments=[_dealer_attachment(dealer_name="Acme Auto", team_name="Westside Group")],
        )
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        channels_posted = [
            c.kwargs["channel"]
            for c in mock_client_instance.chat_postMessage.call_args_list
        ]
        assert "team-westside-alerts" in channels_posted
        assert "alerts" in channels_posted
        assert mock_client_instance.chat_postMessage.call_count == 2

    def test_team_channel_message_includes_dealer_name(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(
            analysis=[_frustration_analysis(), _summary_analysis(body="Summary text")],
            attachments=[_dealer_attachment(dealer_name="Acme Auto", team_name="Westside Group")],
        )
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        team_call = mock_client_instance.chat_postMessage.call_args_list[0]
        assert "#Acme Auto" in team_call.kwargs["text"]

    def test_strolid_team_posts_only_to_default_channel(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(
            analysis=[_frustration_analysis(), _summary_analysis(body="Summary")],
            attachments=[_dealer_attachment(team_name="Strolid Internal")],
        )
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        assert mock_client_instance.chat_postMessage.call_count == 1
        _, kwargs = mock_client_instance.chat_postMessage.call_args
        assert kwargs["channel"] == "alerts"

    def test_marks_analysis_as_posted(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[_frustration_analysis(), _summary_analysis()])
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        # Vcon deep-copies its data, so inspect the vcon's internal analysis list
        posted = next(a for a in vcon.analysis if a["type"] == "customer_frustration")
        assert posted.get("was_posted_to_slack") is True

    def test_stores_vcon_after_posting(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[_frustration_analysis(), _summary_analysis()])
        mock_instance = self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        mock_instance.store_vcon.assert_called_once_with(vcon)

    def test_stores_vcon_even_when_no_analysis_matches(self, mock_vcon_redis, mock_web_client):
        vcon = _make_vcon()
        mock_instance = self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        mock_instance.store_vcon.assert_called_once_with(vcon)

    def test_returns_vcon_id(self, mock_vcon_redis, mock_web_client):
        vcon = _make_vcon(analysis=[_frustration_analysis(), _summary_analysis()])
        self._setup(mock_vcon_redis, vcon)
        mock_web_client.return_value = MagicMock()

        assert run("test-uuid", "test-link", BASE_OPTS) == "test-uuid"

    def test_only_posts_unposted_analysis_when_mix_present(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[
            _frustration_analysis(dialog=0, was_posted=True),
            _frustration_analysis(dialog=1),
            _summary_analysis(dialog=0, body="Summary 0"),
            _summary_analysis(dialog=1, body="Summary 1"),
        ])
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        assert mock_client_instance.chat_postMessage.call_count == 1
        _, kwargs = mock_client_instance.chat_postMessage.call_args
        assert kwargs["text"] == "Summary 1"

    def test_includes_header_block_in_analysis_mode(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(analysis=[_frustration_analysis(), _summary_analysis(body="Summary")])
        self._setup(mock_vcon_redis, vcon)

        run("test-uuid", "test-link", BASE_OPTS)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        blocks = kwargs["blocks"]
        assert any(
            b.get("text", {}).get("text", "").startswith("Check this out")
            for b in blocks
        )

    def test_url_contains_vcon_id(self, mock_vcon_redis, mock_web_client):
        mock_client_instance = MagicMock()
        mock_web_client.return_value = mock_client_instance

        vcon = _make_vcon(uuid="my-vcon-id", analysis=[_frustration_analysis(), _summary_analysis()])
        self._setup(mock_vcon_redis, vcon)

        opts = {**BASE_OPTS, "url": "https://example.com/hex"}
        run("my-vcon-id", "test-link", opts)

        _, kwargs = mock_client_instance.chat_postMessage.call_args
        blocks_str = str(kwargs["blocks"])
        assert "my-vcon-id" in blocks_str
