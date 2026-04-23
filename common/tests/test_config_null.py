"""Tests for get_config() handling of null/empty config files (CON-510)."""

from unittest.mock import patch, mock_open

import pytest

import config as config_module
from config import get_config


@pytest.fixture(autouse=True)
def _reset_config_cache():
    """Reset the module-level cache so each test observes a fresh load."""
    config_module._config = None
    config_module._config_cache_key = None
    yield
    config_module._config = None
    config_module._config_cache_key = None


class TestGetConfigNullHandling:
    """Test that get_config() returns {} when yaml.safe_load returns None."""

    def test_get_config_returns_empty_dict_when_yaml_is_null(self):
        """All-comment YAML makes yaml.safe_load return None; get_config must return {}."""
        # yaml.safe_load returns None for a file with only comments
        null_yaml = "# just a comment\n"
        with patch("builtins.open", mock_open(read_data=null_yaml)):
            result = get_config()

        assert result == {}, f"Expected {{}} but got {result!r}"

    def test_get_config_returns_empty_dict_when_file_is_empty(self):
        """Completely empty file also makes yaml.safe_load return None."""
        with patch("builtins.open", mock_open(read_data="")):
            result = get_config()

        assert result == {}, f"Expected {{}} but got {result!r}"

    def test_get_config_returns_dict_when_valid(self):
        """Normal config file should be returned as-is."""
        valid_yaml = "chains:\n  my_chain:\n    ingress_lists:\n      - my_queue\n"
        with patch("builtins.open", mock_open(read_data=valid_yaml)):
            result = get_config()

        assert result == {"chains": {"my_chain": {"ingress_lists": ["my_queue"]}}}


class TestGetIngressChainMapNullConfig:
    """Test that get_ingress_chain_map() does not crash when config is null."""

    def test_get_ingress_chain_map_logic_with_null_config(self):
        """Simulate get_ingress_chain_map() logic when config is {} (null yaml result).

        The real function does:
            chains = config.get("chains", {})
            for chain_name, chain_config in chains.items(): ...
        This must not crash when config is {}.
        """
        null_yaml = "# only comments\n"
        with patch("builtins.open", mock_open(read_data=null_yaml)):
            cfg = get_config()

        # Replicate get_ingress_chain_map logic
        chains = cfg.get("chains", {})
        ingress_details = {}
        for chain_name, chain_config in chains.items():
            for ingress_list in chain_config.get("ingress_lists", []):
                ingress_details[ingress_list] = {"name": chain_name, **chain_config}

        assert ingress_details == {}

    def test_worker_loop_does_not_crash_on_null_config(self):
        """Simulate the worker_loop config reload path with a null config."""
        # Verify that calling .get() on the result of get_config() doesn't raise
        null_yaml = "# nothing here\n"
        with patch("builtins.open", mock_open(read_data=null_yaml)):
            cfg = get_config()

        # This is exactly what get_ingress_chain_map() does — must not raise
        chains = cfg.get("chains", {})
        assert chains == {}
