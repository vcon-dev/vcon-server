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

from typing import Optional, Dict, Any, Type
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
    "table_name": "vcons",  # Default table name
}


def create_vcons_model(database: PostgresqlExtDatabase, table_name: str = "vcons") -> Type[Model]:
    """
    Dynamically create a Vcons model class for the specified database and table.
    
    Args:
        database: The database connection to use
        table_name: The name of the table to use
        
    Returns:
        Type[Model]: A dynamically created Vcons model class
    """
    class DynamicVcons(Model):
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
    
    # Set the database and table_name after class creation
    DynamicVcons._meta.database = database
    DynamicVcons._meta.table_name = table_name
    
    return DynamicVcons


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
        table_name = opts.get("table_name", "vcons")
        
        # Create dynamic model for this database and table
        VconsModel = create_vcons_model(db, table_name)
        
        # Ensure table exists
        db.create_tables([VconsModel], safe=True)

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
        VconsModel.insert(**vcon_data).on_conflict(
            conflict_target=(VconsModel.id),
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
        table_name = opts.get("table_name", "vcons")
        
        # Create dynamic model for this database and table
        VconsModel = create_vcons_model(db, table_name)
        
        # Attempt to retrieve the vCon
        try:
            vcon = VconsModel.get(VconsModel.id == vcon_uuid)
            return vcon.vcon_json
        except VconsModel.DoesNotExist:
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


def delete(
    vcon_uuid: str,
    opts: Dict[str, Any] = default_options,
) -> bool:
    """
    Delete a vCon from PostgreSQL storage by UUID.
    
    Args:
        vcon_uuid: UUID of the vCon to delete
        opts: Dictionary containing database connection parameters
        
    Returns:
        bool: True if the vCon was successfully deleted, False if it was not found
        
    Raises:
        Exception: If there's an error deleting the vCon
    """
    logger.info("Starting the Postgres storage delete for vCon: %s", vcon_uuid)
    db = None
    try:
        # Connect to Postgres
        db = get_db_connection(opts)
        table_name = opts.get("table_name", "vcons")
        
        # Create dynamic model for this database and table
        VconsModel = create_vcons_model(db, table_name)
        
        # Attempt to delete the vCon
        try:
            deleted_count = VconsModel.delete().where(VconsModel.id == vcon_uuid).execute()
            if deleted_count > 0:
                logger.info("Successfully deleted vCon: %s", vcon_uuid)
                return True
            else:
                logger.info("vCon %s not found in Postgres storage", vcon_uuid)
                return False
                
        except Exception as e:
            logger.error(f"Failed to delete vCon {vcon_uuid}: {e}")
            raise e
            
    except Exception as e:
        logger.error(
            f"postgres storage plugin: failed to delete vCon: {vcon_uuid}, error: {e}"
        )
        raise e
    finally:
        if db:
            db.close()
