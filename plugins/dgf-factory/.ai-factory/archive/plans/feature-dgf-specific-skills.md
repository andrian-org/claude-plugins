---
archived: 2026-10-04
---
# Implementation Plan: DGF-Specific Skills

Branch: feature/dgf-specific-skills
Created: 2026-09-27

Base: `develop` at `b0be7f1`. `config.yaml` names `main` as `git.base_branch`, but `main` is 83 commits behind
`develop` and lacks milestones 6–11, which this plan builds on. The branch is cut from `develop` and merges back into
it, as milestones 9–11 did.

**This plan does not close the milestone.** It builds `/dgf-component`, `/dgf-process`, `/dgf-audit` and `/dgf-model`.
`/dgf-scaffold` stays blocked until its bootstrap template is identified (D1), so the roadmap entry stays open with
`/dgf-scaffold` as its one unbuilt item.

## Original Request

DGF-Specific Skills — /dgf-component, /dgf-process, /dgf-audit, then /dgf-model; /dgf-scaffold stays here (the estate is brownfield-dominant) and drives the existing bootstrap template rather than emitting files — blocked until that template is identified, since it is not in first-party DGF (ADR 0004). /dgf-audit also owns blast radius — the processes a changed shared workflow reaches — which the verify gate's affected_processes leaves out (ADR 0022 §6)

## Settings

- **Testing: yes.**
  - A stdlib `unittest` test for every new module, script, finding code, template and rule. Run from the plugin root
    with `python3 -m unittest discover -s tests -t .`, and prefer `.venv/bin/python` when it exists.
  - Every new blocking code, and every new exit-`3` path, gets a known-bad case under `tests/fixtures/known-bad/`.
  - Tests that need `git` skip through `helpers.have_git()`. Tests that need `lxml` or `jsonschema` skip through
    `helpers.have_dependencies()`.
  - A test that asserts an exact finding list must pass under an interpreter without either dependency
    (`.ai-factory/RULES.md`).
  - Every skill that STOPs on a script's exit code is walked through its own worked example against that script
    (`.ai-factory/RULES.md`, Task 17).
- **Logging: verbose.** There is no logging framework (`.ai-factory/rules/base.md` §Logging).
  - New code traces through `report.debug("<module>.<function>", message, key=value…)`. The trace goes to **stderr**
    under `--verbose`, `DEBUG=1` or `LOG_LEVEL=debug`.
  - Report lines go to stdout, and usage errors go through `report.fail()`.
  - Skills do not log; they relay script output.
- **Docs: yes.** A mandatory documentation checkpoint at completion (Task 18), routed through `/aif-docs`.
- **Decisions.** They are recorded in ADR 0023 and ADR 0024 (Tasks 1–2).
  - D1–D5 are the user's (Andrian Mamei, 2026-09-26/27).
  - D6–D20 are the planner's, taken from the evidence below. Reverse any of them at review.

  **The user's:**
  - **D1 — `/dgf-scaffold` stays blocked.** No task builds it. The bootstrap template is still unidentified, and a
    2026-09-27 search found no `dotnet new` template, no new-workspace script and no bootstrap page (E4). ADR 0023 §7
    records the blocker and what would unblock it. ADR 0004's follow-up stands.
  - **D2 — Authoring only inside the plan's scope.** Any mode that only reads (inspect, validate) runs anywhere. Any
    mode that writes (scaffold, author, modify, add) works only inside the active plan, as `/dgf-fix` does (E9):
    - `locate_plan.py` finds the plan, and `check_plan.py` checks it;
    - `check_change.py --changed … --skip-validators` decides the scope before any write;
    - the skill never ticks a checkbox — `/dgf-implement` owns the ledger — never deletes a file, and never converts an
      existing file's family.
  - **D3 — `/dgf-model` checks the model, and the check joins the gate.**
    - `scripts/validate_model.py` checks the references a `settings.xml` and a `_form.xml` make, and joins
      `runner.VALIDATORS`. The verify gate, `check_change.py` and the known-good run pick it up with no further change.
    - The known-good run is settled to CLEAN (Task 8).
    - A migration is reported as database work outside the root, never written (ADR 0010 §3, E5).
  - **D4 — Blast radius is `/dgf-audit`'s report, not a gate.**
    - A shared graph library and `scripts/audit_root.py` compute which processes reach a file, per application, over
      the whole root.
    - `/dgf-audit` relays the result and emits no `dgf-gate-result` block.
    - The verify gate, its `affected_processes` and ADR 0022 are unchanged (E2).
  - **D5 — Permissions are an inventory, not a check.**
    - The audit lists every role name the root uses and where it is used.
    - It says plainly that nothing in the root declares roles, which are database rows (E7), so it checks no name.

  **The planner's:**
  - **D6 — ADR 0023 decides the milestone.**
    - Sections: §1 authoring scope (D2); §2 the artifact partition (D8); §3 the model and `validate_model.py` (D3, D11,
      D12); §4 the reference graph (D9); §5 blast radius and the audit (D4, D10, D17); §6 roles (D5); §7 `/dgf-scaffold`
      (D1); §8 what static reach cannot see (D16).
    - ADR 0010, 0014, 0021 and 0022 each stand as they are. The next ADR supersedes 0021; nothing else changes an
      accepted decision.
  - **D7 — The four new skills read an override, so there are ten readers, and ADR 0024 supersedes ADR 0021 in full.**
    - Patches are DGF gotchas, and these four skills are where DGF gotchas bite. A skill that reads no override
      cannot learn.
    - ADR 0021 §5 says "the readers are six", and §6 says `/dgf-evolve` targets exactly those readers (E8). Growing the
      set changes what 0021 decides, so it is not an erratum (E13).
    - ADR 0024 restates 0021 with the same section numbers. Only §5's reader list and §6's targets change.
    - Live citations of ADR 0021 are repointed to 0024, as 0022's were in milestone 11. Historical mentions stay.
    - **The override header stays `(ADR 0021)`.** `overrides.WRITTEN` is an on-disk format that the check enforces
      exactly, not a citation (E17). Changing it would refuse every override an estate has committed. ADR 0024 §3
      records that the header's text is frozen.
    - This is the costliest planner decision (R1). If it is reversed, the four skills read no override, carry no
      `skill-context/` string, and Task 2 is dropped.
  - **D8 — The artifact partition is decided by one table, not by prose.** Each writing skill writes only the artifacts
    it owns, read from `route_means.py`'s route and the `legacy-artifacts` row (E11):

    | Artifact | Owner |
    |---|---|
    | `process`, `workflow` (shared or process-local) | `/dgf-process` |
    | `settings` | `/dgf-model` |
    | every JSON component under `FM/_COMPONENTS/`, and `form`, `table-view`, `lookup-view`, `grid-form`, `options` | `/dgf-component` |

    For an artifact it does not own, a writing skill **STOPs** and names the owner.
  - **D9 — One reference graph, in `scripts/lib/graph.py`, resolved the engine's way, per application.**
    - A node is a configuration file, named by its root-relative path. An edge is a reference.
    - Each edge is resolved by the rule of the loader that reads it, never by name matching: the existing `workspace`
      resolvers for processes, workflows and component files, and new `lib/model.py` resolvers for tables, forms,
      lookup views, dialogs, grids and data sources.
    - The graph is built for each application: that application plus `webasm`, with a `webasm` file's selected-scope
      reference resolved in that application. `workspace._resolve` gains an `app=None` keyword that fixes the selected
      application, passed through every resolver (E17). With `app=None`, behaviour is unchanged.
    - Which elements are edges is read from a new machine-read table, `reference-edges`, in
      `knowledge/reference-graph.md`. A `Resolves as` value the library does not know is exit `3`
      (`KNOWLEDGE_TABLE`), never a guess.
    - The table also says which edges reach walks (`Reach`) and which validator checks each edge (`Checked by`). No
      script keeps its own list of edge kinds.
  - **D10 — `scripts/audit_root.py` is the audit.** It has two modes:
    - a whole-root audit: the validators' counts, the graph's health, unreached shared workflows and the role
      inventory;
    - reach: for given files, or a branch's changed files, the processes that reach each one per application, and its
      direct referrers.

    It never writes and emits no gate block. It exits `0`, `1`, `2` or `3`, like every validator.
  - **D11 — Model resolution lives in `scripts/lib/model.py`,** shared by `validate_model.py` and `graph.py`.
    - Each loader keeps its own rule. `TableManager` strips everything up to the last `.` **first**, then matches
      `BASE:` in any case, so `BASE:dbo.X` resolves in the application; `EditableGridManager` does not clean the name;
      `LookUpDialogManager` has no base path, so a `webasm` entity's dialog resolves in the application (E6, E16).
    - A `webasm` file's unprefixed reference is resolved in every application, as `workspace._resolve` already does
      for components — or in one, when the graph passes `app`.
  - **D12 — A model reference blocks only where its loader throws.** This is the ADR 0014 principle applied to the
    model.
    - The `reference-edges` row's `When absent` column records what the loader does when the target is missing:
      `throws` → `MODEL_REFERENCE_UNRESOLVED` (exit `1`); `template` → `MODEL_REFERENCE_TEMPLATED` (exit `2`).
    - Verified so far (E6, E16):
      - a missing table throws (`TableManager.LoadAsync`), and so does a missing dialog (`LookUpDialogManager`);
      - a missing lookup view, grid or form is built from a template **and written into the workspace**
        (`CreateFromTemplateAsync` in each manager), and an empty view, grid or form name is `default`;
      - a composite reference is two edges: the table part `throws`, the view, grid or form part `template`;
      - a relation's `table` is the junction's database table, not a `_DATA` entity, so it is not checked;
      - a `binding` names columns, not files, so it is not an edge;
      - a form cell that names no field is an empty cell (`FormCell.IsEmptyCell`), which the runtime tolerates — so
        it is at most a warning.
    - `MODEL_REFERENCE_TEMPLATED`'s message says the runtime will write the default file into the workspace.
    - Task 3 re-reads each loader for its ledger. A loader whose behaviour cannot be established is left unchecked
      and listed under `NOT RUN`.
  - **D13 — Permissions and tools.**
    - All four skills are in `NO_GIT`: their git reads are the scripts'. `/dgf-audit` is also in `READ_ONLY`.
    - Each pre-approves only `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*)`, and the DGF docs MCP tools it calls.
    - Each skill is `version: 0.1.0` with `disable-model-invocation: false`.
  - **D14 — Templates are output shapes, proven by a test.**
    - `/dgf-process` ships `templates/process.xml` and `templates/_workflow.xml`; `/dgf-model` ships
      `templates/settings.xml`.
    - A test runs each through its validator and requires a clean result, with only the documented
      `XSD_LAGS_RUNTIME` allowance for `settings.xsd`.
    - `/dgf-component` composes JSON from `get_json_schema_details` and `get_component_examples`, and a legacy form
      with `build_form_xml` where the MCP offers it. It then validates in-process; the MCP is never the check
      (ADR 0014 §4).
  - **D15 — Three new knowledge files, stamped and ledgered, read at DGF `cccd4325b`:**
    - `knowledge/data-model.md` — entities, fields, relations, bindings, the loaders and where the schema lives;
    - `knowledge/reference-graph.md` — every edge, its resolution, its `When absent`, and §3, what static reach cannot
      see;
    - `knowledge/permissions.md` — where role names appear, and that the root declares none.

    Each has `dgf_version: "1.1.11"` and a `provenance/` ledger. Two new machine-read tables, `reference-edges` and
    `role-sources`, are registered in `knowledge.TABLES` and `knowledge/README.md` §7.
  - **D16 — A reach report never reads as complete.** Every reach report ends with a `LIMIT:` line naming what static
    reach cannot see (E3):
    - names assigned at run time (`_WORKFLOWNAME_`, `_FORMNAME_`, `_TABLENAME_`);
    - processes chosen from the database;
    - open handlers;
    - entry points outside processes (`_PROFILE`, sitemaps, `_form.xml` and view `WORKFLOW:` strings, JSON
      `workflow` components).

    An edge is `dynamic` when **its own step's** `Assign` sets the name that replaces its target (E16):
    `_WORKFLOWNAME_` on a `SubWorkflow`, and `_TABLENAME_` or `_FORMNAME_` on an `Invoke`. An `Assign` elsewhere in
    the workflow does not make it dynamic. A chain through a dynamic edge is flagged `AUDIT_REFERENCE_DYNAMIC`.
  - **D17 — No `.dgf-factory/processes/` snapshot.** Reach is computed on demand from the files. The blueprint's
    `[assume]` `processes/` directory is closed as not built, because a stored map goes stale with the next commit.
  - **D18 — Process reach follows workflow-bearing edges only.**
    - A process reaches a file along the process's actions, its `validationFlow`, `MultiTask` actions and `SubWorkflow`
      calls. It then reaches the forms those workflows invoke or record through, each form's entity (`form-table`),
      and the entities and data sources they name directly. These are the rows whose `Reach` is `follow` or `end`.
    - `Process/@table` is a database table name, not an entity (E16), so it is no edge.
    - A `StateProcess` step starts or moves *another* process, so reach stops there (`Reach` `none`).
    - An entity-to-entity edge (`extract-*`, `slavegrid-*`) is reported one level deep, as a direct referrer
      (`Reach` `none`); followed transitively, it would spread through every lookup table in the estate.
  - **D19 — The doctor knows `dgf-model`.** `EXPECTED_SLICES` gains it (E10), and `tests/test_doctor.py`'s slice tuple
    gains the four skills.
  - **D20 — Out of scope, each a follow-up:**
    - `/dgf-plan` recording reach for tasks that touch a shared workflow;
    - the workflow edges no validator checks (`Checked by` `—`) as blocking validator checks;
    - tracing entry points outside processes;
    - a role registry check;
    - `inventory_root.py` counting entities;
    - `/dgf-scaffold`.

