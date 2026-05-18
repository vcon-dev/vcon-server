import io
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, mock_open, patch

from links import deepgram_link


RAW_LITELLM = getattr(deepgram_link.transcribe_via_litellm, "__wrapped__", deepgram_link.transcribe_via_litellm)
RAW_TRANSCRIBE_DG = getattr(deepgram_link.transcribe_dg, "__wrapped__", deepgram_link.transcribe_dg)


def make_tempfile(path):
    temp_file = MagicMock()
    temp_file.name = path
    context_manager = MagicMock()
    context_manager.__enter__.return_value = temp_file
    context_manager.__exit__.return_value = False
    return context_manager


def build_wav_bytes(duration_seconds=1, rate=8000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(b"\x00\x00" * rate * duration_seconds)
    return buf.getvalue()


def test_get_transcription_returns_existing_entry():
    vcon = SimpleNamespace(analysis=[{"dialog": 1, "type": "summary"}, {"dialog": 0, "type": "transcript"}])

    assert deepgram_link.get_transcription(vcon, 0) == {"dialog": 0, "type": "transcript"}
    assert deepgram_link.get_transcription(vcon, 2) is None


def test_transcribe_via_litellm_returns_none_without_proxy_config():
    assert RAW_LITELLM("https://example.com/audio.mp3", {"model": "nova-3"}) is None


def test_transcribe_via_litellm_handles_empty_audio_download():
    response = Mock()
    response.iter_content.return_value = [b""]
    temp_context = make_tempfile("/tmp/audio.mp3")

    with patch("links.deepgram_link.requests.get", return_value=response), patch(
        "links.deepgram_link.tempfile.NamedTemporaryFile", return_value=temp_context
    ), patch("links.deepgram_link.os.unlink") as mock_unlink:
        result = RAW_LITELLM(
            "https://example.com/audio.mp3",
            {"LITELLM_PROXY_URL": "https://proxy", "LITELLM_MASTER_KEY": "secret"},
        )

    assert result is None
    mock_unlink.assert_called_once_with("/tmp/audio.mp3")


def test_transcribe_via_litellm_returns_transcript_and_cleans_up_tempfile():
    response = Mock()
    response.iter_content.return_value = [b"abc", b"def"]
    temp_context = make_tempfile("/tmp/audio.mp3")
    client = Mock()
    api_response = Mock(text="hello world")
    client.audio.transcriptions.create.return_value = api_response

    with patch("links.deepgram_link.requests.get", return_value=response), patch(
        "links.deepgram_link.tempfile.NamedTemporaryFile", return_value=temp_context
    ), patch("links.deepgram_link.get_openai_client", return_value=client), patch(
        "builtins.open", mock_open(read_data=b"abcdef")
    ), patch("links.deepgram_link.os.unlink") as mock_unlink:
        result = RAW_LITELLM(
            "https://example.com/audio.mp3?sig=1",
            {
                "LITELLM_PROXY_URL": "https://proxy",
                "LITELLM_MASTER_KEY": "secret",
                "model": "nova-3",
            },
        )

    assert result == {"transcript": "hello world"}
    client.audio.transcriptions.create.assert_called_once()
    mock_unlink.assert_called_once_with("/tmp/audio.mp3")


def test_transcribe_dg_extracts_transcript_language_and_tracks_usage():
    dg_client = Mock()
    dg_client.listen.rest.v.return_value.transcribe_url.return_value.to_json.return_value = (
        '{"metadata":{"duration":12.3},"results":{"channels":[{"detected_language":"es","alternatives":[{"transcript":"hola","confidence":0.91}]}]}}'
    )

    with patch("links.deepgram_link.send_ai_usage_data_for_tracking") as mock_usage:
        result = RAW_TRANSCRIBE_DG(
            dg_client,
            {"url": "https://example.com/audio.mp3"},
            {"model": "nova-3"},
            vcon_uuid="vc-1",
            run_opts={"send_ai_usage_data_to_url": "https://usage.example", "ai_usage_api_token": "token"},
        )

    assert result["transcript"] == "hola"
    assert result["confidence"] == 0.91
    assert result["detected_language"] == "es"
    mock_usage.assert_called_once_with(
        vcon_uuid="vc-1",
        input_units=12,
        output_units=0,
        unit_type="seconds",
        type="VCON_PROCESSING",
        send_ai_usage_data_to_url="https://usage.example",
        ai_usage_api_token="token",
        model="nova-3",
        sub_type="DEEPGRAM_TRANSCRIBE",
    )


def test_get_wav_duration_from_url_reads_valid_wav_and_handles_failures():
    response = Mock(content=build_wav_bytes(duration_seconds=2))
    with patch("links.deepgram_link.requests.get", return_value=response):
        assert deepgram_link.get_wav_duration_from_url("https://example.com/audio.wav") == 2

    with patch("links.deepgram_link.requests.get", side_effect=RuntimeError("boom")):
        assert deepgram_link.get_wav_duration_from_url("https://example.com/audio.wav") is None
