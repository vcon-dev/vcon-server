import sys
import os
from pathlib import Path

# Get the absolute path to the server directory
server_dir = str(Path(__file__).parent.parent.parent.parent.absolute())

# Add to PYTHONPATH environment variable
os.environ["PYTHONPATH"] = f"{server_dir}:{os.environ.get('PYTHONPATH', '')}"

# Add to sys.path if not already there
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)
