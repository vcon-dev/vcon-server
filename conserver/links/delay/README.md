# Delay Link

The Delay link is a lightweight **testing fixture**. It sleeps for a configurable
number of seconds and then passes the vCon through the chain unchanged. It does
not read or modify the vCon.

Its purpose is to make a chain take a predictable amount of wall-clock time so
that concurrent processing behaviour can be observed during QA — for example,
verifying that per-worker in-flight concurrency (`CONSERVER_VCON_CONCURRENCY`)
actually processes multiple vCons in parallel rather than serially.

> This link is intended for test and staging environments. It is not meant to
> run in a production chain.

## Configuration Options

```python
default_options = {
    "seconds": 5  # how long to sleep before continuing the chain
}
```

### Options Description

- `seconds`: The number of seconds to sleep before returning. Accepts an int or
  float. Negative values are clamped to `0` (a warning is logged).

## How It Works

1. Merges the provided options over the defaults.
2. Logs the start of the delay.
3. Sleeps for `seconds`.
4. Logs that processing has resumed.
5. Returns the vCon UUID so the chain continues.

## Usage in a Chain

Insert the link anywhere in a chain to artificially widen its processing window:

```yaml
links:
  delay_10s:
    module: links.delay
    options:
      seconds: 10

chains:
  qa_concurrency_chain:
    links:
      - delay_10s
    ingress_lists:
      - qa_ingress
```

Enqueue several vCons and watch the logs / traces: with concurrency enabled the
delayed links should overlap in time instead of running back-to-back.

## Dependencies

- Custom utilities:
  - logging_utils

## Testing

```bash
pytest conserver/links/delay/test_delay.py
```

The tests mock `time.sleep`, so they run instantly and assert the sleep duration
and pass-through behaviour (including default fallback and negative clamping).
