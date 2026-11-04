# delay

Sleeps for a set time and passes the vCon on. It is a test aid for watching concurrent workers, and has no use in production chains.

Module: `links.delay`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `seconds` | number | `5` | Time to sleep. A negative value logs a warning and counts as 0 |

## Follow the processing steps

The link sleeps, blocking its worker for that time. It never reads the vCon. See [Workers](../../configuration/workers.md) for `CONSERVER_VCON_CONCURRENCY`.

## Read the return value

Always returns the uuid.

## Inspect the vCon changes

None.

## Copy a configuration example

```yaml
links:
  slow_down:
    module: links.delay
    options:
      seconds: 5
```
