# jq_link

Filters vCons with jq expressions.

## Configuration

```yaml
links:
  jq_filter:
    module: links.jq_link
    options:
      filter: '.attachments | length > 0'
      forward_matches: true
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `filter` | string | `"."` | jq expression evaluated against the vCon |
| `forward_matches` | boolean | `true` | Forward matches when `true`, or forward non-matches when `false` |

## Examples

```yaml
links:
  has_analysis:
    module: links.jq_link
    options:
      filter: '.analysis | length > 0'
      forward_matches: true

  skip_empty_analysis:
    module: links.jq_link
    options:
      filter: '.analysis | length == 0'
      forward_matches: false
```

## Mixed-Type `body` Arrays

Some legacy vCons contain mixed values inside attachment or analysis `body`
arrays. For example, a tags-like array may contain strings plus integers or
objects. Raw jq string functions such as `startswith()` fail on non-string
inputs.

`jq_link` now retries once with string-only `body` arrays when jq raises a
string-input type error. That hardens common filters that scan `body[]` values
for tag prefixes.

For new filters, prefer explicit string guards:

```jq
.attachments[0]
| select(.body[] | strings | startswith("call_type:") and . != "call_type:2")
```

or:

```jq
.attachments[0]
| select(any(.body[]; type == "string" and startswith("call_type:") and . != "call_type:2"))
```

## Behavior

If the jq expression returns a truthy first result, the link treats the vCon as
a match. Invalid filters or runtime jq failures are logged and the vCon is
filtered out.
