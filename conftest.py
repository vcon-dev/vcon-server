# conftest.py
import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_env(pytestconfig):
    load_dotenv(".env.test")
