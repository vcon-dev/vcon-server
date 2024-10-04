# DataTrails Link

## Overview

The DataTrails Asset Link is a conserver link designed to integrate vCon (virtual conversation) data with the [DataTrails API](https://docs.datatrails.ai/developers/api-reference/).
The DataTrails Asset Link allows for the creation of DataTrails Events based on vCon information, enabling seamless tracking and management of conversation-related assets.

## Features

- Automatic creation of [DataTrails Events](https://docs.datatrails.ai/developers/api-reference/events-api/) from vCon data
- Appending DataTrails Events with new vCon information
- Automatic token management and refresh for DataTrails API authentication
- Configurable asset attributes and behaviors
- Event recording for vCon updates

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

To use the DataTrails Asset Link, you need to configure it in your conserver setup.
Add the following to your conserver configuration file, replacing `"<your_client_id>"` and `"<your_client_secret>"` with your actual [DataTrails API credentials](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/).

```yaml
links:
  datatrails:
    module: links.datatrails
    options:
      datatrails_client_id: "<your_client_id>"
      datatrails_client_secret: "<your_client_secret>"
```

## Usage

The DataTrails Asset Link will automatically process vCons as they pass through the conserver.

For each vCon:

1. If no DataTrails asset exists for the vCon, a new asset will be created
1. A DataTrails Event will be recorded, integrity protecting the latest vCon, setting the `subject` to `vcon://<vcon_uuid>` for correlation of events to each vCon

### Customizing Asset Creation and Updates

You can customize how events are created by setting specific tags in your vCon before it's processed by this link:

- `asset_name`: Use this to set a custom name for the asset.
- `datatrails_event_attributes`: JSON string of additional attributes for the event.

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
