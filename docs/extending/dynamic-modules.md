# Load dynamic modules

The conserver can import a link or tracer from outside the repo, and install it with `pip` if it is missing. This page shows how to configure that and when to avoid it.

## Add a module to the configuration

Give a link or tracer a `module` to import and a `pip_name` to install.

```yaml
links:
  pypi_link:
    module: custom_link_package.main
    pip_name: custom-link-package==1.2.3
    options:
      setting: value

  git_link:
    module: git_link.processor
    pip_name: git+https://github.com/username/repo.git@v1.2.3
    options:
      setting: value
```

`pip_name` defaults to `module`. It accepts any single requirement that `pip install` accepts, including a branch or tag after `@`.

Use the `imports` section to load a module when each worker starts, rather than when a vCon first reaches it:

```yaml
imports:
  custom_utility:
    module: custom_utils
    pip_name: custom-utils-package
  requests_import:
    module: requests
  legacy_module: some.legacy.module   # Older form: the module name alone
```

See [YAML configuration](../configuration/yaml-configuration.md#import-extra-modules) for the section itself.

Storage adapters do not use this. The server imports them by name and ignores `pip_name`, so their packages must already be installed.

## Learn the loading rules

1. The conserver tries to import `module`.
2. If that raises `ModuleNotFoundError`, it runs `python -m pip install <pip_name>` and imports again.
3. It keeps the module for the life of the process.

Each worker process does this for itself.

| Fact | Effect |
|---|---|
| `pip` runs only when the import fails | Changing a pinned version does not upgrade a module that is already installed |
| The install lands in the running environment | A new container starts without it and installs it again |
| A failure in `imports` raises | The worker stops at startup |
| A failure for a link raises when a vCon reaches it | That vCon moves to the dead letter queue |
| `pip_name` is passed as one argument, with no shell | `${VAR}` is not expanded, and extra flags such as `--index-url` do not work |

`pip` must exist in the environment. The published images include it. For a manual install, create the environment with `uv venv --seed`, as in [Install from source](../installation/manual-installation.md#install-the-dependencies).

## Bake modules into an image

For production, install modules at build time. A deployment then needs no network access to a package index at runtime, and every worker has the same version.

```dockerfile
FROM public.ecr.aws/r4g1k2s3/vcon-dev/vcon-server-conserver:<version>
RUN pip install custom-link-package==1.2.3
```

Keep `module` in the configuration and leave out `pip_name`.

## Reach a private package

The server does not expand environment variables in `config.yml` or in `pip_name`. Give `pip` its credentials through its own channels:

- For a private index, set `PIP_INDEX_URL` in the conserver's environment.
- For a private Git repo, use `git+ssh://git@github.com/org/repo.git` with a key in the container, or a Git credential helper.
- A token written into `pip_name` works, but it sits in plain text in `config.yml` and comes back from `GET /config`.

## Package a module

```
my-vcon-link/
  pyproject.toml
  README.md
  my_link/
    __init__.py
```

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "my-vcon-link"
version = "1.0.0"
description = "Custom vCon processing link"
requires-python = ">=3.12"
dependencies = [
    "requests>=2.31.0",
]
```

The module follows the [link contract](creating-links.md#follow-the-link-contract). It imports server code such as `lib.vcon_redis` from the running server, so do not list those as dependencies. Tests outside the repo need the server's `common/` on the path, or a stub.

```python
# my_link/__init__.py

from lib.logging_utils import init_logger
from lib.vcon_redis import VconRedis

logger = init_logger(__name__)

default_options = {
    "setting": "default",
}


def run(vcon_uuid, link_name, opts=default_options):
    options = {**default_options, **(opts or {})}

    vcon_redis = VconRedis()
    vcon = vcon_redis.get_vcon(vcon_uuid)
    if vcon is None:
        return None

    # Your processing logic

    vcon_redis.store_vcon(vcon)
    return vcon_uuid
```

Publish the package the way your project publishes everything else, ideally from CI on a tag push, and state which server image you tested against.

## Keep third-party code safe

Dynamic modules run with the same access as the conserver. That covers Redis, every vCon and all credentials in `config.yml`.

- Pin every `pip_name` to a version or tag.
- Read the code of a module before you add it, and scan its dependencies in your own CI.
- Install from sources you trust, and prefer [an image you built](#bake-modules-into-an-image).
- Protect global API keys. `POST /config` rewrites the configuration, and a worker that rereads it can then install what a new `pip_name` names.

## Handle a missing dependency

Import optional packages inside `run`, and raise a clear error so the vCon reaches the dead letter queue:

```python
def run(vcon_uuid, link_name, opts=default_options):
    try:
        import optional_dependency
    except ImportError as e:
        raise ImportError("Install optional-dependency to use this link") from e
```

## Troubleshoot a dynamic module

Run these in the conserver container.

| Check | Command |
|---|---|
| Is it installed | `pip list \| grep my-package` |
| Does it import | `python -c "import my_module; print(my_module)"` |
| Are there conflicts | `pip check` |
| Reinstall it | `pip install --force-reinstall my-package` |

The conserver log shows `Module <name> not found, attempting to install <pip_name>`, then either success or the `pip` error.

`No module named pip` means the environment was created without `--seed`.
