# Tag Router Link

The Tag Router link routes vCon objects to different Redis lists based on their tags. It supports name-only matching (any value) and exact `"name:value"` matching, plus optional AND rules that require all listed tags to be present.

## Features

- Route vCons to different Redis lists based on tag content
- **Tag matching**: name-only (e.g. `category`) or exact full tag (e.g. `category:action`)
- **AND rules** (`tag_route_rules`): route only when the vCon has *all* required tags
- Support for multiple tag formats in attachments (list and dictionary)
- Configurable forwarding behavior
- Efficient Redis list management

## Configuration Options

```python
default_options = {
    "tag_routes": {
        "important": "important_vcons",   # OR logic: route if vCon has this tag (any value)
        "category:action": "action_list"  # exact: route only when tag is "category:action"
    },
    "tag_route_rules": [                  # AND logic: route only when vCon has ALL listed tags
        {"tags": ["tag1:value1", "tag2:value2"], "target_list": "target_ingress"}
    ],
    "forward_original": True
}
```

### Options Description

- **`tag_routes`**: Dictionary mapping tag keys to target Redis list names (OR logic). A key can be a **name only** (e.g. `"important"`) to match any tag with that name, or a **full tag** (e.g. `"category:action"`) to match only that exact tag.
- **`tag_route_rules`**: List of rules with AND logic. Each rule has `tags` (list of tag keys) and `target_list`. The vCon is routed to that list only when it has *all* of the listed tags.
- **`forward_original`**: If True, processing continues after routing. If False, the link returns None to stop further processing.

## Usage

The link:
1. Retrieves the vCon from Redis
2. Extracts tags from attachments and builds a match set (tag names and full `"name:value"` strings)
3. Evaluates `tag_route_rules` (AND): routes to each rule’s target list when the vCon has all required tags
4. Evaluates `tag_routes` (OR): routes to each list whose key is in the match set
5. Returns the vCon UUID or None according to `forward_original`

## Tag Format and Matching

Attachments can use:
1. **List format**: `["tag_name:value", "another_tag:value"]`
2. **Dictionary format**: `{"tag_name": "value", "another_tag": "value"}` (only keys are used for matching)

**Matching:** A **name-only** key (e.g. `"category"`) matches any tag with that name. A **full tag** key (e.g. `"category:action"`) matches only when the vCon has that exact tag.

## Error Handling

- Skips when neither `tag_routes` nor `tag_route_rules` is configured
- Logs debug information about the routing process
- Continues processing even if some tags don't have matching routes
- Proper handling of missing or malformed tags

## Dependencies

- Redis for vCon storage and list management
- Custom utilities:
  - vcon_redis
  - logging_utils

## Requirements

- Redis connection must be configured
- Appropriate permissions for vCon access and storage
- Tags must be present in vCon attachments
- Target Redis lists must be accessible

## Common Use Cases

- Distributing vCons to different processing queues based on priority
- Organizing vCons into category-specific lists
- Implementing tag-based workflow routing
- Creating separate storage locations for different types of conversations
- Building tag-based notification systems 