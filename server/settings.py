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

VCON_STORAGE = os.getenv("VCON_STORAGE", "")
INDEX_NAME = "vcon"
WEVIATE_HOST = os.getenv("WEVIATE_HOST", "localhost:8000")
WEVIATE_API_KEY = os.getenv('WEVIATE_API_KEY')
VCON_SORTED_FORCE_RESET = os.getenv("VCON_SORTED_FORCE_RESET", "true")
VCON_SORTED_SET_NAME = os.getenv("VCON_SORTED_SET_NAME", "vcons")

CONSERVER_CONFIG_FILE = os.getenv("CONSERVER_CONFIG_FILE", "./example_config.yml")
API_ROOT_PATH = os.getenv("API_ROOT_PATH", "/api")
