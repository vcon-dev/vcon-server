# Elasticsearch storage adapter

Indexes the parts of a vCon as separate documents. Parties, attachments, analysis and dialog each go to their own indices. The adapter does not store the vCon as one document and cannot read it back.

Module: `storage.elasticsearch`. Needs `elasticsearch`, from the `storage` dependency group. The group pins it below version 9.

## Configure the adapter

Self-managed cluster:

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      url: https://elasticsearch:9200
      username: elastic
      password: example-password
      ca_certs: /etc/ssl/es/ca.crt
      index_prefix: prod_
```

Elastic Cloud:

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      cloud_id: example:ZXhhbXBsZQ==
      api_key: example-key
```

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `name` | string | `elasticsearch` | Not read by the adapter |
| `cloud_id` | string | `""` | Elastic Cloud id. If `cloud_id` or `api_key` is set, the adapter takes the cloud path, which reads both |
| `api_key` | string | `""` | Elastic Cloud API key |
| `index` | string | `vcon_index` | Not read by the adapter. Index names come from `index_prefix` |
| `ca_certs` | string | none | Path to a CA bundle. If it is unset or the path does not exist, the client runs with `verify_certs=False` |
| `url` | string | none | Cluster URL. Required on the non-cloud path |
| `username` | string | none | Basic auth user. Required on the non-cloud path |
| `password` | string | none | Basic auth password. Required on the non-cloud path |
| `index_prefix` | string | `""` | Prepended to every index name, after trimming whitespace |

## Save a vCon

`save` reads the vCon through `VconRedis`, applies `EGRESS_FORMAT_VERSION`, then writes these documents:

| Part | Index | Document id |
|---|---|---|
| Party | `vcon_parties_<role>`, or `vcon_parties` when the party has no role | `<uuid>_<index>` |
| Attachment | `vcon_attachments_<type or purpose, lowercased>`, or `..._unknown` | `<uuid>_<index>` |
| Analysis | `vcon_analysis_<type>` | `<uuid>_<index>` |
| Dialog | `vcon_dialog` | `<uuid>_<index>` |

Each index name starts with `index_prefix`. Every document also gets `vcon_id` and `started_at`, the `start` of the first dialog. When the vCon has an attachment with purpose `tenant`, every document gets `tenant_id` from the `id` in its body. A JSON string body on an attachment or analysis entry is parsed before indexing.

A vCon with an empty dialog list is skipped without an error.

## Read a vCon

The adapter has no `get`.

## Delete a vCon

`delete` lists indices matching `<index_prefix>vcon*` and runs one `delete_by_query` on `vcon_id` with `refresh=True`. It returns `True` when at least one document went, `False` otherwise, and raises on a query error.

## Handle a failed write

Failures to connect, to read the vCon or to prepare a part raise, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). An analysis entry with no `encoding` key raises `KeyError` here.

A failure on one document is different. `do_vcon_parts_indexing` logs it and carries on, so the vCon counts as stored with that document missing, and nothing reaches the DLQ. Watch the logs for `failed to insert`.

A repeated `save` overwrites documents with the same ids. If a vCon lost a part between saves, the old document stays.
