# Utopia Storage Module for vCon Server

Sends each vCon to a [Utopia](https://github.com/deeplethe/utopia) knowledge base. Utopia is a self-hosted bitemporal knowledge graph: it extracts facts from documents, dates each one on both a world clock and a record clock, and keeps the quoted evidence for every fact. Point it at your conversations and you can ask what was said about a customer, product or issue as of any date, with the source vCon behind every answer.

## How a vCon becomes a Utopia document

Utopia reads prose, not JSON, and it dates a document only from a leading `YYYY-MM-DD` line in a Markdown file. So `save` renders the vCon as dated sentences and uploads it as `<uuid>.md`:

```
2026-09-18

# Conversation 8f752fc9-d6d8-4d2c-a9d0-d859f61d7c51

+15085550100 took part.
On 2026-09-18 at 14:02, +15085550100 and Support had a recorded call lasting 240 seconds.

On 2026-09-18, the conversation was summarised: ...

Transcript of the conversation on 2026-09-18 at 14:02:

On 2026-09-18, Speaker 0: ...

Lawful basis: consent, granted for recording, analysis, expires 2027-01-01.
Source: vCon 8f752fc9-d6d8-4d2c-a9d0-d859f61d7c51, created 2026-09-18T14:02:00Z.
```

Sentences rather than key-value pairs, because `On 2026-09-18, X called Y` extracts as a fact with a start date, and `created_at: 2026-09-18` leaves the model guessing. Utopia extracts chunk by chunk, so every summary and transcript paragraph repeats the date rather than relying on a heading in another chunk.

The renderer reads `wtf_transcription`, OpenAI, Deepgram and legacy `transcript` bodies, `summary` analysis, the `tags` attachment and the `lawful_basis` attachment. It accepts legacy records (`vcon: "0.0.1"`, attachment `type` instead of `purpose`, dict bodies).

## Behaviour

- **save** uploads the rendering. Utopia skips content it already holds (same sha256 in the KB), so an unchanged vCon is a no-op. When the rendering changed, for example after a new analysis or an amendment, the new document is uploaded first and the older `<uuid>.md` is then deleted, so a failed upload loses nothing.
- **delete** deletes every live `<uuid>.md`. A Utopia delete is a tombstone: it invalidates facts that no other document supports and can be undone from the Utopia console.
- **get** is not implemented. Utopia holds the rendering, not the vCon.

Failures raise, so the conserver's storage retry and dead-letter handling apply.

## Configuration

| Option | Description | Default |
| --- | --- | --- |
| base_url | Utopia REST API root | `http://127.0.0.1:1516/api/v1` |
| kb_id | Knowledge base UUID. Required | `""` |
| email | Utopia service account. Required | `""` |
| password | Service account password. Required | `""` |
| timeout | Request timeout in seconds | `30` |
| transient_retries | Retries for connection errors and 429/502/503/504 | `3` |
| transient_backoff_base_s | Exponential backoff factor in seconds | `0.5` |
| require_analysis_grant | Skip vCons whose lawful basis does not grant `analysis` | `false` |

```yaml
storages:
  utopia:
    module: storage.utopia
    options:
      base_url: http://utopia:1516/api/v1
      kb_id: 00000000-0000-0000-0000-000000000000
      email: conserver@example.com
      password: <service-account-password>
      require_analysis_grant: false
```

Add `utopia` to a chain's `storages` list.

The service account needs the Editor role on the knowledge base. Utopia's REST API accepts session tokens only, not the personal access tokens it issues for MCP, so the module logs in with the account and logs in again when its token expires (Utopia tokens last 7 days).

## Lawful basis

Every rendering ends with one lawful basis sentence, either the basis and its grants or `Lawful basis: none recorded.` A missing basis is never filled in. With `require_analysis_grant: true`, a vCon whose basis does not grant `analysis`, or has expired, is not sent and a warning names its uuid. The default is off because most existing corpora predate the lawful basis extension; turn it on for regulated data.

## Before you send real conversations

- Utopia sends document chunks to a language model to extract facts. Point Utopia at a local model endpoint (Ollama, vLLM) if transcripts may not leave your environment, and run a redaction link earlier in the chain.
- Utopia is pre-1.0. Pin its image version, and do not expose it to the public internet.

## Not yet handled

- A `redacted` vCon should purge the original's document permanently rather than tombstone it. That needs the Admin role and Utopia's purge endpoint.
- Party phone numbers and emails are rendered in text but not yet seeded as Utopia entity aliases.
