# This file helps pytest properly discover test modules in Docker environments.
# It ensures that tests/storage is recognized as part of the tests package,
# not confused with server/storage due to pythonpath settings.
import sys
from pathlib import Path

# Get the project root directory (parent of tests/)
project_root = Path(__file__).parent.parent
server_dir = project_root / "server"

# Ensure both project root and server directory are in sys.path
# This matches the pythonpath setting in pytest.ini: "., server"
for path in [project_root, server_dir]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
