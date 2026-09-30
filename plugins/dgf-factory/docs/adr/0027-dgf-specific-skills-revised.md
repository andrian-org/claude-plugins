---
id: 0027
title: "The DGF-specific skills write only inside a plan's scope, check the model in the gate, and report blast radius from a reference graph resolved per application — and /dgf-scaffold creates an application from an empty folder"
status: accepted
date: 2026-09-29
deciders: [Andrian Mamei]
supersedes: [0023]
tags: [skills, scope, graph, model, scaffold]
---

# 0027 — The DGF-specific skills write only inside a plan's scope, check the model in the gate, and report blast radius from a reference graph resolved per application — and /dgf-scaffold creates an application from an empty folder

**Status: accepted** (2026-09-29, Andrian Mamei). This ADR restates [ADR 0023](0023-dgf-specific-skills.md) in
full, with its section numbers, and changes three things. It folds ADR 0023's two 2026-09-27 errata into the
text they corrected (listed under Context). It gives §1 and §2 one rule each, for a folder that has no root and
no plan. And it replaces §7, which said `/dgf-scaffold` stays blocked, with the scaffold's design. The decider
made the choices behind §7 on 2026-09-29, while `/dgf-scaffold` was planned
(`.ai-factory/plans/feature-dgf-scaffold.md`, decisions D2–D12): the command creates an application from scratch
in an empty folder, generates the database too, and carries no estate content. [ADR 0026](0026-authoring-entry-point-revised.md)
§2 is the decision that makes it possible; this ADR is its design. ADR 0023's other points stand as its
decider chose them on 2026-09-26 and 2026-09-27: a skill that writes works only inside the active plan's scope
(§1), `/dgf-model`'s check joins the gate (§3), blast radius is `/dgf-audit`'s report and not a gate (§5), and
roles are an inventory, not a check (§6). The rest was drawn from the evidence below and accepted with that
plan (`.ai-factory/plans/feature-dgf-specific-skills.md`, decisions D6–D20).

## Context

Read on **2026-09-26** and **2026-09-27** from this repository (`develop` at `b0be7f1`) and from DGF
(`cccd4325b`, 2026-09-26); the scaffold facts were read on **2026-09-29** and **2026-09-30** from
`feature/dgf-scaffold` and from DGF (`1d5999186`).

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
  "could not be located in first-party DGF", and decided the scaffold "drives a template". ADR 0023 §7 kept
  `/dgf-scaffold` blocked on identifying it. It was re-searched on 2026-09-27 and again on **2026-09-29**: no
  `.template.config` or `template.json`, no new-workspace, new-app or new-tenant script, no bootstrap page, and
  `spec-schema-examples/` holds only `.gitkeep`. [ADR 0026](0026-authoring-entry-point-revised.md) §2 therefore
  reverses ADR 0004 §2: the scaffold generates the application itself. The nearest evidence is that `dgf` is the
  reference application workspace (`src/samples/workspaces/readme.md`), and that it needs an
  `aspnet_Applications` row before the API starts (`src/samples/Database/readme.md:84-88`).
  `Dockerfile.workspace` packages an existing workspace; it creates none.

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
  into the workspace** (`src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs:19-69`). The generated file can
  itself fail: `GetXmlTemplate` reads the name of the first `Text` field that is not the key, a null reference
  when the table has none (`:43-69`, `:100-146`).
- **Dialogs.** `LookUpDialogManager` reads `_LOOKUP/<dialog>/_dialog.xml` from the selected application
  only, and a missing dialog throws "Lookup Dialog … not found" (`LookUpDialogManager.cs:13-28`, `:26`).
  An `extract` with a non-empty `table` loads table and view, and ignores `dialog`; only with no `table`
  is the dialog loaded (`ExtractProperties.cs:7-14`, `LookUpViewManager.cs:191-198`).
- **Grids.** `EditableGridManager.GetXmlFilePath` tests `BASE:` in any case and does not clean the table
  name itself, but every grid loads through `LoadAsync(tableName, gridName)`, which loads the table with
  `TableManager.LoadAsync` first and builds the grid path from the loaded table's already-cleaned name, so a
  grid resolves exactly as a lookup view does. A missing table throws; a grid folder with no file is copied
  from `default` when there is one, and otherwise a generated file is saved there
  (`src/Core/DGF.Domain/Data/EditableGrid/EditableGridManager.cs:10-40`, `:22-26`, `:50-53`, `:70-77`,
  `:88-92`, `:99-125`).
