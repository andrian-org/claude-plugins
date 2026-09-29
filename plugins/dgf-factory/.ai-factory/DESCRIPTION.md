# dgf-factory

## Overview

`dgf-factory` is a Claude Code plugin that ports the AI Factory prompt-and-artifact
pipeline into a **DGF-specific agent factory**. Where AI Factory is deliberately
framework-agnostic and learns a project at setup time, dgf-factory is intended to
ship already knowing the DotGov Framework (DGF), and then learn the *system built
with* DGF on top of that.

The plugin is delivered through the existing `dotgov` Claude Code marketplace in
this repository, alongside `doc-coverage-audit`.

Design source of truth: [docs/blueprint.md](../docs/blueprint.md) —
Part 1 is a teardown of AI Factory's architecture, Part 2 maps it onto DGF.

## Current State

Roadmap milestone 11 ("Learning Loop") is built, and milestone 12 ("DGF-Specific Skills") is built
but for `/dgf-scaffold`, which waits on the estate's bootstrap template (ADR 0023 §7). The repository
currently contains:

- `README.md` + `docs/` — landing page and documentation set
- `docs/blueprint.md` — the design document (Part 1 teardown, Part 2 DGF mapping)
- `.claude/skills/aif-*` + `.claude/agents/*` — a full AI Factory 2.18.1 install, used as
  the working reference implementation and as the pipeline that builds this plugin
- `.claude/skills/plugin-structure/` — Claude Code plugin layout reference (installed from skills.sh)
- `.claude-plugin/plugin.json` — the manifest; the plugin loads with `--plugin-dir`
- `skills/dgf-doctor/` — the walking-skeleton slice: `SKILL.md` plus `scripts/doctor.py`,
  which exercises auto-discovery, `${CLAUDE_PLUGIN_ROOT}`, the exit-code contract and the
  `dgf-gate-result` block without needing any DGF facts. It also blocks on a dangling
  `${CLAUDE_PLUGIN_ROOT}/…` path and on frontmatter that YAML would read differently
- `skills/dgf`, `dgf-plan`, `dgf-implement`, `dgf-verify`, `dgf-commit` — the pipeline spine:
  set up a workspaces root, plan (fast, full, ultra), execute task by task, gate the change,
  commit by workspace. Their references hold the config and DESCRIPTION templates, the plan
  and ultra formats, the implementation guide and the gate-result contract
  ([docs/pipeline.md](../docs/pipeline.md)). `/dgf-verify` and `/dgf-doctor` relay a gate block a
  script built; no prompt writes one ([ADR 0022](../docs/adr/0022-gate-block-contract-revised.md))
- `skills/dgf-fix`, `dgf-evolve` — the learning loop ([ADR 0024](../docs/adr/0024-learning-loop-revised.md)):
  `/dgf-fix` fixes a problem inside the active plan's scope — reproduced, scope decided by
  `check_change.py --skip-validators` before any edit, confirmed by the same check — and writes a
  patch (`references/PATCH-FORMAT.md`); `/dgf-evolve`, run only when asked, distils the new patches
  into skill-context overrides (`references/OVERRIDE-FORMAT.md`), an evolution log and the patch
  cursor. The ten skills that read an override run `check_override.py` first, and a refused
  override is never read. The verify gate suggests `/dgf-fix` for a finding the branch introduced
- `skills/dgf-component`, `dgf-process`, `dgf-model`, `dgf-audit` — the DGF-specific skills
  ([ADR 0023](../docs/adr/0023-dgf-specific-skills.md)): inspect and validate anywhere, write only
  inside the active plan's scope, each only the artifacts it owns (components and legacy forms and
  views; processes and workflows; entities). `/dgf-audit` is read-only: the root's health, and a
  file's blast radius — the processes that reach it in each application — with a `LIMIT:` line on
  every reach. `/dgf-process` and `/dgf-model` ship templates
