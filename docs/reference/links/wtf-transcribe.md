# wtf_transcribe

Sends each recording to a vfun server and stores the World Transcription Format (WTF) result.

Module: `links.wtf_transcribe`

## Set the options

| Option | Type | Default | Description |
|---|---|---|---|
| `vfun-server-url` | string | `None` | URL of the vfun server. Required |
| `language` | string | `None` | Language override, sent to vfun and written to `body.transcript.language`. When unset, vfun detects the language |
| `diarize` | bool | `false` | Asks for speaker diarization. The module marks this as work in progress |
| `vfun-timeout` | number | `300` | Timeout in seconds for the vfun request |
| `url-timeout` | number | `60` | Timeout in seconds for fetching a dialog's `url` |
| `api-key` | string | `None` | Sent as a bearer token when set |

## Follow the processing steps

1. Stop if `vfun-server-url` is empty or the vCon is missing.
2. For each dialog of type `recording` that has no `wtf_transcription` analysis, get the audio. A `url` comes first: `file://` reads a local path, anything else is fetched. Otherwise the link decodes the inline `body`.
3. Post the audio to vfun as the multipart field `file-binary`.
4. Add the analysis, then save the vCon after the last dialog.

There is no minimum duration. A failure on one dialog, including a timeout, is logged and the link moves to the next dialog. There are no retries.

The media type sent to vfun comes from the dialog's `mediatype`, then its filename extension, then defaults to `audio/wav`.

## Read the return value

Returns the uuid, also when some dialogs failed. Returns `None`, which stops the chain, when `vfun-server-url` is missing or the vCon is not found.

## Inspect the vCon changes

One analysis entry per transcribed dialog.

| Field | Value |
|---|---|
| `type` | `wtf_transcription` |
| `dialog` | Dialog index |
| `vendor` | `vfun` |
| `schema` | `wtf-1.0` |
| `mediatype` | `application/json` |
| `body` | The vfun reply as a JSON value |
| `encoding` | `json` |

## Copy a configuration example

```yaml
links:
  wtf:
    module: links.wtf_transcribe
    options:
      vfun-server-url: http://localhost:4380/wtf
      language: en
      vfun-timeout: 300
      url-timeout: 60
      api-key: your-vfun-key
```

## Track the metrics

The link emits no metrics of its own.
