import os
import pytest
from unittest.mock import patch, MagicMock
from server.links.deepgram_link import run
from server.vcon import Vcon

@pytest.fixture
def vcon_with_no_valid_dialog():
    vcon = Vcon.build_new()
    vcon.add_dialog({"type": "text", "body": "Not a recording"})
    vcon.add_dialog({"type": "recording", "url": None, "duration": 120})
    vcon.add_dialog({"type": "recording", "url": "http://audio.url/short.wav", "duration": 10})
    return vcon

@pytest.fixture
def vcon_with_one_valid_dialog():
    vcon = Vcon.build_new()
    vcon.add_dialog({"type": "recording", "url": "http://audio.url/ok.wav", "duration": 120})
    return vcon

@pytest.fixture
def vcon_with_transcript():
    vcon = Vcon.build_new()
    vcon.add_dialog({"type": "recording", "url": "http://audio.url/already.wav", "duration": 120})
    vcon.add_analysis(type="transcript", dialog=0, vendor="deepgram", body={"transcript": "hi", "confidence": 0.99})
    return vcon

@patch('server.links.deepgram_link.DeepgramClient')
@patch('server.links.deepgram_link.transcribe_dg')
def test_run_skips_non_recording_and_short_and_no_url(mock_transcribe, mock_dg, vcon_with_no_valid_dialog):
    with patch('server.links.deepgram_link.VconRedis', autospec=True) as mock:
        instance = MagicMock()
        instance.get_vcon.return_value = vcon_with_no_valid_dialog
        mock.return_value = instance
        mock_transcribe.return_value = {"transcript": "ok", "confidence": 0.99}
        opts = {"DEEPGRAM_KEY": "test", "minimum_duration": 60, "api": {}}
        vcon_uuid = "test-uuid"
        result = run(vcon_uuid, "deepgram", opts)
        # No dialog should be processed
        assert mock_transcribe.call_count == 0
        assert instance.store_vcon.called
        assert result == vcon_uuid

@patch('server.links.deepgram_link.DeepgramClient')
@patch('server.links.deepgram_link.transcribe_dg')
def test_run_skips_already_transcribed(mock_transcribe, mock_dg, vcon_with_transcript):
    with patch('server.links.deepgram_link.VconRedis', autospec=True) as mock:
        instance = MagicMock()
        instance.get_vcon.return_value = vcon_with_transcript
        mock.return_value = instance
        opts = {"DEEPGRAM_KEY": "test", "minimum_duration": 60, "api": {}}
        vcon_uuid = "test-uuid"
        result = run(vcon_uuid, "deepgram", opts)
        assert mock_transcribe.call_count == 0
        assert instance.store_vcon.called
        assert result == vcon_uuid

@patch('server.links.deepgram_link.DeepgramClient')
@patch('server.links.deepgram_link.transcribe_dg')
def test_run_successful_transcription(mock_transcribe, mock_dg, vcon_with_one_valid_dialog):
    with patch('server.links.deepgram_link.VconRedis', autospec=True) as mock:
        instance = MagicMock()
        instance.get_vcon.return_value = vcon_with_one_valid_dialog
        mock.return_value = instance
        mock_transcribe.return_value = {"transcript": "ok", "confidence": 0.99}
        opts = {"DEEPGRAM_KEY": "test", "minimum_duration": 60, "api": {}}
        vcon_uuid = "test-uuid"
        result = run(vcon_uuid, "deepgram", opts)
        found = any(a for a in vcon_with_one_valid_dialog.analysis if a["type"] == "transcript")
        assert found
        assert instance.store_vcon.called
        assert result == vcon_uuid