## Roadmap Linkage

Milestone: "DGF-Specific Skills"
Rationale: This plan builds four of the milestone's five skills, and `/dgf-audit`'s blast radius, as the milestone
names them. `/dgf-scaffold` stays blocked by the user's decision D1, so the milestone stays open after this plan with
that one item left.

## Evidence

Read on 2026-09-26 and 2026-09-27, at dgf-factory `develop` `b0be7f1` and DGF `cccd4325b` (2026-09-26). DGF paths are
maintainer evidence and go only into ADR Context and `provenance/` ledgers, never into a shipped file (ADR 0012).

- **E1 — The milestone and its predecessors.**
  - `.ai-factory/ROADMAP.md:20` is the entry.
  - The blueprint's phase-2 table has `/dgf-component`, `/dgf-process`, `/dgf-model` (`[assume]`), `/dgf-audit` and
    `/dgf-scaffold` (`docs/blueprint.md:297-301`), and the build order has "6. Then the DGF-specific skills"
    (`:360`).
  - The artifact layout marks `processes/` "process-model snapshots + blast-radius maps `[assume]`" (`:322`). The gate
    schema names `"process"` and `"components"` gate ids (`:330`), which were never built.
  - `docs/skill-authoring.md:24-33` already uses `dgf-component` as its frontmatter example.
- **E2 — Blast radius was left to this milestone.**
  - ADR 0022 §6 says `affected_*` fields are "the change's own footprint … not its blast radius: which processes reach
    a changed shared workflow is `/dgf-audit`'s question" (`docs/adr/0022-gate-block-contract-revised.md:198-212`).
  - Alternatives reject blast radius in `affected_processes` (`:275-276`), and Negative records that "the footprint is
    not the blast radius" (`:312`).
  - `scripts/verify_gate.py:35` and `footprint()` (`:362-382`) compute the changed set only.
  - `GATES` holds only `verify` and `doctor` (`scripts/lib/gate_result.py:34`).
- **E3 — Static reach is computable, per application, and incomplete.**
  - From the DGF samples (`src/samples/workspaces`), resolved with the engine's rules plus `SubWorkflow` closure:
    - running `zims`: 126 workflows reachable, 109 of them shared. **49 shared workflows are reached by more than one
      process**, the widest being `webasm/AX.Notify`, reached by 11;
    - running `dgf`: 40 shared workflows reachable, 21 of them by more than one process.
  - Base processes are app-dependent: 43 `WORKFLOW:/X` actions in `webasm` processes resolve in the running
    application's `_WORKFLOW`, and 22 of them dangle under `dgf`.
  - Incomplete, because of:
    - `_WORKFLOWNAME_` (7 uses in 4 files), `_FORMNAME_` (21 in 15) and `_TABLENAME_` (32 in 13), all evaluated at run
      time. `_WORKFLOWNAME_` overrides a `SubWorkflow` target (`src/Core/DGF.DataViewer/Workflow/HumanWorkflow.cs:601-606`,
      verified: `_WorkflowName = assignState.WorkflowName != "" ? assignState.WorkflowName : wfSubWorkflow.Settings.WorkflowName`,
      then `LoadWorkflowAsync(_WorkflowName, true)`);
    - processes chosen from the database (`prc_WF_StartProcess.sql:87-125`; ProcessFlow's `ServiceID`);
    - open handlers (`OpenHandler.cs:28-36`);
    - entry points in `_PROFILE` (`WORKFLOW:` 262, `STATEPROCESS:` 165), `_form.xml` (73) and JSON `workflow`
      components (47).
  - A textual scan finds 28 of 128 `webasm` and 39 of 188 `zims` shared workflows referenced nowhere. This is a
    heuristic.
  - Workflow → X edges across 341 workflow files (`src/Core/DGF.Domain/Workflow/AbstractSequence.cs:22-38`):
    - `SubWorkflow/Settings/@workflow` 309;
    - `Invoke` with `control="Form"` 384 of 418;
    - `XmlIsland` / `UpdateRecord` / `CreateRecord` `Settings/@table` 384 / 256 / 4;
    - `DataSourceStep/@DataSourceName` 22;
    - `StateProcess` 40.
  - Two `webasm` workflows are spelled `_workflow.XML`, which Linux would not load.
  - Source: the research pass of 2026-09-27. Task 4 re-reads every runtime path it encodes.
- **E4 — No bootstrap template.**
  - ADR 0004 §Context: "could not be located in first-party DGF" (`docs/adr/0004-authoring-entry-point.md:54`). §2
    decides that it "drives a template" (`:78`), and the follow-up is "Identify the bootstrap template" (`:145`).
  - Re-searched 2026-09-27: no `.template.config` or `template.json`, no new-workspace, new-app or new-tenant script,
    and no bootstrap docs page.
  - The nearest evidence: `dgf` is the reference application workspace (`src/samples/workspaces/readme.md`), built by
    `tasks/default-workspace-plan.md`. It needs an `aspnet_Applications` row before the API starts
    (`src/samples/Database/readme.md:84-88`). `Dockerfile.workspace` packages an existing workspace.
- **E5 — The data model is described in the root; its schema is not.**
  - An entity is `FM/_DATA/<E>/settings.xml` → `Table` (`[XmlRoot("entity")]`,
    `src/Core/DGF.Domain/Data/Table/Table.cs:9-115`), with fields (`Field.cs:56-145`) and a `datasource` (`DB` or
    `Provider`; `TableDataSource.cs:10-52`).
  - Relations:
    - `extract` (N:1, table + view or dialog);
    - `relation` (M:N; its `table` is `DataSourceTable`, a database junction table: `RelationProperties.cs:14-15`);
    - `slavegrid` (1:N, table + grid);
    - `binding` (cascades).
  - Samples:
    - `webasm` has 194 entities and 3255 fields; `zims` has 223 and 5044; `dgf` has 12 and 103;
    - across the three: `extract table` 1746, `relation` 14, `slavegrid` 146, `binding` 231.
  - `settings.xsd` declares `extract` `table`/`view` (required) and `dialog`, `binding` `from`/`to`, `slavegrid`
    `table`/`grid`, and `relation` `table` (`knowledge/schemas/xsd/settings.xsd:83-86`, `:158-160`, `:165-166`,
    `:189-190`, `:223`).
  - The database schema is framework-owned plus per-consumer SSDT/DACPAC projects outside the workspaces root
    (`src/samples/Database/readme.md:13-38`, `:73-76`). No EF migration touches application tables. `_DATACALLS` is
    read by nothing: no `WorkspaceSettings` constant, and no loader.
  - SQL is out of scope for every skill that writes (`docs/adr/0010-dgf-implement-scope.md:138`).
- **E6 — The model loaders, read 2026-09-27 at `cccd4325b`.**
  - `TableManager.GetXmlWorkPath` matches `BASE:` with `InvariantCultureIgnoreCase` and strips `schema.`.
    `LoadAsync` **throws** "Settings file for the table … not found" (`src/Core/DGF.Domain/Data/Table/TableManager.cs:16-43`).
  - `LookUpViewManager.LoadAsync(table, view)`:
    - an empty view is `default`;
    - `_lookupviews/<view>/_view.xml` is tried first;
    - a missing view is built by `CreateFromTemplateAsync` — **no throw** (`src/Core/DGF.Domain/Data/Lookup/LookUpViewManager.cs:19-60`).
  - `LoadDefaultView`: with a table, it loads table + view; otherwise it loads the dialog, then that dialog's first
    view (`:191-198`).
  - `LookUpDialogManager` reads `_LOOKUP/<dialog>/_dialog.xml`, application path only (`LookUpDialogManager.cs:13-28`,
    per research; Task 3 re-reads it).
  - `EditableGridManager.GetXmlFilePath`: `BASE:` in any case, and the table name **not** cleaned. `LoadAsync` loads the
    table first, so a missing table throws (`src/Core/DGF.Domain/Data/EditableGrid/EditableGridManager.cs:10-40`). What
    a missing grid does is read in Task 3.
  - `FormCell(field, table)` sets `Settings`, and `IsEmptyCell => Settings == null`
    (`src/Core/DGF.Domain/Data/Form/FormCell.cs:168-180`). `DiagnosticCheckService` skips a cell whose `Settings` is null
    (`src/Core/DGF.Explorer/Services/DiagnosticCheckService.cs:734-741`), and checks `extract`, `relation` and
    `slavegrid` per field type (`:181-229`).
- **E7 — Roles are database rows; the root names them as strings.**
  - Roles are `AspNetRoles` rows seeded by `ApplicationDbContextSeed`
    (`src/Core/DGF.Infrastructure/Persistence/Seed/ApplicationDbContextSeed.cs:29-57`).
  - The root names them in:
    - `_application.sitemap` `mapNode/@roles` and `@deny` (`ApplicationMapNode.cs:12-34`; enforced in
      `SiteMapManager.cs:614-629`, where a `roles` of exactly `Members` means any authenticated user — E16);
    - `FM/_COMPONENTS/sitemap.json` `requireClaims`;
    - `_PROFILE/<Profile>/<RoleGroup>/` folders (`TreeManager.cs:23-36`, falling back to `Members`);
    - process `Task/@role` (`Task.cs:7-16`) and `MultiTask/TaskGroup/@role` (`MultiTaskGroup.cs:19-22`).
  - JSON components and `_form.xml` carry no role attribute.
- **E8 — The readers.**
  - ADR 0021 §5: "The readers are six" (`docs/adr/0021-learning-loop.md:188`). §6: `/dgf-evolve` "targets exactly the
    readers" (`:194`).
  - The contract test holds `READERS` (`tests/test_skill_contracts.py:126`) to the skills whose `SKILL.md` runs
    `check_override.py --skill <own name>`, and the `**Targets:**` line (`skills/dgf-evolve/SKILL.md:27`) to `READERS`.
    A `SKILL.md` that mentions `skill-context/` or `skill_context` must be a reader or the writer.
  - The six readers' override block is word for word, apart from the skill name (for example
    `skills/dgf-fix/SKILL.md:40-56`).
  - 30 files cite ADR 0021 today (grep, 2026-09-27), one of them only as a bare `0021`
    (`docs/pipeline.md:289`).
- **E9 — `/dgf-fix` is the model for a writing skill** (`skills/dgf-fix/SKILL.md`):
  - Step 0 finds the root and checks the override;
  - Step 0.2 finds the plan (`locate_plan.py`) and checks it (`check_plan.py`), with STOP rows;
  - Step 3 decides the scope with `check_change.py --changed M:… A:… --skip-validators`;
  - Step 5 confirms with `check_change.py --base … --files …`;
  - it relays with exit tables, stops after at most 3 attempts, and never deletes.

  Its frontmatter pre-approves `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*)` and four MCP tools, and no git.
- **E10 — The slices and the contract.**
  - `EXPECTED_SLICES` already lists `dgf-component`, `dgf-process` and `dgf-audit`, but not `dgf-model`
    (`skills/dgf-doctor/scripts/doctor.py:124-125`). It drives INFO lines only.
  - The doctor blocks on frontmatter YAML hazards (`:416-443`), so an `argument-hint` that starts with `[` is quoted.
  - `READ_ONLY = ("dgf-doctor", "dgf-verify")` and `NO_GIT = READ_ONLY + ("dgf-evolve", "dgf-fix")`
    (`tests/test_skill_contracts.py:174-175`).
  - Every called script must exist, every flag must appear in its `--help`, and every backticked code must be in
    `report.CODES` (`:62-107`).
  - A known-bad case's `cli` must be a file under `scripts/` (`tests/test_known_bad.py:43`).
- **E11 — Routing is already a table.**
  - `route_means.py <name>` prints `ROUTE: <family> <where> — <reason>` from `legacy-artifacts`, `component-folders`,
    `correspondence` and `parity`.
  - `legacy-artifacts` (`knowledge/composition-specs.md:112-122`) has `process`, `workflow`, `form`, `settings`,
    `table-view`, `lookup-view`, `grid-form` and `options`.
  - `plan.artifact(rel)` names a file's artifact (`scripts/lib/plan.py:478-517`).
