# Microsoft Dataverse Storage

This module implements storage capabilities for vCon server using Microsoft Dataverse, a cloud-based business application platform that's part of the Microsoft Power Platform.

## Overview

Microsoft Dataverse storage allows vCon data to be stored in the Microsoft Dataverse environment as custom entities. This provides integration with Microsoft Power Platform applications and the broader Microsoft ecosystem.

## Prerequisites

1. Microsoft Dataverse environment 
2. Azure AD app registration with proper API permissions
3. Custom entity in Dataverse for vCon storage

## Configuration

Required configuration options in your config.yml:

```yaml
storages:
  dataverse:
    module: server.storage.dataverse
    options:
      url: "https://your-org.crm.dynamics.com"  # Your Dataverse environment URL
      api_version: "9.2"                       # Dataverse API version
      tenant_id: "your-tenant-id"              # Azure AD tenant ID
      client_id: "your-app-id"                 # Azure AD client ID
      client_secret: "your-client-secret"      # Azure AD client secret
      entity_name: "vcon_storage"              # Custom entity name in Dataverse
      uuid_field: "vcon_uuid"                  # Field name for vCon UUID
      data_field: "vcon_data"                  # Field name for vCon JSON data
      subject_field: "vcon_subject"            # Field name for vCon subject
      created_at_field: "vcon_created_at"      # Field name for vCon creation date
```

## Features

- Azure AD authentication using MSAL
- Custom entity creation and updates
- JSON serialization of vCon data
- Automatic token acquisition and refresh
- Error handling and logging

## Usage

```python
from storage import Storage

# Initialize Dataverse storage
dataverse_storage = Storage("dataverse")

# Save vCon data
dataverse_storage.save(vcon_id)

# Retrieve vCon data
vcon_data = dataverse_storage.get(vcon_id)
```

## Dataverse Entity Setup

Before using this storage module, you need to create a custom entity in your Dataverse environment with these fields:

1. `vcon_uuid` (Single Line of Text) - Primary field to store the vCon UUID
2. `vcon_data` (Multiple Lines of Text) - To store the full vCon JSON data
3. `vcon_subject` (Single Line of Text) - To store the vCon subject for easier retrieval
4. `vcon_created_at` (DateTime) - To store the vCon creation timestamp

You can create this entity using the Power Apps portal or Dataverse Web API.

## Implementation Details

The Dataverse storage implementation:
- Uses Microsoft Authentication Library (MSAL) for authentication
- Leverages the Dataverse Web API for CRUD operations
- Properly handles token acquisition and refresh
- Provides comprehensive error handling and logging
- Includes optimized query patterns

## Dependencies

- msal
- requests

## Security Considerations

1. Store client secrets securely and never commit them to source control
2. Use least privilege principle for the Azure AD app registration
3. Implement proper error handling to avoid leaking sensitive information
4. Consider implementing custom encryption for sensitive vCon data

## Best Practices

1. Regularly rotate client secrets
2. Monitor API rate limits and implement retry logic
3. Use batch operations for bulk data
4. Implement proper logging and monitoring
5. Consider implementing caching for frequently accessed data
6. Ensure proper error handling
7. Use connection pooling
8. Implement retry logic for transient errors