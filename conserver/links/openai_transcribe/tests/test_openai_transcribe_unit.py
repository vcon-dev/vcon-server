from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, Mock, call, mock_open, patch

import pytest

from .. import (
    combine_transcription_results,
    find_silence_split_points,
    get_audio_duration,
    get_transcription,
    run,
    split_audio_file,
    transcribe_openai,
)


MODULE = run.__module__
RAW_TRANSCRIBE = getattr(transcribe_openai, "__wrapped__", transcribe_openai)


class FakeChunk:
    def __init__(self, exports, start, stop):
        self.exports = exports
        self.start = start
        self.stop = stop

    def export(self, path, format, bitrate, parameters):
        self.exports.append(
            {
                "path": path,
                "format": format,
                "bitrate": bitrate,
                "parameters": parameters,
                "start": self.start,
                "stop": self.stop,
            }
        )


class FakeAudio:
    def __init__(self, total_ms):
        self.total_ms = total_ms
        self.exports = []

    def __len__(self):
        return self.total_ms

    def __getitem__(self, key):
        start = 0 if key.start is None else key.start
        stop = self.total_ms if key.stop is None else key.stop
        return FakeChunk(self.exports, start, stop)


class FakeVcon:
    def __init__(self, dialogs, analysis=None):
        self.uuid = "vc-1"
        self.dialog = dialogs
        self.analysis = list(analysis or [])
        self.added_analysis = []

    def add_analysis(self, **kwargs):
        self.added_analysis.append(kwargs)
        self.analysis.append(
            {
                "dialog": kwargs["dialog"],
                "type": kwargs["type"],
                "body": kwargs["body"],
            }
        )


def make_tempfile(path):
    temp_file = MagicMock()
    temp_file.name = path
    context_manager = MagicMock()
    context_manager.__enter__.return_value = temp_file
    context_manager.__exit__.return_value = False
    return context_manager, temp_file


def make_transcription_response(payload):
    response = Mock()
    response.dict.return_value = payload
    return response


def test_get_transcription_returns_existing_transcript():
    transcript = {"dialog": 2, "type": "transcript", "body": {"text": "hello"}}
    vcon = SimpleNamespace(analysis=[{"dialog": 2, "type": "summary"}, transcript])

    assert get_transcription(vcon, 2) == transcript
    assert get_transcription(vcon, 1) is None


def test_get_audio_duration_success():
    with patch(f"{MODULE}.ffmpeg", new=SimpleNamespace(probe=Mock(return_value={"streams": [{"duration": "12.5"}]}))):
        assert get_audio_duration("/tmp/audio.wav") == 12.5


def test_get_audio_duration_reraises_probe_error():
    with patch(f"{MODULE}.ffmpeg", new=SimpleNamespace(probe=Mock(side_effect=RuntimeError("bad probe")))):
        with pytest.raises(RuntimeError, match="bad probe"):
            get_audio_duration("/tmp/audio.wav")


def test_find_silence_split_points_prefers_silence_and_falls_back_to_target():
    fake_audio = FakeAudio(25_000)

    with patch(f"{MODULE}.AudioSegment.from_file", return_value=fake_audio), patch(
        f"{MODULE}.detect_nonsilent",
        return_value=[[2_000, 8_000], [10_000, 14_000], [18_000, 23_000]],
    ):
        result = find_silence_split_points("/tmp/audio.wav", max_duration=10)

    assert result == [9000.0, 20000]


def test_find_silence_split_points_returns_empty_for_short_audio_and_errors():
    with patch(f"{MODULE}.AudioSegment.from_file", return_value=FakeAudio(4_000)):
        assert find_silence_split_points("/tmp/audio.wav", max_duration=10) == []

    with patch(f"{MODULE}.AudioSegment.from_file", return_value=FakeAudio(12_000)), patch(
        f"{MODULE}.detect_nonsilent", return_value=[]
    ):
        assert find_silence_split_points("/tmp/audio.wav", max_duration=10) == []

    with patch(f"{MODULE}.AudioSegment.from_file", side_effect=RuntimeError("load failed")):
        assert find_silence_split_points("/tmp/audio.wav", max_duration=10) == []


def test_split_audio_file_returns_original_when_audio_is_under_limit():
    with patch(f"{MODULE}.get_audio_duration", return_value=4):
        assert split_audio_file("/tmp/audio.wav", max_duration=10) == ["/tmp/audio.wav"]


def test_split_audio_file_uses_time_based_chunking_when_silence_is_disabled():
    fake_audio = FakeAudio(12_000)

    with patch(f"{MODULE}.get_audio_duration", return_value=12), patch(
        f"{MODULE}.tempfile.mkdtemp", return_value="/tmp/chunks"
    ), patch(f"{MODULE}.AudioSegment.from_file", return_value=fake_audio):
        result = split_audio_file(
            "/tmp/audio.wav",
            max_duration=5,
            opts={"use_silence_chunking": False},
        )

    assert result == [
        "/tmp/chunks/audio_chunk_000.mp3",
        "/tmp/chunks/audio_chunk_001.mp3",
        "/tmp/chunks/audio_chunk_002.mp3",
    ]
    assert [export["start"] for export in fake_audio.exports] == [0, 5000, 10000]
    assert [export["stop"] for export in fake_audio.exports] == [5000, 10000, 12000]


