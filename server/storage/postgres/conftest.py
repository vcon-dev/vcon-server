import pytest
import subprocess
import time
import psycopg2
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def postgres_server():
    """Start a PostgreSQL container for testing."""
    
    container_name = "test-postgres-vcon"
    
    # Clean up any existing container
    subprocess.run(["docker", "rm", "-f", container_name], 
                   capture_output=True, text=True)
    
    logger.info("Starting PostgreSQL container for tests...")
    
    # Start new container
    result = subprocess.run([
        "docker", "run", "-d",
        "--name", container_name,
        "-e", "POSTGRES_PASSWORD=testpassword123",
        "-e", "POSTGRES_USER=vcon_test",
        "-e", "POSTGRES_DB=vcon_test_db",
        "-p", "5433:5432",  # Use port 5433 to avoid conflicts
        "postgres:15"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start PostgreSQL container: {result.stderr}")
    
    # Wait for PostgreSQL to be ready
    postgres_config = {
        "name": "postgres",
        "database": "vcon_test_db",
        "user": "vcon_test",
        "password": "testpassword123",
        "host": "localhost",
        "port": 5433
    }
    
    logger.info("Waiting for PostgreSQL to be ready...")
    for attempt in range(60):  # Wait up to 60 seconds
        try:
            conn = psycopg2.connect(
                host=postgres_config["host"],
                port=postgres_config["port"],
                user=postgres_config["user"],
                password=postgres_config["password"],
                database=postgres_config["database"]
            )
            conn.close()
            logger.info("PostgreSQL is ready!")
            break
        except psycopg2.OperationalError:
            time.sleep(1)
    else:
        # Cleanup on failure
        subprocess.run(["docker", "rm", "-f", container_name], 
                       capture_output=True, text=True)
        raise RuntimeError("PostgreSQL failed to start within 60 seconds")
    
    yield postgres_config
    
    # Cleanup
    logger.info("Cleaning up PostgreSQL container...")
    subprocess.run(["docker", "rm", "-f", container_name], 
                   capture_output=True, text=True)


@pytest.fixture
def postgres_options(postgres_server):
    """Provide PostgreSQL connection options for testing."""
    return postgres_server


@pytest.fixture
def clean_postgres_db(postgres_server):
    """Provide a clean PostgreSQL database for each test."""
    from server.storage.postgres import get_db_connection, Vcons, BaseModel
    
    # Connect to database
    db = get_db_connection(postgres_server)
    
    # Properly associate models with the database connection
    BaseModel._meta.database = db
    Vcons._meta.database = db
    
    # Drop and recreate tables for clean state
    db.drop_tables([Vcons], safe=True)
    db.create_tables([Vcons], safe=True)
    
    yield postgres_server
    
    # Cleanup after test - handle potential connection issues gracefully
    try:
        db.drop_tables([Vcons], safe=True)
        db.close()
    except Exception as e:
        # Log the error but don't fail the test
        logger.warning(f"Cleanup error (this is expected for error handling tests): {e}")
        # Try to close the connection anyway
        try:
            db.close()
        except:
            pass