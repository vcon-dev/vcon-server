# post_analysis_to_slack

Posts a summary to Slack when a chosen analysis entry contains a given string.

Module: `links.post_analysis_to_slack`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `token` | string | `None` | Slack bot token. Required |
| `default_channel_name` | string | none | Channel for every post. Required, and absent from `default_options`, so leaving it out raises `KeyError` at the first post |
| `url` | string | `Url to link to the details page` | Target of the Details button. Replaces `{vcon_id}` with the uuid, or adds `?_vcon_id="<uuid>"` when there is no placeholder |
| `only_if.analysis_type` | string | `customer_frustration` | Analysis `type` to check |
| `only_if.includes` | string | `NEEDS REVIEW` | Substring to look for in that entry's body |
| `channel_name` | string | `None` | In `default_options`, but no code reads it |
| `analysis_to_post` | string | `summary` | In `default_options`, but no code reads it. The posted text always comes from the `summary` entry |

This `only_if` differs from the [shared filter](index.md#set-the-shared-filter-options): it has no `section` and works per analysis entry.

## Follow the processing steps

For each analysis entry:

1. Skip it unless its `type` is `only_if.analysis_type`, its body contains `only_if.includes`, and it has no `was_posted_to_slack` flag.
2. Find the `summary` entry for the same dialog. If there is none the link raises `TypeError`.
3. If a deployment-specific team attachment names a team, also post to `team-<name>-alerts`, with the first word of the team name in lowercase. See `get_team` and `get_dealer` in the source. The attachment purpose and an excluded team name are hard-coded there, so this step does not apply to other deployments.
4. Post to `default_channel_name`.
5. Set `was_posted_to_slack` on the entry.

The vCon is saved after the loop. If a post fails, the link sends a short notice to `default_channel_name`, then raises.

## Read the return value

Returns the uuid. A failed post raises, and the vCon goes to the dead letter queue. A missing vCon raises `AttributeError`.

## Inspect the vCon changes

Sets `was_posted_to_slack: true` on each posted analysis entry. This flag stops a second post when the vCon runs again.

## Copy a configuration example

```yaml
links:
  slack_alerts:
    module: links.post_analysis_to_slack
    options:
      token: your-slack-bot-token
      default_channel_name: call-alerts
      url: https://portal.example.com/vcons/{vcon_id}
      only_if:
        analysis_type: customer_frustration
        includes: NEEDS REVIEW
```

## Track the metrics

`conserver.link.slack.post_failures` and `conserver.link.slack.fallback_channel_used`. See [Metrics](../metrics.md).
