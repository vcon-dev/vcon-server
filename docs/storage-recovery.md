# Recover failed storage writes

A failed backend write enters `DLQ:storage:<configured-storage-name>`. It does not
re-enter the processing chain, so recovery does not repeat transcription. Other
backends and egress continue. Monitor `conserver.storage.count{outcome="error"}`
and `conserver.dlq.count{queue_name="DLQ:storage:<name>"}`.

The Redis body retention extension and enqueue happen atomically.
`VCON_DLQ_EXPIRY` defaults to seven days; longer TTLs and persistent bodies are
preserved. Zero disables the extension. A missing body or Redis failure is logged
as requiring manual recovery. Redis durability and available capacity remain
prerequisites; this is not a second durable store. Recover before the body expires.

The vcon-mcp HTTP backend retries connection failures, read timeouts, and
429/502/503/504 responses. Options are `transient_retries` (default 3),
`transient_backoff_base_s` (default 0.5), and `timeout` (default 30 seconds per
request). Retry-After is respected. Permanent 4xx responses are not retried.
POST retries require the backend's UUID-based upsert contract.

Using the API's configured root path and normal authentication:

- `GET /dlq/storage?storage_name=<name>` lists pending UUIDs.
- `POST /dlq/storage/reprocess?storage_name=<name>&count=10` retries a bounded
  snapshot, returning the number successfully written. Start with a small count.

Entries are removed only after successful writes. A failed write stops the batch
and leaves its entry queued. A stopped API process or failed acknowledgement also
leaves entries replayable. This is at-least-once delivery: interrupted replays may
repeat a successful save. Verify that the selected backend tolerates repeated
writes of the same UUID. Storage I/O runs in the threadpool rather than blocking
the API event loop.

A Redis lock serializes replay per backend across API processes. Concurrent replay
returns HTTP 409. The lock deliberately has no expiry: a slow backend must not let
a second replay acknowledge entries belonging to an earlier snapshot. Normal
completion and errors release it. After a process crash, stop or verify the
termination of every replay for that backend before manually deleting only
`DLQ:storage:<name>:replay-lock`, then retry. Never clear a lock while replay might
still be running; preserve the DLQ list and vCon bodies.

## Validate before production rollout

Use an isolated RedisJSON instance and a disposable HTTP receiver. Make the receiver
return 503, confirm bounded retries followed by a per-backend DLQ entry and retained
body, restore successful responses, replay, and verify the receiver stored one UUID
without invoking processing links. Stop replay during a write and confirm its UUID
remains queued. Never create a production backend outage for this test.

Release the upstream conserver and API images together. Overlay deployments must
update both base images; updating only workers queues failures without providing
the recovery endpoint. Preserve the previous images for rollback. Rolling back
must not clear `DLQ:storage:*`; old images cannot replay these queues. After rollout,
verify versions, health, storage-error alerts, and queue depth before a small replay.
