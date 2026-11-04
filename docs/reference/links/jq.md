# jq_link

Passes or stops a vCon according to a jq expression.

Module: `links.jq_link`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `filter` | string | `.` | jq expression run against the vCon |
| `forward_matches` | bool | `true` | When true, matching vCons continue. When false, non-matching vCons continue |

## Follow the processing steps

1. Load the vCon and run the expression on its dict form.
2. Treat the vCon as a match if the first result is truthy. Later results are ignored, and no result means no match.
3. Forward the vCon if the match agrees with `forward_matches`.

Truthiness here is Python's, not jq's. A first result of `0`, `""`, `[]` or `{}` is not a match.

Some legacy vCons hold mixed values in `body` arrays, and jq string functions such as `startswith()` raise on the non-strings. When jq reports `requires string inputs`, the link retries once with those arrays reduced to their strings. For new filters, guard explicitly:

```jq
.attachments[0]
| select(any(.body[]; type == "string" and startswith("call_type:") and . != "call_type:2"))
```

## Read the return value

Returns the uuid to forward, or `None` to stop the chain. An invalid filter or any other jq error is logged and also returns `None`, so a broken expression drops every vCon and raises nothing. A missing vCon returns `None`.

A stopped chain skips its storages and egress lists.

## Inspect the vCon changes

None.

## Copy a configuration example

```yaml
links:
  has_analysis:
    module: links.jq_link
    options:
      filter: '.analysis | length > 0'
      forward_matches: true
```

## Track the metrics

`conserver.link.jq.vcon_filtered_out`, `conserver.link.jq.filter_errors` and `conserver.link.jq.string_body_array_retries`. See [Metrics](../metrics.md).
