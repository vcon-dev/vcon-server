"""
Integration tests for Milvus storage with actual server
"""

import pytest
import os
import time
import uuid
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import logging

# Skip if integration tests not enabled
pytestmark = pytest.mark.skipif(
    not os.getenv("MILVUS_INTEGRATION_TESTS", "false").lower() == "true",
    reason="Set MILVUS_INTEGRATION_TESTS=true to run integration tests"
)

# Test configuration
MILVUS_HOST = os.getenv("MILVUS_TEST_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_TEST_PORT", "19530")
MILVUS_USER = os.getenv("MILVUS_TEST_USER", "")
MILVUS_PASSWORD = os.getenv("MILVUS_TEST_PASSWORD", "")
TEST_COLLECTION_PREFIX = "test_vcons_"

try:
    from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType
    PYMILVUS_AVAILABLE = True
except ImportError:
    PYMILVUS_AVAILABLE = False
    pytestmark = pytest.mark.skip("pymilvus not installed")


def generate_mock_vcon():
    """Generate a mock vCon for testing."""
    from datetime import datetime, UTC
    
    vcon_uuid = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    return {
        "uuid": vcon_uuid,
        "vcon": "0.0.1",
        "created_at": datetime.now(UTC).isoformat(),
        "parties": [
            {"name": "Test User 1", "tel": "+1234567890"},
            {"name": "Test User 2", "tel": "+0987654321"}
        ],
        "dialog": [
            {
                "type": "recording",
                "start": datetime.now(UTC).isoformat(),
                "parties": [0, 1],
                "body": {
                    "transcript": "This is a test conversation for Milvus integration testing."
                }
            }
        ],
        "analysis": [
            {
                "type": "transcript",
                "vendor": "test",
                "body": {
                    "text": "This is a test conversation for Milvus integration testing."
                }
            }
        ],
        "metadata": {
            "title": "Test vCon for Milvus Integration",
            "description": "Generated for testing purposes"
        }
    }


@pytest.fixture(scope="session")
def milvus_connection():
    """Setup connection to Milvus server for testing."""
    if not PYMILVUS_AVAILABLE:
        pytest.skip("pymilvus not available")
    
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
        
        logging.info(f"Connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")
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
def test_collection(milvus_connection, test_collection_name):
    """Create a test collection for vCons."""
    # Define collection schema similar to what MilvusStorage would create
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="vcon_uuid", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="party_id", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
        FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=50),
    ]
    
    schema = CollectionSchema(fields=fields, description="Test vCons collection")
    collection = Collection(name=test_collection_name, schema=schema, using=milvus_connection)
    
    # Create a simple index
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    
    yield collection
    
    # Cleanup
    try:
        collection.drop()
        logging.info(f"Dropped test collection: {test_collection_name}")
    except Exception as e:
        logging.warning(f"Failed to cleanup collection {test_collection_name}: {e}")


