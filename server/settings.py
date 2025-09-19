import os
from pathlib import Path
import logging
import dotenv

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

logger.info("Reading settings")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")
TICK_INTERVAL = int(os.getenv("TICK_INTERVAL", 5000))
HOSTNAME = os.getenv("HOSTNAME", "http://localhost:8000")
ENV = os.getenv("ENV", "dev")
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
LOGGING_CONFIG_FILE = os.getenv("LOGGING_CONFIG_FILE", Path(__file__).parent / 'logging.conf')
CONSERVER_API_TOKEN = os.getenv("CONSERVER_API_TOKEN")
CONSERVER_API_TOKEN_FILE = os.getenv("CONSERVER_API_TOKEN_FILE")
CONSERVER_HEADER_NAME = os.getenv("CONSERVER_HEADER_NAME", "x-conserver-api-token")

DEEPGRAM_KEY = os.getenv("DEEPGRAM_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Fix VCON_STORAGE with better default and directory creation
default_storage_path = os.path.expanduser("~/.vcon/storage")
VCON_STORAGE = os.getenv("VCON_STORAGE")
if not VCON_STORAGE:
    VCON_STORAGE = default_storage_path

# Ensure the storage directory exists
try:
    os.makedirs(VCON_STORAGE, exist_ok=True)
    logger.info(f"Using VCON storage directory: {VCON_STORAGE}")
except OSError as e:
    logger.warning(f"Could not create storage directory {VCON_STORAGE}: {e}")

INDEX_NAME = "vcon"
WEVIATE_HOST = os.getenv("WEVIATE_HOST", "localhost:8000")
WEVIATE_API_KEY = os.getenv('WEVIATE_API_KEY')
VCON_SORTED_FORCE_RESET = os.getenv("VCON_SORTED_FORCE_RESET", "true")
VCON_SORTED_SET_NAME = os.getenv("VCON_SORTED_SET_NAME", "vcons")

# Index expiration time in seconds (default 1 day)
VCON_INDEX_EXPIRY = int(os.getenv("VCON_INDEX_EXPIRY", 86400))

# Redis expiration time in seconds (default 1 hour)
# When a vCon is fetched from a storage backend because it's not in Redis,
# it will be stored back in Redis with this expiration time.
# This improves performance for subsequent requests for the same vCon.
VCON_REDIS_EXPIRY = int(os.getenv("VCON_REDIS_EXPIRY", 3600))

# Fix CONSERVER_CONFIG_FILE with proper path resolution
config_file_env = os.getenv("CONSERVER_CONFIG_FILE")
if config_file_env and config_file_env.strip():
    CONSERVER_CONFIG_FILE = config_file_env
else:
    # Use the path relative to this settings.py file
    current_dir = Path(__file__).parent
    potential_config_paths = [
        current_dir / "example_config.yml",
        current_dir / "../example_config.yml",  # If settings.py is in a subdirectory
        Path.cwd() / "example_config.yml",     # Current working directory
    ]
    
    CONSERVER_CONFIG_FILE = None
    for config_path in potential_config_paths:
        if config_path.exists():
            CONSERVER_CONFIG_FILE = str(config_path)
            logger.info(f"Found config file at: {CONSERVER_CONFIG_FILE}")
            break
    
    if not CONSERVER_CONFIG_FILE:
        # Default to the first option and let the error handling elsewhere deal with it
        CONSERVER_CONFIG_FILE = str(current_dir / "example_config.yml")
        logger.warning(f"Config file not found, defaulting to: {CONSERVER_CONFIG_FILE}")

API_ROOT_PATH = os.getenv("API_ROOT_PATH", "/api")