"""Tests for CONSERVER_INGRESS_INCLUDE / CONSERVER_INGRESS_EXCLUDE.

The filters let separate conserver deployments share one chain config while
each serves its own ingress lists.

Run with:
    docker compose run --rm conserver pytest conserver/tests/test_ingress_filter.py -v
"""
from importlib import reload
from unittest.mock import MagicMock, patch

import pytest

FILTER_ENV = (
    "CONSERVER_INGRESS_INCLUDE",
    "CONSERVER_INGRESS_EXCLUDE",
    "CONSERVER_INGRESS_REQUIRE_FILTER",
    "CONSERVER_FOLLOWERS_ENABLED",
)


LISTS = ["default", "transcribe", "chain_a", "chain_b"]


def _reload_config():
    import settings
    import config
    reload(settings)
    reload(config)
    return config


def _reload_all():
    """Reload modules under the current env so no filter state leaks between tests."""
    import sys
    _reload_config()
    if "main" in sys.modules:
        with patch("redis_mgr.get_client", return_value=MagicMock()):
            reload(sys.modules["main"])


@pytest.fixture(autouse=True)
def _clear_filters(monkeypatch):
    for name in FILTER_ENV:
        monkeypatch.delenv(name, raising=False)
    yield
    for name in FILTER_ENV:
        monkeypatch.delenv(name, raising=False)
    _reload_all()


def test_no_filter_keeps_every_list_in_order():
    config = _reload_config()
    assert config.filter_ingress_lists(LISTS) == LISTS


def test_include_keeps_only_named_lists(monkeypatch):
    monkeypatch.setenv("CONSERVER_INGRESS_INCLUDE", "default")
    config = _reload_config()
    assert config.filter_ingress_lists(LISTS) == ["default"]


def test_exclude_drops_named_lists_and_keeps_new_ones(monkeypatch):
    """Exclude is the safe form for the main deployment: a chain added later
    is still served rather than silently orphaned."""
    monkeypatch.setenv("CONSERVER_INGRESS_EXCLUDE", "default")
    config = _reload_config()
    assert config.filter_ingress_lists(LISTS + ["new_chain"]) == ["transcribe", "chain_a", "chain_b", "new_chain"]


def test_whitespace_and_empty_entries_are_ignored(monkeypatch):
    monkeypatch.setenv("CONSERVER_INGRESS_INCLUDE", " transcribe , ,chain_a ")
    config = _reload_config()
    assert config.filter_ingress_lists(LISTS) == ["transcribe", "chain_a"]


def test_exclude_applies_after_include(monkeypatch):
    monkeypatch.setenv("CONSERVER_INGRESS_INCLUDE", "default,transcribe")
    monkeypatch.setenv("CONSERVER_INGRESS_EXCLUDE", "transcribe")
    config = _reload_config()
    assert config.filter_ingress_lists(LISTS) == ["default"]


def test_include_of_unknown_list_yields_nothing(monkeypatch):
    monkeypatch.setenv("CONSERVER_INGRESS_INCLUDE", "typo")
    config = _reload_config()
    assert config.filter_ingress_lists(LISTS) == []


