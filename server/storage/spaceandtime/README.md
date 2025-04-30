# Space and Time Storage

This module implements blockchain-based storage using Space and Time for the vCon server.

## Overview

Space and Time storage provides decentralized, immutable storage capabilities using blockchain technology, making it ideal for storing vCon data with verifiable integrity.

## Configuration

Required configuration options:

```yaml
storages:
  spaceandtime:
    module: storage.spaceandtime
    options:
      api_key: your_api_key           # Space and Time API key
      project_id: your_project_id     # Project ID
      database: vcon                  # Database name
      table: vcons                    # Table name
      network: mainnet                # Network (mainnet/testnet)
```

## Features

- Blockchain-based storage
- Immutable data records
- Verifiable integrity
- SQL query support
- Automatic metrics logging
- Data encryption
- Access control

## Usage

```python
from storage import Storage

# Initialize Space and Time storage
sxt_storage = Storage("spaceandtime")

# Save vCon data
sxt_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = sxt_storage.get(vcon_id)
```

## Implementation Details

The Space and Time storage implementation:
- Uses Space and Time SDK for blockchain operations
- Implements data encryption
- Supports SQL queries
- Provides access control
- Includes automatic metrics logging

## Dependencies

- spaceandtime-sdk
- cryptography

## Best Practices

1. Secure API key management
2. Implement proper access control
3. Use appropriate encryption
4. Monitor blockchain status
5. Regular backup verification
6. Implement proper error handling
7. Use appropriate data types
8. Monitor gas costs
9. Implement retry logic
10. Use appropriate network (mainnet/testnet) 