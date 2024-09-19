# DataTrails Asset Link

## Overview

The DataTrails Asset Link is a conserver link designed to integrate vCon (virtual conversation) data with the [DataTrails API](https://docs.datatrails.ai/developers/api-reference/).
The DataTrails Asset Link allows for the creation of DataTrails Events based on vCon information, enabling seamless tracking and management of conversation-related assets.

## Features

- Automatic creation of [DataTrails Events](https://docs.datatrails.ai/developers/api-reference/events-api/) from vCon data
- Appending DataTrails Events with new vCon information
- Automatic token management and refresh for DataTrails API authentication
- Configurable asset attributes and behaviors
- Event recording for asset updates

## Prerequisites

- Python 3.7+
- Access to a DataTrails account with API credentials
- Conserver setup with vCon support

## Installation

1. Clone this repository or copy the `datatrails_asset_link.py` file into your conserver's `links` directory.

2. Install the required dependencies:

   ```bash
   pip install requests
   ```

## Configuration

To use the DataTrails Asset Link, you need to configure it in your conserver setup.
Add the following to your conserver configuration file, replacing `"your_client_id"` and `"your_client_secret"` with your actual [DataTrails API credentials](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/).

```yaml
links:
  - name: datatrails_asset_link
    module: datatrails_asset_link
    options:
      api_url: "https://app.datatrails.ai/archivist/v2/assets"
      auth_url: "https://app.datatrails.ai/archivist/iam/v1/appidp/token"
      client_id: "your_client_id"
      client_secret: "your_client_secret"
      default_behaviours:
        - "RecordEvidence"
      default_attributes:
        arc_display_type: "DataTrails Asset"
        arc_description: "Asset created by DataTrails conserver link"
```

## Usage

The DataTrails Asset Link will automatically process vCons as they pass through the conserver.

For each vCon:

1. If no DataTrails asset exists for the vCon, a new asset will be created.
1. If an asset already exists, it will be updated with new information from the vCon.
1. An event will be recorded for the asset, capturing the latest vCon data.

### Customizing Asset Creation and Updates

You can customize how assets are created and updated by setting specific tags in your vCon before it's processed by this link:

- `datatrails_asset_id`: Set this to link the vCon to an existing DataTrails asset.
- `asset_name`: Use this to set a custom name for the asset.
- `datatrails_event_type`: Specify the type of event to be recorded (default is "VConUpdate").
- `datatrails_event_attributes`: JSON string of additional attributes for the event.
- `datatrails_asset_attributes`: JSON string of additional attributes for the asset.

Example of setting a custom tag in a vCon:

```python
vcon.add_tag("asset_name", "Customer Interaction 12345")
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
   pytest path/to/test_datatrails_asset_link.py
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

- If you encounter authentication issues, ensure your `client_id` and `client_secret` are correct and have the necessary permissions in DataTrails.
- Check the conserver logs for any error messages related to the DataTrails Asset Link.
- Verify that your vCons contain the expected data and tags.

## Support

For issues, questions, or contributions, please open an issue in the GitHub repository or contact the maintainer.

## License

The [DataTrails Asset Link is open-sourced under the MIT license](./LICENSE).