- **E12 — What the scripts already resolve, and what they throw away.**
  - The `workspace` resolvers already return a concrete target:
    - `resolve_workflow_ref`, `resolve_workflow_name` (`scripts/lib/workspace.py:250-265`);
    - `resolve_validation_flow` (`:268`);
    - `resolve_process` (`:287`);
    - `resolve_component_file` (`:311`);
    - the core `_resolve` (`:164-188`), which returns `Resolved`/`Unresolved`/`CaseOnly`/`AppDependent`.
  - The callers keep only the findings:
    - `process_checks.workflow_references` and `change_state_targets`;
    - `resolve_components.references` / `resolve_reference`.
  - The only reverse index is `process_checks.entry_states(root)` (`:187-206`), and it keeps states, not sources.
  - Nothing resolves:
    - a `SubWorkflow`'s `workflow`, or `Invoke`/`XmlIsland`/`UpdateRecord`/`CreateRecord`'s `table`/`form`;
    - `DataSourceStep`, or a process's `@table`;
    - a form's cells, or `settings.xml`'s `extract`/`slavegrid`.
  - `_ENTRY_CACHE` and `_DECLARED_CACHE` are module-level and never invalidated (`process_checks.py:45-46`), so the
    graph must not lean on them.
  - `runner.VALIDATORS` is `("validate_process.py", "validate_config.py", "resolve_components.py")`
    (`scripts/lib/runner.py:26`). `run_known_good.py` runs through the runner.
- **E13 — The ADR rules.**
  - Supersession is always full: a successor restates every section still valid, and the old ADR changes only
    `status` and `date` (`docs/adr/README.md:64-73`).
  - An erratum may not change a decision (`:75-90`).
  - `tools/check-dual-schema-docs.sh` §5 and §5b check links and chains.
  - Milestone 11 repointed ADR 0020's live citations when 0022 superseded it
    (`.ai-factory/plans/feature-learning-loop.md:96-99`, Task 2).
- **E14 — The baseline is green.** Measured on 2026-09-27:
  - 680 unit tests pass (34.6 s);
  - `tools/check_drift.py` against DGF `cccd4325b` is CLEAN: 7 ledgers, 255 sources, stamps `1.1.11`;
  - `tools/run_known_good.py` is CLEAN at `cccd4325b` with the 2026-09-24 counts: 71 errors excused by `EXCEPTION`,
    9 by `EXPECTED_EXTERNAL`.
- **E15 — Authoring policy.**
  - "AI generates XML for all five legacy artifact types" (DGF's format-coverage page, shipped as
    `knowledge/composition-specs.md` §4).
  - `Workflow` and `ProcessFlow` JSON are ✗ (`schema-families.md` §6).
  - The MCP's `build_form_xml` turns a FormSpec into `_form.xml`. The FormSpec carries no settings, workflow or process,
    and is to be followed by `validate_form_xml` and `validate_xml_cross_references` (DGF `docs/wiki/AI-Authoring/form-spec.md:207-221`).
  - No DGF page is a process- or workflow-authoring guide; the closest are `Recipes/demo-eservice-recipes.md` and
    `Getting-Started/The-DGF-Workspace.md` §7.
