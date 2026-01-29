# conftest.py
import pytest
from dotenv import load_dotenv
from pathlib import Path


@pytest.fixture(scope="session", autouse=True)
def load_env(pytestconfig):
    # Prefer local, untracked secrets in `.env.test`. Fall back to a committed template
    # (`env.test.example`) so tests can run without creating `.env.test`.
    root = Path(__file__).resolve().parent
    local_env = root / ".env.test"
    example_env = root / "env.test.example"

    if local_env.exists():
        load_dotenv(local_env, override=True)
    elif example_env.exists():
        load_dotenv(example_env, override=True)
