"""Integration tests: invalid vCons must be rejected at the pipeline entry point.

Any JSON file placed in the invalid_fixtures/ directory is automatically picked
up and posted to the API. Every fixture is expected to be rejected with HTTP 422
before it can enter the conserver pipeline.
"""

import json
import os

import pytest
from fastapi.testclient import TestClient

import api
from settings import CONSERVER_API_TOKEN, CONSERVER_HEADER_NAME

_INVALID_FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "invalid_fixtures")

_invalid_fixtures = [
    f for f in os.listdir(_INVALID_FIXTURES_DIR) if f.endswith(".json")
]


@pytest.mark.integration
@pytest.mark.parametrize("filename", _invalid_fixtures)
def test_invalid_vcon_rejected_by_pipeline(filename):
    """Invalid vCons must be rejected with 422 and never enter the pipeline."""
    filepath = os.path.join(_INVALID_FIXTURES_DIR, filename)
    with open(filepath) as f:
        invalid_vcon = json.load(f)

    token = CONSERVER_API_TOKEN or "default_token"
    header = CONSERVER_HEADER_NAME or "X-API-Token"

    with TestClient(app=api.app, headers={header: token}) as client:
        response = client.post("/vcon", json=invalid_vcon)

    assert response.status_code == 422, (
        f"{filename} was not rejected — got {response.status_code}: {response.json()}"
    )
