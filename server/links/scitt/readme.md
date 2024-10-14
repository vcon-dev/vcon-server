# SCITT Link

While vCons are authored, signed and stored in vCon services, assure integrity and inclusions protection through an implementation of [SCITT][scitt-architecture]

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

## Usage

The SCITT Link will automatically process vCons as they pass through the conserver providing integrity protection on the processed vCon.

## Configuration

The SCITT Link requires minimal configuration in the conserver setup.

- Add the following datatrails configurations to the conserver configuration file (`config.yml`)
- Replace `"<your_client_id>"` and `"<your_client_secret>"` with your [DataTrails API credentials](https://docs.datatrails.ai/developers/developer-patterns/getting-access-tokens-using-app-registrations/)
- Set `vcon_operation` to differentiate what operation is being recorded on DataTrails/SCITT.  
- The DataTrails `arc_display_type` is configured as: `"vcon_operation}"`, enabling [configurable permissions on Event Types](https://docs.datatrails.ai/platform/administration/sharing-access-outside-your-tenant/#creating-an-obac-policy)  

```yaml
links:
  scitt-create:
    module: links.scitt
    options:
      client_id: "<your_client_id>"
      client_secret: "<your_client_secret>"
      vcon_operation: "vcon-create"
  scitt-consent:
    module: links.scitt
    options:
      client_id: "<your_client_id>"
      client_secret: "<your_client_secret>"
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