- `knowledge/` — the DGF knowledge base: `README.md` (the stamping convention, and §7 the
  machine-read table contract), nine stamped facts files (`schema-families`,
  `component-catalogue`, `composition-specs`, `naming-conventions`, `json-reader`,
  `process-model`, and milestone 12's `data-model`, `reference-graph` and `permissions`) carrying
  fourteen machine-read tables the scripts load (`reference-edges`, the newest, is every reference
  a configuration file makes, how it resolves, and what the runtime does when its target is
  missing), and `schemas/` — the
  vendored set (69 JSON + 9 XSD + grammar reference + 3 standalone contracts, ~3.5 MB) with a
  `MANIFEST.md` of dialects and membership. Shipped, so it names no DGF repository path
- `provenance/` — **not shipped.** One ledger per knowledge file, recording the DGF files its
  facts were read from with a `sha256` each; the schema ledger adds the DGF commit and each
  vendored file's upstream and shipped digests
- `tools/` — **not shipped.** `check-dual-schema-docs.sh` (the repo-maintenance contract check,
  eight sections; section 8 runs the unit tests), `check_knowledge_stamps.py` (stamps, ledgers
  and vendored digests), `vendor_schemas.py` (re-vendors DGF's schema set, rewriting DGF paths
  on the way in), `run_known_good.py` with `known-good-exceptions.txt` (every validator over
  DGF's samples, each error excused with evidence — CLEAN at DGF `cccd4325b`), `check_drift.py`
  (the ledgers' digests against a DGF checkout — CLEAN, 10 ledgers, 323 sources) and
  `requirements.in`
- `scripts/` — shipped. The validators skills call: `validate_config.py` (family, schema
  read the runtime's way, parity), `resolve_components.py` (component types, component file
  references), `validate_process.py` (process structure and semantics, `CHANGE_STATE`
  targets), `validate_model.py` (the references an entity and a form make, resolved each loader's
  way, and a form's cells — the runner's fourth validator, so the gate checks the model) and
  `route_means.py` (ADR 0010's order of means). The audit, `audit_root.py` (the whole root's
  health and a file's blast radius, from the reference graph `lib/graph.py` builds per
  application; never a gate). The spine's four:
  `locate_plan.py` (the root and the active plan), `inventory_root.py` (each workspace,
  counted), `check_plan.py` (every rule of the plan format, its Commit Plan included, and
  overlaps with other branches' plans) and `check_change.py` (a change against its plan, and new
  findings against the merge-base). The verify gate, `verify_gate.py`, which runs the plan
  and change checks in-process and prints one computed `dgf-gate-result` block. The loop's two,
  stdlib-only: `check_patches.py` (the patch format, and which patches are new against the
  cursor) and `check_override.py` (whether a skill may read its override). With them, their
  shared `lib/` — `plan.py`, `git.py`, `runner.py`, `baseline.py`, `gate_result.py` (the one
  builder of every gate block), `patches.py`, `overrides.py`, `model.py`, `edges.py`, `graph.py`
  and `roles.py` among its modules — and
  `requirements.txt`: `lxml` 6.1.3 and
  `jsonschema` 4.25.1, exact pins with hashes, Python 3.9 floor
- `tests/` — **not shipped.** The `unittest` suite, unit fixtures, the 82-case known-bad
  corpus (one per blocking finding and exit-3 path), and `test_skill_contracts.py`, which fails
  when a skill quotes a finding code or passes a flag no script has, and holds the override
  readers and writer to the limit
- `docs/adr/` — 25 decision records, 0001–0025; the index is `docs/adr/README.md`
- `.mcp.json` (dgf-mcp only), `.ai-factory/config.yaml`

Not yet created: `/dgf-scaffold`, `agents/` and the marketplace entry.

## Tech Stack

- **Primary medium:** Markdown — skills are written prompt-as-program (numbered steps,
  explicit gates, mandatory outputs, STOP conditions), not prose descriptions
- **Scripting:** Node.js (`.mjs`) and Python 3.9+ for deterministic validators and helpers;
  the validators need `lxml` and `jsonschema`, hash-pinned in `scripts/requirements.txt` and
  compiled from `tools/requirements.in` with `uv`
- **Packaging:** Claude Code plugin — `.claude-plugin/plugin.json` + marketplace entry
- **Target framework (the domain being encoded):** DotGov Framework — .NET 10 / Angular 19
- **Build system:** none. There is no compile step; the artifacts are Markdown and scripts
- **Version control:** git, Azure DevOps (`dev.azure.com/dotgov/Core/dotgov-claude-plugins`), base branch `main`

## Target Framework Facts (verified)

Verified against `~/workspaces/dotgov/_DotGovFramework/DotGovFramework`. These
supersede the `[assume]` flags in Part 2 of the blueprint.

| Fact | Evidence |
|---|---|
| DGF is a **Component-Hosted Pluggable Monolith**, not a BPMN engine | `AGENTS.md` project overview |
| .NET 10 (`net10.0`, nullable **disabled**), Angular 19.2 + NGXS, SQL Server + EF Core | `src/Directory.Build.props`, `AGENTS.md` |
| **34** component service registrations across 31 modules, each implementing `IComponentService<TSource>` — one of five disagreeing component counts (34 services / 67 `ComponentType` members / 56 lifecycle / 59 examples / 66 with schemas); `knowledge/component-catalogue.md` says which answers which question | the 34 `ComponentServiceProvider.RegisterComponentService(` call sites; `src/Components/DGF.Components.Shared/Contracts/IComponentService.cs` |
| One dispatcher for all UI requests | `src/DGF.API/Controllers/ComponentsController.cs` |
| Components **are statically enumerable** — a real validator is feasible | `ComponentServiceProvider` name→type registry + `RegisterComponentServices()` reflection scan |
| Consumer apps compose plugins **declaratively via XML/JSON specs** and the DataFetcher EventBase verb dispatcher | `AGENTS.md` project overview |
| DGF supports **two configuration formats** — modern JSON component config and legacy XML — because it still runs older systems | `docs/wiki/AI-Authoring/format-coverage.md` |
| Modern JSON schemas: generated from `IComponentConfiguration` classes, committed and MCP-served | `src/Tools/dgf-mcp/Schemas/Json/` (69 files), `Schemas/Json/README.md` |
| Legacy XML schemas: 9 XSDs plus an auto-generated grammar reference | `src/Tools/dgf-mcp/Schemas/XSD/`, `Schemas/XmlReference/form.reference.json` |
| The MCP validation surface is **split by family** | `list_available_{json,xsd}_schemas`, `validate_component_config` vs `validate_*_xml` |
| **Schema availability is not runtime parity** — `Workflow` and `ProcessFlow` have JSON schemas but the runtime reads only `_workflow.xml` / `process.xml` (the page itself says `_process.xml`; the loader opens `process.xml`) | `docs/wiki/AI-Authoring/format-coverage.md`; `ProcessManager.cs` |
| Current AI generation policy is **XML for all five legacy artifact types** (form, workflow, process, settings, view), dated Wave 1 | `docs/wiki/AI-Authoring/format-coverage.md` |
| `docs/schemas/` holds only 3 hand-authored standalone contracts, not the generated set | `componentValidator`, `dataFetcherConfiguration`, `eventBase` |
| Hosted DGF documentation MCP | `https://dgf-mcp.dotgov.uk/mcp` |
| Auth: JWT Bearer + OIDC (Azure AD + DGPass); tests: xUnit/FluentAssertions/Moq + Jest/Playwright | `AGENTS.md` tech stack |
| DGF version source of truth is **`1.1.11`**, set only under `Condition="'$(Configuration)' == 'ClientDebug'"` despite a comment claiming all configurations share it | `src/Directory.Build.props` L30-34 |
| **Nothing first-party version-stamps DGF knowledge** — no `version` on the XSDs, none in the generated JSON schemas, no compatibility matrix; release notes are the only version-aware surface | `Schemas/XSD/`, `Schemas/Json/`, `docs/wiki/Release-notes/` |
| Process verification is **asymmetric**: structure is headless and deterministic (one-line XSD wrappers; `DgfMcpServer.csproj` has zero `<ProjectReference>`), semantics are checked by nothing DGF ships (`process.xsd` has no `xs:key`/`xs:keyref`, process is excluded at `XmlCrossReferenceValidator.cs:94`, `DiagnosticCheckService`'s process branch is commented out) | verified 2026-09-21 — see [ADR 0014](../docs/adr/0014-process-verification-runtime-resolution.md) |
| A process **cannot be executed headlessly** — stepping one needs a case record and therefore the database | `DGF.OM/Process/StateProcess/InstanceHandler.cs` `GetProcessMapAsync` |
| Workspaces inherit from a **base workspace** (`webasm`): `FmPath` resolves in the selected workspace, `FmBasePath` in the base, so a base artifact is live in every application | `src/Core/DGF.Kernel/WorkspaceSettings.cs` |
| Neither Python's nor Node's standard library validates XSD or JSON Schema, and a plugin cannot install its own dependencies — so validators run on Python with `lxml` + `jsonschema`, installed by the user and detected as missing (exit `3`). `lxml` bundles its own libxml2 (2.14.6), not the system `xmllint`'s | verified 2026-09-24 — see [ADR 0015](../docs/adr/0015-validator-runtime-and-json-reader.md) |
| Modern components are JSON files under `<workspace>/FM/_COMPONENTS/<Type>/<name>.json`, loaded only as `.json`; a `BASE:` prefix resolves the same path in `webasm` | `src/Components/DGF.Components.Shared/ComponentFileLoadService.cs:14-25` — see [ADR 0010](../docs/adr/0010-dgf-implement-scope.md) |
| The runtime reads component JSON with **System.Text.Json**, one options object: property names case-insensitive, comments skipped, `JsonStringEnumConverter` (enum names in any case), no `NumberHandling` (a number never reads from a string), and unknown properties silently ignored. The `type` key alone is exact-case | `src/DGF.API/ConfigureServices.cs:238-258`; `src/Core/DGF.Kernel/Utils/Serialization/JsonSerializationService.cs` — `knowledge/json-reader.md`, [ADR 0015](../docs/adr/0015-validator-runtime-and-json-reader.md) |
| `WorkflowManager.GetWorkPath` has **one branch per name form and no fallback**; existence is `File.Exists` on the built path, case-sensitive on Linux. A process `action`'s bare name is process-local | `src/Core/DGF.OM/Workflow/WorkflowManager.cs:15-40`; `StateProcessClient.cs` `ResolveUiSettings` — `knowledge/process-model.md` §2, [ADR 0014](../docs/adr/0014-process-verification-runtime-resolution.md) |
| The vendored XSDs **lag the runtime**: against DGF's samples, `process.xsd` fails 2/23 files and `workflow.xsd` 211/341. Only `process.xsd` has a runtime-divergence list; failures against the other legacy grammars are warnings until each has one | lxml 6.1.3 over `src/samples/workspaces`, 2026-09-24 — [ADR 0016](../docs/adr/0016-legacy-xsd-lag.md) |
| **`applibs*` folders are not workspaces.** They hold plugin assemblies (`ApplicationConfig.CustomAssembliesPath`, read by `AssemblyLoader`) — only `.dll` files, no `FM/` — and `WorkspaceSettings` never names them | `src/samples/workspaces/readme.md:12`; `src/Core/DGF.Kernel/Configuration/ApplicationConfig.cs:8`; `src/Core/DGF.Kernel/Extensions/AssemblyLoader.cs:13`; the five sample `applibs*` folders, 2026-09-25 — [ADR 0017](../docs/adr/0017-plan-file-format.md) §4 |
| **The UI loads exactly three custom files** — `assets/js/formhelper.js`, `assets/js/formshared.js`, `assets/styles/custom.css`. The shell ships a default of each; a deployment bind-mounts a workspace's file over it, outside the workspaces root. Nothing in the root makes the UI load a *new* file under `js/`, `FM/js/` or `css/`; a form's own `_form.js` is read beside its `_form.xml` | `src/DGF.UI/src/app/components/app/app.component.ts:191-207`; `src/DGF.UI/angular.json:26-33`; `src/samples/DGF.Compose/docker-compose.zims.yml:58-61`, `docker-compose.ecouncil.yml:62-65`; `src/Core/DGF.Domain/Data/Form/FormManager.cs:183-196`, 2026-09-25 — `knowledge/composition-specs.md` §5, [ADR 0017](../docs/adr/0017-plan-file-format.md) §3 |
| **Nothing in a workspaces root states the DGF version.** `sitemap.json`'s `version` is the site map's own; the UI's `version` is the container's build argument | grep of `src/samples/workspaces`; `src/DGF.UI/src/app/interfaces/app-settings.type.ts:9`; `src/DGF.UI/Dockerfile:1, 30, 36-42`, 2026-09-25 — [ADR 0019](../docs/adr/0019-declared-dgf-version.md) |
| **`webasm` may be mounted from another repository** than the application, so an estate's repository may not contain the base workspace | `src/samples/DGF.Compose/docker-compose.zims.yml:22-23` (zims from one repository, webasm from another) vs `docker-compose.ecouncil.yml:21`, 2026-09-25 — `knowledge/composition-specs.md` §1.2 |

**Correction to the blueprint:** Part 2 was written from a one-sentence description
that characterised DGF as having "workflows and BPMN-like processes". No BPMN engine
was found — that much is correct. But the inference drawn from it, that no formal
process specification exists, is wrong. DGF ships formal, machine-checkable process and
workflow grammars: `process.xsd` (root `Process` → `OnStart`, `States`) and
`workflow.xsd` (root `Workflow` → `Sequence`, `Input`), which are state-machine-shaped
rather than BPMN. `format-coverage.md` confirms both are the *live runtime formats* —
`process.xml` and `_workflow.xml` are XML-only today. `/dgf-process` was built on those two
XSDs (decided 2026-09-27, ADR 0023): `validate_process.py` checks a process against
`process.xsd` and against the runtime model (ADR 0014), and the skill authors both artifacts in
XML only.

**All seven blueprint open questions are now closed.** **#1** (spec format — both families
have committed schemas, and the DGF MCP exposes headless validators for each) and **#2**
(component enumeration — yes, statically enumerable) were answered from the repository. The
other five are recorded in [`docs/adr/`](../docs/adr/README.md): **#3** authoring entry point
and scope ([0004](../docs/adr/0004-authoring-entry-point.md)), **#7** default team rules
([0005](../docs/adr/0005-default-team-rules.md)), **#5** process verification
([0014](../docs/adr/0014-process-verification-runtime-resolution.md), superseding 0006, which
superseded 0002), **#6** version
gating ([0013](../docs/adr/0013-version-gating-provenance-ledger.md), superseding 0008 and
0003), and **#4**, decided on 2026-09-23 ([0010](../docs/adr/0010-dgf-implement-scope.md)):
`/dgf-implement` composes configuration. It uses modern JSON under `FM/_COMPONENTS/` first,
legacy XML only where no JSON alternative exists, and a little JavaScript or CSS only where
configuration cannot express the plan.

## Architecture Notes

Five ideas carried over from AI Factory unchanged — they are framework-independent:

1. **Single-writer artifact ownership.** Every artifact has exactly one owning command;
   everything else treats it as read-only input.
2. **Planner/executor split.** `index.md` + phase-file bundles; checkboxes live only in
   `index.md`. A strong model writes the bundle, a cheap model executes it, and the
   executor is forbidden from re-deciding architecture.
3. **Machine-readable quality gates.** A final fenced `dgf-gate-result` JSON block with
   `schema_version: 1` and last-block-wins parsing, keeping compatibility with the
   AI Factory contract.
4. **Worktree-isolated parallel workers** under a coordinator.
5. **The learning loop:** fix → patch → evolve → skill-context override.

What is genuinely new: deterministic validators. Anything a script can decide must never
be left to the model — component resolution, binding completeness and spec
well-formedness are all statically checkable against the shipped JSON Schemas and XSDs.
This is the highest-leverage deviation from AI Factory, which has almost no deterministic
validators.

Such a validator must get two things right. It must **dual-dispatch**: a JSON-only
validator generates false negatives on every legacy XML configuration. And it must be
**parity-aware**: a validator that reports success because a `Workflow` config matched
`WorkflowConfiguration.schema.json` generates a false positive, because the runtime reads
only `_workflow.xml`. See [`docs/dgf-schemas.md`](../docs/dgf-schemas.md).
`scripts/validate_config.py` does both, and reads JSON the way the runtime does
([ADR 0015](../docs/adr/0015-validator-runtime-and-json-reader.md)).

Artifact root is `.dgf-factory/`, mirroring `.ai-factory/`.

## Architecture

See [.ai-factory/ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture guidelines —
folder structure, dependency rules, communication mechanisms and anti-patterns.

Pattern: **Structured Modules (Vertical Slices)** — one skill is one self-contained
slice, with shared DGF facts in `knowledge/` and cross-slice validators in `scripts/`.
Maintainer material — `tools/` and `provenance/` — sits beside the slices and is never
shipped.
Expressed in Claude Code plugin folder names, because auto-discovery only loads
components from the plugin's mandated paths.

## Delivery Model (decided)

`dgf-factory` is an **independent Claude Code plugin** in the `dotgov` marketplace, and its
pipeline architecture **derives from AI Factory 2.18.1** — a derivation, not a dependency:
nothing at runtime requires AI Factory to be installed.

It takes no dependency on any other DGF agent-tooling effort, shares no artifacts with one,
and is under no obligation to track another repository's ADR series. The overlap with prior
work was measured on 2026-09-21 and deliberately set aside.

Decision and its full consequences — including what this costs and what would reverse it —
in [ADR 0001](../docs/adr/0001-independent-plugin-with-ai-factory-derived-architecture.md).

## Non-Functional Requirements

- **Correctness of framework facts over pipeline polish.** The blueprint is explicit that
  wrong DGF facts are the main risk. Reference material must cite its source in the DGF
  repository or the DGF MCP, and must be dated and version-stamped.
- **Determinism first.** Prefer a validator script over a prompt instruction wherever a
  script can decide the question.
- **No fabricated framework detail.** Anything not verified against the DGF repository or
  the DGF MCP stays marked `[assume]` until confirmed.
- **Dual-schema completeness.** Any statement, prompt or script about component schemas
  covers both families — modern JSON and legacy XSD — or explicitly scopes itself to one
  and says why. Defaulting to JSON is the failure mode to design against.
- **Parity-aware claims.** Never state that a component is JSON-capable without citing its
  runtime column in `format-coverage.md`, shipped as `knowledge/schema-families.md` §6 (all 67
  rows, [ADR 0011](../docs/adr/0011-schema-parity-authority.md)). A schema existing is not the
  runtime reading it.
- **Token budget.** Declaring playwright and chrome-devtools costs roughly 12,000 tokens of
  tool schema per session, so browser MCP servers are not declared in this project. This is
  also why browser-driven checks stay out of the gates — see
  [ADR 0014](../docs/adr/0014-process-verification-runtime-resolution.md) §5.
- **Line endings.** LF enforced repo-wide via `.gitattributes` — CRLF breaks shebangs and
  heredocs in plugin scripts.
- **Portability.** Intra-plugin paths use `${CLAUDE_PLUGIN_ROOT}`, never absolute paths.
- **No DGF repository paths in shipped files.** A developer's install has no DGF checkout,
  so nothing under `skills/`, `agents/`, `commands/`, `scripts/`, `knowledge/` or
  `.claude-plugin/` names a path into it. Shipped files cite the knowledge base, a DGF docs
  MCP call or a DGF type name; paths and digests live in `provenance/`. `doctor.py` blocks
  on a violation — see [ADR 0012](../docs/adr/0012-no-dgf-paths-in-shipped-files.md).