- **Forms.** A missing form is copied from `default`, or generated from the table's fields, and
  **written into the workspace** (`FormManager.CreateFromTemplateAsync`, `FormManager.cs:131-139`). A form
  folder with no `_form.xml` throws only when the table has a `default` form to copy (`:131-144`); with no
  `default`, a generated file is saved there. The generator throws on a field with no `uimask`
  (`FormManager.GetXmlTemplate`, `:55-120`). The table is loaded first, and throws. Every generator — the
  grid's too — pastes the names and titles it uses unescaped, so a value that leaves the file unparsable, such
  as a bare `&`, makes `SaveXml`'s parse throw.
- **Cells and bindings.** `FormCell(field, table)` sets `Settings`, and `IsEmptyCell => Settings == null`
  (`src/Core/DGF.Domain/Data/Form/FormCell.cs:168-180`); `DiagnosticCheckService` skips such a cell
  (`src/Core/DGF.Explorer/Services/DiagnosticCheckService.cs:734-741`). Only a cell with no `name` is the
  empty cell: a bound cell that names no field throws in `Form.AddFields` (`Form.cs:58-76`), and a form with
  no `tabs` element binds no cell at all. A `binding`'s `from` is a column of the host entity and its `to` a
  column of the extract's table (`SqlQueryBuilder.cs:603-604`): it names columns, not files.

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

### ADR 0023's errata, folded in

Both errata of 2026-09-27 are folded into the Context bullets they corrected, and §3 needs no change: its
rule — a reference blocks only where its loader throws — covers them unchanged.

- **First erratum** (grids, forms, cells): a grid resolves as a lookup view does, because it loads the table
  first; a form or grid folder with no file throws only when a `default` exists to copy; only a cell with no
  `name` is the empty cell. Source: `EditableGridManager.cs:22-26`, `:50-53`, `:88-92`; `FormManager.cs:131-144`;
  `Form.cs:58-76`, at DGF `cccd4325b`; found by `/aif-verify`.
- **Second erratum** (generated files and counts): the static-reach counts are `STATEPROCESS:` 172 and 44
  JSON `workflow` components, and the three generators can fail on a missing `Text` field, a missing `uimask`
  or an unescaped value. Source: a count over DGF's samples; `LookUpViewManager.cs:43-69`, `:100-146`;
  `FormManager.cs:55-120`, `:131-139`; `EditableGridManager.cs:99-125`, at DGF `cccd4325b`; found by
  `/aif-verify`.

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
`/dgf-scaffold` creates a new application from an empty folder, generating it from shipped templates and
checking what it generated; it writes nowhere else.**

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
- **In an empty folder there is no root and no plan, so the scaffold writes without either.** It is the one
  writer that needs neither: it refuses any folder that is not empty (§7), and every change after its first is
  brownfield work that returns to this section's rules.

### 2. The artifact partition

Each writing skill writes only the artifacts it owns, read from `route_means.py`'s route and the
`legacy-artifacts` row:

| Artifact | Owner |
|---|---|
| `process`, `workflow` (shared or process-local) | `/dgf-process` |
| `settings` | `/dgf-model` |
| every JSON component under `FM/_COMPONENTS/`, and `form`, `table-view`, `lookup-view`, `grid-form`, `options` | `/dgf-component` |
| every file of a new application, until `/dgf` sets its root up | `/dgf-scaffold` |

For an artifact it does not own, a writing skill **STOPs** and names the owner. The table is the
partition; no prose restates it differently. The last row ends when `/dgf` sets the root up: from then on
every file in it belongs to the row that owns its artifact.

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
  output names the narrowing in its checks ([ADR 0026](0026-authoring-entry-point-revised.md) §3).

### 6. Roles

- **Permissions are an inventory, not a check.** The audit lists every role name the root uses and where
  it is used, read from a machine-read `role-sources` table in `knowledge/permissions.md`.
