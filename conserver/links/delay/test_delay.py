from unittest.mock import patch

from links.delay import default_options, run


@patch("links.delay.time.sleep")
def test_run_sleeps_default(mock_sleep):
    result = run("test-uuid", "delay")

    assert result == "test-uuid"
    mock_sleep.assert_called_once_with(default_options["seconds"])


@patch("links.delay.time.sleep")
def test_run_sleeps_custom(mock_sleep):
    result = run("test-uuid", "delay", opts={"seconds": 12})

    assert result == "test-uuid"
    mock_sleep.assert_called_once_with(12)


@patch("links.delay.time.sleep")
def test_partial_opts_keep_default_seconds(mock_sleep):
    # An opts dict without "seconds" must fall back to the default, not KeyError.
    result = run("test-uuid", "delay", opts={"unrelated": True})

    assert result == "test-uuid"
    mock_sleep.assert_called_once_with(default_options["seconds"])


@patch("links.delay.time.sleep")
def test_negative_seconds_clamped_to_zero(mock_sleep):
    result = run("test-uuid", "delay", opts={"seconds": -3})

    assert result == "test-uuid"
    mock_sleep.assert_called_once_with(0)
