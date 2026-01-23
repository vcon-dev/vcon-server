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

# Worker configuration for parallel processing
# Number of worker processes to spawn (default 1 = single-threaded mode)
CONSERVER_WORKERS = int(os.getenv("CONSERVER_WORKERS", 1))

# Enable parallel storage writes using ThreadPoolExecutor (default True)
CONSERVER_PARALLEL_STORAGE = os.getenv("CONSERVER_PARALLEL_STORAGE", "true").lower() in ("true", "1", "yes")

# Multiprocessing start method: "fork", "spawn", or "forkserver"
# - "fork" (default on Unix): Copy-on-write memory, fastest startup, but can cause
#   issues with threads and some libraries (OpenSSL, CUDA, etc.)
# - "spawn": Fresh Python interpreter per worker, higher memory but safer
# - "forkserver": Hybrid approach, spawns from a clean forked server process
# - "" or unset: Use Python's platform default (fork on Unix, spawn on Windows/macOS)
CONSERVER_START_METHOD = os.getenv("CONSERVER_START_METHOD", "").lower() or None
