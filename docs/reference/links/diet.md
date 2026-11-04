# diet

Removes content from a vCon, or moves dialog bodies out to S3 or an HTTP endpoint.

Module: `links.diet`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `remove_dialog_body` | bool | `false` | Empties each dialog's `body`, after moving it if a target is set |
| `post_media_to_url` | string | `""` | URL that receives each body. Used when `s3_bucket` is empty |
| `remove_analysis` | bool | `false` | Deletes the whole `analysis` array |
| `remove_attachment_types` | list | `[]` | Removes attachments whose `mime_type` is in this list |
| `remove_system_prompts` | bool | `false` | Deletes every `system_prompt` key, at any depth |
| `s3_bucket` | string | `""` | Bucket for dialog bodies. Takes priority over `post_media_to_url` |
| `s3_path` | string | `""` | Key prefix |
| `aws_access_key_id` | string | `""` | AWS access key ID |
| `aws_secret_access_key` | string | `""` | AWS secret key |
| `aws_region` | string | `us-east-1` | AWS region |
| `presigned_url_expiration` | number | `None` | Lifetime of the stored URL in seconds. `None` means 3600 |

## Follow the processing steps

1. Load the vCon. If it is missing, log an error and pass the uuid on.
2. If `remove_dialog_body` is true, handle each dialog that has a `body`:
    - With `s3_bucket`, upload the body to `[s3_path/]<vcon_uuid>/[<dialog_id>_]<random>.txt` and store a presigned URL.
    - With `post_media_to_url`, POST JSON with `content`, `vcon_uuid` and `dialog_id`. A 200 reply with a `url` key sets that URL.
    - With neither, set `body` to `""`.
3. Delete `analysis` if `remove_analysis` is true.
4. Filter attachments if `remove_attachment_types` is set.
5. Delete `system_prompt` keys if `remove_system_prompts` is true.
6. Save the vCon.

## Check the limits

- A failed upload or POST sets `body` to `""`. The content is gone from the vCon and the link continues. Only the POST path counts `conserver.link.diet.media_post_failures`.
- A presigned URL stops working when it expires, and the link keeps no other reference to the object.
- `remove_analysis` deletes the key itself. A later link that adds analysis then raises `KeyError`, so place `diet` after them.
- `remove_attachment_types` compares the literal field `mime_type`. Attachments that use `mediatype`, as spec-current vCons do, never match.
- The attachment filter has no exception for `lawful_basis`. An attachment with a listed `mime_type` is removed whatever its purpose.
- The link does not read `only_if` or `sampling_rate`.

## Read the return value

Returns the uuid, also when the vCon is missing.

## Inspect the vCon changes

The link only removes or replaces content. A moved dialog has its `body` set to the URL and gains `body_type: "url"`, and its `encoding` stays as it was.

## Copy a configuration example

```yaml
links:
  slim_down:
    module: links.diet
    options:
      remove_dialog_body: true
      s3_bucket: vcon-media
      s3_path: dialogs
      aws_access_key_id: your-access-key-id
      aws_secret_access_key: your-secret-key
      aws_region: us-east-1
      presigned_url_expiration: 86400
      remove_system_prompts: true
```

## Track the metrics

`conserver.link.diet.media_post_failures`. See [Metrics](../metrics.md).
