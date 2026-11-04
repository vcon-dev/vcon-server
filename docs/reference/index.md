# Reference

These pages state what the code does: every option, variable, route and metric, for lookup rather than reading in order. For task-led help, start with [configuration](../configuration/index.md).

## Find the page for a name

| Looking for | Page |
|---|---|
| A link and its options | [Links](links/index.md) |
| A storage adapter and its options | [Storage adapters](storage-adapters/index.md) |
| A tracer and its options | [JLINC tracer](tracers/jlinc.md) |
| An API route, its parameters and responses | [API](api.md) |
| A route, its auth and its status code, in one table | [API routes](api-routes.md) |
| An environment variable, its default and where it is read | [Environment variables](environment.md) |
| A container, port or Compose profile | [Ports and services](ports.md) |
| A metric name, its type and where it is emitted | [Metrics](metrics.md) |
| A command-line option | [CLI](cli-reference.md) |

## Trust the generated pages

`scripts/docs/` builds four of these pages from the code, so their names, defaults and types come straight from it: [environment variables](environment.md), [ports and services](ports.md), [API routes](api-routes.md) and [metrics](metrics.md). Each generator fails if `scripts/docs/descriptions.yml` names something the code no longer has.

To change text on one of these pages, edit `scripts/docs/descriptions.yml` and run `scripts/docs/check.sh`. Do not edit the page.

## Name modules in the YAML file

The `module` value in the [YAML configuration](../configuration/yaml-configuration.md) is a Python module path:

| Kind | Form | Example |
|---|---|---|
| Link | `links.<name>` | `links.tag` |
| Storage adapter | `storage.<name>` | `storage.postgres` |
| Tracer | `tracers.<name>` | `tracers.jlinc` |

The folders are `conserver/links/`, `common/storage/` and `conserver/tracers/`. A link or tracer can also come from an installed package. See [dynamic modules](../extending/dynamic-modules.md).
