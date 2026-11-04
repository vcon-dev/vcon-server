# Archived documents

These pages keep older product notes on record. Use the live manual for anything you plan to run or configure.

!!! warning "These files are historical"
    The files in this archive are historical and no longer maintained. They were last edited on or before 2026-04-08 and do not describe the current code. Routes, options, image names, version numbers, Redis keys and roadmap dates in them can be wrong or never have existed.

    Statements about compliance, consent or data rights in these files are not claims about the open source server. The server carries `lawful_basis` attachments and does not manage consent. It does not make a deployment compliant. See [lawful basis](../concepts/lawful-basis.md) and [editions](../concepts/editions.md).

## Browse the archived files

| File | Live page to use instead |
|---|---|
| [Product docs index](prod_mgt/README.md) | [Documentation home](../index.md) |
| [Product overview](prod_mgt/01_PRODUCT_OVERVIEW.md) | [Server architecture](../concepts/architecture.md) |
| [Core functionality](prod_mgt/02_CORE_FUNCTIONALITY.md) | [Chains, links and storage](../concepts/chains-links-storage.md), [vCon lifecycle](../concepts/vcon-lifecycle.md) |
| [Storage adapters](prod_mgt/03_STORAGE_ADAPTERS.md) | [Storage adapters](../reference/storage-adapters/index.md) |
| [Link processors](prod_mgt/04_LINK_PROCESSORS.md) | [Links](../reference/links/index.md), [JLINC tracer](../reference/tracers/jlinc.md) |
| [External integrations](prod_mgt/05_EXTERNAL_INTEGRATIONS.md) | [Links](../reference/links/index.md), [JLINC tracer](../reference/tracers/jlinc.md) |
| [Deployment and operations](prod_mgt/06_DEPLOYMENT_OPERATIONS.md) | [Installation](../installation/index.md), [Operations](../operations/index.md), [Workers](../configuration/workers.md) |
| [Use cases and examples](prod_mgt/07_USE_CASES_EXAMPLES.md) | [Chains and pipelines](../configuration/chains-and-pipelines.md) |
| [API reference](prod_mgt/08_API_REFERENCE.md) | [API reference](../reference/api.md) |
| [Architecture and design](prod_mgt/09_ARCHITECTURE_DESIGN.md) | [Server architecture](../concepts/architecture.md) |
| [Roadmap](prod_mgt/10_ROADMAP_FUTURE.md) | None. The dates have passed and no live roadmap replaces it |
| [Redis caching](README_REDIS_CACHING.md) | [Read a stored vCon](../concepts/vcon-lifecycle.md#read-a-stored-vcon) |

## Track the merged content

Content that was unique and still true moved to the live pages below before these files were archived.

| Source | Content | Live page |
|---|---|---|
| Redis caching | Reads served from Redis after a recache, and the `VCON_REDIS_EXPIRY` trade-off | [vCon lifecycle](../concepts/vcon-lifecycle.md#read-a-stored-vcon) |
| Storage adapters | Multi-storage patterns, corrected to say a list makes copies and not tiers | [Storage adapters](../reference/storage-adapters/index.md#combine-backends-on-a-chain) |
| Link processors | Filter links go early in a chain | [Chains and pipelines](../configuration/chains-and-pipelines.md#halt-a-vcon-in-a-chain) |
| Link processors | Links must be safe to repeat | [Create a processing link](../extending/creating-links.md#follow-these-practices) |

The rest was already covered by the live pages or no longer matches the code. The chain examples in the use cases file, for instance, set options the links do not read.
