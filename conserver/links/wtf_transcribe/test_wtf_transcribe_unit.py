import base64
from types import SimpleNamespace
from unittest.mock import ANY, Mock, mock_open, patch

import pytest
import requests

from links.wtf_transcribe import (
    add_transcription_to_vcon,
    analysis_dialog_index,
    analysis_is_wtf_transcription,
    dialog_filename,
    dialog_mimetype,
    dialog_to_audio_binary,
    dialog_to_binary,
    dialog_to_index,
    is_dialog_already_transcribed,
    is_dialog_index_already_transcribed,
    is_dialog_recording,
    is_file_url,
    maybe_load_file_url,
    maybe_load_remote_url,
    run,
    send_audio_to_vfun,
    should_transcribe_dialog,
    transcribe_dialog,
    transcribe_vcon_dialogs,
)


MODULE = run.__module__


class FakeVcon:
    def __init__(self, dialogs, analysis=None):
        self.dialog = dialogs
        self.analysis = list(analysis or [])
        self.add_analysis = Mock()


def test_analysis_and_dialog_helpers_cover_transcribed_and_recording_checks():
    vcon = FakeVcon(
        dialogs=[
            {"type": "recording", "url": "https://example.com/audio.wav"},
            {"type": "recording", "body": base64.b64encode(b"hello").decode("ascii")},
            {"type": "text", "body": "not audio"},
        ],
        analysis=[{"type": "wtf_transcription", "dialog": 0}],
    )

    assert analysis_is_wtf_transcription(vcon.analysis[0]) is True
    assert analysis_dialog_index(vcon.analysis[0]) == 0
    assert is_dialog_recording(vcon.dialog[0]) is True
    assert is_dialog_recording(vcon.dialog[2]) is False
    assert dialog_to_index(vcon, vcon.dialog[1]) == 1
    assert is_dialog_index_already_transcribed(vcon, 0) is True
    assert is_dialog_already_transcribed(vcon, vcon.dialog[0]) is True
    assert should_transcribe_dialog(vcon, vcon.dialog[0]) is False
    assert should_transcribe_dialog(vcon, vcon.dialog[1]) is True
    assert should_transcribe_dialog(vcon, vcon.dialog[2]) is False


def test_file_and_remote_loaders_handle_success_and_failure():
    assert is_file_url("file:///tmp/audio.wav") is True
    assert dialog_filename({}, 3) == "audio_3.wav"
    assert dialog_mimetype({}) == "audio/wav"

    with patch("builtins.open", mock_open(read_data=b"file-bytes")):
        assert maybe_load_file_url("file:///tmp/audio.wav") == b"file-bytes"

    with patch("builtins.open", side_effect=OSError("missing")):
        assert maybe_load_file_url("file:///tmp/audio.wav") is None

    response = Mock(content=b"remote-bytes")
    with patch(f"{MODULE}.requests.get", return_value=response) as mock_get:
        assert maybe_load_remote_url("https://example.com/audio.wav", timeout=42) == b"remote-bytes"
        mock_get.assert_called_once_with("https://example.com/audio.wav", timeout=42)

    with patch(f"{MODULE}.requests.get", side_effect=RuntimeError("boom")):
        assert maybe_load_remote_url("https://example.com/audio.wav", timeout=42) is None


def test_dialog_to_binary_handles_url_base64url_base64_and_invalid_inputs():
    with patch(f"{MODULE}.maybe_load_file_url", return_value=b"file-audio") as mock_file_loader:
        assert dialog_to_binary({"url": "file:///tmp/audio.wav"}, url_timeout=11) == b"file-audio"
        mock_file_loader.assert_called_once_with("file:///tmp/audio.wav")

    with patch(f"{MODULE}.maybe_load_remote_url", return_value=b"remote-audio") as mock_remote_loader:
        assert dialog_to_audio_binary({"url": "https://example.com/audio.wav"}, 13) == b"remote-audio"
        mock_remote_loader.assert_called_once_with("https://example.com/audio.wav", 13)

    base64url_body = base64.urlsafe_b64encode(b"url-safe").decode("ascii")
    assert dialog_to_binary({"encoding": "base64url", "body": base64url_body}) == b"url-safe"

    base64_body = base64.b64encode(b"plain").decode("ascii")
    assert dialog_to_binary({"body": base64_body}) == b"plain"

    with pytest.raises(TypeError, match="unrecognized type"):
        dialog_to_binary({})


