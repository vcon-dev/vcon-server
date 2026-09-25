"""Utopia storage: rendering, and save/delete against a loopback fake Utopia."""

from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
from threading import Thread
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
import uuid as uuidlib

import pytest

import storage.utopia as utopia
from vcon import Vcon

KB = "11111111-1111-1111-1111-111111111111"
VCON_UUID = "8f752fc9-d6d8-4d2c-a9d0-d859f61d7c51"


# A legacy record in the shape of the vcon-dev/fake-vcons corpus.
LEGACY = {
    "uuid": VCON_UUID,
    "vcon": "0.0.1",
    "created_at": "2025-02-27T16:44:59.773035",
    "parties": [
        {"tel": "+15085550199", "name": "Jane Doe", "role": "customer"},
        {"mailto": "agent@example.com", "name": "John Roe", "role": "agent"},
    ],
    "dialog": [{"type": "text", "start": "2025-02-27T16:44:59.773035", "parties": [1, 0]}],
    "analysis": [
        {"type": "transcript", "dialog": 0, "body": {"transcript": "Hello, how can I help?\n\nI need a pickup."}},
        {"type": "summary", "dialog": 0, "body": "The agent answered a question.", "encoding": "none"},
    ],
    "attachments": [{"type": "tags", "body": ["disposition:VM Left"]}],
}


def current(grants=("recording", "analysis"), expiration="2999-01-01T00:00:00Z", text="Hello there."):
    return {
        "uuid": VCON_UUID,
        "vcon": "0.4.0",
        "created_at": "2026-09-18T14:02:00Z",
        "parties": [{"tel": "+15085550100"}, {"name": "Support"}],
        "dialog": [{"type": "recording", "start": "2026-09-18T14:02:00Z",
                    "duration": 240.4, "parties": [0, 1]}],
        "analysis": [{
            "type": "wtf_transcription", "dialog": 0, "encoding": "json",
            "body": json.dumps({"transcript": {"text": text},
                                "segments": [{"text": text, "speaker": 0},
                                             {"text": "Hi.", "speaker": 1}]}),
        }],
        "attachments": [{
            "purpose": "lawful_basis", "encoding": "json",
            "body": json.dumps({
                "lawful_basis": "consent", "expiration": expiration,
                "purpose_grants": [{"purpose": p, "granted": True} for p in grants],
                "proof_mechanisms": [{"mechanism_type": "audio_recording"}],
            }),
        }],
    }


def test_render_legacy_record():
    text, granted = utopia.render(LEGACY)
    lines = text.splitlines()
    assert lines[0] == "2025-02-27"  # Utopia takes the document date from line one
    assert "Jane Doe took part as customer, reachable by phone +15085550199." in lines
    assert "On 2025-02-27 at 16:44, John Roe and Jane Doe had a text conversation." in lines
    assert "On 2025-02-27, Hello, how can I help?" in lines
    assert "On 2025-02-27, I need a pickup." in lines  # each paragraph dated
    assert "On 2025-02-27, the conversation was summarised: The agent answered a question." in lines
    assert "Tagged disposition:VM Left." in lines
    assert "Lawful basis: none recorded." in lines
    assert granted is False


def test_render_current_record_with_lawful_basis():
    text, granted = utopia.render(current())
    assert text.startswith("2026-09-18\n")
    assert "On 2026-09-18 at 14:02, +15085550100 and Support had a recorded call lasting 240 seconds." in text
    assert "+15085550100 took part.\n" in text
    assert "On 2026-09-18, Speaker 0: Hello there.\nOn 2026-09-18, Speaker 1: Hi." in text
    assert "Lawful basis: consent, granted for recording, analysis, expires 2999-01-01." in text
    assert granted is True


def test_expired_or_missing_grant_is_not_granted():
    assert utopia.render(current(expiration="2020-01-01T00:00:00Z"))[1] is False
    text, granted = utopia.render(current(grants=("recording",)))
    assert granted is False and "granted for recording," in text


