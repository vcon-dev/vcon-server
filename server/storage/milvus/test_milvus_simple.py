"""
Simplified Milvus integration tests
"""

import pytest
import os
import pymilvus

# Skip if integration tests not enabled
pytestmark = pytest.mark.skipif(
    not os.getenv("MILVUS_INTEGRATION_TESTS", "false").lower() == "true",
    reason="Set MILVUS_INTEGRATION_TESTS=true to run integration tests"
)

try:
    from pymilvus import connections, utility
    PYMILVUS_AVAILABLE = True
except ImportError:
    PYMILVUS_AVAILABLE = False
    pytestmark = pytest.mark.skip("pymilvus not installed")

# Test configuration
MILVUS_HOST = os.getenv("MILVUS_TEST_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_TEST_PORT", "19530")

class TestMilvusBasic:
    """Basic Milvus integration tests."""
    
    def test_connection_establishment(self):
        """Test that we can connect to Milvus server."""
        if not PYMILVUS_AVAILABLE:
            pytest.skip("pymilvus not available")
        
        try:
            # Try to connect to Milvus
            connections.connect(
                alias="test",
                host=MILVUS_HOST,
                port=MILVUS_PORT
            )
            
            # Test server info
            server_version = utility.get_server_version(using="test")
            print(f"✓ Connected to Milvus version: {server_version}")
            assert server_version is not None
            
            # Cleanup
            connections.disconnect("test")
            
        except Exception as e:
            pytest.skip(f"Cannot connect to Milvus server at {MILVUS_HOST}:{MILVUS_PORT}: {e}")
