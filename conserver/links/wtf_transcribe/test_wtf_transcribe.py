from unittest.mock import MagicMock, patch

from links.wtf_transcribe import (
    build_vfun_data,
    build_vfun_headers,
    create_wtf_analysis,
    maybe_decode_double_encoded_json,
    run,
)


def test_build_vfun_headers_includes_optional_api_key():
    assert build_vfun_headers("secret") == {"Authorization": "Bearer secret"}
    assert build_vfun_headers(None) == {}


def test_build_vfun_data_serializes_options():
    assert build_vfun_data(True, "en") == {"diarize": "true", "language": "en"}
    assert build_vfun_data(False, None) == {"diarize": "false"}


def test_maybe_decode_double_encoded_json_handles_strings_and_dicts():
    assert maybe_decode_double_encoded_json('{"status": "ok"}') == {"status": "ok"}
    assert maybe_decode_double_encoded_json({"status": "ok"}) == {"status": "ok"}


def test_create_wtf_analysis_adds_language_to_transcript():
    analysis = create_wtf_analysis(
        dialog_index=1,
        vfun_response={"transcript": {"text": "hello"}},
        language="es",
    )

    assert analysis["type"] == "wtf_transcription"
    assert analysis["dialog"] == 1
    assert analysis["body"]["transcript"]["language"] == "es"


@patch("links.wtf_transcribe.init_redis")
def test_run_returns_none_when_vfun_server_url_is_missing(mock_init_redis):
    result = run("test-uuid", "wtf_transcribe", opts={})

    assert result is None
    mock_init_redis.assert_called_once()


@patch("links.wtf_transcribe.uuid_to_vcon", return_value=None)
@patch("links.wtf_transcribe.init_redis")
def test_run_returns_none_when_vcon_is_missing(mock_init_redis, mock_uuid_to_vcon):
    mock_init_redis.return_value = MagicMock()

    result = run(
        "test-uuid",
        "wtf_transcribe",
        opts={"vfun-server-url": "https://vfun.test/wtf"},
    )

    assert result is None
