# API Reference

## Base URL
```
https://your-domain.com/api
```

## Authentication

All API requests require authentication using an API token in the header:

```http
x-conserver-api-token: your-api-token
```

## Endpoints

### vCon Operations

#### Create vCon
```http
POST /api/vcon
```

**Request Body:**
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "vcon": "0.0.1",
  "created_at": "2024-01-15T10:30:00Z",
  "parties": [
    {
      "tel": "+1234567890",
      "name": "John Doe",
      "role": "customer"
    }
  ],
  "dialog": [],
  "attachments": [],
  "analysis": []
}
```

**Query Parameters:**
- `ingress_lists` (optional): Comma-separated list of ingress queues

**Response:** `201 Created`
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "created"
}
```

#### Get vCon
```http
GET /api/vcon/{uuid}
```

**Path Parameters:**
- `uuid`: vCon unique identifier

**Response:** `200 OK`
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "vcon": "0.0.1",
  "created_at": "2024-01-15T10:30:00Z",
  "parties": [...],
  "dialog": [...],
  "attachments": [...],
  "analysis": [...]
}
```

**Error Response:** `404 Not Found`
```json
{
  "detail": "vCon not found"
}
```

#### Update vCon
```http
PUT /api/vcon/{uuid}
```

**Request Body:** Complete vCon object

**Response:** `200 OK`

#### Delete vCon
```http
DELETE /api/vcon/{uuid}
```

**Response:** `204 No Content`

#### Get Multiple vCons
```http
GET /api/vcons?vcon_uuids=uuid1&vcon_uuids=uuid2
```

**Query Parameters:**
- `vcon_uuids`: List of UUIDs (repeatable)

**Response:** `200 OK`
```json
[
  {
    "uuid": "uuid1",
    "vcon": "0.0.1",
    ...
  },
  {
    "uuid": "uuid2",
    "vcon": "0.0.1",
    ...
  }
]
```

### Search Operations

#### Search vCons
```http
GET /api/vcons/search
```

**Query Parameters:** (at least one required)
- `tel`: Phone number
- `mailto`: Email address
- `name`: Party name

**Example:**
```http
GET /api/vcons/search?tel=+1234567890&name=John%20Doe
```

**Response:** `200 OK`
```json
[
  "550e8400-e29b-41d4-a716-446655440000",
  "660e8400-e29b-41d4-a716-446655440001"
]
```

#### Get vCons by Date Range
```http
GET /api/vcons_by_date_range
```

**Query Parameters:**
- `start`: ISO 8601 start date
- `end`: ISO 8601 end date

**Example:**
```http
GET /api/vcons_by_date_range?start=2024-01-01T00:00:00Z&end=2024-01-31T23:59:59Z
```

**Response:** `200 OK`
```json
[
  "uuid1",
  "uuid2",
  "uuid3"
]
```

### Chain Operations

#### Add to Chain Ingress
```http
POST /api/chain/{chain_name}/ingress
```

**Path Parameters:**
- `chain_name`: Name of the processing chain

**Request Body:**
```json
{
  "vcon_uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response:** `200 OK`
```json
{
  "message": "vCon added to test_chain ingress"
}
```

#### Process Chain Egress
```http
POST /api/chain/{chain_name}/egress
```

**Path Parameters:**
- `chain_name`: Name of the processing chain

**Query Parameters:**
- `vcon_uuid`: UUID of vCon to process

**Response:** `200 OK`
```json
{
  "vcon_uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Configuration

#### Get Configuration
```http
GET /api/config
```

**Response:** `200 OK`
```yaml
links:
  deepgram_link:
    module: links.deepgram_link
    options:
      DEEPGRAM_KEY: "***"
storages:
  postgres:
    module: storage.postgres
chains:
  main_chain:
    links: [...]
```

#### Update Configuration
```http
POST /api/config
```

**Request Body:** Complete configuration object

**Response:** `204 No Content`

### Dead Letter Queue

#### Get DLQ Contents
```http
GET /api/dlq?ingress_list=main_ingress
```

**Query Parameters:**
- `ingress_list`: Name of ingress list

**Response:** `200 OK`
```json
[
  "550e8400-e29b-41d4-a716-446655440000",
  "660e8400-e29b-41d4-a716-446655440001"
]
```

#### Reprocess DLQ
```http
POST /api/dlq/reprocess?ingress_list=main_ingress
```

**Query Parameters:**
- `ingress_list`: Name of ingress list

**Response:** `200 OK`
```json
{
  "reprocessed": 5
}
```

### Index Operations

#### Rebuild Search Index
```http
GET /api/index_vcons
```

**Response:** `200 OK`
```json
{
  "indexed": 1250
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid request parameters"
}
```

### 403 Forbidden
```json
{
  "detail": "Invalid API key"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error",
  "error": "Detailed error message"
}
```

## Rate Limiting

The API implements rate limiting to ensure fair usage:
- Default: 1000 requests per hour per API key
- Burst: 100 requests per minute

Rate limit headers:
```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1642082400
```

## Pagination

Large result sets support pagination:

```http
GET /api/vcons?page=1&page_size=100
```

Response headers:
```http
X-Total-Count: 5000
X-Page-Count: 50
Link: <.../vcons?page=2>; rel="next"
```

## Webhooks

### Webhook Payload
When configured, vCon data is sent to webhooks:

```json
{
  "event": "vcon.processed",
  "timestamp": "2024-01-15T10:30:00Z",
  "vcon": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    ...
  }
}
```

### Webhook Security
Webhooks include signature verification:

```http
X-Webhook-Signature: sha256=abc123...
```

## SDK Examples

### Python
```python
import requests

class VconClient:
    def __init__(self, base_url, api_token):
        self.base_url = base_url
        self.headers = {"x-conserver-api-token": api_token}
    
    def get_vcon(self, uuid):
        response = requests.get(
            f"{self.base_url}/api/vcon/{uuid}",
            headers=self.headers
        )
        return response.json()
    
    def create_vcon(self, vcon_data):
        response = requests.post(
            f"{self.base_url}/api/vcon",
            json=vcon_data,
            headers=self.headers
        )
        return response.json()
```

### JavaScript
```javascript
class VconClient {
  constructor(baseUrl, apiToken) {
    this.baseUrl = baseUrl;
    this.headers = {
      'x-conserver-api-token': apiToken,
      'Content-Type': 'application/json'
    };
  }
  
  async getVcon(uuid) {
    const response = await fetch(
      `${this.baseUrl}/api/vcon/${uuid}`,
      { headers: this.headers }
    );
    return response.json();
  }
  
  async createVcon(vconData) {
    const response = await fetch(
      `${this.baseUrl}/api/vcon`,
      {
        method: 'POST',
        headers: this.headers,
        body: JSON.stringify(vconData)
      }
    );
    return response.json();
  }
}
```

### cURL Examples
```bash
# Get vCon
curl -X GET https://api.example.com/api/vcon/550e8400-e29b-41d4-a716-446655440000 \
  -H "x-conserver-api-token: your-token"

# Create vCon
curl -X POST https://api.example.com/api/vcon \
  -H "x-conserver-api-token: your-token" \
  -H "Content-Type: application/json" \
  -d '{"vcon":"0.0.1","parties":[]}'

# Search vCons
curl -X GET "https://api.example.com/api/vcons/search?tel=+1234567890" \
  -H "x-conserver-api-token: your-token"
```