@patch('server.links.deepgram_link.DeepgramClient')
@patch('server.links.deepgram_link.transcribe_dg')
def test_run_low_confidence(mock_transcribe, mock_dg, vcon_with_one_valid_dialog):
    with patch('server.links.deepgram_link.VconRedis', autospec=True) as mock:
        instance = MagicMock()
        instance.get_vcon.return_value = vcon_with_one_valid_dialog
        mock.return_value = instance
        mock_transcribe.return_value = {"transcript": "ok", "confidence": 0.2}
        opts = {"DEEPGRAM_KEY": "test", "minimum_duration": 60, "api": {}}
        vcon_uuid = "test-uuid"
        result = run(vcon_uuid, "deepgram", opts)
        found = any(a for a in vcon_with_one_valid_dialog.analysis if a["type"] == "transcript")
        assert not found
        assert instance.store_vcon.called
        assert result == vcon_uuid

@patch('server.links.deepgram_link.DeepgramClient')
@patch('server.links.deepgram_link.transcribe_dg')
def test_run_transcribe_error(mock_transcribe, mock_dg, vcon_with_one_valid_dialog):
    with patch('server.links.deepgram_link.VconRedis', autospec=True) as mock:
        instance = MagicMock()
        instance.get_vcon.return_value = vcon_with_one_valid_dialog
        mock.return_value = instance
        mock_transcribe.side_effect = Exception("API error")
        opts = {"DEEPGRAM_KEY": "test", "minimum_duration": 60, "api": {}}
        vcon_uuid = "test-uuid"
        with pytest.raises(Exception):
            run(vcon_uuid, "deepgram", opts)
        found = any(a for a in vcon_with_one_valid_dialog.analysis if a["type"] == "transcript")
        assert not found
        assert not instance.store_vcon.called

# ------------------- Integration Test Section -------------------

DEEPGRAM_KEY = os.environ.get("DEEPGRAM_KEY")
pytestmark = pytest.mark.skipif(not DEEPGRAM_KEY, reason="DEEPGRAM_KEY not set in environment")

@pytest.mark.integration
def test_deepgram_integration_real_api(tmp_path):
    """
    Integration test: runs Deepgram transcription on a real public audio file if DEEPGRAM_KEY is set.
    """
    from server.links.deepgram_link import run
    from server.vcon import Vcon
    from server.links.deepgram_link import VconRedis

    # Use a short public domain WAV file (e.g., from Wikimedia)
    audio_url = "https://raw.githubusercontent.com/vcon-dev/vcon-server/main/server/links/hugging_face_whisper/en_NatGen_CallCenter_BethTom_CancelPhonePlan.wav"
    vcon = Vcon.build_new()
    vcon.add_dialog({
        "type": "recording",
        "url": audio_url,
        "duration": 2  # seconds
    })
    vcon_uuid = vcon.uuid

    # Patch VconRedis to use our in-memory vcon
    class DummyVconRedis:
        def __init__(self):
            self._vcon = vcon
        def get_vcon(self, uuid):
            return self._vcon
        def store_vcon(self, vcon_obj):
            self._vcon = vcon_obj

    opts = {
        "DEEPGRAM_KEY": DEEPGRAM_KEY,
        "minimum_duration": 1,
        "api": {
            "model": "nova-3",
            "language": "en",
            "smart_format": True,
            "punctuate": True,
            "diarize": False,
            "utterances": False,
            "profanity_filter": False,
            "redact": False,
        }
    }

    # Patch VconRedis only for this test
    import server.links.deepgram_link as deepgram_mod
    orig_vcon_redis = deepgram_mod.VconRedis
    deepgram_mod.VconRedis = DummyVconRedis
    try:
        result = run(vcon_uuid, "deepgram", opts)
        assert result == vcon_uuid
        transcript_analysis = next((a for a in vcon.analysis if a["type"] == "transcript"), None)
        assert transcript_analysis is not None
        assert transcript_analysis["body"].get("transcript")
        assert transcript_analysis["body"].get("confidence", 0) > 0
    finally:
        deepgram_mod.VconRedis = orig_vcon_redis 

def make_vcon(dialogs):
    vcon = MagicMock()
    vcon.dialog = dialogs
    vcon.analysis = []
    vcon.uuid = "test-uuid"
    def add_analysis(**kwargs):
        vcon.analysis.append(kwargs)
    vcon.add_analysis = add_analysis
    return vcon

