# Install from source

This page runs the server from a checkout with [uv](https://docs.astral.sh/uv/), with no containers. Use it for development and debugging. The Dockerfiles use the same tool and the same `uv.lock`.

## Prepare the tools

You need Git, uv and Redis. `pyproject.toml` needs Python 3.12 or 3.13, and uv downloads a suitable Python if the host has none.

=== "Ubuntu/Debian"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    sudo apt install redis-server
    sudo systemctl enable --now redis-server
    ```

=== "macOS"

    ```bash
    brew install uv redis
    brew services start redis
    ```

You can run Redis in Docker instead:

```bash
docker run -d --name redis -p 6379:6379 redis:7.4-alpine
```

The server needs plain Redis and no modules. Check it with:

```bash
redis-cli ping
```

Links that process audio need FFmpeg and SoX, which the conserver image installs:

=== "Ubuntu/Debian"

    ```bash
    sudo apt install ffmpeg sox libsox-fmt-all
    ```

=== "macOS"

    ```bash
    brew install ffmpeg sox
    ```

## Install the dependencies

```bash
git clone https://github.com/vcon-dev/vcon-server.git
cd vcon-server
uv venv --seed --python 3.12
uv sync --group api --group conserver
```

`--seed` keeps `pip` in the environment. The server calls `pip` to install [dynamic modules](../extending/dynamic-modules.md), and `uv venv` leaves it out otherwise.

`uv sync` includes the `dev` group by default, which holds pytest. Add `--no-dev` to leave it out. The other groups in `pyproject.toml` are:

| Group | Adds |
|---|---|
| `api` | FastAPI, uvicorn and the `storage` group |
| `conserver` | Link packages, `watchdog` and the `storage` group |
| `storage` | Clients for the common storage backends |
| `storage-milvus` | The Milvus client, for `storage.milvus` |
| `conserver-local` | `transformers`, for local models in `hugging_llm_link` |

## Set the environment

```bash
cp .env.example .env
```

Change these lines in `.env`:

```bash
REDIS_URL=redis://localhost:6379
CONSERVER_API_TOKEN=your-development-token
CONSERVER_CONFIG_FILE=./config.yml
LOGGING_CONFIG_FILE=common/logging_dev.conf
```

The sample `LOGGING_CONFIG_FILE` points at a path that no longer exists, and the sample `CONSERVER_CONFIG_FILE` is empty. Either one stops the server. See the [environment reference](../reference/environment.md) for the rest.

The code imports from `common/`, `conserver/` and `api/` as top-level paths, so set `PYTHONPATH` in each shell. With these paths, `import vcon` loads `common/vcon.py`.

```bash
export PYTHONPATH=.:common:conserver:api
```

## Write the chain configuration

Create `config.yml` with the small file on the [Docker page](docker.md#write-the-chain-configuration). Do not run `example_config.yml` unchanged, because its `imports` section stops the worker.

## Start the server

Start the conserver:

```bash
uv run python conserver/main.py
```

In a second shell, with `PYTHONPATH` set, start the API:

```bash
uv run uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Check it:

```bash
curl http://localhost:8000/api/health
curl http://localhost:8000/api/version
```

To send a first vCon, follow the [quick start](../getting-started/quick-start.md), and use `localhost` for the host.

## Work on the code

Restart the conserver on code changes, as the Compose file does:

```bash
uv run watchmedo auto-restart -p '*.py' -R -- python conserver/main.py
```

Run the tests from the repo root. `pytest.ini` sets the import paths, and it loads `.env.test` if you create one from `.env.test.example`.

```bash
uv run pytest                                    # All tests
uv run pytest -m "not integration"               # Skip integration tests
uv run pytest tests/core/test_vcon_redis.py      # One file
uv run pytest conserver/links/tag                # One link
uv run pytest --cov --cov-report=html            # With coverage
```

Some tests need Redis at `REDIS_URL`, and some need provider keys. CI runs them in the Compose stack, and the [contributing guide](../contributing.md) covers that path.

## Find your way around the repo

```
vcon-server/
├── api/
│   └── api.py              # FastAPI app
├── common/                 # Shared by the API and the conserver
│   ├── config.py           # YAML loading
│   ├── settings.py         # Environment settings
│   ├── vcon.py             # The Vcon class that links use
│   ├── lib/                # VconRedis, VconQueue, metrics and helpers
│   └── storage/            # Storage adapters
├── conserver/
│   ├── main.py             # Worker entry point
│   ├── links/              # Processing links
│   └── tracers/            # Tracers
├── docker/                 # Dockerfiles and the Redis wait script
├── scripts/                # Install scripts and the Redis migration tool
├── tests/                  # Core and storage tests
├── docker-compose.yml
├── example_config.yml      # Syntax catalogue, not a working configuration
├── pyproject.toml
└── uv.lock
```

Each link and adapter keeps its tests beside its code.

## Set up your editor

Point the editor at `.venv/bin/python` and add the same import paths.

For VS Code, in `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.analysis.extraPaths": ["common", "conserver", "api"],
  "python.testing.pytestEnabled": true
}
```

For PyCharm, select the `.venv` interpreter and mark `common`, `conserver` and `api` as Sources Root.

## Troubleshoot a manual install

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'lib'` or `'settings'` | `PYTHONPATH` is not set | [Set the environment](#set-the-environment) |
| `ModuleNotFoundError: No module named 'fastapi'` | The `api` group is missing | Run `uv sync --group api --group conserver` |
| `FileNotFoundError: server/logging_dev.conf doesn't exist` | Sample `LOGGING_CONFIG_FILE` | [Set the environment](#set-the-environment) |
| `No module named pip` when a module installs | The environment was made without `--seed` | Remove `.venv` and repeat [the install](#install-the-dependencies) |
| `Connection refused` on Redis | Redis is down, or the URL is wrong | Run `redis-cli ping` and check `REDIS_URL` |
| An adapter fails to import | Its package group is missing | See the [storage adapter reference](../reference/storage-adapters/index.md#install-the-adapter-packages) |

## Continue with these guides

- [Configuration guide](../configuration/index.md)
- [Creating links](../extending/creating-links.md)
- [Contributing](../contributing.md)
