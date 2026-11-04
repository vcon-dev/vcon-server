# vCon Server documentation plan

Status: approved 2026-11-03. Base commit `323109a` on `origin/main`, branch `docs/vconic-docs-set`.

This plan gives operators and link authors one set of docs that matches the open source code, states plainly what that code does and does not do for consent, and gives maintainers a CI check that keeps it that way.

## Current state

`docs/` holds 42 Markdown pages, about 12,700 lines, built with MkDocs Material. `mkdocs build --strict` passes.

Well covered: installation paths, YAML configuration, chains, workers, authentication, dead letter queue, logging, the three extension guides.

Thin or wrong:

| Area | Finding |
|---|---|
| Publishing | `https://vcon-dev.github.io/vcon-server/` returns 404. GitHub Pages is not enabled and no workflow deploys the site, yet `README.md` sends every reader there |
| Dead link | `README.md` links `/contributing/`, and no such page exists |
| Links | 23 link modules, 5 reference pages. `datatrails`, `delay`, `hugging_llm_link`, `scitt` and `wtf_transcribe` appear nowhere in `docs/` |
| Storage | 15 adapters, 3 reference pages. `scitt`, `spaceandtime`, `utopia` and `vcon_mcp` appear nowhere in `docs/` |
| Environment | 42 variables read directly in code by a first grep; 13 missing from the environment page, 8 of them from all of `docs/` |
| API | `/dlq/storage`, `/dlq/storage/reprocess` and `/stats/queue` are missing from the API reference |
| Metrics | About 38 metric names in code, no generated list |
| Orphans | `docs/storage-recovery.md` and `docs/installation/redis-migration.md` are outside the nav |
| Tooling | 51 Poetry references in docs; zero `uv sync` or `uv run`. The Dockerfiles and `uv.lock` use uv |
| Spec examples | 11 or more examples show `vcon: "0.0.1"`; the current syntax value is `0.4.0` |
| Redis | `docs/installation/docker.md` and `docs/storage-recovery.md` mention RedisJSON or Redis Stack after the move to plain Redis (#203). Each needs review; `redis-migration.md` mentions them on purpose |
| Lawful basis | No page says what the open source server does with a `lawful_basis` attachment, or that it does not manage consent |
| Edition language | `docs/index.md:13` says "Enterprise Ready" and `docs/operations/index.md:248` labels a sizing tier "Enterprise". Both read as product editions |
| Consent claims | `prod_mgt/04_LINK_PROCESSORS.md:125` and `prod_mgt/05_EXTERNAL_INTEGRATIONS.md:148` credit JLINC with consent management. The JLINC code here is a tracer and has no consent logic |
| Older drift | `server/links` module paths, the old Redis queue pattern and deprecated vendor transcribe modules in `docs/extending/` and `docs/configuration/`; `docs/index.md:135` claims a version that `pyproject.toml` does not |
| Agent context | No `CLAUDE.md`, `AGENTS.md` or `CONTRIBUTING.md` in the repo |
| Overlap | `prod_mgt/` (11 files, 3,067 lines, last touched 2026-04-08), `README_REDIS_CACHING.md`, `common/README_CORE.md` and per-link READMEs overlap `docs/` |

Diagrams: 14 Mermaid blocks across 11 pages, unbranded. No SVGs, decks or animations in this repo. `vcon-dev/vcon-docs` holds `conserver/figures/vcon-day-stations.svg` and a conveyor infographic page.

## Edition boundary

These docs cover the open source server only. A commercial edition builds on the published open source image and adds its own files; it is a separate product with separate docs.

Active consent management is a commercial feature. Its absence here is by design and is not a gap to fix.

| Capability | Open source server | Docs treatment |
|---|---|---|
| Carry a `lawful_basis` attachment through the pipeline, storage and egress | Yes. Preserved on read, write and legacy downgrade (`common/lib/vcon_compat.py`, `common/lib/vcon_egress_compat.py`, storage round-trip tests) | Document |
| Show an existing basis in rendered output | Yes, in the `utopia` adapter (`common/storage/utopia/__init__.py:156`) | Document |
| Opt-in skip when no basis grants `analysis` | Yes, `require_analysis_grant`, default false, `utopia` adapter only | Document as adapter behaviour; see decision 10 |
| Create a lawful basis record | No | State the absence |
| Validate, enforce or gate on consent in a chain | No | State the absence |
| Manage consent over time: revocation, policy, proof | No | State the absence |

Rules for every agent in this run:

- Write only about behaviour in this repo. Never present consent management as an open source capability, and never imply the server makes a deployment compliant.
- Never name private modules, private repos, customers or commercial pricing. A name list kept outside this repo feeds the Verify check, so the list itself stays private.
- Do not read private repos for content. The boundary above is the only input from them.
- Do not write instructions for rebuilding commercial features. `extending/creating-links.md` stays generic.
- Treat a missing commercial feature as expected. It goes in no contradiction list and no Linear issue.

## Target structure

| Section | Page | State |
|---|---|---|
| Start | `index.md`, `getting-started/*` | Existing, revise |
| Start | `README.md` | Existing, fix links |
| Concepts | `concepts/architecture.md` | New |
| Concepts | `concepts/vcon-lifecycle.md` | New |
| Concepts | `concepts/chains-links-storage.md` | New |
| Concepts | `concepts/lawful-basis.md` | New, covers what the server carries and what it leaves out |
| Concepts | `concepts/editions.md` | New, per decision 8 |
| Guides | `installation/*`, `configuration/*`, `extending/*` | Existing, revise; Poetry to uv |
| Guides | `contributing.md` | New |
| Reference | `reference/links/*` | 5 existing, 18 new, one per module |
| Reference | `reference/storage-adapters/*` | 3 existing, 12 new, one per adapter |
| Reference | `reference/tracers/jlinc.md` | New |
| Reference | `reference/api.md` | Moved from `operations/api-reference.md`, gaps closed |
| Reference | `reference/environment.md`, `ports.md`, `metrics.md` | Generated |
| Reference | `reference/cli-reference.md` | Existing, verify |
| Operations | `operations/*` | Existing, revise |
| Operations | `operations/storage-recovery.md` | Moved into the nav |
| Operations | `installation/redis-migration.md` | Added to the nav |
| Visuals | `visuals/index.md`, `diagrams/`, `motion/` | New |
| Archive | `archive/` | New, per decision 4 |

## Core diagram set

| ID | Diagram | Kind | Code source of truth | Owner page | Exists | Motion |
|---|---|---|---|---|---|---|
| D01 | System context | flowchart | `api/api.py`, `conserver/main.py`, `common/storage/` | `concepts/architecture.md` | Partial | M1 |
| D02 | Container and port map | flowchart | `docker-compose.yml`, `docker/`, `nginx.conf` | `reference/ports.md` | No | |
| D03 | Deploy map | flowchart | `docker-compose.yml`, `docs/installation/kubernetes.md` | `installation/index.md` | Partial | |
| D04 | Ingress paths | flowchart | `api/api.py` (`/vcon`, `/vcon/ingress`, `/vcon/external-ingress`), `conserver/follower.py` | `concepts/architecture.md` | No | |
| D05 | Chain pipeline | flowchart | `conserver/main.py` (`VconChainRequest`, `worker_loop`) | `configuration/chains-and-pipelines.md` | Partial | M1 |
| D06 | Worker and queue topology | flowchart | `conserver/main.py`, `common/lib/queue.py` | `configuration/workers.md` | Partial | M2 |
| D07 | vCon lifecycle | state | `conserver/main.py`, `common/lib/vcon_redis.py`, `conserver/links/expire_vcon` | `concepts/vcon-lifecycle.md` | No | M3 |
| D08 | Dead letter flow | state | `common/lib/queue.py`, `common/dlq_utils.py`, `api/api.py` | `operations/dead-letter-queue.md` | Partial | M4 |
| D09 | Storage write and recovery | sequence | `common/storage/base.py`, `common/dlq_utils.py` | `operations/storage-recovery.md` | No | M4 |
| D10 | vCon assembly, lawful basis shown as carried and never created | class | `common/vcon.py`, `common/lib/vcon_compat.py`, link modules | `concepts/lawful-basis.md` | No | M3 |
| D11 | Egress compatibility | flowchart | `common/lib/vcon_egress_compat.py` | `configuration/egress-compatibility.md` | No | |
| D12 | Link execution contract | sequence | `conserver/main.py`, `conserver/hook.py`, `conserver/after_link_hook.py` | `extending/creating-links.md` | Partial | |
| D13 | Authentication paths | sequence | `api/api.py`, `common/settings.py` | `configuration/authentication.md` | Partial | |
| D14 | Observability | flowchart | `common/lib/metrics.py`, `common/lib/tracing.py`, `common/lib/queue_metrics.py`, `conserver/tracers/` | `operations/monitoring.md` | No | |

The event bus and media path items from the standard list do not apply: this repo has Redis lists, covered by D06, and handles no live media. It has no agent loops.

## Motion scenes

No scenes exist, so numbering starts at M1. Every scene has a static Mermaid twin.

| ID | Scene | Twin |
|---|---|---|
| M1 | A vCon runs a chain | D01, D05 |
| M2 | Workers drain the ingress queues | D06 |
| M3 | A vCon gains analysis, tags and attachments | D07, D10 |
| M4 | A failed vCon reaches the DLQ and returns | D08, D09 |

## Generated reference

`scripts/docs/` emits environment variables, ports, API routes and metric names from code. The environment script must parse `common/settings.py`, direct `os.getenv` reads and per-module reads. `scripts/docs/check.sh` runs the generators, renders the diagrams, runs `mkdocs build --strict` and fails on a git diff. A new CI job runs it, with SVG byte diffs skipped.

## Orchestration

Agents write to this worktree and never commit. About 25 agents in total. The first run on another repo used 29 agents, 85 minutes and 5.4M subagent tokens on 2 CPUs.

| Phase | Agents | Work | Gate |
|---|---|---|---|
| Inventory | 1 | Generators, theme, render and check scripts, CI job, README extract | Scripts run clean |
| Diagrams | 4 | D01 to D14, split by source file | `mmdc` renders |
| Reference | 4 | Links; storage and tracers; API and CLI; config, ports, metrics | Every name in code appears in the docs and the reverse |
| Guides | 6 | Start and README; concepts; lifecycle and lawful basis; install and uv; ops; merges, archive, nav | Pages link to reference and copy nothing |
| Motions | 1, 4, then 1 | Scene shell and brand; one agent per scene; integrator with Playwright | Every tab runs over `file://` |
| Verify | 3, then 1 | Code audit, cold reader, mechanical checks including the private name list and the edition rules; fixer changes docs only | `check.sh` passes, zero private names |

Reference then Guides runs alongside Motions after Diagrams.

## Decisions taken 2026-11-03

All ten recommendations below were accepted as written.

1. **Docs home and publishing.** Keep `docs/` as the canonical operator manual, add a deploy workflow, enable GitHub Pages, and have conserver.io link to it.
2. **Branding scope.** Vconic colours and type in diagrams, motion scenes and the MkDocs theme, with no Vconic logo or product claims, since this is a community repo under `vcon-dev`.
3. **README.** Keep it at its current short size and fix the links.
4. **Merges.** Fold `README_REDIS_CACHING.md` into `docs/`, leave per-link READMEs as the short form with a link to the reference page, and move `prod_mgt/` into `docs/archive/` with its unique content merged.
5. **Agent context file.** Add a short `CLAUDE.md`.
6. **Linear home.** No project matches this repo by name. File under the existing conserver hardening project.
7. **Plan file.** Keep this file in `docs/plans/`, outside the nav.
8. **Edition mention.** One short `concepts/editions.md` saying a commercial edition exists and adds active consent management, with no module names or pricing, and a link from the lawful basis page.
9. **Commercial docs.** Keep them out of this run and do a second run in the private repo, reusing these diagrams.
10. **`require_analysis_grant`.** This small consent gate already sits in open source. Leave it and document it as an adapter option, since it reads a basis and manages nothing. Moving it would be a code change.

## Flags found while planning

- **Lawful basis:** no open source path creates a `lawful_basis` attachment, by design. See the edition boundary. This is recorded for the audit and is not a code problem.
- **Two `Vcon` classes:** with the `PYTHONPATH` set in `docker/Dockerfile*` and `pytest.ini`, `import vcon` resolves to `common/vcon.py`, not the pinned `vcon>=0.9.2` library. Tested on 2026-11-03. Every link therefore runs on the local class, and docs must describe that one.
- **Legacy shape in the live class:** `add_attachment` (`common/vcon.py:177`) writes `type`, not `purpose`, and omits the required `party`, `dialog` and `start`. `build_new` (line 51) emits `vcon: "0.0.1"`, `redacted` and the reserved `group`, though nothing outside tests calls it. Whether `VconRedis._enforce_spec_on_write` repairs these needs checking.
- **Hard-coded company domain:** `common/vcon.py:15` defaults `UUID8_DOMAIN_NAME` to a company domain in public code, and `build_new` at line 53 passes the same literal, bypassing the setting.
- **Commercial reference:** `docker-compose.yml:20` carries a commented commercial image name.
- **Storage stub:** `common/storage/spaceandtime/__init__.py:41` writes `"vcon": "test"`, and needs review.
- **Version:** `pyproject.toml` still says `0.1.0`.
- **Toolchain end of life:** Material for MkDocs reaches end of life on 2027-05-05. No action in this run.
- **Open branch:** PR #226 changes link metrics and may touch the metrics page.
