# Tag Link

The Tag link is a specialized plugin that adds tags to vCon objects. It provides a simple way to categorize and organize vCons with custom tags, enabling better filtering, searching, and organization of conversation data.

## Features

- Add multiple tags to vCon objects
- Simple configuration with tag list
- In-place modification of vCon objects
- Efficient tag management
- Minimal dependencies
- Seamless integration with vCon processing chains

## Configuration Options

```python
default_options = {
    "tags": ["iron", "maiden"],  # List of tags to add to the vCon
}
```

### Options Description

- `tags`: A list of tag names to add to the vCon. Each tag is added with the same name as both the tag name and value.

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. Adding each configured tag to the vCon
3. Storing the updated vCon back in Redis
4. Returning the vCon UUID for further processing

## Tag Format

Tags are added to the vCon with:
- Tag name: The string from the tags list
- Tag value: The same string as the tag name

## Error Handling

- Graceful handling of missing tags configuration
- Logs debug information about the process
- Continues processing even if some tags fail to be added

## Dependencies

- Redis for vCon storage
- Custom utilities:
  - vcon_redis
  - logging_utils

## Requirements

- Redis connection must be configured
- Appropriate permissions for vCon access and storage 