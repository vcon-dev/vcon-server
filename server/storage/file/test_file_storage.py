"""
Tests for the file storage module.

Tests cover:
- Basic CRUD operations (save, get, delete)
- Compression support
- Date-based organization
- File size limits
- Edge cases and error handling
"""

import pytest
import json
import gzip
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from server.storage.file import (
    save,
    get,
    delete,
    exists,
    list_vcons,
    default_options,
    _get_file_path,
    _find_vcon_file,
    _cleanup_empty_dirs,
)
from server.vcon import Vcon


@pytest.fixture
def temp_storage_dir():
    """Create a temporary directory for file storage tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_vcon():
    """Create a sample vCon for testing."""
    vcon = Vcon.build_new()
    vcon.add_party({"name": "Test User", "role": "agent"})
    vcon.add_dialog({"type": "text", "body": "Hello, world!"})
    return vcon


@pytest.fixture
def mock_vcon_redis(sample_vcon):
    """Mock VconRedis to return sample vCon."""
    with patch("server.storage.file.VconRedis") as MockVconRedis:
        mock_redis = MagicMock()
        mock_redis.get_vcon.return_value = sample_vcon
        MockVconRedis.return_value = mock_redis
        yield MockVconRedis


class TestGetFilePath:
    """Tests for _get_file_path helper function."""

    def test_flat_structure_no_date(self, temp_storage_dir):
        """Test file path without date organization."""
        opts = {"path": temp_storage_dir, "organize_by_date": False, "compression": False}
        path = _get_file_path("test-uuid", opts)
        assert path == Path(temp_storage_dir) / "test-uuid.json"

    def test_flat_structure_with_compression(self, temp_storage_dir):
        """Test file path with compression enabled."""
        opts = {"path": temp_storage_dir, "organize_by_date": False, "compression": True}
        path = _get_file_path("test-uuid", opts)
        assert path == Path(temp_storage_dir) / "test-uuid.json.gz"

    def test_date_organized_structure(self, temp_storage_dir):
        """Test file path with date organization."""
        opts = {"path": temp_storage_dir, "organize_by_date": True, "compression": False}
        created_at = "2024-03-15T10:30:00+00:00"
        path = _get_file_path("test-uuid", opts, created_at)
        assert path == Path(temp_storage_dir) / "2024/03/15" / "test-uuid.json"

    def test_date_organized_with_z_suffix(self, temp_storage_dir):
        """Test file path with Z suffix in timestamp."""
        opts = {"path": temp_storage_dir, "organize_by_date": True, "compression": False}
        created_at = "2024-03-15T10:30:00Z"
        path = _get_file_path("test-uuid", opts, created_at)
        assert path == Path(temp_storage_dir) / "2024/03/15" / "test-uuid.json"

    def test_invalid_date_falls_back_to_flat(self, temp_storage_dir):
        """Test that invalid date falls back to flat structure."""
        opts = {"path": temp_storage_dir, "organize_by_date": True, "compression": False}
        path = _get_file_path("test-uuid", opts, "invalid-date")
        assert path == Path(temp_storage_dir) / "test-uuid.json"


class TestSave:
    """Tests for save function."""

    def test_save_basic(self, temp_storage_dir, mock_vcon_redis, sample_vcon):
        """Test basic save operation."""
        opts = {
            "path": temp_storage_dir,
            "organize_by_date": False,
            "compression": False,
            "max_file_size": 10485760,
            "file_permissions": 0o644,
            "dir_permissions": 0o755,
        }

        save(sample_vcon.uuid, opts)

        expected_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json"
        assert expected_path.exists()

        with open(expected_path) as f:
            saved_data = json.load(f)
        assert saved_data["uuid"] == sample_vcon.uuid

    def test_save_with_compression(self, temp_storage_dir, mock_vcon_redis, sample_vcon):
        """Test save with gzip compression."""
        opts = {
            "path": temp_storage_dir,
            "organize_by_date": False,
            "compression": True,
            "max_file_size": 10485760,
            "file_permissions": 0o644,
            "dir_permissions": 0o755,
        }

        save(sample_vcon.uuid, opts)

        expected_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json.gz"
        assert expected_path.exists()

        with gzip.open(expected_path, "rt") as f:
            saved_data = json.load(f)
        assert saved_data["uuid"] == sample_vcon.uuid

    def test_save_with_date_organization(self, temp_storage_dir, mock_vcon_redis, sample_vcon):
        """Test save with date-based directory structure."""
        opts = {
            "path": temp_storage_dir,
            "organize_by_date": True,
            "compression": False,
            "max_file_size": 10485760,
            "file_permissions": 0o644,
            "dir_permissions": 0o755,
        }

        save(sample_vcon.uuid, opts)

        # Should create date-based directory structure
        base_path = Path(temp_storage_dir)
        json_files = list(base_path.rglob("*.json"))
        assert len(json_files) == 1
        assert sample_vcon.uuid in str(json_files[0])

    def test_save_exceeds_max_size(self, temp_storage_dir, mock_vcon_redis, sample_vcon):
        """Test that save fails when file exceeds max size."""
        opts = {
            "path": temp_storage_dir,
            "organize_by_date": False,
            "compression": False,
            "max_file_size": 10,  # Very small limit
            "file_permissions": 0o644,
            "dir_permissions": 0o755,
        }

        with pytest.raises(ValueError, match="exceeds max file size"):
            save(sample_vcon.uuid, opts)

    def test_save_creates_directories(self, temp_storage_dir, mock_vcon_redis, sample_vcon):
        """Test that save creates necessary directories."""
        nested_path = os.path.join(temp_storage_dir, "nested", "deep", "path")
        opts = {
            "path": nested_path,
            "organize_by_date": False,
            "compression": False,
            "max_file_size": 10485760,
            "file_permissions": 0o644,
            "dir_permissions": 0o755,
        }

        save(sample_vcon.uuid, opts)

        expected_path = Path(nested_path) / f"{sample_vcon.uuid}.json"
        assert expected_path.exists()


class TestGet:
    """Tests for get function."""

    def test_get_basic(self, temp_storage_dir, sample_vcon):
        """Test basic get operation."""
        opts = {"path": temp_storage_dir, "compression": False}

        # Create a test file
        file_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json"
        with open(file_path, "w") as f:
            f.write(sample_vcon.dumps())

        result = get(sample_vcon.uuid, opts)
        assert result is not None
        assert result["uuid"] == sample_vcon.uuid

    def test_get_compressed(self, temp_storage_dir, sample_vcon):
        """Test get with compressed file."""
        opts = {"path": temp_storage_dir, "compression": True}

        # Create a compressed test file
        file_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json.gz"
        with gzip.open(file_path, "wt") as f:
            f.write(sample_vcon.dumps())

        result = get(sample_vcon.uuid, opts)
        assert result is not None
        assert result["uuid"] == sample_vcon.uuid

    def test_get_from_date_directory(self, temp_storage_dir, sample_vcon):
        """Test get from date-organized directory."""
        opts = {"path": temp_storage_dir, "compression": False}

        # Create a date-organized test file
        date_path = Path(temp_storage_dir) / "2024" / "03" / "15"
        date_path.mkdir(parents=True)
        file_path = date_path / f"{sample_vcon.uuid}.json"
        with open(file_path, "w") as f:
            f.write(sample_vcon.dumps())

        result = get(sample_vcon.uuid, opts)
        assert result is not None
        assert result["uuid"] == sample_vcon.uuid

    def test_get_not_found(self, temp_storage_dir):
        """Test get returns None for non-existent file."""
        opts = {"path": temp_storage_dir, "compression": False}
        result = get("nonexistent-uuid", opts)
        assert result is None

    def test_get_prefers_uncompressed_when_both_exist(self, temp_storage_dir, sample_vcon):
        """Test that get prefers uncompressed file when both exist."""
        opts = {"path": temp_storage_dir, "compression": False}

        # Create both compressed and uncompressed files with different content
        uncompressed_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json"
        compressed_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json.gz"

        with open(uncompressed_path, "w") as f:
            json.dump({"uuid": sample_vcon.uuid, "marker": "uncompressed"}, f)

        with gzip.open(compressed_path, "wt") as f:
            json.dump({"uuid": sample_vcon.uuid, "marker": "compressed"}, f)

        result = get(sample_vcon.uuid, opts)
        assert result["marker"] == "uncompressed"


class TestDelete:
    """Tests for delete function."""

    def test_delete_basic(self, temp_storage_dir, sample_vcon):
        """Test basic delete operation."""
        opts = {"path": temp_storage_dir, "compression": False}

        # Create a test file
        file_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json"
        file_path.write_text(sample_vcon.dumps())
        assert file_path.exists()

        result = delete(sample_vcon.uuid, opts)
        assert result is True
        assert not file_path.exists()

    def test_delete_compressed(self, temp_storage_dir, sample_vcon):
        """Test delete with compressed file."""
        opts = {"path": temp_storage_dir, "compression": True}

        # Create a compressed test file
        file_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json.gz"
        with gzip.open(file_path, "wt") as f:
            f.write(sample_vcon.dumps())
        assert file_path.exists()

        result = delete(sample_vcon.uuid, opts)
        assert result is True
        assert not file_path.exists()

    def test_delete_not_found(self, temp_storage_dir):
        """Test delete returns False for non-existent file."""
        opts = {"path": temp_storage_dir, "compression": False}
        result = delete("nonexistent-uuid", opts)
        assert result is False

    def test_delete_cleans_empty_directories(self, temp_storage_dir, sample_vcon):
        """Test that delete cleans up empty parent directories."""
        opts = {"path": temp_storage_dir, "compression": False}

        # Create a date-organized test file
        date_path = Path(temp_storage_dir) / "2024" / "03" / "15"
        date_path.mkdir(parents=True)
        file_path = date_path / f"{sample_vcon.uuid}.json"
        file_path.write_text(sample_vcon.dumps())

        result = delete(sample_vcon.uuid, opts)
        assert result is True

        # Empty date directories should be cleaned up
        assert not (Path(temp_storage_dir) / "2024" / "03" / "15").exists()
        assert not (Path(temp_storage_dir) / "2024" / "03").exists()
        assert not (Path(temp_storage_dir) / "2024").exists()


class TestExists:
    """Tests for exists function."""

    def test_exists_true(self, temp_storage_dir, sample_vcon):
        """Test exists returns True for existing file."""
        opts = {"path": temp_storage_dir, "compression": False}

        # Create a test file
        file_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json"
        file_path.write_text(sample_vcon.dumps())

        assert exists(sample_vcon.uuid, opts) is True

    def test_exists_false(self, temp_storage_dir):
        """Test exists returns False for non-existent file."""
        opts = {"path": temp_storage_dir, "compression": False}
        assert exists("nonexistent-uuid", opts) is False


class TestListVcons:
    """Tests for list_vcons function."""

    def test_list_vcons_empty(self, temp_storage_dir):
        """Test list_vcons returns empty list for empty directory."""
        opts = {"path": temp_storage_dir}
        result = list_vcons(opts)
        assert result == []

    def test_list_vcons_basic(self, temp_storage_dir):
        """Test list_vcons returns all UUIDs."""
        opts = {"path": temp_storage_dir}

        # Create some test files
        uuids = ["uuid-1", "uuid-2", "uuid-3"]
        for uuid in uuids:
            (Path(temp_storage_dir) / f"{uuid}.json").write_text("{}")

        result = list_vcons(opts)
        assert len(result) == 3
        assert set(result) == set(uuids)

    def test_list_vcons_with_pagination(self, temp_storage_dir):
        """Test list_vcons respects limit and offset."""
        opts = {"path": temp_storage_dir}

        # Create test files
        for i in range(5):
            (Path(temp_storage_dir) / f"uuid-{i}.json").write_text("{}")
            # Ensure different modification times
            import time
            time.sleep(0.01)

        result = list_vcons(opts, limit=2, offset=1)
        assert len(result) == 2

    def test_list_vcons_includes_compressed(self, temp_storage_dir):
        """Test list_vcons includes compressed files."""
        opts = {"path": temp_storage_dir}

        # Create both compressed and uncompressed files
        (Path(temp_storage_dir) / "uuid-1.json").write_text("{}")
        with gzip.open(Path(temp_storage_dir) / "uuid-2.json.gz", "wt") as f:
            f.write("{}")

        result = list_vcons(opts)
        assert len(result) == 2
        assert "uuid-1" in result
        assert "uuid-2" in result

    def test_list_vcons_from_nested_dirs(self, temp_storage_dir):
        """Test list_vcons finds files in nested directories."""
        opts = {"path": temp_storage_dir}

        # Create files in nested directories
        nested = Path(temp_storage_dir) / "2024" / "03" / "15"
        nested.mkdir(parents=True)
        (nested / "uuid-nested.json").write_text("{}")
        (Path(temp_storage_dir) / "uuid-flat.json").write_text("{}")

        result = list_vcons(opts)
        assert len(result) == 2
        assert "uuid-nested" in result
        assert "uuid-flat" in result


class TestCleanupEmptyDirs:
    """Tests for _cleanup_empty_dirs helper function."""

    def test_cleanup_removes_empty_dirs(self, temp_storage_dir):
        """Test that empty directories are removed."""
        base_path = Path(temp_storage_dir)
        nested_path = base_path / "a" / "b" / "c"
        nested_path.mkdir(parents=True)

        _cleanup_empty_dirs(nested_path, base_path)

        assert not (base_path / "a" / "b" / "c").exists()
        assert not (base_path / "a" / "b").exists()
        assert not (base_path / "a").exists()

    def test_cleanup_stops_at_non_empty_dir(self, temp_storage_dir):
        """Test that cleanup stops at non-empty directories."""
        base_path = Path(temp_storage_dir)
        nested_path = base_path / "a" / "b" / "c"
        nested_path.mkdir(parents=True)

        # Add a file to middle directory
        (base_path / "a" / "b" / "other.txt").write_text("content")

        _cleanup_empty_dirs(nested_path, base_path)

        assert not (base_path / "a" / "b" / "c").exists()
        assert (base_path / "a" / "b").exists()

    def test_cleanup_stops_at_base_path(self, temp_storage_dir):
        """Test that cleanup doesn't remove the base path."""
        base_path = Path(temp_storage_dir)

        _cleanup_empty_dirs(base_path, base_path)

        assert base_path.exists()


