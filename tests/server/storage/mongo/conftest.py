import pytest
import pymongo
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid
import os
import sys
import fakeredis
import json

# Ensure the root directory is in the path for imports
# This is only needed if pytest.ini doesn't have pythonpath set correctly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from vcon import Vcon

# Test configuration that can be imported by all tests
TEST_DB_CONFIG = {
    "name": "mongo", 
    "database": "test_conserver", 
    "collection": "test_vcons",
    "url": "mongodb://localhost:27017/"
}

# Example vCon data for testing
SAMPLE_VCON_DATA = {
    "uuid": "test-uuid-123",
    "version": "1.1.0",
    "created_at": "2023-01-01T12:00:00.000Z",
    "metadata": {
        "title": "Test vCon",
        "description": "A vCon for testing purposes"
    },
    "dialog": [
        {
            "start": "2023-01-01T12:01:00.000Z",
            "sender": {
                "name": "Test User"
            },
            "message": {
                "type": "text",
                "text": "Hello, this is a test message"
            }
        }
    ]
}

@pytest.fixture
def mock_mongo_client():
    """Mock pymongo.MongoClient with the necessary methods for testing"""
    with patch('pymongo.MongoClient') as mock_client:
        # Create nested mocks for the client's return values
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        # Configure the chain of returns
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        
        # Pass the client and collection for use in tests
        yield mock_client, mock_collection

@pytest.fixture
def sample_vcon():
    """Create a sample Vcon object for testing"""
    return Vcon(SAMPLE_VCON_DATA)

@pytest.fixture
def mock_vcon_redis():
    """Mock the VconRedis class"""
    with patch('server.lib.vcon_redis.VconRedis') as mock:
        redis_instance = MagicMock()
        mock.return_value = redis_instance
        yield redis_instance

@pytest.fixture
def mongo_sample_document():
    """Sample MongoDB document with datetime objects"""
    return {
        "_id": "test-uuid-123",
        "version": "1.1.0",
        "created_at": datetime(2023, 1, 1, 12, 0, 0),
        "metadata": {
            "title": "Test vCon",
            "description": "A vCon for testing purposes"
        },
        "dialog": [
            {
                "start": datetime(2023, 1, 1, 12, 1, 0),
                "sender": {
                    "name": "Test User"
                },
                "message": {
                    "type": "text",
                    "text": "Hello, this is a test message"
                }
            }
        ]
    }

# Integration testing fixtures

@pytest.fixture(scope="module")
def mongo_test_client():
    """Create a real MongoDB client for integration testing"""
    try:
        client = pymongo.MongoClient(
            TEST_DB_CONFIG["url"], 
            serverSelectionTimeoutMS=2000  # 2 second timeout
        )
        # Check if we can connect
        client.server_info()
        yield client
        # Clean up after tests
        client.drop_database(TEST_DB_CONFIG["database"])
        client.close()
    except pymongo.errors.ServerSelectionTimeoutError:
        pytest.skip("MongoDB server not available for integration tests")

@pytest.fixture
def unique_vcon():
    """Create a sample Vcon object with unique ID for testing"""
    data = SAMPLE_VCON_DATA.copy()
    data["uuid"] = str(uuid.uuid4())
    return Vcon(data)

@pytest.fixture
def vcon_redis_patcher(unique_vcon):
    """Mock VconRedis to return our sample vCon with unique ID"""
    with patch('server.lib.vcon_redis.VconRedis') as mock:
        redis_instance = MagicMock()
        redis_instance.get_vcon.return_value = unique_vcon
        mock.return_value = redis_instance
        yield redis_instance, unique_vcon

@pytest.fixture
def mock_redis():
    """
    Create a mock of the Redis client using fakeredis.
    This will patch the Redis client in redis_mgr.py with a fake Redis server.
    """
    # Create fakeredis server instance
    fake_redis_server = fakeredis.FakeServer()
    fake_redis = fakeredis.FakeRedis(server=fake_redis_server, decode_responses=True)
    
    # Add JSON capabilities to our mock
    # This is necessary because Redis.json() is used in the code
    class MockJsonCommands:
        def set(self, key, path, value):
            # Simplified implementation for JSON SET
            if path == "$" or path == ".":
                fake_redis.set(key, json.dumps(value))
            return "OK"
        
        def get(self, key, path=None):
            # Simplified implementation for JSON GET
            data = fake_redis.get(key)
            if data:
                return json.loads(data)
            return None
    
    # Add json method to our fake_redis instance
    fake_redis.json = lambda: MockJsonCommands()
    
    # Patch the Redis client
    with patch('server.redis_mgr.redis', fake_redis):
        yield fake_redis

@pytest.fixture
def prepare_redis_with_vcon(mock_redis, sample_vcon):
    """
    Prepare Redis with sample vCon data.
    This is useful for tests that need to read a vCon from Redis.
    """
    key = f"vcon:{sample_vcon.uuid}"
    vcon_dict = sample_vcon.to_dict()
    mock_redis.json().set(key, "$", vcon_dict)
    return sample_vcon 