def test_send_audio_to_vfun_builds_request_and_decodes_double_encoded_json():
    response = Mock()
    response.json.return_value = '{"transcript": {"text": "hello"}}'

    with patch(f"{MODULE}.requests.post", return_value=response) as mock_post:
        result = send_audio_to_vfun(
            audio_binary=b"audio",
            dialog={"filename": "clip.mp3", "mimetype": "audio/mp3"},
            dialog_index=2,
            vfun_server_url="https://vfun.example/wtf",
            api_key="secret",
            diarize=True,
            language="en",
            vfun_timeout=90,
        )

    assert result == {"transcript": {"text": "hello"}}
    mock_post.assert_called_once_with(
        "https://vfun.example/wtf",
        files={"file-binary": ("clip.mp3", b"audio", "audio/mp3")},
        data={"diarize": "true", "language": "en"},
        headers={"Authorization": "Bearer secret"},
        timeout=90,
    )


def test_add_transcription_to_vcon_uses_expected_shape():
    vcon = FakeVcon(dialogs=[])

    add_transcription_to_vcon(vcon, 1, {"transcript": {"text": "hello"}}, "es")

    vcon.add_analysis.assert_called_once_with(
        type="wtf_transcription",
        dialog=1,
        vendor="vfun",
        body={"transcript": {"text": "hello", "language": "es"}},
        extra={"mediatype": "application/json", "schema": "wtf-1.0"},
    )


def test_transcribe_dialog_handles_success_missing_audio_timeout_and_errors():
    vcon = FakeVcon(dialogs=[])

    with patch(f"{MODULE}.dialog_to_audio_binary", return_value=b"audio"), patch(
        f"{MODULE}.send_audio_to_vfun", return_value={"transcript": {"text": "hello"}}
    ) as mock_send, patch(f"{MODULE}.add_transcription_to_vcon") as mock_add:
        assert transcribe_dialog(vcon, {"body": "x"}, 0, "https://vfun", "key", False, "en", 30, 5) is True
        mock_send.assert_called_once()
        mock_add.assert_called_once_with(vcon, 0, {"transcript": {"text": "hello"}}, "en")

    with patch(f"{MODULE}.dialog_to_audio_binary", return_value=None):
        assert transcribe_dialog(vcon, {"body": "x"}, 0, "https://vfun", "key", False, "en", 30, 5) is False

    with patch(f"{MODULE}.dialog_to_audio_binary", return_value=b"audio"), patch(
        f"{MODULE}.send_audio_to_vfun", side_effect=requests.exceptions.Timeout()
    ):
        assert transcribe_dialog(vcon, {"body": "x"}, 0, "https://vfun", "key", False, "en", 30, 5) is False

    with patch(f"{MODULE}.dialog_to_audio_binary", return_value=b"audio"), patch(
        f"{MODULE}.send_audio_to_vfun", side_effect=RuntimeError("bad response")
    ):
        assert transcribe_dialog(vcon, {"body": "x"}, 0, "https://vfun", "key", False, "en", 30, 5) is False


def test_transcribe_vcon_dialogs_only_processes_eligible_dialogs():
    dialogs = [
        {"type": "recording", "url": "https://example.com/first.wav"},
        {"type": "recording", "url": "https://example.com/second.wav"},
        {"type": "text", "body": "ignore"},
    ]
    vcon = FakeVcon(dialogs=dialogs, analysis=[{"type": "wtf_transcription", "dialog": 1}])

    with patch(f"{MODULE}.transcribe_dialog") as mock_transcribe:
        transcribe_vcon_dialogs(vcon, "https://vfun", "key", True, "en", 30, 5)

    mock_transcribe.assert_called_once_with(vcon, dialogs[0], 0, "https://vfun", "key", True, "en", 30, 5)


@patch(f"{MODULE}.save_vcon")
@patch(f"{MODULE}.transcribe_vcon_dialogs")
@patch(f"{MODULE}.uuid_to_vcon")
@patch(f"{MODULE}.init_redis")
def test_run_happy_path_installs_defaults_and_saves(
    mock_init_redis,
    mock_uuid_to_vcon,
    mock_transcribe_vcon_dialogs,
    mock_save_vcon,
):
    redis = Mock()
    vcon = FakeVcon(dialogs=[])
    mock_init_redis.return_value = redis
    mock_uuid_to_vcon.return_value = vcon
    opts = {"vfun-server-url": "https://vfun.example/wtf"}

    result = run("vc-1", "wtf_transcribe", opts=opts)

    assert result == "vc-1"
    assert opts == {
        "vfun-server-url": "https://vfun.example/wtf",
        "language": None,
        "diarize": False,
        "vfun-timeout": 300,
        "url-timeout": 60,
        "api-key": None,
    }
    mock_transcribe_vcon_dialogs.assert_called_once_with(
        vcon,
        vfun_server_url="https://vfun.example/wtf",
        api_key=None,
        diarize=False,
        language=None,
        vfun_timeout=300,
        url_timeout=60,
    )
    mock_save_vcon.assert_called_once_with(vcon, redis)
