"""
PostgreSQL storage module for vcon-server

This module provides integration with PostgreSQL for storing vCons. It uses the peewee ORM
for database operations and stores vCons in a dedicated table with JSON support.

The module supports:
- Storing complete vCon objects as JSON
- Storing metadata fields for quick access
- Automatic table creation if not exists
- Connection pooling and proper resource cleanup
"""

from typing import Optional, Dict, Any
from lib.logging_utils import init_logger
from server.lib.vcon_redis import VconRedis
from playhouse.postgres_ext import PostgresqlExtDatabase, BinaryJSONField
from peewee import (
    Model,
    DateTimeField,
    TextField,
    UUIDField,
)
from datetime import datetime

logger = init_logger(__name__)

# Default configuration for PostgreSQL connection
default_options = {
    "name": "postgres",
    "database": "vcon_db",  # Default database name
    "user": "postgres",     # Default username
    "password": "",         # Password should be provided in options
    "host": "localhost",    # Default host
    "port": 5432,          # Default PostgreSQL port
}

class BaseModel(Model):
    """Base model class for Peewee ORM models."""
    class Meta:
        database = None  # Will be set when database connection is established

class Vcons(BaseModel):
    """
    vCon storage model for PostgreSQL.
    
    Attributes:
        id (UUID): Primary key, same as vCon UUID
        vcon (Text): Raw vCon data
        uuid (UUID): vCon UUID (duplicated for indexing)
        created_at (DateTime): vCon creation timestamp
        updated_at (DateTime): Last update timestamp
        subject (Text): vCon subject for quick access
        vcon_json (JSONB): vCon data in JSON format for querying
    """
    id = UUIDField(primary_key=True)
    vcon = TextField()
    uuid = UUIDField()
    created_at = DateTimeField()
    updated_at = DateTimeField(null=True)
    subject = TextField(null=True)
    vcon_json = BinaryJSONField(null=True)

def get_db_connection(opts: Dict[str, Any]) -> PostgresqlExtDatabase:
    """
    Create a new database connection using the provided options.
    
    Args:
        opts: Dictionary containing database connection parameters
        
    Returns:
        PostgresqlExtDatabase: Configured database connection
        
    Raises:
        Exception: If connection parameters are invalid
    """
    return PostgresqlExtDatabase(
        opts["database"],
        user=opts["user"],
        password=opts["password"],
        host=opts["host"],
        port=opts["port"],
    )

def save(
    vcon_uuid: str,
    opts: Dict[str, Any] = default_options,
) -> None:
    """
    Save a vCon to PostgreSQL storage.
    
    Args:
        vcon_uuid: UUID of the vCon to save
        opts: Dictionary containing database connection parameters
        
    Raises:
        Exception: If there's an error saving the vCon
    """
    logger.info("Starting the Postgres storage for vCon: %s", vcon_uuid)
    db = None
    try:
        vcon_redis = VconRedis()
        vcon = vcon_redis.get_vcon(vcon_uuid)
        
        # Connect to Postgres
        db = get_db_connection(opts)
        BaseModel._meta.database = db
        
        # Ensure table exists
        db.create_tables([Vcons], safe=True)

        # Prepare vCon data
        vcon_data = {
            "id": vcon.uuid,
            "uuid": vcon.uuid,
            "vcon": vcon.vcon,
            "created_at": vcon.created_at,
            "updated_at": datetime.now(),
            "subject": vcon.subject,
            "vcon_json": vcon.to_dict(),
        }
        
        # Insert or update the vCon
        Vcons.insert(**vcon_data).on_conflict(
            conflict_target=(Vcons.id),
            update=vcon_data
        ).execute()

        logger.info("Finished the Postgres storage for vCon: %s", vcon_uuid)
    except Exception as e:
        logger.error(
            f"postgres storage plugin: failed to insert vCon: {vcon_uuid}, error: {e}"
        )
        raise e
    finally:
        if db:
            db.close()

def get(
    vcon_uuid: str,
    opts: Dict[str, Any] = default_options,
) -> Optional[dict]:
    """
    Get a vCon from PostgreSQL storage by UUID.
    
    Args:
        vcon_uuid: UUID of the vCon to retrieve
        opts: Dictionary containing database connection parameters
        
    Returns:
        Optional[dict]: The vCon data as a dictionary if found, None otherwise
        
    Note:
        This method returns only the vcon_json field which contains the complete
        vCon data in JSON format. Other fields are available in the database
        but not returned to maintain consistency with other storage implementations.
    """
    logger.info("Starting the Postgres storage get for vCon: %s", vcon_uuid)
    db = None
    try:
        # Connect to Postgres
        db = get_db_connection(opts)
        BaseModel._meta.database = db

        # Attempt to retrieve the vCon
        try:
            vcon = Vcons.get(Vcons.id == vcon_uuid)
            return vcon.vcon_json
        except Vcons.DoesNotExist:
            logger.info(f"vCon {vcon_uuid} not found in Postgres storage")
            return None
            
    except Exception as e:
        logger.error(
            f"postgres storage plugin: failed to get vCon: {vcon_uuid}, error: {e}"
        )
        return None
    finally:
        if db:
            db.close()
