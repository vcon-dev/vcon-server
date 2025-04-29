# SCITT Link

The SCITT (Supply Chain Integrity, Transparency, and Trust) link is a specialized plugin that provides integrity and inclusion protection for vCon objects by creating and registering signed statements on a SCITT Transparency Service. It ensures that vCons can be verified as authentic and complete, protecting against tampering and deletion.

## Features

- Creates signed statements based on vCon data
- Registers statements on a SCITT Transparency Service
- Supports different vCon operations (create, update, delete)
- Configurable signing keys and authentication
- Integration with DataTrails SCITT implementation
- Hash-based payload verification
- OIDC authentication support

## Configuration Options

```python
default_options = {
    "client_id": "<set-in-config.yml>",  # DataTrails client ID
    "client_secret": "<set-in-config.yml>",  # DataTrails client secret
    "scrapi_url": "https://app.datatrails.ai/archivist/v2",  # SCITT Reference API URL
    "auth_url": "https://app.datatrails.ai/archivist/iam/v1/appidp/token",  # Authentication URL
    "signing_key_path": None,  # Path to the signing key file
    "issuer": "ANONYMOUS CONSERVER",  # Issuer identifier
    "vcon_operation": "vcon-create",  # Operation type to record
    "key_id": None,  # Key ID for signing
    "OIDC_flow": "client-credentials"  # OIDC authentication flow
}
```

### Options Description

- `client_id`: Your DataTrails client ID
- `client_secret`: Your DataTrails client secret
- `scrapi_url`: URL for the SCITT Reference API
- `auth_url`: URL for authentication
- `signing_key_path`: Path to the signing key file
- `issuer`: Identifier for the statement issuer
- `vcon_operation`: Type of vCon operation being recorded
- `key_id`: Key ID for signing the statement
- `OIDC_flow`: OIDC authentication flow to use

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Creating a signed statement based on the vCon data:
   - Setting the subject to the vCon identifier
   - Creating metadata with the vCon operation
   - Using the vCon hash as the payload
   - Signing the statement with the provided key
3. Registering the signed statement on the SCITT service:
   - Authenticating with the SCITT service
   - Submitting the signed statement
   - Receiving an operation ID for tracking
4. Returning the vCon UUID for further processing

## Signed Statement Format

The signed statement includes:
- Issuer information
- Subject (vCon identifier)
- Metadata (vCon operation)
- Payload (vCon hash)
- Signature using the provided key
- Hash algorithm information
- Content type information

## Error Handling

- Validates required configuration options
- Handles missing vCon objects
- Supports different OIDC authentication flows
- Logs detailed information about the process
- Raises appropriate HTTP exceptions for errors

## Dependencies

- Requests library for API communication
- Custom utilities:
  - vcon_redis
  - logging_utils
  - create_hashed_signed_statement
  - register_signed_statement

## Requirements

- Python 3.7+
- Access to a SCITT implementation (e.g., DataTrails)
- DataTrails API credentials
- Signing key for statement creation
- Redis connection for vCon storage
- Appropriate permissions for vCon access and SCITT service

## Overview

Most storage services provide the ability to create, modify and delete content.
Which raises the question, can you guarantee your vCons weren't tampered with, or important updates weren't deleted?

> _If a vCon disappeared in the woods, would you know?_

With the SCITT capabilities, the integrity and inclusion of all vCons are recorded.
If you're in possession of a vCon that's not recorded on a SCITT ledger, how do you know it's a valid vCon, or the latest version of that vCon?

The SCITT Conserver Link is designed to integrate vCon (virtual conversation) data with a SCITT Reference API (SCRAPI) implementation.
The SCITT Link creates Signed Statements based on vCon information, enabling seamless tracking and management of conversation-related assets.
Setting the `vcon_operation` chain configuration, log different types of Events, based on which chain is executed.

## Prerequisites

- Python 3.7+
- Access to a [SCITT Implementation][scitt-implementations]

## Installation

1. Clone this repository or copy the `scitt/__init__.py` file into your conserver's `links` directory.
2. Install the required dependencies:

   ```bash
   pip install requests
   ```

## Configuration

The SCITT Link requires minimal configuration in the conserver setup.

- Add the following datatrails configurations to the conserver configuration file (`config.yml`)
- Replace `"<your_client_id>"` and `"<your_client_secret>"` with your [DataTrails API credentials](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/)
- Set `vcon_operation` to differentiate what operation is being recorded on DataTrails/SCITT.  
- The DataTrails `arc_display_type` is configured as: `"vcon_operation}"`, enabling [configurable permissions on Event Types](https://docs.datatrails.ai/platform/administration/sharing-access-outside-your-tenant/#creating-an-obac-policy)  

### DataTrails

For more information, see [DataTrails SCITT Conserver](https://docs.datatrails.ai/developers/api-reference/templates/scitt)

```yaml
links:
  scitt:
    module: links.scitt
    options:
      client_id: "<set-in-config.yml>",
      client_secret: "<set-in-config.yml>",
      scrapi_url: "https://app.datatrails.ai/archivist/v2",
      auth_url: "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
```

```yaml
links:
  scitt:
    module: links.scitt
    options:
      vcon_operation: "vcon-create"
      client_id: "<set-in-config.yml>",
      client_secret: "<set-in-config.yml>",
      scrapi_url: "<SCRAPI URL>",
      auth_url: "<Auth URL>",

chains:
  create_chain:
    links:
      - scitt
    ingress_lists:
      - create_ingress
    egress_lists:
      - default_egress
    enabled: 1
```

## Contributing

Contributions to improve the DataTrails Asset Link are welcome.
Please follow these steps:

1. Fork the repository.
1. Create a new branch for your feature or bug fix.
1. Write tests for your changes.
1. Implement your changes.
1. Run the tests to ensure they all pass.
1. Submit a pull request with a clear description of your changes.

## License

The [SCITT Link is open-sourced under the MIT license](./LICENSE).

[scitt-architecture]:     https://datatracker.ietf.org/wg/scitt/about/
[scitt-implementations]:  https://scitt.io/implementations
