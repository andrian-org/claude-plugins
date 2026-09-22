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

Setup stage. The repository currently contains:

- `README.md` + `docs/` — landing page and documentation set
- `docs/blueprint.md` — the design document (Part 1 teardown, Part 2 DGF mapping)
- `.claude/skills/aif-*` + `.claude/agents/*` — a full AI Factory 2.18.1 install, used as
  the working reference implementation and as the pipeline that builds this plugin
- `.claude/skills/plugin-structure/` — Claude Code plugin layout reference (installed from skills.sh)
- `.claude-plugin/plugin.json` — the manifest; the plugin loads with `--plugin-dir`
- `skills/dgf-doctor/` — the walking-skeleton slice: `SKILL.md` plus `scripts/doctor.py`,
  which exercises auto-discovery, `${CLAUDE_PLUGIN_ROOT}`, the exit-code contract and the
  `dgf-gate-result` block without needing any DGF facts
- `scripts/check-dual-schema-docs.sh` — the repo-maintenance contract check
- `.mcp.json` (dgf-mcp only), `.ai-factory/config.yaml`

Not yet created: the rest of the `dgf-*` skill corpus, the DGF knowledge references,
the deterministic dual-schema validators, and the marketplace entry.

## Tech Stack

- **Primary medium:** Markdown — skills are written prompt-as-program (numbered steps,
  explicit gates, mandatory outputs, STOP conditions), not prose descriptions
- **Scripting:** Node.js (`.mjs`) and Python 3 for deterministic validators and helpers
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
| ~40 component plugins, each implementing `IComponentService<TSource>` | `src/Components/DGF.Components.Shared/Contracts/IComponentService.cs` |
| One dispatcher for all UI requests | `src/DGF.API/Controllers/ComponentsController.cs` |
| Components **are statically enumerable** — a real validator is feasible | `ComponentServiceProvider` name→type registry + `RegisterComponentServices()` reflection scan |
| Consumer apps compose plugins **declaratively via XML/JSON specs** and the DataFetcher EventBase verb dispatcher | `AGENTS.md` project overview |
| DGF supports **two configuration formats** — modern JSON component config and legacy XML — because it still runs older systems | `docs/wiki/AI-Authoring/format-coverage.md` |
| Modern JSON schemas: generated from `IComponentConfiguration` classes, committed and MCP-served | `src/Tools/dgf-mcp/Schemas/Json/` (69 files), `Schemas/Json/README.md` |
| Legacy XML schemas: 9 XSDs plus an auto-generated grammar reference | `src/Tools/dgf-mcp/Schemas/XSD/`, `Schemas/XmlReference/form.reference.json` |
| The MCP validation surface is **split by family** | `list_available_{json,xsd}_schemas`, `validate_component_config` vs `validate_*_xml` |
| **Schema availability is not runtime parity** — `Workflow` and `ProcessFlow` have JSON schemas but the runtime reads only `_workflow.xml` / `_process.xml` | `docs/wiki/AI-Authoring/format-coverage.md` |
| Current AI generation policy is **XML for all five legacy artifact types** (form, workflow, process, settings, view), dated Wave 1 | `docs/wiki/AI-Authoring/format-coverage.md` |
| `docs/schemas/` holds only 3 hand-authored standalone contracts, not the generated set | `componentValidator`, `dataFetcherConfiguration`, `eventBase` |
| Hosted DGF documentation MCP | `https://dgf-mcp.dotgov.uk/mcp` |
| Auth: JWT Bearer + OIDC (Azure AD + DGPass); tests: xUnit/FluentAssertions/Moq + Jest/Playwright | `AGENTS.md` tech stack |
| DGF version source of truth is **`1.1.11`**, set only under `Condition="'$(Configuration)' == 'ClientDebug'"` despite a comment claiming all configurations share it | `src/Directory.Build.props` L30-34 |
| **Nothing first-party version-stamps DGF knowledge** — no `version` on the XSDs, none in the generated JSON schemas, no compatibility matrix; release notes are the only version-aware surface | `Schemas/XSD/`, `Schemas/Json/`, `docs/wiki/Release-notes/` |
| Process verification is **asymmetric**: structure is headless and deterministic (one-line XSD wrappers; `DgfMcpServer.csproj` has zero `<ProjectReference>`), semantics are checked by nothing DGF ships (`process.xsd` has no `xs:key`/`xs:keyref`, process is excluded at `XmlCrossReferenceValidator.cs:94`, `DiagnosticCheckService`'s process branch is commented out) | verified 2026-09-21 — see [ADR 0002](../docs/adr/0002-process-verification.md) |
| A process **cannot be executed headlessly** — stepping one needs a case record and therefore the database | `DGF.OM/Process/StateProcess/InstanceHandler.cs` `GetProcessMapAsync` |
| Workspaces inherit from a **base workspace** (`webasm`): `FmPath` resolves in the selected workspace, `FmBasePath` in the base, so a base artifact is live in every application | `src/Core/DGF.Kernel/WorkspaceSettings.cs` |

**Correction to the blueprint:** Part 2 was written from a one-sentence description
that characterised DGF as having "workflows and BPMN-like processes". No BPMN engine
was found — that much is correct. But the inference drawn from it, that no formal
process specification exists, is wrong. DGF ships formal, machine-checkable process and
workflow grammars: `process.xsd` (root `Process` → `OnStart`, `States`) and
`workflow.xsd` (root `Workflow` → `Sequence`, `Input`), which are state-machine-shaped
rather than BPMN. `format-coverage.md` confirms both are the *live runtime formats* —
`_process.xml` and `_workflow.xml` are XML-only today. The proposed `/dgf-process` skill
should therefore be re-derived from those two XSDs, alongside `eventBase.schema.json`
and `dataFetcherConfiguration.schema.json`.

**All seven blueprint open questions are now closed.** **#1** (spec format — both families
have committed schemas, and the DGF MCP exposes headless validators for each) and **#2**
(component enumeration — yes, statically enumerable) were answered from the repository;
**#4** substantially so — DGF systems compose configuration rather than write code, and
today that configuration is XML for the five legacy artifact types. The remaining four were
decided on 2026-09-21 and recorded in [`docs/adr/`](../docs/adr/README.md): **#5** process
verification ([0002](../docs/adr/0002-process-verification.md)), **#6** version gating
([0003](../docs/adr/0003-version-gating.md)), **#3** authoring entry point and scope
([0004](../docs/adr/0004-authoring-entry-point.md)), **#7** default team rules
([0005](../docs/adr/0005-default-team-rules.md)).

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

Artifact root is `.dgf-factory/`, mirroring `.ai-factory/`.

## Architecture

See [.ai-factory/ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture guidelines —
folder structure, dependency rules, communication mechanisms and anti-patterns.

Pattern: **Structured Modules (Vertical Slices)** — one skill is one self-contained
slice, with shared DGF facts in `knowledge/` and cross-slice validators in `scripts/`.
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
  runtime column in `format-coverage.md`. A schema existing is not the runtime reading it.
- **Token budget.** Declaring playwright and chrome-devtools costs roughly 12,000 tokens of
  tool schema per session, so browser MCP servers are not declared in this project. This is
  also why browser-driven checks stay out of the gates — see
  [ADR 0002](../docs/adr/0002-process-verification.md) §4.
- **Line endings.** LF enforced repo-wide via `.gitattributes` — CRLF breaks shebangs and
  heredocs in plugin scripts.
- **Portability.** Intra-plugin paths use `${CLAUDE_PLUGIN_ROOT}`, never absolute paths.
