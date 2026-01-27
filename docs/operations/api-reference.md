# API Reference

Complete reference for all vCon Server REST API endpoints.

## Base URL

```
http://localhost:8000/api
```

The base path can be configured with `API_ROOT_PATH` environment variable.

## Authentication

All endpoints (except health) require authentication via header:

```bash
curl -H "x-conserver-api-token: your-token" ...
```

Header name configurable via `CONSERVER_HEADER_NAME`.

## System Endpoints

### Health Check

Check if the API server is healthy.

```http
GET /health
```

**Authentication:** Not required

**Response:**

```json
{
  "status": "healthy"
}
```

**Example:**

```bash
curl http://localhost:8000/api/health
```

### Version

Get server version information.

```http
GET /version
```

**Authentication:** Not required

**Response:**

```json
{
  "version": "2024.01.15",
  "git_commit": "a1b2c3d",
  "build_time": "2024-01-15T10:30:00Z"
}
```

**Example:**

```bash
curl http://localhost:8000/api/version
```

## vCon Endpoints

### List vCons

Get a paginated list of vCon UUIDs.

```http
GET /vcon
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `size` | int | 100 | Items per page |
| `since` | datetime | - | Filter by created_at >= |
| `until` | datetime | - | Filter by created_at <= |

**Response:**

```json
{
  "vcons": ["uuid-1", "uuid-2", "uuid-3"],
  "page": 1,
  "size": 100,
  "total": 250
}
```

**Example:**

```bash
curl "http://localhost:8000/api/vcon?page=1&size=50" \
  -H "x-conserver-api-token: $TOKEN"
```

### Get vCon

Retrieve a specific vCon by UUID.

```http
GET /vcon/{vcon_uuid}
```

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `vcon_uuid` | vCon UUID |

**Response:** Full vCon JSON object

**Example:**

```bash
curl http://localhost:8000/api/vcon/abc-123-def \
  -H "x-conserver-api-token: $TOKEN"
```

**Notes:**

- If not in Redis cache, syncs from storage backends
- Returns 404 if not found in any storage

### Create vCon

Create or update a vCon.

```http
POST /vcon
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `ingress_lists` | string | Comma-separated list of ingress queues |

**Request Body:** vCon JSON object

**Response:**

```json
{
  "uuid": "abc-123-def",
  "status": "created"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/api/vcon?ingress_lists=default" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{
    "vcon": "0.0.1",
    "uuid": "abc-123-def",
    "created_at": "2024-01-15T10:30:00Z",
    "parties": [
      {"tel": "+15551234567"}
    ],
    "dialog": []
  }'
```

### Batch Get vCons

Retrieve multiple vCons by UUID.

```http
GET /vcons
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `uuids` | string | Comma-separated UUIDs |

**Response:** Array of vCon objects

**Example:**

```bash
curl "http://localhost:8000/api/vcons?uuids=uuid-1,uuid-2,uuid-3" \
  -H "x-conserver-api-token: $TOKEN"
```

### Delete vCon

Delete a vCon from Redis and all storage backends.

```http
DELETE /vcon/{vcon_uuid}
```

**Path Parameters:**

| Parameter | Description |
|-----------|-------------|
| `vcon_uuid` | vCon UUID |

**Response:**

```json
{
  "uuid": "abc-123-def",
  "status": "deleted"
}
```

**Example:**

```bash
curl -X DELETE http://localhost:8000/api/vcon/abc-123-def \
  -H "x-conserver-api-token: $TOKEN"
```

## Search Endpoints

### Search vCons

Search vCons by metadata.

```http
GET /vcons/search
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tel` | string | Phone number (partial match) |
| `mailto` | string | Email address (partial match) |
| `name` | string | Party name (partial match) |

**Response:**

```json
{
  "vcons": ["uuid-1", "uuid-2"],
  "count": 2
}
```

**Example:**

```bash
# Search by phone
curl "http://localhost:8000/api/vcons/search?tel=+1555" \
  -H "x-conserver-api-token: $TOKEN"

# Search by email
curl "http://localhost:8000/api/vcons/search?mailto=@example.com" \
  -H "x-conserver-api-token: $TOKEN"

# Combined search (AND logic)
curl "http://localhost:8000/api/vcons/search?tel=+1555&name=John" \
  -H "x-conserver-api-token: $TOKEN"
