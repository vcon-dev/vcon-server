# Tag Router Link

The Tag Router link is a specialized plugin that routes vCon objects to different Redis lists based on their tags. It provides a flexible way to organize and distribute vCons to different processing queues or storage locations based on their tag content.

## Features

- Route vCons to different Redis lists based on tag content
- Support for multiple tag formats (list and dictionary)
- Configurable forwarding behavior
- Flexible tag-based routing rules
- Efficient Redis list management
- Seamless integration with vCon processing chains

## Configuration Options

```python
default_options = {
    "tag_routes": {
        "important": "important_vcons",  # Route vCons with "important" tag to "important_vcons" list
        "urgent": "urgent_vcons"        # Route vCons with "urgent" tag to "urgent_vcons" list
    },
    "forward_original": True  # Whether to continue normal processing after routing
}
```

### Options Description

- `tag_routes`: A dictionary mapping tag names to target Redis list names. When a vCon has a tag matching a key in this dictionary, its UUID will be pushed to the corresponding Redis list.
- `forward_original`: A boolean indicating whether to continue normal processing after routing. If False, the link will return None to stop further processing.

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Extracting tags from attachments
3. Matching tags against configured routes
4. Pushing vCon UUIDs to appropriate Redis lists
5. Optionally continuing normal processing

## Tag Format

The link supports two tag formats in attachments:
1. List format: `["tag_name:value", "another_tag:value"]`
2. Dictionary format: `{"tag_name": "value", "another_tag": "value"}`

In both cases, only the tag name (before the colon in list format, or the key in dictionary format) is used for routing.

## Error Handling

- Graceful handling of missing tag routes configuration
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