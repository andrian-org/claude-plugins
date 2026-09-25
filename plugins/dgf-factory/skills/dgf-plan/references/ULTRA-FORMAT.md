# dgf-plan — Ultra Bundle Format

Use this reference only for `ultra` mode. An ultra bundle lets a strong planning model commit
every composition decision so that a smaller executing model can carry it out without
reconstructing intent. The executor never re-decides: when the workspaces disagree with the
bundle, it stops and reports the drift.

The header, task lines and field bullets are exactly those of `PLAN-FORMAT.md`. This file adds
the bundle layout, the phase files, and the gates a bundle must pass.

## Bundle layout

```text
.dgf-factory/plans/<stem>/
├── index.md
├── phase-01-<phase-slug>.md
├── phase-02-<phase-slug>.md
└── phase-NN-<phase-slug>.md
```

- `<stem>` is the `branch` with every `/` replaced by `-`, as for a full plan.
- The bundle holds `index.md` and direct child phase files only — no nested directories.
  `check_plan.py` reports a link to anything else as `PLAN_ULTRA_BROKEN`.
- Zero-pad phase numbers so lexical order is execution order.

## Sources of truth

- **`index.md` is the manifest, the scope anchor and the only progress ledger.** Its
  frontmatter carries `mode: ultra`, which is the bundle marker: there is no HTML-comment
  marker.
- **Task lines and their `kind`/`reason`/`files`/`deletes` bullets live only in `index.md`.**
  Phase files hold the detail and never a task checkbox.
- The ordered links under `## Phase Index` define which files belong to the bundle. An unlinked
  markdown file in the bundle is an orphan.
- Every `Task N` in `index.md` has exactly one `## Task N: …` section in one linked phase file.

## `index.md` template

```markdown
---
plan_format: 1
mode: ultra
branch: feature/zims-inspection-fee
created: 2026-09-25
affects_workspaces: [zims, webasm]
base_workspace_reason: "The fee DataSource is shared by every application's payment page"
---

# Implementation Plan: Inspection fee on the application form

## Original Request

<the user's words, verbatim>

## Scope

<why each workspace is in; what is out of scope and why>

## Decisions

- <a cross-phase decision: which workspace owns a shared artifact, which family, which
  reference form (`BASE:X`, `/X`, a process-local name) — with its evidence>

## Phase Index

1. [Phase 1: Fee data](phase-01-fee-data.md) — Tasks 1–2
2. [Phase 2: Behaviour](phase-02-behaviour.md) — Task 3

## Cross-Phase Dependencies

- Task 3 depends on Task 2 because the panel it hides is added by Task 2.

## Affected Artifacts

| Artifact | Workspace | State | Family | Route evidence |
|---|---|---|---|---|

## Commit Plan

<only when there are 5 or more tasks, as in `PLAN-FORMAT.md` — for example:>
- **Commit 1** (after tasks 1–3): `feat(zims): show the inspection fee`
- **Commit 2** (after tasks 4–6): `feat(zims): hide the fee until payment is confirmed`

## Tasks

### Phase 1: Fee data
- [ ] Task 1: [Add the inspection-fee DataSource](phase-01-fee-data.md#task-1-add-the-inspection-fee-datasource)
  - kind: config
  - files: webasm/FM/_COMPONENTS/DataSource/InspectionFee.json
- [ ] Task 2: [Show the fee on the application form](phase-01-fee-data.md#task-2-show-the-fee-on-the-application-form) (depends on 1)
  - kind: config
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.xml

### Phase 2: Behaviour
- [ ] Task 3: [Hide the fee panel until payment is confirmed](phase-02-behaviour.md#task-3-hide-the-fee-panel-until-payment-is-confirmed) (depends on 2)
  - kind: code
  - reason: No EventBase verb reads the gateway callback (knowledge/composition-specs.md §3.1)
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.js

## Open Questions

- <a decision the evidence could not settle — the bundle is not implementation-ready while
  any remain>

## Risks

## Definition of Done

- <completion criteria that are not tasks: `/dgf-verify` passes; …>
```