- **E16 — The runtime re-read of 2026-09-27 (the `/aif-improve` pass, DGF `cccd4325b`).** It answers what E6 left
  open, and corrects DD4's first draft. Tasks 3–5 re-read each file for the ledger before writing a fact from it.
  - `TableManager.GetXmlWorkPath` calls `GetCleanTableName` (strip up to the last `.`, `ViewManagerBase.cs:14-19`)
    **before** the `BASE:` test, so `BASE:dbo.X` resolves in the application. An unprefixed name is the selected
    application's only: no fallback to `webasm` (`TableManager.cs:16-40`).
  - A missing **form** is not an error. `FormManager.CreateFromTemplateAsync` copies the `default` form, or generates
    one from the table's fields, and **writes it into the workspace** (`FormManager.cs:131-139`). A form folder with no
    `_form.xml` throws (`:144`). The table is loaded first and throws.
  - A missing **grid** is copied from `default` or generated and saved (`EditableGridManager.cs:70-77`); the table is
    loaded first and throws. Grids live at `_DATA/<table>/_gridforms/<grid>/_grid.xml`.
  - A missing **lookup view** is generated and saved by `CreateFromTemplateAsync` (`LookUpViewManager.cs:59-69`).
  - A missing **dialog** throws "Lookup Dialog … not found" (`LookUpDialogManager.cs:26`). `_LOOKUP` is the selected
    application's only, so a `webasm` entity's `dialog` resolves in each application.
  - `extract`: a non-empty `table` loads table + view, and `dialog` is ignored; only with no `table` is the dialog
    loaded (`ExtractProperties.cs:7-14`, `LookUpViewManager.cs:191-198`).
  - `binding`: `from` is a column of the host entity and `to` a column of the extract's table
    (`SqlQueryBuilder.cs:603-604`). It names columns, not files, so it is **not an edge**.
  - `Process/@table` is a **database table name**: `InstanceHandler` passes it to SQL, `BASE:` stripped
    (`InstanceHandler.cs:274, 443, 471`). No loader opens `_DATA` for it.
  - `UpdateRecord`/`CreateRecord` load through `FormManager.LoadAsync(table, form)` (`SequenceWorkflow.cs:470-471`);
    `XmlIsland` loads its table only when its `FieldSet` is non-empty (`:62-67`).
  - `Invoke` acts on a form only when `control`, upper-cased, is `FORM` (`HumanWorkflow.cs:486-496`).
  - Run-time names are **per step**: a step's own `Assign` child is evaluated for that step (`RoundTrip.cs:282-288,
    390`, `:355-362`). `_WORKFLOWNAME_` replaces a `SubWorkflow`'s target (`HumanWorkflow.cs:601-603`), and
    `_TABLENAME_`/`_FORMNAME_` replace an `Invoke`'s table and form (`:504-506`).
  - A missing `SubWorkflow` target throws (`WorkflowManager.cs:68`); a missing `DataSourceStep` file throws
    `FileNotFoundException` (`DataSourceLoader.cs:20`), and an empty name is a no-op. A step's exception is rethrown
    unless the step has `hideExceptions="true"` (`SequenceWorkflow.cs:603-617`).
  - A `StateProcess` step's missing process is caught per id and sets `_HasError_`; it is not rethrown
    (`SequenceWorkflow.cs:515-535`).
  - `DataSourceLoader` reads `_COMPONENTS/DataSource/<name>.json`, `BASE:` in any case, subfolders allowed
    (`DataSourceLoader.cs:12-29`) — `workspace.component_location`'s rule exactly.
  - Roles: `CheckPermissions` splits `roles` and `deny` on `,` **with no trimming**, and `Members` counts only when the
    whole `roles` value is exactly `Members`, case-sensitive (`SiteMapManager.cs:614-629`). `_application.sitemap`
    sits at the workspace root, beside `FM/` (`ApplicationMap.cs:8-9`).
- **E17 — The plugin code re-read of 2026-09-27.**
  - `overrides.WRITTEN` (`scripts/lib/overrides.py:52`) is the **exact** header line an override must carry, `(ADR
    0021)` included; `_quoted()` refuses any other `> ` line as `OVERRIDE_SHAPE` (`:224-228`). The five override
    known-bad fixtures and every estate's committed override carry it.
  - `knowledge._cells()` strips one pair of backticks around a whole cell (`scripts/lib/knowledge.py:104-113`), so
    `` `A` `B` `` reads as `` A` `B ``. Allowed values are checked against the whole cell.
  - From a `webasm` owner, `workspace._resolve` always resolves a selected-scope reference in **every** application
    (`scripts/lib/workspace.py:164-188`). Nothing fixes the selected application.
  - No `tests/test_runner.py` exists, and no test pins `runner.VALIDATORS`.
  - `READ_ONLY` only builds `NO_GIT` (`tests/test_skill_contracts.py:174-175`); nothing checks a read-only skill's tools.
  - The doctor already blocks on a `${CLAUDE_PLUGIN_ROOT}/…` path a `.md` file cites and the plugin lacks
    (`PLUGIN_PATH_DANGLING`, `skills/dgf-doctor/scripts/doctor.py:490-500`).

## Design

### DD1 — ADR 0023: the DGF-specific skills

`docs/adr/0023-dgf-specific-skills.md`. Its title: "The DGF-specific skills write only inside a plan's scope, check the
model in the gate, and report blast radius from a reference graph resolved per application".

- §1 authoring scope (D2);
- §2 the partition (D8);
- §3 the model (D3, D11, D12): the severity rule — a model reference blocks only where its loader throws — stated
  once. Each edge's `When absent`, and the loader behind it, is **cited** to `knowledge/reference-graph.md` §1, never
  listed in the ADR. Tasks 3–4 settle those facts after this ADR is accepted, and a fact that changes must not need an
  erratum or a superseding ADR;
- §4 the graph (D9, D18);
- §5 the audit and blast radius (D4, D10, D17) — no gate block, ADR 0022 §6 unchanged, reach per application;
- §6 roles (D5);
- §7 `/dgf-scaffold` (D1) — blocked. What unblocks it is the tool, where it lives and the inputs it takes, which is
  ADR 0004's follow-up. Until then no skill emits a new workspace;
- §8 the limits of static reach (D16).

### DD2 — ADR 0024: the learning loop, ten readers

`docs/adr/0024-learning-loop-revised.md`, `supersedes: [0021]`. Its title: "The learning loop: /dgf-fix records patches
inside a plan's scope, and /dgf-evolve writes overrides a script checks, which may only tighten a skill — read by ten
skills".

- It restates 0021's Context, §1–§8, Alternatives and Consequences, with the same section numbers.
- §5's last bullet becomes: "**The readers are ten** — `/dgf`, `/dgf-audit`, `/dgf-commit`, `/dgf-component`,
  `/dgf-fix`, `/dgf-implement`, `/dgf-model`, `/dgf-plan`, `/dgf-process` and `/dgf-verify` — and each runs it before
  reading its override."
- §6's targets are the same ten.
- §3 adds one sentence: the override header's text, `(ADR 0021)` included, is a frozen format that
  `check_override.py` requires exactly, and it does not follow the ADR's number (D7, E17).
- Context adds E8 and the reason: the four new skills are where DGF gotchas bite.
- Alternatives add "the four new skills read no override" (rejected: a skill that reads no override cannot learn from
  a patch).
- Negative adds: ten skills pay the check's call; a consumer that counted six meets ten; 0021's live citations moved.

### DD3 — `knowledge/data-model.md` (Task 3)

Structural facts, stamped `dgf_version: "1.1.11"`, `read_date` the day. Sections:

1. **An entity.** It is the folder `FM/_DATA/<Entity>/`. `settings.xml` has root `entity`, with its attributes, its
   `datasource` (`DB`: a database table or view; `Provider`: an `Assembly,Type`) and its fields. The folder name is the
   logical entity; the `datasource` `name` is the physical object.
2. **A field.**
   - Its attributes, and its `type` values with sample counts (Text 3991 … Html 1).
   - Which types carry which child: `Lookup`/`Picklist` → `extract`, `EditableGrid` → `slavegrid`.
3. **Relations.** Each of `extract`, `relation`, `slavegrid` and `binding`: what it names, which loader reads it, and
   what happens when the target is missing — E6 and E16, re-read.
   - `extract` loads table + view when `table` is set, and the dialog only when it is not.
   - A missing view, grid or form is generated and written into the workspace; a missing table or dialog throws.
   - The `relation` table is a database object: not a file in the root.
   - A `binding` names a host column (`from`) and a column of the extract's table (`to`): not a file, so not an edge.
4. **A form binds to its entity.**
   - A `_form.xml` under `_DATA/<E>/_forms/<f>/` belongs to `<E>`, and `FormManager` loads that table first.
   - A cell's `name` is a field name. A cell with no field is an empty cell, and a cell with content is custom.
5. **Where the schema lives.** It is outside the workspaces root: framework tables, plus the consumer's own database
   project. A change to fields or entities needs database work there. `_DATACALLS` is read by no loader.

- Ledger: `provenance/knowledge/data-model.md` lists every DGF file read, with its `sha256`: `Table.cs`, `Field.cs`,
  `TableDataSource.cs`, `ExtractProperties.cs`, `RelationProperties.cs`, `SlaveGridProperties.cs`,
  `BindingProperties.cs`, `TableManager.cs`, `ViewManagerBase.cs`, `LookUpViewManager.cs`, `LookUpDialogManager.cs`,
  `EditableGridManager.cs`, `FormManager.cs`, `FormCell.cs`, `SqlQueryBuilder.cs`, `WorkspaceSettings.cs`,
  `src/samples/Database/readme.md` and `settings.xsd`.
- **No machine-read table here.** The model's edges are rows of `reference-edges` (DD4), so one table says what an edge
  is.

### DD4 — `knowledge/reference-graph.md` and the `reference-edges` table (Task 4)

§1 is the table, marked `<!-- machine-read: reference-edges -->`. Values come from E16. Task 4 re-reads each class
before writing its row. A `…` cell is still unread.

| Edge | From | Element | Attribute | Condition | To | Resolves as | When absent | Reach | Checked by |
|---|---|---|---|---|---|---|---|---|---|
| `process-action` | `process` | `OnStart State Transition` | `action` | — | `workflow` | `action` | `throws` | `follow` | `validate_process.py` |
| `multitask-action` | `multitask` | `TaskGroup` | `action expiredaction postviewaction` | — | `workflow` | `action` | `throws` | `follow` | `validate_process.py` |
| `validation-flow` | `process` | `Process` | `validationFlow` | — | `workflow` | `workflow-name` | `throws` | `follow` | `validate_process.py` |
| `state-process` | `workflow` | `StateProcess` | `process` | — | `process` | `process-name` | … | `none` | `validate_process.py` |
| `sub-workflow` | `workflow` | `SubWorkflow/Settings` | `workflow` | — | `workflow` | `workflow-name` | `throws` | `follow` | — |
| `invoke-table` | `workflow` | `Invoke/Settings` | `table` | `control-form` | `settings` | `table-name` | `throws` | `end` | — |
| `invoke-form` | `workflow` | `Invoke/Settings` | `table+form` | `control-form` | `form` | `form` | `template` | `follow` | — |
| `record-table` | `workflow` | `UpdateRecord/Settings CreateRecord/Settings` | `table` | — | `settings` | `table-name` | `throws` | `end` | — |
| `record-form` | `workflow` | `UpdateRecord/Settings CreateRecord/Settings` | `table+form` | — | `form` | `form` | `template` | `follow` | — |
| `island-table` | `workflow` | `XmlIsland/Settings` | `table` | `fieldset-non-empty` | `settings` | `table-name` | `throws` | `end` | — |
| `datasource-step` | `workflow` | `DataSourceStep` | `DataSourceName` | — | `component` | `datasource` | `throws` | `end` | — |
| `form-table` | `form` | — | — | — | `settings` | `owning-table` | `throws` | `end` | `validate_model.py` |
| `extract-table` | `settings` | `field/extract` | `table` | — | `settings` | `table-name` | `throws` | `none` | `validate_model.py` |
| `extract-view` | `settings` | `field/extract` | `table+view` | — | `lookup-view` | `lookup-view` | `template` | `none` | `validate_model.py` |
| `extract-dialog` | `settings` | `field/extract` | `dialog` | `extract-no-table` | `lookup-dialog` | `lookup-dialog` | `throws` | `none` | `validate_model.py` |
| `slavegrid-table` | `settings` | `field/slavegrid` | `table` | — | `settings` | `table-name` | `throws` | `none` | `validate_model.py` |
| `slavegrid-grid` | `settings` | `field/slavegrid` | `table+grid` | — | `grid-form` | `grid` | `template` | `none` | `validate_model.py` |
| `layout-child` | `component` | `content[]` | `path` | — | `component` | `component-file` | … | `none` | `resolve_components.py` |
| `reference-component` | `component` | `ReferenceComponent` | `componentName` | — | `component` | `component-file` | … | `none` | `resolve_components.py` |

- Every row is **read from the runtime class that binds it**, never from the samples or the XSD (`.ai-factory/RULES.md`
  rule 1). The `…` cells, and each row's exact element path, are filled from that reading.
- A row whose runtime behaviour cannot be established is **left out**, and named in §3 as not traced. No script names
  an edge kind in code, so leaving a row out needs no code change.
- **The cell grammar** is set because `knowledge._cells()` strips only one pair of backticks around a whole cell
  (E17):
  - a cell's values go inside one pair of backticks, separated by spaces;
  - in `Element` and `Attribute`, space-separated values are **alternatives**, and each one is its own edge;
  - `a+b` is **one composite reference**, its parts passed in order to the `Resolves as` function;
  - `knowledge.values(cell)` splits a cell into its values; `—` is no value;
  - a row whose `Attribute` part count does not match its `Resolves as` function's arity is `KNOWLEDGE_TABLE`
    (exit `3`), raised when `graph.py` or `validate_model.py` loads the table.
- `When absent` values: `throws`, `template` (the runtime generates the file and writes it into the workspace),
  `skipped` (the runtime ignores it), `unknown`. `unknown` is a legal value that no check may block on. A
  workflow-step `throws` holds unless the step has `hideExceptions="true"`; §2 says so, and the graph does not model
  it.
- `Condition` values: `—`; `control-form` (the `Invoke`'s `control`, upper-cased, is `FORM`); `fieldset-non-empty`
  (the `XmlIsland` has a non-empty `FieldSet`); `extract-no-table` (the `extract` has no `table`).
- `Reach` values (D18): `follow` — reach walks through the target; `end` — reach reaches the target and goes no
  further; `none` — reach does not walk the edge, which still counts as a referrer.
- `Checked by` values: `validate_process.py`, `validate_model.py`, `resolve_components.py`, or `—`. `validate_model.py`
  checks the rows that name it. The audit reports an unresolved edge only for a `—` row.
- §2, the rules behind `Resolves as`:
  - `action` and `workflow-name` restate `process-model.md` §2.2–2.3 by reference;
  - `workflow-name` for `sub-workflow` has **no process-local prefix** (E3, `HumanWorkflow.OnSubWorkflow`);
  - `process-name` per §2.5;
  - `table-name`, `form`, `lookup-view`, `lookup-dialog`, `grid` and `owning-table` per `data-model.md` §3;
  - `datasource` is `workspace.resolve_component_file(name, "DataSource", …)`, because `DataSourceLoader`'s rule is
    `component_location`'s (E16). An empty name is no reference;
  - `component-file` per `json-reader.md` §2.1.
- §3, **what static reach cannot see**: D16's list, each with its runtime class and sample count. It also names
  `Process/@table` (a database table name, E16) and `hideExceptions`.
- Ledger: `provenance/knowledge/reference-graph.md`, listing:
  - `HumanWorkflow.cs`, `RoundTrip.cs`, `SequenceWorkflow.cs`, `AbstractSequence.cs`, `SubWorkflow.cs`, `Invoke.cs`,
    `FormSettings.cs`, `StartProcess.cs`;
  - the `XmlIsland`/`UpdateRecord`/`CreateRecord` settings classes, and `DataSourceLoader.cs`;
  - `WorkflowManager.cs`, `ProcessManager.cs`, `InstanceHandler.cs`, `StateProcessClient.cs`,
    `ComponentFileLoadService.cs`, `OpenHandler.cs`, `ProcessFlowComponentService.cs` and `prc_WF_StartProcess.sql`.
- Register `reference-edges` in `scripts/lib/knowledge.py` `TABLES`, with its exact header and allowed values for
  `From`, `To`, `Condition`, `Resolves as`, `When absent`, `Reach` and `Checked by`. Add `knowledge.values()`. Add a
  row to `knowledge/README.md` §7, and state the cell grammar in §7.

### DD5 — `knowledge/permissions.md` and the `role-sources` table (Task 5)

- §1: roles are database rows (E7); nothing in the root declares one.
- §2 is the table, marked `<!-- machine-read: role-sources -->`:

  | Source | File | Element | Attribute | Separator | Meaning |
  |---|---|---|---|---|---|
  | `sitemap-roles` | `_application.sitemap` | `mapNode` | `roles` | `,` | allowed roles; empty is anyone; exactly `Members` is any signed-in user |
  | `sitemap-deny` | `_application.sitemap` | `mapNode` | `deny` | `,` | denied roles |
  | `sitemap-claims` | `FM/_COMPONENTS/sitemap.json` | a route's `metaData` | `requireClaims` | — | required claims |
  | `profile-group` | `FM/_PROFILE/<Profile>/<RoleGroup>/` | (folder) | — | — | the role group whose tree applies |
  | `task-role` | `process.xml` | `Task` | `role` | — | a task's assignee role |
  | `taskgroup-role` | `FM/_PROCESS/<P>/<State>.xml` | `TaskGroup` | `role` | — | a MultiTask group's role |

  Task 5 confirms each file's location and the separator from the runtime class (`ApplicationMap`, `SiteMapManager`,
  `TreeManager`, `Task`, `MultiTaskGroup`). E16 found `_application.sitemap` at the workspace root, beside `FM/`, and
  found that a `,` separator is **not trimmed**: `roles="A, B"` tests the role `" B"`. §2 says so.
- §3: the `Members` fallback, and the literal `Applicant`/`SM_CurrentRole` usage, which is data, not a declaration.
- Ledger `provenance/knowledge/permissions.md`. Register `role-sources`, and add a README §7 row.

### DD6 — `scripts/lib/model.py` (Task 6)

Stdlib plus `lxml` through `family.xml_parser()`. Public API:

- `clean_table(name) -> str` — `GetCleanTableName`: strip everything up to the last `.`.
- `table_location(name) -> (scope, parts)` — `clean_table` **first**, then `BASE:` in any case → `base`; otherwise
  `selected`. So `BASE:dbo.X` is `selected` (E16).
- `resolve_table(name, owner, root, app=None)`, `resolve_form(table, form, owner, root, app=None)`,
  `resolve_lookup_view(table, view, owner, root, app=None)`, `resolve_lookup_dialog(name, owner, root, app=None)`,
  `resolve_grid(table, grid, owner, root, app=None)` and `owning_table(form_path, root)`.
  - Each returns a `workspace` result type (`Resolved`, `Unresolved`, `CaseOnly`, `AppDependent`), through
    `workspace._resolve` with its own location function.
  - An empty view, grid or form is `default`. A dialog has no base scope, so from a `webasm` entity it resolves in
    each application.
  - There is no `resolve_datasource`: a `DataSourceStep` resolves through `workspace.resolve_component_file(name,
    "DataSource", …)` (DD4 §2).
- **`workspace._resolve` gains `app=None`** (E17). With `app`, a selected-scope reference from a `webasm` owner
  resolves in `app` alone and returns `Resolved`, `Unresolved` or `CaseOnly`, never `AppDependent`. Every existing
  resolver — `resolve_workflow_name`, `resolve_workflow_ref`, `resolve_validation_flow`, `resolve_process`,
  `resolve_component_file` — passes the keyword through. `app=None` keeps today's behaviour, and every existing test
  still passes.
- `fields(settings_tree) -> {name: (type, line)}`, and `cells(form_tree) -> [(name, line, custom)]`.
- Exact case through `workspace.exact_file`, never `Path.exists()` (`.ai-factory/RULES.md` rule 2).
- A trace on every resolution: `report.debug("model.resolve_table", …, name=…, owner=…, result=…)`.

### DD7 — `scripts/validate_model.py` (Task 7)

- **CLI:** `validate_model.py [--workspaces-root R] (--all | <settings.xml | _form.xml>...) [--verbose]`, mirroring
  `validate_process.py`: `--all` needs `--workspaces-root`, and `--all` with files is exit `3`.
- **Checks, in `checks_run`:**
  - `model-references` — every `reference-edges` row whose `Checked by` is `validate_model.py`;
  - `form-cells`.

  **`NOT RUN`:**
  - `relation-table`: "a relation's table is a database object outside the root";
  - `entity-datasource`: "a `DB` or `Provider` name is a database object or an assembly". It is named apart from the
    `datasource-step` edge, which is a `_COMPONENTS/DataSource` file;
  - any edge whose `When absent` is `unknown`.
- **Codes**, added to `report.CODES` under `# the model (validate_model.py; ADR 0023 §3)`:

  | Code | Exit | When |
  |---|---|---|
  | `MODEL_REFERENCE_UNRESOLVED` | 1 | a `throws` edge resolves nowhere |
  | `MODEL_REFERENCE_TEMPLATED` | 2 | a `template` edge resolves nowhere, so the runtime generates a default and writes it into the workspace |
  | `MODEL_REFERENCE_APP_DEPENDENT` | 2 | from a `webasm` file, it resolves in some applications only; names both lists |
  | `MODEL_CELL_UNBOUND` | 2 | a form cell names no field of its entity and carries no content |

  - `CASE_ONLY_MATCH`, `XML_MALFORMED` and `FAMILY_UNRESOLVED` are reused.
  - A message names the edge, the value and the expected root-relative path, with no absolute path, because
    `baseline.key` keys on the message.
  - A `skipped` edge is never reported.
- **Output:** `report.render(header="Model validation")`. A file that parses gets `rep.family = "xsd"`, as the runner
  does for workflows, so its `FAMILY:` line never reads `unresolved`.
- **Exits:** `0`, `1`, `2`, `3`. `deps.require()` → `3`.
- **Reusable entry point:** `check_file(path, root_override=None) -> Report`.
- **Joining the gate:**
  - Add `"validate_model.py"` to `runner.VALIDATORS`.
  - `runner.targets()` already collects `settings.xml` and `_form.xml` among `configs`. `run()` passes
    `validate_model` only the configuration files whose `plan.artifact()` is `settings` or `form`. The runner holds
    absolute paths, so each is made root-relative before `plan.artifact()`.
  - A new `tests/test_runner.py` pins the runner (E17: no test does today). It checks that `VALIDATORS` is the four,
    that `validate_model` receives only `settings` and `form` files, and that a whole-root and a `files` run route a
    file to the same validators.
  - `check_change.py`, `verify_gate.py` and `tools/run_known_good.py` need no code change beyond what the runner
    returns. Update `run_known_good.py`'s docstring.