@patch("server.links.deepgram_link.VconRedis")
@patch("server.links.deepgram_link.DeepgramClient")
def test_run_with_duration(mock_deepgram_client, mock_vcon_redis):
    dialogs = [
        {"type": "recording", "url": "http://audio", "duration": 120},
    ]
    vcon = make_vcon(dialogs)
    mock_vcon_redis.return_value.get_vcon.return_value = vcon
    mock_vcon_redis.return_value.store_vcon = MagicMock()
    mock_deepgram_client.return_value = MagicMock()
    with patch("server.links.deepgram_link.transcribe_dg") as mock_transcribe:
        mock_transcribe.return_value = {"confidence": 0.9, "transcript": "text"}
        from server.links.deepgram_link import run
        result = run("test-uuid", "deepgram", opts={"DEEPGRAM_KEY": "fake", "api": {}})
        assert result == "test-uuid"
        assert len(vcon.analysis) == 1

@patch("server.links.deepgram_link.VconRedis")
@patch("server.links.deepgram_link.DeepgramClient")
def test_run_with_short_duration(mock_deepgram_client, mock_vcon_redis):
    dialogs = [
        {"type": "recording", "url": "http://audio", "duration": 10},
    ]
    vcon = make_vcon(dialogs)
    mock_vcon_redis.return_value.get_vcon.return_value = vcon
    mock_vcon_redis.return_value.store_vcon = MagicMock()
    mock_deepgram_client.return_value = MagicMock()
    with patch("server.links.deepgram_link.transcribe_dg") as mock_transcribe:
        from server.links.deepgram_link import run
        result = run("test-uuid", "deepgram", opts={"DEEPGRAM_KEY": "fake", "api": {}})
        assert result == "test-uuid"
        assert len(vcon.analysis) == 0

@patch("server.links.deepgram_link.VconRedis")
@patch("server.links.deepgram_link.DeepgramClient")
def test_run_missing_duration_wav_fetches_and_transcribes(mock_deepgram_client, mock_vcon_redis):
    dialogs = [
        {"type": "recording", "url": "http://audio.wav"},
    ]
    vcon = make_vcon(dialogs)
    mock_vcon_redis.return_value.get_vcon.return_value = vcon
    mock_vcon_redis.return_value.store_vcon = MagicMock()
    mock_deepgram_client.return_value = MagicMock()
    with patch("server.links.deepgram_link.get_wav_duration_from_url") as mock_get_duration, \
         patch("server.links.deepgram_link.transcribe_dg") as mock_transcribe:
        mock_get_duration.return_value = 120
        mock_transcribe.return_value = {"confidence": 0.9, "transcript": "text"}
        from server.links.deepgram_link import run
        result = run("test-uuid", "deepgram", opts={"DEEPGRAM_KEY": "fake", "api": {}})
        assert result == "test-uuid"
        assert len(vcon.analysis) == 1

@patch("server.links.deepgram_link.VconRedis")
@patch("server.links.deepgram_link.DeepgramClient")
def test_run_missing_duration_nonwav_transcribes_anyway(mock_deepgram_client, mock_vcon_redis):
    dialogs = [
        {"type": "recording", "url": "http://audio.mp3"},
    ]
    vcon = make_vcon(dialogs)
    mock_vcon_redis.return_value.get_vcon.return_value = vcon
    mock_vcon_redis.return_value.store_vcon = MagicMock()
    mock_deepgram_client.return_value = MagicMock()
    with patch("server.links.deepgram_link.transcribe_dg") as mock_transcribe:
        mock_transcribe.return_value = {"confidence": 0.9, "transcript": "text"}
        from server.links.deepgram_link import run
        result = run("test-uuid", "deepgram", opts={"DEEPGRAM_KEY": "fake", "api": {}})
        assert result == "test-uuid"
        assert len(vcon.analysis) == 1 