import json
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


@patch("links.tag.VconRedis")
def test_run_applies_name_value_string_tags(mock_vcon_redis):
    # "name:value" options must set name -> value, not "tag:tag". (CON-737)
    vcon = Vcon.build_new()
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    run("test-uuid", "tag", opts={"tags": ["source:siprec-adapter", "pipeline:interop"]})

    assert vcon.get_tag("source") == "siprec-adapter"
    assert vcon.get_tag("pipeline") == "interop"


@patch("links.tag.VconRedis")
def test_run_applies_dict_form_tags(mock_vcon_redis):
    # dict-form options: {name: value}. (CON-737)
    vcon = Vcon.build_new()
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    run("test-uuid", "tag", opts={"tags": {"env": "prod", "team": "interop"}})

    assert vcon.get_tag("env") == "prod"
    assert vcon.get_tag("team") == "interop"


@patch("links.tag.VconRedis")
def test_run_tolerates_dict_bodied_tags_attachment(mock_vcon_redis):
    # A producer (e.g. the SIPREC adapter) wrote purpose="tags" with a dict
    # body. add_tag must flatten it instead of raising on `.append`. (CON-737)
    vcon = Vcon.build_new()
    vcon.vcon_dict["attachments"].append(
        {"purpose": "tags", "encoding": "json", "body": json.dumps({"source": "siprec"})}
    )
    mock_instance = mock_vcon_redis.return_value
    mock_instance.get_vcon.return_value = vcon

    result = run("test-uuid", "tag", opts={"tags": ["pipeline:interop"]})

    assert result == "test-uuid"
    assert vcon.get_tag("source") == "siprec"      # pre-existing dict entry preserved
    assert vcon.get_tag("pipeline") == "interop"   # new tag appended
    mock_instance.store_vcon.assert_called_once_with(vcon)
