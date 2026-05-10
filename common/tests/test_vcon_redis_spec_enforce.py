"""Tests for VconRedis._enforce_spec_on_write."""

from lib.vcon_redis import VconRedis


def test_sets_missing_syntax_param():
    d = {"uuid": "u"}
    VconRedis._enforce_spec_on_write(d)
    assert d["vcon"] == "0.4.0"


def test_keeps_existing_syntax_param():
    d = {"uuid": "u", "vcon": "0.4.0"}
    VconRedis._enforce_spec_on_write(d)
    assert d["vcon"] == "0.4.0"


def test_strips_empty_group():
    d = {"uuid": "u", "group": []}
    VconRedis._enforce_spec_on_write(d)
    assert "group" not in d


def test_strips_empty_redacted():
    d = {"uuid": "u", "redacted": {}}
    VconRedis._enforce_spec_on_write(d)
    assert "redacted" not in d


def test_keeps_non_empty_group_and_redacted():
    d = {
        "uuid": "u",
        "group": [{"uuid": "g1"}],
        "redacted": {"uuid": "previous"},
    }
    VconRedis._enforce_spec_on_write(d)
    assert d["group"] == [{"uuid": "g1"}]
    assert d["redacted"] == {"uuid": "previous"}


def test_returns_same_dict():
    d = {"uuid": "u"}
    assert VconRedis._enforce_spec_on_write(d) is d
