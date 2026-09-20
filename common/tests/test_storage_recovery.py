"""Storage-only recovery uses synthetic IDs, not customer vCon documents."""

import asyncio
import threading
from unittest.mock import MagicMock, patch

import pytest


class QueueState:
    def __init__(self, items):
        self.items = list(items)
        self.ack_error = False
        self.locked = False

    def lock(self, name, **kwargs):
        state = self

        class Lock:
            async def acquire(self, blocking=False):
                if state.locked:
                    return False
                state.locked = True
                return True

            async def release(self):
                state.locked = False

        return Lock()

    async def lrange(self, key, start, end):
        return self.items[start : end + 1]

    async def lpop(self, key):
        return self.items.pop(0) if self.items else None

    async def lrem(self, key, count, value):
        if self.ack_error:
            raise RuntimeError('ack unavailable')
        self.items.remove(value)
        return 1


def replay(state, save, count=2):
    import api
    from lib.queue import VconQueue

    storage = MagicMock()
    storage.save.side_effect = save
    with (
        patch.object(api, 'redis_async', state, create=True),
        patch.object(api, 'Storage', return_value=storage),
        patch.object(api, 'queue', VconQueue(client=MagicMock())),
    ):
        return asyncio.run(api.post_storage_dlq_reprocess(storage_name='test', count=count))


def test_entry_survives_until_write_succeeds():
    state = QueueState(['one', 'two', 'three'])
    saved = []

    def save(vid):
        assert vid in state.items
        saved.append(vid)

    response = replay(state, save)
    assert response.body == b'2'
    assert saved == ['one', 'two']
    assert state.items == ['three']


def test_write_failure_keeps_entry_without_a_requeue_write():
    state = QueueState(['one', 'two'])

    def fail(vid):
        raise RuntimeError('backend down')

    assert replay(state, fail).body == b'0'
    assert state.items == ['one', 'two']


def test_interrupted_replay_keeps_entry():
    state = QueueState(['one'])

    def interrupt(vid):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        replay(state, interrupt)
    assert state.items == ['one']


def test_ack_failure_keeps_successful_write_replayable():
    from fastapi import HTTPException

    state = QueueState(['one'])
    state.ack_error = True
    with pytest.raises(HTTPException) as error:
        replay(state, lambda vid: None)
    assert error.value.status_code == 500
    assert state.items == ['one']


def test_slow_storage_runs_off_the_api_event_loop():
    state = QueueState(['one'])
    api_thread = threading.get_ident()
    threads = []
    replay(state, lambda vid: threads.append(threading.get_ident()))
    assert threads and threads[0] != api_thread


def test_concurrent_replay_is_rejected_without_touching_queue():
    from fastapi import HTTPException

    state = QueueState(['one'])
    state.locked = True
    saved = []
    with pytest.raises(HTTPException) as error:
        replay(state, saved.append)
    assert error.value.status_code == 409
    assert state.items == ['one']
    assert saved == []


def test_second_replay_cannot_ack_a_new_failure_for_same_uuid():
    from fastapi import HTTPException

    state = QueueState(['one'])

    def save(vid):
        # Another API process must not snapshot this entry while our save is pending.
        with pytest.raises(HTTPException) as error:
            replay(state, lambda item: None)
        assert error.value.status_code == 409
        state.items.append(vid)  # A producer records another failed write for this UUID.

    assert replay(state, save).body == b'1'
    assert state.items == ['one']
    assert not state.locked
