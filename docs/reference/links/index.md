# Links

A link is one processing step in a chain. Each module lives in `conserver/links/<name>/` and loads as `links.<name>`. This section has one page per module, with options and defaults taken from the code.

## Browse the link modules

| Page | Module | Status | Effect on the vCon |
|---|---|---|---|
| [transcribe](transcribe.md) | `links.transcribe` | Current | Depends on the vendor. Adds `transcript` analysis |
| [wtf_transcribe](wtf-transcribe.md) | `links.wtf_transcribe` | Current | Adds `wtf_transcription` analysis |
| [deepgram_link](deepgram.md) | `links.deepgram_link` | Deprecated | Adds `transcript` analysis |
| [groq_whisper](groq-whisper.md) | `links.groq_whisper` | Deprecated | Adds `transcript` analysis |
| [hugging_face_whisper](huggingface-whisper.md) | `links.hugging_face_whisper` | Deprecated | Adds `transcript` analysis |
| [openai_transcribe](openai-transcribe.md) | `links.openai_transcribe` | Deprecated | Adds `transcript` analysis |
| [analyze](analyze.md) | `links.analyze` | Current | Adds analysis per dialog |
| [analyze_and_label](analyze-and-label.md) | `links.analyze_and_label` | Current | Adds analysis per dialog and one tag per label |
| [analyze_vcon](analyze-vcon.md) | `links.analyze_vcon` | Current | Adds one analysis for the whole vCon |
| [check_and_tag](check-and-tag.md) | `links.check_and_tag` | Current | Adds analysis per dialog and a tag when the answer is yes |
| [detect_engagement](detect-engagement.md) | `links.detect_engagement` | Current | Adds analysis per dialog and an `engagement` tag |
| [hugging_llm_link](hugging-llm.md) | `links.hugging_llm_link` | Known issue | Fails when it reaches a transcript |
| [tag](tag.md) | `links.tag` | Current | Adds tags |
| [tag_router](tag-router.md) | `links.tag_router` | Current | None. Pushes the uuid to other lists |
| [jq_link](jq.md) | `links.jq_link` | Current | None. Filters the chain |
| [sampler](sampler.md) | `links.sampler` | Current | None. Filters the chain |
| [webhook](webhook.md) | `links.webhook` | Current | None. Posts the vCon out |
| [post_analysis_to_slack](slack.md) | `links.post_analysis_to_slack` | Current | Marks posted analysis entries |
| [diet](diet.md) | `links.diet` | Current | Removes or moves content |
| [expire_vcon](expire-vcon.md) | `links.expire_vcon` | Current | None. Sets a Redis TTL |
| [datatrails](datatrails.md) | `links.datatrails` | Current. Imports `fastapi`, so it fails to import in the `docker/Dockerfile.conserver` image and each vCon goes to the dead letter queue. It imports in the `docker/Dockerfile` image | None. Records events externally |
| [scitt](scitt.md) | `links.scitt` | Current. Imports `fastapi`, so it fails to import in the `docker/Dockerfile.conserver` image and each vCon goes to the dead letter queue. It imports in the `docker/Dockerfile` image | Adds `scitt_receipt` analysis |
| [delay](delay.md) | `links.delay` | Test aid | None. Sleeps |

## Declare a link in a chain

Define each link once under `links`, then list its name in a chain. A chain holds names only.

```yaml
links:
  summarize:
    module: links.analyze
    options:
      OPENAI_API_KEY: your-openai-key
      prompt: Summarize this conversation in two sentences.
      source:
        analysis_type: transcript
        text_location: body.text

chains:
  main:
    links:
      - summarize
    storages:
      - postgres
    ingress_lists:
      - default
    enabled: 1
```

Set `options` on every link, even if it is only `options: {}`. `conserver/main.py` passes the value of `options` straight to `run`, so a link with no `options` key receives `None` in place of its `default_options`, and most modules then raise. A missing block does not break `delay`, `hugging_llm_link` or the four deprecated transcription modules. `transcribe` then falls to `whisper_builtin` and raises, and `wtf_transcribe` halts the chain because it has no `vfun-server-url`.

The config loader reads YAML with `yaml.safe_load` and does not expand `${VAR}`. A value such as `${OPENAI_API_KEY}` reaches the link as that literal text. See [YAML configuration](../../configuration/yaml-configuration.md) for the rest of the file.

## Follow the link contract

The worker calls `run(vcon_uuid, link_name, opts)` for each link in order.

