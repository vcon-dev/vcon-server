import pytest
from unittest.mock import patch
import os
import json
# import sys
from . import run
import redis_mgr


# load vcons from redis
def load_vcons():
    vcons = []
    count = 0
    redis = redis_mgr.get_client()
    for key in redis.keys("vcon:*"):
        vcon = redis_mgr.get_key(key)
        vcons.append(vcon)
        count += 1
        if count == 10:
            break
    return vcons


# @pytest.fixture(scope="function")
# def vcon_input(fixture_name):
#     file_path = os.path.join(os.path.dirname(__file__), f'dataset//{fixture_name}.json')
#     with open(file_path, 'r') as f:
#         return json.load(f)


# @pytest.mark.parametrize("fixture_name", ["vcon_fixture"])
def test_run():
    test_vcons = load_vcons()
    print(test_vcons["uuid"])
    for vcon in test_vcons:
        redis_mgr.set_key(f"vcon:{vcon["uuid"]}", vcon)
        result = run(vcon["uuid"], 'tag')
        assert result == vcon["uuid"]
        # result.add_tag.assert_any_call('strolid', 'iron')
        # result.add_tag.assert_any_call('strolid', 'maiden')
    # mock_vcon_redis.return_value.store_vcon.assert_called_once_with(mock_vcon)


def test_run_vcon_not_found():
    # There is no vcon at this key
    result = run('bad_key', 'tag')
    assert result == 'bad_key'


# @pytest.mark.parametrize("fixture_name", ["bad_vcon"])
# def test_run_bad_vcon(vcon_input):
#     with pytest.raises(Exception):
#         mock_vcon_data = vcon_input
#         redis_mgr.set_key(f"vcon:{mock_vcon_data["uuid"]}", mock_vcon_data)
#         run(mock_vcon_data["uuid"], 'tag')


# def test_run_tags_added_to_vcon(mock_vcon_redis, mock_vcon):
#     vcon_uuid = "test_uuid"
#     opts = {"tags": ["iron", "maiden"]}
#     with patch("your_module.VconRedis", return_value=mock_vcon_redis):
#         result = run(vcon_uuid, "test_link", opts=opts)
#     assert result == vcon_uuid
#     mock_vcon.add_tag.assert_any_call("strolid", "iron")
#     mock_vcon.add_tag.assert_any_call("strolid", "maiden")
#     mock_vcon_redis.store_vcon.assert_called_once_with(mock_vcon)



    