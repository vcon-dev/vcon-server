# Migrate RedisJSON data before upgrading

The server now stores whole documents as JSON strings through ordinary Redis
SET/GET/MGET/DEL. RedisJSON is no longer required. Existing RedisJSON keys are
module values, not strings: old and new workers cannot share the same key format.
This is a storage-format change even though HTTP and VconRedis interfaces remain
unchanged. Schedule a maintenance window for existing deployments.

Fresh installations can use the pinned ordinary Redis image in Compose. Existing
installations must migrate first. Never start ordinary Redis on the old Stack
volume, remove that volume, or flush the source database to make startup succeed.

## Prepare the endpoints

1. Inventory every application using the source Redis database, including external
   writers, ingress/DLQ queues, indexes, configuration and storage-backend prefixes.
   Identify all keys this deployment owns. Do not copy another tenant's keys.
2. Stop ingress and all source and target writers/workers. Record queue lengths,
   order and in-flight processing state; resolve in-flight work before copying.
   Keep both endpoints stopped until verification and cutover finish.
3. Take and verify a source snapshot/volume backup. Retain the old application and
   Stack image digests and the exact original connection configuration.
4. Start a separate ordinary Redis instance on a **fresh volume** and empty target
   database, with the persistence, credentials, network isolation and expiration
   notifications required by the deployment. Do not expose it publicly. Ensure
   source and target clocks agree because expirations use absolute milliseconds.
5. Use Redis 7 or newer on the source (PEXPIRETIME is required). Native DUMP/RESTORE
   format compatibility must be verified for the chosen target. The tested pair
   is Redis Stack 7.4.7 to ordinary Redis 7.4.11. The tool rejects a lower
   target major/minor version before any writes; newer-source to older-target
   restores can fail. Other Redis-compatible products and cluster
   modes are not certified by this change.

## Copy the owned data

Install this repository's Python dependencies. Set `REDIS_MIGRATION_SOURCE_URL`
and `REDIS_MIGRATION_TARGET_URL` using the deployment's secret-management method.
Do not put credential-bearing URLs on the command line or in a committed file.
Then, from the repository root:

```sh
python scripts/migrate_redis_json.py --writers-stopped --match 'vcon:*' --match 'config:*'
```

Those patterns are examples, **not a complete application inventory**. Include the
actual ingress/DLQ queues, sorted sets, indexes, retry/recovery keys and backend
storage prefixes identified above. For an exclusively owned database, use
`--match '*'` to preserve all native keys along with JSON documents.

The tool refuses the same source/target database, any occupied target, and unknown
module types. It reads source data only. It converts ReJSON-RL values to strings,
validates JSON without rewriting it, and copies native strings, lists, sets,
sorted sets, hashes and streams using DUMP/RESTORE. Persistent keys remain
persistent. Expiring keys retain absolute deadlines; keys that expire while
copying are omitted. Overlapping patterns and repeated SCAN results are deduped.
Memory usage scales with the selected key names, not their payloads.

A failure leaves the source intact but can leave a partial target. Keep writers
stopped and retry into another fresh empty target after diagnosing the error.
The tool intentionally refuses to resume over or overwrite a partial target.
Do not delete the partial copy or source backup merely to retry.

## Verify and switch the application

Before changing application endpoints:

- Compare selected key counts, allowing only expected expirations. Verify JSON
  semantic equality and native payloads, including full queue order and duplicate
  entries. The script checks types and JSON readback; independent dataset
  comparison is still required before production cutover.
- Check persistent keys and absolute expiry deadlines. Do not reset all TTLs to
  their original durations, which would extend retention.
- Confirm no module values remain in the target; check persistence and restart
  recovery on the new volume, and expiration notifications (`Ex`).
- Smoke-test new API and worker images together against the target, including
  create/read/update/delete, ordered batches, storage fallback, queues and indexes.
  Use synthetic data for the smoke test and record it separately from source data.

Switch the API and every worker together to the new endpoint and images. Reopen
traffic only after verification. Watch errors, queue and DLQ depths, processing
throughput, and expiry behavior. Keep the original snapshot/volume and images
through the agreed rollback window. Never run old RedisJSON workers against the
new string keys.

Before traffic reopens, rollback means returning the API and workers to the old
images and untouched source endpoint. After traffic reopens, freeze writers and
reconcile newly accepted records and queue acknowledgements before rolling back.
Restoring the old snapshot alone would lose new writes or replay processed work.

## Run the regression tests

The development Docker image contains redis-server for private Unix-socket
contract tests. These tests start their own process and do not use REDIS_URL.
The existing API/TTL integration tests use REDIS_URL, which must point to a
disposable test instance. They now fail if that service is unavailable.

```sh
pytest tests/core/test_plain_redis.py tests/core/test_redis_json_migration.py
pytest tests/core/test_vcon_redis.py tests/core/test_vcon_redis_ttl.py common/tests/test_api.py
```

JSON syntax errors remain visible errors. Missing keys still return None and batch
reads retain input order and missing positions. Updates without an explicit TTL
retain any existing expiration; positive explicit TTLs are set atomically, while
zero or negative TTLs retain the previous immediate-expiration behavior.

CI separately runs the legacy JSON migration test with
`REDISJSON_TEST_SOURCE_URL` and `REDISJSON_TEST_TARGET_URL` set to fresh disposable
services/databases. Redis Stack is used only as that migration test's legacy
source, never as the runtime service. The source fixture remains intact until
explicit test cleanup, which verifies the pre-cutover rollback path.
