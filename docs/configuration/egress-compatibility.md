# Egress Format Compatibility

The conserver normalizes every vCon to the current spec version (`vcon: "0.4.0"`)
internally. Some deployments have downstream consumers (analytics pipelines,
indexes, BI tooling) that were built against an older vCon schema and cannot yet
be migrated. The **egress format compatibility** option lets a deployment emit a
legacy vCon format from individual egress points, without changing the canonical
representation used inside the pipeline.

## How it works

A single converter (`lib.vcon_egress_compat.to_legacy`) downgrades an outgoing
payload to a target legacy version. It is applied **only** at the egress point
you opt in, and only to the emitted/persisted copy — the canonical vCon held in
Redis is never modified. The converter never mutates its input.

This is the inverse of the read/write normalization the conserver applies to
bring legacy producers up to the current spec, so a downgraded payload that is
later re-ingested normalizes back up cleanly.

## Enabling it

Set `egress_format_version` to a supported legacy version string in the options
of any of the egress points below. Leave it unset for the default behavior
(current spec, byte-identical to a deployment without this feature).

### Storage backends

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      # ... connection options ...
      egress_format_version: "0.0.1"
  s3:
    module: storage.s3
    options:
      # ... connection options ...
      egress_format_version: "0.0.1"
  elasticsearch:
    module: storage.elasticsearch
    options:
      # ... connection options ...
      egress_format_version: "0.0.1"
```

### Webhook link

```yaml
links:
  my_webhook:
    module: links.webhook
    options:
      webhook-urls:
        - https://downstream.example.com/ingest
      egress_format_version: "0.0.1"
```

An unsupported version string raises an error at processing time rather than
emitting a wrong payload.

## Supported version mappings

| Target | Status |
| --- | --- |
| `0.0.1` | Supported |

### Field deltas applied for `0.0.1`

| Current spec (0.4.0) | Legacy (0.0.1) | Scope |
| --- | --- | --- |
| `vcon: "0.4.0"` | `vcon: "0.0.1"` | top level |
| `amended` | `appended` | top level |
| `critical` | `must_support` | top level + dialog / analysis entries |
| `purpose` | `type` | attachments (only when `type` is absent) |
| `mediatype` | `mimetype` | dialog + attachments |
| `schema` | `schema_version` | dialog + analysis |
| `body` as JSON string + `encoding: "json"` | native object/array + `encoding: "none"` | analysis + attachments |
| empty `group` / `redacted` omitted | re-added as `group: []`, `redacted: {}`, `appended: null` | top level |

The JSON-body conversion re-inflates analysis and attachment bodies that the
spec write-path serializes to strings. Dialog bodies are not serialized on
write and are left unchanged.

## Known gaps and notes

- **Attachment `type` vs. `purpose`:** for attachments that already carry a
  `type` value (e.g. the `lawful_basis` extension, which uses `type` as its
  value), the value is preserved rather than overwritten.
- **Custom/extension fields** (e.g. application-specific top-level keys or
  `vendor_schema`) are passed through unchanged in both directions.
- **Coverage:** the supported delta set reflects the differences between the
  current spec and `0.0.1`. New downstream requirements should be validated
  against the target schema and added here before relying on them.
- **Internal representation is unaffected:** enabling the option on one egress
  point does not change any other egress point or the in-pipeline vCon.
