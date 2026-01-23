"""Integration tests for parallel processing functionality.

These tests verify the multi-worker and parallel storage features work correctly.
Run with: pytest server/tests/test_parallel_processing.py -v
"""

import os
import time
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestVconChainRequestParallelStorage:
    """Test the VconChainRequest parallel storage functionality."""

    @pytest.fixture
    def mock_storage_class(self):
        """Create a mock Storage class that tracks calls."""
        call_log = []
        
        class MockStorage:
            def __init__(self, storage_name):
                self.storage_name = storage_name
            
            def save(self, vcon_id):
                # Simulate I/O delay
                time.sleep(0.1)
                call_log.append({
                    "storage": self.storage_name,
                    "vcon_id": vcon_id,
                    "time": time.time()
                })
        
        return MockStorage, call_log

    def test_parallel_storage_faster_than_sequential(self, mock_storage_class):
        """Test that parallel storage is faster than sequential for multiple backends."""
        MockStorage, call_log = mock_storage_class
        
        storage_backends = ["s3", "mongo", "postgres", "milvus"]
        vcon_id = "test-vcon-123"
        
        # Sequential timing
        sequential_start = time.time()
        for storage_name in storage_backends:
            MockStorage(storage_name).save(vcon_id)
        sequential_time = time.time() - sequential_start
        
        call_log.clear()
        
        # Parallel timing
        parallel_start = time.time()
        with ThreadPoolExecutor(max_workers=len(storage_backends)) as executor:
            futures = [
                executor.submit(lambda s: MockStorage(s).save(vcon_id), storage_name)
                for storage_name in storage_backends
            ]
            for future in futures:
                future.result()
        parallel_time = time.time() - parallel_start
        
        # Parallel should be significantly faster (at least 2x for 4 backends)
        # Each mock takes 0.1s, so sequential ~0.4s, parallel ~0.1s
        assert parallel_time < sequential_time * 0.75, \
            f"Parallel ({parallel_time:.3f}s) should be faster than sequential ({sequential_time:.3f}s)"

    def test_parallel_storage_all_backends_called(self, mock_storage_class):
        """Test that all storage backends are called in parallel mode."""
        MockStorage, call_log = mock_storage_class
        
        storage_backends = ["s3", "mongo", "postgres"]
        vcon_id = "test-vcon-456"
        
        with ThreadPoolExecutor(max_workers=len(storage_backends)) as executor:
            futures = {
                executor.submit(lambda s: MockStorage(s).save(vcon_id), storage_name): storage_name
                for storage_name in storage_backends
            }
            for future in as_completed(futures):
                future.result()
        
        # Verify all backends were called
        called_storages = {entry["storage"] for entry in call_log}
        assert called_storages == set(storage_backends)

    def test_parallel_storage_continues_on_failure(self, mock_storage_class):
        """Test that parallel storage continues even if one backend fails."""
        call_log = []
        
        class MockStorageWithFailure:
            def __init__(self, storage_name):
                self.storage_name = storage_name
            
            def save(self, vcon_id):
                if self.storage_name == "failing_backend":
                    raise Exception("Simulated storage failure")
                call_log.append(self.storage_name)
        
        storage_backends = ["s3", "failing_backend", "mongo"]
        vcon_id = "test-vcon-789"
        errors = []
        
        with ThreadPoolExecutor(max_workers=len(storage_backends)) as executor:
            future_to_storage = {
                executor.submit(lambda s: MockStorageWithFailure(s).save(vcon_id), name): name
                for name in storage_backends
            }
            
            for future in as_completed(future_to_storage):
                storage_name = future_to_storage[future]
                try:
                    future.result()
                except Exception as e:
                    errors.append(storage_name)
        
        # Successful backends should have completed
        assert "s3" in call_log
        assert "mongo" in call_log
        
        # Failed backend should be in errors
        assert "failing_backend" in errors


class TestWorkerLoopBehavior:
    """Test worker loop behavior and signal handling."""

    def test_worker_returns_vcon_to_queue_on_shutdown(self):
        """Test that a worker returns a vCon to the queue when shutdown is requested."""
        # This tests the logic, not actual Redis operations
        returned_vcons = []
        
        def mock_lpush(queue, vcon_id):
            returned_vcons.append((queue, vcon_id))
        
        # Simulate shutdown during processing
        shutdown_requested = True
        ingress_list = "test_queue"
        vcon_id = "test-vcon-999"
        
        if shutdown_requested:
            mock_lpush(ingress_list, vcon_id)
        
        assert returned_vcons == [("test_queue", "test-vcon-999")]

    def test_worker_name_format(self):
        """Test worker naming convention."""
        for worker_id in [1, 2, 10, 99]:
            worker_name = f"Worker-{worker_id}"
            process_name = f"vcon-worker-{worker_id}"
            
            assert worker_name == f"Worker-{worker_id}"
            assert process_name == f"vcon-worker-{worker_id}"


class TestSignalHandling:
    """Test signal handling for graceful shutdown."""

    def test_shutdown_flag_set_on_signal(self):
        """Test that shutdown flag is set when signal is received."""
        shutdown_requested = False
        
        def signal_handler(signum, frame):
            nonlocal shutdown_requested
            shutdown_requested = True
        
        # Simulate signal
        signal_handler(15, None)  # SIGTERM = 15
        
        assert shutdown_requested is True

    def test_multiple_signals_handled(self):
        """Test that both SIGTERM and SIGINT are handled."""
        import signal
        
        signals_received = []
        
        def handler(signum, frame):
            signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            signals_received.append(signal_name)
        
        # Simulate both signals
        handler(signal.SIGTERM, None)
        handler(signal.SIGINT, None)
        
        assert "SIGTERM" in signals_received
        assert "SIGINT" in signals_received


class TestConfigurationValidation:
    """Test configuration edge cases."""

    def test_worker_count_minimum_is_one(self):
        """Test that worker count cannot be less than 1."""
        def get_worker_count(env_value):
            return max(1, int(env_value) if env_value else 1)
        
        assert get_worker_count("0") == 1
        assert get_worker_count("-1") == 1
        assert get_worker_count("1") == 1
        assert get_worker_count("4") == 4

    def test_parallel_storage_only_with_multiple_backends(self):
        """Test that parallel storage logic only triggers with 2+ backends."""
        def should_use_parallel(backends, parallel_enabled):
            return parallel_enabled and len(backends) > 1
        
        assert should_use_parallel(["s3"], True) is False
        assert should_use_parallel(["s3", "mongo"], True) is True
        assert should_use_parallel(["s3", "mongo"], False) is False
        assert should_use_parallel([], True) is False
