# sampler

Selectively passes vCons through a processing chain based on a configurable sampling strategy. Returns the vCon UUID when the vCon is selected, or `None` to drop it from the chain.

## Configuration

```yaml
links:
  sampler:
    module: links.sampler
    options:
      method: percentage
      value: 50
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `method` | string | `percentage` | Sampling algorithm to apply. One of `percentage`, `rate`, `modulo`, or `time_based`. |
| `value` | number | `50` | Parameter for the chosen method (see table below). |
| `seed` | int \| null | `null` | Optional random seed for reproducible sampling. If `null`, sampling is non-deterministic. |

### Method reference

| Method | `value` meaning | Notes |
|--------|-----------------|-------|
| `percentage` | Percentage of vCons to keep (0–100) | Uses `random.uniform`; `value: 100` passes all vCons, `value: 0` drops all. |
| `rate` | Average seconds between kept samples | Uses an exponential distribution; lower values keep more vCons. |
| `modulo` | Keep every *n*th vCon | Uses a SHA-256 hash of the UUID modulo `value`; deterministic per UUID. |
| `time_based` | Interval in seconds | Keeps a vCon only when `current_unix_time % value == 0`. |

## Example

```yaml
chains:
  sample_for_review:
    links:
      - sampler:
          method: percentage
          value: 10
      - analyze
    storages:
      - postgres
    ingress_lists:
      - transcribed
    enabled: 1
```

### Modulo example — keep every 5th call

```yaml
chains:
  every_fifth:
    links:
      - sampler:
          method: modulo
          value: 5
      - deepgram_link
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

## Behavior

1. Merges provided options with defaults.
2. Seeds the random number generator if `seed` is set.
3. Applies the configured sampling function to the vCon UUID.
4. Returns the UUID if the vCon passes, or `None` to drop it (halting further processing in the chain).
5. Raises `ValueError` if an unknown `method` is specified.
