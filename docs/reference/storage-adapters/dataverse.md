# Dataverse storage adapter

Stores a vCon as a row in a Microsoft Dataverse table through the Web API, with Azure AD client credentials from MSAL.

Module: `storage.dataverse`. Needs `msal`, from the `storage` dependency group.

## Configure the adapter

```yaml
storages:
  dataverse:
    module: storage.dataverse
    options:
      url: https://example.crm.dynamics.com
      api_version: "9.2"
      tenant_id: 00000000-0000-0000-0000-000000000000
      client_id: 00000000-0000-0000-0000-000000000000
      client_secret: example-secret
      entity_name: vcon_storage
      uuid_field: vcon_uuid
      data_field: vcon_data
      subject_field: vcon_subject
      created_at_field: vcon_created_at
```

## Set the options

The adapter reads every key directly, so all of them except `name` are required in an `options` block.

| Option | Type | Default | Description |
|---|---|---|---|
| `name` | string | `dataverse` | Not read by the adapter |
| `url` | string | `https://org.crm.dynamics.com` | Environment URL. Also forms the token scope `<url>/.default` |
| `api_version` | string | `9.2` | Web API version in the request path |
| `tenant_id` | string | `""` | Azure AD tenant |
| `client_id` | string | `""` | Azure AD application id |
| `client_secret` | string | `""` | Azure AD client secret |
| `entity_name` | string | `vcon_storage` | Entity set name in the request path |
| `uuid_field` | string | `vcon_uuid` | Column for the vCon UUID |
| `data_field` | string | `vcon_data` | Column for the vCon JSON string |
| `subject_field` | string | `vcon_subject` | Column for the subject |
| `created_at_field` | string | `vcon_created_at` | Column for the creation time |

## Save a vCon

1. Read the vCon through `VconRedis`.
2. Acquire a new token and open a session. Each `save` and `get` does this.
3. Query for an existing row by UUID. An error in this query is logged at debug level and treated as no match.
4. Send a `PATCH` to `<entity_name>(<id>)` when a row was found, otherwise a `POST` to `<entity_name>`.

`created_at` falls back to the current time when the vCon has none. The adapter does not apply `EGRESS_FORMAT_VERSION`.

## Read a vCon

`get` runs the same query and parses `data_field` from the first row. It returns `None` when no row matches, the field is empty or holds bad JSON, or any error occurs.

## Delete a vCon

The adapter has no `delete`. A row stays in Dataverse after `DELETE /vcon/{uuid}`.

## Handle a failed write

A token failure or HTTP error raises, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write). The adapter has no retry of its own.

A repeated `save` updates the row only if the lookup in step 3 works. Otherwise it creates another row.

## Check the known problems

- TODO(verify): the filter is built as `$vcon_uuid eq '<uuid>'`, with a leading `$` on the column name. If Dataverse rejects that, `get` always returns `None` and every `save` creates a row. No test covers the query.
- TODO(verify): the lookup takes the row key from a field called `id`. If the table's key column has another name, the update branch never runs.
