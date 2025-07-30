import pytest
import json
import uuid
from unittest.mock import MagicMock, patch
from datetime import datetime
from server.storage.postgres import save, get, Vcons, get_db_connection, BaseModel

class TestPostgresIntegration:
    """Test PostgreSQL storage integration with real database."""
    
    def test_postgres_connection(self, postgres_options):
        """Test that we can connect to PostgreSQL."""
        db = get_db_connection(postgres_options)
        assert db is not None
        
        # Test basic connection
        db.connect()
        assert db.is_connection_usable()
        db.close()
    
    def test_table_creation(self, clean_postgres_db):
        """Test that tables are created correctly."""
        db = get_db_connection(clean_postgres_db)
        BaseModel._meta.database = db
        Vcons._meta.database = db 

        # Create tables
        db.drop_tables([Vcons], safe=True)
        db.create_tables([Vcons], safe=True)
        
        # Verify table exists
        tables = db.get_tables()
        assert "vcons" in tables
        
        db.close()
    
    @patch('server.storage.postgres.VconRedis')
    def test_save_vcon(self, mock_redis, clean_postgres_db):
        """Test saving a vCon to PostgreSQL."""
        # Mock vCon object
        mock_vcon = MagicMock()
        test_uuid = str(uuid.uuid4())
        mock_vcon.uuid = test_uuid
        mock_vcon.vcon = '{"vcon": "0.0.1", "uuid": "' + test_uuid + '"}'
        mock_vcon.created_at = datetime.now()
        mock_vcon.subject = "Test Subject"
        mock_vcon.to_dict.return_value = {"vcon": "0.0.1", "uuid": test_uuid}
        
        # Mock Redis
        mock_redis_instance = MagicMock()
        mock_redis_instance.get_vcon.return_value = mock_vcon
        mock_redis.return_value = mock_redis_instance
        
        # Save vCon
        save(test_uuid, clean_postgres_db)
        
        # Verify it was saved
        db = get_db_connection(clean_postgres_db)
        BaseModel._meta.database = db
        
        saved_vcon = Vcons.get(Vcons.id == test_uuid)
        assert str(saved_vcon.uuid) == test_uuid
        assert saved_vcon.subject == "Test Subject"
        assert saved_vcon.vcon_json["uuid"] == test_uuid
        
        db.close()
    
    @patch('server.storage.postgres.VconRedis')
    def test_get_vcon(self, mock_redis, clean_postgres_db):
        """Test retrieving a vCon from PostgreSQL."""
        # Mock vCon object
        mock_vcon = MagicMock()
        test_uuid = str(uuid.uuid4())
        mock_vcon.uuid = test_uuid
        mock_vcon.vcon = '{"vcon": "0.0.1", "uuid": "' + test_uuid + '"}'
        mock_vcon.created_at = datetime.now()
        mock_vcon.subject = "Test Subject"
        mock_vcon.to_dict.return_value = {"vcon": "0.0.1", "uuid": test_uuid}
        
        # Mock Redis
        mock_redis_instance = MagicMock()
        mock_redis_instance.get_vcon.return_value = mock_vcon
        mock_redis.return_value = mock_redis_instance
        
        # Save vCon first
        save(test_uuid, clean_postgres_db)
        
        # Get vCon
        retrieved_vcon = get(test_uuid, clean_postgres_db)
        
        # Verify retrieval
        assert retrieved_vcon is not None
        assert retrieved_vcon["uuid"] == test_uuid
    
    def test_get_nonexistent_vcon(self, clean_postgres_db):
        """Test retrieving a non-existent vCon."""
        fake_uuid = str(uuid.uuid4())
        result = get(fake_uuid, clean_postgres_db)
        assert result is None
    
    @patch('server.storage.postgres.VconRedis')
    def test_upsert_vcon(self, mock_redis, clean_postgres_db):
        """Test that saving the same vCon twice updates it."""
        # Mock vCon object
        mock_vcon = MagicMock()
        test_uuid = str(uuid.uuid4())
        mock_vcon.uuid = test_uuid
        mock_vcon.vcon = '{"vcon": "0.0.1", "uuid": "' + test_uuid + '"}'
        mock_vcon.created_at = datetime.now()
        mock_vcon.subject = "Original Subject"
        mock_vcon.to_dict.return_value = {"vcon": "0.0.1", "uuid": test_uuid}
        
        # Mock Redis
        mock_redis_instance = MagicMock()
        mock_redis_instance.get_vcon.return_value = mock_vcon
        mock_redis.return_value = mock_redis_instance
        
        # Save vCon first time
        save(test_uuid, clean_postgres_db)
        
        # Update mock vCon
        mock_vcon.subject = "Updated Subject"
        mock_vcon.to_dict.return_value = {"vcon": "0.0.1", "uuid": test_uuid, "updated": True}
        
        # Save vCon second time (should update)
        save(test_uuid, clean_postgres_db)
        
        # Verify it was updated
        db = get_db_connection(clean_postgres_db)
        BaseModel._meta.database = db
        
        # Should only have one record
        count = Vcons.select().count()
        assert count == 1
        
        # Should have updated values
        saved_vcon = Vcons.get(Vcons.id == test_uuid)
        assert saved_vcon.subject == "Updated Subject"
        assert saved_vcon.vcon_json["updated"] is True
        
        db.close()
    
    @patch('server.storage.postgres.VconRedis')
    def test_multiple_vcons(self, mock_redis, clean_postgres_db):
        """Test saving multiple vCons."""
        # Mock Redis
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        
        vcon_uuids = []
        for i in range(3):
            test_uuid = str(uuid.uuid4())
            vcon_uuids.append(test_uuid)
            
            # Mock vCon object
            mock_vcon = MagicMock()
            mock_vcon.uuid = test_uuid
            mock_vcon.vcon = f'{{"vcon": "0.0.1", "uuid": "{test_uuid}"}}'
            mock_vcon.created_at = datetime.now()
            mock_vcon.subject = f"Test Subject {i}"
            mock_vcon.to_dict.return_value = {"vcon": "0.0.1", "uuid": test_uuid}
            
            mock_redis_instance.get_vcon.return_value = mock_vcon
            
            # Save vCon
            save(test_uuid, clean_postgres_db)
        
        # Verify all were saved
        db = get_db_connection(clean_postgres_db)
        BaseModel._meta.database = db
        
        count = Vcons.select().count()
        assert count == 3
        
        # Verify we can retrieve all
        for test_uuid in vcon_uuids:
            retrieved = get(test_uuid, clean_postgres_db)
            assert retrieved is not None
            assert retrieved["uuid"] == test_uuid
        
        db.close()
    
    def test_database_error_handling(self, clean_postgres_db):
        """Test error handling when database operations fail."""
        # Test with invalid UUID
        with pytest.raises(Exception):
            get("invalid-uuid", clean_postgres_db)
        
        # Test with invalid database options - this should raise an exception
        invalid_opts = {
            "name": "postgres",
            "database": "nonexistent_db",
            "user": "nonexistent_user",
            "password": "wrong_password",
            "host": "localhost",
            "port": 5433
        }
        
        with pytest.raises(Exception):
            get(str(uuid.uuid4()), invalid_opts)