# Webhook Link

The Webhook link is a specialized plugin that sends vCon objects to configured webhook URLs. It provides a flexible way to integrate vCon processing with external systems by forwarding vCon data to specified endpoints.

## Features

- Send vCon objects to multiple webhook URLs
- Configurable authentication headers
- API token support
- JSON payload formatting
- Response logging
- Seamless integration with vCon processing chains

## Configuration Options

```python
default_options = {
    "webhook-urls": ["https://example.com/webhook"],  # List of webhook URLs to send vCons to
    "auth_header": "Bearer your-auth-token",          # Authorization header value
    "api_token": "your-api-token"                     # API token for x-conserver-api-token header
}
```

### Options Description

- `webhook-urls`: A list of URLs where vCon data will be sent. The link will attempt to send the vCon to each URL in the list.
- `auth_header`: The value for the Authorization header in the webhook requests.
- `api_token`: The value for the x-conserver-api-token header in the webhook requests.

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Converting the vCon to a JSON dictionary
3. Sending POST requests to each configured webhook URL
4. Logging the response from each webhook
5. Continuing normal processing by returning the vCon UUID

## Request Format

The webhook requests include:
- HTTP Method: POST
- Content-Type: application/json
- Headers:
  - Authorization: Configured auth_header value
  - x-conserver-api-token: Configured api_token value
- Body: JSON representation of the vCon object

## Error Handling

- Logs debug information about the webhook process
- Logs response status codes and text from webhook endpoints
- Continues processing even if some webhook requests fail
- Maintains vCon processing chain by returning the vCon UUID

## Dependencies

- Redis for vCon storage
- Requests library for HTTP communication
- Custom utilities:
  - vcon_redis
  - logging_utils

## Requirements

- Redis connection must be configured
- Appropriate permissions for vCon access and storage
- Webhook URLs must be accessible
- Valid authentication credentials for webhook endpoints

## Common Use Cases

- Integrating vCon processing with external systems
- Building event-driven workflows
- Creating notification systems
- Implementing data synchronization
- Setting up monitoring and analytics pipelines 