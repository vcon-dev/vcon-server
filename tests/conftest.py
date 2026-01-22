# This file helps pytest properly discover test modules in Docker environments.
# It ensures that tests/storage is recognized as part of the tests package,
# not confused with server/storage due to pythonpath settings.
import sys
from pathlib import Path

# Ensure the tests directory is in sys.path
tests_dir = Path(__file__).parent
if str(tests_dir) not in sys.path:
    sys.path.insert(0, str(tests_dir))