### DD8 — `scripts/lib/graph.py` (Task 9)

- **Types:**
  - `Node(path, artifact, name, workspace)`;
  - `Edge(kind, source, line, value, target, status, apps)`, where `status` is `resolved`, `unresolved`,
    `case-only` or `dynamic`.
  - A `_LOOKUP/<dialog>/_dialog.xml` or MultiTask `<State>.xml` node has no `plan.artifact()` row, so `graph.py` names
    its artifact itself: `lookup-dialog` or `multitask`, the `reference-edges` values.
- **`build(root, app) -> Graph`** parses every configuration file in `app` and `webasm` once. It collects files with
  `runner.targets(root)`, includes MultiTask `<State>.xml` files, and adds `form-table` containment.
  - For each `reference-edges` row, it reads the attribute values and resolves them with the row's `Resolves as`
    function from `workspace`/`model`, passing `app=app`, so the selected workspace is fixed to `app` (D9).
  - A `webasm` file's selected-scope reference resolves in `app`.
  - A row's `Condition` is evaluated before the row applies. An unknown `Resolves as` or `Condition`, or an
    attribute part count that does not match the function's arity, raises `knowledge.KnowledgeTableError` → exit `3`.
  - An edge whose **own step's** `Assign` sets its run-time name gets `status=dynamic`, keeping the static target
    (D16): `_WORKFLOWNAME_` on a `sub-workflow` edge, and `_TABLENAME_` or `_FORMNAME_` on an `invoke-table` or
    `invoke-form` edge.
- **`build_all(root) -> {app: Graph}`**, one entry per application from `workspace.applications(root)`.
- **`Graph.reach(target_path) -> [(process_node, chain)]`**:
  - a breadth-first walk forward from every process node, over the rows whose `Reach` is `follow`, stopping at a
    target reached by an `end` row (D18);
  - a visited set, so `SubWorkflow` cycles end;
  - one shortest chain per process, and a deterministic sort by process path.
- **`Graph.referrers(target_path) -> [Edge]`** — every edge of any kind into the target, one level deep.
- **`Graph.unreached(kind="workflow") -> [Node]`** — shared workflows (`_WORKFLOW/`) that no edge reaches.
- It uses no module-level caches. Each `build` parses fresh (E12).
- Trace: `report.debug("graph.build", …, app=…, nodes=…, edges=…)`, and one trace per unresolved edge.

### DD9 — `scripts/lib/roles.py` (Task 10)

- `inventory(root) -> {role: {source: [(file, line)]}}` reads `role-sources`: split on `,` **without trimming**, as
  `SiteMapManager.CheckPermissions` splits (E16), so a role name is listed exactly as the runtime tests it and the
  audit prints it quoted (`ROLE: " B" …`). It reads folder names for `profile-group`, and JSON routes for
  `sitemap-claims`. `_application.sitemap` is read at the workspace root, beside `FM/`.
- Stdlib only, with `xml.etree` for the sitemap and process files. A file it cannot parse is skipped with a
  `report.debug` trace; the other validators already report malformed XML.

### DD10 — `scripts/audit_root.py` (Task 11)

- **CLI:** `audit_root.py --workspaces-root R [--reach PATH… | --base REF | --changed S:PATH…] [--app NAME]
  [--skip-validators] [--verbose]`
  - `--reach` paths are root-relative, checked by `plan.path_problem()`.
  - `--base` and `--changed` are parsed as in `check_change.py`: a ref starting with `-` is exit `3`, and changes
    come from `git.changed()`.
  - `--app` narrows the audit to one application, for speed only (ADR 0004 §3). ADR 0004 §3 also requires a narrowed
    run to say so in its checks, so the output carries `NOT RUN: applications (narrowed to <app> by --app; the other
    applications were not audited)` as well as `AUDIT_NARROWED`.
  - `--skip-validators` applies to a whole-root audit only. With a reach mode it is exit `3`.
- **Whole-root output** (`report.render(header="Audit", lines=…)`):

  ```text
  ROOT: <root>
  APPLICATIONS: <a> <b> (base webasm)
  GRAPH: <app> nodes=<n> edges=<n> resolved=<n> unresolved=<n> case-only=<n> dynamic=<n>
  EDGE: <app> <kind> resolved=<n> unresolved=<n> …
  VALIDATOR: <cli> files=<n> <LABEL> <CODE>=<n> …
  ROLE: <name> <source>=<n> …
  LIMIT: static reach only — <D16's list> (knowledge/reference-graph.md §3)
  ```

  - `CHECKS RUN:` is `graph`, `validators` (unless skipped) and `roles`. `NOT RUN:` has
    `role-check — nothing in the root declares roles (knowledge/permissions.md §1)`.
  - The findings are:
    - each validator `ERROR`, as its own line;
    - `AUDIT_REFERENCE_UNRESOLVED` (exit `2`) for an unresolved edge no validator checks, naming the applications it
      fails in;
    - `CASE_ONLY_MATCH` for a case-only one;
    - `AUDIT_WORKFLOW_UNREACHED` (exit `0`, INFO) per unreached shared workflow;
    - `AUDIT_NARROWED` (exit `2`) when `--app` narrowed the audit.
  - Which edges "no validator checks" is read from `reference-edges`: the rows whose `Checked by` is `—` (D9). A row
    that names a validator is that validator's to report, and reporting it here would report it twice.
- **Reach output:**

  ```text
  REACH: <path> artifact=<artifact> name=<name>
  APP: <app> processes=<n>
  PROCESS: <app> <reference> via <file>:<line> > <file>:<line> > <path>
  REFERRER: <app> <kind> <file>:<line>
  NONE: <app> — no traced reference reaches it
  LIMIT: …
  ```

  - `CHECKS RUN:` is `graph` and `reach`.
  - A deleted file (`D:`) is reached through the head graph's unresolved edges whose expected path is that file, and
    says so.
  - `AUDIT_REFERENCE_DYNAMIC` (exit `0`, INFO) marks a chain that passes a dynamic edge.
  - `AUDIT_REACH_NOT_ARTIFACT` (exit `3`) is a reach path that is not a configuration file under the root.
- **Exits** are the worst finding: `0`, `1` (a validator `ERROR` in the root), `2` or `3`. `deps.require()` → `3`.
  It never writes and emits no gate block.
- Codes go under `# the audit (audit_root.py; ADR 0023 §5)`.

### DD11 — `/dgf-component` (Task 12)

```yaml
name: dgf-component
description: Inspect, validate or scaffold a DGF component — modern JSON under FM/_COMPONENTS or a legacy form, view, grid or options file — in both schema families and parity-aware, writing only inside the active plan's scope. Use for "add a component", "check this component", "is this component valid", "scaffold a DataTable", "what uses this component".
argument-hint: "[inspect | validate | scaffold] <file, Type/name or Type>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__list_components mcp__plugin_dgf-factory_dgf-mcp__get_component_doc mcp__plugin_dgf-factory_dgf-mcp__get_json_schema_details mcp__plugin_dgf-factory_dgf-mcp__get_component_examples mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference mcp__plugin_dgf-factory_dgf-mcp__build_form_xml
disable-model-invocation: false
version: 0.1.0
```

- **Step 0: Context** — `locate_plan.py --root-only`, the config, and the override block word for word with
  `--skill dgf-component`, then the latest 10 patches as cautions.
- **Step 0.1: Mode:** `inspect` (the default for a file), `validate`, `scaffold`.
- **inspect** is read-only:
  - `validate_config.py <file>`, whose `FAMILY:` line is the family;
  - `resolve_components.py <file>`;
  - `route_means.py <Type>`, for the route and parity;
  - `audit_root.py --reach <file>`, for referrers and reaching processes;
  - `get_component_doc` for the type.

  A `Type/name` argument is found by exact-case glob of `*/FM/_COMPONENTS/<Type>/<name>.json`, and every match is
  listed.
- **validate** is read-only: `validate_config.py` and `resolve_components.py` over the files or directories. Both
  families, and every exit row relayed.
- **scaffold** writes only inside the plan:
  1. Steps 0.2 and 3 of `/dgf-fix`: the plan, then the scope via `--changed A:<file> --skip-validators`.
  2. `route_means.py <Type>` gives the artifact. D8's partition: `process`/`workflow` → STOP, `/dgf-process`;
     `settings` → STOP, `/dgf-model`.
  3. The path comes from the `component-folders` or `legacy-artifacts` row.
  4. An existing file → STOP: scaffold never overwrites, and edits belong to `/dgf-implement` or `/dgf-fix`.
  5. Compose: JSON from `get_json_schema_details` and `get_component_examples`, with exact-case `type`; a form with
     `build_form_xml`, then adjusted by hand from `get_xml_property_reference`.
  6. `validate_config.py`, then `resolve_components.py`, at most 3 attempts.
  7. `check_change.py --base … --files <file>` (or `--changed` without git).
  8. Report. Suggest `/dgf-implement` to continue the task the file belongs to, then `/dgf-verify`.
- **Critical Rules:**
  - resolve the family first, and handle both;
  - a passing JSON schema is not runtime parity — relay `PARITY_*`;
  - write only inside the plan;
  - never overwrite, delete or convert;
  - never tick a checkbox;
  - no gate block;
  - `${CLAUDE_PLUGIN_ROOT}` always.

### DD12 — `/dgf-process` (Task 13)

- The frontmatter mirrors DD11. The tools are the scripts plus `get_xml_property_reference`, `search_docs`,
  `get_recipes_for` and `get_doc_page`.