@pytest.fixture
def main_module(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:65535/0")
    with patch("redis_mgr.get_client", return_value=MagicMock()):
        import main
        reload(main)
    main.shutdown_requested = False
    main.worker_processes = []
    main.imported_modules = {}
    yield main
    # Module state is restored by _clear_filters, which reloads under a clean env.
    main.shutdown_requested = False


def test_worker_loop_blpops_only_filtered_lists(main_module, monkeypatch):
    monkeypatch.setenv("CONSERVER_INGRESS_EXCLUDE", "default")
    _reload_config()
    reload(main_module)
    main_module.shutdown_requested = False

    fake_config = {
        "chains": {
            name: {"ingress_lists": [name], "links": [], "storages": [], "enabled": 1}
            for name in LISTS
        },
        "imports": {},
    }
    seen = []

    def fake_blpop(lists, timeout):  # noqa: ARG001
        seen.append(list(lists))
        main_module.shutdown_requested = True
        return None

    mock_r = MagicMock()
    mock_r.blpop.side_effect = fake_blpop
    with patch("main.redis_mgr.get_client", return_value=mock_r), \
         patch("main.init_error_tracker"), \
         patch("main.init_tracing"), \
         patch("main.get_config", return_value=fake_config), \
         patch("main.signal.signal"), \
         patch("main.get_vcon_concurrency", return_value=1), \
         patch("lib.queue_metrics.register_ingress_list_length_gauge"), \
         patch("lib.queue_metrics.register_redis_memory_gauge"):
        main_module.worker_loop(worker_id=1)

    assert seen == [["transcribe", "chain_a", "chain_b"]]


# Fail-closed behaviour

def _chains(names):
    return {
        "chains": {
            name: {"ingress_lists": [name], "links": [], "storages": [], "enabled": 1}
            for name in names
        },
        "imports": {},
    }


def _startup(main_module, monkeypatch, env=None, names=LISTS):
    """Reload with env, load a config of `names`, and run the startup validation."""
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    _reload_config()
    reload(main_module)
    monkeypatch.setattr(main_module, "config", _chains(names), raising=False)
    # The module logger writes to the stdout captured at import, so inspect calls instead.
    monkeypatch.setattr(main_module, "logger", MagicMock())
    return main_module.validate_ingress_filter()


@pytest.mark.parametrize("value", ["", ",", " ", " , "])
def test_empty_include_is_a_config_error(monkeypatch, value):
    monkeypatch.setenv("CONSERVER_INGRESS_INCLUDE", value)
    config = _reload_config()
    with pytest.raises(ValueError, match="CONSERVER_INGRESS_INCLUDE"):
        config.filter_ingress_lists(LISTS)


@pytest.mark.parametrize("value", ["", ",", " , "])
def test_empty_exclude_is_a_config_error(monkeypatch, value):
    monkeypatch.setenv("CONSERVER_INGRESS_EXCLUDE", value)
    config = _reload_config()
    with pytest.raises(ValueError, match="CONSERVER_INGRESS_EXCLUDE"):
        config.filter_ingress_lists(LISTS)


@pytest.mark.parametrize("value", ["", ",", " ", " , "])
def test_startup_exits_on_empty_include(main_module, monkeypatch, value):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_INCLUDE": value})
    assert exc.value.code != 0


def test_startup_exits_on_empty_exclude(main_module, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_EXCLUDE": ""})
    assert exc.value.code != 0


def test_startup_exits_when_include_matches_no_list(main_module, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_INCLUDE": "typo,other"})
    assert exc.value.code != 0
    out = " ".join(str(c) for c in main_module.logger.error.call_args_list)
    assert "typo" in out and "other" in out


def test_startup_exits_when_include_and_exclude_cancel_out(main_module, monkeypatch):
    env = {
        "CONSERVER_INGRESS_INCLUDE": "default",
        "CONSERVER_INGRESS_EXCLUDE": "default",
    }
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, env)
    assert exc.value.code != 0


def test_any_unknown_include_exits(main_module, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_INCLUDE": "default,typo"})
    assert exc.value.code != 0
    assert "typo" in " ".join(str(c) for c in main_module.logger.error.call_args_list)


def test_unknown_exclude_exits(main_module, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_EXCLUDE": "defualt"})
    assert exc.value.code != 0
    assert "defualt" in " ".join(str(c) for c in main_module.logger.error.call_args_list)


def test_partially_unknown_exclude_exits(main_module, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_EXCLUDE": "default,typo"})
    assert exc.value.code != 0


def test_all_unknown_exclude_exits(main_module, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_EXCLUDE": "typo,other"})
    assert exc.value.code != 0
    out = " ".join(str(c) for c in main_module.logger.error.call_args_list)
    assert "typo" in out and "other" in out


def test_startup_logs_parsed_sets_and_served_lists(main_module, monkeypatch):
    _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_EXCLUDE": " default , "})
    out = " ".join(str(c) for c in main_module.logger.info.call_args_list)
    assert "'<all>', ['default'], ['transcribe', 'chain_a', 'chain_b']" in out


def test_require_filter_without_filter_exits(main_module, monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {"CONSERVER_INGRESS_REQUIRE_FILTER": "1"})
    assert exc.value.code != 0


@pytest.mark.parametrize("flag", ["1", "true"])
def test_require_filter_with_valid_filter_starts(main_module, monkeypatch, flag):
    env = {
        "CONSERVER_INGRESS_REQUIRE_FILTER": flag,
        "CONSERVER_INGRESS_INCLUDE": "default",
    }
    assert _startup(main_module, monkeypatch, env) == ["default"]


def test_no_filter_without_require_filter_serves_everything(main_module, monkeypatch):
    assert _startup(main_module, monkeypatch) == LISTS


def _run_main(main_module, monkeypatch, env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    _reload_config()
    reload(main_module)
    with patch("main.init_tracing"), \
         patch("main.get_config", return_value=_chains(LISTS)), \
         patch("main.get_worker_count", return_value=1), \
         patch("main.worker_loop") as worker_loop, \
         patch("main.follower.start_followers") as start_followers:
        main_module.main()
    return start_followers, worker_loop


def test_followers_start_by_default(main_module, monkeypatch):
    start_followers, worker_loop = _run_main(main_module, monkeypatch, {})
    start_followers.assert_called_once()
    worker_loop.assert_called_once()


@pytest.mark.parametrize("value", ["false", "0"])
def test_followers_disabled_does_not_start_followers(main_module, monkeypatch, value):
    start_followers, worker_loop = _run_main(
        main_module, monkeypatch, {"CONSERVER_FOLLOWERS_ENABLED": value}
    )
    start_followers.assert_not_called()
    worker_loop.assert_called_once()


# Strict boolean parsing

BOOL_VARS = {
    "CONSERVER_INGRESS_REQUIRE_FILTER": ("CONSERVER_INGRESS_REQUIRE_FILTER", False),
    "CONSERVER_FOLLOWERS_ENABLED": ("CONSERVER_FOLLOWERS_ENABLED", True),
}


@pytest.mark.parametrize("name", list(BOOL_VARS))
def test_bool_defaults_when_unset(name):
    import settings
    reload(settings)
    assert getattr(settings, name) is BOOL_VARS[name][1]
    assert settings.CONSERVER_BOOL_ERRORS == []


@pytest.mark.parametrize("name", list(BOOL_VARS))
@pytest.mark.parametrize(
    "raw,expected",
    [("yes", True), ("on", True), ("1", True), ("TRUE", True), (" True ", True),
     ("no", False), ("off", False), ("0", False), ("FALSE", False)],
)
def test_bool_parses_accepted_values(monkeypatch, name, raw, expected):
    import settings
    monkeypatch.setenv(name, raw)
    reload(settings)
    assert getattr(settings, name) is expected
    assert settings.CONSERVER_BOOL_ERRORS == []


@pytest.mark.parametrize("name", list(BOOL_VARS))
@pytest.mark.parametrize("raw", ["", "enable", "2"])
def test_bool_invalid_value_exits_at_startup(main_module, monkeypatch, name, raw):
    with pytest.raises(SystemExit) as exc:
        _startup(main_module, monkeypatch, {name: raw})
    assert exc.value.code != 0
    assert name in " ".join(str(c) for c in main_module.logger.error.call_args_list)


@pytest.mark.parametrize("raw", ["", "enable", "2"])
def test_invalid_followers_flag_exits_before_followers_start(main_module, monkeypatch, raw):
    with pytest.raises(SystemExit) as exc:
        _run_main(main_module, monkeypatch, {"CONSERVER_FOLLOWERS_ENABLED": raw})
    assert exc.value.code != 0