@contextmanager
def fake_utopia():
    """Login, list, upload and delete, with Utopia's sha256 dedup and tombstones."""
    state = {"docs": {}, "logins": 0, "tokens": set()}

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authed(self):
            token = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
            if token in state["tokens"]:
                return True
            self._send(401, {"error": "unauthorized"})
            return False

        def _body(self):
            return self.rfile.read(int(self.headers.get("Content-Length") or 0))

        def do_POST(self):
            path = urlparse(self.path).path
            body = self._body()
            if path == "/api/v1/auth/login":
                state["logins"] += 1
                token = f"t{state['logins']}"
                state["tokens"].add(token)
                return self._send(200, {"token": token})
            if path != f"/api/v1/kbs/{KB}/documents":
                return self._send(404, {})
            if not self._authed():
                return None
            name = re.search(rb'filename="([^"]+)"', body).group(1).decode()
            content = body.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0]
            digest = sha256(content).hexdigest()
            if any(d["sha256"] == digest and not d["deleted"] for d in state["docs"].values()):
                return self._send(200, {"created": [], "skipped": [{"filename": name}]})
            doc = {"id": str(uuidlib.uuid4()), "filename": name, "sha256": digest,
                   "content": content.decode(), "deleted": False}
            state["docs"][doc["id"]] = doc
            return self._send(200, {"created": [doc], "skipped": []})

        def do_GET(self):
            if not self._authed():
                return
            q = parse_qs(urlparse(self.path).query).get("q", [""])[0]
            docs = [d for d in state["docs"].values() if q in d["filename"] and not d["deleted"]]
            self._send(200, {"docs": docs, "total": len(docs)})

        def do_DELETE(self):
            if not self._authed():
                return
            state["docs"][urlparse(self.path).path.rsplit("/", 1)[1]]["deleted"] = True
            self._send(200, {"ok": True})

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1", state
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def env():
    utopia._tokens.clear()
    with fake_utopia() as (base_url, state), patch("storage.utopia.VconRedis") as redis:
        opts = {"base_url": base_url, "kb_id": KB, "email": "svc@example.com",
                "password": "secret-password", "transient_retries": 0}
        yield opts, state, redis.return_value.get_vcon


def live(state):
    return [d for d in state["docs"].values() if not d["deleted"]]


def test_save_resave_and_delete(env):
    opts, state, get_vcon = env
    get_vcon.return_value = Vcon(current())

    utopia.save(VCON_UUID, opts)
    assert [d["filename"] for d in live(state)] == [f"{VCON_UUID}.md"]
    assert live(state)[0]["content"].startswith("2026-09-18\n")

    utopia.save(VCON_UUID, opts)  # identical content: Utopia skips, nothing tombstoned
    assert len(state["docs"]) == 1 and len(live(state)) == 1

    get_vcon.return_value = Vcon(current(text="An amended line."))
    utopia.save(VCON_UUID, opts)  # new content supersedes the old rendering
    assert len(state["docs"]) == 2
    assert len(live(state)) == 1 and "Speaker 0: An amended line." in live(state)[0]["content"]

    assert utopia.delete(VCON_UUID, opts) is True
    assert live(state) == []
    assert utopia.delete(VCON_UUID, opts) is False


def test_expired_token_logs_in_again(env):
    opts, state, get_vcon = env
    get_vcon.return_value = Vcon(current())
    utopia.save(VCON_UUID, opts)
    state["tokens"].clear()  # Utopia restarted or the 7-day JWT ran out
    get_vcon.return_value = Vcon(current(text="Later."))
    utopia.save(VCON_UUID, opts)
    assert state["logins"] == 2 and len(live(state)) == 1


def test_require_analysis_grant_skips_upload(env):
    opts, state, get_vcon = env
    get_vcon.return_value = Vcon(LEGACY)
    utopia.save(VCON_UUID, {**opts, "require_analysis_grant": True})
    assert state["docs"] == {} and state["logins"] == 0


def test_missing_options_fail_loudly():
    with pytest.raises(ValueError, match="kb_id, email, password"):
        utopia.save(VCON_UUID, {})
