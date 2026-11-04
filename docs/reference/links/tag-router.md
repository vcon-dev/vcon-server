# tag_router

Pushes the vCon's uuid to other Redis lists according to its tags.

Module: `links.tag_router`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `tag_routes` | dict | `{}` | Tag name to target Redis list |
| `forward_original` | bool | `true` | Continues the current chain after routing |

## Follow the processing steps

1. Load the vCon. If `tag_routes` is empty, log a warning and pass the vCon on.
2. Collect tag names from every attachment with `purpose` or legacy `type` of `tags`. In a list body, the name is the part before the first colon. A string with no colon is ignored. In a dict body, the keys are the names.
3. For each tag name with a route, push the uuid to the target list.

Routing matches on the tag name only. A vCon with `department:sales` and `department:support` pushes twice to the `department` route.

The target list receives the uuid only, through `VconQueue` in `lib.queue`. To process the vCon there, make the list an `ingress_lists` entry of a chain.

## Read the return value

| Case | Returns |
|---|---|
| vCon missing | `None` |
| `tag_routes` empty | The uuid, whatever `forward_original` says |
| Otherwise, `forward_original` true | The uuid |
| Otherwise, `forward_original` false | `None`, even if no route matched |

With `forward_original: false`, the chain stops here, so this chain's storages and egress lists do not run.

## Inspect the vCon changes

None.

## Copy a configuration example

```yaml
links:
  route_by_tag:
    module: links.tag_router
    options:
      tag_routes:
        urgent: urgent_vcons
        department: department_vcons
      forward_original: false
```

## Track the metrics

`conserver.link.tag_router.routes_matched` and `conserver.link.tag_router.routed_count`. See [Metrics](../metrics.md).
