---
id: 0023
title: "The DGF-specific skills write only inside a plan's scope, check the model in the gate, and report blast radius from a reference graph resolved per application"
status: superseded-by-0027
date: 2026-09-29
deciders: [Andrian Mamei]
supersedes: []
tags: [skills, scope, graph, model]
---

# 0023 — The DGF-specific skills write only inside a plan's scope, check the model in the gate, and report blast radius from a reference graph resolved per application

**Status: accepted** (2026-09-27, Andrian Mamei). The decider chose five points on 2026-09-26 and
2026-09-27, while roadmap milestone 12 ("DGF-Specific Skills") was planned: `/dgf-scaffold` stays
blocked (§7), a skill that writes works only inside the active plan's scope (§1), `/dgf-model`'s check
joins the gate (§3), blast radius is `/dgf-audit`'s report and not a gate (§5), and roles are an
inventory, not a check (§6). The other points were drawn from the evidence below with that plan
(`.ai-factory/plans/feature-dgf-specific-skills.md`, decisions D6–D20), and accepted with it. This ADR
decides what `/dgf-component`, `/dgf-process`, `/dgf-model` and `/dgf-audit` may write, which artifacts
each owns, what the model check blocks on, and how blast radius is computed and reported.

## Context

Read on **2026-09-26** and **2026-09-27** from this repository (`develop` at `b0be7f1`) and from DGF
(`cccd4325b`, 2026-09-26).

### The milestone, and what earlier decisions left to it

- **The roadmap entry** is `.ai-factory/ROADMAP.md:20`. The blueprint's phase-2 table lists
  `/dgf-component`, `/dgf-process`, `/dgf-model` (marked `[assume]`), `/dgf-audit` and `/dgf-scaffold`
  (`docs/blueprint.md:297-301`), and its build order reads "6. Then the DGF-specific skills" (`:360`).
  The artifact layout marks `processes/` as "process-model snapshots + blast-radius maps `[assume]`"
  (`:322`), and the gate schema names `"process"` and `"components"` gate ids (`:330`), neither ever
  built. `docs/skill-authoring.md:24-33` already uses `dgf-component` as its frontmatter example.
- **Blast radius was left here.** [ADR 0022](0022-gate-block-contract-revised.md) §6 says the
  `affected_*` fields are "the change's own footprint … not its blast radius: which processes reach a
  changed shared workflow is `/dgf-audit`'s question" (`docs/adr/0022-gate-block-contract-revised.md:198-212`).
  Its Alternatives reject blast radius in `affected_processes` (`:275-276`), and its Negative records
  that "the footprint is not the blast radius" (`:312`). `scripts/verify_gate.py:35` and `footprint()`
  (`:362-382`) compute the changed set only, and `GATES` holds only `verify` and `doctor`
  (`scripts/lib/gate_result.py:34`).
- **No bootstrap template exists to drive.** [ADR 0004](0004-authoring-entry-point.md) §Context found it
  "could not be located in first-party DGF" (`docs/adr/0004-authoring-entry-point.md:54`), §2 decides the
  scaffold "drives a template" (`:78`), and the follow-up is to "Identify the bootstrap template"
  (`:145`). Re-searched on 2026-09-27: no `.template.config` or `template.json`, no new-workspace,
  new-app or new-tenant script, no bootstrap page. The nearest evidence is that `dgf` is the reference
  application workspace (`src/samples/workspaces/readme.md`), built by `tasks/default-workspace-plan.md`,
  and that it needs an `aspnet_Applications` row before the API starts
  (`src/samples/Database/readme.md:84-88`). `Dockerfile.workspace` packages an existing workspace; it
  creates none.

### Static reach — computable, per application, incomplete

- **From DGF's samples** (`src/samples/workspaces`), resolved with the engine's rules plus `SubWorkflow`
  closure: running `zims`, 126 workflows are reachable, 109 of them shared, and **49 shared workflows
  are reached by more than one process** — the widest, `webasm/AX.Notify`, by 11. Running `dgf`, 40
  shared workflows are reachable, 21 of them by more than one process.
