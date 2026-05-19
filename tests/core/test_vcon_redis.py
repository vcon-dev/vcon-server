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


# ---------------------------------------------------------------------------
# Storage fallback path (CONSERVER-B7)
# ---------------------------------------------------------------------------


def _miss_then_hit_redis(mock_redis, storage_dict):
    """Configure the mocked redis client so .json().get() returns None
    (Redis miss). Returns the mock_json handle so callers can assert on
    re-cache writes."""
    mock_json = MagicMock()
    mock_json.get.return_value = None
    mock_redis.json.return_value = mock_json
    return mock_json


@patch("lib.vcon_redis.Storage")
@patch("lib.vcon_redis.Configuration")
@patch("lib.vcon_redis.VCON_STORAGE_FALLBACK_ENABLED", True)
@patch("lib.vcon_redis.redis")
def test_get_vcon_redis_miss_storage_hit_recaches(
    mock_redis, mock_config, mock_storage_cls
):
    vcon_dict = _load_sample_vcon_dict()
    mock_json = _miss_then_hit_redis(mock_redis, vcon_dict)
    mock_config.get_storages.return_value = {"s3": {}}

    storage_instance = MagicMock()
    storage_instance.get.return_value = vcon_dict
    mock_storage_cls.return_value = storage_instance

    loaded = VconRedis().get_vcon(vcon_dict["uuid"])

    assert loaded is not None
    assert loaded.uuid == vcon_dict["uuid"]
    mock_storage_cls.assert_called_once_with(storage_name="s3")
    storage_instance.get.assert_called_once_with(vcon_dict["uuid"])
    # Re-cache happened: json().set and expire on the key, and sorted-set add.
    assert mock_json.set.call_count == 1
    mock_redis.expire.assert_called_once()
    mock_redis.zadd.assert_called_once()


@patch("lib.vcon_redis.Storage")
@patch("lib.vcon_redis.Configuration")
@patch("lib.vcon_redis.VCON_STORAGE_FALLBACK_ENABLED", True)
@patch("lib.vcon_redis.redis")
def test_get_vcon_redis_miss_storage_miss_returns_none(
    mock_redis, mock_config, mock_storage_cls
):
    _miss_then_hit_redis(mock_redis, None)
    mock_config.get_storages.return_value = {"s3": {}, "postgres": {}}
    storage_instance = MagicMock()
    storage_instance.get.return_value = None
    mock_storage_cls.return_value = storage_instance

    assert VconRedis().get_vcon("missing-uuid") is None
    # Both backends were tried.
    assert storage_instance.get.call_count == 2


@patch("lib.vcon_redis.Storage")
@patch("lib.vcon_redis.Configuration")
@patch("lib.vcon_redis.VCON_STORAGE_FALLBACK_ENABLED", False)
@patch("lib.vcon_redis.redis")
def test_get_vcon_storage_fallback_disabled(
    mock_redis, mock_config, mock_storage_cls
):
    _miss_then_hit_redis(mock_redis, None)

    assert VconRedis().get_vcon("missing-uuid") is None
    # Flag off: no storage iteration, no Storage instantiation.
    mock_config.get_storages.assert_not_called()
    mock_storage_cls.assert_not_called()


@patch("lib.vcon_redis.Storage")
@patch("lib.vcon_redis.Configuration")
@patch("lib.vcon_redis.VCON_STORAGE_FALLBACK_ENABLED", True)
@patch("lib.vcon_redis.redis")
def test_get_vcon_first_storage_errors_second_succeeds(
    mock_redis, mock_config, mock_storage_cls
):
    vcon_dict = _load_sample_vcon_dict()
    _miss_then_hit_redis(mock_redis, vcon_dict)
    mock_config.get_storages.return_value = {"broken": {}, "s3": {}}

    broken = MagicMock()
    broken.get.side_effect = RuntimeError("backend down")
    good = MagicMock()
    good.get.return_value = vcon_dict
    mock_storage_cls.side_effect = [broken, good]

    loaded = VconRedis().get_vcon(vcon_dict["uuid"])

    assert loaded is not None
    assert loaded.uuid == vcon_dict["uuid"]
    assert mock_storage_cls.call_count == 2


@patch("lib.vcon_redis.Storage")
@patch("lib.vcon_redis.Configuration")
@patch("lib.vcon_redis.VCON_STORAGE_FALLBACK_ENABLED", True)
@patch("lib.vcon_redis.redis")
def test_get_vcon_dict_falls_back_to_storage(
    mock_redis, mock_config, mock_storage_cls
):
    vcon_dict = _load_sample_vcon_dict()
    _miss_then_hit_redis(mock_redis, vcon_dict)
    mock_config.get_storages.return_value = {"s3": {}}
    storage_instance = MagicMock()
    storage_instance.get.return_value = vcon_dict
    mock_storage_cls.return_value = storage_instance

    loaded = VconRedis().get_vcon_dict(vcon_dict["uuid"])

    assert loaded is not None
    assert loaded["uuid"] == vcon_dict["uuid"]
    storage_instance.get.assert_called_once()


@patch("lib.vcon_redis.Storage")
@patch("lib.vcon_redis.Configuration")
@patch("lib.vcon_redis.VCON_STORAGE_FALLBACK_ENABLED", True)
@patch("lib.vcon_redis.redis")
def test_get_vcon_redis_hit_skips_storage(
    mock_redis, mock_config, mock_storage_cls
):
    """When Redis has the vCon, storage must not be touched at all."""
    vcon_dict = _load_sample_vcon_dict()
    mock_json = MagicMock()
    mock_json.get.return_value = vcon_dict  # Redis hit
    mock_redis.json.return_value = mock_json

    loaded = VconRedis().get_vcon(vcon_dict["uuid"])

    assert loaded is not None
    mock_config.get_storages.assert_not_called()
    mock_storage_cls.assert_not_called()