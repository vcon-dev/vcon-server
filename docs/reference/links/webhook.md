# webhook

Posts the vCon as JSON to one or more URLs.

Module: `links.webhook`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `webhook-urls` | list | `[]` | URLs to post to |
| `headers` | dict | `{}` | Request headers |

## Follow the processing steps

1. Load the vCon. A missing vCon raises `AttributeError`.
2. Convert the payload to a legacy format if `EGRESS_FORMAT_VERSION` is set. See [Egress format compatibility](../../configuration/egress-compatibility.md). The stored vCon does not change.
3. If `webhook-urls` is empty, log a warning, count it and pass the vCon on.
4. POST the payload to each URL in order.

The body is the vCon object itself, with no wrapper. The link logs the response but does not check its status, so a 4xx or 5xx counts as delivered. No request timeout is set, and there are no retries.

## Read the return value

Returns the uuid. A connection error raises, the remaining URLs are not tried, and the vCon goes to the dead letter queue. Reprocessing posts again to the URLs that already succeeded.

## Inspect the vCon changes

None.

## Copy a configuration example

```yaml
links:
  notify:
    module: links.webhook
    options:
      webhook-urls:
        - https://api.example.com/vcon-processed
      headers:
        Authorization: Bearer your-token
```

## Track the metrics

`conserver.link.webhook.no_urls_configured` and `conserver.link.webhook.post_failures`. See [Metrics](../metrics.md).
