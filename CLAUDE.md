# vCon Server

Open source pipeline for vCon conversation records: a FastAPI service, a worker that runs chains of links, and plain Redis between them. Human docs start at `docs/index.md`. Developer setup is in `docs/contributing.md`.

## Layout

- `api/api.py`: the REST API
- `conserver/main.py`: the worker. `conserver/links/` holds links, `conserver/tracers/` holds tracers
- `common/`: shared code. `vcon.py`, `lib/`, `storage/`, `settings.py`, `config.py`
- `tests/`, `common/tests/`, `conserver/tests/`, and tests inside each link folder
- `docker/`: `Dockerfile` for dev and CI, `Dockerfile.api` and `Dockerfile.conserver` for production
- `scripts/docs/`: doc generators and `check.sh`

## Commands

The toolchain is uv with `uv.lock`, never Poetry.

```bash
uv sync --group conserver --group api --group storage-milvus   # plain uv sync cannot import the services
uv lock                                                        # after a dependency change
uv run pytest conserver/links/tag                              # host, tests that mock Redis
docker compose run --rm conserver pytest                       # everything, as CI does
uv run black path/to/changed_file.py                           # line length 120, changed files only
```

Many tests need Redis, and `-m "not integration"` does not exclude them. `docker compose` needs `.env`, `config.yml` and the `conserver` network: see `docs/getting-started/quick-start.md`.

## Docs check

```bash
bash scripts/docs/check.sh
```

It runs the generators, renders the diagrams and runs `mkdocs build --strict`. Never hand edit `docs/reference/environment.md`, `ports.md`, `api-routes.md` or `metrics.md`.

## Import path trap

The path holds the repo root, `common`, `conserver` and `api` (`pytest.ini`, `docker/Dockerfile`). So:

- `import vcon` resolves to `common/vcon.py`, not the `vcon` package in `pyproject.toml`. Check that file before you call a method.
- Import shared code as `lib.*`: `from lib.vcon_redis import VconRedis`. Use `lib.queue.VconQueue` for queue work.
- Links live in `conserver/links`, not `server/links`, and load as `links.<name>`.
- Vendor transcribe modules are deprecated. Use `links.transcribe`.
- Redis is plain Redis. RedisJSON and Redis Stack appear only in the migration path.

## Consent boundary

Active consent management is outside this repo. The server carries and preserves `lawful_basis` attachments. It never creates, validates, enforces or manages consent, and it does not make a deployment compliant. A missing consent feature here is by design and not a bug. Do not add one, and do not document one. See `docs/concepts/lawful-basis.md`.

## Rules

- Example vCons use `"vcon": "0.4.0"`.
- Keep personal and company names out of issues, commits and pull requests.
- There is no product version. `pyproject.toml` holds a placeholder.