def test_split_audio_file_uses_detected_silence_split_points():
    fake_audio = FakeAudio(8_000)

    with patch(f"{MODULE}.get_audio_duration", return_value=8), patch(
        f"{MODULE}.find_silence_split_points", return_value=[3500]
    ), patch(f"{MODULE}.tempfile.mkdtemp", return_value="/tmp/chunks"), patch(
        f"{MODULE}.AudioSegment.from_file", return_value=fake_audio
    ):
        result = split_audio_file("/tmp/audio.wav", max_duration=5, opts={"use_silence_chunking": True})

    assert result == ["/tmp/chunks/audio_chunk_000.mp3", "/tmp/chunks/audio_chunk_001.mp3"]
    assert [export["start"] for export in fake_audio.exports] == [0, 3500]
    assert [export["stop"] for export in fake_audio.exports] == [3500, 8000]


def test_combine_transcription_results_merges_text_usage_and_chunk_metadata():
    result = combine_transcription_results(
        [
            {"text": "hello", "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}},
            {"text": "world", "usage": {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7}},
        ]
    )

    assert combine_transcription_results([]) == {}
    assert combine_transcription_results([{"text": "solo"}]) == {"text": "solo"}
    assert result["text"] == "hello world"
    assert result["usage"]["input_tokens"] == 7
    assert result["usage"]["output_tokens"] == 3
    assert result["usage"]["total_tokens"] == 10
    assert result["chunked_transcription"]["total_chunks"] == 2


def test_transcribe_openai_uses_header_filename_and_tracks_usage():
    client = Mock()
    client.audio.transcriptions.create.return_value = make_transcription_response(
        {"text": "hello", "usage": {"input_tokens": 11, "output_tokens": 4}}
    )
    response = Mock(
        headers={"content-disposition": 'attachment; filename="track.mp4"'},
        content=b"audio-bytes",
    )
    temp_context, temp_file = make_tempfile("/tmp/original.mp4")

    with patch(f"{MODULE}.get_openai_client", return_value=client), patch(
        f"{MODULE}.requests.get", return_value=response
    ), patch(f"{MODULE}.tempfile.NamedTemporaryFile", return_value=temp_context), patch(
        f"{MODULE}.split_audio_file", return_value=["/tmp/chunk_1.mp3"]
    ), patch("builtins.open", mock_open(read_data=b"chunk")), patch(
        f"{MODULE}.os.unlink"
    ) as mock_unlink, patch(f"{MODULE}.send_ai_usage_data_for_tracking") as mock_usage:
        result = RAW_TRANSCRIBE(
            "https://example.com/audio",
            opts={
                "model": "gpt-4o-transcribe",
                "send_ai_usage_data_to_url": "https://usage.example",
                "ai_usage_api_token": "token",
            },
            vcon_uuid="vc-1",
        )

    assert result["text"] == "hello"
    temp_file.write.assert_called_once_with(b"audio-bytes")
    client.audio.transcriptions.create.assert_called_once()
    mock_usage.assert_called_once_with(
        vcon_uuid="vc-1",
        input_units=11,
        output_units=4,
        unit_type="tokens",
        type="VCON_PROCESSING",
        send_ai_usage_data_to_url="https://usage.example",
        ai_usage_api_token="token",
        model="gpt-4o-transcribe",
        sub_type="OPENAI_TRANSCRIBE",
    )
    mock_unlink.assert_has_calls([call("/tmp/original.mp4")])


def test_transcribe_openai_falls_back_to_url_filename_and_combines_chunk_results():
    client = Mock()
    client.audio.transcriptions.create.side_effect = [
        make_transcription_response(
            {"text": "hello", "usage": {"input_tokens": 3, "output_tokens": 1, "total_tokens": 4}}
        ),
        make_transcription_response(
            {"text": "world", "usage": {"input_tokens": 4, "output_tokens": 2, "total_tokens": 6}}
        ),
    ]
    response = Mock(headers={}, content=b"audio-bytes")
    temp_context, _temp_file = make_tempfile("/tmp/original.wav")

    with patch(f"{MODULE}.get_openai_client", return_value=client), patch(
        f"{MODULE}.requests.get", return_value=response
    ), patch(f"{MODULE}.tempfile.NamedTemporaryFile", return_value=temp_context) as mock_tempfile, patch(
        f"{MODULE}.split_audio_file", return_value=["/tmp/chunks/a.mp3", "/tmp/chunks/b.mp3"]
    ), patch("builtins.open", mock_open(read_data=b"chunk")), patch(
        f"{MODULE}.os.unlink"
    ) as mock_unlink, patch(f"{MODULE}.os.rmdir") as mock_rmdir, patch(
        f"{MODULE}.send_ai_usage_data_for_tracking"
    ) as mock_usage:
        result = RAW_TRANSCRIBE("https://example.com/call%20one.wav", opts={"model": "gpt-4o-transcribe"})

    assert result["text"] == "hello world"
    assert result["chunked_transcription"]["total_chunks"] == 2
    mock_tempfile.assert_called_once_with(delete=False, suffix=".wav")
    mock_unlink.assert_has_calls(
        [call("/tmp/original.wav"), call("/tmp/chunks/a.mp3"), call("/tmp/chunks/b.mp3")]
    )
    mock_rmdir.assert_called_once_with("/tmp/chunks")
    mock_usage.assert_not_called()


def test_transcribe_openai_reraises_failures():
    with patch(f"{MODULE}.get_openai_client", return_value=Mock()), patch(
        f"{MODULE}.requests.get", side_effect=RuntimeError("download failed")
    ):
        with pytest.raises(RuntimeError, match="download failed"):
            RAW_TRANSCRIBE("https://example.com/audio")


def test_run_skips_irrelevant_dialogs_and_redacts_sensitive_opts():
    fake_vcon = FakeVcon(
        dialogs=[
            {"type": "text"},
            {"type": "recording", "duration": 10},
            {"type": "recording", "duration": 1, "url": "https://example.com/short.mp3"},
            {"type": "recording", "duration": 10, "url": "https://example.com/existing.mp3"},
            {"type": "recording", "url": "https://example.com/no-duration.mp3"},
            {"type": "recording", "duration": 10, "url": "https://example.com/new.mp3"},
        ],
        analysis=[{"dialog": 3, "type": "transcript", "body": {"text": "done"}}],
    )
    redis_client = Mock(get_vcon=Mock(return_value=fake_vcon), store_vcon=Mock())

    with patch(f"{MODULE}.VconRedis", return_value=redis_client), patch(
        f"{MODULE}.transcribe_openai",
        side_effect=[
            {"text": "missing duration result", "usage": {"input_tokens": 1, "output_tokens": 1}},
            {"text": "new result", "usage": {"input_tokens": 2, "output_tokens": 1}},
        ],
    ) as mock_transcribe, patch(f"{MODULE}.record_histogram") as mock_histogram:
        result = run(
            "vc-1",
            "openai-link",
            opts={
                "minimum_duration": 3,
                "model": "gpt-4o-transcribe",
                "OPENAI_API_KEY": "secret",
                "ai_usage_api_token": "usage-secret",
                "send_ai_usage_data_to_url": "https://usage.example",
            },
        )

    assert result == "vc-1"
    assert mock_transcribe.call_args_list == [
        call("https://example.com/no-duration.mp3", ANY, "vc-1"),
        call("https://example.com/new.mp3", ANY, "vc-1"),
    ]
    assert mock_histogram.call_count == 2
    assert len(fake_vcon.added_analysis) == 2
    redacted_opts = fake_vcon.added_analysis[0]["extra"]["vendor_schema"]["opts"]
    assert redacted_opts["model"] == "gpt-4o-transcribe"
    assert redacted_opts["minimum_duration"] == 3
    assert redacted_opts["use_silence_chunking"] is True
    assert "OPENAI_API_KEY" not in redacted_opts
    assert "AZURE_OPENAI_API_KEY" not in redacted_opts
    assert "ai_usage_api_token" not in redacted_opts
    assert "send_ai_usage_data_to_url" not in redacted_opts
    redis_client.store_vcon.assert_called_once_with(fake_vcon)


def test_run_increments_counter_and_breaks_when_no_transcription_is_generated():
    fake_vcon = FakeVcon(dialogs=[{"type": "recording", "duration": 10, "url": "https://example.com/audio.mp3"}])
    redis_client = Mock(get_vcon=Mock(return_value=fake_vcon), store_vcon=Mock())

    with patch(f"{MODULE}.VconRedis", return_value=redis_client), patch(
        f"{MODULE}.transcribe_openai", return_value=None
    ) as mock_transcribe, patch(f"{MODULE}.increment_counter") as mock_counter:
        result = run("vc-1", "openai-link")

    assert result == "vc-1"
    mock_transcribe.assert_called_once()
    mock_counter.assert_called_once_with(
        "conserver.link.openai.transcription_failures",
        attributes={"link.name": "openai-link", "vcon.uuid": "vc-1"},
    )
    assert fake_vcon.added_analysis == []
    redis_client.store_vcon.assert_called_once_with(fake_vcon)


def test_run_increments_counter_and_reraises_transcription_errors():
    fake_vcon = FakeVcon(dialogs=[{"type": "recording", "duration": 10, "url": "https://example.com/audio.mp3"}])
    redis_client = Mock(get_vcon=Mock(return_value=fake_vcon), store_vcon=Mock())

    with patch(f"{MODULE}.VconRedis", return_value=redis_client), patch(
        f"{MODULE}.transcribe_openai", side_effect=RuntimeError("boom")
    ), patch(f"{MODULE}.increment_counter") as mock_counter:
        with pytest.raises(RuntimeError, match="boom"):
            run("vc-1", "openai-link")

    mock_counter.assert_called_once_with(
        "conserver.link.openai.transcription_failures",
        attributes={"link.name": "openai-link", "vcon.uuid": "vc-1"},
    )
    redis_client.store_vcon.assert_not_called()
