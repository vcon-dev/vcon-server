# Post Analysis to Slack Link

The Post Analysis to Slack link is a specialized plugin that posts vCon analysis results to Slack channels. It provides a way to notify teams about important analysis findings, with support for team-specific channels and customizable posting conditions.

## Features

- Post vCon analysis results to Slack channels
- Support for team-specific notification channels
- Conditional posting based on analysis type and content
- Rich message formatting with buttons and links
- Fallback to default channel for error handling
- Tracking of posted analyses to prevent duplicates
- Integration with dealer and team information

## Configuration Options

```python
default_options = {
    "token": None,  # Slack API token
    "channel_name": None,  # Default Slack channel name
    "url": "Url to hex sheet",  # URL for the details button
    "analysis_to_post": "summary",  # Type of analysis to post
    "only_if": {
        "analysis_type": "customer_frustration",  # Analysis type to match
        "includes": "NEEDS REVIEW"  # Text that must be included in the analysis
    },
}
```

### Options Description

- `token`: Your Slack API token
- `channel_name`: Default Slack channel for notifications
- `url`: URL for the details button in the Slack message
- `analysis_to_post`: Type of analysis to post (e.g., "summary")
- `only_if`: Conditions that must be met for posting:
  - `analysis_type`: Type of analysis to match
  - `includes`: Text that must be included in the analysis body

## Usage

The link processes vCons by:
1. Retrieving the vCon from Redis
2. For each analysis in the vCon:
   - Checking if it matches the posting conditions
   - Verifying if it's already been posted to Slack
   - Extracting team and dealer information
   - Finding the corresponding summary analysis
   - Posting to team-specific channel if applicable
   - Posting to the default channel
   - Marking the analysis as posted
3. Storing the updated vCon back in Redis

## Slack Message Format

The link posts formatted messages to Slack with:
- A section with a neutral face emoji
- The analysis summary text
- A button linking to the details URL
- Team and dealer information when available

## Error Handling

- Posts to default channel if team channel doesn't exist
- Logs errors when posting to Slack
- Tracks posted analyses to prevent duplicates
- Graceful handling of missing team or dealer information

## Dependencies

- Slack SDK for Python
- Redis for vCon storage
- Custom utilities:
  - vcon_redis
  - logging_utils

## Requirements

- Slack API token must be provided
- Redis connection must be configured
- Appropriate permissions for vCon access and storage
- Slack workspace with configured channels 