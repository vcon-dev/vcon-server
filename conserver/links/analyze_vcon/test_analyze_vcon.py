import json
from unittest.mock import Mock, patch

import pytest

from links.analyze_vcon import (
    get_analysis_for_type,
    prepare_vcon_for_analysis,
    run,
)
from vcon import Vcon


@pytest.fixture
def sample_vcon():
    vcon = Vcon.build_new()
    vcon.add_dialog({"type": "text", "body": "Customer asked for a refund."})
    return vcon


def test_prepare_vcon_for_analysis_removes_dialog_bodies(sample_vcon):
    prepared = prepare_vcon_for_analysis(sample_vcon, remove_body_properties=True)

    assert "body" not in prepared["dialog"][0]


def test_prepare_vcon_for_analysis_preserves_dialog_bodies(sample_vcon):
    prepared = prepare_vcon_for_analysis(sample_vcon, remove_body_properties=False)

    assert prepared["dialog"][0]["body"] == "Customer asked for a refund."


def test_get_analysis_for_type(sample_vcon):
    sample_vcon.add_analysis(
        type="json_analysis",
        dialog=0,
        vendor="openai",
        body={"summary": "existing"},
    )

    assert get_analysis_for_type(sample_vcon, "json_analysis") is not None
    assert get_analysis_for_type(sample_vcon, "missing") is None


@patch("links.analyze_vcon.get_openai_client")
@patch("links.analyze_vcon.is_included", return_value=True)
@patch("links.analyze_vcon.randomly_execute_with_sampling", return_value=True)
@patch("links.analyze_vcon.VconRedis")
def test_run_skips_when_analysis_already_exists(
    mock_vcon_redis,
    mock_sampling,
    mock_is_included,
    mock_get_openai_client,
    sample_vcon,
):
    sample_vcon.add_analysis(
        type="json_analysis",
        dialog=0,
        vendor="openai",
        body={"summary": "existing"},
    )
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = sample_vcon

    result = run("test-uuid", "analyze_vcon")

    assert result == "test-uuid"
    mock_get_openai_client.assert_not_called()
    mock_instance.store_vcon.assert_not_called()


@patch("links.analyze_vcon.record_histogram")
@patch("links.analyze_vcon.increment_counter")
@patch("links.analyze_vcon.get_openai_client")
@patch("links.analyze_vcon.generate_analysis", return_value="not valid json")
@patch("links.analyze_vcon.is_included", return_value=True)
@patch("links.analyze_vcon.randomly_execute_with_sampling", return_value=True)
@patch("links.analyze_vcon.VconRedis")
def test_run_raises_for_invalid_json_response(
    mock_vcon_redis,
    mock_sampling,
    mock_is_included,
    mock_generate_analysis,
    mock_get_openai_client,
    mock_increment_counter,
    mock_record_histogram,
    sample_vcon,
):
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = sample_vcon
    mock_get_openai_client.return_value = Mock()

    with pytest.raises(ValueError, match="Invalid JSON response from OpenAI"):
        run("test-uuid", "analyze_vcon")

    mock_instance.store_vcon.assert_not_called()
    mock_record_histogram.assert_not_called()
    mock_increment_counter.assert_any_call(
        "conserver.link.openai.invalid_json",
        attributes={
            "analysis_type": "json_analysis",
            "link.name": "analyze_vcon",
            "vcon.uuid": "test-uuid",
        },
    )
    mock_increment_counter.assert_any_call(
        "conserver.link.openai.analysis_failures",
        attributes={
            "analysis_type": "json_analysis",
            "link.name": "analyze_vcon",
            "vcon.uuid": "test-uuid",
        },
    )
