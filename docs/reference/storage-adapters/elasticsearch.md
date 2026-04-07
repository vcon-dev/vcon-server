# elasticsearch

Indexes vCon components into Elasticsearch for full-text search and analytics. Each vCon is decomposed into separate documents stored across multiple indices: parties, attachments, analysis, and dialog.

## Prerequisites

- Elasticsearch 7.x or 8.x (self-hosted or Elastic Cloud)
- The `elasticsearch` Python package

```
pip install elasticsearch
```

## Configuration

### Self-Hosted

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      url: http://localhost:9200
      username: elastic
      password: changeme
      index_prefix: ""
```

### Elastic Cloud

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      cloud_id: my-deployment:dXMtZWFzdC0x...
      api_key: VnVhQ2ZHY0JDZGJrUW...
      index_prefix: prod_
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | `elasticsearch` | Adapter name |
| `cloud_id` | string | `""` | Elastic Cloud deployment ID. When set, `cloud_id` and `api_key` are used for authentication |
| `api_key` | string | `""` | Elastic Cloud API key |
| `url` | string | `None` | Self-hosted Elasticsearch URL (e.g. `http://localhost:9200`) |
| `username` | string | `None` | Basic auth username for self-hosted deployments |
| `password` | string | `None` | Basic auth password for self-hosted deployments |
| `ca_certs` | string | `None` | Path to CA certificate file for TLS verification |
| `index_prefix` | string | `""` | Prefix added to all index names (e.g. `prod_` yields `prod_vcon_dialog`) |

## Index Structure

vCon components are stored in separate indices based on type and role:

| Index Pattern | Description | Example |
|---------------|-------------|---------|
| `{prefix}vcon_parties_{role}` | Party records grouped by role | `vcon_parties_agent` |
| `{prefix}vcon_attachments_{type}` | Attachments grouped by type | `vcon_attachments_transcript` |
| `{prefix}vcon_analysis_{type}` | Analysis records grouped by type | `vcon_analysis_summary` |
| `{prefix}vcon_dialog` | All dialog entries | `vcon_dialog` |

Each document includes `vcon_id` and `started_at` fields (derived from the first dialog entry) for cross-index correlation. If a tenant attachment is present, `tenant_id` is also indexed.

## Example

```yaml
storages:
  elasticsearch:
    module: storage.elasticsearch
    options:
      url: https://elasticsearch:9200
      username: elastic
      password: ${ELASTICSEARCH_PASSWORD}
      ca_certs: /certs/ca.crt
      index_prefix: vcon_

chains:
  main:
    links:
      - transcribe
      - summarize
    storages:
      - elasticsearch
    ingress_lists:
      - default
    enabled: 1
```

## Queries

Search across Elasticsearch indices directly:

```bash
# Find all vCon components for a specific vCon UUID
GET vcon_*/_search
{
  "query": {
    "term": { "vcon_id": "abc-123-def" }
  }
}

# Full-text search across analysis summaries
GET vcon_analysis_summary/_search
{
  "query": {
    "match": { "body": "billing issue" }
  }
}

# Find all agent parties
GET vcon_parties_agent/_search
{
  "query": { "match_all": {} }
}
```

## Notes

- vCons with no dialog entries are silently skipped — at least one dialog entry is required for indexing.
- JSON-encoded string bodies in attachments and analysis are automatically parsed before indexing.
- The `delete` function removes all documents for a vCon across every `{prefix}vcon*` index using `delete_by_query`.
