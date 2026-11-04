# Configuration guide

vCon Server reads two kinds of settings:

| Source | Holds | Reference |
|---|---|---|
| Environment variables, usually in `.env` | Redis, API keys, workers, logging, telemetry | [Environment reference](../reference/environment.md) and [environment guide](environment-variables.md) |
| YAML file, usually `config.yml` | Links, storages, tracers, chains, ingress keys, followers | [YAML configuration](yaml-configuration.md) |

Credentials for links and storage backends go in the YAML file as `options`. The server does not expand `${VAR}` in that file.

## Start with a minimal setup

**.env**:

```bash
REDIS_URL=redis://localhost:6379
CONSERVER_API_TOKEN=your-secure-token
CONSERVER_CONFIG_FILE=./config.yml
```

**config.yml**:

```yaml
storages:
  redis_storage:
    module: storage.redis_storage

chains:
  simple_chain:
    links: []
    storages:
      - redis_storage
    ingress_lists:
      - default
```

## Grow into a production setup

**.env**:

```bash
REDIS_URL=redis://redis:6379
CONSERVER_API_TOKEN=your-production-token
CONSERVER_CONFIG_FILE=./config.yml
ENV=production
LOGGING_CONFIG_FILE=common/logging.conf

CONSERVER_WORKERS=4
CONSERVER_PARALLEL_STORAGE=true
```

The logging file sets log levels. See [logging](../operations/logging.md).

**config.yml**:

```yaml
links:
  transcribe:
    module: links.transcribe
    options:
      vendor: deepgram
      vendor_options:
        DEEPGRAM_KEY: your-deepgram-key
        api:
          model: nova-3
  analyze:
    module: links.analyze
    options:
      OPENAI_API_KEY: your-openai-key
      analysis_type: summary
      model: gpt-4
      prompt: Summarize this conversation.
      source:
        analysis_type: transcript
        text_location: body.transcript
  tag_processed:
    module: links.tag
    options:
      tags:
        - processed

storages:
  postgres:
    module: storage.postgres
    options:
      host: postgres
      port: 5432
      database: vcon_server
      user: postgres
      password: your-password
  s3:
    module: storage.s3
    options:
      aws_access_key_id: your-key-id
      aws_secret_access_key: your-secret
      aws_bucket: vcon-archive

chains:
  production_chain:
    links:
      - transcribe
      - analyze
      - tag_processed
    storages:
      - postgres
      - s3
    ingress_lists:
      - production
    egress_lists:
      - processed
```

The [link reference](../reference/links/index.md) and the [storage adapter reference](../reference/storage-adapters/index.md) list every option.

## Find the right page

| Page | Covers |
|---|---|
| [Environment variables](environment-variables.md) | Choosing values |
| [YAML configuration](yaml-configuration.md) | The file structure and reload rules |
| [Chains and pipelines](chains-and-pipelines.md) | Building pipelines |
| [Egress format compatibility](egress-compatibility.md) | Sending the legacy vCon format |
| [Authentication](authentication.md) | API keys and ingress keys |
| [Workers](workers.md) | Worker processes, concurrency and parallel storage |

## Understand the loading order

### Load order for the environment

`common/settings.py` loads a `.env` file when it is imported. A variable already set in the process wins over the same variable in `.env`. Compose passes `.env` through `env_file`. Each process reads these values once at startup.

### Location of the YAML file

`CONSERVER_CONFIG_FILE` gives the path. The default is `./example_config.yml`, which is a catalogue of syntax and stops the worker if you run it unchanged, so always set your own.

The server reads the file again as it runs, so most edits need no restart. See [the reload table](yaml-configuration.md#plan-for-reloads).

### Checks on your configuration

The server does not validate the file at startup. A link with a bad module name fails when a vCon first reaches it. To see what the server loads, run this in the conserver container:

```bash
python -c "from config import get_config; import json; print(json.dumps(get_config(), indent=2))"
```

For a manual install, prefix it with `uv run` and set `PYTHONPATH` as in [Install from source](../installation/manual-installation.md#set-the-environment).

## Follow these practices

- Keep `.env` and `config.yml` out of version control, because both hold secrets.
- Use a separate file for each environment.
- Name chains for what they do.
- Set `options` on every link, even as `options: {}`.
- Use [ingress keys](authentication.md#scope-a-key-to-an-ingress-list) for outside systems.
- Size workers with the [workers guide](workers.md).

## Copy a common configuration

These fragments show the `chains` section only. Each name must match an entry you define under `links` or `storages`.

### Call analytics

```yaml
chains:
  call_analytics:
    links:
      - transcribe         # links.transcribe
      - analyze            # links.analyze
      - detect_engagement  # links.detect_engagement
      - tag_router         # links.tag_router
    storages:
      - postgres
      - elasticsearch
    ingress_lists:
      - call_recordings
```

### Long-term archive with a trace

Tracers sit at the top level and run for every chain. A `tracers` key inside a chain is not read. See [Add tracers](yaml-configuration.md#add-tracers).

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

chains:
  archive:
    links:
      - transcribe         # links.transcribe
      - check_and_tag      # links.check_and_tag
    storages:
      - s3
      - postgres
    ingress_lists:
      - archive_calls
```

The tracer reports processing steps. It reads no `lawful_basis` attachment and makes no deployment compliant. See [Lawful basis](../concepts/lawful-basis.md).

### Searchable knowledge base

`storage.milvus` needs the `storage-milvus` dependency group, which the published images leave out.

```yaml
chains:
  knowledge_base:
    links:
      - transcribe         # links.transcribe
      - analyze_and_label  # links.analyze_and_label
    storages:
      - milvus
      - mongo
    ingress_lists:
      - knowledge_ingress
```

## Troubleshoot a configuration

### Check the file path and syntax

```bash
ls -la "$CONSERVER_CONFIG_FILE"
python -c "import yaml; yaml.safe_load(open('config.yml'))"
```

### Check a suspect variable

Run this where the process runs, with `PYTHONPATH` set:

```bash
env | grep CONSERVER
python -c "import settings; print(settings.REDIS_URL)"
```

### Trace a silent chain

Check that the list you submit to appears in the chain's `ingress_lists`:

```yaml
chains:
  my_chain:
    ingress_lists:
      - my_list  # Must match where vCons are submitted
```

The worker never reads `enabled`. Setting `enabled: 0` does not stop a chain, so remove its `ingress_lists` instead.

## Continue with these guides

- [Environment variables](environment-variables.md)
- [YAML configuration](yaml-configuration.md)
- [Chains and pipelines](chains-and-pipelines.md)
