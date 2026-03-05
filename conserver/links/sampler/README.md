# Sampler Link

The Sampler link is a specialized plugin that selectively processes vCons based on various sampling methods. It provides a way to reduce the volume of vCons being processed in a chain, enabling efficient resource utilization and focused analysis.

## Features

- Multiple sampling methods for flexible vCon selection
- Percentage-based sampling for proportional reduction
- Rate-based sampling for time-controlled processing
- Modulo-based sampling for consistent selection patterns
- Time-based sampling for periodic processing
- Configurable random seed for reproducible sampling
- Efficient implementation with minimal dependencies

## Configuration Options

```python
default_options = {
    "method": "percentage",  # Sampling method to use
    "value": 50,  # Value specific to the chosen method
    "seed": None,  # Random seed for reproducible sampling
}
```

### Options Description

- `method`: The sampling method to use:
  - `percentage`: Keep a percentage of vCons (0-100)
  - `rate`: Keep vCons at a specific rate (seconds between samples)
  - `modulo`: Keep every nth vCon
  - `time_based`: Keep vCons at specific time intervals
- `value`: The value specific to the chosen method
- `seed`: Optional random seed for reproducible sampling

## Usage

The link processes vCons by:
1. Determining the sampling method and parameters
2. Applying the appropriate sampling function to the vCon UUID
3. Returning the vCon UUID if it passes the sampling criteria
4. Returning None to filter out the vCon if it doesn't pass

## Sampling Methods

### Percentage Sampling

Keeps a specified percentage of vCons:
```python
# Keep 30% of vCons
opts = {"method": "percentage", "value": 30}
```

### Rate Sampling

Keeps vCons at a specific rate:
```python
# Keep one vCon every 5 seconds on average
opts = {"method": "rate", "value": 5}
```

### Modulo Sampling

Keeps every nth vCon based on a hash of the UUID:
```python
# Keep every 10th vCon
opts = {"method": "modulo", "value": 10}
```

### Time-based Sampling

Keeps vCons at specific time intervals:
```python
# Keep vCons every 60 seconds
opts = {"method": "time_based", "value": 60}
```

## Error Handling

- Validates sampling method before processing
- Raises ValueError for unknown sampling methods
- Graceful handling of invalid parameter values
- Consistent behavior with reproducible results when seed is provided

## Dependencies

- Python standard library (random, time, hashlib)
- Custom utilities:
  - logging_utils

## Requirements

- No external dependencies required
- Appropriate permissions for vCon access
- Understanding of sampling methods for effective configuration 