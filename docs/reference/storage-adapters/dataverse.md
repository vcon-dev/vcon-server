# dataverse

Stores vCons in Microsoft Dataverse as custom entity records. Authentication uses Azure Active Directory via the MSAL library, making this adapter suitable for organizations already using the Microsoft Power Platform.

## Prerequisites

1. A Microsoft Dataverse environment (Dynamics 365 or Power Platform)
2. An Azure AD app registration with the `Dynamics CRM user_impersonation` API permission (or equivalent)
3. A custom entity in Dataverse with the fields described below
4. The `msal` and `requests` Python packages

```
pip install msal requests
```

### Dataverse Entity Setup

Create a custom entity (table) in your Dataverse environment containing these columns:

| Column | Type | Description |
|--------|------|-------------|
| `vcon_uuid` | Single Line of Text | vCon UUID (used as the lookup key) |
| `vcon_data` | Multiple Lines of Text | Full vCon serialized as JSON |
| `vcon_subject` | Single Line of Text | vCon subject |
| `vcon_created_at` | Date and Time | vCon creation timestamp |

The column logical names must match the `uuid_field`, `data_field`, `subject_field`, and `created_at_field` options.

## Configuration

```yaml
storages:
  dataverse:
    module: storage.dataverse
    options:
      url: https://your-org.crm.dynamics.com
      tenant_id: ${AZURE_TENANT_ID}
      client_id: ${AZURE_CLIENT_ID}
      client_secret: ${AZURE_CLIENT_SECRET}
      entity_name: vcon_storage
      uuid_field: vcon_uuid
      data_field: vcon_data
      subject_field: vcon_subject
      created_at_field: vcon_created_at
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | `dataverse` | Adapter name |
| `url` | string | `https://org.crm.dynamics.com` | Dataverse environment URL |
| `api_version` | string | `9.2` | Dataverse Web API version |
| `tenant_id` | string | `""` | Azure AD tenant (directory) ID |
| `client_id` | string | `""` | Azure AD application (client) ID |
| `client_secret` | string | `""` | Azure AD client secret |
| `entity_name` | string | `vcon_storage` | Logical name of the custom entity (table) in Dataverse |
| `uuid_field` | string | `vcon_uuid` | Column logical name that stores the vCon UUID |
| `data_field` | string | `vcon_data` | Column logical name that stores the full vCon JSON |
| `subject_field` | string | `vcon_subject` | Column logical name that stores the vCon subject |
| `created_at_field` | string | `vcon_created_at` | Column logical name that stores the creation timestamp |

## Example

```yaml
storages:
  dataverse:
    module: storage.dataverse
    options:
      url: https://contoso.crm.dynamics.com
      api_version: "9.2"
      tenant_id: ${AZURE_TENANT_ID}
      client_id: ${AZURE_CLIENT_ID}
      client_secret: ${AZURE_CLIENT_SECRET}
      entity_name: cr123_vcon_storage
      uuid_field: cr123_vcon_uuid
      data_field: cr123_vcon_data
      subject_field: cr123_vcon_subject
      created_at_field: cr123_vcon_created_at

chains:
  main:
    links:
      - transcribe
    storages:
      - dataverse
    ingress_lists:
      - default
    enabled: 1
```

## Notes

- An access token is acquired via MSAL client-credentials flow on every `save` or `get` call. Tokens are not cached between calls.
- On `save`, the adapter checks whether an entity with the same UUID already exists and performs a PATCH (update) if found, or a POST (create) otherwise.
- Store the `client_secret` in an environment variable or secrets manager — never commit it to source control.
- Custom entity logical names in Dataverse typically include a publisher prefix (e.g. `cr123_vcon_storage`). Ensure the `entity_name` and field names match the logical names shown in the Power Apps maker portal.
