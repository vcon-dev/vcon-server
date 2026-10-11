"""Webhook storage reuses one keep-alive connection instead of a new socket per write."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from storage import webhook


class _Receiver(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    client_ports = []

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        _Receiver.client_ports.append(self.client_address[1])
        self.send_response(201)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


def test_sequential_writes_share_one_connection():
    _Receiver.client_ports = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Receiver)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/probe"
    try:
        with patch.object(webhook, "VconRedis") as bodies:
            bodies.return_value.get_vcon.return_value.to_dict.return_value = {"synthetic_retry_probe": True}
            for _ in range(5):
                webhook.save("synthetic-id", {"webhook-urls": [url]})
    finally:
        server.shutdown()
        server.server_close()
    assert len(_Receiver.client_ports) == 5
    assert len(set(_Receiver.client_ports)) == 1


def test_session_is_rebuilt_after_fork():
    first = webhook._get_session(4)
    with patch.object(webhook.os, "getpid", return_value=-1):
        assert webhook._get_session(4) is not first
