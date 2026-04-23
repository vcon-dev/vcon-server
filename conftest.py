"""Root test fixtures.

Shared fixtures live here so test files across `tests/`, `common/tests/`, and
`conserver/tests/` can reuse them without re-deriving. If you find yourself
copy-pasting a fixture across test files, move it here.

Fixtures:
  - `load_env` (autouse, session): loads `.env.test` once per session
  - `sample_vcon`: factory → dict, builds a valid random vCon
  - `redis_client`: live Redis client (env var REDIS_URL), skip if unreachable
  - `minimal_config`: factory → dict, builds a small chain config (links, storages, chains)
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import pytest
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_env(pytestconfig):
    load_dotenv(".env.test")


def _build_vcon(
    *,
    num_parties: int = 2,
    num_dialogs: int = 1,
    num_analysis: int = 0,
    num_attachments: int = 0,
    extra: Optional[dict] = None,
) -> dict:
    """Build a deterministic-shape vCon. Random values, controlled cardinality."""
    now = datetime.now(timezone.utc).isoformat()
    vcon: dict[str, Any] = {
        "uuid": str(uuid.uuid4()),
        "vcon": "0.0.1",
        "created_at": now,
        "subject": None,
        "parties": [],
        "dialog": [],
        "analysis": [],
        "attachments": [],
        "group": [],
        "redacted": {},
        "appended": None,
    }
    for i in range(num_parties):
        vcon["parties"].append(
            {
                "name": f"Party{i}",
                "tel": f"+155500000{i:02d}",
                "mailto": f"party{i}@example.test",
                "meta": {"role": "agent" if i == 0 else "customer"},
            }
        )
    for i in range(num_dialogs):
        vcon["dialog"].append(
            {
                "type": "recording",
                "start": now,
                "parties": [0, min(1, max(0, num_parties - 1))],
                "duration": random.randint(60, 600),
                "mimetype": "audio/x-wav",
                "url": f"https://example.test/dialog-{i}.wav",
            }
        )
    for i in range(num_analysis):
        vcon["analysis"].append(
            {
                "type": "transcript",
                "dialog": 0,
                "vendor": "test",
                "encoding": "json",
                "body": json.dumps({"transcript": f"synthetic-{i}"}),
            }
        )
    for i in range(num_attachments):
        vcon["attachments"].append(
            {
                "type": "note",
                "body": f"attachment-{i}",
                "encoding": "none",
            }
        )
    if extra:
        vcon.update(extra)
    return vcon


@pytest.fixture
def sample_vcon() -> Callable[..., dict]:
    """Factory fixture for a valid vCon payload.

    Usage:
        vcon = sample_vcon()                    # defaults: 2 parties, 1 dialog
        vcon = sample_vcon(num_dialogs=3)       # custom shape
        vcon = sample_vcon(extra={"meta": {"k": "v"}})
    """
    return _build_vcon


@pytest.fixture
def redis_client():
    """Live Redis client. Skips the test if Redis is unreachable.

    Reads REDIS_URL from env (defaults to redis://localhost:6379). Tests that
    need RedisJSON should rely on redis-stack in docker-compose (CI) or a
    locally-started redis-stack container. This fixture does NOT start Redis.
    """
    import os

    try:
        import redis as redis_lib
    except ImportError:  # pragma: no cover
        pytest.skip("redis client library not installed")

    url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    client = redis_lib.Redis.from_url(url, decode_responses=True)
    try:
        client.ping()
    except Exception as exc:
        pytest.skip(f"Redis unreachable at {url}: {exc}")
    yield client
    try:
        client.close()
    except Exception:
        pass


@pytest.fixture
def minimal_config(tmp_path) -> Callable[..., dict]:
    """Factory fixture for a minimal chain config (link + storage + chain).

    Returns the config dict AND writes it to a yaml file at tmp_path/config.yml.
    Caller can monkeypatch settings.CONSERVER_CONFIG_FILE to point at that path.

    Usage:
        cfg = minimal_config(link_module="links.tag", link_opts={"tags": ["x"]})
        cfg["config_path"] is the yaml file path
        cfg["config"] is the config dict
        cfg["storage_dir"] is the file-storage output dir
    """

    def _factory(
        *,
        link_module: str = "links.tag",
        link_opts: Optional[dict] = None,
        storage_module: str = "storage.file",
        storage_opts: Optional[dict] = None,
        chain_name: str = "test_chain",
        ingress_list: str = "test_ingress",
    ) -> dict:
        import yaml

        storage_dir = tmp_path / "vcons"
        storage_dir.mkdir(exist_ok=True)

        link_opts = link_opts if link_opts is not None else {"tags": ["unit_test"]}
        storage_opts = storage_opts if storage_opts is not None else {
            "path": str(storage_dir),
            "organize_by_date": False,
            "compression": False,
        }

        config = {
            "links": {
                "link_0": {"module": link_module, "options": link_opts},
            },
            "storages": {
                "storage_0": {"module": storage_module, "options": storage_opts},
            },
            "chains": {
                chain_name: {
                    "links": ["link_0"],
                    "storages": ["storage_0"],
                    "ingress_lists": [ingress_list],
                    "egress_lists": [],
                    "enabled": 1,
                },
            },
        }
        config_path = tmp_path / "config.yml"
        config_path.write_text(yaml.safe_dump(config))
        return {
            "config": config,
            "config_path": config_path,
            "storage_dir": storage_dir,
            "chain_name": chain_name,
            "ingress_list": ingress_list,
        }

    return _factory