```

## Chain Processing Endpoints

### Ingress

Add vCon UUIDs to a processing chain.

```http
POST /vcon/ingress
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ingress_list` | string | Yes | Ingress queue name |

**Request Body:**

```json
{
  "uuids": ["uuid-1", "uuid-2"]
}
```

**Response:**

```json
{
  "queued": 2,
  "ingress_list": "default"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/api/vcon/ingress?ingress_list=default" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{"uuids": ["uuid-1", "uuid-2"]}'
```

### Egress

Remove vCon UUIDs from a chain's output.

```http
GET /vcon/egress
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `egress_list` | string | Required | Egress queue name |
| `limit` | int | 10 | Maximum items to return |

**Response:**

```json
{
  "uuids": ["uuid-1", "uuid-2"],
  "count": 2,
  "egress_list": "processed"
}
```

**Example:**

```bash
curl "http://localhost:8000/api/vcon/egress?egress_list=processed&limit=5" \
  -H "x-conserver-api-token: $TOKEN"
```

### Count

Count vCons in an egress list.

```http
GET /vcon/count
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `egress_list` | string | Egress queue name |

**Response:**

```json
{
  "count": 42,
  "egress_list": "processed"
}
```

**Example:**

```bash
curl "http://localhost:8000/api/vcon/count?egress_list=processed" \
  -H "x-conserver-api-token: $TOKEN"
```

## External Ingress

### External Ingress

Submit vCons from external partners with scoped authentication.

```http
POST /vcon/external-ingress
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ingress_list` | string | Yes | Ingress queue (must match ingress_auth config) |

**Authentication:** Ingress-specific API key (configured in `ingress_auth`)

**Request Body:** vCon JSON object

**Response:**

```json
{
  "uuid": "abc-123-def",
  "status": "queued",
  "ingress_list": "partner_input"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/api/vcon/external-ingress?ingress_list=partner_input" \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: partner-specific-key" \
  -d '{"vcon": "0.0.1", "uuid": "...", ...}'
```

## Dead Letter Queue Endpoints

### List DLQ

Get vCons in the dead letter queue.

```http
GET /dlq
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ingress_list` | string | Yes | Original ingress list |

**Response:**

```json
{
  "uuids": ["uuid-1", "uuid-2"],
  "count": 2,
  "dlq_name": "DLQ:default"
}
```

**Example:**

```bash
curl "http://localhost:8000/api/dlq?ingress_list=default" \
  -H "x-conserver-api-token: $TOKEN"
```

### Reprocess DLQ

Move items from DLQ back to ingress for retry.

```http
POST /dlq/reprocess
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `ingress_list` | string | Yes | Original ingress list |

**Response:**

```json
{
  "reprocessed": 5,
  "ingress_list": "default"
}
```

**Example:**

```bash
curl -X POST "http://localhost:8000/api/dlq/reprocess?ingress_list=default" \
  -H "x-conserver-api-token: $TOKEN"
```

## Configuration Endpoints

### Get Configuration

Retrieve current server configuration.

```http
GET /config
```

**Response:** Full configuration object

**Example:**

```bash
curl http://localhost:8000/api/config \
  -H "x-conserver-api-token: $TOKEN" | jq .
```

### Update Configuration

Update server configuration.

```http
POST /config
```

**Request Body:** Configuration object (partial updates supported)

**Example:**

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -H "x-conserver-api-token: $TOKEN" \
  -d '{"chains": {...}}'
```

!!! warning "Configuration Updates"
    Configuration updates may require service restart to take full effect.

### Rebuild Index

Rebuild the vCon search index.

```http
GET /index_vcons
```

**Response:**

```json
{
  "status": "indexing",
  "count": 1000
}
```

**Example:**

```bash
curl http://localhost:8000/api/index_vcons \
  -H "x-conserver-api-token: $TOKEN"
```

## Error Responses

### 400 Bad Request

Invalid request format or parameters.

```json
{
  "detail": "Invalid UUID format"
}
```

### 403 Forbidden

Authentication failed.

```json
{
  "detail": "Invalid or missing API token"
}
```

### 404 Not Found

Resource not found.

```json
{
  "detail": "vCon not found: abc-123"
}
```

### 500 Internal Server Error

Server error.

```json
{
  "detail": "Internal server error"
}
```

## Rate Limiting

Rate limiting should be configured at the reverse proxy level:

```nginx
# nginx.conf
limit_req_zone $binary_remote_addr zone=api:10m rate=100r/s;

server {
    location /api {
        limit_req zone=api burst=200 nodelay;
        proxy_pass http://api:8000;
    }
}
```

## SDK Examples

### Python

```python
import requests

class VconClient:
    def __init__(self, base_url, token):
        self.base_url = base_url
        self.headers = {"x-conserver-api-token": token}
    
    def get_vcon(self, uuid):
        response = requests.get(
            f"{self.base_url}/vcon/{uuid}",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def create_vcon(self, vcon, ingress_list=None):
        params = {"ingress_lists": ingress_list} if ingress_list else {}
        response = requests.post(
            f"{self.base_url}/vcon",
            headers=self.headers,
            params=params,
            json=vcon
        )
        response.raise_for_status()
        return response.json()
    
    def search(self, tel=None, mailto=None, name=None):
        params = {k: v for k, v in {
            "tel": tel, "mailto": mailto, "name": name
        }.items() if v}
        response = requests.get(
            f"{self.base_url}/vcons/search",
            headers=self.headers,
            params=params
        )
        response.raise_for_status()
        return response.json()

# Usage
client = VconClient("http://localhost:8000/api", "your-token")
vcon = client.get_vcon("abc-123")
results = client.search(tel="+1555")
```

### JavaScript

```javascript
class VconClient {
  constructor(baseUrl, token) {
    this.baseUrl = baseUrl;
    this.headers = {
      'x-conserver-api-token': token,
      'Content-Type': 'application/json'
    };
  }

  async getVcon(uuid) {
    const response = await fetch(`${this.baseUrl}/vcon/${uuid}`, {
      headers: this.headers
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async createVcon(vcon, ingressList = null) {
    const url = new URL(`${this.baseUrl}/vcon`);
    if (ingressList) url.searchParams.set('ingress_lists', ingressList);
    
    const response = await fetch(url, {
      method: 'POST',
      headers: this.headers,
      body: JSON.stringify(vcon)
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async search({ tel, mailto, name } = {}) {
    const url = new URL(`${this.baseUrl}/vcons/search`);
    if (tel) url.searchParams.set('tel', tel);
    if (mailto) url.searchParams.set('mailto', mailto);
    if (name) url.searchParams.set('name', name);
    
    const response = await fetch(url, { headers: this.headers });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
}

// Usage
const client = new VconClient('http://localhost:8000/api', 'your-token');
const vcon = await client.getVcon('abc-123');
const results = await client.search({ tel: '+1555' });
```
