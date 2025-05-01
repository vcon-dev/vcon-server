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
    userDid: "string"         # The user's DID
    userSigningKey: "string"  # The user's signing key
    auditServerUrl: ["http://jlinc-archive-server:8081"]  # List of JLINC audit server URLs to try
    apiServerUrl: ["http://jlinc-api-server:9090"]        # List of JLINC API server URLs to try
```

## Process

1. Retrieves the vCon from Redis
2. Sends the vCon to the JLINC API server for processing
3. Sends the processed vCon to the JLINC audit server
4. Returns success if both operations succeed, failure otherwise

## Error Handling

The link will try all provided API server URLs and audit server URLs in order until successful. If all attempts fail, the link will return a failure status. 