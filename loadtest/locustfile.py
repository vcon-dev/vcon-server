"""Load-test scenarios for vcon-server.

Run against a fully deployed stack (api + conserver worker + redis).
Captures baseline throughput/latency for the two hottest paths:

1. POST /vcon (ingress throughput, tests the api path)
2. POST /vcon with ingress_lists (ingress throughput + worker-chain enqueue)

Usage (one-off, 30s, 20 users):

    uv sync --group loadtest
    CONSERVER_API_TOKEN=... CONSERVER_API_URL=http://localhost:8000 \\
        uv run locust -f loadtest/locustfile.py \\
        --host=$CONSERVER_API_URL --headless -u 20 -r 5 -t 30s \\
        --csv=loadtest/baseline

The --csv flag writes three CSVs (stats, stats_history, failures) that capture
the baseline. Commit a relevant baseline_*.md summary alongside refactors.

Worker-chain throughput is exercised implicitly — the worker will consume from
the `loadtest_ingress` list. For a pure chain-throughput test, seed the list
directly with redis-cli (see loadtest/README.md).
"""
from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timezone

from locust import HttpUser, between, task


INGRESS_LIST = os.environ.get("LOADTEST_INGRESS_LIST", "loadtest_ingress")
API_TOKEN = os.environ.get("CONSERVER_API_TOKEN", "")
API_HEADER = os.environ.get("CONSERVER_HEADER_NAME", "x-conserver-api-token")


def _minimal_vcon() -> dict:
    """Minimal valid vCon payload for ingress load."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "uuid": str(uuid.uuid4()),
        "vcon": "0.0.1",
        "created_at": now,
        "parties": [
            {"name": "Alice", "tel": "+15551112222"},
            {"name": "Bob", "tel": "+15553334444"},
        ],
        "dialog": [
            {
                "type": "recording",
                "start": now,
                "parties": [0, 1],
                "duration": random.randint(60, 600),
                "mimetype": "audio/x-wav",
                "url": "https://example.com/recording.wav",
            }
        ],
        "analysis": [],
        "attachments": [],
    }


class IngressUser(HttpUser):
    """Simulates producers posting vCons. Half go straight to a chain ingress."""

    wait_time = between(0.1, 0.5)

    def on_start(self) -> None:
        self.client.headers.update({API_HEADER: API_TOKEN})

    @task(3)
    def post_vcon_plain(self) -> None:
        """POST /vcon without ingress list — pure storage+index path."""
        payload = _minimal_vcon()
        with self.client.post(
            "/vcon",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            name="POST /vcon (no ingress)",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"status={resp.status_code} body={resp.text[:200]}")

    @task(1)
    def post_vcon_with_ingress(self) -> None:
        """POST /vcon with ingress_list — drives worker chain throughput."""
        payload = _minimal_vcon()
        with self.client.post(
            "/vcon",
            params={"ingress_lists": [INGRESS_LIST]},
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            name="POST /vcon (with ingress)",
            catch_response=True,
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"status={resp.status_code} body={resp.text[:200]}")
