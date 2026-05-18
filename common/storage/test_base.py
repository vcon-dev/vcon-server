from types import SimpleNamespace
from unittest.mock import Mock, patch

from storage import base as base_module
from storage.base import Storage


def test_storage_uses_default_options_and_calls_save():
    module = SimpleNamespace(default_options={"path": "/tmp"}, save=Mock(), get=Mock(), delete=Mock())

    with patch("storage.base.get_config", return_value={"storages": {"file": {"module": "storage.file"}}}), \
         patch("storage.base.importlib.import_module", return_value=module), \
         patch.object(base_module, "_imported_modules", {}):
        storage = Storage("file")
        storage.save("uuid-1")

    assert storage.options == {"path": "/tmp"}
    module.save.assert_called_once_with("uuid-1", {"path": "/tmp"})


def test_storage_uses_custom_options_and_returns_get_result():
    module = SimpleNamespace(default_options={"path": "/tmp"}, save=Mock(), get=Mock(return_value={"uuid": "u"}), delete=Mock())

    with patch(
        "storage.base.get_config",
        return_value={"storages": {"file": {"module": "storage.file", "options": {"path": "/custom"}}}},
    ), patch("storage.base.importlib.import_module", return_value=module), patch.object(base_module, "_imported_modules", {}):
        storage = Storage("file")
        result = storage.get("uuid-2")

    assert storage.options == {"path": "/custom"}
    assert result == {"uuid": "u"}
    module.get.assert_called_once_with("uuid-2", {"path": "/custom"})


def test_storage_get_and_delete_handle_missing_methods():
    module = SimpleNamespace(default_options={"path": "/tmp"}, save=Mock())

    with patch("storage.base.get_config", return_value={"storages": {"file": {"module": "storage.file"}}}), \
         patch("storage.base.importlib.import_module", return_value=module), \
         patch.object(base_module, "_imported_modules", {}):
        storage = Storage("file")

        assert storage.get("uuid-3") is None
        assert storage.delete("uuid-3") is False


def test_storage_reuses_cached_imported_module():
    module = SimpleNamespace(default_options={"path": "/tmp"}, save=Mock(), get=Mock(), delete=Mock())

    with patch("storage.base.get_config", return_value={"storages": {"file": {"module": "storage.file"}}}), \
         patch("storage.base.importlib.import_module", return_value=module) as mock_import, \
         patch.object(base_module, "_imported_modules", {}):
        first = Storage("file")
        second = Storage("file")

    assert first.module is second.module is module
    mock_import.assert_called_once_with("storage.file")
