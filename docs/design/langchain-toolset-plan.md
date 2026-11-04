# Implementation Plan: vCon LangChain Tool Set

Status: **Draft / Proposal**
Target branch: `claude/vcons-lang-chain-plan-8gkkz1`

## 1. Goal

Expose vCons to LangChain-based agents as a first-class **tool set**. A developer
building an agent (LangChain, LangGraph, or anything that consumes
`langchain_core` tools) should be able to write:

```python
from vcon_langchain import VconToolkit

toolkit = VconToolkit(base_url="http://localhost:8000", api_token="...")
tools = toolkit.get_tools()

agent = create_react_agent(llm, tools)
agent.invoke({"messages": [("user", "Summarize the last call from +15551234567")]})
```

…and have the agent discover, read, and manipulate vCons in a running
conserver — searching by party, pulling transcripts and analysis, tagging,
creating vCons, and pushing them into processing chains.

This is a **new integration surface**, distinct from the existing "links"
plugin system:

| Concept | Contract | Who calls it | Direction |
|---------|----------|--------------|-----------|
| **Link** (existing) | `run(vcon_uuid, link_name, opts)` | The conserver worker, per queued vCon | Pipeline pushes work in |
| **LangChain tool** (new) | `BaseTool` / `StructuredTool` with a Pydantic args schema | An LLM agent, on demand | Agent pulls data out / acts |

They are complementary. Links do not change.

## 2. Scope

### In scope
- A small, installable Python package `vcon_langchain` providing:
  - A thin transport client over the conserver REST API.
  - A set of `langchain_core` `StructuredTool`s, each with a typed args schema.
  - A `VconToolkit(BaseToolkit)` that assembles and returns the tools.
  - Sync **and** async execution (`_run` / `_arun`).
- Optional `pyproject.toml` dependency group `langchain`.
- Unit tests (transport mocked — no live conserver required).
- Docs page under `docs/extending/` + mkdocs nav entry, and a runnable example.

### Out of scope (call out as follow-ups)
- Vector / semantic search tools (depends on the Milvus backend; can be a later
  tool once a search endpoint exists).
- Streaming / websocket tools.
- Shipping to PyPI (packaging is structured to allow it later, but publishing is
  a separate decision).
- LangChain **retriever** and **document loader** wrappers (natural follow-ups;
  noted in §9).

## 3. Design decision: what the tools talk to

Two backends are possible:

**A. REST API client (recommended default).** Tools issue HTTP calls to a
conserver's API (`api/api.py`). Pros: fully decoupled, runs anywhere (agent need
not share a process or Redis with the conserver), honors the existing API-key
auth model, no new coupling to Redis internals. Cons: requires a reachable API +
token.

**B. In-process `VconRedis` backend.** Tools call `VconRedis` / `Vcon` directly.
Pros: no HTTP hop, usable inside the conserver process. Cons: requires Redis
config + the `storage`/`conserver` dependency groups, only works co-located, and
couples the tool set to server internals.

**Plan: build A first**, behind a small `VconBackend` protocol so B can be added
later without touching the tool classes. The toolkit takes either a `base_url` +
`api_token` (→ REST backend) or an explicit `backend=` instance. This keeps the
tool layer transport-agnostic and testable.

## 4. Package layout

A self-contained package at the repo root, mirroring how the repo already
isolates optional integrations:

```
vcon_langchain/
  __init__.py            # exports VconToolkit, VconClient, individual tools
  backend.py            # VconBackend protocol + VconApiBackend (REST via requests/httpx)
  client.py             # VconClient: typed wrappers over the API endpoints
  schemas.py            # Pydantic args schemas for each tool
  tools.py              # StructuredTool subclasses (one per operation)
  toolkit.py            # VconToolkit(BaseToolkit)
  extract.py            # pure helpers: transcript/analysis/party extraction from a vCon dict
  tests/
    __init__.py
    conftest.py         # sample vCon fixtures + a fake backend
    test_client.py
    test_tools.py
    test_toolkit.py
    test_extract.py
  README.md
```

