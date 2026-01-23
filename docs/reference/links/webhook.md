# webhook

Sends vCon data to external HTTP endpoints.

## Configuration

```yaml
links:
  webhook:
    module: links.webhook
    options:
      url: https://api.example.com/webhook
      method: POST
      headers:
        Authorization: Bearer token
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `url` | string | Required | Webhook URL |
| `method` | string | `POST` | HTTP method |
| `headers` | dict | `{}` | Request headers |
| `timeout` | int | `30` | Request timeout |
| `include_vcon` | bool | `true` | Include full vCon |
| `retry_count` | int | `3` | Retry attempts |

## Example

```yaml
chains:
  notify:
    links:
      - analyze
      - webhook:
          url: https://api.example.com/vcon-processed
          method: POST
          headers:
            Authorization: Bearer ${WEBHOOK_TOKEN}
            Content-Type: application/json
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

## Payload

Default payload includes full vCon:

```json
{
  "vcon": {
    "uuid": "...",
    "created_at": "...",
    "parties": [...],
    "dialog": [...],
    "analysis": [...]
  }
}
```
