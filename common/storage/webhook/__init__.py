import os
import threading
import time

from lib.vcon_redis import VconRedis
from lib.logging_utils import init_logger
from lib.metrics import record_histogram

import requests
from requests.adapters import HTTPAdapter

logger = init_logger(__name__)

default_options = {
    "webhook-urls": [],
    "headers": {},
    "timeout": 30,
    # Keep-alive connections kept per worker process. Size it to the in-flight
    # vCons per worker (CONSERVER_VCON_CONCURRENCY); extra connections still work
    # but are closed after use.
    "pool-size": 16,
}

# One Session per process so writes reuse keep-alive connections. A bare
# requests.post opened (and TIME_WAITed) a new socket per write, which exhausted
# the pod's ephemeral ports at a few hundred writes/s. Storage writes run on
# short-lived threads, so the session is shared across threads; urllib3's pool
# is thread-safe and these POSTs carry no cookies. Rebuilt after a fork so a
# child never shares its parent's sockets.
_session = None
_session_pid = None
_session_lock = threading.Lock()


def _get_session(pool_size):
    global _session, _session_pid
    pid = os.getpid()
    if _session is None or _session_pid != pid:
        with _session_lock:
            if _session is None or _session_pid != pid:
                session = requests.Session()
                adapter = HTTPAdapter(pool_connections=4, pool_maxsize=pool_size)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                _session, _session_pid = session, pid
    return _session


def save(vcon_uuid, opts=default_options):
    vcon_redis = VconRedis()
    vCon = vcon_redis.get_vcon(vcon_uuid)

    json_dict = vCon.to_dict()

    if json_dict.get("vcon") == "0.0.1" or "vcon" not in json_dict:
        json_dict["vcon"] = "0.3.0"

    headers = opts.get("headers", {})

    webhook_urls = opts.get("webhook-urls", [])
    if not webhook_urls:
        logger.warning(
            f"webhook storage: no webhook-urls configured for vcon {vcon_uuid}, skipping"
        )
        return

    for url in webhook_urls:
        logger.info(
            f"webhook storage: posting vcon {vcon_uuid} to webhook url: {url}"
        )
        webhook_start = time.time()
        session = _get_session(opts.get("pool-size", default_options["pool-size"]))
        resp = session.post(
            url, json=json_dict, headers=headers,
            timeout=opts.get("timeout", default_options["timeout"]),
        )
        webhook_duration = round(time.time() - webhook_start, 3)
        logger.info(
            f"webhook storage response for {vcon_uuid}: {resp.status_code} {resp.text}"
        )
        record_histogram("conserver.webhook.duration", webhook_duration,
                         attributes={"status_code": str(resp.status_code)})

        # Propagate HTTP failures so the conserver retains this write in its storage DLQ.
        resp.raise_for_status()
