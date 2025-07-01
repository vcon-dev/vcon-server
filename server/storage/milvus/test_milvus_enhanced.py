"""
Enhanced Milvus integration tests with full vCon functionality
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

try:
    from pymilvus import connections, utility, Collection, FieldSchema, CollectionSchema, DataType
    PYMILVUS_AVAILABLE = True
except ImportError:
    PYMILVUS_AVAILABLE = False
    pytestmark = pytest.mark.skip("pymilvus not installed")

# Test configuration
MILVUS_HOST = os.getenv("MILVUS_TEST_HOST", "localhost")
MILVUS_PORT = os.getenv("MILVUS_TEST_PORT", "19530")
TEST_COLLECTION_PREFIX = "test_vcons_"

def generate_mock_vcon():
    """Generate a mock vCon for testing."""
    from datetime import datetime, UTC
    
    vcon_uuid = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    return {
        "uuid": vcon_uuid,
        "vcon": "0.0.1",
        "created_at": datetime.now(UTC).isoformat(),
        "parties": [
            {"name": "Alice Johnson", "tel": "+1234567890", "role": "customer"},
            {"name": "Bob Smith", "tel": "+0987654321", "role": "agent"}
        ],
        "dialog": [
            {
                "type": "recording",
                "start": datetime.now(UTC).isoformat(),
                "parties": [0, 1],
                "body": {
                    "transcript": "Hello, I'm calling about my account. I need help with billing issues and want to update my information."
                }
            }
        ],
        "analysis": [
            {
                "type": "transcript",
                "vendor": "test",
                "body": {
                    "text": "Hello, I'm calling about my account. I need help with billing issues and want to update my information."
                }
            },
            {
                "type": "summary", 
                "vendor": "test",
                "body": "Customer called about account issues, specifically billing and information updates."
            }
        ],
        "metadata": {
            "title": "Customer Service Call - Account Issues",
            "description": "Customer inquiry about billing and account updates"
        }
    }

@pytest.fixture(scope="session")
def milvus_connection():
    """Setup connection to Milvus server for testing."""
    if not PYMILVUS_AVAILABLE:
        pytest.skip("pymilvus not available")
    
    alias = f"test_connection_{int(time.time())}"
    
    try:
        connections.connect(
            alias=alias,
            host=MILVUS_HOST,
            port=MILVUS_PORT
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
def vcon_collection(milvus_connection, test_collection_name):
    """Create a vCon-specific collection for testing."""
    # Define schema similar to what your MilvusStorage would create
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="vcon_uuid", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="party_id", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
        FieldSchema(name="created_at", dtype=DataType.VARCHAR, max_length=50),
        FieldSchema(name="subject", dtype=DataType.VARCHAR, max_length=255),
        FieldSchema(name="metadata_title", dtype=DataType.VARCHAR, max_length=255),
        FieldSchema(name="has_transcript", dtype=DataType.BOOL),
        FieldSchema(name="has_summary", dtype=DataType.BOOL),
        FieldSchema(name="party_count", dtype=DataType.INT16),
    ]
    
    schema = CollectionSchema(fields=fields, description="Test vCons collection for integration testing")
    collection = Collection(name=test_collection_name, schema=schema, using=milvus_connection)
    
    # Create index
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
            print(f"✓ Connected to Milvus version: {server_version}")
            assert server_version is not None
        except Exception as e:
            pytest.fail(f"Failed to get server version: {e}")
    
    def test_collection_operations(self, vcon_collection):
        """Test basic collection operations."""
        # Verify collection exists
        assert vcon_collection.name.startswith(TEST_COLLECTION_PREFIX)
        
        # Check schema
        schema = vcon_collection.schema
        field_names = [field.name for field in schema.fields]
        
        expected_fields = ['id', 'vcon_uuid', 'party_id', 'text', 'embedding', 'created_at']
        for field in expected_fields:
            assert field in field_names, f"Required field '{field}' not found in schema"
    
    def test_vcon_data_insertion(self, vcon_collection):
        """Test inserting vCon-like data into Milvus."""
        # Generate test vCon
        test_vcon = generate_mock_vcon()
        vcon_uuid = test_vcon["uuid"]
        
        # Extract text content (simulate what MilvusStorage would do)
        text_content = ""
        if test_vcon.get("dialog"):
            for dialog in test_vcon["dialog"]:
                if dialog.get("body", {}).get("transcript"):
                    text_content += dialog["body"]["transcript"] + " "
        
        if test_vcon.get("analysis"):
            for analysis in test_vcon["analysis"]:
                if analysis.get("type") == "summary" and analysis.get("body"):
                    text_content += str(analysis["body"]) + " "
        
        # Create mock embedding
        mock_embedding = [0.1] * 1536
        
        # Prepare data for insertion
        data = [{
            "vcon_uuid": vcon_uuid,
            "party_id": "test_party_1",
            "text": text_content.strip(),
            "embedding": mock_embedding,
            "created_at": test_vcon["created_at"],
            "subject": test_vcon.get("subject", ""),
            "metadata_title": test_vcon.get("metadata", {}).get("title", ""),
            "has_transcript": bool(test_vcon.get("dialog")),
            "has_summary": bool([a for a in test_vcon.get("analysis", []) if a.get("type") == "summary"]),
            "party_count": len(test_vcon.get("parties", []))
        }]
        
        # Insert data
        result = vcon_collection.insert(data)
        assert result.insert_count == 1
        
        # Flush and load
        vcon_collection.flush()
        vcon_collection.load()
        time.sleep(1)
        
        # Query the data
        query_result = vcon_collection.query(
            expr=f"vcon_uuid == '{vcon_uuid}'",
            output_fields=["vcon_uuid", "text", "party_count", "has_transcript", "has_summary"]
        )
        
        assert len(query_result) == 1
        assert query_result[0]["vcon_uuid"] == vcon_uuid
        assert query_result[0]["party_count"] == 2
        assert query_result[0]["has_transcript"] == True
        assert query_result[0]["has_summary"] == True
    
    def test_multiple_vcon_insertion(self, vcon_collection):
        """Test inserting multiple vCons."""
        vcon_uuids = []
        test_data = []
        
        # Generate multiple test vCons
        for i in range(5):
            test_vcon = generate_mock_vcon()
            vcon_uuid = test_vcon["uuid"]
            vcon_uuids.append(vcon_uuid)
            
            # Vary the data slightly
            text_content = f"Test conversation {i} about customer service and support issues."
            
            test_data.append({
                "vcon_uuid": vcon_uuid,
                "party_id": f"test_party_{i}",
                "text": text_content,
                "embedding": [0.1 + i * 0.01] * 1536,
                "created_at": test_vcon["created_at"],
                "subject": f"Test Subject {i}",
                "metadata_title": f"Test Call {i}",
                "has_transcript": True,
                "has_summary": i % 2 == 0,  # Alternate
                "party_count": 2 + (i % 3)  # 2, 3, 4, 2, 3
            })
        
        # Insert all data
        result = vcon_collection.insert(test_data)
        assert result.insert_count == 5
        
        # Flush and load
        vcon_collection.flush()
        vcon_collection.load()
        time.sleep(2)
        
        # Query each vCon
        for vcon_uuid in vcon_uuids:
            query_result = vcon_collection.query(
                expr=f"vcon_uuid == '{vcon_uuid}'",
                output_fields=["vcon_uuid"]
            )
            assert len(query_result) == 1
            assert query_result[0]["vcon_uuid"] == vcon_uuid
    
    def test_vector_similarity_search(self, vcon_collection):
        """Test vector similarity search functionality."""
        # Insert test data with different embeddings
        test_data = []
        embeddings = [
            [0.1] * 1536,    # Base embedding
            [0.2] * 1536,    # Similar
            [0.9] * 1536,    # Very different
        ]
        
        for i, embedding in enumerate(embeddings):
            test_vcon = generate_mock_vcon()
            test_data.append({
                "vcon_uuid": test_vcon["uuid"],
                "party_id": f"party_{i}",
                "text": f"Test conversation {i}",
                "embedding": embedding,
                "created_at": test_vcon["created_at"],
                "subject": f"Subject {i}",
                "metadata_title": f"Title {i}",
                "has_transcript": True,
                "has_summary": True,
                "party_count": 2
            })
        
        # Insert and prepare
        vcon_collection.insert(test_data)
        vcon_collection.flush()
        vcon_collection.load()
        time.sleep(2)
        
        # Perform similarity search
        search_vector = [0.15] * 1536  # Should be closest to first embedding
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        
        results = vcon_collection.search(
            data=[search_vector],
            anns_field="embedding",
            param=search_params,
            limit=3,
            output_fields=["vcon_uuid", "text"]
        )
        
        # Verify results
        assert len(results) == 1  # One query
        assert len(results[0]) >= 1  # At least one result
        
        # Results should be ordered by similarity
        distances = [hit.distance for hit in results[0]]
        assert all(distances[i] <= distances[i+1] for i in range(len(distances)-1))

@pytest.mark.performance  
class TestMilvusPerformance:
    """Performance tests for Milvus operations with vCon data."""
    
    def test_bulk_vcon_insertion_performance(self, vcon_collection):
        """Test performance of bulk vCon insertions."""
        num_vcons = 50
        start_time = time.time()
        
        # Generate bulk vCon data
        bulk_data = []
        for i in range(num_vcons):
            test_vcon = generate_mock_vcon()
            bulk_data.append({
                "vcon_uuid": test_vcon["uuid"],
                "party_id": f"bulk_party_{i}",
                "text": f"Bulk test conversation {i} about various customer service topics.",
                "embedding": [0.1 + i * 0.001] * 1536,
                "created_at": test_vcon["created_at"],
                "subject": f"Bulk Subject {i}",
                "metadata_title": f"Bulk Call {i}",
                "has_transcript": True,
                "has_summary": i % 3 == 0,
                "party_count": 2 + (i % 4)
            })
        
        # Insert bulk data
        result = vcon_collection.insert(bulk_data)
        assert result.insert_count == num_vcons
        
        vcon_collection.flush()
        insert_time = time.time() - start_time
        
        print(f"Inserted {num_vcons} vCons in {insert_time:.2f} seconds")
        print(f"Average insert time: {insert_time/num_vcons:.4f} seconds per vCon")
        
        # Performance assertion
        assert insert_time < 30, f"Bulk insert took too long: {insert_time:.2f}s"
    
    def test_search_performance(self, vcon_collection):
        """Test search performance with realistic data."""
        # Insert test data
        num_vcons = 20
        test_data = []
        
        for i in range(num_vcons):
            test_vcon = generate_mock_vcon()
            test_data.append({
                "vcon_uuid": test_vcon["uuid"],
                "party_id": f"search_party_{i}",
                "text": f"Search test conversation {i}",
                "embedding": [0.1 + i * 0.01] * 1536,
                "created_at": test_vcon["created_at"],
                "subject": f"Search Subject {i}",
                "metadata_title": f"Search Call {i}",
                "has_transcript": True,
                "has_summary": True,
                "party_count": 2
            })
        
        vcon_collection.insert(test_data)
        vcon_collection.flush()
        vcon_collection.load()
        time.sleep(2)
        
        # Test search performance
        search_vector = [0.15] * 1536
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        
        start_time = time.time()
        
        # Perform multiple searches
        for _ in range(10):
            results = vcon_collection.search(
                data=[search_vector],
                anns_field="embedding",
                param=search_params,
                limit=5,
                output_fields=["vcon_uuid"]
            )
            assert len(results[0]) > 0
        
        search_time = time.time() - start_time
        avg_search_time = search_time / 10
        
        print(f"Average search time: {avg_search_time:.4f} seconds")
        
        # Performance assertion
        assert avg_search_time < 1.0, f"Search too slow: {avg_search_time:.4f}s"