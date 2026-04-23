"""End-to-end chain test: API -> Redis -> chain link -> storage.

Posts a vCon via the FastAPI TestClient, drives the posted vCon through a
VconChainRequest in-process with a `tag` link and `file` storage backend,
then asserts the file-storage artifact contains the tag the link added.

Marked `integration` because it requires a running redis-stack (for RedisJSON).
Run with: pytest -m integration tests/integration/test_e2e_chain.py

Uses shared fixtures from the root conftest.py (`sample_vcon`, `redis_client`,
`minimal_config`) as an exemplar migration for V4.
"""
from __future__ import annotations

import json

import pytest


pytestmark = pytest.mark.integration


def test_e2e_chain_api_to_file_storage(
    sample_vcon, redis_client, minimal_config, monkeypatch
):
    """Full path: POST /vcon -> ingress list -> chain -> file storage.

    Verifies (a) the api accepted and queued the vCon, (b) the chain ran the
    `tag` link which mutated the vCon, (c) the `file` storage backend wrote
    the mutated vCon to disk with the tag.
    """
    cfg = minimal_config(
        link_module="links.tag",
        link_opts={"tags": ["e2e_verified"]},
        chain_name="e2e_chain",
        ingress_list="e2e_ingress",
    )

    # settings.py captures CONSERVER_CONFIG_FILE at module import, so env var
    # alone won't affect get_config() once settings has been imported.
    import settings as _settings

    monkeypatch.setattr(_settings, "CONSERVER_CONFIG_FILE", str(cfg["config_path"]))

    import api
    import main as conserver_main
    from config import get_config
    from fastapi.testclient import TestClient
    from settings import CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME

    # Rebuild cached config inside conserver.main so the chain processor sees it.
    conserver_main.config = get_config()
    chain_details = {
        "name": cfg["chain_name"],
        **conserver_main.config["chains"][cfg["chain_name"]],
    }

    vcon = sample_vcon()
    vcon_uuid = vcon["uuid"]

    token = CONSERVER_API_TOKEN or "default_token"
    header = CONSERVER_HEADER_NAME or "X-API-Token"
    with TestClient(api.app, headers={header: token}) as client:
        response = client.post(
            "/vcon", json=vcon, params={"ingress_lists": [cfg["ingress_list"]]}
        )
        assert response.status_code == 201, response.text

    # Verify the vCon landed in the ingress list.
    queued = redis_client.lrange(cfg["ingress_list"], 0, -1)
    assert vcon_uuid in queued, (
        f"vCon {vcon_uuid} missing from ingress list: {queued}"
    )

    # Drive the chain in-process (no worker subprocess needed).
    req = conserver_main.VconChainRequest(chain_details, vcon_uuid)
    req.process()

    # File storage should contain the vCon, with the tag attachment written by
    # the `tag` link.
    out_path = cfg["storage_dir"] / f"{vcon_uuid}.json"
    assert out_path.exists(), f"Expected storage artifact at {out_path}"
    stored = json.loads(out_path.read_text())

    tag_attachments = [
        a for a in stored.get("attachments", []) if a.get("type") == "tags"
    ]
    assert tag_attachments, "tag link did not write a tags attachment"
    body = tag_attachments[0]["body"]
    assert any("e2e_verified" in entry for entry in body), (
        f"Expected 'e2e_verified' tag in {body}"
    )

    # Cleanup so the test is idempotent across runs against the same Redis.
    redis_client.delete(cfg["ingress_list"])
    redis_client.delete(f"vcon:{vcon_uuid}")
