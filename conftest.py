# conftest.py
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

@pytest.fixture(scope="session", autouse=True)
def load_env(pytestconfig):
    load_dotenv(".env.test")

@pytest.fixture(autouse=True)
def mock_redis_json_improved():
    """Improved Redis JSON mock that handles the JSON.SET command"""
    with patch('redis.Redis') as redis_mock:
        json_mock = MagicMock()
        redis_mock.return_value.json = MagicMock(return_value=json_mock)
        
        # Mock the set and get methods
        json_mock.set = MagicMock(return_value=True)
        json_mock.get = MagicMock(return_value={'data': 'mocked_data'})
        
        # Also mock the async version
        with patch('redis.asyncio.Redis') as async_redis_mock:
            async_json_mock = MagicMock()
            async_redis_mock.return_value.json = MagicMock(return_value=async_json_mock)
            
            # Async methods
            async def mock_set(*args, **kwargs):
                return True
                
            async def mock_get(*args, **kwargs):
                return {'data': 'mocked_data'}
                
            async_json_mock.set = mock_set
            async_json_mock.get = mock_get
            
            yield