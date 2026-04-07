# jq_link

Filters vCons using a [jq](https://jqlang.github.io/jq/) expression. The link evaluates the expression against the vCon and either forwards or drops the vCon based on whether the result is truthy and the `forward_matches` setting.

No vCon content is modified — the link only decides whether to continue chain processing.

## Prerequisites

- The `jq` Python package must be installed (`pip install jq`).

## Configuration

```yaml
links:
  jq_link:
    module: links.jq_link
    options:
      filter: ".dialog | length > 0"
      forward_matches: true
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `filter` | string | `.` | A jq expression evaluated against the vCon dictionary. The first output value is cast to a boolean to determine a match. |
| `forward_matches` | bool | `true` | When `true`, the vCon is forwarded if the filter result is truthy. When `false`, the vCon is forwarded if the filter result is falsy (i.e. acts as a "drop if matches" gate). |

## Example

### Forward only vCons that have a transcript

```yaml
chains:
  requires_transcript:
    links:
      - jq_link:
          filter: '.analysis | map(select(.type == "transcript")) | length > 0'
          forward_matches: true
      - analyze
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

### Drop vCons with no dialogs

```yaml
chains:
  non_empty_only:
    links:
      - jq_link:
          filter: ".dialog | length == 0"
          forward_matches: false
      - deepgram_link
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

### Filter by a metadata attribute

```yaml
chains:
  cats_only:
    links:
      - jq_link:
          filter: '.meta.arc_display_type == "Cat"'
          forward_matches: true
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

## Common filter patterns

| Goal | Filter expression |
|------|-------------------|
| vCon has at least one dialog | `.dialog \| length > 0` |
| vCon has a transcript analysis | `.analysis[] \| select(.type == "transcript") \| any` |
| Dialog duration over 60 s | `.dialog[] \| select(.duration > 60) \| any` |
| Specific party role present | `.parties[] \| select(.role == "agent") \| any` |
| At least two parties | `.parties \| length >= 2` |
| Analysis list is empty | `.analysis \| length == 0` |

## Behavior

1. Retrieves the vCon from Redis and converts it to a dictionary.
2. Compiles and runs the jq `filter` expression.
3. Treats the first result as a boolean (`matches`).
4. Returns the vCon UUID when `matches == forward_matches`, otherwise returns `None` to halt the chain.
5. Returns `None` (drops the vCon) if the vCon cannot be found or the filter expression raises an error.
