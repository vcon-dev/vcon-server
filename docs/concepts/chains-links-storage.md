# Chains, links and storage

This page gives you the model behind the `chains`, `links` and `storages` sections of the config file, so you can predict what a chain does to a vCon before you run it.

A chain is a named route. It reads UUIDs from ingress lists, passes each vCon through links in order, then hands it to egress lists and storage backends. Links change or filter the vCon. Storage backends keep it.

## Define a chain

Define each link and storage once at the top level, then name it in a chain.

```yaml
links:
  label:
    module: links.tag
    options:
      tags:
        - reviewed

storages:
  archive:
    module: storage.file
    options:
      path: /data/vcons

chains:
  main:
    links:
      - label
    storages:
      - archive
    ingress_lists:
      - default
```

An ingress list feeds one chain. If two chains name the same list, the chain defined last takes it.

[Build processing chains](../configuration/yaml-configuration.md#build-processing-chains) lists every key and the older keys the server ignores. [Chains and pipelines](../configuration/chains-and-pipelines.md) covers chain design.

## Follow one chain run

A worker takes these steps for each UUID it pops:

1. It retrieves any trace context stored for that list and UUID.
2. It calls `hook.before_processing`. A falsy result skips the vCon, with no error and no dead letter entry.
3. It runs each link in order.
4. If no link halted the chain, it pushes the UUID to every egress list, then writes to every storage backend.
5. It calls `hook.after_processing`, whether or not the run succeeded.

Egress comes before storage, so a downstream chain can start before the storage writes finish.

[Chains and pipelines](../configuration/chains-and-pipelines.md) draws this flow. [Creating links](../extending/creating-links.md) has the sequence diagram for a single link.

## Learn the link contract

A link is a Python module with a `run` function. The worker calls `run(vcon_uuid, link_name, options)` and acts on the result.

| The link | The chain |
|---|---|
| Returns the same UUID | Continues to the next link |
| Returns a different UUID | Continues. Later links, egress and storage use the new UUID. If a later link raises, the DLQ entry and its TTL still use the UUID the worker popped |
| Returns a falsy value | Stops. The vCon skips egress and storage, and this does not count as an error |
| Raises an exception | Stops. The UUID goes to `DLQ:<ingress list>` |

A filter link therefore keeps a vCon out of storage as well as out of later links. The vCon stays in Redis until it expires. Put storage in an earlier chain if you need to keep what a filter removes.

The worker passes the `options` value from the config as it stands. A link with no `options` key receives `None`, not its `default_options`, so [write `options: {}`](../configuration/yaml-configuration.md#add-processing-links) even when you set nothing. A bare `options:` key also loads as `None`.

Bundled links live in `conserver/links/` and load as `links.<name>`. They read and write the vCon through `lib.vcon_redis.VconRedis` and do queue work through `lib.queue.VconQueue`. Under the image `PYTHONPATH`, `import vcon` gives the `Vcon` class in `common/vcon.py`.

| Family | Links |
|---|---|
| Transcription | [transcribe](../reference/links/transcribe.md), [wtf_transcribe](../reference/links/wtf-transcribe.md) |
| Analysis | [analyze](../reference/links/analyze.md), [analyze_vcon](../reference/links/analyze-vcon.md), [analyze_and_label](../reference/links/analyze-and-label.md), [check_and_tag](../reference/links/check-and-tag.md), [detect_engagement](../reference/links/detect-engagement.md) |
| Tags and routing | [tag](../reference/links/tag.md), [tag_router](../reference/links/tag-router.md) |
| Filters | [jq_link](../reference/links/jq.md), [sampler](../reference/links/sampler.md) |
| Delivery | [webhook](../reference/links/webhook.md), [post_analysis_to_slack](../reference/links/slack.md) |
| Content and expiry | [diet](../reference/links/diet.md), [expire_vcon](../reference/links/expire-vcon.md) |
| External records | [datatrails](../reference/links/datatrails.md), [scitt](../reference/links/scitt.md) |

The [link reference](../reference/links/index.md) has the full list, including deprecated modules. The vendor transcription modules are deprecated: the worker reroutes `links.openai_transcribe`, `links.groq_whisper`, `links.hugging_face_whisper` and `links.deepgram_link` through `links.transcribe` and logs a warning. New chains should use `links.transcribe` with a `vendor` option.

To write your own, see [Creating Links](../extending/creating-links.md). [Dynamic Modules](../extending/dynamic-modules.md) covers modules installed from outside the repo.

## Save to storage backends

A storage adapter copies a vCon out of Redis when a chain finishes. Each adapter is a module in `common/storage/`, loaded as `storage.<name>` by the `Storage` class. `save` is required. `get` and `delete` are optional.

With more than one backend on a chain, writes run in parallel threads unless `CONSERVER_PARALLEL_STORAGE` is off. Otherwise they run in the order listed.

A failed write does not stop the other backends or fail the chain. That backend gets a `DLQ:storage:<backend>` entry, and [storage recovery](../operations/storage-recovery.md) replays the write alone.

Backends also serve reads. On a Redis miss the server looks through the configured backends, as [Server architecture](architecture.md#keep-working-state-in-redis) explains. A backend that cannot answer `get` adds nothing to that lookup, so keep at least one that can.

The [adapter comparison](../reference/storage-adapters/index.md#compare-the-adapters) shows what each adapter supports. A few adapters convert the vCon to an older format when `EGRESS_FORMAT_VERSION` is set. See [Egress format compatibility](../configuration/egress-compatibility.md).

## Connect chains with lists

Chains have no direct link to each other. One chain's egress list becomes another chain's ingress list. This example assumes links named `transcribe` and `label`.

```yaml
chains:
  transcribe:
    links:
      - transcribe
    ingress_lists:
      - calls
    egress_lists:
      - transcribed
  review:
    links:
      - label
    ingress_lists:
      - transcribed
```

An egress list that no chain reads still has a use. A [follower](../configuration/yaml-configuration.md#pull-from-another-server) on another server or a client calling `GET /vcon/egress` can drain it. Otherwise it just grows.

Naming several egress lists sends the same UUID to each. The vCon body is still one Redis key, and a link writes the whole document back, so two chains working on one vCon at the same time can overwrite each other's changes. The [tag_router](../reference/links/tag-router.md) link routes by tag from inside a chain.

## Add tracers and hooks

Tracers and hooks run around links without being part of a chain.

Tracers are defined under the top-level `tracers` key and apply to every chain. Each one runs once before the first link and again after every link that returns. A tracer error is logged and the chain carries on, unless the tracer's `dlq_vcon_on_error` option is true. A failing tracer with no `options` key also stops the chain and sends the vCon to the DLQ, so always set `options`, even as `options: {}`. See [Creating Tracers](../extending/creating-tracers.md) and the [JLINC tracer](../reference/tracers/jlinc.md).

Hooks are plain functions in `conserver/hook.py`, `conserver/after_link_hook.py` and `api/vcon_hook.py`. All of them do nothing by default.

## Continue with related pages

- [Server architecture](architecture.md) places chains inside the running services.
- [vCon lifecycle](vcon-lifecycle.md) shows how a vCon changes state across a chain.
- [Lawful basis](lawful-basis.md) says what the server does with a `lawful_basis` attachment.
