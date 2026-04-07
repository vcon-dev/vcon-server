# vCon Data Model Reference

## What is vCon?

vCon (Virtual Conversation) is an IETF standard container format for storing and exchanging conversation data. It is defined in [draft-ietf-vcon-vcon-container](https://datatracker.ietf.org/doc/draft-ietf-vcon-vcon-container/) and is designed to capture the full context of a conversation — parties involved, the dialog content (audio, text, or video), attachments, and machine-generated analysis — in a single portable JSON document.

vCon Server uses version `"0.0.1"` of the format. A vCon travels through processing chains as a JSON object stored in Redis (keyed as `vcon:<uuid>`), and is enriched by each link in the chain before being written to one or more storage backends.

---

## Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `vcon` | string | Required | Syntactic version of the vCon JSON format. Always `"0.0.1"` in this implementation. |
| `uuid` | string (UUID) | Required | Globally unique identifier for the vCon. Used to reference the vCon in Redis and storage. Must be globally unique. |
| `created_at` | string (ISO 8601) | Required | Creation timestamp. Set once when the vCon is built and must not change afterwards. Format: `2024-01-15T10:30:00.000+00:00`. |
| `updated_at` | string (ISO 8601) | Optional | Timestamp of the most recent modification to the vCon. |
| `subject` | string | Optional | A short human-readable description of the conversation topic. |
| `redacted` | object | Optional | An object describing any redacted content. Present as an empty object `{}` when no redactions have been applied. |
| `group` | array | Optional | An array of references to other vCons that are part of a group with this one. Present as an empty array `[]` when unused. |
| `parties` | array of Party objects | Required | The participants in the conversation. Must contain at least the parties involved in the dialog. |
| `dialog` | array of Dialog objects | Required | The actual conversation content — recordings, transcripts, or signaling events. |
| `attachments` | array of Attachment objects | Required | Supplementary data attached to the vCon. Includes the special `tags` attachment type. |
| `analysis` | array of Analysis objects | Required | Machine-generated analysis results such as transcriptions, summaries, and sentiment scores. |

---

## Party Object

A party represents one participant in the conversation.

| Field | Type | Required | Description |
|---|---|---|---|
| `tel` | string | Optional | E.164 telephone number, e.g. `"+15551234567"`. |
| `mailto` | string | Optional | Email address, e.g. `"alice@example.com"`. |
| `name` | string | Optional | Human-readable display name. |
| `role` | string | Optional | Role in the conversation, e.g. `"agent"` or `"customer"`. |
| `uuid` | string | Optional | Identifier for the party, useful for linking to external systems. |
| `meta` | object | Optional | Additional metadata as key/value pairs. |

At least one contact field (`tel` or `mailto`) is recommended to make the party identifiable. Parties are referenced by their zero-based index in the `parties` array from within dialog and analysis entries.

### Example Party

```json
{
  "tel": "+15551234567",
  "name": "Alice Example",
  "role": "customer"
}
```

---

## Dialog Object

A dialog entry represents one unit of conversation content. Multiple dialog entries are common — for example, separate entries for each leg of a transferred call or each message in a chat thread.

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Required | The kind of dialog. See dialog types below. |
| `start` | string (ISO 8601) | Required | Start time of this dialog segment. |
| `duration` | number | Optional | Duration in seconds. |
| `parties` | array of integers | Required | Indices into the top-level `parties` array identifying who participated. |
| `originator` | integer | Optional | Index of the party who initiated this dialog segment. |
| `mimetype` | string | Optional | MIME type of the content when `body` or `url` is present, e.g. `"audio/x-wav"` or `"text/plain"`. |
| `filename` | string | Optional | Original filename for the content. |
| `body` | string | Optional | Inline content. For `text` dialogs this is the message text; for encoded content this is the encoded string. |
| `url` | string | Optional | URL pointing to the external content (e.g. an audio file in S3). |
| `encoding` | string | Optional | Encoding applied to `body`. See Encoding Types. |
| `alg` | string | Optional | Hash algorithm used for `signature`, e.g. `"SHA-512"`. |
| `signature` | string | Optional | Cryptographic signature of the content for integrity verification. |
| `disposition` | string | Optional | SIP disposition or call outcome, e.g. `"no-answer"`. |
| `meta` | object | Optional | Additional metadata specific to the dialog type. |

### Dialog Types

| Type | Description |
|---|---|
| `recording` | An audio or video recording of the conversation. `url` or `body` contains the media. |
| `text` | A text message or transcript segment. `body` contains the text content. |
| `transfer` | A call transfer event. Records the signaling of a call being redirected. |
| `incomplete` | A dialog segment that did not complete normally, e.g. a missed call. |

### Example Dialog Entry

```json
{
  "type": "recording",
  "start": "2024-01-15T10:30:00.000+00:00",
  "duration": 182.4,
  "parties": [0, 1],
  "originator": 0,
  "mimetype": "audio/x-wav",
  "url": "https://storage.example.com/recordings/abc123.wav",
  "encoding": "none"
}
```

---

## Attachment Object

Attachments carry supplementary data associated with the vCon as a whole (rather than with a specific dialog segment). Common uses include metadata tags, original source files, and structured documents.

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Required | Identifies what the attachment represents. The special value `"tags"` is used for key/value metadata tags. |
| `body` | string, object, or array | Required | The attachment content. Shape depends on `type` and `encoding`. |
| `encoding` | string | Required | Encoding of `body`. See Encoding Types. |
| `filename` | string | Optional | Original filename if the attachment is a file. |
| `mimetype` | string | Optional | MIME type of the content. |

### The `tags` Attachment Type

The `tags` attachment is a special, well-known attachment type used throughout vCon Server for metadata tagging. When present, it has exactly one entry in the `attachments` array with `"type": "tags"`.

- `body` is an **array of strings**.
- Each string has the format `"name:value"`.
- There is at most one `tags` attachment per vCon; additional tags are appended to its `body` array.

Links add tags using `vcon.add_tag(name, value)`, and read them using `vcon.get_tag(name)`.

#### Example tags attachment

```json
{
  "type": "tags",
  "body": [
    "status:processed",
    "sentiment:positive",
    "language:en"
  ],
  "encoding": "none"
}
```

### Example General Attachment

```json
{
  "type": "transcript_source",
  "body": "{\"provider\": \"deepgram\", \"model\": \"nova-2\"}",
  "encoding": "json",
  "mimetype": "application/json"
}
```

---

## Analysis Object

Analysis entries hold the results of automated processing applied to the conversation — transcripts, summaries, sentiment scores, named entity recognition output, and so on.

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Required | The kind of analysis, e.g. `"transcript"`, `"summary"`, `"sentiment"`. |
| `dialog` | integer or array of integers | Required | Index (or indices) of the dialog entries this analysis applies to. |
| `vendor` | string | Required | Name of the system or service that produced the analysis, e.g. `"deepgram"`, `"openai"`. |
| `body` | string, object, or array | Required | The analysis result. Shape depends on the `type` and `encoding`. |
| `encoding` | string | Required | Encoding of `body`. See Encoding Types. |
| `vendor_schema` | string | Optional | Identifier for the vendor-specific schema version of `body`. |

Extra fields can be added to an analysis entry via the `extra` parameter of `vcon.add_analysis()` and will be merged at the top level of the object.

### Example Analysis Entry

```json
{
  "type": "transcript",
  "dialog": 0,
  "vendor": "deepgram",
  "body": {
    "transcript": "Hello, how can I help you today?",
    "confidence": 0.98,
    "words": []
  },
  "encoding": "json"
}
```

---

## Encoding Types

The `encoding` field appears on both `attachments` and `analysis` entries and controls how `body` should be interpreted.

| Value | Description |
|---|---|
| `none` | `body` is a plain Python/JSON value — a string, object, or array — and requires no decoding. |
| `json` | `body` is a JSON-encoded string. The string must be valid JSON; the consumer should parse it with `json.loads()`. |
| `base64url` | `body` is a Base64url-encoded string (URL-safe alphabet, no padding). Used for binary content such as audio files embedded inline. Decoded with `base64.urlsafe_b64decode()`. |

---

## Complete Annotated Example

The following JSON shows a complete, minimal vCon containing two parties, one audio recording dialog, a `tags` attachment, and a transcript analysis entry.

```json
{
  "vcon": "0.0.1",
  "uuid": "018e1b2c-3d4e-8f56-a789-0b1c2d3e4f50",
  "created_at": "2024-01-15T10:30:00.000+00:00",
  "updated_at": "2024-01-15T10:32:15.000+00:00",
  "subject": "Customer support call — billing inquiry",
  "redacted": {},
  "group": [],

  "parties": [
    {
      "tel": "+15551234567",
      "name": "Alice Example",
      "role": "customer"
    },
    {
      "tel": "+15559876543",
      "name": "Bob Agent",
      "role": "agent"
    }
  ],

  "dialog": [
    {
      "type": "recording",
      "start": "2024-01-15T10:30:00.000+00:00",
      "duration": 182.4,
      "parties": [0, 1],
      "originator": 0,
      "mimetype": "audio/x-wav",
      "url": "https://storage.example.com/recordings/018e1b2c.wav",
      "encoding": "none"
    }
  ],

  "attachments": [
    {
      "type": "tags",
      "body": [
        "status:processed",
        "language:en",
        "topic:billing"
      ],
      "encoding": "none"
    }
  ],

  "analysis": [
    {
      "type": "transcript",
      "dialog": 0,
      "vendor": "deepgram",
      "body": {
        "transcript": "Hello, thank you for calling. How can I help you today?",
        "confidence": 0.97
      },
      "encoding": "json"
    }
  ]
}
```

---

## UUID Generation

vCon Server generates **UUID version 8** identifiers for new vCons. UUID v8 is a custom UUID format defined in [draft-peabody-dispatch-new-uuid-format](https://www.ietf.org/archive/id/draft-peabody-dispatch-new-uuid-format-04.txt) that allows implementors to embed domain-specific bits.

The implementation in `server/vcon.py` (`Vcon.uuid8_domain_name`) works as follows:

1. A SHA-1 hash is computed over the configured DNS domain name string.
2. The upper 62 bits of the hash are used as the `custom_c` portion of the UUID, making the identifier domain-scoped.
3. The `custom_a` and `custom_b` portions are derived from the current Unix timestamp in milliseconds and a sub-millisecond counter, providing monotonic ordering within a process.

The domain name defaults to `"strolid.com"` and can be overridden by setting the `UUID8_DOMAIN_NAME` environment variable:

```bash
UUID8_DOMAIN_NAME=mycompany.com
```

This means UUIDs generated by different deployments that use different domain names will occupy different ranges of the UUID space, reducing collision risk across independently operating systems.
