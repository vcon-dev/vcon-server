"""Atomic queue/retention tests against an isolated disposable Redis process.

Values are opaque synthetic strings, not vCon objects or consent records.
"""

import shutil
import subprocess
import time
import tempfile

import pytest
from redis import Redis
from lib.queue import VconQueue


@pytest.fixture(scope='module')
def isolated_redis(tmp_path_factory):
    binary = shutil.which('redis-server')
    if not binary:
        pytest.skip('redis-server required')
    scratch = tempfile.TemporaryDirectory(prefix='con714-', dir='/tmp')
    socket = scratch.name + '/redis.sock'
    process = subprocess.Popen(
        [binary, '--port', '0', '--unixsocket', socket, '--save', '', '--appendonly', 'no'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = Redis(unix_socket_path=socket, decode_responses=True)
    try:
        for _ in range(100):
            try:
                if client.ping():
                    break
            except Exception:
                time.sleep(0.02)
        else:
            pytest.fail('isolated Redis failed to start')
        yield client
    finally:
        client.close()
        process.terminate()
        process.wait(timeout=5)
        scratch.cleanup()


@pytest.mark.parametrize('ttl,expected', [(10, 600), (1200, 1200), (None, -1)])
def test_enqueue_preserves_body_for_at_least_recovery_window(isolated_redis, ttl, expected):
    r = isolated_redis
    vid = f'synthetic-{ttl}'
    r.set('vcon:' + vid, 'synthetic body', ex=ttl)
    queue = VconQueue(client=r)
    queue.enqueue_storage_dlq(vid, vid, retention_seconds=600)
    assert r.lrange('DLQ:storage:' + vid, 0, -1) == [vid]
    remaining = r.ttl('vcon:' + vid)
    assert remaining == -1 if expected == -1 else expected - 1 <= remaining <= expected


def test_missing_body_is_reported_not_queued(isolated_redis):
    with pytest.raises(ValueError, match='missing'):
        VconQueue(client=isolated_redis).enqueue_storage_dlq('missing', 'missing', retention_seconds=600)
    assert isolated_redis.llen('DLQ:storage:missing') == 0
