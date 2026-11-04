# Write the YAML configuration

One YAML file defines what the server does to each vCon: which links run, where results go, and who may submit. `CONSERVER_CONFIG_FILE` names the file. Server-level settings live in [environment variables](environment-variables.md).

Start from the small file in [the Docker guide](../installation/docker.md#write-the-chain-configuration).

`example_config.yml` is a syntax catalogue to read, not to run. It names modules that are not in this repo, and its empty `tracers` key sends every vCon to the dead letter queue.

## Learn the file rules

The server loads the file with `yaml.safe_load`, with no further processing:

- `${VAR}` is not expanded. A value such as `${OPENAI_API_KEY}` reaches the link as that literal text. Write the real value, and render the file in your deployment tooling if you keep secrets elsewhere.
- Nothing validates the file on load. An unknown key is ignored and a wrong one fails when the code reaches it.
- `GET /config` returns the parsed file, secrets included, to any caller with an API key. `POST /config` replaces the whole file, and comments are lost.

## Know the top-level keys

| Key | Read by | Holds |
|---|---|---|
| `ingress_auth` | API | API keys per ingress list |
| `imports` | Conserver | Modules to load when a worker starts |
| `links` | Conserver | Named processing links |
| `storages` | Conserver and API | Named storage backends |
| `tracers` | Conserver | Named tracers |
| `chains` | Conserver and queue metrics | Pipelines that join the above |
| `followers` | Conserver | Remote servers to pull from |

Every key is optional. With no `chains`, the workers log a warning and retry every 15 seconds.

## Plan for reloads

The server reads the file again at these points, so most edits need no restart:

| Section | Takes effect |
|---|---|
| `chains`, `links`, `tracers` | On each worker loop, after a vCon is popped or the 15 second wait ends |
| `storages` | On the next write or read |
| `ingress_auth` | On the next request |
| `imports` | When a worker starts |
| `followers` | When the conserver process starts |

A YAML syntax error stops a worker at its next reload, so check a change before you save it over the live file.

## Authorize external ingress

`ingress_auth` maps an ingress list to one key or a list of keys:

```yaml
ingress_auth:
  customer_data: "replace-with-a-key"
  support_calls:
    - "replace-with-a-key-for-client-1"
    - "replace-with-a-key-for-client-2"
```

A caller sends the key to `POST /vcon/external-ingress`:

```bash
curl -X POST "http://localhost:8000/vcon/external-ingress?ingress_list=customer_data" \
  -H "x-conserver-api-token: replace-with-a-key" \
  -H "Content-Type: application/json" \
  -d @vcon.json
```

A key works only for its own list. With `ingress_auth` empty, or the list missing from it, the API returns 403. See [authentication](authentication.md).

## Import extra modules

`imports` loads modules when each worker starts. A module that is missing is installed with `pip`, and an import that still fails stops the worker.

```yaml
imports:
  custom_utility:
    module: custom_utils
    pip_name: custom-utils-package
  github_helper:
    module: github_helper
    pip_name: git+https://github.com/username/helper-repo.git
  requests_import:
    module: requests
  legacy_module: some.legacy.module
```

`pip_name` defaults to the module name. A plain string is the older form and names the module alone. See [dynamic modules](../extending/dynamic-modules.md).

## Add processing links

A link entry has a name of your choice and these keys:

| Key | Required | Use |
|---|---|---|
| `module` | Yes | Python module with a `run` function, such as `links.tag` |
| `options` | In practice | Mapping passed to the link |
| `pip_name` | No | Package to install when the module is missing |

```yaml
links:
  tag_processed:
    module: links.tag
    options:
      tags:
        - processed
```

Always write `options`, even as `options: {}`. Without the key the link receives `None`, not its `default_options`, and most bundled links then raise an error. A bare `options:` key also loads as `None`. A missing block does not break `delay`, `hugging_llm_link` or the four deprecated transcription modules. `transcribe` then falls to `whisper_builtin` and raises, and `wtf_transcribe` halts the chain because it has no `vfun-server-url`.

`options.after_link` goes to the after-link hook, which does nothing unless a build replaces it. See [creating links](../extending/creating-links.md).

The [link reference](../reference/links/index.md) lists each bundled link and its options.

### Transcribe with one link

`links.transcribe` is the transcription link. `vendor` picks the service and `vendor_options` goes to it unchanged.

```yaml
links:
  transcribe:
    module: links.transcribe
    options:
      vendor: deepgram
      vendor_options:
        DEEPGRAM_KEY: replace-with-a-key
        api:
          model: nova-3
```

Always set `vendor`. The default, `whisper_builtin`, calls `Vcon.transcribe`, which the `Vcon` class in `common/vcon.py` does not have, so the link raises an error.

The per-vendor modules are deprecated. A chain that names one still runs: the server routes it through `links.transcribe`, treats its `options` as `vendor_options` and logs a warning.

| Deprecated module | `vendor` |
|---|---|
| `links.deepgram_link` | `deepgram` |
| `links.groq_whisper` | `groq` |
| `links.hugging_face_whisper` | `hugging_face` |
| `links.openai_transcribe` | `openai` |

`links.wtf_transcribe` is a separate link and does not go through this dispatcher.

## Add storage backends

A storage entry has a name, a `module` and `options`:

```yaml
storages:
  postgres:
    module: storage.postgres
    options:
      user: vcon
      password: replace-with-a-password
      host: postgres
      port: "5432"
      database: vcon_server
```

With no `options` key, the adapter gets its `default_options`. With the key, it gets exactly that mapping, and the server does not merge in the defaults. Check the adapter's reference page for the options it requires.

Storage modules load with a plain import, so `pip_name` has no effect here. List a storage package under `imports`, or install it in the image. The API process does not run `imports`, and it loads the same adapters to read vCons, so an image install covers both.

The [storage adapter reference](../reference/storage-adapters/index.md) lists each adapter.

## Add tracers

Tracers run around links and report each step to an outside system. Every tracer under the top-level `tracers` key runs for every chain.

```yaml
tracers:
  jlinc:
    module: tracers.jlinc
    options:
      data_store_api_url: http://jlinc-server:9090
      data_store_api_key: replace-with-a-key
      archive_api_url: http://jlinc-server:9090
      archive_api_key: replace-with-a-key
      system_prefix: VCONProd
      agreement_id: 00000000-0000-0000-0000-000000000000
      hash_event_data: true
      dlq_vcon_on_error: true
```

Keep the `options` key. Without it the tracer receives `None`, and the error handling in `conserver/main.py` raises a second error when the tracer fails.

A tracer error is logged and processing continues, unless `dlq_vcon_on_error` is true. Then the vCon moves to the dead letter queue. A chain with no links runs no tracers. See [creating tracers](../extending/creating-tracers.md).

## Build processing chains

A chain ties links and storage to ingress lists:

```yaml
chains:
  main_chain:
    links:
      - transcribe
      - tag_processed
    storages:
      - postgres
    ingress_lists:
      - main_ingress
    egress_lists:
      - processed
```

| Key | Required | Use |
|---|---|---|
| `links` | Yes | Link names, run in order. Use `[]` for none. A chain without the key fails each vCon with `KeyError` |
| `ingress_lists` | To run at all | Redis lists the workers read for this chain |
| `storages` | No | Storage names to write when the links finish |
| `egress_lists` | No | Redis lists that receive the vCon UUID when the links finish |

These rules follow from the code:

- Each entry under `links` must be a plain name. An inline mapping such as `- analyze: {model: gpt-4}` raises `TypeError` and sends the vCon to the dead letter queue. To vary options, define a second link.
- If two chains name the same ingress list, the chain defined last takes it.
- A link that returns nothing halts the chain. The vCon then skips egress lists and storage.
- Egress lists fill before storage runs. A storage failure does not fail the chain: that vCon goes to `DLQ:storage:<backend>`.

Three keys that appear in older examples do nothing:

| Key | What the code does |
|---|---|
| `enabled` | Never reads it. `enabled: 0` does not stop a chain. To stop one, remove its `ingress_lists` |
| `timeout` | Writes it to a debug log and enforces nothing |
| `tracers` | Never reads it on a chain. See [tracers](#add-tracers) |

The `ingress-lists` and `egress-lists` keys on a link, seen in `example_config.yml`, are ignored too.

[Chains and pipelines](chains-and-pipelines.md) covers chain design.

## Pull from another server

A follower polls the egress list of another server and copies each vCon into a local ingress list. Followers start with the conserver process.

```yaml
followers:
  upstream_server:
    url: http://upstream-vcon-server:8000
    egress_list: processed
    follower_ingress_list: incoming_from_upstream
    auth_token: replace-with-the-upstream-key
    pulling_interval: 60
    fetch_vcon_limit: 10
```

| Key | Use |
|---|---|
| `url` | Base URL of the other server's API, with no trailing slash |
| `egress_list` | Egress list to pop UUIDs from |
| `follower_ingress_list` | Local list that receives each vCon |
| `auth_token` | API key for the other server, sent in the header named by the local `CONSERVER_HEADER_NAME` |
| `pulling_interval` | Seconds between polls |
| `fetch_vcon_limit` | UUIDs to pop on each poll |

All six keys are required. Popping removes the UUID from the other server's list, so give each follower its own egress list.

## See a complete example

This file joins the sections above into one working shape. Replace the placeholders before you use it.

```yaml
ingress_auth:
  partner_a: "replace-with-a-key"

links:
  transcribe:
    module: links.transcribe
    options:
      vendor: deepgram
      vendor_options:
        DEEPGRAM_KEY: replace-with-a-key
        api:
          model: nova-3
  summarize:
    module: links.analyze
    options:
      OPENAI_API_KEY: replace-with-a-key
      analysis_type: summary
      prompt: "Summarize this conversation."
      source:
        analysis_type: transcript
        text_location: body.transcript
  tag_processed:
    module: links.tag
    options:
      tags:
        - processed
  route_urgent:
    module: links.tag_router
    options:
      tag_routes:
        urgent: urgent_queue
      forward_original: true

storages:
  postgres:
    module: storage.postgres
    options:
      user: vcon
      password: replace-with-a-password
      host: postgres
      port: "5432"
      database: vcon_server
  s3:
    module: storage.s3
    options:
      aws_access_key_id: replace-with-a-key-id
      aws_secret_access_key: replace-with-a-secret
      aws_bucket: vcon-archive
      aws_region: us-east-1

chains:
  main_pipeline:
    links:
      - transcribe
      - summarize
      - tag_processed
      - route_urgent
    storages:
      - postgres
      - s3
    ingress_lists:
      - main_ingress
      - partner_a
    egress_lists:
      - processed

  archive_only:
    links: []
    storages:
      - s3
    ingress_lists:
      - archive_ingress
```
