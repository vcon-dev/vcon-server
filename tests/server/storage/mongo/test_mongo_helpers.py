import pytest
from datetime import datetime

from server.storage.mongo import (
    convert_date_to_mongo_date,
    convert_mongo_date_to_string,
    prepare_mongo_for_vcon
)

class TestDateConversion:
    
    def test_convert_date_to_mongo_date_z_format(self):
        """Test ISO date string with Z format to datetime conversion"""
        date_str = "2023-01-01T12:00:00.000Z"
        result = convert_date_to_mongo_date(date_str)
        
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.minute == 0
        assert result.second == 0
    
    def test_convert_date_to_mongo_date_offset_format(self):
        """Test ISO date string with timezone offset to datetime conversion"""
        date_str = "2023-01-01T12:00:00.000+00:00"
        result = convert_date_to_mongo_date(date_str)
        
        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
    
    def test_convert_date_to_mongo_date_invalid_format(self):
        """Test invalid date string conversion handling"""
        date_str = "not-a-date"
        
        with pytest.raises(Exception):
            convert_date_to_mongo_date(date_str)
    
    def test_convert_mongo_date_to_string(self):
        """Test datetime to ISO string conversion"""
        date_obj = datetime(2023, 1, 1, 12, 0, 0, 500000)  # with microseconds
        result = convert_mongo_date_to_string(date_obj)
        
        assert isinstance(result, str)
        assert result == "2023-01-01T12:00:00.500Z"
    
    def test_convert_mongo_date_to_string_non_datetime(self):
        """Test non-datetime object handling"""
        # With string input
        assert convert_mongo_date_to_string("not a date") == "not a date"
        
        # With None input
        assert convert_mongo_date_to_string(None) is None
        
        # With number input
        assert convert_mongo_date_to_string(123) == 123


class TestDocumentConversion:
    
    def test_prepare_mongo_for_vcon_complete(self):
        """Test conversion of complete MongoDB document to vCon format"""
        mongo_doc = {
            "_id": "test-id-123",
            "version": "1.1.0",
            "created_at": datetime(2023, 1, 1, 12, 0, 0),
            "metadata": {
                "title": "Test Document"
            },
            "dialog": [
                {
                    "start": datetime(2023, 1, 1, 12, 5, 0),
                    "message": {"text": "Test message"}
                }
            ]
        }
        
        result = prepare_mongo_for_vcon(mongo_doc)
        
        # Check ID conversion
        assert "_id" not in result
        assert result["uuid"] == "test-id-123"
        
        # Check date conversion
        assert result["created_at"] == "2023-01-01T12:00:00.000Z"
        assert result["dialog"][0]["start"] == "2023-01-01T12:05:00.000Z"
    
    def test_prepare_mongo_for_vcon_empty(self):
        """Test handling of empty/None document"""
        assert prepare_mongo_for_vcon(None) is None
        assert prepare_mongo_for_vcon({}) is not None
    
    def test_prepare_mongo_for_vcon_missing_fields(self):
        """Test handling of documents with missing fields"""
        # Document without created_at
        doc_no_created_at = {
            "_id": "test-id-123",
            "version": "1.1.0",
            "dialog": []
        }
        result = prepare_mongo_for_vcon(doc_no_created_at)
        assert "uuid" in result
        assert "created_at" not in result
        
        # Document without dialog
        doc_no_dialog = {
            "_id": "test-id-123",
            "version": "1.1.0",
            "created_at": datetime(2023, 1, 1, 12, 0, 0)
        }
        result = prepare_mongo_for_vcon(doc_no_dialog)
        assert "uuid" in result
        assert "created_at" in result
        assert isinstance(result["created_at"], str)
        assert "dialog" not in result
    
    def test_prepare_mongo_for_vcon_dialog_without_start(self):
        """Test handling of dialog entries without start dates"""
        mongo_doc = {
            "_id": "test-id-123",
            "version": "1.1.0",
            "dialog": [
                {
                    # No start field
                    "message": {"text": "Test message"}
                }
            ]
        }
        
        result = prepare_mongo_for_vcon(mongo_doc)
        assert "dialog" in result
        assert "start" not in result["dialog"][0] 