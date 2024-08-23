```markdown
# DataTrails Asset Link

## Overview

The DataTrails Asset Link is a conserver link designed to integrate vCon (virtual conversation) data with the DataTrails API. It allows for the creation and updating of assets in DataTrails based on vCon information, enabling seamless tracking and management of conversation-related assets.

## Features

- Automatic creation of DataTrails assets from vCon data
- Updating existing DataTrails assets with new vCon information
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

   ```
   pip install requests
   ```

## Configuration

To use the DataTrails Asset Link, you need to configure it in your conserver setup. Add the following to your conserver configuration file:

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

Replace `your_client_id` and `your_client_secret` with your actual DataTrails API credentials.

## Usage

The DataTrails Asset Link will automatically process vCons as they pass through the conserver. For each vCon:

1. If no DataTrails asset exists for the vCon, a new asset will be created.
2. If an asset already exists, it will be updated with new information from the vCon.
3. An event will be recorded for the asset, capturing the latest vCon data.

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

   ```
   pip install pytest
   ```

2. Run the tests:

   ```
   pytest path/to/test_datatrails_asset_link.py
   ```

### Contributing

Contributions to improve the DataTrails Asset Link are welcome. Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Write tests for your changes.
4. Implement your changes.
5. Run the tests to ensure they all pass.
6. Submit a pull request with a clear description of your changes.

## Troubleshooting

- If you encounter authentication issues, ensure your `client_id` and `client_secret` are correct and have the necessary permissions in DataTrails.
- Check the conserver logs for any error messages related to the DataTrails Asset Link.
- Verify that your vCons contain the expected data and tags.

## Support

For issues, questions, or contributions, please open an issue in the GitHub repository or contact the maintainer.

## License

The DataTrails Asset Link is open-sourced software licensed under the [MIT license](https://opensource.org/licenses/MIT).

```
MIT License

Copyright (c) [year] [fullname]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