- `argument-hint: "[inspect | validate | author | modify] <process, workflow or file>"`.
- **inspect** is read-only:
  - `validate_process.py --workspaces-root "<root>" <file>`;
  - `audit_root.py --reach <file>`, the processes reaching it per application (a shared workflow's blast radius);
  - a summary of the states, transitions and actions read from the file.
- **validate** is read-only: `validate_process.py` over files, or `--all`.
- **author** writes a new `process.xml`, shared `_workflow.xml` or process-local `_workflow.xml`, inside the plan:
  - the path comes from the `legacy-artifacts` row;
  - the scope is decided with `--changed A:`;
  - it starts from `${CLAUDE_PLUGIN_ROOT}/skills/dgf-process/templates/process.xml` or `_workflow.xml`, renamed;
  - facts come from `process-model.md` and `reference-graph.md`, never from memory;
  - then `validate_process.py`, and `check_change.py … --files`.
- **modify**, inside the plan:
  1. Run `audit_root.py --reach <file>` **before** the edit, and record the processes it reaches.
  2. Decide the scope with `--changed M:`.
  3. Edit.
  4. Run `validate_process.py`, then the **whole-root** `check_change.py --base` with no `--files`. A renamed state
     breaks `CHANGE_STATE` steps in files the edit never touched (ADR 0014 §2).
  5. Report the reach as the processes to regression-test by hand. A process cannot run headlessly (ADR 0014 §5).
- XML always: a `Workflow` or `ProcessFlow` JSON is never written (E15).
- Templates: `templates/process.xml` holds a minimal valid process (one state, `OnStart` to it, a transition to
  `End`). `templates/_workflow.xml` holds a minimal valid workflow. Names are `Example`, which the skill replaces.

### DD13 — `/dgf-model` (Task 14)

- `argument-hint: "[inspect | validate | add | modify] <entity or settings.xml>"`. The tools are the scripts plus
  `get_xml_property_reference` and `search_docs`.
- **inspect** is read-only:
  - `validate_config.py <settings.xml>` (settings.xsd; `XSD_LAGS_RUNTIME` warns, ADR 0016);
  - `validate_model.py <settings.xml>`;
  - `audit_root.py --reach <settings.xml>`, for the forms, workflows and processes using the entity;
  - a field and relation list read from the file;
  - the `datasource` name, "a database object outside the root".
- **validate** is read-only: `validate_model.py` over files, or `--all`.
- **add / modify**, inside the plan:
  - `settings.xml` only, starting from `templates/settings.xml`. Forms and views go to `/dgf-component` (D8).
  - Validate with `validate_config.py` and `validate_model.py`, then the whole-root `check_change.py --base`: a removed
    field unbinds cells in forms the edit never touched.
  - **The migration.** Name the table and columns the change needs in the database. If the plan's `## Scope` does
    not name that database work, say so, and suggest `/dgf-plan` to widen it. Never write SQL (ADR 0010 §3).

### DD14 — `/dgf-audit` (Task 15)

```yaml
name: dgf-audit
description: Audit a whole DGF workspaces root — the validators' health, the reference graph from processes through workflows to forms, entities and components, and the role names in use — or show a change's blast radius, the processes that reach a file in each application. Read-only. Use for "audit the estate", "blast radius", "what reaches this workflow", "which processes use this", "impact of this change".
argument-hint: "[--reach <file>… | --branch] [--app <name>]"
allowed-tools: Read Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
```

- **Step 0** — the root, the config, and the override with `--skill dgf-audit`.
- **Step 1: Mode:**
  - no argument → a whole-root audit;
  - `--reach <files>` → `audit_root.py --reach`;
  - `--branch` → `audit_root.py --base <git.base_branch>`, when `git.enabled`. Otherwise **STOP**, and ask for
    `--reach`.
  - `--app` passes through, and the report says the result is narrowed.
- **Step 2** — relay the output, capturing the exit code before any pipe. Then summarise:
  - per application, the processes reached;
  - the unresolved references;
  - the unreached shared workflows, as candidates rather than dead code;
  - the roles, as an unchecked inventory, each name quoted as the runtime reads it (an untrimmed `" B"` stays visible);
  - every `LIMIT:` line, verbatim.
- **Never:** claim a complete reach, emit a `dgf-gate-result` block, or write a file.
- **Next:** a defect in the estate → `/dgf-plan` to fix it; a reach result → the processes to regression-test.

### DD15 — The contract, and the other slices (Task 16)

- `tests/test_skill_contracts.py`:
  - `READERS` becomes the ten, in sorted-directory order: `dgf`, `dgf-audit`, `dgf-commit`, `dgf-component`,
    `dgf-fix`, `dgf-implement`, `dgf-model`, `dgf-plan`, `dgf-process`, `dgf-verify`;
  - `READ_ONLY` gains `dgf-audit`, and gets a check of its own: a `READ_ONLY` skill's `allowed-tools` holds neither
    `Write` nor `Edit`. Today `READ_ONLY` only builds `NO_GIT` (E17), so `/dgf-audit`'s "never writes" would rest on
    the prompt alone. `dgf-doctor` and `dgf-verify` already pass;
  - `NO_GIT` gains `dgf-audit`, `dgf-component`, `dgf-model` and `dgf-process`.
- `skills/dgf-evolve/SKILL.md`: the `**Targets:**` line becomes the ten, and the prose at `:29-30`, `:55` and `:57`
  says ten.
- `skills/dgf-evolve/references/OVERRIDE-FORMAT.md:11` lists the ten.
- The doctor: `EXPECTED_SLICES` gains `dgf-model`, and `tests/test_doctor.py:173`'s tuple gains the four.
- **A templates test**, `tests/test_skill_templates.py`: each template validates with its validator. Process and
  workflow exit `0`; `settings.xml` exits `0` or `2`, with only `XSD_LAGS_RUNTIME`. That a template path a skill names
  exists is already the doctor's `PLUGIN_PATH_DANGLING` (E17), so the test does not repeat it.
- **The composers read the new knowledge.** `/dgf-implement` Step 3.3 and `/dgf-plan`'s reference-resolution line list
  the knowledge files they compose from. Both gain `knowledge/data-model.md` and `knowledge/reference-graph.md`, since
  the gate now checks the model.

## Commit Plan

- **Commit 1** (after tasks 1–2): `docs(adr): decide the DGF-specific skills, and restate the learning loop for ten readers`
- **Commit 2** (after tasks 3–5): `feat(knowledge): add the data model, the reference graph and the role sources`
- **Commit 3** (after tasks 6–8): `feat(scripts): check the model, in the gate`
- **Commit 4** (after tasks 9–11): `feat(scripts): build the reference graph and audit the root, with blast radius`
- **Commit 5** (after tasks 12–16): `feat(skills): add /dgf-component, /dgf-process, /dgf-model and /dgf-audit`
- **Commit 6** (after tasks 17–18): `docs: document the DGF-specific skills`

Tasks 12–16 are one commit because the contract test's `READERS` must equal the skills that run `check_override.py`,
the moment either side changes.

## Tasks

### Phase 1: Decisions

- [x] **Task 1: Write ADR 0023 — the DGF-specific skills — and index it.**
  Create `docs/adr/0023-dgf-specific-skills.md`. Follow `docs/adr/README.md` §"Section contract":
  - frontmatter: status `accepted`, date the day it is written, deciders `[Andrian Mamei]`, `supersedes: []`, tags
    `[skills, scope, graph, model]`;
  - *Title:* DD1's;
  - *Context* cites E1–E7, E9, E11, E12, E15, E16 and E17, with paths, lines and the read date;
  - *Decision:* DD1's §1–§8, each with the decisions it carries. §3 states the severity rule and cites
    `knowledge/reference-graph.md` §1 for each edge's `When absent`; it lists no loader's behaviour, so Tasks 3–4 can
    settle one without an erratum (DD1);
  - *Alternatives:*
    - read-only skills (put to the user; rejected by D2);
    - model checks standalone, and deferring `/dgf-model` (put to the user; rejected by D3);
    - blast radius in the verify block, or an `audit` gate (put to the user; rejected by D4 — both supersede ADR 0022,
      and consistency findings over a brownfield estate are mostly pre-existing);
    - a role registry check (put to the user; rejected by D5 — no registry exists in the root);
    - a stored `processes/` map (rejected: D17);
    - name-matching the graph (rejected: resolution by the engine's rules, ADR 0014 §3);
    - one `BASE:` rule for every loader (rejected: E6 shows three different rules);
    - transitive entity-to-entity reach (rejected: D18);
  - *Consequences:*
    - Positive:
      - a change to a shared workflow names the processes to regression-test, per application;
      - a removed field or missing table blocks at the gate;
      - each artifact has one writing skill;
      - roles are visible.
    - Negative:
      - the graph mirrors engine code that can change (provenance and drift mitigate this);
      - reach is incomplete (D16), and a reader may still trust it too far;
      - three more writers beside `/dgf-implement` and `/dgf-fix`, held by the scope script;
      - the known-good run has a new validator to settle;
      - `/dgf-scaffold` is still blocked;
      - four more skill descriptions in every session.
    - Follow-ups: D20.
  - Add row 0023 to `docs/adr/README.md` §Index.
  - Run `bash tools/check-dual-schema-docs.sh`: sections 5 and 5b pass.
  - Logging: none — documentation only.
  - Files: `docs/adr/0023-dgf-specific-skills.md`, `docs/adr/README.md`.

- [x] **Task 2: Write ADR 0024, superseding ADR 0021, and repoint its live citations.** (depends on 1)
  - Create `docs/adr/0024-learning-loop-revised.md` per DD2: `supersedes: [0021]`, deciders `[Andrian Mamei]`, tags
    `[learning, pipeline, overrides]`. Restate every section of 0021 with the same numbers. Change only what DD2 names.
  - Set ADR 0021's `status: superseded-by-0024` and its `date` to the day. Leave its body alone. Update its index row,
    and add row 0024.
  - Repoint every **live** citation of ADR 0021 to 0024, keeping the section numbers:
    - `.ai-factory/ARCHITECTURE.md`, `.ai-factory/DESCRIPTION.md`, `AGENTS.md` (and its Agent Rules list: 0021 joins
      the superseded history);
    - `.ai-factory/ROADMAP.md`'s **Follow-ups** (`:32-33`, "Harvest the patches" and `/dgf-transfer`, which cite §8),
      but not its completed entry;
    - `docs/adr/README.md`'s See Also (`:147-148`);
    - `docs/architecture.md`, `docs/blueprint.md` (only its dated `(corrected …)` cells that decide, not history),
      `docs/pipeline.md` (including the bare `0021` at `:289`), `docs/skill-authoring.md`;
    - `scripts/check_override.py`, `scripts/check_patches.py`, `scripts/lib/overrides.py`, `scripts/lib/patches.py`,
      `scripts/lib/report.py`;
    - `skills/dgf-evolve/references/OVERRIDE-FORMAT.md`, `skills/dgf-fix/references/PATCH-FORMAT.md`;
    - `tests/test_check_override.py`, `tests/test_check_patches.py`, `tests/test_overrides.py`,
      `tests/test_patches.py`, `tests/test_report.py`, `tests/test_skill_contracts.py`.
  - **Leave alone:**
    - ADR 0021 itself, and ADR 0022, which is accepted and never edited except by erratum;
    - ADR 0024, which must cite 0021, and ADR 0021's own row in `docs/adr/README.md` §Index, which stays with its new
      status;
    - the completed roadmap entry, the archived plans, `plans/feature-learning-loop.md` and this plan;
    - **the override header, `(ADR 0021)` included** (D7, E17). It is the exact line `check_override.py` requires, so
      changing it would refuse every override an estate has committed. Keep `overrides.WRITTEN`
      (`scripts/lib/overrides.py:52`), the template lines `skills/dgf-evolve/references/OVERRIDE-FORMAT.md:18,35,91`,
      the assertions at `tests/test_overrides.py:15,232`, and the five known-bad override fixtures unchanged. Repoint
      only the prose citations in those files, such as `overrides.py`'s docstring at `:1,7` and `OVERRIDE-FORMAT.md:5`.
      Add a comment above `WRITTEN` saying its text is a frozen format, now decided by ADR 0024 §3, and a test that pins
      it byte for byte.
  - Then run, with the globs quoted so zsh does not expand them:
    `grep -rn "0021" skills scripts knowledge tests docs AGENTS.md README.md tools .ai-factory --include='*.md' --include='*.py' --include='*.sh'`.
    The bare `0021` catches citations the `ADR 0021` form misses. Each hit left must be in the "leave alone" list; the
    only other hit expected is the hash in `scripts/requirements.txt`, which `--include` already excludes.
  - Run `bash tools/check-dual-schema-docs.sh` and the test suite: all green. Only citations moved, and every
    known-bad override case still reports exactly its own code.
  - Logging: none.
  - Files: `docs/adr/0024-learning-loop-revised.md`, `docs/adr/0021-learning-loop.md` (frontmatter only),
    `docs/adr/README.md`, `.ai-factory/ROADMAP.md` (Follow-ups only), and the files above.

### Phase 2: Knowledge (maintainer work, against a DGF checkout)

- [x] **Task 3: Write `knowledge/data-model.md` and its ledger.** (depends on 1)
  - Implement DD3.
  - Read every loader it states from DGF at `cccd4325b` before writing the fact (`.ai-factory/RULES.md` rule 1).
    E16 has already answered the questions this task was to settle. Re-read each one for the ledger, and stop and
    report if a re-read disagrees with E16:
    - a missing grid is copied from `default` or generated, and saved (`EditableGridManager`);
    - a missing dialog throws, and `_LOOKUP` has no base path (`LookUpDialogManager`);
    - `FormManager.LoadAsync` loads its table first, and a missing form is generated and saved;
    - `BindingProperties`' `from` and `to` are columns, so `binding` is not an edge, and `data-model.md` §3 says so.

    Each answer is the `When absent` of its DD4 row.
  - Stamp `dgf_version: "1.1.11"` and `read_date`. No DGF path in the file: name types, file names and MCP pages
    (ADR 0012).
  - Write `provenance/knowledge/data-model.md` with each file's `sha256`.
  - Run `python3 tools/check_knowledge_stamps.py` and `python3 tools/check_drift.py <DGF>`: both CLEAN.
  - Logging: none — knowledge only.
  - Files: `knowledge/data-model.md`, `provenance/knowledge/data-model.md`.

- [x] **Task 4: Write `knowledge/reference-graph.md` with the `reference-edges` table, and register it.** (depends on 3)
  - Implement DD4. Read every edge's runtime class before its row is written. Leave out, and name in §3, any row that
    cannot be established.
  - Register `reference-edges` in `scripts/lib/knowledge.py` `TABLES`, with the allowed values for `Condition`,
    `Reach` and `Checked by` as well. Add `knowledge.values(cell)`, and add the `knowledge/README.md` §7 row with the
    cell grammar.
  - Extend `tests/test_knowledge.py`:
    - the table loads, and its allowed values are enforced;
    - a malformed row is exit `3`;
    - `values()` splits alternatives, keeps an `a+b` composite whole, and reads `—` as no value;
    - a row whose `Attribute` part count does not match its `Resolves as` arity is `KnowledgeTableError`;
    - every row's `Checked by` names a script under `scripts/`.

    Run the doctor: every table loads.
  - Ledger `provenance/knowledge/reference-graph.md`. Stamps and drift CLEAN.
  - Logging: none in knowledge. `knowledge.py` keeps its existing traces.
  - Files: `knowledge/reference-graph.md`, `provenance/knowledge/reference-graph.md`, `scripts/lib/knowledge.py`,
    `knowledge/README.md`, `tests/test_knowledge.py`.

- [x] **Task 5: Write `knowledge/permissions.md` with the `role-sources` table, and register it.** (depends on 1)
  - Implement DD5. Confirm each source's file location and separator from its runtime class.
  - Register `role-sources`, add the README §7 row, extend `tests/test_knowledge.py`, and write the ledger. Stamps and
    drift CLEAN.
  - Logging: none.
  - Files: `knowledge/permissions.md`, `provenance/knowledge/permissions.md`, `scripts/lib/knowledge.py`,
    `knowledge/README.md`, `tests/test_knowledge.py`.

### Phase 3: The model, in the gate

- [x] **Task 6: Add `scripts/lib/model.py`.** (depends on 3, 4)
  - Implement DD6.
  - Tests in `tests/test_model.py`, over `helpers.make_root` roots:
    - a table in the application, and one in `webasm` via `BASE:` and `base:` (any case);
    - a `schema.`-prefixed name, and `BASE:dbo.X`, which resolves in the **application** because the name is cleaned
      before the `BASE:` test (E16);
    - a case-only match;
    - a missing table;
    - a `webasm` entity's unprefixed table present in one application and absent in another (`AppDependent`, naming
      both lists);
    - a lookup view present, absent and empty (`default`);
    - a dialog in the application; one only in `webasm`, referenced from an application entity (unresolved: no base
      path); and a `webasm` entity's dialog, resolved in each application's `_LOOKUP`;
    - a grid with and without `BASE:`, and the raw table name kept;
    - a form present and absent (`default` for an empty name);
    - `owning_table` for a nested form name with `/`;
    - `fields()` and `cells()`, including a custom cell.
  - `workspace._resolve` gains `app=None`, passed through every resolver (DD6). In `tests/test_workspace.py`:
    - with `app`, a `webasm` owner's selected-scope reference resolves in that application alone, and is never
      `AppDependent`;
    - `BASE:` references ignore `app`;
    - with `app=None`, every existing test passes unchanged.
  - Logging: `report.debug("model.<fn>", …)` on every resolution, with `name`, `owner`, `scope`, `app` and the result.
  - Files: `scripts/lib/model.py`, `scripts/lib/workspace.py`, `tests/test_model.py`, `tests/test_workspace.py`.

- [x] **Task 7: Add `scripts/validate_model.py`, and join it to the runner.** (depends on 6)
  - Implement DD7. Add the four codes to `report.CODES`, and pin their exits in `tests/test_report.py`.
  - `tests/test_validate_model.py`:
    - every code's positive and negative case;
    - `--all` with and without a root, and `--all` with files (exit `3`);
    - `NOT RUN` for `relation-table` and `entity-datasource`;
    - a `webasm` form that `validate_config.py` also reads, with its `FAMILY:` line reading `xsd`;
    - a `skipped` edge never reported;
    - a malformed `settings.xml` → `XML_MALFORMED`;
    - the run without dependencies → exit `3` through `helpers.run_cli_blocking()`.
  - Known-bad cases, with `cli: validate_model.py`:
    - `model-extract-table-unresolved`;
    - one per other `throws` edge Task 3 confirmed: for example `model-slavegrid-table-unresolved`,
      `model-extract-dialog-unresolved` and `model-form-table-missing`. A missing grid, view or form is `template`,
      so it is exit `2`, and is never a known-bad case (`test_known_bad.py` accepts exit `1` or `3` only).
  - A change-relative case, `change-new-model-reference-unresolved` (`cli: check_change.py`): a branch that removes an
    entity another entity's `extract` names.
  - In `tests/test_verify_gate.py`:
    - a new `MODEL_REFERENCE_UNRESOLVED` blocks, and `suggested_next` is `/dgf-fix` once the tasks are checked;
    - the same finding at the merge-base is `INFO PRE_EXISTING` and does not block.
  - Add `"validate_model.py"` to `runner.VALIDATORS`. Update the docstrings of `runner.py` and
    `tools/run_known_good.py`. Add `tests/test_runner.py` as DD7 describes; there is no runner test today (E17).
  - Logging: `report.debug("validate_model.check_file", …)` per file, per edge row and per finding.
  - Files: `scripts/validate_model.py`, `scripts/lib/report.py`, `scripts/lib/runner.py`, `tools/run_known_good.py`,
    `tests/test_validate_model.py`, `tests/test_runner.py`, `tests/test_report.py`, `tests/test_verify_gate.py`,
    `tests/test_check_change.py`, `tests/fixtures/known-bad/model-*/`,
    `tests/fixtures/known-bad/change-new-model-reference-unresolved/`.

- [x] **Task 8: Settle the known-good run with the model validator.** (depends on 7)
  - Run `python3 tools/run_known_good.py <DGF>` at `cccd4325b`.
  - Settle every new `ERROR` either by a validator fix, when `validate_model.py` disagrees with the runtime, or by an
    `EXCEPTION` line in `tools/known-good-exceptions.txt` that cites the runtime code path. **Never excuse a validator
    gap** (`.ai-factory/RULES.md` rule 3).
    - A cluster of one defect across many files is excused per file, with `*` keys, each citing the same path.
  - Update the baseline comment: the DGF commit, the new counts per validator, and the date. The verdict must be CLEAN.
  - If more than 50 errors need an `EXCEPTION`, stop and report the clusters before writing them. That many sample
    defects suggests the validator is wrong, not the samples.
  - Logging: none new.
  - Files: `tools/known-good-exceptions.txt`, and `scripts/validate_model.py` / `scripts/lib/model.py` if a fix is due.

### Phase 4: The graph and the audit

- [x] **Task 9: Add `scripts/lib/graph.py`.** (depends on 4, 6)
  - Implement DD8.
  - `tests/test_graph.py`, over built roots:
    - every `reference-edges` kind resolved;
    - a `webasm` process's `/X` action resolved per application: present in one, absent in another;
    - a `SubWorkflow` with no process-local prefix;
    - a `SubWorkflow` cycle ending;
    - a `SubWorkflow` whose own `Assign` sets `_WORKFLOWNAME_` → `dynamic`, and a second `SubWorkflow` in the same
      workflow without one → not dynamic;
    - an `Invoke` whose own `Assign` sets `_FORMNAME_` or `_TABLENAME_` → its `invoke-form` or `invoke-table` edge
      `dynamic`;
    - an `Invoke` with `control="form"` (any case) is an edge, and one with another `control` is not;
    - an `XmlIsland` with an empty `FieldSet` makes no `island-table` edge;
    - `reach()` through `SubWorkflow` two levels deep, stopping at a `StateProcess` target (D18);
    - an entity reached by a process through `invoke-form` → `form-table`, through `invoke-table`, and through
      `record-table`;
    - the walk's edges come from the `Reach` column: a test table with one row's `Reach` changed changes `reach()`;
    - `referrers()` one level deep, including `extract-table`;
    - `unreached()`;
    - an unknown `Resolves as` or `Condition` value, and an arity mismatch → `KnowledgeTableError`;
    - two builds in one process giving the same result (no stale cache).
  - Logging: DD8's traces.
  - Files: `scripts/lib/graph.py`, `tests/test_graph.py`.

- [x] **Task 10: Add `scripts/lib/roles.py`.** (depends on 5)
  - Implement DD9.
  - `tests/test_roles.py`:
    - each `role-sources` row;
    - `roles="A, B"` lists `A` and `" B"`, **untrimmed**, as `SiteMapManager.CheckPermissions` tests them (E16);
    - an empty `roles=""`;
    - `_application.sitemap` read at the workspace root, and one under `FM/` ignored;
    - a folder role group;
    - an unparsable file skipped with a trace.
  - Logging: `report.debug("roles.inventory", …, source=…, file=…)`.
  - Files: `scripts/lib/roles.py`, `tests/test_roles.py`.

- [x] **Task 11: Add `scripts/audit_root.py`.** (depends on 7, 9, 10)
  - Implement DD10. Add its five codes to `report.CODES`, and pin them in `tests/test_report.py`.
  - `tests/test_audit_root.py`:
    - a whole-root audit, with and without `--skip-validators`;
    - `--app` → `AUDIT_NARROWED`, and a `NOT RUN: applications` line naming the narrowing (ADR 0004 §3);
    - `AUDIT_REFERENCE_UNRESOLVED` only for a `Checked by` `—` row: an unresolved `extract-table` is left to
      `validate_model.py` and is not reported twice;
    - `--reach` on a shared workflow two processes reach, in two applications;
    - `--reach` on a non-artifact → exit `3`;
    - `--skip-validators` with `--reach` → exit `3`;
    - `--base` over a git repository: a branch that edits a shared workflow, and one that deletes it;
    - `--changed` without git;
    - `LIMIT:` always present in reach output;
    - no file written under the root, compared before and after;
    - no `dgf-gate-result` in the output;
    - no dependencies → exit `3`.
  - Known-bad case `audit-reach-not-artifact` (`cli: audit_root.py`, exit `3`).
  - Run it over the DGF samples. Record in this plan's implementation notes whether its zims and dgf reach counts
    agree with E3. ADR 0023 is accepted by then and takes no such edit. A difference is explained, or the graph is
    fixed.
  - Logging: `report.debug("audit_root.<fn>", …)` for mode, applications, counts and each reach target.
  - Files: `scripts/audit_root.py`, `scripts/lib/report.py`, `tests/test_audit_root.py`, `tests/test_report.py`,
    `tests/fixtures/known-bad/audit-reach-not-artifact/`.

### Phase 5: The skills

- [x] **Task 12: Write `/dgf-component`.** (depends on 11)
  - `skills/dgf-component/SKILL.md` per DD11, in the house style: an intro saying what it ports and what it drops,
    `## Workflow`, `## Execution Rules` (DO/DON'T), `## Artifact Ownership` and `## Critical Rules`.
  - Every script call has an `| Exit | Action |` table. The override block is word for word.
  - Every fact is cited from `knowledge/`. No DGF path.
  - Logging: none — the skill relays script output.
  - Files: `skills/dgf-component/SKILL.md`.

- [x] **Task 13: Write `/dgf-process` and its templates.** (depends on 11)
  - `skills/dgf-process/SKILL.md` per DD12, plus `templates/process.xml` and `templates/_workflow.xml`.
  - Logging: none.
  - Files: `skills/dgf-process/SKILL.md`, `skills/dgf-process/templates/process.xml`,
    `skills/dgf-process/templates/_workflow.xml`.

- [x] **Task 14: Write `/dgf-model` and its template.** (depends on 11)
  - `skills/dgf-model/SKILL.md` per DD13, plus `templates/settings.xml`.
  - Logging: none.
  - Files: `skills/dgf-model/SKILL.md`, `skills/dgf-model/templates/settings.xml`.

- [x] **Task 15: Write `/dgf-audit`.** (depends on 11)
  - `skills/dgf-audit/SKILL.md` per DD14.
  - Logging: none.
  - Files: `skills/dgf-audit/SKILL.md`.

- [x] **Task 16: Wire the readers, the slices and the templates test.** (depends on 12–15)
  - Implement DD15. Run the full suite, `python3 skills/dgf-doctor/scripts/doctor.py` and
    `bash tools/check-dual-schema-docs.sh`: all green, and the doctor lists the four slices as present.
  - Logging: none.
  - Files: `tests/test_skill_contracts.py`, `tests/test_doctor.py`, `tests/test_skill_templates.py`,
    `skills/dgf-evolve/SKILL.md`, `skills/dgf-evolve/references/OVERRIDE-FORMAT.md`,
    `skills/dgf-doctor/scripts/doctor.py`, `skills/dgf-implement/SKILL.md`, `skills/dgf-plan/SKILL.md`.

### Phase 6: Proof and documentation

- [x] **Task 17: Walk every new skill's worked example against its scripts, then run every check.** (depends on 8, 16)
  - For each of the four skills, build a small root with `helpers.make_root` (or a scratch copy of a known-bad
    fixture). Run each step's command exactly as the SKILL.md writes it, and check each exit row it names against the
    script's real exit (`.ai-factory/RULES.md` rule 4). Fix the skill where they differ.
    - Walk each writing mode's scope STOP (`CHANGE_OUT_OF_SCOPE`) and its partition STOP.
  - Then run, and paste the tails into the implementation notes:
    - the unit suite;
    - the doctor;
    - `tools/check-dual-schema-docs.sh`;
    - `tools/check_knowledge_stamps.py`;
    - `tools/check_drift.py <DGF>`;
    - `tools/run_known_good.py <DGF>` (CLEAN).
  - Logging: none.
  - Files: the four `SKILL.md` files, if a walk finds a difference.

- [x] **Task 18: Documentation checkpoint.** (depends on 17) Route through `/aif-docs`.
  - `docs/pipeline.md`:
    - a section "The DGF-specific skills": what each does, the scripts it runs, what it writes, and D8's partition
      table;
    - the diagram;
    - the `.dgf-factory/` table (overrides read by ten);
    - "blast radius is `/dgf-audit`'s", with its limits.
  - `README.md`: what exists, and the command examples.
  - `AGENTS.md`: tree, entry points, "Not yet created", "six readers" (`:129`) → ten, ADR list.
  - Every other "six readers" line: `docs/pipeline.md:18` (the diagram) and `:259`, `docs/skill-authoring.md:69`, and
    `.ai-factory/DESCRIPTION.md:42`. `docs/adr/README.md:33` moves with Task 2's index row.
  - `docs/architecture.md` (tree, readers), `docs/getting-started.md` ("What is not here yet"),
    `docs/skill-authoring.md` (readers, the `dgf-component` example made real, and an `audit_root.py` row in the
    script-output table at `:113-123`), and `docs/dgf-knowledge.md` (the three new files).
  - `docs/blueprint.md`: dated `(decided 2026-09-27, ADR 0023)` corrections to the phase-2 rows, `/dgf-model`'s
    `[assume]`, the `processes/` line (`:322`, D17) and the gate ids never built (`:333`). The question text is never
    edited.
  - `.ai-factory/ARCHITECTURE.md`:
    - the tree and the slice list;
    - its stale `Bash(python3 *)` example at `:309`, which the contract test would refuse;
    - the `validate_component.py` sketch at `:61-68` and `:323`, which is not what was built.
  - `.ai-factory/DESCRIPTION.md`: Current State.
  - `.ai-factory/ROADMAP.md`:
    - the milestone text says the four skills are built and `/dgf-scaffold` alone is blocked, with a link to this plan;
    - the checkbox stays open;
    - D20's items join Follow-ups.
  - Run `bash tools/check-dual-schema-docs.sh`: CLEAN.
  - Logging: none.
  - Files: those named above.

## Risks

- **R1 — ADR 0024 is churn for one list.** About twenty files move a citation. The move is mechanical, and the grep in
  Task 2 proves it complete. If D7 is reversed at review, Task 2 goes, and the four skills drop their override blocks.
- **R2 — The model validator may find many sample defects.** 1746 `extract` tables across the three workspaces is a lot
  of surface. Task 8's stop at 50 keeps a validator gap from being excused wholesale.
- **R3 — Reach under-reports, and readers may trust it.** `LIMIT:` is on every reach report, `AUDIT_REFERENCE_DYNAMIC`
  marks chains that cross a run-time name, and the skill never calls a reach complete.
- **R4 — The graph mirrors engine code.** `HumanWorkflow`, `TableManager`, `LookUpViewManager` and the rest can change.
  Each is in a provenance ledger, so `check_drift.py` catches a change.
- **R5 — Three rules for `BASE:`.** Workflows and processes match it ordinally; tables, grids and views in any case,
  after the name is cleaned; a dialog has no base at all. One shared helper would get two of them wrong. Task 6 tests
  each loader's rule on its own, `BASE:dbo.X` included.
- **R9 — The override header cites a superseded ADR.** It stays `(ADR 0021)` after ADR 0024 supersedes 0021, because
  it is an enforced format (D7). A reader may take it for a stale citation. The comment above `WRITTEN` and ADR 0024 §3
  say why it stays, and a test pins it.
- **R10 — The DD4 table was drafted before its loaders were read in full.** The `/aif-improve` pass corrected six rows
  (E16). Task 4 re-reads every class, and no script names an edge kind in code, so a corrected row changes only the
  table.
- **R6 — More writers.** `/dgf-component`, `/dgf-process` and `/dgf-model` write workspace files beside
  `/dgf-implement` and `/dgf-fix`. The scope script decides before each write, and D8 gives each artifact one writing
  skill. The checkbox ledger keeps one owner.
- **R7 — The milestone stays open.** Only identifying the template closes it (D1).
- **R8 — Context cost.** Four more skill descriptions load in every session, and a whole-root audit parses every file in
  every application. `--app` exists for iteration, and is marked narrowed.

## Follow-ups

- `/dgf-plan` runs `audit_root.py --reach` for tasks that touch a shared workflow, and writes the reached processes into
  the plan as regression notes.
- Promote the `reference-edges` rows whose `Checked by` is `—` from audit warnings to validator checks, where their
  `When absent` is `throws`: today `sub-workflow`, `invoke-table`, `record-table`, `island-table` and
  `datasource-step`. This extends ADR 0014's deferred list, whose `Process/@table` item E16 closes as a database table
  name.
- Trace entry points outside processes: `_PROFILE` `OpenForm`/`CreateForm`/`CustomActionsXml`, sitemaps, `_form.xml` and
  view `WORKFLOW:` strings, and JSON `workflow` components. `profile.xsd` does not compile, so this needs a grammar first.
- A role check, if an estate ever keeps its roles list in the root.
- `inventory_root.py` counts entities per workspace.
- Read a `settings.xml` with a DTD as `XmlSerializer` does. `model.read_entity` decodes the file as
  `File.ReadAllTextAsync` does since the sixth `/aif-verify`, but still refuses a DTD, which the runtime accepts. On
  such a file the entity-load check reports `NOT RUN`, and the generated-file checks do not run
  (`knowledge/data-model.md` §3.6; found by the fourth `/aif-verify`).
- Check what XmlSerializer refuses before `Table.InitFields` runs: a child element in `primarykey`, a root that is
  not `entity` in no namespace, a `required` that is not an xsd:boolean, a `type` no `FieldTypeEnum` member names, an
  `xml:space` other than `preserve` or `default`, `version="1.1"`, and UTF-16 with no byte-order mark, which the
  runtime reads as UTF-8. Each makes the load throw; today `settings.xsd` warns on some, and `validate_model.py`
  reports none (the fifth and sixth `/aif-verify`'s .NET differentials).
- Honour `xsi:nil` as XmlSerializer does. `xsi:nil="true"` on `fields` binds no fields, on a `field` a null one, and
  on the root makes `Deserialize` return null — each a load that throws or returns nothing. `model.read_entity`
  ignores it, so the entity-load check passes all three (the sixth `/aif-verify`).
- Parse every XML file the validators read as the runtime reads it. The shared parser (`family.xml_parser`, lxml)
  follows the declaration's encoding, so it reports `XML_MALFORMED` on files the runtime loads: UTF-8 bytes declared
  `UTF-16` — the header .NET's `StringWriter` writes — non-ASCII text declared `us-ascii`, bytes `windows-1252`
  leaves undefined, and UTF-32 with a byte-order mark. It also refuses a prefix or the default namespace bound to the
  XML namespace, which .NET's reader allows. It accepts `version="1.1"`, which .NET refuses. Every validator is
  affected, not only `validate_model.py` (the sixth `/aif-verify`).
- Match `XmlDocument.LoadXml` in `model._parse_error` where expat cannot be told to: a prefix or the default
  namespace bound to the XML namespace, and a surrogate pair written as two character references. LoadXml takes
  both and the generated file loads; expat refuses both, so the reference is blocked as throwing
  (`knowledge/data-model.md` §3.6; the sixth `/aif-verify`).
- A reference into an entity whose own load throws blocks at the referrer too. Today the entity's `settings.xml`
  is blocked, once (`MODEL_ENTITY_UNLOADABLE`), and a reference into it still resolves, since the file is there. So
  an entity already broken at the merge-base lets a new reference to it pass the gate, and the referrer's view, grid
  or form warning says the runtime generates a default, which it cannot: the table's load throws first.
- Leave XML outside every `FM/` out of the audit's validator run, as draft JSON is. Today a malformed
  `a/tools/_workflow.xml` is validated, and its `FAMILY_UNRESOLVED` is demoted to exit `1`, a defect in the root,
  though no loader reads the file (the fifth `/aif-verify`).
- `graph._parse` returns no references for a file it cannot read (`OSError`, caught there for JSON and in
  `process_checks.parse` for XML), so a reach through it reads as complete. Say so in the report instead, as the
  audit's validators catch does for a validator that raises.
- `/dgf-scaffold`, once ADR 0004's template is identified.

## Implementation Notes

Recorded by `/aif-implement`, 2026-09-27.

- **Task 3 — two runtime facts differed from the draft, and the knowledge states the code** (ledger:
  `provenance/knowledge/data-model.md`):
  - A grid resolves like a lookup view. `EditableGridManager.GetXmlFilePath` does not clean a name itself, but
    every load goes through `TableManager.LoadAsync` first and passes the cleaned `table.Name` (D11, R5 and the
    Task 6 test "the raw table name kept" assumed otherwise). `model.resolve_grid` cleans, and its test says why.
  - A bound cell that names no field **throws** (`Form.InitFields` → `AddFields`), so the form does not load. Only a
    cell with no `name` is the tolerated empty cell. By ADR 0023 §3's own rule, `MODEL_CELL_UNBOUND` is exit `1`,
    not DD7's `2`, and it has a known-bad case (`model-cell-unbound`).
- **Task 4 — the table grew where the runtime required it**: `state-process` became `change-state-process`
  (`validate_process.py` checks only `CHANGE_STATE`) and `start-process` (`START`/`INFO`, `Checked by` `—`); a
  missing `StateProcess` target is `caught`, a fifth `When absent` value; `multitask-settings` lets a walk reach a
  MultiTask file from its process; `invoke-form` has its own rule for the `/READONLY` suffix. Which `Assign` names
  make which edges dynamic is a third machine-read table, `run-time-names`, so no script names an edge kind.
- **Task 7 — one shared reader, `scripts/lib/edges.py`**, reads a row's references for both `validate_model.py` and
  `graph.py`. A two-part reference whose table is the problem is not reported a second time (`restates_its_table`).
- **Task 11 — reach over DGF's samples agrees with E3.** Running `zims`, 49 shared workflows are reached by more than
  one process, the widest `webasm/AX.Notify` by 11; running `dgf`, 21. Counting only process actions and
  `SubWorkflow` calls gives E3's 126 reachable / 109 shared (`zims`) and 40 shared (`dgf`) exactly. The graph finds
  one more in each, `webasm/EDefaultProcessValidation`, reached only through a `validationFlow`, which D18 walks
  and E3's scan did not. The whole-root audit takes about 10 s over the samples.
- **Task 17 — each skill walked against its scripts** (a scratch set-up root on a git branch, every command run
  as the SKILL.md writes it). Every exit row held: `locate_plan.py` 0 with a root and 1 `ROOT_NOT_SET_UP` without;
  `check_override.py` 0 `OVERRIDE: none` for all four; `check_plan.py` 1 `PLAN_BASE_REASON_MISSING` for a webasm
  plan with no reason, then 0; `route_means.py` 0 with a `ROUTE:` naming `_workflow.xml`/`process.xml`/`settings.xml`
  for the partition STOPs, and 3 `ROUTE_NO_ROW`; the scope STOPs — `CHANGE_UNDECLARED_WORKSPACE` and
  `CHANGE_OUT_OF_SCOPE` exit 1, `CHANGE_UNPLANNED_FILE` exit 2; a removed field clean in `validate_model.py` alone
  but `MODEL_CELL_UNBOUND` exit 1 in the whole-root `check_change.py`; `audit_root.py` 0, 2 with `AUDIT_NARROWED`,
  3 with `AUDIT_REACH_NOT_ARTIFACT` and with `--skip-validators` on a reach, no block, no file written. **One
  difference, fixed in the skill:** a modify that points a `SubWorkflow` at a missing target passes
  `validate_process.py` and `check_change.py`, since no validator checks that edge yet; `/dgf-process` Step 7 now
  runs `audit_root.py --skip-validators` and corrects an `AUDIT_REFERENCE_UNRESOLVED` in the file it wrote.
- **Task 12 — `list_components` is not in `/dgf-component`'s `allowed-tools`.** DD11's frontmatter lists
  it, but the skill never calls it, and D13 pre-approves only the MCP tools a skill calls.
  `docs/skill-authoring.md` shows the frontmatter as built (reconciled by the seventh `/aif-verify`).
- **Task 17 — a writing mode without git, and a malformed file, walked by the seventh `/aif-verify`.**
  With no git the whole-root `check_change.py` counts every finding as new, so `/dgf-process` modify and
  `/dgf-model` add or modify stopped on any old defect in a file they never touched. The seventh round's
  fix compared the two runs in prose. The eighth `/aif-verify` found that this broke `rules/base.md`'s
  Determinism rule, and that an old exit-`3` file still masked a new break. So, by the user's
  decision of 2026-09-28 ([ADR 0025](../../docs/adr/0025-saved-baseline-without-git.md)),
  `check_change.py --save-baseline` saves the run before the write and `--baseline` settles the run
  after it, as against a merge-base. `/dgf-process` now confirms an author over the whole root too.
  A written file that exits `3` with `FAMILY_UNRESOLVED`, or with `SCHEMA_UNSELECTABLE` naming its
  root, is sent back for correction instead of to "a missing dependency".
- **Task 17 — the checks**, 2026-09-27, DGF `cccd4325b`:

  ```text
  unit suite        Ran 795 tests … OK   (without lxml/jsonschema: OK, skipped=218)
  doctor            Errors: 0  Warnings: 0  Info: 18 — dgf-component, dgf-process, dgf-audit, dgf-model present
  docs check        Errors: 0  Warnings: 1 — VALIDATOR_DEPS_MISSING: its doctor pass runs the system python3
  stamps            Files checked: 10  Errors: 0  Warnings: 0  CLEAN
  drift             Ledgers: 10  Sources: 321  Warnings: 0  CLEAN
  known-good        excused by EXCEPTION: 99, by EXPECTED_EXTERNAL: 9 — CLEAN
  ```
