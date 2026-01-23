# tag

Adds static tags to vCons.

## Configuration

```yaml
links:
  tag:
    module: links.tag
    options:
      tags:
        - processed
        - v1
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `tags` | list | `[]` | List of tags to add |

## Example

```yaml
chains:
  tagging:
    links:
      - tag:
          tags:
            - processed
            - team_a
            - priority_normal
    storages:
      - redis_storage
    ingress_lists:
      - default
    enabled: 1
```

## Alternative Format

Tags can be key-value pairs:

```yaml
links:
  tag:
    module: links.tag
    options:
      tags:
        - name: status
          value: processed
        - name: version
          value: "1.0"
```

## Output

Adds tags to vCon metadata.
