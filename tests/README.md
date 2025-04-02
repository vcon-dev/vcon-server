# Tests for vCon Server

This directory contains tests for the vCon server components.

## Running Tests

Tests use the standard pytest framework. You can run tests from the project root with:

```bash
# Run all tests
pytest

# Run tests with more verbose output
pytest -v

# Run tests for a specific module
pytest tests/server/storage/mongo/

# Run a specific test file
pytest tests/server/storage/mongo/test_mongo_storage.py

# Run a specific test function
pytest tests/server/storage/mongo/test_mongo_storage.py::TestMongoStorage::test_save_success
```

## Test Categories

Some tests are categorized using pytest markers:

### Integration Tests

Tests marked with `@pytest.mark.integration` require external services (like MongoDB) to be running.

To run integration tests:

```bash
# Run only integration tests
pytest -m integration

# Run all tests except integration tests
pytest -m "not integration"
```

## Test Configuration

Test configuration is managed through:

1. `pytest.ini` at the project root
2. `conftest.py` files at various levels in the test hierarchy

The configuration sets up:
- Custom markers like "integration"
- Python import paths
- Fixtures for test data and mocks 