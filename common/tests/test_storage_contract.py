"""Tests for the storage-backend contract check (Refactor #2)."""
from __future__ import annotations

import types

import pytest

from storage.base import _validate_storage_module


def _module(**attrs) -> types.ModuleType:
    m = types.ModuleType("fake_backend")
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


def test_valid_backend_passes():
    def save(vcon_uuid, opts):
        return None

    mod = _module(default_options={}, save=save)
    _validate_storage_module(mod, "fake")


def test_missing_default_options_raises():
    mod = _module(save=lambda u, o: None)
    with pytest.raises(TypeError, match="default_options"):
        _validate_storage_module(mod, "fake")


def test_non_dict_default_options_raises():
    mod = _module(default_options=[], save=lambda u, o: None)
    with pytest.raises(TypeError, match="must be a dict"):
        _validate_storage_module(mod, "fake")


def test_missing_save_raises():
    mod = _module(default_options={})
    with pytest.raises(TypeError, match="`save` is missing or not callable"):
        _validate_storage_module(mod, "fake")


def test_save_with_too_few_params_raises():
    def save(vcon_uuid):  # missing opts
        return None

    mod = _module(default_options={}, save=save)
    with pytest.raises(TypeError, match="at least 2 positional"):
        _validate_storage_module(mod, "fake")


def test_optional_delete_non_callable_raises():
    mod = _module(default_options={}, save=lambda u, o: None, delete=42)
    with pytest.raises(TypeError, match="`delete` exists but is not callable"):
        _validate_storage_module(mod, "fake")


@pytest.mark.parametrize(
    "module_name",
    [
        "storage.file",
        "storage.webhook",
        "storage.redis_storage",
    ],
)
def test_real_backends_satisfy_contract(module_name):
    """Smoke check: the backends we ship already satisfy the contract."""
    import importlib

    mod = importlib.import_module(module_name)
    _validate_storage_module(mod, module_name)
