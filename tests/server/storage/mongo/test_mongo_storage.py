import pytest
import pymongo
from unittest.mock import patch, MagicMock
from datetime import datetime
import uuid

from vcon import Vcon
from server.storage.mongo import (
    save, 
    read, 
    convert_date_to_mongo_date, 
    convert_mongo_date_to_string,
    prepare_vcon_for_mongo,
    prepare_mongo_for_vcon
)

from tests.server.storage.mongo.conftest import TEST_DB_CONFIG

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


class TestMongoStorage:
    
    @pytest.fixture
    def mock_mongo_client(self):
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
    def sample_vcon(self):
        """Create a sample Vcon object for testing"""
        return Vcon(SAMPLE_VCON_DATA)
    
    @pytest.fixture
    def mock_vcon_redis(self):
        """Mock the VconRedis class"""
        with patch('server.lib.vcon_redis.VconRedis') as mock:
            redis_instance = MagicMock()
            mock.return_value = redis_instance
            yield redis_instance
    
    def test_convert_date_to_mongo_date(self):
        """Test ISO string to datetime conversion"""
        # Test with Z format
        date_str = "2023-01-01T12:00:00.000Z"
        result = convert_date_to_mongo_date(date_str)
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 0
        
        # Test with timezone offset format
        date_str = "2023-01-01T12:00:00.000+00:00"
        result = convert_date_to_mongo_date(date_str)
        assert isinstance(result, datetime)
        assert result.year == 2023
    
    def test_convert_mongo_date_to_string(self):
        """Test datetime to ISO string conversion"""
        date_obj = datetime(2023, 1, 1, 12, 0, 0)
        result = convert_mongo_date_to_string(date_obj)
        assert isinstance(result, str)
        assert result == "2023-01-01T12:00:00.000Z"
        
        # Test with non-datetime object
        result = convert_mongo_date_to_string("not a date")
        assert result == "not a date"
    
    def test_prepare_vcon_for_mongo(self, sample_vcon):
        """Test conversion of vCon object to MongoDB format"""
        result = prepare_vcon_for_mongo(sample_vcon)
        
        # Check if _id is set
        assert result["_id"] == sample_vcon.uuid
        
        # Check if created_at is converted to datetime
        assert isinstance(result["created_at"], datetime)
        
        # Check if dialog start is converted to datetime
        assert isinstance(result["dialog"][0]["start"], datetime)
    
    def test_prepare_mongo_for_vcon(self):
        """Test conversion of MongoDB document to vCon format"""
        # Create a test MongoDB document
        mongo_doc = {
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
        
        result = prepare_mongo_for_vcon(mongo_doc)
        
        # Check if _id is converted to uuid
        assert "uuid" in result
        assert result["uuid"] == "test-uuid-123"
        assert "_id" not in result
        
        # Check if dates are converted to strings
        assert isinstance(result["created_at"], str)
        assert result["created_at"] == "2023-01-01T12:00:00.000Z"
        
        # Check if dialog start date is converted to string
        assert isinstance(result["dialog"][0]["start"], str)
        assert result["dialog"][0]["start"] == "2023-01-01T12:01:00.000Z"
    
    def test_save_success(self, mock_mongo_client, mock_vcon_redis, sample_vcon, mock_redis):
        """Test successful save of vCon to MongoDB"""
        client_mock, collection_mock = mock_mongo_client
        
        # Configure VconRedis to return our sample vCon
        mock_vcon_redis.get_vcon.return_value = sample_vcon
        
        # Patch the VconRedis constructor to return our mock
        with patch('server.storage.mongo.VconRedis', return_value=mock_vcon_redis):
            # Call the save function
            save("test-uuid-123", opts=TEST_DB_CONFIG)
        
        # Assert the MongoDB client was created with the right URL
        client_mock.assert_called_with(TEST_DB_CONFIG["url"])
        
        # Assert update_one was called with the right arguments
        collection_mock.update_one.assert_called_once()
        args, kwargs = collection_mock.update_one.call_args
        assert args[0] == {"_id": "test-uuid-123"}
        assert "$set" in args[1]
        
        # Ensure the redis get_vcon was called with the right UUID
        mock_vcon_redis.get_vcon.assert_called_with("test-uuid-123")
    
    def test_save_vcon_not_in_redis(self, mock_mongo_client, mock_vcon_redis, mock_redis):
        """Test save when vCon is not found in Redis"""
        # Configure VconRedis to return None
        mock_vcon_redis.get_vcon.return_value = None
        
        # Patch the VconRedis constructor to return our mock
        with patch('server.storage.mongo.VconRedis', return_value=mock_vcon_redis):
            # Call the save function and expect a ValueError
            with pytest.raises(ValueError) as e:
                save("missing-uuid", opts=TEST_DB_CONFIG)
            
            assert "not found in Redis" in str(e.value)
    
    def test_read_success(self, mock_mongo_client, sample_vcon, mock_redis):
        """Test successful read of vCon from MongoDB"""
        client_mock, collection_mock = mock_mongo_client
        
        # Create a MongoDB document that would be returned from find_one
        mongo_doc = prepare_vcon_for_mongo(sample_vcon)
        
        # Configure collection_mock to return our document
        collection_mock.find_one.return_value = mongo_doc
        
        # Call the read function
        result = read("test-uuid-123", opts=TEST_DB_CONFIG)
        
        # Assert the MongoDB client was created with the right URL
        client_mock.assert_called_with(TEST_DB_CONFIG["url"])
        
        # Assert find_one was called with the right arguments
        collection_mock.find_one.assert_called_with({"_id": "test-uuid-123"})
        
        # Check that the result is a Vcon
        assert isinstance(result, Vcon)
        assert result.uuid == "test-uuid-123"
    
    def test_read_not_found(self, mock_mongo_client):
        """Test read when vCon is not found in MongoDB"""
        client_mock, collection_mock = mock_mongo_client
        
        # Configure collection_mock to return None
        collection_mock.find_one.return_value = None
        
        # Call the read function
        result = read("missing-uuid", opts=TEST_DB_CONFIG)
        
        # Assert find_one was called
        collection_mock.find_one.assert_called_with({"_id": "missing-uuid"})
        
        # Check that the result is None
        assert result is None
    
    @patch('server.storage.mongo.logger')
    def test_read_exception(self, mock_logger, mock_mongo_client):
        """Test read handling of exceptions"""
        client_mock, collection_mock = mock_mongo_client
        
        # Configure collection_mock to raise an exception
        collection_mock.find_one.side_effect = Exception("Test exception")
        
        # Call the read function and expect exception to be re-raised
        with pytest.raises(Exception) as e:
            read("test-uuid-123", opts=TEST_DB_CONFIG)
        
        assert "Test exception" in str(e.value)
        
        # Check that the error was logged
        mock_logger.error.assert_called_once()


@pytest.mark.integration
class TestMongoStorageIntegration:
    
    def test_save_and_read_integration(self, mock_redis, sample_vcon):
        """Test save and read with a mocked MongoDB instance"""
        # Create a MongoDB document that would be returned from find_one
        mongo_doc = prepare_vcon_for_mongo(sample_vcon)
        
        # Create a mock MongoDB collection
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = mongo_doc
        mock_collection.update_one.return_value = MagicMock()
        
        # Create a mock MongoDB database
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_collection
        
        # Create a mock MongoDB client
        mock_client = MagicMock()
        mock_client.__getitem__.return_value = mock_db
        mock_client.server_info.return_value = {"version": "4.0.0"}
        
        # Create a mock VconRedis instance that returns our sample vCon
        mock_vcon_redis = MagicMock()
        mock_vcon_redis.get_vcon.return_value = sample_vcon
        
        # Patch both MongoClient and VconRedis
        with patch('pymongo.MongoClient', return_value=mock_client), \
             patch('server.storage.mongo.VconRedis', return_value=mock_vcon_redis):
            
            # Save the vCon to MongoDB
            save(sample_vcon.uuid, opts=TEST_DB_CONFIG)
            
            # Verify update_one was called
            mock_collection.update_one.assert_called_once()
            
            # Read it back
            result = read(sample_vcon.uuid, opts=TEST_DB_CONFIG)
        
        # Check if it matches
        assert result is not None
        assert result.uuid == sample_vcon.uuid
        
        # Check other properties using the vcon_dict
        assert result.vcon_dict.get("metadata") == sample_vcon.vcon_dict.get("metadata")
        
        # Check that the dialog was correctly preserved
        assert len(result.dialog) == len(sample_vcon.dialog)
        if len(sample_vcon.dialog) > 0:
            assert result.dialog[0].get("message", {}).get("text") == sample_vcon.dialog[0].get("message", {}).get("text") 