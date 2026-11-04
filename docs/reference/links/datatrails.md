# datatrails

Records an event for the vCon on the DataTrails service, so a vCon's hash can be checked later.

Module: `links.datatrails`

Imports `fastapi`, which the `conserver` dependency group does not include. The link fails to import in the `docker/Dockerfile.conserver` image, and each vCon then goes to the dead letter queue. It imports in the `docker/Dockerfile` image.

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `api_url` | string | `https://app.datatrails.ai/archivist` | Base API URL |
| `auth_url` | string | `https://app.datatrails.ai/archivist/iam/v1/appidp/token` | In `default_options`, but no code reads it. The token URL comes from `auth.token_endpoint` |
| `partner_id` | string | `not-set` | Sent as the `DataTrails-Partner-ID` header |
| `asset_attributes` | dict | `{"arc_display_type": "vcon_droid", "conserver_link_version": "0.3.0"}` | Attributes used to find or create the asset |
| `auth.type` | string | required | Must be `oidc-client-credentials`, in any case |
| `auth.token_endpoint` | string | required | Token URL |
| `auth.client_id` | string | required | Client ID |
| `auth.client_secret` | string | required | Client secret |
| `vcon_operation` | string | required | Operation name. Absent from `default_options`, so leaving the key out raises `KeyError`. An empty value becomes `vcon` |

The event name is `vcon_` plus `vcon_operation` in lowercase, after any leading `vcon_` or `vcon-` is removed.

## Follow the processing steps

1. Merge the options and build the authenticator.
2. Load the vCon.
3. Find the day's asset by `asset_attributes` plus a `droid_id` of today's UTC date, or create it.
4. Create an event on that asset. Its attributes include the vCon's SHA-256 hash as `payload`, `vcon://<uuid>` as `subject`, and the operation.
5. Create an asset-free event with the same attributes and a trail of the subject. A failure here is counted and logged, and the link continues.

## Read the return value

Returns the uuid. Bad `auth` raises `HTTPException` with status 501, and a missing vCon raises it with status 404. A failed token, asset or asset event request raises as well. In each case the vCon goes to the dead letter queue.

## Inspect the vCon changes

None. The link does not save the vCon or store a receipt.

## Copy a configuration example

```yaml
links:
  datatrails_created:
    module: links.datatrails
    options:
      partner_id: your-partner-id
      vcon_operation: vcon_created
      auth:
        type: oidc-client-credentials
        token_endpoint: https://app.datatrails.ai/archivist/iam/v1/appidp/token
        client_id: your-client-id
        client_secret: your-client-secret
```

## Track the metrics

`conserver.link.datatrails.event_creation_failures`. See [Metrics](../metrics.md).
