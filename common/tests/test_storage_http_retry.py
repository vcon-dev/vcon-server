"""Exercise storage HTTP retry policy over loopback without storing vCons."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from unittest.mock import patch

import pytest
import requests

from storage.vcon_mcp import _session


@contextmanager
def responding_server(statuses):
    """Serve a finite sequence, retaining request bodies for replay checks."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append(body)
            status = statuses[min(len(received) - 1, len(statuses) - 1)]
            self.send_response(status)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/retry-test", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def retry_session():
    session = _session({"transient_retries": 2, "transient_backoff_base_s": 0})
    session.trust_env = False  # Never route loopback fixtures through a proxy.
    return session


def test_post_retries_503_with_same_body_then_succeeds():
    payload = {"synthetic_retry_probe": True}
    with responding_server([503, 200]) as (url, received):
        session = retry_session()
        with patch.object(session, "close", wraps=session.close) as close:
            with session:
                response = session.post(url, json=payload, timeout=2)
                response.raise_for_status()
            close.assert_called_once_with()

    assert response.status_code == 200
    assert len(received) == 2
    assert received[0] == received[1]
    assert json.loads(received[0]) == payload


def test_permanent_401_is_not_retried_and_session_closes_on_error():
    with responding_server([401]) as (url, received):
        session = retry_session()
        with patch.object(session, "close", wraps=session.close) as close:
            with pytest.raises(requests.HTTPError):
                with session:
                    response = session.post(url, json={"synthetic_retry_probe": True}, timeout=2)
                    response.raise_for_status()
            close.assert_called_once_with()

    assert response.status_code == 401
    assert len(received) == 1


def test_retry_exhaustion_returns_last_response_for_storage_to_raise():
    with responding_server([503]) as (url, received):
        with retry_session() as session:
            response = session.post(url, json={"synthetic_retry_probe": True}, timeout=2)
            with pytest.raises(requests.HTTPError):
                response.raise_for_status()

    assert response.status_code == 503
    assert len(received) == 3  # Initial attempt plus two configured retries.
