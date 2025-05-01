# DataTrails Link

The DataTrails link is a specialized plugin that integrates vCon data with the DataTrails platform, creating a verifiable audit trail for vCon operations. It supports both asset-based and asset-free event recording, with plans to transition fully to asset-free events in the future.

## Features

- Integration with DataTrails platform for verifiable audit trails
- Support for both asset-based and asset-free events
- Automatic token management with refresh mechanism
- Configurable authentication methods (currently supports OIDC client credentials)
- Structured event attributes mapping to SCITT envelopes
- Support for trails indexing
- Version tracking for API compatibility

## Configuration Options

```python
default_options = {
    "api_url": "https://app.datatrails.ai/archivist",
    "auth_url": "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
    "partner_id": "not-set",
    "asset_attributes": {
        "arc_display_type": "vcon_droid",
        "conserver_link_version": link_version
    },
    "auth": {
        "type": "oidc-client-credentials",
        "token_endpoint": "https://app.datatrails.ai/archivist/iam/v1/appidp/token",
        "client_id": "your-client-id",
        "client_secret": "your-client-secret"
    },
    "vcon_operation": "vcon"  # Optional, defaults to "vcon"
}
```

### Options Description

- `api_url`: Base URL for the DataTrails API
- `auth_url`: URL for authentication endpoint
- `partner_id`: Your DataTrails partner ID
- `asset_attributes`: Attributes for asset creation (temporary, will be deprecated)
- `auth`: Authentication configuration
  - `type`: Authentication type (currently supports "oidc-client-credentials")
  - `token_endpoint`: Endpoint for token requests
  - `client_id`: Your client ID
  - `client_secret`: Your client secret
- `vcon_operation`: Operation type for the vCon event

## Usage

The link processes vCons by:
1. Authenticating with DataTrails
2. Retrieving the vCon from Redis
3. Creating or finding an asset (temporary, will be deprecated)
4. Creating an asset-based event with vCon data
5. Creating an asset-free event (if supported)
6. Recording event metadata and trails

## Event Attributes

Events include the following attributes:
- `arc_display_type`: Operation type
- `arc_event_type`: Operation type
- `conserver_link`: Link type
- `conserver_link_name`: Link name
- `conserver_link_version`: Link version
- `payload`: vCon hash
- `payload_hash_alg`: Hash algorithm (SHA-256)
- `payload_preimage_content_type`: Content type (application/vcon+json)
- `subject`: vCon identifier
- `timestamp_declared`: Event timestamp
- `vcon_draft_version`: vCon draft version
- `vcon_operation`: Operation type

## Error Handling

- Implements token refresh mechanism
- Handles API errors with appropriate HTTP exceptions
- Logs failures and important events
- Graceful handling of asset-free event creation failures

## Dependencies

- Requests library for API communication
- Redis for vCon storage
- Custom utilities:
  - vcon_redis
  - logging_utils

## Requirements

- DataTrails API credentials
- Redis connection must be configured
- Appropriate permissions for vCon access and storage

## Future Changes

- Asset-based events will be deprecated in favor of asset-free events
- Support for additional authentication methods may be added
- Potential integration with SCITT statements

## Overview

Most storage services provide the ability to create, modify and delete content.
Which raises the question, can you guarantee your vCons weren't tampered with, or important updates weren't deleted?

> _If a vCon disappeared in the woods, would you know?_

With the SCITT capabilities of DataTrails, the integrity and inclusion of all vCons are recorded.
If you're in possession of a vCon that's not recorded on a SCITT ledger, how do you know it's a valid vCon, or the latest version of that vCon?

The DataTrails Link is a conserver link designed to integrate vCon (virtual conversation) data with the [DataTrails Events API][datatrails-events].
The DataTrails Link allows for the creation of DataTrails Events based on vCon information, enabling seamless tracking and management of conversation-related assets.
Setting the `vcon_operation` chain configuration, log different types of Events, based on which chain is executed.

## Prerequisites

- Python 3.7+
- Access to a DataTrails account with [API credentials](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/)
- Conserver setup with vCon support

## Installation

1. Clone this repository or copy the `datatrails/__init__.py` file into your conserver's `links` directory.
2. Install the required dependencies:

   ```bash
   pip install requests
   ```

## Usage

The DataTrails Link will automatically process vCons as they pass through the conserver providing integrity protection to the "moments that matter".
To seal a vCon, for the changes applied, add the DataTrails Link to the end of a conserver chain.
For each chain completion, the hash of the vCon will be placed on the ledger, with additional non-PII information providing integrity and inclusion protection.

### Ledgering a vCon

For each vCon Chain:

1. A [DataTrails Event](https://docs.datatrails.ai/developers/api-reference/events-api/) will be recorded, integrity protecting each vCon, setting the `subject` to `vcon://<vcon_uuid>` for correlation of events to each vCon.
1. If no DataTrails Asset exists for the vCon, a new asset will be created.  
   _**Note:** this is a temporary solution as Assets are being deprecated._  
   In this latest version `0.3.0`, an early preview of Asset-Free events has been added.  
   This workflow is additional, and non-blocking for parallel testing by the DataTrails platform.

## Configuration

The DataTrails Link requires minimal configuration in the conserver setup.

- Add the following datatrails configurations to the conserver configuration file (`config.yml`)
- Replace `"<your_client_id>"` and `"<your_client_secret>"` with your [DataTrails API credentials](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/)
- Set `vcon_operation` to differentiate what operation is being recorded on DataTrails/SCITT.  
- The DataTrails `arc_display_type` is configured as: `"vcon_operation"`, enabling [configurable permissions on Event Types](https://docs.datatrails.ai/platform/administration/sharing-access-outside-your-tenant/#creating-an-obac-policy)
- `partner_id` enables tracking which customer conserver links should be associated with their partner.
  The value will be provided by your DataTrails contact.

```yaml
links:
  datatrails-created:
    module: links.datatrails
    options:
      api_url: "https://app.datatrails.ai/archivist"
      vcon_operation: "vcon_created"
      partner_id: "your-company-name"
      auth:
        type: "OIDC-client-credentials"
        token_endpoint: "https://app.datatrails.ai/archivist/iam/v1/appidp/token"
        client_id: "<your_client_id>"
        client_secret: "<your_client_secret>"
  datatrails_consent_revoked:
    module: links.datatrails
    options:
      api_url: "https://app.datatrails.ai/archivist"
      vcon_operation: "vcon_consent_revoked"
      auth:
        type: "OIDC-client-credentials"
        token_endpoint: "https://app.datatrails.ai/archivist/iam/v1/appidp/token"
        client_id: "<your_client_id>"
        client_secret: "<your_client_secret>"

chains:
  create_chain:
    links:
      - datatrails_created
    ingress_lists:
      - create_ingress
    egress_lists:
      - default_egress
    enabled: 1
  consent_revoked_chain:
    links:
      - datatrails_consent_revoked
    ingress_lists:
      - consent_ingress
    egress_lists:
      - default_egress
    enabled: 1
```

## Verifying vCons

DataTrails provides several APIs for verifying the integrity and inclusion of changes to a vCons history.

Please see [DataTrails vCon Templates](https://docs.datatrails.ai/developers/templates/vcons/) for more info.

## Development and Testing

### Running Tests

Running within a docker environment is an easy way run tests, with a known environment.

To run the tests for the DataTrails Link:

1. Start the Docker environment:

    ```bash
    docker compose up -d
    ```

1. Exec into the conserver container

    ```bash
    docker exec -it vcon-server-api-1 bash
    ```

1. Install pytest:

   ```bash
   pip install pytest
   ```

1. Run the tests:

   ```bash
   pytest server/links/datatrails/
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

## Troubleshooting

- If you encounter authentication issues, ensure your `datatrails_client_id` and `datatrails_client_secret` are correct and have the necessary permissions in DataTrails.  
  See [Creating Access Tokens Using a Custom Integration][datatrails-tokens]
- Check the conserver logs for any error messages related to the DataTrails Link.
- Verify that your vCons contain the expected data and tags.

## Version History

### `0.3.0`

_**Note: BREAKING CHANGE**_

- Configuration for DataTrails has changed
- This version adds a preview of [Asset-free Events](https://docs.datatrails.ai/developers/api-reference/events-api/), as a non-blocking addition for parallel testing in the DataTrails platform.
- Asset-free events uses version 1 `/v1/events` to differentiate from the `/v2/assets` APIs.  
  This change required a change to the `api_url` configuration.  
  Your configuration will have:  
  `api_url: "https://app.datatrails.ai/archivist/v2"`  
  **WHICH HAS BEEN CHANGED** to  
  `api_url: "https://app.datatrails.ai/archivist"`  
  moving `/v2` to the asset call, and uses `v1/events` for the new Asset Free events.

## Support

For issues, questions, or contributions, please open an issue in the GitHub repository or contact [DataTrails Support](https://support.datatrails.ai/)

## License

The [DataTrails Asset Link is open-sourced under the MIT license](./LICENSE).

[datatrails-tokens]:  https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/
[datatrails-events]:  https://docs.datatrails.ai/developers/api-reference/events-api/
[scitt-scrapi]:       https://datatracker.ietf.org/doc/draft-ietf-scitt-scrapi/
[scitt-link]:         https://github.com/vcon-dev/vcon-server/tree/main/server/links/scitt
[scitt-architecture]: https://datatracker.ietf.org/wg/scitt/about/
[datatrails-vcon-template]: https://docs.datatrails.ai/developers/templates/vcons/