Rationale for a top-level package (not `common/lib/…` or a link): the tool set is
a **client SDK** consumed by external agent code. Keeping it standalone lets it
be installed/published independently and avoids dragging server-only deps
(FastAPI, Redis, storage drivers) into an agent's environment.

## 5. The tools

Each tool is a `StructuredTool` with (a) a stable `name`, (b) a one-paragraph
`description` written for an LLM (states what it returns and when to use it), and
(c) a Pydantic `args_schema`. Descriptions matter — they are the agent's only
signal for tool selection — so they get first-class attention and test coverage.

Backing each tool are the API endpoints in `api/api.py`:

| Tool `name` | Args | Backing endpoint | Returns |
|-------------|------|------------------|---------|
| `get_vcon` | `uuid` | `GET /vcon/{uuid}` | Full vCon JSON (spec 0.4.0) |
| `get_vcons` | `uuids: list` | `GET /vcons` | List of vCons |
| `search_vcons` | `tel?`, `mailto?`, `name?` | `GET /vcons/search` | Matching UUIDs |
| `list_recent_vcons` | `since?`, `until?`, `page?`, `size?` | `GET /vcon` | Recent UUIDs |
| `get_vcon_transcript` | `uuid`, `dialog_index?` | `GET /vcon/{uuid}` + `extract.py` | Plain-text transcript |
| `get_vcon_analysis` | `uuid`, `analysis_type?` | `GET /vcon/{uuid}` + `extract.py` | Analysis body (e.g. summary) |
| `get_vcon_parties` | `uuid` | `GET /vcon/{uuid}` + `extract.py` | Compact party roster |
| `get_vcon_tags` | `uuid` | `GET /vcon/{uuid}` | `name: value` tag map |
| `add_vcon_tag` | `uuid`, `name`, `value` | `GET` → mutate → `POST /vcon` | Confirmation |
| `create_vcon` | `parties`, `dialog?`, `ingress_lists?` | `POST /vcon` | New vCon UUID |
| `submit_vcon_to_chain` | `uuids`, `ingress_list` | `POST /vcon/ingress` | Enqueue confirmation |

