# Manual Installation

This guide covers installing vCon Server manually for development or customized deployments.

## Prerequisites

- Python 3.12 or later
- Poetry 2.0 or later
- Redis 7.0 or later
- Git

## Installation Steps

### Step 1: Install Python 3.12

=== "Ubuntu/Debian"

    ```bash
    sudo apt update
    sudo apt install python3.12 python3.12-venv python3.12-dev
    ```

=== "macOS"

    ```bash
    brew install python@3.12
    ```

=== "Windows"

    Download from [python.org](https://www.python.org/downloads/) or use:
    ```powershell
    winget install Python.Python.3.12
    ```

### Step 2: Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -

# Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
poetry --version
```

### Step 3: Install Redis

=== "Ubuntu/Debian"

    ```bash
    sudo apt install redis-server
    sudo systemctl enable redis-server
    sudo systemctl start redis-server
    ```

=== "macOS"

    ```bash
    brew install redis
    brew services start redis
    ```

=== "Docker"

    ```bash
    docker run -d --name redis -p 6379:6379 redis:7
    ```

Verify Redis is running:

```bash
redis-cli ping
# Should return: PONG
```

### Step 4: Clone Repository

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
```

### Step 5: Install Dependencies

```bash
poetry install
```

This installs all required Python packages in a virtual environment.

### Step 6: Configure Environment

Create a `.env` file:

```bash
cp .env.example .env
```

Edit with your settings:

```bash
# Required
REDIS_URL=redis://localhost:6379
CONSERVER_API_TOKEN=your-development-token

# Optional: AI services
DEEPGRAM_KEY=your-key
OPENAI_API_KEY=your-key

# Development settings
ENV=dev
LOG_LEVEL=DEBUG
```

### Step 7: Configure Processing

Copy the example configuration:

```bash
cp example_config.yml config.yml
```

Point to it in your environment:

```bash
export CONSERVER_CONFIG_FILE=./config.yml
```

### Step 8: Run the Server

Start the conserver (processing worker):

```bash
poetry run python ./server/main.py
```

In a separate terminal, start the API server:

```bash
poetry run uvicorn server.api:app --reload --host 0.0.0.0 --port 8000
```

### Step 9: Verify Installation

```bash
# Check health
curl http://localhost:8000/api/health

# Check version
curl http://localhost:8000/api/version
```

## Development Mode

### Auto-Reload

For development, use watchdog for auto-reload on code changes:

```bash
# Install watchdog
poetry add watchdog --group dev

# Run with auto-reload
poetry run watchmedo auto-restart \
  --directory=./server \
  --pattern="*.py" \
  --recursive \
  -- python ./server/main.py
```

### Debug Logging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
export LOGGING_CONFIG_FILE=./server/logging_dev.conf
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run specific test file
poetry run pytest server/tests/test_api.py

# Run with coverage
poetry run pytest --cov=server
```

## Installing Optional Dependencies

### FFmpeg (for audio processing)

=== "Ubuntu/Debian"

    ```bash
    sudo apt install ffmpeg
    ```

=== "macOS"

    ```bash
    brew install ffmpeg
    ```

### SoX (for audio manipulation)

=== "Ubuntu/Debian"

    ```bash
    sudo apt install sox libsox-fmt-all
    ```

=== "macOS"

    ```bash
    brew install sox
    ```

## Storage Backend Setup

### PostgreSQL

=== "Ubuntu/Debian"

    ```bash
    sudo apt install postgresql postgresql-contrib
    sudo systemctl start postgresql
    
    # Create database
    sudo -u postgres createuser vcon
    sudo -u postgres createdb -O vcon vcon_server
    ```

=== "macOS"

    ```bash
    brew install postgresql@15
    brew services start postgresql@15
    
    createuser vcon
    createdb -O vcon vcon_server
    ```

=== "Docker"

    ```bash
    docker run -d --name postgres \
      -e POSTGRES_USER=vcon \
      -e POSTGRES_PASSWORD=vcon \
      -e POSTGRES_DB=vcon_server \
      -p 5432:5432 \
      postgres:15
    ```

### MongoDB

=== "Ubuntu/Debian"

    ```bash
    # Follow MongoDB installation guide for your Ubuntu version
    # https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/
    ```

=== "macOS"

    ```bash
    brew tap mongodb/brew
    brew install mongodb-community
    brew services start mongodb-community
    ```

=== "Docker"

    ```bash
    docker run -d --name mongo \
      -e MONGO_INITDB_ROOT_USERNAME=root \
      -e MONGO_INITDB_ROOT_PASSWORD=example \
      -p 27017:27017 \
      mongo:6
    ```

## Project Structure

Understanding the project structure helps with development:

```
vcon-server/
├── server/
│   ├── __init__.py
│   ├── api.py              # FastAPI application
│   ├── main.py             # Worker entry point
│   ├── config.py           # Configuration loading
│   ├── settings.py         # Environment settings
│   ├── vcon.py             # vCon data model
│   ├── lib/                # Shared utilities
│   │   ├── vcon_redis.py   # Redis operations
│   │   ├── logging_utils.py
│   │   └── ...
│   ├── links/              # Processing links
│   │   ├── analyze/
│   │   ├── deepgram_link/
│   │   ├── tag/
│   │   └── ...
│   ├── storage/            # Storage adapters
│   │   ├── postgres/
│   │   ├── mongo/
│   │   ├── s3/
│   │   └── ...
│   └── tests/              # Test files
├── docker/
│   └── Dockerfile
├── scripts/
│   └── install_conserver.sh
├── pyproject.toml          # Poetry configuration
├── example_config.yml      # Example configuration
└── .env.example            # Example environment
```

## IDE Setup

### VS Code

Recommended extensions:

- Python (Microsoft)
- Pylance
- Python Test Explorer

Settings (`.vscode/settings.json`):

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["server/tests"],
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true
}
```

### PyCharm

1. Open the project folder
2. Configure Poetry interpreter: Settings > Project > Python Interpreter > Add > Poetry Environment
3. Mark `server` as Sources Root

## Troubleshooting

### Poetry Install Fails

Clear cache and retry:

```bash
poetry cache clear . --all
poetry install
```

### Redis Connection Refused

Check Redis is running:

```bash
redis-cli ping
```

Check the URL in `.env`:

```bash
REDIS_URL=redis://localhost:6379
```

### Import Errors

Ensure you're in the Poetry environment:

```bash
poetry shell
python ./server/main.py
```

Or prefix commands with `poetry run`:

```bash
poetry run python ./server/main.py
```

### Module Not Found

Install missing dependencies:

```bash
poetry install --all-extras
```

## Next Steps

- [Configuration Guide](../configuration/index.md) - Customize your setup
- [Creating Links](../extending/creating-links.md) - Develop custom processors
- [Running Tests](../operations/troubleshooting.md) - Test your changes
