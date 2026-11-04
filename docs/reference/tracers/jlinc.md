# JLINC tracer

Reports each link step to a JLINC API server as an audit event. A tracer runs alongside the links in a chain. This one does not change the vCon.

Module: `tracers.jlinc`, in `conserver/tracers/jlinc/`. Needs no extra packages.

The tracer records events and does nothing else. It has no consent logic. It does not read `lawful_basis` attachments, and it does not create, check or enforce an agreement. `agreement_id` is a value it forwards.

## Configure the tracer

```yaml
tracers:
  jlinc:
    module: tracers.jlinc
    options:
      data_store_api_url: http://jlinc-server:9090
      data_store_api_key: example-key
      archive_api_url: http://jlinc-server:9090
      archive_api_key: example-key
      system_prefix: VCONTest
      agreement_id: 00000000-0000-0000-0000-000000000000
      hash_event_data: true
      dlq_vcon_on_error: false
```

The server runs every entry under the top-level `tracers:` key for every chain. A `tracers:` list inside a chain, as the comments in `example_config.yml` suggest, is not read.

The `options` block is required. The conserver passes `tracer.get("options")` straight to `run`, so `default_options` never applies and a tracer with no options raises `TypeError`. `pip_name` is accepted here, as for links.

## Set the options

| Option | Type | `default_options` value | Description |
|---|---|---|---|
| `data_store_api_url` | string | `http://jlinc-server:9090` | Base URL for all API calls. Required |
| `data_store_api_key` | string | `""` | Sent as `Authorization: Bearer <key>`. Required |
| `archive_api_url` | string | `http://jlinc-server:9090` | Sent as `archive.url` in each event body. Required |
| `archive_api_key` | string | `""` | Sent as `archive.key` in each event body. Required |
| `system_prefix` | string | `VCONTest` | Prefix for entity names. Required |
| `agreement_id` | string | `00000000-0000-0000-0000-000000000000` | Sent as `agreementId` in each event body. Required |
| `hash_event_data` | boolean | `true` | When true, send a SHA-256 hash in place of the vCon |
| `dlq_vcon_on_error` | boolean | `false` | Read by the conserver. See [Handle a failure](#handle-a-failure) |

!!! warning "Set hash_event_data explicitly"
    The default of `true` does not apply to a key left out of `options`. Without the key, hashing is off and the full vCon goes to the JLINC server.

## Follow an event

The conserver calls the tracer once before the first link and once after each link, whether or not the link halted the chain. Each call does this:

1. Read the vCon through `VconRedis`.
2. On first use in a process, fetch the domain from `entity/domains/get` and take the first one.
3. Work out sender and recipient entities, creating any that are missing.
4. Build the payload.
5. Post the event to `event/produce`.

All calls are `POST {data_store_api_url}/api/v1/data/<path>`.

Entities are named `<prefix>-system@<domain>` and `<prefix>-<link>@<domain>`. The prefix and link name are lowercased, and any character outside `a-z`, `0-9`, `.`, `_` and `-` becomes `_`. An entity is fetched with `entity/get`, created with `entity/create` if the reply has no `didDoc`, and remembered in process memory.

Sender and recipient depend on the position in the chain, where `links` is the chain's link list:

| Call | Sender | Recipient |
|---|---|---|
| Before the first link | system | `links[0]` |
| After the first link | `links[-1]`, the last link in the list | `links[1]`, or system for a one-link chain |
| After link `i` | `links[i-1]` | `links[i+1]` |
| After the last link | `links[n-2]` | system |

The link that just ran is not the sender.

The event body has this shape:

```json
{
  "type": "data",
  "senderShortName": "vcontest-tag@example.com",
  "recipientShortName": "vcontest-system@example.com",
  "agreementId": "00000000-0000-0000-0000-000000000000",
  "data": {"hash": "<sha256 of the vCon JSON>"},
  "meta": {"in_vcon_uuid": "<uuid>", "out_vcon_uuid": "<uuid>"},
  "archive": {"url": "http://jlinc-server:9090", "key": "<archive_api_key>"}
}
```

With hashing off, `data` is the full vCon, including any attachments. The archive key travels in every event body.

## Handle a failure

| Failure | Result |
|---|---|
| vCon not found | Logs an error and returns `False`. The conserver ignores the return value |
| API call fails or returns an unexpected body | Logs a warning, then logs success and returns `True`. No event is recorded and the chain continues |
| Any exception that leaves `run` | The conserver logs it, then re-raises only if `dlq_vcon_on_error` is true |

A re-raised exception takes the link failure path in `_process_link`, which sends the vCon to the [dead letter queue](../../operations/dead-letter-queue.md) for its ingress list.

Connection errors and API errors sit inside the tracer's own `try` block and never leave `run`, so `dlq_vcon_on_error` does not cover them. It covers failures outside that block, such as a Redis error on read. A failed JLINC call shows up only as a warning in the logs, and the tracer does not retry it.

API calls set no request timeout, so a server that accepts a connection and never answers holds the chain at that step.