- **It says plainly that nothing in the root declares roles**, which are database rows, so it checks no
  name. A name is listed exactly as the runtime tests it — split on `,`, untrimmed — so a stray space
  stays visible.

### 7. `/dgf-scaffold`

**`/dgf-scaffold` creates a new DGF application from an empty folder, and generates everything itself.** It
refuses a folder that is not empty. Two slice-local scripts decide what a script can decide; the model only
designs the application and asks. The application is generated from shipped templates and checked before it is
reported, and the new workspaces root is handed to `/dgf`.

**The reading of ADR 0010 this section rests on.** [ADR 0010](0010-dgf-implement-scope.md) is read as the scope
of `/dgf-plan` and `/dgf-implement`: they compose configuration and never plan or write C# or SQL, and that
stands. The scaffold's generator is a separate, template-only writer that writes only into an empty folder.
Read this way, ADR 0010 stands unchanged. If its closing sentence — "That work belongs to a general coding flow
outside this plugin" — is read as plugin-wide, this section is rejected and ADR 0010 must be superseded first.
A reviewer may reject the reading here.

#### 7.1 Greenfield only

- `design.py --empty-only` refuses a folder holding anything but `.git/` and `docs/application.json`
  (`SCAFFOLD_DIR_NOT_EMPTY`). Adding to an existing application is the pipeline's job.
- The skill therefore never reads or writes `.dgf-factory/`, runs no override check and reads no patches: there
  is no root.

#### 7.2 One design file, the generator's only input

- **`docs/application.json`** (`design_format: 1`) holds the whole application. The model writes it from the
  request and the survey. It holds:
  - the application's name and `dgf_version` (the `DGF.API` package version to target);
  - `instances[]` and `instance_model`;
  - `apis[]`, each with its `deployments[]` — one API process for one instance, with its authentication;
  - `auth` providers and `roles[]`;
  - `base` (`source`: a local path to a `webasm`; `supply`: `copy` or `mount`);
  - `modules[]` (§7.6) and `data_model` (§7.7);
  - `sources`: for every value, whether it came from `prompt`, `asked` or `default`.
- **It never holds an instance's `ApplicationId`.** `generate.py` derives it as a `uuid5` of the application
  and instance names, so a re-generation from the same design reproduces it.
- **It stays in `docs/`** as the record of what was generated: the generator, run from it into a new empty
  folder, reproduces the application.

#### 7.3 Two scripts

- **`design.py --folder <dir> [--empty-only]`** checks the design and prints what is open. It checks that the
  folder is empty, every name against its rule, every cross-reference, the data model, and every value against
  the knowledge tables. It prints one `SCAFFOLD_ASK` per open value, with its rule and its candidates, and one
  `DEFAULT: <key> = <value>` line per defaulted value. It exits `0` complete, `1` conflict, `2` questions
  remain, `3` unreadable.
- **`generate.py --folder <dir> [--dry-run | --check]`** refuses unless `design.py` exits `0`. `--dry-run`
  prints every target and writes nothing. Without a flag it renders into a staging directory inside the
  folder and moves the result into place only when everything has rendered. `--check` runs the
  post-generation check (§7.10).
- **Both are slice-local** (`skills/dgf-scaffold/scripts/`), since no other skill uses them. They load
  `scripts/lib/report.py` and `scripts/lib/knowledge.py` by path, as `doctor.py` does — those two modules and
  `gate_result.py` are the only lib modules with no relative import — and have their own argument parser, whose
  `error()` exits `3`, and their own exact-case helper over `os.scandir`. Their codes are registered in
  `report.CODES`, the single source of severity.
- **The template manifest is `skills/dgf-scaffold/templates/manifest.json`**, read by `generate.py` itself. It
  is not a machine-read markdown table: every `knowledge.TABLES` entry is loaded from `knowledge/` by
  `load_all()` and by the doctor, so a slice-local table would be a blocking `KNOWLEDGE_TABLE`.

#### 7.4 The solution layout

The layout is the plugin's own, with neutral names, mirroring the common shape of the surveyed applications
with DGF's samples as the evidence:

