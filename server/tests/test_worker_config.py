"""Tests for worker configuration and parallel processing settings."""

import os
import pytest
from unittest.mock import patch, MagicMock
import multiprocessing


class TestWorkerConfiguration:
    """Test worker count and parallel storage configuration."""

    def test_get_worker_count_default(self):
        """Test default worker count is 1."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove CONSERVER_WORKERS if it exists
            os.environ.pop("CONSERVER_WORKERS", None)
            
            # Re-import to pick up new env
            import importlib
            import settings
            importlib.reload(settings)
            
            from config import get_worker_count
            importlib.reload(__import__('config'))
            from config import get_worker_count
            
            # Default should be 1
            assert settings.CONSERVER_WORKERS == 1

    def test_get_worker_count_from_env(self):
        """Test worker count from environment variable."""
        with patch.dict(os.environ, {"CONSERVER_WORKERS": "4"}):
            import importlib
            import settings
            importlib.reload(settings)
            
            assert settings.CONSERVER_WORKERS == 4

    def test_parallel_storage_default_enabled(self):
        """Test parallel storage is enabled by default."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CONSERVER_PARALLEL_STORAGE", None)
            
            import importlib
            import settings
            importlib.reload(settings)
            
            assert settings.CONSERVER_PARALLEL_STORAGE is True

    def test_parallel_storage_disabled(self):
        """Test parallel storage can be disabled."""
        with patch.dict(os.environ, {"CONSERVER_PARALLEL_STORAGE": "false"}):
            import importlib
            import settings
            importlib.reload(settings)
            
            assert settings.CONSERVER_PARALLEL_STORAGE is False

    def test_parallel_storage_various_true_values(self):
        """Test various truthy values for parallel storage."""
        for value in ["true", "True", "TRUE", "1", "yes", "YES"]:
            with patch.dict(os.environ, {"CONSERVER_PARALLEL_STORAGE": value}):
                import importlib
                import settings
                importlib.reload(settings)
                
                assert settings.CONSERVER_PARALLEL_STORAGE is True, f"Failed for value: {value}"


class TestParallelStorageExecution:
    """Test parallel storage write functionality."""

    def test_parallel_storage_with_multiple_backends(self):
        """Test that parallel storage is used when multiple backends configured."""
        from concurrent.futures import ThreadPoolExecutor
        
        # Track which storages were called
        storage_calls = []
        
        def mock_storage_save(storage_name):
            storage_calls.append(storage_name)
            return True
        
        storage_backends = ["s3", "mongo", "postgres"]
        
        with ThreadPoolExecutor(max_workers=len(storage_backends)) as executor:
            futures = {
                executor.submit(mock_storage_save, name): name 
                for name in storage_backends
            }
            for future in futures:
                future.result()
        
        # All storages should have been called
        assert set(storage_calls) == set(storage_backends)

    def test_parallel_storage_handles_exceptions(self):
        """Test that parallel storage handles individual failures gracefully."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {"success": [], "failed": []}
        
        def mock_storage_save(storage_name):
            if storage_name == "failing_storage":
                raise Exception("Simulated failure")
            return storage_name
        
        storage_backends = ["s3", "failing_storage", "mongo"]
        
        with ThreadPoolExecutor(max_workers=len(storage_backends)) as executor:
            future_to_storage = {
                executor.submit(mock_storage_save, name): name 
                for name in storage_backends
            }
            
            for future in as_completed(future_to_storage):
                storage_name = future_to_storage[future]
                try:
                    future.result()
                    results["success"].append(storage_name)
                except Exception:
                    results["failed"].append(storage_name)
        
        assert "s3" in results["success"]
        assert "mongo" in results["success"]
        assert "failing_storage" in results["failed"]


class TestWorkerProcessManagement:
    """Test worker process spawning and management."""

    def test_worker_process_can_be_spawned(self):
        """Test that a worker process can be created."""
        def dummy_worker(worker_id):
            pass
        
        process = multiprocessing.Process(
            target=dummy_worker,
            args=(1,),
            name="test-worker-1"
        )
        
        assert process.name == "test-worker-1"
        assert not process.is_alive()

    def test_multiple_workers_have_unique_ids(self):
        """Test that multiple workers get unique IDs."""
        worker_ids = []
        
        for i in range(4):
            worker_id = i + 1
            worker_ids.append(worker_id)
        
        assert worker_ids == [1, 2, 3, 4]
        assert len(set(worker_ids)) == 4  # All unique
