# DataTrails Link

![DataTrails](https://www.datatrails.ai/wp-content/uploads/2024/10/DataTrails_Horizontal_Logo_Black.svg)

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

### DataTrails and SCITT

> _**Note:**_ The [IETF SCITT architecture][scitt-architecture] and [SCRAPI][scitt-scrapi] are in currently draft form.
> The [SCITT Link][scitt-link] conforms the draft version as specified in the `.scitt-version` property.
> To provide a production SLA, [DataTrails Events][datatrails-events] provides a SCITT like API that will continue to evolve as the SCITT draft matures.

## Features

- Automatic creation of [DataTrails Events][datatrails-events] from vCon data
- Appending DataTrails Events with new vCon information
- Automatic token management and refresh for DataTrails API authentication
- Configurable attributes

### vCon - DataTrails Attribute Mappings

The following vCon properties are mapped to DataTrails Attributes and SCITT.

There are different sources for the content:

- **config.yaml** - set in the conserver configuration, which can be unique per conserver chain configuration
- **Link code** - set within the DataTrails Link code, and not considered configurable
- **vcon** - pulled from the vcon object passed into the Link

| Source | Property | DataTrails Attribute | SCITT | Note |
| -      | -        | -                    | -    | -    |
| config.yaml | `vcon_operation` | `arc_display_type` | |used for default permissions,<br>_duplicate of vcon_operation_ |
| config.yaml | `vcon_operation`| `vcon_operation` | `metamap.vcon_operation` | used for filtering |
| config.yaml | `DataTrails-User-Agent` | `headers["DataTrails-User-Agent"]` | N/A | diagnostics for the source of the request |
| config.yaml | `partner_id` | `headers["DataTrails-Partner-ID"]` | N/A |used for tracing source requests |
| Link code | |  `conserver_link_version` | `metamap.link_version` | version control of data |
| Link code | | `payload_hash_alg` | `protected-header.payload_hash_alg` | Hash algorithm of the vcon |
| Link code | |  `payload_preimage_content_type` | `protected-header.payload_preimage_content_type` | Content type of the vCon |
| vcon | `hash` | `payload_hash_value` | `protected-header.payload_hash_value` |vCon Hash |
| vcon | `vcon_uuid` | `subject` | `protected-header.cwt-claims.subject` | Unique Identifier of the vCon |
| vcon | `vcon.updated_at or`<br>`vcon.created_at` | `vcon_updated_at` | `metamap.vcon_updated_at`| Created or Updated datetime |

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
- The DataTrails `arc_display_type` is configured as: `"vcon_operation}"`, enabling [configurable permissions on Event Types](https://docs.datatrails.ai/platform/administration/sharing-access-outside-your-tenant/#creating-an-obac-policy)  

```yaml
links:
  datatrails-create:
    module: links.datatrails
    options:
      datatrails_client_id: "<your_client_id>"
      datatrails_client_secret: "<your_client_secret>"
      vcon_operation: "vcon-create"
  datatrails-consent:
    module: links.datatrails
    options:
      datatrails_client_id: "<your_client_id>"
      datatrails_client_secret: "<your_client_secret>"
      vcon_operation: "vcon-consent"

chains:
  create_chain:
    links:
      - datatrails-create
    ingress_lists:
      - create_ingress
    egress_lists:
      - default_egress
    enabled: 1
  consent_chain:
    links:
      - datatrails-consent
    ingress_lists:
      - consent_ingress
    egress_lists:
      - default_egress
    enabled: 1
```

## Verifying vCons

DataTrails provides several APIs for verifying the integrity and inclusion of changes to a vCons history.
We'll also explore specific vCon scenarios, such as consent and revocation validation.

### Retrieving All vCon Events

For each important operation performed on a vCon, a DataTrails Event (SCITT Signed Statement) should be recorded.

To align with SCITT semantics, the vcon_uuid is set to the DataTrails `subject` event attribute. (`event_attributes.subject`)

To query the history of DataTrails Events for a given vCon, use the following:

- For bash/curl commands, configure the `.datatrails/bearer-token.txt` using the DataTrails [Creating Access Tokens](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/) developer docs.
- Query the collection of DataTrails Events, using the `subject` attribute.
  Set the `VCON` env variable to the `vcon_uuid`

   ```bash
   DATATRAILS_EVENTS_URL="https://app.datatrails.ai/archivist/v2/assets/-/events"
   VCON=bbba043b-d1aa-4691-8739-ac3ddd030390
   curl -g -X GET \
     -H "@$HOME/.datatrails/bearer-token.txt" \
     "$DATATRAILS_EVENTS_URL?event_attributes.subject=vcon://$VCON" \
     | jq
   ```

- Verify Inclusions of a Specific vCon Hash

   ```bash
   DATATRAILS_EVENTS_URL="https://app.datatrails.ai/archivist/v2/assets/-/events"
   VCON="bbba043b-d1aa-4691-8739-ac3ddd030390"
   VCON_HASH="eae12ce2ae12c7b1280921236857d2dc1332babd311ae0fbcab620bdb148fd0d"
   curl -g -X GET \
     -H "@$HOME/.datatrails/bearer-token.txt" \
     "$DATATRAILS_EVENTS_URL?event_attributes.subject=vcon://$VCON" \
     + "&event_attributes.payload_hash_alg=SHA-256" \
     + "&event_attributes.payload_hash_value=$VCON_HASH" \
     | jq
   ```

- Query Events for a Specific vCon for a Specific Operation

   ```bash
   DATATRAILS_EVENTS_URL="https://app.datatrails.ai/archivist/v2/assets/-/events"
   VCON="bbba043b-d1aa-4691-8739-ac3ddd030390"
   VCON_OPERATION="vcon-create"
   curl -g -X GET \
     -H "@$HOME/.datatrails/bearer-token.txt" \
     "$DATATRAILS_EVENTS_URL?event_attributes.subject=vcon://$VCON" \
     + "&event_attributes.vcon_operation=$VCON_OPERATION" \
     | jq
   ```

- Query All Events for a Specific Operations

   ```bash
   DATATRAILS_EVENTS_URL="https://app.datatrails.ai/archivist/v2/assets/-/events"
   VCON_OPERATION="vcon-create"
   curl -g -X GET \
     -H "@$HOME/.datatrails/bearer-token.txt" \
     "$DATATRAILS_EVENTS_URL?event_attributes.vcon_operation=$VCON_OPERATION" \
     | jq
   ```

- Limit Events Created by a Specific DataTrails Identity

   ```bash
   DATATRAILS_EVENTS_URL="https://app.datatrails.ai/archivist/v2/assets/-/events"
   VCON=bbba043b-d1aa-4691-8739-ac3ddd030390
   curl -g -X GET \
     -H "@$HOME/.datatrails/bearer-token.txt" \
     "$DATATRAILS_EVENTS_URL?event_attributes.subject=vcon://$VCON" \
     + "&principal_declared.issuer=https://app.datatrails.ai/appidpv1" \
     + "&principal_declared.subject=b5cfacfd-b918-4338-ad61-f4947477f874" \
     | jq
   ```

## Development and Testing

### Running Tests

To run the tests for the DataTrails Asset Link:

1. Install pytest:

   ```bash
   pip install pytest
   ```

2. Run the tests:

   ```bash
   pytest test_datatrails_link.py
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