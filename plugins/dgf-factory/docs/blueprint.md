[← DGF Schemas](dgf-schemas.md) · [Back to README](../README.md)

> **Note:** this page moved from `ARCHITECTURE-BLUEPRINT.md` in the plugin root.
> File paths in Part 2 are relative to the **plugin root** (`plugins/dgf-factory/`),
> not to this `docs/` directory.

# dgf-factory — Architecture Blueprint

Design notes for building a DGF-specific agent factory, modelled on [AI Factory](https://github.com/lee-to/ai-factory) (`lee-to/ai-factory`, branch `2.x`).

**Part 1** is a teardown of how AI Factory actually works — the reusable architecture.
**Part 2** maps that architecture onto DGF and lists what has to change.

File paths in Part 1 are relative to the `ai-factory` repo root. Paths in Part 2 are relative to this plugin directory.

---

# Part 1 — How AI Factory works

## The core idea

AI Factory is not an agent and not a model. It is a **prompt-and-artifact operating system** that sits on top of whatever coding agent you already use (Claude Code, Codex, Cursor, …). It does not try to make the model smarter at any single task — it forces *every* task through the same deterministic pipeline, and keeps the state of that pipeline **in files on disk rather than in the model's context window**.

That single decision explains almost every other design choice in the repo.

## Two layers

### Layer 1 — the CLI (`src/`, ~20 TypeScript files)

Zero AI at runtime. It is a build-and-install system: one canonical corpus of skills is compiled into each agent's native format through a transformer registry (`src/core/transformer.ts`, `src/core/transformers/`).

The agent registry in `src/core/agents.ts` is just a table — "where does this agent keep skills, subagents, MCP config, and what file extension does it want":

| agent | skillsDir | agentsDir | agent file ext | MCP config |
|---|---|---|---|---|
| claude | `.claude/skills` | `.claude/agents` | `.md` | `.mcp.json` |
| codex | `.codex/skills` | `.codex/agents` | `.toml` | n/a |
| cursor | `.cursor/skills` | — | — | `.cursor/mcp.json` |
| copilot | `.github/skills` | — | — | `.vscode/mcp.json` |

`src/core/installer.ts` tracks **ownership** — managed-skill receipts with `sourceHash` + `installedHash` per skill — so `ai-factory update` can refresh what it owns and detect what the user hand-edited. State lives in the project's `.ai-factory.json`. There is also an extension system (`src/core/extensions.ts`, `src/core/injections.ts`) that lets third parties add commands, prompt injections, MCP servers, and agents.

### Layer 2 — the skills (`skills/`, ~13.5k lines of Markdown)

This is where the actual intelligence lives, written as **prompt-as-program**: numbered steps, explicit gates, mandatory outputs, and "STOP and report" conditions. `skills/aif-implement/SKILL.md` is 1091 lines of a state machine, not a description. `skills/aif-plan/SKILL.md` is 991.

The shape of every skill file:

```markdown
---
name: aif-implement
description: <trigger phrases — this is what makes the skill fire>
argument-hint: "[...]"
allowed-tools: Read Glob Grep Write Bash(...) Skill AskUserQuestion
---

# <Title>

## Workflow
### Step 0 (pre): Detect Handoff Mode
### Step 0: Check Current State
### Step 0.1: Load Project Context & Past Experience
### Step 1: ...
## Execution Rules
### DO: / ### DON'T:
## Critical Rules
```

## The task-solving pipeline

```
/aif (setup, once)  →  DESCRIPTION.md + ARCHITECTURE.md + RULES.md + config.yaml
                                    │
  explore / grounded  →  plan  →  improve  →  implement  →  verify / review / security / rules  →  commit
                                    │                                                                │
                                    └──────────────── fix → patch → evolve ←──────────────────────────┘
```

Each stage writes a durable artifact the next stage reads. The plan file is literally the program counter: checkboxes are the source of truth, updated immediately after each task (`skills/aif-implement/SKILL.md`, Step 3.6). You can `/clear`, crash, or return three days later and resume exactly where you were.

The full skill set (30 skills):

| group | skills |
|---|---|
| setup | `aif`, `aif-architecture`, `aif-roadmap`, `aif-rules`, `aif-warmup` |
| discovery | `aif-explore`, `aif-grounded`, `aif-reference`, `aif-distillation` |
| build | `aif-plan`, `aif-improve`, `aif-implement`, `aif-loop` |
| quality | `aif-verify`, `aif-review`, `aif-security-checklist`, `aif-rules-check`, `aif-qa`, `aif-qa-check`, `aif-best-practices` |
| delivery | `aif-commit`, `aif-docs`, `aif-ci`, `aif-dockerize`, `aif-build-automation` |
| learning | `aif-fix`, `aif-evolve`, `aif-transfer`, `aif-skill-generator` |
| housekeeping | `aif-archive` |

## The five architectural ideas that actually matter

### 1. Externalized, single-writer state

Every artifact has exactly one owning command. Everything else treats it as read-only input.

| artifact | owner | others |
|---|---|---|
| `.ai-factory/DESCRIPTION.md` | `/aif` | `/aif-implement` may update only when implementation context actually changed |
| `.ai-factory/ARCHITECTURE.md` | `/aif-architecture` | `/aif-implement` may update structure notes |
| `.ai-factory/ROADMAP.md` | `/aif-roadmap` | `/aif-implement` may mark milestones with evidence |
| `RULES.md`, `rules/<area>.md` | `/aif-rules` | read-only elsewhere |
| `RESEARCH.md` / `research/<slug>/` | `/aif-explore` | read-only elsewhere |
| `PLAN.md`, `plans/<id>.md`, `plans/<id>/index.md` | `/aif-plan` | `/aif-improve` refines |
| `FIX_PLAN.md`, `patches/*.md` | `/aif-fix` | consumed by `/aif-evolve` |
| `skill-context/*` | `/aif-evolve` | overrides shipped skills |

Research snapshots carry a SHA256 so downstream skills detect drift and **warn** rather than silently applying newer research to an older plan. Plans embed a copy of the research they were built from — that copy, not the live file, is the committed requirements snapshot.

This is what makes multi-session, multi-agent work non-chaotic. Without single-writer ownership, two skills racing on `ARCHITECTURE.md` silently destroy each other's work.

### 2. Planner/executor model split (ultra mode)

`/aif-plan ultra` produces an indexed bundle:

```
.ai-factory/plans/feature-billing-ledger/
├── index.md                        ← manifest + ONLY progress ledger; carries <!-- aif:plan-mode:ultra -->
├── phase-01-ledger-domain.md       ← exact paths, symbols, ordered edits, interfaces,
├── phase-02-persistence-migration.md    data flow, errors, logging, tests, risks,
└── phase-03-service-integration.md      acceptance criteria, verification commands
```

A strong model writes the bundle. A cheap model executes it. Checkboxes live **only** in `index.md` — never duplicated in phase files — so there is exactly one progress ledger.

The critical rule: the executor is forbidden from re-deciding architecture. If a phase file conflicts with current code, it must **stop and report the drift**, not silently make the architectural choice ultra mode existed to pre-commit. Expensive thinking happens once; cheap execution happens many times.

### 3. Machine-readable quality gates

`/aif-verify`, `/aif-review`, `/aif-security-checklist` and `/aif-rules-check` keep their human-readable Markdown report, then append one final fenced block:

````
```aif-gate-result
{
  "schema_version": 1,
  "gate": "verify",
  "status": "fail",
  "blocking": true,
  "blockers": [
    { "id": "verify-task-1", "severity": "error", "file": "src/example.ts",
      "summary": "Required behavior is missing." }
  ],
  "affected_files": ["src/example.ts"],
  "suggested_next": { "command": "/aif-fix", "reason": "Blocking gaps remain." }
}
```
````

Orchestrators parse **only the last such block** instead of scraping prose. `suggested_next.command` comes from a fixed allowlist. This is what lets the whole system be driven headlessly — see the `aif-handoff` kanban integration and the `HANDOFF_MODE=1` branches throughout the skills.

### 4. Parallelism via worktree isolation

`subagents/claude/agents/implement-coordinator.md` builds a task dependency graph, then dispatches `implement-worker` agents concurrently — each with `isolation: worktree`, `maxTurns: 16`, exactly one task — then merges results and advances to the next dependency layer.

Constraint that shapes the design: **subagents cannot spawn subagents**. So the coordinator must run as a top-level session (`claude --agent implement-coordinator`), and workers run their quality checks inline via direct tool calls rather than delegating.

Quality checks are separate scoped "sidecar" agents: `review-sidecar`, `security-sidecar`, `rules-sidecar`, `best-practices-sidecar`, `docs-auditor`, `commit-preparer`. The Reflex Loop (`/aif-loop`) has its own agent family: `loop-orchestrator`, `loop-planner`, `loop-producer`, `loop-evaluator`, `loop-critic`, `loop-refiner` plus prep agents.

Codex gets the same agents as `.toml` — 8 of them, the subset that maps cleanly.

### 5. The learning loop — the real differentiator

```
/aif-fix → fixes bug → writes patch → /aif-evolve distills → skill-context → smarter next run
```

`/aif-fix` does not just fix a bug; it writes a structured patch to `.ai-factory/patches/YYYY-MM-DD-HH.mm.md`:

```markdown
# Null reference in UserProfile when user has no avatar
**Date:** … **Files:** … **Severity:** medium
## Problem / ## Root Cause / ## Solution / ## Prevention / ## Tags
```

`/aif-evolve` reads *new* patches incrementally via `evolutions/patch-cursor.json` and distils them into `.ai-factory/skill-context/<skill>/SKILL.md`. Those files are **project-level overrides that beat the shipped SKILL.md on conflict** — same precedence logic as nested CLAUDE.md. Every skill opens by loading its skill-context file and declaring that rule explicitly:

> When a skill-context rule conflicts with a general rule in this SKILL.md, **the skill-context rule wins**. Generating artifacts that violate skill-context rules is a bug.

It is prompt-level fine-tuning through the filesystem — no retraining, no vector DB. `/aif-transfer <other-project>` ports *verified* prevention rules from a sibling project without importing its patches or advancing its cursor.

## Supporting mechanics worth copying

- **Config as relocation layer.** `.ai-factory/config.yaml` (template: `skills/aif/references/config-template.yaml`) controls `language.{ui,artifacts,technical_terms}`, every artifact path, `workflow.plan_id_format` (`slug` | `sequential`), `git.*`, and named rule areas. Skills read it; only `/aif` and `/aif-rules area:<name>` write it, and reruns touch **managed keys only** so user comments survive.
- **Artifact traceability.** Optional YAML frontmatter (`id`, `type`, `status`, `owners`, `depends_on`, `affects`, `implements`, `verifies`, `documents`, `supersedes`) plus `ai-factory audit-artifacts` — a linter for broken references, duplicate ids, dependency cycles, and specs with no implementing/verifying artifact. `--strict` and `--json` for CI.
- **Security posture for external skills.** Two-level check before *any* skill from skills.sh is trusted: an automated `security-scan.py` prompt-injection scan (exit 0/1/2), then a semantic review — "does every instruction serve the skill's stated purpose?". Blocked skills are removed *and* purged from `skills-lock.json` so they cannot be resurrected. Built-in skills are explicitly out of scope of the blocking scan.
- **Session recovery.** `/aif-warmup` reloads DESCRIPTION / ARCHITECTURE / ROADMAP / RESEARCH / RULES + applicable AGENTS.md into a compact handoff. `/aif-implement` Step 0.0 is a dedicated resume path after `/clear`.
- **Reliability gate.** `/aif-grounded` is a separate skill whose only job is to force evidence-based answers and return "insufficient information" instead of guessing.
- **Archive lifecycle.** `/aif-archive` moves fully-checked plans to `archive/plans/`, stamps `archived: YYYY-MM-DD`, and excludes them from plan discovery so the working set stays small.

## Why it is stack-agnostic

Nothing in the pipeline encodes a language or framework. Stack knowledge is *derived* at setup into `DESCRIPTION.md` / `ARCHITECTURE.md` and *accumulated* into rules and patches. **The pipeline is the constant; project context is the variable.**

## The honest trade-off

Reliability rests entirely on instruction-following across ~13.5k lines of Markdown. There is no runtime enforcing that a skill actually ran its steps. The mitigations are the gates, the mandatory checkbox updates, and the "STOP, don't guess" rules. It is defense-in-depth against model drift, not a hard guarantee. The shell suite in `scripts/` tests the CLI's file mechanics and contract *shapes* — not the model's compliance with the prompts.

---

# Part 2 — Mapping onto DGF

> **Assumptions flag.** What follows is derived from one sentence of description: *DGF is a web framework built from many components, including workflows and BPMN-like processes, used to build whole systems from scratch.* Everything below marked **[assume]** needs to be confirmed or corrected against the real framework before it is written into a skill. Getting these facts wrong is the main risk to this build.

## What inverts: DGF is domain-specific, AI Factory is not

This is the fundamental difference and it changes the whole value proposition.

| | AI Factory | dgf-factory |
|---|---|---|
| framework knowledge | deliberately none | **the entire point** |
| where stack knowledge lives | derived at setup into DESCRIPTION.md | **shipped in the plugin** as references |
| what a plan step looks like | "create a User model" | "declare component X, bind it to process step Y" |
| verification | generic (compiles, tests pass) | **DGF-shaped** (process definition valid, components resolvable, bindings complete) |

AI Factory learns your project. dgf-factory should arrive already knowing DGF, and then learn your *system built with* DGF. Both loops run; the first one is pre-loaded.

Practical consequence: the biggest single asset in this plugin is not the pipeline — that is copyable — it is **`skills/*/references/*.md` containing accurate, versioned DGF knowledge**: component catalogue, process/BPMN element semantics, binding rules, naming conventions, the idioms that separate correct DGF from code that merely runs.

## What changes: delivery layer

AI Factory ships as an npm CLI that installs into 15+ agents. This is a **Claude Code plugin** in an existing marketplace. Layer 1 largely collapses:

| AI Factory | dgf-factory |
|---|---|
| `src/core/transformer.ts` + 5 transformers | **drop** — Claude Code only |
| `src/core/agents.ts` registry | **drop** — one target |
| `ai-factory init` wizard | **drop** — plugin install does it |
| `.ai-factory.json` managed-skill receipts | **drop** — the marketplace owns updates |
| `src/core/mcp.ts` MCP wiring | **keep as `.mcp.json`** if DGF has tooling worth exposing |
| skills corpus | **keep — this is the whole plugin** |
| subagents | **keep** — `.claude/agents/*.md`, ship as-is then specialize |
| extensions/injections | **out of scope** — there is no injection mechanism in a plugin, and this plugin ships its own skills rather than layering onto generic ones ([ADR 0001](adr/0001-independent-plugin-with-ai-factory-derived-architecture.md)) |

Proposed layout, consistent with `plugins/doc-coverage-audit/`:

```
plugins/dgf-factory/
├── .claude-plugin/plugin.json      ← name, version, author, license
├── skills/
│   ├── dgf/SKILL.md                ← setup
│   ├── dgf-plan/SKILL.md
│   ├── dgf-implement/SKILL.md
│   ├── …
│   └── dgf-component/
│       ├── SKILL.md
│       ├── references/             ← THE DGF KNOWLEDGE BASE
│       └── scripts/                ← deterministic validators
├── agents/                         ← coordinator, workers, sidecars
└── ARCHITECTURE-BLUEPRINT.md       ← this file
```

Then register it in `.claude-plugin/marketplace.json` alongside `doc-coverage-audit`.

## What stays: all five core ideas

Copy these unchanged — they are the architecture, and they are framework-independent:

1. Single-writer artifact ownership.
2. Planner/executor split with an `index.md` + phase-file bundle.
3. `dgf-gate-result` JSON blocks (same schema, renamed key).
4. Worktree-isolated parallel workers under a coordinator.
5. fix → patch → evolve → skill-context override.

Plus: config-as-relocation, warmup/resume, archive lifecycle, the grounded gate.

## What is genuinely new: process-aware artifacts

This is where dgf-factory can be *better* than AI Factory rather than merely a port. A BPMN-like process definition is not source code and not prose — it is a **formal, machine-checkable spec**. That makes several things possible that AI Factory cannot do:

- **The process model is a first-class planning artifact.** *(confirmed 2026-09-19)* `/dgf-plan` for a feature that touches a process should read the existing process definition, and a plan phase should reference process elements by id — not describe them in prose. The definitions are `_process.xml` and `_workflow.xml`, validated by `process.xsd` and `workflow.xsd`.
- **Deterministic verification.** Unlike "does this code look right", you can actually check: every task in the process has a handler, every gateway has exhaustive outgoing conditions, every referenced component exists, every form field binds to a real model attribute, no orphan/unreachable nodes. **Write these as scripts under `scripts/`, not as prompt instructions.** Anything a script can decide should never be left to the model — this is the single highest-leverage deviation from AI Factory, which has almost no deterministic validators.
- **Component-graph traceability.** AI Factory's `audit-artifacts` links Markdown docs. DGF's equivalent can link *real system objects*: process → steps → components → data model → permissions. A changed process definition has a computable blast radius.
- **"From scratch" as a supported entry point.** AI Factory always assumes an existing codebase. If DGF systems are commonly greenfield, `/dgf-plan` needs a scaffold mode where reconnaissance is replaced by a structured interview: what entities, what processes, what roles, what integrations. **[assume]** worth confirming how often greenfield is the real case.

## Proposed skill set

Start with the spine, then add DGF-specific skills. Do not port all 30 — port the ones that carry the pipeline.

**Phase 1 — the spine (port, adapt lightly):**

| skill | note |
|---|---|
| `/dgf` | setup; writes DESCRIPTION / config; detects DGF version, module layout, existing processes |
| `/dgf-plan` | fast / full / ultra, same three modes |
| `/dgf-implement` | the state machine; checkbox ledger |
| `/dgf-verify` | emits `dgf-gate-result` |
| `/dgf-commit` | conventional commits |
| `/dgf-fix` | writes patches |
| `/dgf-evolve` | distils patches into skill-context |

**Phase 2 — DGF-specific (the actual value):**

| skill | purpose |
|---|---|
| `/dgf-component` | scaffold / inspect / validate a component against the catalogue, in **both** schema families and parity-aware — *(corrected 2026-09-19)* |
| `/dgf-process` | author or modify a process; validate against `process.xsd` / `workflow.xsd` rather than a BPMN model — *(corrected 2026-09-19)* |
| `/dgf-model` | **[assume]** entities, relations, migrations |
| `/dgf-audit` | whole-system consistency: process ↔ component ↔ model ↔ permission graph |
| `/dgf-scaffold` | greenfield bootstrap — **drives the existing template/generator** and verifies its output, rather than emitting files. Stays in phase 3 / milestone 12; the estate is brownfield-dominant — *(decided 2026-09-21, [ADR 0004](adr/0004-authoring-entry-point.md))* |

**Phase 3 — quality and learning:** `/dgf-review`, `/dgf-rules`, `/dgf-rules-check`, `/dgf-qa`, `/dgf-docs`, `/dgf-explore`, `/dgf-grounded`, `/dgf-archive`.

## Artifact layout

Mirror `.ai-factory/` as `.dgf-factory/`, with process-aware additions:

```
.dgf-factory/
├── config.yaml
├── DESCRIPTION.md            ← what this system is, DGF version, module map
├── ARCHITECTURE.md           ← component topology + process inventory
├── ROADMAP.md
├── RULES.md  +  rules/
├── RESEARCH.md  |  research/<slug>/
├── plans/<id>/{index.md, phase-NN-*.md}
├── patches/                  ← DGF-specific gotchas accumulate here; this becomes gold
├── evolutions/
├── skill-context/
├── archive/
└── processes/                ← NEW: process-model snapshots + blast-radius maps  [assume]
```

## Gate schema

Same shape, renamed, with DGF-specific gates:

````
```dgf-gate-result
{
  "schema_version": 1,
  "gate": "verify" | "review" | "rules" | "process" | "components",
  "status": "pass" | "warn" | "fail",
  "blocking": true,
  "blockers": [ { "id": "...", "severity": "error", "file": "...", "schema_family": "json" | "xsd" | "both", "summary": "..." } ],
  "affected_files": [],
  "affected_processes": [],          // NEW
  "affected_components": [],         // NEW
  "suggested_next": { "command": "/dgf-fix", "reason": "..." }
}
```
````

Keep `schema_version: 1` and the last-block-wins parsing rule so anything built on the AI Factory contract can read these too.

*(added 2026-09-19)* `schema_family` says which family produced a finding. Without it a blocker from an XSD validation is indistinguishable from a JSON one, and the two have different fixes.

## Build order

1. **Write the DGF knowledge references first.** Component catalogue, process semantics, binding rules, naming conventions, common mistakes. Everything else depends on these, and no amount of pipeline quality compensates for wrong framework facts.
   > *(2026-09-19)* These must cover **both schema families** and the runtime-parity axis from the start. See [DGF Schemas](dgf-schemas.md).
2. **Write the deterministic validators next** (`scripts/`). Process well-formedness, component resolution, binding completeness. These are worth more than any prompt.
   > *(2026-09-19)* Each validator dual-dispatches on the resolved family and checks runtime parity before reporting success. Retrofitting a second family into a single-family validator is a rewrite, not an extension — build both in from the first commit.
3. **Port the spine** — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`. Lift the AI Factory SKILL.md structure wholesale and swap the domain content; the step numbering and gate discipline are the valuable part.
4. **Wire `dgf-gate-result`** into verify, then the rest.
5. **Add the learning loop** — `/dgf-fix` + `/dgf-evolve`. Ship these early even if crude: every DGF gotcha caught during development becomes a patch, and the patch corpus is what makes the plugin get better over time.
6. **Then the DGF-specific skills** — `/dgf-component`, `/dgf-process`, `/dgf-audit`.
7. **Then parallelism** — coordinator + workers. It is the flashiest part and the least load-bearing. Do not start here.

## Open questions to resolve before writing skills

These are the facts the skills will encode. Wrong answers are expensive to unwind.

> **All seven are now closed** *(2026-09-21)*. The question text below is left unchanged as the
> historical record of what was unknown; each carries an `ANSWERED` block linking the decision.
> The decisions themselves live in [`docs/adr/`](adr/README.md).

1. **Process definitions** — what format on disk (XML/JSON/DSL/DB)? Is there a CLI or library to validate one without running the app? That determines whether `/dgf-process` can have a real validator or only prompt heuristics.
   > **ANSWERED (2026-09-19).** XML on disk, validated by XSD: `process.xsd` (root `Process` → `OnStart`, `States`) and `workflow.xsd` (root `Workflow` → `Sequence`, `Input`). No app run is needed — the DGF MCP exposes headless validators for both families (`validate_process_xml`, `validate_workflow_xml`, `validate_component_config`, `validate_*_json`). `/dgf-process` can have a real validator. See [DGF Schemas](dgf-schemas.md).
2. **Component declaration** — how is a component registered and discovered? Can the set of valid components be enumerated statically?
   > **ANSWERED (2026-09-18).** Yes — `ComponentServiceProvider` holds a name→type registry populated by a `RegisterComponentServices()` reflection scan.
3. **Greenfield vs. brownfield** — is "build a system from scratch" the dominant case? If yes, `/dgf-scaffold` moves to phase 1.
   > **ANSWERED (2026-09-21).** No — **mostly brownfield**, so the conditional evaluates to no and `/dgf-scaffold` stays in phase 3 / milestone 12. When a new system does start it comes **from a template or generator**, never from nothing, so the scaffold skill drives that tool rather than emitting files. The unit of work is the **whole workspaces root** — every workspace plus the `webasm` base and the `applibs*` libraries — which is the only scope at which a base-workspace change can be verified against the applications that inherit it. See [ADR 0004](adr/0004-authoring-entry-point.md).
4. **Generated vs. hand-written** — how much of a DGF system is code the agent writes versus configuration it composes? If mostly configuration, "implement a task" means something quite different from AI Factory's assumption and `/dgf-implement` needs reshaping.
   > **SUBSTANTIALLY ANSWERED (2026-09-19).** Mostly configuration — and today that configuration is **XML** for the five legacy artifact types (form, workflow, process, settings, view). `format-coverage.md` records the Wave-1 policy: AI generates XML for all five regardless of partial JSON parity. `/dgf-implement` therefore composes and validates configuration far more than it writes code.
5. **Test story** — what does verification look like for a process? Is there a way to execute a process definition headlessly?
   > **ANSWERED (2026-09-21).** Asymmetric. **Structure** is deterministic and headless today — the MCP's process/workflow validators are one-line XSD wrappers over `XsdValidationService`, and `DgfMcpServer.csproj` has zero `<ProjectReference>`, so no engine build is needed. **Semantics** are checked by nothing DGF ships: `process.xsd` contains no `xs:key`/`xs:keyref`/`xs:unique`, so the grammar cannot verify a `Transition/@state` names a declared `State/@name`; `XmlCrossReferenceValidator.cs:94` excludes process outright; and `DiagnosticCheckService`'s process branch is commented out and DB-bound. **Execution is not headless** — stepping a process needs a case record and therefore the database. So this plugin's gates verify structure plus its own semantic checks, and make no claim about runtime behaviour. See [ADR 0002](adr/0002-process-verification.md).
6. **Versioning** — do DGF versions differ enough that references need version gates?
   > **ANSWERED (2026-09-21).** **Yes.** `RELEASE-1.1.15.md` §"Breaking Changes" is the proof: `expandAll` and `paging` were "accepted in configuration and then ignored", and now take effect — `"paging"` on an eager TreeTable moved from silently dropped to a hard configuration error. The same JSON validates against the same schema in 1.1.14 and 1.1.15 and is merely fatal in one, so schema validation cannot substitute for a version gate. The mechanism: **stamp every fact** (DGF version, read date, per-source SHA256), **range only behavioural facts**, never the structural majority. See [ADR 0003](adr/0003-version-gating.md).
7. **Team conventions** — which dotGov-specific rules should ship as defaults in `RULES.md` rather than being discovered per project?
   > **ANSWERED (2026-09-21).** Seven ship as defaults, each tagged with how it is enforced: XML-always for the five legacy artifact types (*script*), declarative behaviour only in `FM/` artifacts (*gate*), base-workspace edits need justification (*gate*), DGF-seam scope discipline (*prompt-only*), plus auth, test stack and workspace layout as shipped stack facts. Nothing was rejected as project-specific, which the ADR records as a weak rather than a clean result. `RULES.md` itself stays owned by `/dgf-rules`. See [ADR 0005](adr/0005-default-team-rules.md).

## References

- AI Factory repo: `lee-to/ai-factory` (branch `2.x`), and its `docs/` — `workflow.md`, `plan-files.md`, `quality-gates.md`, `config-reference.md`, `evolve.md`, `subagents.md`, `extensions.md`, `security.md`.
- Local checkout used for this teardown: `/Users/andrianmamei/workspaces/open-source/lee-to/ai-factory`
- Sibling plugin for layout conventions: `plugins/doc-coverage-audit/`
- A full AI Factory install to read as a worked example: `plugins/claude-plugin-creator/.claude/`

---

## See Also

- [Architecture Decision Records](adr/README.md) — the decisions that closed the open questions above
- [DGF Knowledge Sourcing](dgf-knowledge.md) — how the facts this blueprint depends on get verified and version-stamped
- [DGF Schemas](dgf-schemas.md) — the two schema families, and the corrections dated 2026-09-19 above
- [Architecture](architecture.md) — the slice structure and dependency rules that came out of this design
- [Skill Authoring](skill-authoring.md) — how the pipeline described in Part 1 is actually written