Design notes:
- The three convenience tools (`get_vcon_transcript`, `get_vcon_analysis`,
  `get_vcon_parties`) exist because handing an LLM a full multi-KB vCon JSON is
  token-expensive and noisy. They fetch the vCon and return only the salient
  slice, reusing the same body-decoding rules the server uses
  (`Vcon.decoded_body` semantics — `encoding: json` bodies are strings that must
  be `json.loads`'d). `extract.py` re-implements this decode as a small pure
  function over the vCon dict so the package has no server dependency.
- Mutating tools (`add_vcon_tag`) do read-modify-write against the API. There is
  no PATCH endpoint, so the tool GETs, applies the change with the same logic as
  `Vcon.add_tag` (append `name:value` to the `tags`-purpose attachment,
  `encoding: json`), and re-POSTs. This is documented as last-write-wins; note
  the race in the tool description and the docs.
- `create_vcon` builds a minimal spec-0.4.0 vCon (uuid, `vcon: "0.4.0"`,
  `created_at`, parties/dialog) — ideally via the canonical `vcon>=0.9.2`
  library that is already a core dependency, so we don't re-implement UUID8
  generation.
- Destructive `delete_vcon` is **intentionally excluded** from the default
  toolkit. It can be opt-in via `VconToolkit(..., include_destructive=True)` so
  an autonomous agent can't delete records unless the developer opts in.

### Tool result shape
Tools return **strings** (JSON-encoded where structured), which is the most
broadly compatible LangChain tool-output form. Errors (404, auth failure,
network) are caught and returned as a short human-readable error string rather
than raising, so the agent can recover rather than crashing the run. HTTP
transport errors that indicate a real outage still surface via logging.

## 6. Client / backend

`VconApiBackend` wraps `httpx` (sync + async clients; `httpx` is already a dev
dep and is a clean choice for both). It:
- Sets the `x-conserver-api-token` header (name comes from
  `CONSERVER_HEADER_NAME`, default `x-conserver-api-token`).
- Centralizes base-url joining, timeouts, and ret/status handling.
- Exposes typed methods: `get_vcon`, `get_vcons`, `search`, `list_uuids`,
  `create_vcon`, `ingress`, (`delete` guarded).

`VconClient` is a thin, ergonomic sync facade over the backend for non-agent
use (tests, scripts, notebooks).

`VconBackend` is a `typing.Protocol` so an in-process Redis backend (option B)
can be dropped in later.

## 7. Dependencies

Add an optional group to `pyproject.toml`:

```toml
[dependency-groups]
langchain = [
    "langchain-core>=0.3.0",
    "httpx>=0.27.0",
]
```

- Depend on **`langchain-core`**, not the full `langchain` meta-package —
  `BaseTool`, `StructuredTool`, and `BaseToolkit` all live in `langchain_core`,
  keeping the install light and version-stable.
- `httpx` is already used in dev; promote it to this group.
- No change to the core/api/conserver runtime deps — agents install
  `uv sync --group langchain`.

## 8. Testing

All tests run without a live conserver by injecting a `FakeBackend` that serves
canned vCon dicts (fixtures modeled on `common/tests/vcon_fixture.py`).

- `test_extract.py` — transcript/analysis/party/tag extraction, including the
  `encoding: json` stringified-body case and legacy `type`/`purpose` attachment
  keys (mirror the compat handling in `common/vcon.py`).
- `test_client.py` — each backend method builds the right URL, query params, and
  auth header; error mapping (404 → "not found" result).
- `test_tools.py` — every tool: args-schema validation, happy path, and the
  error-to-string path; assert each tool has a non-empty LLM-facing description.
- `test_toolkit.py` — `get_tools()` returns the expected set; destructive tools
  absent by default and present when opted in; async `_arun` parity.
- Add a `pytest` marker or keep them under `vcon_langchain/tests/` so they're
  collected by the existing config (`pytest.ini` / `pyproject` coverage source
  would gain `vcon_langchain`).

Guard the LangChain import: if `langchain-core` isn't installed, the package
raises a clear `ImportError` with the `uv sync --group langchain` hint (same
pattern as the Milvus backend's guarded `pymilvus` import).

## 9. Documentation

- New page `docs/extending/langchain-toolset.md`: what it is, install, the
  toolkit/tool table, a full runnable agent example, auth notes, and the
  read-modify-write / last-write-wins caveat.
- Add it to `mkdocs.yml` nav under "Extending".
- `vcon_langchain/README.md`: quick-start mirroring the docs page.
- Cross-link from `docs/extending/index.md`.

Follow-up ideas to mention (not build now): a `VconRetriever` for RAG over a
corpus of vCons, a `VconLoader` (LangChain `Document` loader), and a semantic
`search_vcons_semantic` tool once a vector-search endpoint lands.

## 10. Milestones / PR breakdown

Small, reviewable steps (can be one PR or a short stack):

1. **Skeleton + backend + client** — package layout, `VconApiBackend`,
   `VconClient`, `extract.py`, dependency group, guarded import. Tests for
   client + extract.
2. **Tools + toolkit** — schemas, `StructuredTool`s, `VconToolkit`, sync/async.
   Tool + toolkit tests.
3. **Docs + example** — docs page, mkdocs nav, README, `examples/` agent script.

## 11. Open questions (for reviewer)

1. **Backend default** — confirm REST-first (option A) is right, vs. wanting an
   in-process `VconRedis` tool set for use *inside* the conserver. (Plan keeps
   both possible; builds A.)
2. **Package home** — top-level `vcon_langchain/` (this plan) vs. nesting under
   `common/` vs. a separate repo. Top-level keeps it publishable and dep-light.
3. **Mutation tools** — are agent-driven `add_vcon_tag` / `create_vcon` /
   `submit_vcon_to_chain` desired now, or should v1 be **read-only** with writes
   deferred? (Easy to gate behind a `read_only=True` toolkit flag.)
4. **Destructive `delete_vcon`** — confirm it stays opt-in / excluded.
```
