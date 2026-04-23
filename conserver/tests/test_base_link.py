"""Tests for BaseLink (Refactor #2) and a link-contract smoke check."""
from __future__ import annotations

import importlib
import inspect
from unittest.mock import MagicMock, patch

import pytest

from links.base import BaseLink, run_link


class _Counter(BaseLink):
    """Minimal BaseLink subclass that records what it received."""

    default_options = {"mode": "default", "count": 3}

    def execute(self, vcon_uuid: str):
        return {
            "vcon_uuid": vcon_uuid,
            "link_name": self.link_name,
            "opts": self.opts,
        }


def test_baselink_merges_opts_over_defaults():
    """Opts supplied by config should merge key-by-key with defaults."""
    link = _Counter("counter", opts={"mode": "custom"})
    assert link.opts == {"mode": "custom", "count": 3}


def test_baselink_no_opts_uses_defaults():
    """None opts (e.g. chain config with no options: block) → defaults only."""
    link = _Counter("counter", opts=None)
    assert link.opts == {"mode": "default", "count": 3}


def test_baselink_run_link_delegates_to_execute():
    """run_link() should instantiate and invoke execute()."""
    result = run_link(_Counter, "vcon-123", "my_counter", {"mode": "x"})
    assert result == {
        "vcon_uuid": "vcon-123",
        "link_name": "my_counter",
        "opts": {"mode": "x", "count": 3},
    }


def test_baselink_subclass_without_execute_cannot_instantiate():
    """BaseLink.execute is abstract."""

    class Bad(BaseLink):
        pass

    with pytest.raises(TypeError):
        Bad("bad", {})


def test_vcon_redis_property_resolves_from_subclass_module():
    """Tests that patch their own module's VconRedis should see their mock."""
    # Migrated link exposes VconRedis at module level for this purpose.
    with patch("links.tag.VconRedis") as mock_cls:
        mock_cls.return_value = MagicMock(name="mocked-redis")
        from links.tag import TagLink

        link = TagLink("tag_test", {"tags": ["x"]})
        assert link.vcon_redis is mock_cls.return_value


@pytest.mark.parametrize("module_path", ["links.tag", "links.jq_link"])
def test_migrated_links_expose_required_contract(module_path):
    """Each migrated link must export default_options (dict) and run() callable.

    Contract: chain processor invokes ``module.run(vcon_id, link_name, opts)``.
    """
    mod = importlib.import_module(module_path)
    assert hasattr(mod, "default_options"), f"{module_path} missing default_options"
    assert isinstance(mod.default_options, dict), (
        f"{module_path}.default_options must be a dict"
    )
    assert callable(getattr(mod, "run", None)), f"{module_path}.run() not callable"
    sig = inspect.signature(mod.run)
    assert list(sig.parameters)[:2] == ["vcon_uuid", "link_name"], (
        f"{module_path}.run() must accept (vcon_uuid, link_name, opts=None); "
        f"got {list(sig.parameters)}"
    )
