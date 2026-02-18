# Post Analysis to Slack Link

The Post Analysis to Slack link posts vCon analysis results to Slack channels. It supports two modes: an **analysis-based mode** that conditionally posts analysis findings (with team-specific routing), and a **simple notification mode** that posts a single configurable message using a URL template.

## Features

- Post vCon analysis results to Slack channels
- Support for team-specific notification channels
- Conditional posting based on analysis type and content
- Simple notification mode: post one message per vCon with a custom URL (skips analysis checks)
- Rich message formatting with buttons and links
- Fallback to default channel for error handling
- Tracking of posted analyses to prevent duplicates
- Integration with dealer and team information

## Configuration Options

```python
default_options = {
    "token": None,                  # Slack API token
    "default_channel_name": None,   # Default Slack channel name
    "url": "Url to hex sheet",      # URL for the details button (analysis mode)
    "analysis_to_post": "summary",  # Type of analysis to post (analysis mode)
    "only_if": {
        "analysis_type": "customer_frustration",  # Analysis type to match
        "includes": "NEEDS REVIEW"                # Text that must be in the analysis body
    },
    # Simple notification mode (optional): when url_template is set, posts one message
    # to default_channel_name and skips all analysis-based posting.
    "url_template": None,           # URL template; use {vcon_uuid} as a placeholder
    "message_text": "Callback request",  # Message text for simple notifications
}
```

### Options Description

- `token`: Your Slack API token.
- `default_channel_name`: Default Slack channel for notifications.
- `url`: URL used for the details button in analysis-mode messages.
- `analysis_to_post`: Type of analysis to post (e.g., `"summary"`). Analysis mode only.
- `only_if`: Conditions that must be met before posting in analysis mode:
  - `analysis_type`: Type of analysis to match.
  - `includes`: Text that must be present in the analysis body.
- `url_template`: *(Optional)* When set, activates **simple notification mode**. The template may include `{vcon_uuid}` which is replaced with the vCon's UUID. Example: `"https://app.example.com/calls/{vcon_uuid}"`.
- `message_text`: *(Optional)* Message body for simple notifications. Defaults to `"Callback request"`.

## Modes

### Analysis Mode (default)

When `url_template` is **not** set, the link:
1. Retrieves the vCon from Redis.
2. For each analysis entry:
   - Checks if it matches `only_if` conditions.
   - Skips if already posted to Slack.
   - Extracts team and dealer information.
   - Posts to the team-specific channel if applicable.
   - Posts to `default_channel_name`.
   - Marks the analysis as posted.
3. Stores the updated vCon back in Redis.

Messages include a header emoji, the analysis summary text, and a button linking to `url`.

### Simple Notification Mode

When `url_template` **is** set, the link:
1. Formats the URL by substituting `{vcon_uuid}` with the vCon's UUID.
2. Posts a single message to `default_channel_name` containing `message_text` and a button linking to the formatted URL.
3. Returns immediately — no analysis checks, no vCon stored.

Messages do **not** include the header emoji (header is suppressed).

## Error Handling

- Posts to `default_channel_name` if a team-specific channel doesn't exist.
- Logs errors when posting to Slack.
- Tracks posted analyses to prevent duplicates (analysis mode only).
- Graceful handling of missing team or dealer information.

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