"""
Shared fixtures for Milvus tests
"""
import pytest
import os
import time
import uuid
from unittest.mock import patch
from pymilvus import connections, utility, Collection

# Test configuration
MILVUS_HOST = os.getenv("MILVUS_TEST_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_TEST_PORT", "19530")
MILVUS_USER = os.getenv("MILVUS_TEST_USER", "")
MILVUS_PASSWORD = os.getenv("MILVUS_TEST_PASSWORD", "")
TEST_COLLECTION_PREFIX = "test_vcons_"


@pytest.fixture(scope="session")
def milvus_connection():
    """Setup connection to Milvus server for testing."""
    # Only create connection if integration tests are enabled
    if not os.getenv("MILVUS_INTEGRATION_TESTS", "false").lower() == "true":
        pytest.skip("Set MILVUS_INTEGRATION_TESTS=true to run integration tests")
    
    alias = f"test_connection_{int(time.time())}"
    
    try:
        # Connect to Milvus
        connections.connect(
            alias=alias,
            host=MILVUS_HOST,
            port=MILVUS_PORT,
            user=MILVUS_USER,
            password=MILVUS_PASSWORD
        )
        
        yield alias
        
    except Exception as e:
        pytest.skip(f"Cannot connect to Milvus server: {e}")
    finally:
        try:
            connections.disconnect(alias)
        except:
            pass


@pytest.fixture
def test_collection_name():
    """Generate unique collection name for each test."""
    return f"{TEST_COLLECTION_PREFIX}{uuid.uuid4().hex[:8]}"


@pytest.fixture
def clean_test_collections(milvus_connection):
    """Clean up any leftover test collections."""
    # Cleanup before test
    collections = utility.list_collections(using=milvus_connection)
    for collection_name in collections:
        if collection_name.startswith(TEST_COLLECTION_PREFIX):
            try:
                collection = Collection(collection_name, using=milvus_connection)
                collection.drop()
            except:
                pass  # Ignore errors during cleanup
    
    yield
    
    # Cleanup after test
    collections = utility.list_collections(using=milvus_connection)
    for collection_name in collections:
        if collection_name.startswith(TEST_COLLECTION_PREFIX):
            try:
                collection = Collection(collection_name, using=milvus_connection)
                collection.drop()
            except:
                pass  # Ignore errors during cleanup