```text
<dir>/
├── <App>.slnx                     the API hosts and the database project
├── src/<Api>/                     one per API: a thin host on the DGF.API package calling BuildEServicesApi
│   ├── appsettings.json           shared settings, the chosen auth sections, every secret a ${VAR}
│   ├── appsettings.<Deployment>.json   only what differs: WorkspaceName, the auth sections, the ports
│   └── Dockerfile
├── database/<App>.Database/       SDK-style Microsoft.Build.Sql: the app's tables, an aspnet_Applications row per
│                                  instance and the app's AspNetRoles rows, all idempotent post-deployment scripts
├── workspaces/                    the workspaces root: the app workspace(s); webasm when supply = copy
├── docker/                        docker-compose.yml, ui/<Deployment>.json, .env.example
└── docs/                          README.md, architecture.md, data-model.md, configuration.md, application.json
```

- **No Helm and no pipeline.** The request names Docker, and DGF ships no consumer pipeline. Both are
  follow-ups written into `docs/README.md`.
- **What is never literal:** a secret, a host, a feed, a registry or an image tag. Each is a `${VAR}`,
  declared in `docker/.env.example` and `docs/configuration.md`.
- **A template holds only values that DGF pins** (the `solution-parts` table's `Verified values`) and only
  `auth-schemes` keys. Every other value a part needs is a placeholder.

#### 7.5 The workspaces and multi-tenancy

- **An instance is a `WorkspaceName` with its own `aspnet_Applications` row.** The framework partitions its
  rows by that row's id. There are two instance models: `shared-workspace`, where one app workspace is mounted
  under each instance's name with its own `_application-<instance>.sitemap` bind-mounted over
  `_application.sitemap`, and `own-workspace`, one workspace per instance. Isolation between instances is by
  the `ApplicationId` column alone; the generated docs say so.
- **Each workspace gets the minimum** the `workspace-minimum` table records: a `sitemap.json` with the landing
  route first (never `"/"`) and `/login` with a local login page, an `_application.sitemap`, the
  `Page/SiteMap/` pages, and a `_PROFILE` tree per router, in the `Members` group unless a role narrows it.
- **The base is `webasm`, always by that name.** `supply: copy` copies `base.source` into `workspaces/webasm`;
  `supply: mount` mounts it in compose, its path a `${VAR}`. The plugin never pins a base tag: the survey asks.
- **No generated file uses a `BASE:` reference.** Without a base in the root such a reference is an ERROR, and
  a copied base brings its own findings. The generated application is self-contained, whatever base is supplied.

#### 7.6 Workspace artefacts are patterns

Version 1 has three module patterns, rendered from the design:

- **`register`**: the entity's `settings.xml`, its default form and lookup view, a `DataSource`, a `DataTable`,
  a list `Page`, its route in `sitemap.json` and a `_PROFILE` node for its roles;
- **`service`**: a `register` plus a case process — draft, submitted, in review, approved or rejected — with a
  `_workflow.xml` per transition and a task per reviewing role;
- **`page`**: a content `Page` and its route.

Every entity gets its own default form and lookup view, so the runtime never falls back to generating one (§3's
generators throw on a field with no `uimask` or a table with no non-key `Text` field). Every legacy artifact is
XML ([ADR 0010](0010-dgf-implement-scope.md) §1). What falls outside the patterns — custom behaviour,
integrations, documents — is written into `docs/README.md` as work for `/dgf-plan` after `/dgf`, never
improvised.

#### 7.7 The data model and the SQL

- **`data_model.entities[]`** hold `name`, `key` and `fields[]`; each field has `name`, `type` (a runtime
  `FieldTypeEnum` member), `dbtype`, `size`, `required`, `unicode`, `precision`, `scale` and optionally
  `extract {entity, view}`.
- **`design.py` refuses** (`SCAFFOLD_MODEL_INVALID`) what `knowledge/data-model.md` says makes a table's load
  throw, a `type` or `dbtype` that is no row of its table, and `PrimaryKey` and `Checkboxlist` — the vendored
  `settings.xsd` lacks both, so every file would warn `XSD_LAGS_RUNTIME` ([ADR 0016](0016-legacy-xsd-lag.md)).
- **A column's SQL type comes from the `field-sql-types` table**, keyed on `dbtype` and derived from DGF's own
  86 pairs of `settings.xml` and table script. A `dbtype` with no evidence is `SCAFFOLD_SQL_TYPE_UNKNOWN`: a
  column type is never guessed. The same model renders the entity's `settings.xml` and its table script, so the
  two agree by construction.
- **SQL is written only from these templates.** This is the exception to §3's "never writes SQL", stated
  where it is made: a model skill on a live root still names a migration and writes none.

#### 7.8 Authentication is DGF's own

Cookie authentication is always on. The survey offers `dgpass` and `azuread` per deployment; each chosen
provider emits its `Authentication:<scheme>` section with the keys DGF's options class reads, every value a
`${VAR}`, and the login page's `authenticationMethods` lists the same providers. `roles[]` become `AspNetRoles`
seed rows per instance, sitemap `roles` and `_PROFILE` role groups, written exactly: the runtime splits on `,`
without trimming (§6).

#### 7.9 The survey

- **Before `design.py` runs**, if the request reads as two different applications the skill asks which one; if
  `docs/application.json` exists, the skill resumes it.
- **After it runs**, every `SCAFFOLD_ASK` becomes an `AskUserQuestion`, at most four per call, looping back to
  `design.py` for at most five rounds. It then STOPs, keeping the design, and a re-run in the same folder
  resumes it.
- **A default is never silent.** The confirm step relays every `DEFAULT:` line and `generate.py --dry-run`'s
  tree before anything is generated. The model computes neither.

#### 7.10 The post-generation check

`generate.py --check` decides whether the generated application is sound; the skill only relays it. In order,
and any failure exits `1`:

1. **Secrets.** Every value of a key matching `password|secret|key|token|connectionstring` is `${…}`
   (`SCAFFOLD_LITERAL_SECRET`), and every `${VAR}` used is declared (`SCAFFOLD_VAR_UNDECLARED`).
2. **Structure.** The files no validator reads — `_application.sitemap`, each `_application-<instance>.sitemap`,
   each `_tree.xml`, each profile node file — are well-formed with the root and required attributes the
   `workspace-minimum` table records (`SCAFFOLD_STRUCTURE_INVALID`).
3. **Routes.** Every `sitemap.json` route names a generated page, by exact case; `/login` exists with a login
   page, and the landing route is not `"/"` (`SCAFFOLD_ROUTE_UNRESOLVED`).
4. **Validators, generated files only.** `validate_config.py`, `resolve_components.py` and `validate_model.py`
   over the generated files, and `validate_process.py` only when the design has a process. Never `--all` over
   the root: a copied base's own findings are not the generator's. INFO and `NO_SCHEMA` on `sitemap.json`
   (which every site map gets) are allowed, and so is `BASE_WORKSPACE_ABSENT` when `supply: mount`; everything
   else a generated file causes is `SCAFFOLD_VALIDATION_FAILED`, the validator's own line quoted. A validator
   that cannot run (`DEPENDENCY_MISSING`) exits `3` with that code.

A failed check is a generator defect: the skill stops and quotes it, and never patches the output by hand.

#### 7.11 Codes

| Script | Exit | Codes |
|---|---|---|
| `design.py` | `1` | `SCAFFOLD_DIR_NOT_EMPTY`, `SCAFFOLD_NAME_INVALID`, `SCAFFOLD_OPTION_INVALID`, `SCAFFOLD_REFERENCE_INVALID`, `SCAFFOLD_MODEL_INVALID`, `SCAFFOLD_SQL_TYPE_UNKNOWN` |
| `design.py` | `2` | `SCAFFOLD_ASK` |
| `design.py` | `3` | `SCAFFOLD_DESIGN_UNREADABLE` |
| `generate.py` | `1` | `SCAFFOLD_TARGET_EXISTS`, `SCAFFOLD_LITERAL_SECRET`, `SCAFFOLD_VAR_UNDECLARED`, `SCAFFOLD_STRUCTURE_INVALID`, `SCAFFOLD_ROUTE_UNRESOLVED`, `SCAFFOLD_VALIDATION_FAILED` |
| `generate.py` | `3` | `SCAFFOLD_DESIGN_INCOMPLETE`, `SCAFFOLD_TEMPLATE_MISSING`, `SCAFFOLD_WRITE_FAILED`; and the validators' own `DEPENDENCY_MISSING`, relayed |

#### 7.12 Its limits

The scaffold builds no domain: no estate integration, no per-application module beyond the three patterns, no
documents, no reports. It generates nothing an estate's base supplies. The solution files pass no validator,
only the post-generation check and, where `dotnet` exists, one real build; the application does not run until
its `${VAR}`s are filled.

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
- **Keep `/dgf-scaffold` blocked** (ADR 0023 §7). Rejected by the decider on 2026-09-29: the blocker was a
  tool nobody could identify after three searches, and the request is to create the application.
- **A scaffold that writes into an existing root, as the other writers do.** Rejected (§7.1): adding is a
  plan task, held by the scope script and the gate; a scaffold there would bypass both.
- **One generator script, or the model rendering the files.** Rejected (§7.3): the checks are deterministic
  and the render must be reproducible from the design; `rules/base.md:147` leaves nothing a script can decide
  to the model.
- **The template manifest as a machine-read knowledge table.** Rejected (§7.3): every `knowledge.TABLES` entry
  is loaded by `load_all()` and the doctor, so a slice-local table would be a blocking `KNOWLEDGE_TABLE`.
- **Guess a column type for a `dbtype` with no evidence.** Rejected (§7.7): `SCAFFOLD_SQL_TYPE_UNKNOWN` says so
  and the design changes.

## Consequences

### Positive

- **The milestone closes.** `/dgf-scaffold` is built, and a new application starts from a generated, checked
  shape with none of the defects the surveyed applications share.
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
- **A writer of C#, SQL, compose and MSBuild** the plugin never wrote before, held to an empty folder and to
  shipped templates, and dependent on the reading of ADR 0010 in §7.
- **The templates can drift from DGF's samples** until the next `tools/check_drift.py` run, and the solution
  files pass no validator (§7.12).
- **The application does not run until its `${VAR}`s are filled.**
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
- `BASE:` references in generated files, once a base is in the root.
- `PrimaryKey` and `Checkboxlist` fields, once the vendored `settings.xsd` is re-vendored or an evidenced
  exception exists.
- Helm and pipelines; adding to an existing application (`/dgf-plan`); DGF's service spec as the `service`
  pattern's input.

## Errata

ADR 0023's two errata of 2026-09-27 are folded into Context ("ADR 0023's errata, folded in"), and are not repeated here.

- **2026-10-01** — §7 was written before the scaffold was built, and differs from it in five places. None
  changes what §7 decides. Source: the built scaffold (`feature/dgf-scaffold`), the plan's `## Results`, and
  `knowledge/application-layout.md` §3.1, §5 and §6.
  - §7.4 lists `docker/ui/<Deployment>.json`. The UI's settings are inline compose `configs` content instead, because
    a bind-mounted file is not interpolated by compose, and the stack gains `docker/traefik/dynamic.yml` for its
    certificate.
  - §7.7 lists a `unicode` field. There is none: `dbtype` `StringUnicode` selects `NVARCHAR` (55 of 55 fields in
    DGF's samples), and `String` selects `VARCHAR`.
  - §7.8 names the providers `dgpass` and `azuread`. They are `basic`, `dgpass` and `azure`, the shell's own login
    method names; the sections are `Authentication:Basic`, `Authentication:DGPassOIDC` and `Authentication:AzureOIDC`.
  - §7.8 says `roles[]` become `AspNetRoles` rows per instance. `AspNetRoles` has one unique index, on `NormalizedName`
    alone, and the framework seeds roles in code only when the table is empty, so each role is written once (the
    built-in roles included), under the first instance.
  - §7.5 and ADR 0026 leave the `ApplicationId` column's nullability open. The generated application tables declare it
    `NULL`: nothing in the runtime fills it, so `NOT NULL` would fail every insert.
  - Two things §7 did not foresee: the host does not start without its `Integrations` sections, so the generated settings
    carry them as placeholders; and a secret-named key must hold exactly one `${VAR}`, so the SQL and Redis connection
    strings are variables.