| Result | Effect |
|---|---|
| Returns the uuid | The next link runs. After the last link the vCon goes to egress lists and then storages |
| Returns a different uuid | The chain continues with that uuid |
| Returns `None` | The chain stops. Storages and egress lists do not run for this vCon |
| Raises | The worker moves the vCon to the [dead letter queue](../../operations/dead-letter-queue.md) of its ingress list |

So a filter that drops a vCon also keeps it out of the chain's storages. Its copy in Redis stays, subject to any expiry on the key.

After each run the worker calls `conserver/after_link_hook.py` and passes it the `after_link` key from `options`, if there is one. The hook in this repo does nothing.

## Set the shared filter options

`analyze`, `analyze_and_label`, `analyze_vcon`, `check_and_tag` and `detect_engagement` read these two options through `lib.links.filters`. In both cases a skipped vCon continues down the chain unchanged. The other links ignore them, and `post_analysis_to_slack` has its own [`only_if`](slack.md) with a different shape.

| Option | Type | Default | Description |
|---|---|---|---|
| `only_if` | dict | none | Runs the link only when the vCon has a matching entry. Omit it to include every vCon |
| `only_if.section` | string | required | `attachments` or `analysis` |
| `only_if.type` | string | none | Entry to match. Alias of `only_if.purpose`; give one of the two |
| `only_if.purpose` | string | none | Entry to match. Takes priority over `only_if.type` |
| `only_if.includes` | string | required | Value to look for in the entry's `body` |
| `sampling_rate` | float | `1` in each module's `default_options` | Chance of running, from 0 to 1. A value of `0` or an unset option means always run |

For `attachments`, an entry matches on either its `purpose` or its legacy `type`. For `analysis` it matches on `type`. When the target is `tags`, `includes` must equal a whole `name:value` tag. For any other target it is a substring of the body, or of the JSON text of a dict or list body.

```yaml
options:
  only_if:
    section: attachments
    purpose: tags
    includes: department:sales
  sampling_rate: 0.25
```

## Set the LLM client options

`analyze`, `analyze_and_label`, `analyze_vcon`, `check_and_tag`, `detect_engagement` and `openai_transcribe` build their client with `lib.openai_client.get_openai_client`, as does the LiteLLM path of `deepgram_link`. The client reads these keys from the link options, not from the environment. The first complete group wins, in this order.

| Option | Description |
|---|---|
| `LITELLM_PROXY_URL`, `LITELLM_MASTER_KEY` | Use a LiteLLM proxy. Both are required |
| `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY` | Use Azure OpenAI. Both are required |
| `AZURE_OPENAI_API_VERSION` | Azure API version. Defaults to `2024-10-21` |
| `OPENAI_API_KEY`, `openai_api_key`, `api_key` | Use OpenAI. The first one set is used |
| `organization`, `organization_key` | Optional, for OpenAI and LiteLLM |
| `project`, `project_key` | Optional, for OpenAI and LiteLLM |

With none of these set the client raises `ValueError`. Only `detect_engagement` catches that and skips the vCon.

Calls to the model make up to 6 attempts with exponential backoff. After the last attempt the error reaches the link.

## Point analysis at the transcript text

`analyze`, `analyze_and_label`, `check_and_tag` and `detect_engagement` find their input with a `source` option. The link looks up the analysis entry of type `source.analysis_type` on each dialog, decodes its body, then reads the dotted path `source.text_location`. A dialog with no entry or no text at that path logs a warning and is skipped.

The default path must fit the transcription link in the chain.

| Transcript written by | `text_location` to use |
|---|---|
| `transcribe` with vendor `openai` or `groq` | `body.text` |
| `transcribe` with vendor `deepgram` | `body.transcript`. `body.paragraphs.transcript` works only when the Deepgram response has paragraphs. TODO(verify) which `api` options produce them |
| `transcribe` with vendor `hugging_face` | Depends on the endpoint. Usually `body.text`. TODO(verify) |

## Report AI usage to an endpoint

`analyze`, `deepgram_link` and `openai_transcribe` can post usage records. Nothing is sent unless `send_ai_usage_data_to_url` is set.

| Option | Type | Default | Description |
|---|---|---|---|
| `send_ai_usage_data_to_url` | string | `""` | URL that receives one JSON record per model call |
| `ai_usage_api_token` | string | `""` | Sent as a bearer token |

## Carry lawful basis attachments

No link creates, reads or checks a `lawful_basis` attachment, and no link gates on consent. A transcription or analysis link runs whether or not one is present.

Links leave the attachment in place as they load and save the vCon. The only link that removes attachments is [`diet`](diet.md), which filters on `mime_type` and has no exception for `lawful_basis`.
