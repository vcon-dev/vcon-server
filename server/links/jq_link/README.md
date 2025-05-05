# JQ Filter Link

The JQ Filter link allows flexible filtering of vCons in a chain using jq expressions. It can be used to either forward or filter out vCons based on their content, enabling complex filtering logic within your vCon processing pipelines.

## Overview

This link uses jq expressions to evaluate conditions against vCons. Based on whether the conditions match and the configuration, it will either forward the vCon down the chain or filter it out.

### Key Features

- Uses jq expressions for flexible filtering
- Can forward either matching or non-matching vCons
- Configurable through standard link options
- Detailed logging of filter decisions

## Installation

### Prerequisites

- jq.py library: `pip install jq`
  - Works with Python 3.7+ through Python 3.12
  - Pure Python implementation, no system dependencies required
  - Source: [jq.py on GitHub](https://github.com/mwilliamson/jq.py)

### Link Installation

1. Copy the link file to your links directory:
```bash
cp jq_filter.py /path/to/links/directory/
```

2. Ensure the link directory is in your Python path.

## Configuration

The link accepts two configuration options:

- `filter` (string): A jq expression that evaluates to a boolean
- `forward_matches` (boolean): If true, forwards vCons that match the filter. If false, forwards vCons that don't match.

### Example Chain Configuration

```yaml
links:
  filter_cats:
    module: "links.jq_filter"
    options:
      filter: '.attributes.arc_display_type == "Cat"'
      forward_matches: true

  filter_no_analysis:
    module: "links.jq_filter"
    options:
      filter: '.analysis | length == 0'
      forward_matches: false
```

## Common Filter Examples

### Filter by Meta Information

```yaml
# Match specific display type
filter: '.meta.arc_display_type == "Cat"'

# Match meta field presence
filter: '.meta.weight != null'

# Match numeric meta value
filter: '.meta.weight > 5'
```

### Filter by Parties

```yaml
# Match vCons with specific number of parties
filter: '.parties | length >= 2'

# Match vCons with specific party role
filter: '.parties[] | select(.role == "agent") | any'
```

### Filter by Analysis

```yaml
# Match vCons with analysis
filter: '.analysis | length > 0'

# Match vCons with specific analysis type
filter: '.analysis[] | select(.type == "transcript") | any'
```

### Filter by Attachments

```yaml
# Match vCons with attachments
filter: '.attachments | length > 0'

# Match vCons with specific attachment type
filter: '.attachments[] | select(.type == "report") | any'
```

### Complex Filters

```yaml
# Match vCons with either analysis or attachments
filter: '(.analysis | length > 0) or (.attachments | length > 0)'

# Match vCons with specific attribute and analysis
filter: '(.meta.arc_display_type == "Cat") and (.analysis | length > 0)'
```

## Link Behavior

1. The link retrieves the vCon from Redis using the provided UUID
2. Converts the vCon to a dictionary
3. Applies the configured jq filter
4. Based on the filter result and forward_matches setting:
   - Returns the vCon UUID to forward it
   - Returns None to filter it out

### Error Handling

- If the vCon cannot be found in Redis, returns None
- If the jq filter expression is invalid, logs an error and returns None
- If the jq filter execution fails, logs an error and returns None

## Logging

The link uses the standard logging configuration and logs at these levels:

- DEBUG: Link start
- INFO: Filter results and forwarding decisions
- ERROR: vCon retrieval or filter execution errors

## Best Practices

1. Test jq expressions separately before using them in production
2. Start with simple filters and build up to more complex ones
3. Use appropriate logging levels during development
4. Consider performance implications of complex filters
5. Validate filter expressions against sample vCons

## Debugging

To debug filter behavior:

1. Enable DEBUG level logging
2. Test the jq expression directly using the jq command line tool
3. Check the logs for filter evaluation results
4. Verify the vCon structure matches your expectations

## Examples

### Forward Only Unredacted vCons

```yaml
links:
  filter_unredacted:
    module: "links.jq_filter"
    options:
      filter: ".redacted == {}"
      forward_matches: true
```

### Filter Out Empty Analysis

```yaml
links:
  filter_with_analysis:
    module: "links.jq_filter"
    options:
      filter: ".analysis | length == 0"
      forward_matches: false
```

### Forward vCons with Specific Attribute Pattern

```yaml
links:
  filter_pattern:
    module: "links.jq_filter"
    options:
      filter: '.meta.serial_number | test("^ABC\\d{5}$")'
      forward_matches: true
```

## Development

### Running Tests

```bash
python -m pytest tests/links/test_jq_filter.py -v
```

### Contributing

1. Follow the existing code style
2. Add tests for new functionality
3. Update documentation
4. Test thoroughly before submitting changes

## Troubleshooting

Common issues and solutions:

1. **Filter Not Matching**: 
   - Verify vCon structure
   - Test filter with jq command line
   - Enable DEBUG logging

2. **jq Import Error**:
   - Check jq.py installation using `pip install jq`
   - Verify Python version compatibility (3.7+)
   - Check pip installation status with `pip show jq`

3. **Performance Issues**:
   - Simplify complex filters
   - Optimize jq expressions
   - Consider chain order