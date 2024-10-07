# DataTrails Link

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
```

## Usage

The DataTrails Link will automatically process vCons as they pass through the conserver.

For each vCon:

1. If no DataTrails asset exists for the vCon, a new asset will be created.  
   Note: this is a temporary solution as Assets are being deprecated.  
1. A DataTrails Event will be recorded, integrity protecting each vCon, setting the `subject` to `vcon://<vcon_uuid>` for correlation of events to each vCon

### Customizing Event Creation

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

### Contributing

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

For issues, questions, or contributions, please open an issue in the GitHub repository or contact the maintainer.

## License

The [DataTrails Asset Link is open-sourced under the MIT license](./LICENSE).
