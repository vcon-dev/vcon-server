import os
import sys
from pathlib import Path

# Add the server directory to Python path for imports
server_dir = str(Path(__file__).parent)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)
