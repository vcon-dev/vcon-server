# DataTrails Link

<img src="https://www.datatrails.ai/wp-content/uploads/2024/10/DataTrails_Horizontal_Logo_Black.svg" height="100">

While vCons are authored, signed and stored in vCon services, assure integrity and inclusions protection through the DataTrails implementation of [SCITT][scitt-architecture]

## Overview

Most storage services provide the ability to create, modify and delete content.
Which raises the question, can you guarantee your vCons weren't tampered with, or important updates weren't deleted?

> _If a vCon disappeared in the woods, would you know?_

With the SCITT capabilities of DataTrails, the integrity and inclusion of all vCons are recorded.
If you're in possession of a vCon that's not recorded on a SCITT ledger, how do you know it's a valid vCon, or the latest version of that vCon?

The DataTrails Link is a conserver link designed to integrate vCon (virtual conversation) data with the [DataTrails Events API][datatrails-events].
The DataTrails Link allows for the creation of DataTrails Events based on vCon information, enabling seamless tracking and management of conversation-related assets.
Setting the `vcon_operation` chain configuration, log different types of Events, based on which chain is executed.

## Features

- Automatic creation of [DataTrails Events][datatrails-events] from vCon data
- Appending DataTrails Events with new vCon information
- Automatic token management and refresh for DataTrails API authentication
- Configurable attributes

### vCon - DataTrails Attribute Mappings

The following vCon properties are mapped to DataTrails Attributes and SCITT.

See the [DataTrails vCon Template for more details][datatrails-vcon-template]

**DataTrails Event Attributes:**

The DataTrails Link creates a [DataTrails Event](https://docs.datatrails.ai/developers/api-reference/events-api/), equivalent to:

```json
{
  "operation": "Record",
  "behaviour": "RecordEvidence",
  "event_attributes": {
    "arc_display_type": "vcon_created",
    "conserver_link": "DataTrails",
    "conserver_link_name":  "datatrails_created",
    "conserver_link_version": "0.2.0",
    "payload_hash_alg": "SHA-256",
    "payload_preimage_content_type": "application/vcon+json",
    "payload": "5cdc3d525e...bfac2e948f31b61",
    "subject": "vcon://bbba043b-xxxx-xxxx-xxxx-ac3ddd0303af",
    "timestamp_declared": "2024-05-07T16:33:29.004994",
    "vcon_operation": "vcon_create",
    "vcon_draft_version": "00"
  }
}
```

There are different sources for the values:

- **config.yaml** - set in the conserver configuration, which can be unique per conserver chain configuration
- **Link code** - set within the DataTrails Link code, and not considered configurable
- **vcon** - pulled from the vcon object passed into the executing Link

| Source | Property | DataTrails Attribute | SCITT | Note |
| -      | -        | -                    | -    | -    |
| config.yaml | `vcon_operation` | `arc_display_type` | |used for default permissions,<br>_duplicate of vcon_operation_ |
| Link code | | `conserver_link` | `metamap.conserver_link` | The Link type, as named under the links folder |
| Link code | | `conserver_link_name` | `metamap.conserver_link_name` | The name of the link from config.yaml |
| Link code | | `conserver_link_version` | `metamap.conserver_link_version` | Version of the Link codebase |
| vcon | `hash` | `payload` | `protected-header.payload` | Content type of the vCon, prior to hashing |
| Link code | | `payload_hash_alg` | `protected-header.payload_hash_alg` | Hash algorithm of the vcon |
| Link code | | `payload_pre_image_content_type` | `protected-header.payload_pre_image_content_type` | Content Type of the vCon, prior to hashing<br>`application/vcon+json` |
| vcon | `vcon_uuid` | `subject` | `protected-header.cwt-claims.subject` | `vcon://` + \<Unique Identifier of the vCon>  |
| vcon | `vcon.updated_at` | `timestamp_declared` | `metamap.timestamp_declared`| Time the vCon was updated |
| Link code | | `vcon_draft_version` | `metamap.vcon_draft_version` | IETF draft version |
| config.yaml | `vcon_operation`| `vcon_operation` | `metamap.vcon_operation` | Task completed for the update |
| DataTrails | `partner_id`| N/A | `metamap.partner_id` | Partner associated with the customer's `Client_ID` |

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

1. A [DataTrails Event]() will be recorded, integrity protecting each vCon, setting the `subject` to `vcon://<vcon_uuid>` for correlation of events to each vCon
1. If no DataTrails Asset exists for the vCon, a new asset will be created.  
   _**Note:** this is a temporary solution as Assets are being deprecated._

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
      api_url: "https://app.datatrails.ai/archivist/v2"
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
      api_url: "https://app.datatrails.ai/archivist/v2"
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