# tag_router

Routes vCon objects to one or more Redis lists based on their tags. Useful for fanning out processed vCons into category-specific queues without duplicating chain configuration.

## Configuration

```yaml
links:
  tag_router:
    module: links.tag_router
    options:
      tag_routes:
        urgent: urgent_vcons
        billing: billing_queue
      forward_original: true
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tag_routes` | dict | `{}` | Mapping of tag name to target Redis list name. When a vCon carries a matching tag, its UUID is pushed to that list. Multiple tags can match and route simultaneously. |
| `forward_original` | bool | `true` | If `true`, the link returns the vCon UUID so processing continues down the chain. If `false`, returns `None` to stop further processing after routing. |

## Example

```yaml
chains:
  route_by_tag:
    links:
      - analyze_and_label
      - tag_router:
          tag_routes:
            escalation: escalation_queue
            billing: billing_queue
            praise: praise_queue
          forward_original: true
    storages:
      - postgres
    ingress_lists:
      - transcribed
    enabled: 1
```

## Tag Format

The link reads tags from vCon attachments of type `tags`. Two body formats are supported:

- **List format** — each item is a `name:value` string; the part before the first colon is used as the tag name:

  ```json
  ["billing:true", "escalation:true"]
  ```

- **Dictionary format** — keys are used as tag names:

  ```json
  {"billing": "true", "escalation": "true"}
  ```

## Behavior

1. Retrieves the vCon from Redis.
2. Extracts all tag names from `tags`-typed attachments.
3. For each tag that matches a key in `tag_routes`, pushes the vCon UUID to the corresponding Redis list via `RPUSH`.
4. Returns the vCon UUID if `forward_original` is `true`, otherwise returns `None`.
5. If no `tag_routes` are configured, logs a warning and passes the vCon through unchanged.