class TestFindVconFile:
    """Tests for _find_vcon_file helper function."""

    def test_find_in_flat_structure(self, temp_storage_dir, sample_vcon):
        """Test finding file in flat structure."""
        opts = {"path": temp_storage_dir, "compression": False}

        file_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json"
        file_path.write_text(sample_vcon.dumps())

        result = _find_vcon_file(sample_vcon.uuid, opts)
        assert result == file_path

    def test_find_in_nested_structure(self, temp_storage_dir, sample_vcon):
        """Test finding file in nested directory."""
        opts = {"path": temp_storage_dir, "compression": False}

        nested = Path(temp_storage_dir) / "2024" / "01" / "01"
        nested.mkdir(parents=True)
        file_path = nested / f"{sample_vcon.uuid}.json"
        file_path.write_text(sample_vcon.dumps())

        result = _find_vcon_file(sample_vcon.uuid, opts)
        assert result == file_path

    def test_find_compressed_file(self, temp_storage_dir, sample_vcon):
        """Test finding compressed file."""
        opts = {"path": temp_storage_dir, "compression": True}

        file_path = Path(temp_storage_dir) / f"{sample_vcon.uuid}.json.gz"
        with gzip.open(file_path, "wt") as f:
            f.write(sample_vcon.dumps())

        result = _find_vcon_file(sample_vcon.uuid, opts)
        assert result == file_path

    def test_find_not_found(self, temp_storage_dir):
        """Test that None is returned when file not found."""
        opts = {"path": temp_storage_dir, "compression": False}
        result = _find_vcon_file("nonexistent-uuid", opts)
        assert result is None


class TestDefaultOptions:
    """Tests for default options."""

    def test_default_options_structure(self):
        """Test that default options have required keys."""
        assert "path" in default_options
        assert "organize_by_date" in default_options
        assert "compression" in default_options
        assert "max_file_size" in default_options
        assert "file_permissions" in default_options
        assert "dir_permissions" in default_options

    def test_default_path(self):
        """Test default path value."""
        assert default_options["path"] == "/data/vcons"

    def test_default_max_file_size(self):
        """Test default max file size is 10MB."""
        assert default_options["max_file_size"] == 10485760
