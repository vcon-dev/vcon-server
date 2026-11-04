# Utopia storage adapter

Sends each vCon to a [Utopia](https://github.com/deeplethe/utopia) knowledge base. Utopia reads dated prose, so the adapter renders the vCon as Markdown sentences and uploads `<uuid>.md`. Utopia holds that rendering and not the vCon, so the adapter offers no `get`.

Module: `storage.utopia`. Needs no extra packages.

## Configure the adapter

```yaml
storages:
  utopia:
    module: storage.utopia
    options:
      base_url: http://utopia:1516/api/v1
      kb_id: 00000000-0000-0000-0000-000000000000
      email: conserver@example.com
      password: example-password
```

## Set the options

The adapter merges your options over the defaults. A missing `kb_id`, `email` or `password` raises `ValueError` on every `save` and `delete`.

| Option | Type | Default | Description |
|---|---|---|---|
| `base_url` | string | `http://127.0.0.1:1516/api/v1` | Utopia REST API root |
| `kb_id` | string | `""` | Knowledge base UUID. Required |
| `email` | string | `""` | Service account with the Editor role on the knowledge base. Required |
| `password` | string | `""` | Service account password. Required |
| `timeout` | integer | `30` | Request timeout in seconds |
| `transient_retries` | integer | `3` | Retries for transient failures |
| `transient_backoff_base_s` | number | `0.5` | Backoff factor in seconds |
| `require_analysis_grant` | boolean | `false` | Skip a vCon when no lawful basis grants `analysis`. See [Require an analysis grant](#require-an-analysis-grant) |

## Check the rendering

The first line is a `YYYY-MM-DD` date, because Utopia dates a document from that line. The date comes from `created_at`, or else the first dialog `start`.

```text
2026-09-18

# Conversation 018f4a2e-7b1c-8000-9000-000000000001

+15555550100 took part.
On 2026-09-18 at 14:02, +15555550100 and Support had a recorded call lasting 240 seconds.

On 2026-09-18, the conversation was summarised: ...

Transcript of the conversation on 2026-09-18 at 14:02:

On 2026-09-18, Speaker 0: ...

Lawful basis: none recorded.
Source: vCon 018f4a2e-7b1c-8000-9000-000000000001, created 2026-09-18T14:02:00Z.
```

The rendering includes:

- Party names, phone numbers, email addresses and roles.
- One sentence per dialog.
- `summary` analysis.
- `transcript` and `wtf_transcription` analysis.
- `tags` attachments.
- One lawful basis sentence.
- A source line with `amended` or `redacted` references.

This content leaves the server, so treat the knowledge base as a store of conversation data.

The lawful basis sentence reports what the vCon carries. It reads `Lawful basis: none recorded.` when no usable attachment exists. When one exists it gives the `lawful_basis` value, the purposes granted, and any expiry, for example `Lawful basis: consent, granted for recording, analysis, expires 2027-01-01.` The adapter fills no gaps and adds no basis to the vCon.

## Require an analysis grant

`require_analysis_grant` is an adapter option. It reads a `lawful_basis` attachment that is already on the vCon and decides whether this one adapter uploads. It manages nothing.

With the option at its default of `false`, a vCon with no grant still uploads, and the adapter logs that at INFO. With `true`, that vCon is skipped.

The adapter treats `analysis` as granted only when all of these hold:

1. An attachment has `purpose` `lawful_basis`, or the legacy `type` with that value, and its decoded body is an object. The first such attachment is used and later ones are ignored.
2. `purpose_grants` in that body has an entry with `purpose` `analysis` and `granted` exactly `true`.
3. `expiration` is absent or in the future. An expiry that will not parse counts as expired. An expiry with no timezone is read as UTC.

The attachment shape it reads looks like this. The values are illustrative:

```json
{
  "purpose": "lawful_basis",
  "start": "2026-09-18T14:02:00Z",
  "party": 0,
  "dialog": 0,
  "mediatype": "application/json",
  "encoding": "json",
  "body": {
    "lawful_basis": "consent",
    "expiration": "2027-01-01T00:00:00Z",
    "purpose_grants": [
      {"purpose": "analysis", "granted": true, "granted_at": "2026-09-18T14:02:00Z"}
    ]
  }
}
```

A skip works like this:

- The adapter logs a warning and returns before it contacts Utopia.
- The write counts as a success and nothing reaches the DLQ.
- A rendering uploaded earlier stays in Utopia.

The limits of the option:

- It checks the fields above and nothing else. It does not examine `proof_mechanisms`, the `lawful_basis` value or `granted_at`, and it consults no outside source.
- It applies to `utopia` only. Other backends and links in the same chain do not read it.
- It creates, changes and removes no lawful basis attachment.
- It does not make a deployment compliant.

## Save a vCon

1. Read the vCon through `VconRedis`. A missing vCon raises `ValueError`.
2. Render it and apply `require_analysis_grant`.
3. Log in with `POST auth/login` if this process has no token for this `base_url` and `email`. Tokens are cached per process. A `401` clears the token and logs in once more.
4. List documents with `GET kbs/{kb_id}/documents`, querying by UUID with a limit of 200, and keep those named `<uuid>.md`.
5. Upload with `POST kbs/{kb_id}/documents`.
6. If Utopia reports nothing created, the content is unchanged and `save` returns.
7. Otherwise delete the older documents with `DELETE documents/{id}`.

The upload comes first, so a failed upload loses nothing. The adapter does not apply `EGRESS_FORMAT_VERSION`.

## Read a vCon

The adapter has no `get`.

## Delete a vCon

`delete` finds every live `<uuid>.md` and deletes it, then returns `True` if there was at least one. A Utopia delete is a tombstone and can be reversed. Purging for redaction needs the KB Admin role, and the adapter does not do it.

## Handle a failed write

HTTP errors and missing options raise, so the server moves the vCon to the [storage DLQ](index.md#handle-a-failed-write).

Before that, the session retries transient failures with exponential backoff. It shares its retry policy with [`vcon_mcp`](vcon_mcp.md#handle-a-failed-write): connection errors, read timeouts, and `429`, `502`, `503` and `504` responses, for `GET`, `POST` and `DELETE`.

A repeated `save` is safe. Utopia skips an upload whose sha256 is already in the knowledge base.