A task title may be a link to its phase section, as above. The link target must be a phase file
directly inside the bundle, with an optional `#anchor`.

## Phase file template

````markdown
# Phase N: <Name>

Plan: [index.md](index.md)
Tasks: N–M
Depends on: none | Phase N / Task N

## Objective

<the observable outcome this phase produces>

## Current-Artifact Evidence

| Path | Element / key | Existing family | Why it matters |
|---|---|---|---|
| `zims/FM/_DATA/Inspection/_forms/Apply/_form.xml` | `<Panel name="Payment">` | xml | the panel Task 2 extends |
| `webasm/FM/_PROCESS/Payment/process.xml` | `State name="Paid"` | xml | referenced as `BASE:Payment` by zims |

## Files to Change

| Path | Action | Required change |
|---|---|---|
| `zims/FM/_DATA/Inspection/_forms/Apply/_form.xml` | modify | add the fee field to `Payment` |

## Task N: <Deliverable>

### Intent

<why this task exists, and what later tasks depend on it>

### Steps

1. <a concrete edit in a named file and element or key>
2. <the exact reference to add — `type` + `name`, `WORKFLOW:/X`, `BASE:X` — and where it resolves>
3. <every consumer that must still resolve after the edit>

### Route

- New file: the exact `ROUTE:` line `route_means.py <Type|artifact>` printed.
- Existing file: its family on disk, from `validate_config.py`'s `FAMILY:` line. It stays in
  that family.
- `kind: code`: the `code-places` row (`form-script`, `global-script`, `global-script-base`,
  `global-style`) and the `CssClass` or event the code serves.

### Validation

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<index.md>" \
  --base "<base branch>" --files <this task's files>
```

Expected: no new `ERROR`; the named `PRE_EXISTING` findings, if any, unchanged.

### Acceptance

- <an observable, independently checkable result: the reference resolves, the state is
  reachable, the component renders with the new property>
````

This is the command `/dgf-implement` runs after the task when the estate uses git. Without
git it passes `--changed` with the task's files instead of `--base`, and for a task with
`deletes` it leaves out `--files`.

## Required Detail Gate

Before saving a bundle, every task must have:

1. **Exact paths** relative to the workspaces root, and the existing elements, keys or states it
   touches — or an explicit statement that a new file, element or state is introduced.
2. **Ordered edits** detailed enough to make without choosing a component, a family or a
   workspace.
3. **Every reference it adds or changes**, with where it resolves, and every consumer that must
   still resolve afterwards. A change in `webasm` names each application that uses it.
4. **The route**: the `ROUTE:` line for a new file, the on-disk family for an existing one, the
   code place for `kind: code`.
5. **A reason** for every `kind: code` task, citing the component doc, the schema or the
   `EventBase` verb list (`${CLAUDE_PLUGIN_ROOT}/knowledge/composition-specs.md` §3.1).
6. **Validation**: the exact `check_change.py … --files …` command, and the expected result.
7. **No choice hidden behind "handle", "support", "wire up", "as needed" or "etc."** A decision
   the evidence cannot settle goes under `## Open Questions` in `index.md`, and the bundle is
   not implementation-ready until it is answered.

And the bundle must pass `check_plan.py <index.md> --workspaces-root <root>`, exit `0` or `2`.
It checks the header, the tasks, every file's class and route, every Phase Index and task link,
and that:

- Every phase file is linked from `## Phase Index`; none is an orphan.
- Every indexed task has exactly one `## Task N` section, and every section's task is indexed.
- No phase file contains a task checkbox.

No script checks the Commit Plan yet. Read it before saving: its groups must agree with the
phase and task numbering.

## Consumer contract

- Read `index.md` first, then every phase file it links, in order, for a whole-plan check.
- Read a task's complete phase file before implementing that task.
- Update progress checkboxes only in `index.md`.
- When a phase file's evidence no longer matches the workspaces — a state renamed, a file
  moved, a family changed — **stop and report the drift**. Do not re-decide the plan.
- `@<path>` may name the bundle directory or its `index.md`; both mean the same bundle.
