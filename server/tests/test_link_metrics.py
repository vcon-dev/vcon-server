"""End-to-end validation tests for link-level OTEL metrics (CON-6).

Each test exercises a link's run() function with mocked external calls and
asserts that the expected metric names and attributes are emitted to the
in-memory OTEL reader. No external services required.

Run with:
    pytest server/tests/test_link_metrics.py -v
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from tenacity import RetryError

from server.vcon import Vcon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_metrics(reader):
    """Return {metric_name: [{"attributes": {...}, ...}, ...]} from reader."""
    result = {}
    data = reader.get_metrics_data()
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                points = result.setdefault(metric.name, [])
                for dp in metric.data.data_points:
                    point = {"attributes": dict(dp.attributes)}
                    # Histogram data points have sum/count; Sum data points have value
                    if hasattr(dp, "sum") and hasattr(dp, "count"):
                        point["sum"] = dp.sum
                        point["count"] = dp.count
                    else:
                        point["value"] = dp.value
                    points.append(point)
    return result


def make_recording_vcon():
    """Vcon with one recording dialog (duration 120s, no transcript yet)."""
    vcon = Vcon.build_new()
    vcon.add_dialog({
        "type": "recording",
        "url": "https://example.com/audio.wav",
        "duration": 120,
    })
    return vcon


def make_transcript_vcon():
    """Vcon with one dialog that already has a transcript analysis."""
    vcon = make_recording_vcon()
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body={"paragraphs": {"transcript": "Hello world"}, "transcript": "Hello world"},
    )
    return vcon


def assert_metric_has_attrs(metrics, metric_name, expected_attrs):
    """Assert metric_name exists and at least one data point matches expected_attrs."""
    assert metric_name in metrics, f"Metric '{metric_name}' not found. Got: {list(metrics)}"
    points = metrics[metric_name]
    for point in points:
        if all(point["attributes"].get(k) == v for k, v in expected_attrs.items()):
            return
    raise AssertionError(
        f"No data point for '{metric_name}' has attributes {expected_attrs}. "
        f"Data points: {points}"
    )


# ---------------------------------------------------------------------------
# deepgram_link
# ---------------------------------------------------------------------------

class TestDeepgramMetrics:
    LINK_NAME = "deepgram_link"
    UUID = "dg-test-uuid"
    OPTS = {"DEEPGRAM_KEY": "fake-key", "minimum_duration": 60, "minimum_confidence": 0.5, "api": {}}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.deepgram_link import run
        with patch("server.links.deepgram_link.VconRedis") as mock_redis_cls, \
             patch("server.links.deepgram_link.transcribe_dg") as mock_transcribe:
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_transcribe.side_effect = side_effect
            else:
                mock_transcribe.return_value = mock_result
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_transcription_time(self, metric_reader):
        vcon = make_recording_vcon()
        result = {"confidence": 0.9, "transcript": "hello", "detected_language": "en", "words": [], "paragraphs": {}}
        self._run(vcon, mock_result=result)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.deepgram.transcription_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})

    def test_success_records_confidence(self, metric_reader):
        vcon = make_recording_vcon()
        result = {"confidence": 0.9, "transcript": "hello", "detected_language": "en", "words": [], "paragraphs": {}}
        self._run(vcon, mock_result=result)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.deepgram.confidence",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_recording_vcon()
        self._run(vcon, side_effect=Exception("API error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.deepgram.transcription_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})


# ---------------------------------------------------------------------------
# groq_whisper
# ---------------------------------------------------------------------------

class TestGroqWhisperMetrics:
    LINK_NAME = "groq_whisper"
    UUID = "groq-test-uuid"
    OPTS = {"API_KEY": "fake-key", "minimum_duration": 30}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.groq_whisper import run
        with patch("server.links.groq_whisper.VconRedis") as mock_redis_cls, \
             patch("server.links.groq_whisper.transcribe_groq_whisper") as mock_transcribe:
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_transcribe.side_effect = side_effect
            else:
                mock_result_obj = MagicMock()
                mock_result_obj.text = mock_result or "transcription text"
                mock_transcribe.return_value = mock_result_obj
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_transcription_time(self, metric_reader):
        vcon = make_recording_vcon()
        self._run(vcon)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.groq_whisper.transcription_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_recording_vcon()
        self._run(vcon, side_effect=RetryError(last_attempt=MagicMock()))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.groq_whisper.transcription_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})


# ---------------------------------------------------------------------------
# hugging_face_whisper
# ---------------------------------------------------------------------------

class TestHuggingFaceWhisperMetrics:
    LINK_NAME = "hugging_face_whisper"
    UUID = "hfw-test-uuid"
    OPTS = {"API_URL": "https://fake.hf.co", "API_KEY": "fake-key", "minimum_duration": 30, "Content-Type": "audio/flac"}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.hugging_face_whisper import run
        with patch("server.links.hugging_face_whisper.VconRedis") as mock_redis_cls, \
             patch("server.links.hugging_face_whisper.transcribe_hugging_face_whisper") as mock_transcribe:
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_transcribe.side_effect = side_effect
            else:
                mock_transcribe.return_value = mock_result or {"text": "hello world"}
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_transcription_time(self, metric_reader):
        vcon = make_recording_vcon()
        self._run(vcon)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.hugging_face_whisper.transcription_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_recording_vcon()
        self._run(vcon, side_effect=Exception("HF API error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.hugging_face_whisper.transcription_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})


# ---------------------------------------------------------------------------
# openai_transcribe
# ---------------------------------------------------------------------------

class TestOpenAITranscribeMetrics:
    LINK_NAME = "openai_transcribe"
    UUID = "oai-transcribe-uuid"
    OPTS = {"OPENAI_API_KEY": "fake-key", "model": "gpt-4o-transcribe", "minimum_duration": 3}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.openai_transcribe import run
        with patch("server.links.openai_transcribe.VconRedis") as mock_redis_cls, \
             patch("server.links.openai_transcribe.transcribe_openai") as mock_transcribe:
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_transcribe.side_effect = side_effect
            else:
                mock_transcribe.return_value = mock_result or {"text": "transcribed text"}
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_transcription_time(self, metric_reader):
        vcon = make_recording_vcon()
        self._run(vcon)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.transcription_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_recording_vcon()
        self._run(vcon, side_effect=Exception("OpenAI error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.transcription_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

class TestAnalyzeMetrics:
    LINK_NAME = "analyze"
    UUID = "analyze-test-uuid"
    OPTS = {"analysis_type": "summary", "model": "gpt-3.5-turbo-16k", "prompt": "Summarize", "temperature": 0,
            "source": {"analysis_type": "transcript", "text_location": "body.paragraphs.transcript"}}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.analyze import run
        with patch("server.links.analyze.VconRedis") as mock_redis_cls, \
             patch("server.links.analyze.get_openai_client"), \
             patch("server.links.analyze.generate_analysis") as mock_gen, \
             patch("server.links.analyze.is_included", return_value=True), \
             patch("server.links.analyze.randomly_execute_with_sampling", return_value=True), \
             patch("server.links.analyze.send_ai_usage_data_for_tracking"):
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_gen.side_effect = side_effect
            else:
                mock_gen.return_value = mock_result or "This is a summary."
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_analysis_time(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.analysis_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon, side_effect=Exception("OpenAI error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.analysis_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})


# ---------------------------------------------------------------------------
# analyze_and_label
# ---------------------------------------------------------------------------

class TestAnalyzeAndLabelMetrics:
    LINK_NAME = "analyze_and_label"
    UUID = "aal-test-uuid"
    OPTS = {"analysis_type": "labeled_analysis", "model": "gpt-4-turbo", "prompt": "Label this",
            "temperature": 0.2, "source": {"analysis_type": "transcript", "text_location": "body.paragraphs.transcript"},
            "response_format": {"type": "json_object"}}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.analyze_and_label import run
        with patch("server.links.analyze_and_label.VconRedis") as mock_redis_cls, \
             patch("server.links.analyze_and_label.get_openai_client"), \
             patch("server.links.analyze_and_label.generate_analysis_with_labels") as mock_gen, \
             patch("server.links.analyze_and_label.is_included", return_value=True), \
             patch("server.links.analyze_and_label.randomly_execute_with_sampling", return_value=True):
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_gen.side_effect = side_effect
            else:
                mock_gen.return_value = mock_result or json.dumps({"labels": ["label1", "label2"]})
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_labels_added(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.labels_added",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})

    def test_success_records_analysis_time(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.analysis_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon, side_effect=Exception("OpenAI error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.analysis_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})


# ---------------------------------------------------------------------------
# analyze_vcon
# ---------------------------------------------------------------------------

class TestAnalyzeVconMetrics:
    LINK_NAME = "analyze_vcon"
    UUID = "avcon-test-uuid"
    OPTS = {"analysis_type": "json_analysis", "model": "gpt-3.5-turbo-16k",
            "prompt": "Analyze", "system_prompt": "You are helpful.", "temperature": 0,
            "remove_body_properties": False}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.analyze_vcon import run
        with patch("server.links.analyze_vcon.VconRedis") as mock_redis_cls, \
             patch("server.links.analyze_vcon.get_openai_client"), \
             patch("server.links.analyze_vcon.generate_analysis") as mock_gen, \
             patch("server.links.analyze_vcon.is_included", return_value=True), \
             patch("server.links.analyze_vcon.randomly_execute_with_sampling", return_value=True):
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_vcon = MagicMock()
            mock_vcon.uuid = self.UUID
            mock_vcon.analysis = []
            mock_vcon.to_dict.return_value = {"uuid": self.UUID, "dialog": [], "analysis": []}
            mock_redis.get_vcon.return_value = mock_vcon
            if side_effect:
                mock_gen.side_effect = side_effect
            else:
                mock_gen.return_value = mock_result or json.dumps({"summary": "ok"})
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_analysis_time(self, metric_reader):
        self._run(None)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.analysis_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})

    def test_failure_increments_counter(self, metric_reader):
        self._run(None, side_effect=Exception("OpenAI error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.analysis_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})


# ---------------------------------------------------------------------------
# check_and_tag
# ---------------------------------------------------------------------------

class TestCheckAndTagMetrics:
    LINK_NAME = "check_and_tag"
    UUID = "cat-test-uuid"
    OPTS = {"analysis_type": "tag_evaluation", "model": "gpt-4",
            "tag_name": "urgent", "tag_value": "true",
            "evaluation_question": "Is this urgent?",
            "source": {"analysis_type": "transcript", "text_location": "body"},
            "response_format": {"type": "json_object"}}

    def _run(self, vcon, applies=True, side_effect=None):
        from server.links.check_and_tag import run
        with patch("server.links.check_and_tag.VconRedis") as mock_redis_cls, \
             patch("server.links.check_and_tag.get_openai_client"), \
             patch("server.links.check_and_tag.generate_tag_evaluation") as mock_gen, \
             patch("server.links.check_and_tag.is_included", return_value=True), \
             patch("server.links.check_and_tag.randomly_execute_with_sampling", return_value=True):
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_gen.side_effect = side_effect
            else:
                mock_gen.return_value = json.dumps({"applies": applies})
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_tag_applied_increments_counter(self, metric_reader):
        vcon = make_transcript_vcon()
        # transcript body needs to be accessible at path "body" for check_and_tag
        vcon.analysis[0]["body"] = "Hello world"
        self._run(vcon, applies=True)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.tags_applied",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"],
                                  "tag_name": self.OPTS["tag_name"]})

    def test_success_records_evaluation_time(self, metric_reader):
        vcon = make_transcript_vcon()
        vcon.analysis[0]["body"] = "Hello world"
        self._run(vcon, applies=True)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.evaluation_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_transcript_vcon()
        vcon.analysis[0]["body"] = "Hello world"
        self._run(vcon, side_effect=Exception("OpenAI error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.evaluation_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})


# ---------------------------------------------------------------------------
# detect_engagement
# ---------------------------------------------------------------------------

class TestDetectEngagementMetrics:
    LINK_NAME = "detect_engagement"
    UUID = "eng-test-uuid"
    OPTS = {"analysis_type": "engagement_analysis", "model": "gpt-4.1", "temperature": 0.2,
            "OPENAI_API_KEY": "fake-key",
            "source": {"analysis_type": "transcript", "text_location": "body.paragraphs.transcript"}}

    def _run(self, vcon, engaged=True, side_effect=None):
        from server.links.detect_engagement import run
        with patch("server.links.detect_engagement.VconRedis") as mock_redis_cls, \
             patch("server.links.detect_engagement.get_openai_client"), \
             patch("server.links.detect_engagement.check_engagement") as mock_check, \
             patch("server.links.detect_engagement.is_included", return_value=True), \
             patch("server.links.detect_engagement.randomly_execute_with_sampling", return_value=True):
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon
            if side_effect:
                mock_check.side_effect = side_effect
            else:
                mock_check.return_value = engaged
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_engagement_counter(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon, engaged=True)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.engagement_detected",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})

    def test_success_records_analysis_time(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon, engaged=True)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.engagement_analysis_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_transcript_vcon()
        self._run(vcon, side_effect=Exception("OpenAI error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.openai.engagement_analysis_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID,
                                  "analysis_type": self.OPTS["analysis_type"]})


# ---------------------------------------------------------------------------
# hugging_llm_link
# ---------------------------------------------------------------------------

class TestHuggingLLMMetrics:
    LINK_NAME = "hugging_llm"
    UUID = "hllm-test-uuid"
    OPTS = {"HUGGINGFACE_API_KEY": "fake-key", "use_local_model": False}

    def _run(self, vcon, mock_result=None, side_effect=None):
        from server.links.hugging_llm_link import run
        with patch("server.links.hugging_llm_link.VconRedis") as mock_redis_cls, \
             patch("server.links.hugging_llm_link.HuggingFaceLLM") as mock_llm_cls:
            mock_redis = MagicMock()
            mock_redis_cls.return_value = mock_redis
            mock_redis.get_vcon.return_value = vcon

            mock_llm = MagicMock()
            mock_llm_cls.return_value = mock_llm
            if side_effect:
                mock_llm.analyze.side_effect = side_effect
            else:
                mock_llm.analyze.return_value = mock_result or {
                    "analysis": "some analysis", "model": "llama-2", "parameters": {}
                }
            try:
                run(self.UUID, self.LINK_NAME, self.OPTS)
            except Exception:
                pass

    def test_success_records_llm_time(self, metric_reader):
        vcon = make_transcript_vcon()
        # hugging_llm reads body.transcript (dict format)
        vcon.analysis[0]["body"] = {"transcript": "Hello world"}
        self._run(vcon)
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.huggingface.llm_time",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})

    def test_failure_increments_counter(self, metric_reader):
        vcon = make_transcript_vcon()
        vcon.analysis[0]["body"] = {"transcript": "Hello world"}
        self._run(vcon, side_effect=Exception("HF API error"))
        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.link.huggingface.llm_failures",
                                 {"link.name": self.LINK_NAME, "vcon.uuid": self.UUID})


# ---------------------------------------------------------------------------
# Main loop (VconChainRequest)
# ---------------------------------------------------------------------------

class TestMainLoopMetrics:
    CHAIN_NAME = "test_chain"
    UUID = "main-loop-uuid"

    def test_vcon_processing_records_time_and_count(self, metric_reader):
        from server.main import VconChainRequest
        import server.main as main_module

        chain_details = {
            "name": self.CHAIN_NAME,
            "links": ["mock_link"],
            "storages": [],
            "egress_lists": [],
        }

        # Provide a minimal config so _process_link can find the link
        main_module.config = {
            "links": {
                "mock_link": {
                    "module": "mock_module",
                    "options": {},
                }
            }
        }

        mock_module = MagicMock()
        mock_module.run.return_value = self.UUID

        with patch.dict("server.main.imported_modules", {"mock_module": mock_module}):
            req = VconChainRequest(chain_details, self.UUID, context=None)
            req.process()

        metrics = extract_metrics(metric_reader)
        assert_metric_has_attrs(metrics, "conserver.main_loop.vcon_processing_time",
                                 {"chain.name": self.CHAIN_NAME})
        assert_metric_has_attrs(metrics, "conserver.main_loop.count_vcons_processed",
                                 {"chain.name": self.CHAIN_NAME})
