from unittest.mock import patch

from vcon import Vcon

from links.tag import run


@patch("links.tag.VconRedis")
def test_run_applies_default_tags_and_stores_vcon(mock_vcon_redis):
    vcon = Vcon.build_new()
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    result = run("test-uuid", "tag")

    assert result == "test-uuid"
    assert vcon.get_tag("iron") == "iron"
    assert vcon.get_tag("maiden") == "maiden"
    mock_instance.store_vcon.assert_called_once_with(vcon)


@patch("links.tag.VconRedis")
def test_run_respects_custom_tags(mock_vcon_redis):
    vcon = Vcon.build_new()
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    result = run("test-uuid", "tag", opts={"tags": ["priority", "vip"]})

    assert result == "test-uuid"
    assert vcon.get_tag("priority") == "priority"
    assert vcon.get_tag("vip") == "vip"
    mock_instance.store_vcon.assert_called_once_with(vcon)


@patch("links.tag.VconRedis")
def test_run_handles_empty_tag_list(mock_vcon_redis):
    vcon = Vcon.build_new()
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    result = run("test-uuid", "tag", opts={"tags": []})

    assert result == "test-uuid"
    assert vcon.get_tag("iron") is None
    mock_instance.store_vcon.assert_called_once_with(vcon)
