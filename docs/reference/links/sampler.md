# sampler

Keeps a share of vCons and stops the chain for the rest.

Module: `links.sampler`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `method` | string | `percentage` | `percentage`, `rate`, `modulo` or `time_based` |
| `value` | number | `50` | Meaning depends on `method` |
| `seed` | any | `None` | Reseeds Python's `random` on every run when set |

| `method` | `value` | Keeps a vCon when |
|---|---|---|
| `percentage` | Percent, 0 to 100 | A random number from 0 to 100 is at or below `value` |
| `rate` | Positive number | An exponential draw with mean `value` is at most 1. Each vCon is an independent draw, with chance 1 - e^(-1/`value`). No timing state is kept |
| `modulo` | Positive integer | The first 8 hex digits of the uuid's SHA-256, as an integer, divide evenly by `value`. The result is stable for a given uuid and keeps about one in `value` |
| `time_based` | Positive integer, seconds | The current Unix time in whole seconds divides evenly by `value` |

Avoid `seed` with `percentage` or `rate`. The link reseeds on every run, so every vCon gets the same draw and they are all kept or all dropped. The call also reseeds the shared generator for the worker process, which affects `sampling_rate` in other links. `modulo` and `time_based` do not use the generator.

## Follow the processing steps

1. Merge the options and reseed if `seed` is set.
2. Run the method. An unknown `method` raises `ValueError`.
3. Count the outcome.

The link does not load the vCon.

## Read the return value

Returns the uuid to keep the vCon, or `None` to stop the chain. A dropped vCon skips this chain's storages and egress lists.

## Inspect the vCon changes

None.

## Copy a configuration example

```yaml
links:
  sample_ten_percent:
    module: links.sampler
    options:
      method: percentage
      value: 10
```

## Track the metrics

`conserver.link.sampler.sampled_in` and `conserver.link.sampler.sampled_out`. See [Metrics](../metrics.md).
