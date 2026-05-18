import json
from copy import deepcopy
from unittest.mock import MagicMock, patch

import vcon

from lib.vcon_compat import normalize_legacy_fields
from lib.vcon_redis import VconRedis


def _load_sample_vcon_dict():
    with open("tests/dataset/1ba06c0c-97ea-439f-8691-717ef86e4f3e.vcon.json") as f:
        return json.load(f)


@patch("lib.vcon_redis.redis")
def test_store_vcon(mock_redis):
    vcon_redis = VconRedis()
    vcon_obj = vcon.Vcon(_load_sample_vcon_dict())
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json

    vcon_redis.store_vcon(vcon_obj)

    expected_key = f"vcon:{vcon_obj.uuid}"
    mock_json.set.assert_called_once()
    mock_redis.expire.assert_not_called()
    assert mock_json.set.call_args.args[0] == expected_key


@patch("lib.vcon_redis.redis")
def test_get_vcon(mock_redis):
    vcon_redis = VconRedis()
    vcon_dict = _load_sample_vcon_dict()
    mock_json = MagicMock()
    mock_json.get.return_value = vcon_dict
    mock_redis.json.return_value = mock_json

    loaded_vcon = vcon_redis.get_vcon(vcon_dict["uuid"])

    expected_vcon_dict = deepcopy(vcon_dict)
    normalize_legacy_fields(expected_vcon_dict)
    expected_vcon = vcon.Vcon(expected_vcon_dict)

    assert expected_vcon.to_dict() == loaded_vcon.to_dict()


@patch("lib.vcon_redis.redis")
def test_store_vcon_dict(mock_redis):
    vcon_redis = VconRedis()
    vcon_dict = _load_sample_vcon_dict()
    mock_json = MagicMock()
    mock_redis.json.return_value = mock_json

    vcon_redis.store_vcon_dict(vcon_dict)

    expected_key = f"vcon:{vcon_dict['uuid']}"
    mock_json.set.assert_called_once()
    mock_redis.expire.assert_not_called()
    assert mock_json.set.call_args.args[0] == expected_key


@patch("lib.vcon_redis.redis")
def test_get_vcon_dict(mock_redis):
    vcon_redis = VconRedis()
    vcon_dict = _load_sample_vcon_dict()
    mock_json = MagicMock()
    mock_json.get.return_value = vcon_dict
    mock_redis.json.return_value = mock_json

    loaded_vcon_dict = vcon_redis.get_vcon_dict(vcon_dict["uuid"])

    assert vcon_dict == loaded_vcon_dict