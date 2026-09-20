#!/usr/bin/env python3
"""Copy a quiesced Redis database to an empty target, converting RedisJSON.

Connection URLs come from environment variables to avoid credentials in argv.
The source is never modified. See docs/installation/redis-migration.md.
"""

import argparse
import json
import os

from redis import Redis

NATIVE_TYPES = {b"string", b"list", b"set", b"zset", b"hash", b"stream"}
JSON_TYPE = b"ReJSON-RL"


def migrate(source, target, patterns):
    """Copy selected keys, preserving native values and absolute expiry times.

    Requires Redis >= 7 for PEXPIRETIME and stopped writers on both endpoints.
    A partial target is intentionally not resumable: retry into a fresh database.
    """
    source_info, target_info = source.info("server"), target.info("server")
    source_version = tuple(int(n) for n in source_info["redis_version"].split(".")[:2])
    target_version = tuple(int(n) for n in target_info["redis_version"].split(".")[:2])
    if source_version < (7, 0) or target_version < source_version:
        raise ValueError("Require source Redis >= 7 and target version >= source version")
    source_id = (source_info["run_id"], source.connection_pool.connection_kwargs.get("db", 0))
    target_id = (target_info["run_id"], target.connection_pool.connection_kwargs.get("db", 0))
    if source_id == target_id:
        raise ValueError("Source and target must be different databases")
    if target.dbsize():
        raise ValueError("Target must be empty; use a fresh database after a partial copy")

    # Deduplicate SCAN results and overlapping patterns. Store keys, not payloads.
    keys = {key for pattern in patterns for key in source.scan_iter(match=pattern, count=1000)}
    types = {key: source.type(key) for key in keys}
    if any(kind not in NATIVE_TYPES | {JSON_TYPE, b"none"} for kind in types.values()):
        raise ValueError("Unsupported source type; target has not been modified")

    copied = expired = 0
    for key, kind in types.items():
        if kind == b"none":
            expired += 1
            continue
        with source.pipeline(transaction=True) as pipe:
            if kind == JSON_TYPE:
                pipe.execute_command("JSON.GET", key, ".")
            else:
                pipe.dump(key)
            pipe.execute_command("PEXPIRETIME", key)
            payload, deadline = pipe.execute()
        if payload is None or deadline == -2:
            expired += 1
            continue
        seconds, micros = target.time()
        if deadline >= 0 and deadline <= seconds * 1000 + micros // 1000:
            expired += 1
            continue
        if kind == JSON_TYPE:
            json.loads(payload)  # Validate but do not normalize or reserialize vCons.
            options = {"pxat": deadline} if deadline >= 0 else {}
            if not target.set(key, payload, nx=True, **options):
                raise ValueError("Target changed during migration; stop all target writers")
            actual = target.get(key)
            if actual is not None and json.loads(actual) != json.loads(payload):
                raise ValueError("JSON verification failed")
        else:
            # No REPLACE: any competing target write must abort the copy.
            target.restore(key, deadline if deadline >= 0 else 0, payload, absttl=True)
            if target.type(key) not in (kind, b"none"):
                raise ValueError("Native type verification failed")
        copied += 1
    return {"selected": len(keys), "copied": copied, "expired": expired}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--match",
        action="append",
        required=True,
        help="Owned key pattern, repeatable; use '*' only for an exclusively owned database",
    )
    parser.add_argument(
        "--writers-stopped",
        action="store_true",
        required=True,
        help="Confirm all source and target writers are stopped and the source is backed up",
    )
    args = parser.parse_args()
    source = Redis.from_url(os.environ["REDIS_MIGRATION_SOURCE_URL"])
    target = Redis.from_url(os.environ["REDIS_MIGRATION_TARGET_URL"])
    try:
        print(json.dumps(migrate(source, target, args.match)))
    finally:
        source.close()
        target.close()


if __name__ == "__main__":
    main()
