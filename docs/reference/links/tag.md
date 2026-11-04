# tag

Adds fixed tags to a vCon.

Module: `links.tag`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `tags` | list or dict | `["iron", "maiden"]` | Tags to add. See below for the forms |

The link does not merge `default_options`. If `options` omits `tags`, the link adds nothing. It never uses the default list.

`tags` takes three forms.

| Form | Example | Result |
|---|---|---|
| List of `name:value` strings | `- department:sales` | `department:sales` |
| List of bare names | `- processed` | `processed:processed` |
| Dict of name to value | `department: sales` | `department:sales` |

## Follow the processing steps

1. Load the vCon.
2. Turn `tags` into name and value pairs and add each one.
3. Save the vCon.

## Read the return value

Returns the uuid, or `None` when the vCon is missing.

## Inspect the vCon changes

Tags go in the `tags` attachment. `Vcon.add_tag` creates the attachment if needed and appends `name:value` to its list. Tags are not deduplicated.

The attachment has `purpose: "tags"` and `encoding: "json"`. `add_tag` writes the list as a JSON string in `body`, and readers in this repo decode it. It does not set `start`, `party`, `dialog` or `mediatype`.

## Copy a configuration example

```yaml
links:
  label_sales:
    module: links.tag
    options:
      tags:
        - department:sales
        - processed
```