class TestMilvusBasic:
    """Basic Milvus integration tests without vcon-server dependencies."""
    
    def test_connection_establishment(self, milvus_connection):
        """Test that we can connect to Milvus server."""
        # Test basic connection
        assert connections.get_connection_addr(milvus_connection) is not None
        
        # Test server info
        try:
            server_version = utility.get_server_version(using=milvus_connection)
            logging.info(f"Milvus server version: {server_version}")
            assert server_version is not None
        except Exception as e:
            pytest.fail(f"Failed to get server version: {e}")
    
    def test_collection_creation_and_schema(self, test_collection):
        """Test creating a collection and verifying its schema."""
        # Verify collection exists
        assert test_collection.name.startswith(TEST_COLLECTION_PREFIX)
        
        # Check schema
        schema = test_collection.schema
        field_names = [field.name for field in schema.fields]
        
        expected_fields = ['id', 'vcon_uuid', 'party_id', 'text', 'embedding', 'created_at']
        for field in expected_fields:
            assert field in field_names, f"Required field '{field}' not found in schema"
    
    def test_insert_and_query_data(self, test_collection):
        """Test inserting and querying data in Milvus."""
        # Generate test data
        test_vcon = generate_mock_vcon()
        vcon_uuid = test_vcon["uuid"]
        
        # Create mock embedding (1536 dimensions)
        mock_embedding = [0.1] * 1536
        
        # Prepare data for insertion
        data = [{
            "vcon_uuid": vcon_uuid,
            "party_id": "test_party",
            "text": "This is test text for embedding",
            "embedding": mock_embedding,
            "created_at": test_vcon["created_at"]
        }]
        
        # Insert data
        result = test_collection.insert(data)
        assert result.insert_count == 1
        
        # Flush to ensure data is written
        test_collection.flush()
        
        # Load collection for querying
        test_collection.load()
        
        # Wait a moment for indexing
        time.sleep(1)
        
        # Query the data
        query_result = test_collection.query(
            expr=f"vcon_uuid == '{vcon_uuid}'",
            output_fields=["vcon_uuid", "text", "party_id"]
        )
        
        assert len(query_result) == 1
        assert query_result[0]["vcon_uuid"] == vcon_uuid
        assert query_result[0]["text"] == "This is test text for embedding"
    
    def test_multiple_inserts(self, test_collection):
        """Test inserting multiple records."""
        # Generate multiple test vCons
        test_data = []
        vcon_uuids = []
        
        for i in range(3):
            test_vcon = generate_mock_vcon()
            vcon_uuid = test_vcon["uuid"]
            vcon_uuids.append(vcon_uuid)
            
            test_data.append({
                "vcon_uuid": vcon_uuid,
                "party_id": f"test_party_{i}",
                "text": f"Test text for vCon {i}",
                "embedding": [0.1 + i * 0.1] * 1536,  # Slightly different embeddings
                "created_at": test_vcon["created_at"]
            })
        
        # Insert all data
        result = test_collection.insert(test_data)
        assert result.insert_count == 3
        
        # Flush and load
        test_collection.flush()
        test_collection.load()
        time.sleep(1)
        
        # Query each vCon
        for vcon_uuid in vcon_uuids:
            query_result = test_collection.query(
                expr=f"vcon_uuid == '{vcon_uuid}'",
                output_fields=["vcon_uuid"]
            )
            assert len(query_result) == 1
            assert query_result[0]["vcon_uuid"] == vcon_uuid
    
    def test_vector_search(self, test_collection):
        """Test vector similarity search."""
        # Insert test data with embeddings
        test_data = []
        for i in range(5):
            test_vcon = generate_mock_vcon()
            # Create embeddings with different patterns
            embedding = [0.1 + i * 0.05] * 1536
            
            test_data.append({
                "vcon_uuid": test_vcon["uuid"],
                "party_id": f"party_{i}",
                "text": f"Test conversation {i}",
                "embedding": embedding,
                "created_at": test_vcon["created_at"]
            })
        
        # Insert and prepare for search
        test_collection.insert(test_data)
        test_collection.flush()
        test_collection.load()
        time.sleep(2)  # Give more time for indexing
        
        # Perform vector search
        search_vector = [0.15] * 1536  # Should be closest to embedding 1
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        
        results = test_collection.search(
            data=[search_vector],
            anns_field="embedding",
            param=search_params,
            limit=3,
            output_fields=["vcon_uuid", "text"]
        )
        
        # Verify we got results
        assert len(results) == 1  # One query
        assert len(results[0]) > 0  # At least one result
        
        # The results should be ordered by similarity
        for hit in results[0]:
            assert hasattr(hit, 'distance')
            assert hasattr(hit, 'entity')


@pytest.mark.performance
class TestMilvusPerformance:
    """Performance tests for Milvus operations."""
    
    def test_bulk_insert_performance(self, test_collection):
        """Test performance of bulk insertions."""
        num_records = 100
        start_time = time.time()
        
        # Generate bulk data
        bulk_data = []
        for i in range(num_records):
            test_vcon = generate_mock_vcon()
            bulk_data.append({
                "vcon_uuid": test_vcon["uuid"],
                "party_id": f"bulk_party_{i}",
                "text": f"Bulk test text {i}",
                "embedding": [0.1 + i * 0.001] * 1536,
                "created_at": test_vcon["created_at"]
            })
        
        # Insert bulk data
        result = test_collection.insert(bulk_data)
        assert result.insert_count == num_records
        
        test_collection.flush()
        insert_time = time.time() - start_time
        
        logging.info(f"Inserted {num_records} records in {insert_time:.2f} seconds")
        logging.info(f"Average insert time: {insert_time/num_records:.4f} seconds per record")
        
        # Performance assertion (adjust based on your requirements)
        assert insert_time < 30, f"Bulk insert took too long: {insert_time:.2f}s"