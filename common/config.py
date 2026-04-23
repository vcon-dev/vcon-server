"""vCon server configuration loader.

Config is a single YAML file pointed at by `settings.CONSERVER_CONFIG_FILE`.
`get_config()` is called on every worker-loop iteration (see
`conserver/main.py::worker_loop`), so we cache the parsed dict by the file's
mtime+size to avoid re-parsing on every call. Use `reload_config()` to force
a reload (e.g. in response to SIGHUP or in tests).
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import settings
import yaml

_config: Optional[dict] = None
_config_cache_key: Optional[Tuple[str, int, int]] = None


def _cache_key(path: str) -> Optional[Tuple[str, int, int]]:
    """Return (path, mtime_ns, size) for the config file, or None if unreadable."""
    try:
        st = os.stat(path)
        return (path, st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def reload_config() -> dict:
    """Force-reload the configuration from disk, bypassing the cache.

    Call this on SIGHUP or from tests that need to observe a config change.
    """
    global _config, _config_cache_key
    _config = None
    _config_cache_key = None
    return get_config()


def get_config() -> dict:
    """Return the parsed vCon server config (cached by file mtime+size).

    Subsequent calls return the cached dict unless the config file has changed
    on disk. If the file is unreadable (e.g. during a unit test that mocks
    `open`), the cache is bypassed and the file is re-read every call — this
    preserves the pre-cache behavior for tests that swap the config mid-run.
    """
    global _config, _config_cache_key

    path = settings.CONSERVER_CONFIG_FILE
    key = _cache_key(path)

    if _config is not None and key is not None and key == _config_cache_key:
        return _config

    with open(path) as file:
        _config = yaml.safe_load(file) or {}
    _config_cache_key = key
    return _config


def get_worker_count() -> int:
    """Get the number of worker processes to spawn.

    Returns:
        int: Number of workers (minimum 1)
    """
    return max(1, settings.CONSERVER_WORKERS)


def is_parallel_storage_enabled() -> bool:
    """Check if parallel storage writes are enabled.

    Returns:
        bool: True if parallel storage is enabled
    """
    return settings.CONSERVER_PARALLEL_STORAGE


def get_start_method() -> str | None:
    """Get the multiprocessing start method.

    Returns:
        str | None: "fork", "spawn", "forkserver", or None for platform default
    """
    method = settings.CONSERVER_START_METHOD
    if method and method not in ("fork", "spawn", "forkserver"):
        raise ValueError(
            f"Invalid CONSERVER_START_METHOD: {method}. "
            "Must be 'fork', 'spawn', 'forkserver', or empty for default."
        )
    return method


class Configuration:
    @classmethod
    def get_config(cls) -> dict:
        return get_config()

    @classmethod
    def get_storages(cls) -> dict:
        config = cls.get_config()
        return config.get("storages", {})

    @classmethod
    def get_followers(cls) -> dict:
        config = cls.get_config()
        return config.get("followers", {})

    @classmethod
    def get_imports(cls) -> dict:
        config = cls.get_config()
        return config.get("imports", {})

    @classmethod
    def get_ingress_auth(cls) -> dict:
        """Get ingress-specific API key configuration.

        Returns:
            dict: Dictionary mapping ingress list names to their API keys.
                  Values can be either a single string (one API key) or
                  a list of strings (multiple API keys for the same ingress list).
        """
        config = cls.get_config()
        return config.get("ingress_auth", {})
