# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands
- Install dependencies: `poetry install`
- Run server: `docker compose up -d`
- Scale up server: `docker compose up --scale conserver=4 -d`
- Run single test: `poetry run pytest path/to/test_file.py::test_function_name -v`
- Run all tests: `poetry run pytest`
- Format code: `poetry run black .`

## Code Style Guidelines
- Use black for formatting (line length 120, skip string normalization)
- Type annotations are required for function parameters and return values
- Error handling: Use try/except with specific exceptions, log errors with logger
- Imports: Group stdlib, third-party, and local imports separated by blank lines
- Use docstrings for classes, methods, and functions with Args/Returns/Raises
- Tests: Use pytest fixtures, mocks for external services, descriptive test names
- Logging: Use structured logging with appropriate levels (info, debug, error)
- Follow PEP 8 naming conventions (snake_case for functions/variables)
- Use retry patterns with tenacity for external services