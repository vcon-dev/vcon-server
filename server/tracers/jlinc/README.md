# JLINC Link

This link processes vCons through the JLINC API and sends them to the JLINC audit server.

## Configuration

The JLINC link requires the following configuration options:

```yaml
jlinc:
  module: links.jlinc
  ingress-lists: []
  egress-lists: []
  options:
    data_store_api_url: http://jlinc-server:9090       # The Datastore API URL from the JLINC interface
    data_store_api_key: 4a0f1a0c...                    # The Datastore API Key from the JLINC interface
    archive_api_url: http://jlinc-server:9090          # The Archive API URL from the JLINC interface
    archive_api_key: ac4f95c8a2...                     # The Archive API Key from the JLINC interface
    system_prefix: VCONTest                            # The prefix to use for identities in the JLINC DID
    agreement_id: 00000000-0000-0000-0000-000000000000 # The agreement ID, use all zeros for the general auditing nil-agreement
```

## Process

1. Retrieves the vCon from Redis
2. Sends the vCon to the JLINC API server for processing
3. Sends the processed vCon to the JLINC audit server
4. Returns success if both operations succeed, failure otherwise

## Error Handling

The link will try all provided API server URLs and audit server URLs in order until successful. If all attempts fail, the link will return a failure status. 