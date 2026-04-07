# post_analysis_to_slack

Posts vCon analysis results to Slack channels. Sends a formatted message with an inline summary and a details button when a matching analysis entry is found on the vCon. Supports routing to team-specific channels as well as a default fallback channel.

## Prerequisites

- A [Slack Bot Token](https://api.slack.com/authentication/token-types#bot) with `chat:write` scope.
- The bot must be invited to the target Slack channel(s).

## Configuration

```yaml
links:
  post_analysis_to_slack:
    module: links.post_analysis_to_slack
    options:
      token: "${SLACK_BOT_TOKEN}"
      channel_name: vcon-alerts
      default_channel_name: vcon-errors
      url: https://app.example.com/conversations
      analysis_to_post: summary
      only_if:
        analysis_type: customer_frustration
        includes: "NEEDS REVIEW"
```

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `token` | string | `null` | Slack Bot OAuth token. |
| `channel_name` | string | `null` | Default Slack channel to post notifications to. |
| `default_channel_name` | string | — | Fallback channel used when the team-specific channel does not exist. |
| `url` | string | `"Url to hex sheet"` | Base URL used to build the "Details" button link. The vCon UUID is appended as a query parameter. |
| `analysis_to_post` | string | `summary` | Type of analysis whose `body` is used as the Slack message text. |
| `only_if.analysis_type` | string | `customer_frustration` | Only post when an analysis of this type is found on the vCon. |
| `only_if.includes` | string | `NEEDS REVIEW` | Only post when the matching analysis body contains this substring. |

## Example

```yaml
chains:
  slack_alerts:
    links:
      - analyze
      - post_analysis_to_slack:
          token: "${SLACK_BOT_TOKEN}"
          channel_name: call-center-alerts
          default_channel_name: call-center-errors
          url: https://dashboard.example.com/calls
          analysis_to_post: summary
          only_if:
            analysis_type: customer_frustration
            includes: "NEEDS REVIEW"
    storages:
      - postgres
    ingress_lists:
      - analyzed
    enabled: 1
```

## Slack Message Format

Each notification includes three Slack blocks:

1. A header section with a neutral-face emoji.
2. The summary text from the `analysis_to_post` analysis body.
3. A "Details" button linking to `url?_vcon_id="<uuid>"`.

If the vCon has a `strolid_dealer` attachment with a `team` field, the message is also posted to a channel named `team-<teamname>-alerts` with the dealer name appended to the summary text.

## Behavior

1. Retrieves the vCon from Redis.
2. Iterates over analysis entries looking for ones matching `only_if.analysis_type` and containing `only_if.includes` in the body.
3. Skips entries already marked `was_posted_to_slack: true`.
4. Finds the corresponding `summary` analysis entry for the same dialog.
5. Posts the formatted message to the team-specific channel (if applicable) and to `channel_name`.
6. Marks the analysis entry `was_posted_to_slack: true` and saves the vCon.
7. If posting to a team channel fails (channel does not exist), an error is sent to `default_channel_name`.
