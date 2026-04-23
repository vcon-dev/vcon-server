"""Tests for config-loader caching behavior (Refactor #1).

Verifies that get_config() opens the YAML file exactly once when the file
doesn't change, and re-reads it on mtime/size change or when reload_config()
is called explicitly. This is the evidence that config caching eliminates
the per-iteration YAML parse in conserver/main.py::worker_loop.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import config as config_module


@pytest.fixture(autouse=True)
def reset_config_cache():
    """Reset the module-level cache before and after each test in this file."""
    config_module._config = None
    config_module._config_cache_key = None
    yield
    config_module._config = None
    config_module._config_cache_key = None


@pytest.fixture
def yaml_config_file(tmp_path, monkeypatch):
    """Write a tiny real YAML file on disk and point settings at it."""
    cfg_path = tmp_path / "test_config.yml"
    cfg_path.write_text("chains:\n  c1:\n    ingress_lists: [q1]\n")
    import settings as _settings
    monkeypatch.setattr(_settings, "CONSERVER_CONFIG_FILE", str(cfg_path))
    return cfg_path


def test_get_config_opens_file_once_when_unchanged(yaml_config_file):
    """1000 calls to get_config() must hit open() exactly once."""
    real_open = open
    call_count = {"n": 0}

    def counting_open(path, *args, **kwargs):
        if str(path) == str(yaml_config_file):
            call_count["n"] += 1
        return real_open(path, *args, **kwargs)

    with patch("builtins.open", side_effect=counting_open):
        first = config_module.get_config()
        for _ in range(999):
            assert config_module.get_config() is first  # same cached object

    assert call_count["n"] == 1, (
        f"Expected 1 open() call across 1000 get_config() calls, got {call_count['n']}"
    )


def test_get_config_reloads_when_file_changes(yaml_config_file):
    """Mutating the file (mtime change) must invalidate the cache."""
    first = config_module.get_config()
    assert "chains" in first and "c1" in first["chains"]

    # Ensure the OS records a different mtime for the rewrite.
    time.sleep(0.02)
    new_mtime = os.stat(yaml_config_file).st_mtime_ns + 10_000_000
    yaml_config_file.write_text("chains:\n  c2:\n    ingress_lists: [q2]\n")
    os.utime(
        yaml_config_file,
        ns=(new_mtime, new_mtime),
    )

    second = config_module.get_config()
    assert "c2" in second["chains"], (
        f"Expected cache to invalidate on mtime change; got {second}"
    )
    assert second is not first


def test_reload_config_forces_reload(yaml_config_file):
    """reload_config() must always re-read from disk even if mtime unchanged."""
    first = config_module.get_config()

    # Rewrite content WITHOUT bumping mtime (utime-to-identical).
    mtime_before = os.stat(yaml_config_file).st_mtime_ns
    yaml_config_file.write_text("chains:\n  c3:\n    ingress_lists: [q3]\n")
    os.utime(yaml_config_file, ns=(mtime_before, mtime_before))

    second = config_module.reload_config()
    assert "c3" in second["chains"], (
        "reload_config() must re-read from disk regardless of mtime state"
    )
    assert second is not first


def test_mocked_open_bypasses_cache(yaml_config_file):
    """When open() is mocked (file unreadable by os.stat-matching path), the
    cache is skipped so tests that swap content mid-run keep working."""
    from unittest.mock import mock_open

    # Ensure no real file backing — point settings at a path that doesn't exist.
    import settings as _settings
    missing = Path(yaml_config_file).parent / "no_such_file.yml"
    with patch.object(_settings, "CONSERVER_CONFIG_FILE", str(missing)):
        with patch("builtins.open", mock_open(read_data="chains: {c4: {}}\n")):
            result = config_module.get_config()
    assert result == {"chains": {"c4": {}}}