- **Base processes are application-dependent.** 43 `WORKFLOW:/X` actions in `webasm` processes resolve
  in the running application's `_WORKFLOW`, and 22 of them dangle under `dgf`.
- **What a static walk cannot see:**
  - names assigned at run time: `_WORKFLOWNAME_` (7 uses in 4 files), `_FORMNAME_` (21 in 15) and
    `_TABLENAME_` (32 in 13). `_WORKFLOWNAME_` replaces a `SubWorkflow`'s target
    (`src/Core/DGF.DataViewer/Workflow/HumanWorkflow.cs:601-606`:
    `_WorkflowName = assignState.WorkflowName != "" ? assignState.WorkflowName : wfSubWorkflow.Settings.WorkflowName`,
    then `LoadWorkflowAsync(_WorkflowName, true)`), and `_TABLENAME_`/`_FORMNAME_` replace an `Invoke`'s
    table and form (`:504-506`). The name is evaluated from the step's **own** `Assign` child
    (`RoundTrip.cs:282-288`, `:355-362`, `:390`);
  - processes chosen from the database (`prc_WF_StartProcess.sql:87-125`; ProcessFlow's `ServiceID`);
  - open handlers (`OpenHandler.cs:28-36`);
  - entry points outside processes: `_PROFILE` (`WORKFLOW:` 262, `STATEPROCESS:` 172), `_form.xml` (73)
    and JSON `workflow` components (44).
- **A textual scan** finds 28 of 128 `webasm` and 39 of 188 `zims` shared workflows referenced nowhere —
  a heuristic, not proof of dead code.
- **The workflow edges** across 341 workflow files (`src/Core/DGF.Domain/Workflow/AbstractSequence.cs:22-38`):
  `SubWorkflow/Settings/@workflow` 309; `Invoke` with `control="Form"` 384 of 418; `XmlIsland`,
  `UpdateRecord` and `CreateRecord` `Settings/@table` 384, 256 and 4; `DataSourceStep/@DataSourceName`
  22; `StateProcess` 40. `Invoke` acts on a form only when `control`, upper-cased, is `FORM`
  (`HumanWorkflow.cs:486-496`). `UpdateRecord`/`CreateRecord` load through `FormManager.LoadAsync(table,
  form)` (`SequenceWorkflow.cs:470-471`), and `XmlIsland` loads its table only when its `FieldSet` is
  non-empty (`:62-67`).
- **What a missing target does.** A missing `SubWorkflow` target throws (`WorkflowManager.cs:68`); a
  missing `DataSourceStep` file throws `FileNotFoundException` (`DataSourceLoader.cs:20`), and an empty
  name is a no-op. A step's exception is rethrown unless the step has `hideExceptions="true"`
  (`SequenceWorkflow.cs:603-617`). A `StateProcess` step's missing process is caught per id and sets
  `_HasError_`; it is not rethrown (`:515-535`). `DataSourceLoader` reads
  `_COMPONENTS/DataSource/<name>.json`, `BASE:` in any case, subfolders allowed
  (`DataSourceLoader.cs:12-29`) — `workspace.component_location`'s rule exactly.
- **`Process/@table` is a database table name.** `InstanceHandler` passes it to SQL, `BASE:` stripped
  (`InstanceHandler.cs:274`, `:443`, `:471`); no loader opens `_DATA` for it.

### The data model — described in the root, its schema outside it

- **An entity** is `FM/_DATA/<E>/settings.xml`, read into `Table` (`[XmlRoot("entity")]`,
  `src/Core/DGF.Domain/Data/Table/Table.cs:9-115`), with fields (`Field.cs:56-145`) and a `datasource` of
  kind `DB` or `Provider` (`TableDataSource.cs:10-52`). Its relations are `extract` (N:1, a table and a
  view or dialog), `relation` (M:N, whose `table` is `DataSourceTable`, a database junction table:
  `RelationProperties.cs:14-15`), `slavegrid` (1:N, a table and a grid) and `binding` (cascades).
- **The samples:** `webasm` has 194 entities and 3255 fields, `zims` 223 and 5044, `dgf` 12 and 103.
  Across the three: `extract table` 1746, `relation` 14, `slavegrid` 146, `binding` 231.
- **The grammar:** `settings.xsd` declares `extract` `table`/`view` (required) and `dialog`, `binding`
  `from`/`to`, `slavegrid` `table`/`grid`, and `relation` `table`
  (`knowledge/schemas/xsd/settings.xsd:83-86`, `:158-160`, `:165-166`, `:189-190`, `:223`).
- **The database schema is not in the root.** It is framework-owned plus per-consumer SSDT/DACPAC
  projects outside the workspaces root (`src/samples/Database/readme.md:13-38`, `:73-76`). No EF
  migration touches application tables. `_DATACALLS` is read by nothing: no `WorkspaceSettings`
  constant and no loader. SQL is out of scope for every skill that writes
  (`docs/adr/0010-dgf-implement-scope.md:138`, [ADR 0010](0010-dgf-implement-scope.md) §3).

### The model's loaders — three rules for `BASE:`, and two behaviours for a missing target

- **Tables.** `TableManager.GetXmlWorkPath` calls `GetCleanTableName` — strip everything up to the last
  `.` (`ViewManagerBase.cs:14-19`) — **before** it tests `BASE:` with `InvariantCultureIgnoreCase`, so
  `BASE:dbo.X` resolves in the application. An unprefixed name is the selected application's only, with
  no fallback to `webasm`. `LoadAsync` **throws** "Settings file for the table … not found"
  (`src/Core/DGF.Domain/Data/Table/TableManager.cs:16-43`).
- **Lookup views.** `LookUpViewManager.LoadAsync(table, view)` reads an empty view as `default`, tries
  `_lookupviews/<view>/_view.xml`, and builds a missing view by `CreateFromTemplateAsync`, **saving it
  into the workspace** — no throw (`src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs:19-69`).
- **Dialogs.** `LookUpDialogManager` reads `_LOOKUP/<dialog>/_dialog.xml` from the selected application
  only, and a missing dialog throws "Lookup Dialog … not found" (`LookUpDialogManager.cs:13-28`, `:26`).
  An `extract` with a non-empty `table` loads table and view, and ignores `dialog`; only with no `table`
  is the dialog loaded (`ExtractProperties.cs:7-14`, `LookUpViewManager.cs:191-198`).
- **Grids.** `EditableGridManager.GetXmlFilePath` tests `BASE:` in any case and does **not** clean the
  table name. `LoadAsync` loads the table first, so a missing table throws, and a missing grid is copied
  from `default` or generated, and saved (`src/Core/DGF.Domain/Data/EditableGrid/EditableGridManager.cs:10-40`,
  `:70-77`).
- **Forms.** A missing form is copied from `default`, or generated from the table's fields, and
  **written into the workspace** (`FormManager.CreateFromTemplateAsync`, `FormManager.cs:131-139`). A
  form folder with no `_form.xml` throws (`:144`). The table is loaded first, and throws.
- **Cells and bindings.** `FormCell(field, table)` sets `Settings`, and `IsEmptyCell => Settings == null`
  (`src/Core/DGF.Domain/Data/Form/FormCell.cs:168-180`); `DiagnosticCheckService` skips such a cell
  (`src/Core/DGF.Explorer/Services/DiagnosticCheckService.cs:734-741`). A `binding`'s `from` is a column
  of the host entity and its `to` a column of the extract's table (`SqlQueryBuilder.cs:603-604`): it names
  columns, not files.

### Roles — database rows, named in the root as strings

- Roles are `AspNetRoles` rows seeded by `ApplicationDbContextSeed`
  (`src/Core/DGF.Infrastructure/Persistence/Seed/ApplicationDbContextSeed.cs:29-57`).
- The root names them in `_application.sitemap` `mapNode/@roles` and `@deny` (`ApplicationMapNode.cs:12-34`),
  at the workspace root beside `FM/` (`ApplicationMap.cs:8-9`); in `FM/_COMPONENTS/sitemap.json`
  `requireClaims`; in `_PROFILE/<Profile>/<RoleGroup>/` folders (`TreeManager.cs:23-36`, falling back to
  `Members`); and in process `Task/@role` (`Task.cs:7-16`) and `MultiTask/TaskGroup/@role`
  (`MultiTaskGroup.cs:19-22`). JSON components and `_form.xml` carry no role attribute.
- `SiteMapManager.CheckPermissions` splits `roles` and `deny` on `,` **with no trimming**, and `Members`
  counts only when the whole `roles` value is exactly `Members`, case-sensitive
  (`SiteMapManager.cs:614-629`). Nothing in the root declares a role.

### What this repository already has

- **`/dgf-fix` is the model for a skill that writes** (`skills/dgf-fix/SKILL.md`): Step 0 finds the root
  and checks the override; Step 0.2 finds the plan (`locate_plan.py`) and checks it (`check_plan.py`);
  Step 3 decides the scope with `check_change.py --changed M:… A:… --skip-validators`; Step 5 confirms
  with `check_change.py --base … --files …`. It relays exit tables, stops after at most 3 attempts, and
  never deletes. Its frontmatter pre-approves `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*)` and four
  MCP tools, and no git.
- **Routing is already a table.** `route_means.py <name>` prints `ROUTE: <family> <where> — <reason>` from
  `legacy-artifacts`, `component-folders`, `correspondence` and `parity`. `legacy-artifacts`
  (`knowledge/composition-specs.md:112-122`) names `process`, `workflow`, `form`, `settings`,
  `table-view`, `lookup-view`, `grid-form` and `options`, and `plan.artifact(rel)` names a file's
  artifact (`scripts/lib/plan.py:478-517`).
- **The resolvers exist, and their results are thrown away.** The `workspace` resolvers return a
  concrete target — `resolve_workflow_ref` and `resolve_workflow_name` (`scripts/lib/workspace.py:250-265`),
  `resolve_validation_flow` (`:268`), `resolve_process` (`:287`), `resolve_component_file` (`:311`), and
  the core `_resolve` (`:164-188`), which returns `Resolved`, `Unresolved`, `CaseOnly` or
  `AppDependent`. Their callers keep only the findings (`process_checks.workflow_references` and
  `change_state_targets`; `resolve_components.references`). The only reverse index,
  `process_checks.entry_states(root)` (`:187-206`), keeps states, not sources. Nothing resolves a
  `SubWorkflow`'s `workflow`, an `Invoke`/`XmlIsland`/`UpdateRecord`/`CreateRecord` `table` or `form`, a
  `DataSourceStep`, a form's cells, or `settings.xml`'s `extract` and `slavegrid`. `_ENTRY_CACHE` and
  `_DECLARED_CACHE` are module-level and never invalidated (`scripts/lib/process_checks.py:45-46`).
- **The runner decides what the gate validates.** `runner.VALIDATORS` is
  `("validate_process.py", "validate_config.py", "resolve_components.py")` (`scripts/lib/runner.py:26`),
  and `check_change.py`, `verify_gate.py` and `tools/run_known_good.py` all run through it. No test pins
  it.
- **From a `webasm` owner, `workspace._resolve` resolves a selected-scope reference in every application**
  (`scripts/lib/workspace.py:164-188`). Nothing fixes one selected application.
- **The knowledge tables' cell reader** strips one pair of backticks around a whole cell
  (`scripts/lib/knowledge.py:104-113`), so `` `A` `B` `` reads as `` A` `B ``.
- **The override header is a format.** `overrides.WRITTEN` (`scripts/lib/overrides.py:52`) is the exact
  line an override must carry, `(ADR 0021)` included; `_quoted()` refuses any other `> ` line.
- **The contract test** holds `READ_ONLY = ("dgf-doctor", "dgf-verify")` and
  `NO_GIT = READ_ONLY + ("dgf-evolve", "dgf-fix")` (`tests/test_skill_contracts.py:174-175`); `READ_ONLY`
  only builds `NO_GIT`, so nothing checks a read-only skill's tools. `EXPECTED_SLICES` lists
  `dgf-component`, `dgf-process` and `dgf-audit`, but not `dgf-model`
  (`skills/dgf-doctor/scripts/doctor.py:124-125`).

### Authoring policy

- "AI generates XML for all five legacy artifact types" (DGF's format-coverage page, shipped as
  `knowledge/composition-specs.md` §4), and `Workflow` and `ProcessFlow` JSON are ✗
  (`knowledge/schema-families.md` §6).
- The MCP's `build_form_xml` turns a FormSpec into `_form.xml`. The FormSpec carries no settings,
  workflow or process, and is to be followed by `validate_form_xml` and `validate_xml_cross_references`
  (DGF `docs/wiki/AI-Authoring/form-spec.md:207-221`). No DGF page is a process- or workflow-authoring
  guide; the closest are `Recipes/demo-eservice-recipes.md` and `Getting-Started/The-DGF-Workspace.md` §7.

## Decision

**`/dgf-component`, `/dgf-process` and `/dgf-model` inspect and validate anywhere, and write only
inside the active plan's scope, each only the artifacts it owns. `scripts/validate_model.py` checks the
references an entity and a form make, and joins the gate: a model reference blocks only where its loader
throws. `/dgf-audit` reports the root's health and a file's blast radius — the processes that reach it,
per application — from one reference graph resolved by the engine's rules; it is a report, never a gate.
`/dgf-scaffold` stays blocked.**

### 1. Authoring scope

- **A mode that only reads — inspect, validate — runs anywhere.** It needs a workspaces root, not a
  plan.
- **A mode that writes — scaffold, author, modify, add — works only inside the active plan**, as
  `/dgf-fix` does ([ADR 0024](0024-learning-loop-revised.md) §2):
  - `locate_plan.py` finds the plan and `check_plan.py` checks it; with no plan the skill **STOPs** and
    suggests `/dgf-plan`;
  - `check_change.py --changed … --skip-validators` decides the scope **before any write**, and a
    `CHANGE_*` error STOPs it;
  - after the write, the skill's validator and `check_change.py` confirm it.
- **A writing skill never ticks a checkbox** — `/dgf-implement` owns the ledger — **never deletes a
  file, and never converts an existing file's family.** A scaffold never overwrites: an existing file is
  an edit, and an edit belongs to a plan task.

### 2. The artifact partition

Each writing skill writes only the artifacts it owns, read from `route_means.py`'s route and the
`legacy-artifacts` row:

| Artifact | Owner |
|---|---|
| `process`, `workflow` (shared or process-local) | `/dgf-process` |
| `settings` | `/dgf-model` |
| every JSON component under `FM/_COMPONENTS/`, and `form`, `table-view`, `lookup-view`, `grid-form`, `options` | `/dgf-component` |

For an artifact it does not own, a writing skill **STOPs** and names the owner. The table is the
partition; no prose restates it differently.

### 3. The model, and `validate_model.py`

- **`scripts/validate_model.py` checks the references a `settings.xml` and a `_form.xml` make**, and
  joins `runner.VALIDATORS`. The verify gate, `check_change.py` and the known-good run pick it up with no
  further change, and the known-good run is settled to CLEAN before the milestone closes.
- **The severity rule: a model reference blocks only where its loader throws.** This is
  [ADR 0014](0014-process-verification-runtime-resolution.md)'s principle — resolve the way the runtime
  resolves, and block on what the runtime fails on — applied to the model:
  - an edge whose loader throws when its target is missing is `MODEL_REFERENCE_UNRESOLVED`, exit `1`;
  - an edge whose loader builds the missing file from a template and writes it into the workspace is
    `MODEL_REFERENCE_TEMPLATED`, exit `2`, and its message says the runtime will write that file;
  - an edge the runtime ignores is never reported, and one whose behaviour is unknown blocks nothing.
- **Which loader behaviour each edge has is a knowledge fact, not a decision.** It is the `When absent`
  column of the `reference-edges` table, `knowledge/reference-graph.md` §1, read from the loader that
  binds the edge and ledgered in `provenance/`. This ADR lists no loader's behaviour: a corrected cell
  changes the table and its ledger, not this decision.
- **Each loader keeps its own resolution rule** (`scripts/lib/model.py`, shared by the validator and the
  graph). The rules differ: workflows and processes match `BASE:` ordinally; a table — and every view,
  grid and form in its folder — is cleaned before `BASE:` is tested, in any case; and a dialog has no base
  path at all. One shared `BASE:` helper would get two of them wrong.
- **A migration is database work outside the root.** `/dgf-model` names the table and columns a change
  needs, and never writes SQL ([ADR 0010](0010-dgf-implement-scope.md) §3). A relation's `table` and an
  entity's `datasource` name database objects, so no check resolves them in the root.

### 4. The reference graph

- **One graph, in `scripts/lib/graph.py`.** A node is a configuration file, named by its root-relative
  path. An edge is a reference.
- **Each edge is resolved by the rule of the loader that reads it, never by name matching** —
  [ADR 0014](0014-process-verification-runtime-resolution.md) §3 extended past processes: the existing
  `workspace` resolvers for processes, workflows and component files, and `lib/model.py`'s for tables,
  forms, lookup views, dialogs and grids.
- **The graph is built per application**: that application plus `webasm`, with a `webasm` file's
  selected-scope reference resolved in that application. `workspace._resolve` gains an `app` keyword
  that fixes the selected application; without it, its behaviour is unchanged.
- **Which elements are edges is a machine-read table**, `reference-edges`, in
  `knowledge/reference-graph.md`. The table also says which edges reach walks (`Reach`) and which
  validator checks each edge (`Checked by`). No script keeps its own list of edge kinds, and a
  `Resolves as` or `Condition` value the library does not know is exit `3`, never a guess.
- **Reach follows workflow-bearing edges only.** A process reaches a file along its actions, its
  `validationFlow`, its `MultiTask` actions and `SubWorkflow` calls, then the forms those workflows
  invoke or record through, each form's entity, and the entities and data sources they name directly.
  A `StateProcess` step starts or moves another process, so reach stops there. An entity-to-entity edge
  is reported one level deep, as a direct referrer: followed transitively, it would spread through every
  lookup table in the estate. `Process/@table` is a database table name, and no edge.

### 5. The audit and blast radius

- **`scripts/audit_root.py` is the audit.** A whole-root mode reports the validators' counts, the graph's
  health, the shared workflows no traced reference reaches, and the role inventory. A reach mode reports,
  for given files or a branch's changed files, the processes that reach each one per application, and its
  direct referrers.
- **It never writes, and it emits no `dgf-gate-result` block.** It exits `0`, `1`, `2` or `3` like every
  validator. `/dgf-audit` relays it.
- **Blast radius is not a gate.** The verify gate, its `affected_processes` and
  [ADR 0022](0022-gate-block-contract-revised.md) are unchanged: `affected_*` stays the change's
  footprint (ADR 0022 §6), and `gate_result.GATES` gains no `audit` gate.
- **No stored process map.** Reach is computed on demand from the files. The blueprint's `[assume]`
  `.dgf-factory/processes/` directory is closed as not built: a stored map goes stale with the next
  commit.
- **An unresolved edge is reported once.** The audit reports one only for a `reference-edges` row whose
  `Checked by` is `—`; a row that names a validator is that validator's to report.
- **A narrowed audit says so.** `--app` narrows the audit to one application for speed only, and the
  output names the narrowing in its checks ([ADR 0004](0004-authoring-entry-point.md) §3).

### 6. Roles

- **Permissions are an inventory, not a check.** The audit lists every role name the root uses and where
  it is used, read from a machine-read `role-sources` table in `knowledge/permissions.md`.
- **It says plainly that nothing in the root declares roles**, which are database rows, so it checks no
  name. A name is listed exactly as the runtime tests it — split on `,`, untrimmed — so a stray space
  stays visible.

### 7. `/dgf-scaffold`

**Blocked.** No skill emits a new workspace. What unblocks it is ADR 0004's follow-up: the bootstrap tool,
where it lives, and the inputs it takes. Until then the roadmap milestone stays open with `/dgf-scaffold`
as its one unbuilt item, and ADR 0004 §2 stands: when it is built, it drives that tool rather than
emitting files.

### 8. What static reach cannot see

**A reach report never reads as complete.** Every reach report ends with a `LIMIT:` line naming what a
static walk cannot see: names assigned at run time (`_WORKFLOWNAME_`, `_FORMNAME_`, `_TABLENAME_`),
processes chosen from the database, open handlers, and entry points outside processes (`_PROFILE`,
sitemaps, `_form.xml` and view `WORKFLOW:` strings, JSON `workflow` components). An edge is `dynamic`
when **its own step's** `Assign` sets the name that replaces its target, and a chain through a dynamic
edge is flagged. `knowledge/reference-graph.md` §3 holds the list, each item with its runtime class. A
skill that relays a reach report never calls it complete.

## Alternatives considered

- **Read-only skills.** Put to the decider and rejected (§1): `/dgf-implement` and `/dgf-fix` already
  write inside a plan's scope, and a skill that can author a process but not write it hands the model a
  file to paste by hand, outside every check.
- **Model checks standalone, and deferring `/dgf-model`.** Put to the decider and rejected (§3): a
  removed field or a missing table would pass the gate, and the runtime throws on it at the first request.
- **Blast radius in the verify block, or an `audit` gate.** Put to the decider and rejected (§5). Both
  supersede ADR 0022, and consistency findings over a brownfield estate are mostly pre-existing: a gate
  would block every branch on defects it did not introduce, or need a second baseline to avoid it.
- **A role registry check.** Put to the decider and rejected (§6): no registry exists in the root, and a
  check against one the plugin invented would report every role as unknown.
- **A stored `processes/` map.** Rejected (§5): it goes stale with the next commit, and a stale map
  under-reports without saying so.
- **Name-matching the graph.** Rejected (§4): a name matches across workspaces and scopes the loader
  never searches, which is ADR 0014 §3's reason for resolving the engine's way.
- **One `BASE:` rule for every loader.** Rejected (§3): the loaders have three different rules, and one
  helper would get two of them wrong.
- **Transitive entity-to-entity reach.** Rejected (§4): it would spread through every lookup table, so
  every process would reach nearly every entity.

## Consequences

### Positive

- A change to a shared workflow names the processes to regression-test, per application — by hand,
  because a process cannot run headlessly (ADR 0014 §5).
- A removed field or a missing table blocks at the gate, where before the runtime found it.
- Each artifact has one writing skill.
- The role names an estate uses are visible in one list, stray spaces included.

### Negative

- **The graph mirrors engine code that can change.** `HumanWorkflow`, `TableManager`,
  `LookUpViewManager` and the rest are in provenance ledgers, so `tools/check_drift.py` catches a change —
  at the next maintainer run, not at the moment DGF changes.
- **Reach is incomplete** (§8), and a reader may still trust it too far. The `LIMIT:` line and the
  dynamic flag are the only defence.
- **Three more writers** beside `/dgf-implement` and `/dgf-fix`, held to the plan by the scope script, and
  to each other by the partition.
- **The known-good run has a new validator to settle**, over 1746 `extract` tables in the samples.
- **`/dgf-scaffold` is still blocked**, so the milestone stays open.
- **Four more skill descriptions load in every session**, and a whole-root audit parses every file in
  every application.

### Follow-ups

- `/dgf-plan` records reach for tasks that touch a shared workflow, as regression notes.
- The workflow edges no validator checks (`Checked by` `—`), where their loader throws, become blocking
  validator checks: this extends ADR 0014's deferred list.
- Trace entry points outside processes: `_PROFILE`, sitemaps, `_form.xml` and view `WORKFLOW:` strings,
  and JSON `workflow` components. `profile.xsd` does not compile, so this needs a grammar first.
- A role check, if an estate ever keeps its roles list in the root.
- `inventory_root.py` counts entities per workspace.
- `/dgf-scaffold`, once ADR 0004's template is identified.

## Errata

- **2026-09-27** — §3's "Each loader keeps its own resolution rule" said a table's name is cleaned before
  `BASE:` is tested and "a grid's is not"; it now names the three rules below. Context ("Grids") still
  says `EditableGridManager` does not clean the table name, as it was first read. It does not clean it
  itself, but every grid loads through `LoadAsync(tableName, gridName)`, which loads the table with
  `TableManager.LoadAsync` first and builds the grid path from the loaded table's already-cleaned name, so
  a grid resolves exactly as a lookup view does. The three rules that differ are: workflows and processes
  match `BASE:` ordinally; a table, and the views, grids and forms in its folder, is cleaned and then
  matches `BASE:` in any case; a dialog has no base path at all. The Alternative "One `BASE:` rule for
  every loader" stands on those three. Context's "Forms" bullet says
  a form folder with no `_form.xml` throws: it throws only when the table has a `default` form to copy,
  and a grid folder the same; with no `default`, a generated file is saved there. Context's "Cells and
  bindings" bullet reads as if a cell that names no field were tolerated: only a cell with no `name` is
  the empty cell, and a bound cell that names no field throws in `Form.AddFields` — which is why
  `MODEL_CELL_UNBOUND` is exit `1` under §3's own rule — while a form with no `tabs` element binds no cell
  at all. None of this changes what §3 decides; the facts are `knowledge/data-model.md` §3–§4 and
  `knowledge/reference-graph.md` §1. Source: `EditableGridManager.cs:22-26`, `:50-53`, `:88-92`;
  `FormManager.cs:131-144`; `Form.cs:58-76`, at DGF `cccd4325b`; found by `/aif-verify`.
- **2026-09-27** — Context's static-reach bullet counted `STATEPROCESS:` 165 in `_PROFILE` and 47 JSON
  `workflow` components; the samples hold 172 and 44, which `knowledge/reference-graph.md` §3 already
  states, so Context now says 172 and 44. Context's "Lookup views" bullet says a missing view is built
  "no throw", and its "Forms" bullet that a missing form is generated, as first read. The generated file
  can itself fail: `LookUpViewManager.GetXmlTemplate` reads the name of the first `Text` field that is not
  the key, a null reference when the table has none; `FormManager.GetXmlTemplate` throws on a field
  with no `uimask` when there is no `default` to copy; and every generator — the grid's too — pastes the
  names and titles it uses unescaped, so values that leave the file unparsable, such as a bare `&`, make
  `SaveXml`'s parse throw. §3's
  rule — a reference blocks only where its loader throws — covers all three unchanged, and so decides the
  same; the facts are `knowledge/data-model.md` §3.2, §3.4, §3.6 and §4. Source: a count over DGF's samples;
  `LookUpViewManager.cs:43-69`, `:100-146`; `FormManager.cs:55-120`, `:131-139`;
  `EditableGridManager.cs:99-125`, at DGF `cccd4325b`; found by `/aif-verify`.
