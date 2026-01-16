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

# LLM Configuration
# Default model used when not specified in link options
LLM_DEFAULT_MODEL = os.getenv("LLM_DEFAULT_MODEL", "gpt-3.5-turbo")
LLM_DEFAULT_TEMPERATURE = float(os.getenv("LLM_DEFAULT_TEMPERATURE", "0"))
LLM_DEFAULT_TIMEOUT = float(os.getenv("LLM_DEFAULT_TIMEOUT", "120"))

# Additional LLM Provider API Keys
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

VCON_STORAGE = os.getenv("VCON_STORAGE", "")
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

# Context expiration time in seconds (default 1 day)
# Context data stored for ingress operations will expire after this time
# to prevent memory leaks when the same vCon UUID is added multiple times.
VCON_CONTEXT_EXPIRY = int(os.getenv("VCON_CONTEXT_EXPIRY", 86400))

CONSERVER_CONFIG_FILE = os.getenv("CONSERVER_CONFIG_FILE", "./example_config.yml")
API_ROOT_PATH = os.getenv("API_ROOT_PATH", "/api")
