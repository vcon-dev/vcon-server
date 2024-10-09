# DataTrails Link

![image](https://github.com/datatrails/datatrails-scitt-samples/blob/1de38b563c70ae96cd1983227d00675b222932ef/DataTrails_Horizontal_Logo_Black.png?raw=true)

While the vCon is authored, signed and stored in the vCon/Conserver services, the guarantee of integrity protection can be assured through SCITT.

Most storage services provide the ability to create, modify and delete content.
How do you know your vCons weren't tampered with, or important updates were deleted?

> If a vCon disappeared in the woods, would you know?

With the SCITT capabilities of DataTrails, the integrity and inclusion of all vCons are recorded.
If you're in possession of a vCon that's not recorded on a SCITT ledger, how do you know it's a valid vCon, or the latest version of that vCon?

## Overview

The DataTrails Link is a conserver link designed to integrate vCon (virtual conversation) data with the [DataTrails API](https://docs.datatrails.ai/developers/api-reference/).
The DataTrails Link allows for the creation of DataTrails Events based on vCon information, enabling seamless tracking and management of conversation-related assets.

## Features

- Automatic creation of [DataTrails Events](https://docs.datatrails.ai/developers/api-reference/events-api/) from vCon data
- Appending DataTrails Events with new vCon information
- Automatic token management and refresh for DataTrails API authentication
- Configurable attributes

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

## Configuration

The DataTrails Link requires minimal configuration in the conserver setup.
Add the following to the conserver configuration file, replacing `"<your_client_id>"` and `"<your_client_secret>"` with the actual [DataTrails API credentials](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/).

```yaml
links:
  datatrails:
    module: links.datatrails
    options:
      datatrails_client_id: "<your_client_id>"
      datatrails_client_secret: "<your_client_secret>"
chains:
  datatrails_chain:
    links:
      - datatrails
    ingress_lists:
      - datatrails_ingress
    egress_lists:
      - datatrails_egress
    enabled: 1
```

## Usage

The DataTrails Link will automatically process vCons as they pass through the conserver providing integrity protection to the "moments that matter".

### Ledgering a vCon

For each vCon:

1. A [DataTrails Event]() will be recorded, integrity protecting each vCon, setting the `subject` to `vcon://<vcon_uuid>` for correlation of events to each vCon
1. If no DataTrails Asset exists for the vCon, a new asset will be created.  
   Note: this is a temporary solution as Assets are being deprecated.  

#### Customizing Event Creation

Customizing events are configured by setting specific tags in the vCon before it's processed by the DataTrails link

- `vcon_operation`: Set to differentiate what operation is being recorded on DataTrails/SCITT.  
  DataTrails supports [configurable permissions on Event Types](https://docs.datatrails.ai/platform/administration/sharing-access-outside-your-tenant/#creating-an-obac-policy)  
  The DataTrails `arc_display_type` is configured at: `f"vcon-{vcon_operation}"`, enabling permissions to specific vCon operations
- `vcon_operation_id`: Optionally Set to provide additional details for an operation
- `datatrails_metadata`: JSON array of additional attributes for each the event, in key/value format

Example of setting a custom tag in a vCon:

TODO: DISCUSS & possibly DELETE various tags
```python
vcon.add_tag("vcon_operation", "transcription")
vcon.add_tag("vcon_operation_id", "trans-id:abc123")
vcon.add_tag("datatrails_metadata", ["key":value1, "key2", value2])
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

- Query All Events for a Specific Conserver Chain  
  TODO: NOTE: `conserver_chain` is not yet plumbed through the Conserver

   ```bash
   DATATRAILS_EVENTS_URL="https://app.datatrails.ai/archivist/v2/assets/-/events"
   CONSERVER_CHAIN="datatrails_chain"
   curl -g -X GET \
     -H "@$HOME/.datatrails/bearer-token.txt" \
     "$DATATRAILS_EVENTS_URL?event_attributes.subject=vcon://$VCON" \
     + "&event_attributes.conserver_chain=SHA-256" \
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
   pytest datatrails-link-tests.py
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
  See [Creating Access Tokens Using a Custom Integration](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/)
- Check the conserver logs for any error messages related to the DataTrails Link.
- Verify that your vCons contain the expected data and tags.

## Support

For issues, questions, or contributions, please open an issue in the GitHub repository or contact [DataTrails Support](https://support.datatrails.ai/)

## License

The [DataTrails Asset Link is open-sourced under the MIT license](./LICENSE).
