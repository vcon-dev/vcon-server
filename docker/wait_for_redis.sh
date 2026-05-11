#!/bin/bash
# Wait for Redis to be reachable, then exec the next command.
#
# Uses Python + the `redis` library (already a runtime dependency) so that
# every form of REDIS_URL works: with or without credentials, plain or TLS,
# with or without a trailing /<db> selector. The previous implementation
# called `redis-cli -u $REDIS_URL ping`, which the redis-cli version baked
# into the image mis-parsed for `redis://:password@host:port/0`-style URLs
# and so never returned PONG, hanging the container forever.

set -u

if [ -z "${REDIS_URL:-}" ]; then
  echo "REDIS_URL not set; skipping redis wait." >&2
  exec "$@"
fi

while true; do
  python3 - <<'PY' && break
import os, sys
try:
    import redis
    r = redis.from_url(
        os.environ["REDIS_URL"],
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    sys.exit(0 if r.ping() else 1)
except Exception:
    sys.exit(1)
PY
  echo "Redis not ready yet. Retrying..."
  sleep 1
done

echo "Redis is ready. Starting the dependent service..."
exec "$@"
