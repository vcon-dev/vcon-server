# Contributing

This page gets you from a fresh clone to a passing test run and a clean docs check, so your change reaches review without a CI surprise.

Report bugs and propose changes through [GitHub issues](https://github.com/vcon-dev/vcon-server/issues) and pull requests against `main`.

## Learn the repository layout

| Path | Contents |
|---|---|
| `api/` | The FastAPI service |
| `conserver/` | The worker: `main.py`, `links/`, `tracers/`, hooks and the follower |
| `common/` | Code both services import: `vcon.py`, `lib/`, `storage/`, `settings.py`, `config.py` |
| `tests/` | Core and storage tests. `common/tests/`, `conserver/tests/` and each link folder hold more |
| `docker/` | `Dockerfile` for development and CI, plus `Dockerfile.api` and `Dockerfile.conserver` for production images |
| `docs/` | This site. `scripts/docs/` holds the generators and the docs check |

## Set up with uv

The project uses [uv](https://docs.astral.sh/uv/) and `uv.lock`. It needs Python `>=3.12,<3.14`.

Dependencies sit in groups, and a plain `uv sync` installs only the core and `dev` groups. Those are not enough to import the services, so name the groups:

```bash
uv sync --group conserver --group api --group storage-milvus
```

| Group | Adds |
|---|---|
| `dev` | pytest, black and test tools. Installed by default |
| `storage` | Storage backend clients. Pulled in by `api` and `conserver` |
| `api` | FastAPI, uvicorn and `storage` |
| `conserver` | Link dependencies, watchdog and `storage` |
| `storage-milvus` | The Milvus client. Kept out of the production images |
| `conserver-local` | transformers, for the local model path in [hugging_llm_link](reference/links/hugging-llm.md) |

Change dependencies with `uv add` or by editing `pyproject.toml` and running `uv lock`. Commit `uv.lock` with the change. The Dockerfiles install with `--frozen`, so a dependency missing from the lock file never reaches the image.

## Mind the import paths

Four directories go on the Python path: the repo root, `common`, `conserver` and `api`. `pytest.ini` sets them for tests and `docker/Dockerfile` sets `PYTHONPATH` for the image.

- Shared code imports from `lib`, for example `from lib.vcon_redis import VconRedis`.
- Queue work goes through `VconQueue` in `lib.queue`.
- Links live in `conserver/links/` and load as `links.<name>`. Storage adapters load as `storage.<name>`.
- `import vcon` finds `common/vcon.py` first, not the `vcon` package from `pyproject.toml`. Links run on the local class, so read that file to see which methods exist.

To run a script outside pytest, set the path yourself:

```bash
PYTHONPATH=.:common:conserver:api uv run python your_script.py
```

## Run the tests

Run the suite in the container, as CI does. Many tests need Redis, and the container has it. Start the stack first, as the [quick start](getting-started/quick-start.md) shows.

```bash
docker compose run --rm conserver pytest
```

Pick a path to run part of it:

```bash
docker compose run --rm conserver pytest conserver/links/analyze/tests/ -v
```

CI also adds coverage:

```bash
docker compose run --rm conserver pytest --maxfail=5 --disable-warnings --cov --cov-report=term-missing:skip-covered
```

Tests that mock Redis also run on the host, which is quicker for a link you are working on:

```bash
uv run pytest conserver/links/tag
```

On the host, tests that need Redis error out unless one is listening at `REDIS_URL`, default `redis://localhost`. The `integration` marker does not separate them, so `-m "not integration"` does not avoid this.

If your `.env` was copied from `.env.example`, fix `LOGGING_CONFIG_FILE` first, as the [quick start](getting-started/quick-start.md#set-the-environment) describes. Collection fails otherwise.

### Enable the vendor tests

Tests that call Deepgram, OpenAI or Groq skip without credentials. To run them, copy the template and fill it in:

```bash
cp .env.test.example .env.test
```

`pytest.ini` loads `.env.test` before collection. Git ignores that file. Never commit real keys.

## Format your code

`pyproject.toml` configures black with a line length of 120 and no string normalization. Format the code you change, and leave the rest of the file alone to keep the diff small. Not every file in the repo is black clean.

```bash
uv run black path/to/changed_file.py
```

## Change the docs

The site uses MkDocs Material. Run the same check as CI, which needs uv and Node:

```bash
bash scripts/docs/check.sh
```

It runs the generators, renders every diagram and builds the site with `--strict`. To build the site alone:

```bash
NO_MKDOCS_2_WARNING=1 uvx --with mkdocs-material mkdocs build --strict -d /tmp/vcon-site
```

Follow these rules:

- Take every claim from the code. Old docs drift.
- Never hand edit a generated page: [environment](reference/environment.md), [ports](reference/ports.md), [API routes](reference/api-routes.md) and [metrics](reference/metrics.md). Edit the code, or `scripts/docs/descriptions.yml` for the prose, then rerun the check.
- Change a diagram in its `.mmd` source and commit the SVG. See `docs/diagrams/README.md`.
- Example vCons use `"vcon": "0.4.0"`.
- Link to reference pages. Do not copy them.

## Add a link, adapter or tracer

Start from the guides: [creating links](extending/creating-links.md), [creating storage adapters](extending/creating-storage-adapters.md) and [creating tracers](extending/creating-tracers.md). Add tests next to the code and a page under `docs/reference/`.

## Keep the consent boundary

Active consent management is outside this repository. The server carries `lawful_basis` attachments and never creates, validates or enforces them. See [lawful basis](concepts/lawful-basis.md) and [editions](concepts/editions.md). Keep contributions and docs within that boundary, and never describe the server as making a deployment compliant.

## Open a pull request

- Branch from `main` and keep each pull request to one change.
- Keep `.env`, `.env.test`, `config.yml` and any scratch folders out of commits.
- Leave personal and company names out of issues, commits and pull requests. This repo is public, so write "a partner" or "the customer".
- CI runs the tests and the docs check on every pull request.

## Understand releases

Pushing to `main` builds and publishes the images tagged `main-<sha>` and `latest`. Pushing a `v*` tag publishes semver tags such as `1.2.3`, `1.2` and `1`. The tag push is the release. See [upgrading](installation/upgrading.md).
