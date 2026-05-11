from unittest.mock import patch

from links.expire_vcon import default_options, run


@patch("links.expire_vcon.redis")
def test_run_sets_default_expiry(mock_redis):
    result = run("test-uuid", "expire_vcon")

    assert result == "test-uuid"
    mock_redis.expire.assert_called_once_with("vcon:test-uuid", default_options["seconds"])


@patch("links.expire_vcon.redis")
def test_run_sets_custom_expiry(mock_redis):
    result = run("test-uuid", "expire_vcon", opts={"seconds": 90})

    assert result == "test-uuid"
    mock_redis.expire.assert_called_once_with("vcon:test-uuid", 90)
