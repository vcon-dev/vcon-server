import json
from unittest.mock import Mock, patch

import pytest

from links.check_and_tag import get_analysis_for_type, navigate_dict, run
from vcon import Vcon


@pytest.fixture
def mock_vcon_redis():
    with patch("links.check_and_tag.VconRedis", autospec=True) as mock:
        yield mock


@pytest.fixture
def sample_vcon():
    vcon = Vcon.build_new()
    vcon.add_dialog({"type": "text", "body": "Customer called about a refund."})
    vcon.add_analysis(
        type="transcript",
        dialog=0,
        vendor="test",
        body="The customer is upset about a duplicate charge and asks for a refund.",
    )
    return vcon


def test_get_analysis_for_type(sample_vcon):
    analysis = get_analysis_for_type(sample_vcon, 0, "transcript")
    assert analysis is not None
    assert analysis["type"] == "transcript"
    assert get_analysis_for_type(sample_vcon, 0, "missing") is None


def test_navigate_dict():
    assert navigate_dict({"body": {"text": "hello"}}, "body.text") == "hello"
    assert navigate_dict({"body": {"text": "hello"}}, "body.missing") is None


def test_run_requires_tag_name():
    with pytest.raises(ValueError, match="tag_name is required"):
        run(
            "test-uuid",
            "check_and_tag",
            opts={"tag_value": "billing", "evaluation_question": "Is this about billing?"},
        )


@patch("links.check_and_tag.record_histogram")
@patch("links.check_and_tag.increment_counter")
@patch("links.check_and_tag.get_openai_client")
@patch("links.check_and_tag.generate_tag_evaluation")
@patch("links.check_and_tag.is_included", return_value=True)
@patch("links.check_and_tag.randomly_execute_with_sampling", return_value=True)
def test_run_applies_tag_when_evaluation_is_positive(
    mock_sampling,
    mock_is_included,
    mock_generate_tag_evaluation,
    mock_get_openai_client,
    mock_increment_counter,
    mock_record_histogram,
    mock_vcon_redis,
    sample_vcon,
):
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = sample_vcon
    mock_get_openai_client.return_value = Mock()
    mock_generate_tag_evaluation.return_value = json.dumps({"applies": True})

    result = run(
        "test-uuid",
        "check_and_tag",
        opts={
            "tag_name": "topic",
            "tag_value": "billing",
            "evaluation_question": "Is this conversation about billing?",
        },
    )

    assert result == "test-uuid"
    assert sample_vcon.get_tag("topic") == "billing"
    analysis = get_analysis_for_type(sample_vcon, 0, "tag_evaluation")
    assert analysis["body"]["applies"] is True
    mock_instance.store_vcon.assert_called_once_with(sample_vcon)
    mock_increment_counter.assert_any_call(
        "conserver.link.openai.tags_applied",
        attributes={
            "analysis_type": "tag_evaluation",
            "tag_name": "topic",
            "tag_value": "billing",
            "link.name": "check_and_tag",
            "vcon.uuid": "test-uuid",
        },
    )
    mock_record_histogram.assert_called_once()


@patch("links.check_and_tag.record_histogram")
@patch("links.check_and_tag.increment_counter")
@patch("links.check_and_tag.get_openai_client")
@patch("links.check_and_tag.generate_tag_evaluation")
@patch("links.check_and_tag.is_included", return_value=True)
@patch("links.check_and_tag.randomly_execute_with_sampling", return_value=True)
def test_run_records_negative_evaluation_without_applying_tag(
    mock_sampling,
    mock_is_included,
    mock_generate_tag_evaluation,
    mock_get_openai_client,
    mock_increment_counter,
    mock_record_histogram,
    mock_vcon_redis,
    sample_vcon,
):
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = sample_vcon
    mock_get_openai_client.return_value = Mock()
    mock_generate_tag_evaluation.return_value = json.dumps({"applies": False})

    result = run(
        "test-uuid",
        "check_and_tag",
        opts={
            "tag_name": "topic",
            "tag_value": "billing",
            "evaluation_question": "Is this conversation about billing?",
        },
    )

    assert result == "test-uuid"
    assert sample_vcon.get_tag("topic") is None
    analysis = get_analysis_for_type(sample_vcon, 0, "tag_evaluation")
    assert analysis["body"]["applies"] is False
    mock_instance.store_vcon.assert_called_once_with(sample_vcon)
    mock_increment_counter.assert_not_called()
    mock_record_histogram.assert_called_once()


@patch("links.check_and_tag.record_histogram")
@patch("links.check_and_tag.get_openai_client")
@patch("links.check_and_tag.generate_tag_evaluation")
@patch("links.check_and_tag.is_included", return_value=True)
@patch("links.check_and_tag.randomly_execute_with_sampling", return_value=True)
def test_run_skips_dialogs_without_source_analysis(
    mock_sampling,
    mock_is_included,
    mock_generate_tag_evaluation,
    mock_get_openai_client,
    mock_record_histogram,
    mock_vcon_redis,
):
    vcon = Vcon.build_new()
    vcon.add_dialog({"type": "text", "body": "No transcript present"})

    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon
    mock_get_openai_client.return_value = Mock()

    result = run(
        "test-uuid",
        "check_and_tag",
        opts={
            "tag_name": "topic",
            "tag_value": "billing",
            "evaluation_question": "Is this conversation about billing?",
        },
    )

    assert result == "test-uuid"
    mock_generate_tag_evaluation.assert_not_called()
    mock_record_histogram.assert_not_called()
    mock_instance.store_vcon.assert_called_once_with(vcon)
