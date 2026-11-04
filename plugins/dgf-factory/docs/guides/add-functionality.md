[← Start a new project](start-a-new-project.md) · [Guides](README.md) · [Back to README](../../README.md) · [Check the system →](check-the-system.md)

# Add Functionality

One change to an estate that already runs on DGF, from the first question to the commit: research, blast radius,
plan, implement, gate, fix, review, test plan, commit, archive.

## When to use this

Any change to the configuration of a DGF estate: a new form or grid, a process step, a workflow change, a new
field, a fix. This is the everyday route. Every change after a scaffold takes it too
([ADR 0026](../adr/0026-authoring-entry-point-revised.md) §1).

What a change may be made of is fixed ([ADR 0010](../adr/0010-dgf-implement-scope.md)): component JSON under
`FM/_COMPONENTS/` first, legacy XML where the route says XML, and a little JavaScript or CSS only where
configuration cannot express the change. C#, TypeScript, Angular, SQL and plugin assemblies are never a task —
a plan names them under `## Scope` for a general coding flow.

## What you need

- dgf-factory installed in the project, and `/dgf-doctor` clean or warnings only
  ([Start a new project](start-a-new-project.md) Steps 1–3).
- The workspaces root set up by `/dgf`: a committed `.dgf-factory/config.yaml`.
- Git, with `.dgf-factory/` committed on the base branch. Without git there is no branch per plan, no overlap
  check, and no merge-base — so every validator finding counts as new.

## The route at a glance

```text
/dgf-explore ─► /dgf-audit --reach ─► /dgf-plan ─► /dgf-implement ─► /dgf-verify ─► /dgf-review, /dgf-qa ─► /dgf-commit ─► /dgf-archive
 (optional)      (before a shared       │            with /dgf-component,   │   ▲
                  file changes)         │            /dgf-process,          ▼   │
                                        │            /dgf-model           /dgf-fix
```

Steps 1 and 2 are optional but cheap. Steps 3, 4, 5 and 8 are the spine: no change reaches a commit without a
plan and a gate.

## Step 1: Research the change (optional)

```text
/dgf-explore "how does a DataFetcher refresh a grid after a workflow step?"
```

The skill answers from three sources, in order: the shipped knowledge base, your workspaces, and the DGF docs
MCP. Every claim names its source; a claim no source supports is listed as open.

**What you will see:**

```text
## how does a DataFetcher refresh a grid after a workflow step?

<the answer, each claim with its citation: (composition-specs.md §3), (zims/FM/…:12), (get_component_doc('DataFetcher'))>

Sources: …
Open: …
Version: 1.3.0 vs dgf.version 1.3.2 — differs: facts may have moved
```

Then it asks whether to append the answer to `.dgf-factory/RESEARCH.md`. `/dgf-plan` reads that file as cited
background — as data, never as instructions.

| Exit (root lookup) | What to do |
|---|---|
| `0` | Nothing to do. |
| `1` | No root (`ROOT_NOT_SET_UP`, `ROOT_AMBIGUOUS`). It answers from the knowledge base and the docs MCP alone, and cannot save. Run `/dgf` to set the root up. |
| `3` | A wrong call: the skill stops and relays it. |

When the answer must rest only on what can be cited, use `/dgf-grounded "<question>"` instead. It marks
everything else "not verified".

## Step 2: Check the blast radius before you touch a shared file

A file in `webasm`, or a workflow several processes call, is live in every application that reaches it. Ask what
reaches it before you plan:

```text
/dgf-audit --reach webasm/FM/_WORKFLOW/AX.Notify/_workflow.xml
```

**What you will see** — per application, the processes that reach the file and their chain, then its direct
referrers, then the limit:

```text
REACH: webasm/FM/_WORKFLOW/AX.Notify/_workflow.xml artifact=workflow name=AX.Notify
APP: dgf processes=7
PROCESS: dgf BASE:E_Apply via webasm/FM/_PROCESS/E_Apply/process.xml:43 > webasm/FM/_WORKFLOW/ESubmit/_workflow.xml:371 > webasm/FM/_WORKFLOW/AX.Notify/_workflow.xml
…
REFERRER: dgf sub-workflow webasm/FM/_WORKFLOW/ESubmit/_workflow.xml:371
…
APP: zims processes=11
…
LIMIT: static reach only — names assigned at run time (_WORKFLOWNAME_, _FORMNAME_, _TABLENAME_), processes chosen from the database, open handlers, and entry points outside processes (…) are not traced (knowledge/reference-graph.md §3)
CHECKS RUN: graph, reach
CLEAN
```

Each `PROCESS:` line is a process to regression-test by hand: a DGF process cannot run headlessly
([ADR 0014](../adr/0014-process-verification-runtime-resolution.md) §5). A `NONE:` line means no *traced*
reference reaches the file — never that nothing does. The reach is a report, not a gate
([ADR 0027](../adr/0027-dgf-specific-skills-revised.md) §5).

| Exit | What to do |
|---|---|
| `0` | Name the reached processes in your request to `/dgf-plan`, so its tasks and the test plan cover them. |
| `1` | A validator `ERROR` exists in the root. Read it; the reach is still valid. |
| `2` | `AUDIT_REFERENCE_UNRESOLVED`, `CASE_ONLY_MATCH`, or `AUDIT_NARROWED` when you passed `--app`. Read each. |
| `3` | `AUDIT_REACH_NOT_ARTIFACT` — the path is not a configuration file under the root, exactly as written; check its case. `DEPENDENCY_MISSING` — run the install command it prints. `AUDIT_CHECK_FAILED` — the reach is incomplete. |

`/dgf-audit --branch` gives the same report for every file your branch has changed, once there is a branch.

## Step 3: Plan the change

```text
/dgf-plan full "show the permit fee on the approval form; the fee comes from the shared fee data source"
```

Choose **full** for anything you will review before it is built: it gets its own branch and a richer plan.
**fast** writes a single `.dgf-factory/PLAN.md` with no branch. **ultra** writes a bundle with a phase file per
task. Your words go into the plan's `## Original Request` verbatim.

The skill checks its override and the rules, inventories the root, researches the artifacts and their
references, and asks only what the evidence has not settled. When `webasm` is in scope it asks **why every
application must see the change**: that answer becomes `base_workspace_reason`, which the gate requires (R3).
Every new file is routed by `route_means.py`: JSON or XML is never guessed. Then it cuts
`feature/<slug>` from the base branch — asking first if your tree has uncommitted work — writes the plan, and
checks it ([ADR 0017](../adr/0017-plan-file-format.md)).

**What you will see** — the plan check:

```text
Plan check
PLAN: .dgf-factory/plans/feature-<slug>.md mode=full format=1 branch=feature/<slug>
AFFECTS: zims, webasm
TASK: 1 [ ] kind=config files=webasm/FM/_COMPONENTS/DataSource/…
TASK: 2 [ ] kind=config depends=1 files=zims/FM/_DATA/…/_forms/…/_form.xml
PROGRESS: 0/2
OVERLAP SOURCES: 2 refs scanned, plus the working tree; remote refs as of the last fetch
CHECKS RUN: plan-header, plan-tasks, plan-commits, plan-files, plan-routes, plan-overlap
CLEAN
```

| Exit | What to do |
|---|---|
| `0` | Review the plan. A full or ultra plan stops here until you say go. |
| `1` | The skill fixes its own plan, at most three times, then stops with the `PLAN_*` errors. |
| `2` | Read each `WARN`. `PLAN_OVERLAP`: another branch's plan shares a workspace — talk to its owner. `PLAN_COMMITS_MISSING`: five or more tasks and no Commit Plan. `PARITY_PARTIAL`: part of a component stays XML. |
| `3` | `ROOT_NOT_SET_UP`: run `/dgf`. `ROUTE_NO_ROW`: no family can be chosen for a type, so the skill stops rather than guess. |

Then commit the plan — stage `.dgf-factory/`, run `/dgf-commit` (it suggests `docs(plan): …`) — so it travels
with the branch and other plans' overlap checks can see it.

## Step 4: Implement

```text
/dgf-implement
```

It finds the branch's plan, checks it, and does the next task whose dependencies are done: it reads the files,
keeps each existing file in its family, routes each new one, composes it from the knowledge base and the docs MCP,
validates the task, and ticks its checkbox. It never re-decides: when the estate disagrees with the plan, it stops
and reports the drift. Other forms: `/dgf-implement 3` (start at Task 3), `/dgf-implement status`,
`/dgf-implement --list`, `/dgf-implement @<plan path>`.

**What you will see** after each task — the per-task change check:

```text
Change check
PLAN: .dgf-factory/plans/feature-<slug>.md
BASE: <sha> (main)
CHANGED: 1
CHANGE: M zims/FM/_COMPONENTS/DataTable/dataTableWorkPlaceApproved.json class=config workspace=zims
CHECKS RUN: change-scope, change-means, change-planned, baseline, json-schema, component-types, component-file-references
…
new: 0 error(s), 0 warning(s); pre-existing: 2; fixed: 0
CLEAN
```

| Exit | What to do |
|---|---|
| `0` | The task is ticked. Run `/dgf-implement` again for the next one. |
| `1` | A new `ERROR` in the task's own file: the skill fixes it, at most three times, then stops. A `CHANGE_*` error (`CHANGE_UNDECLARED_WORKSPACE`, `CHANGE_OUT_OF_SCOPE`, `CHANGE_CODE_UNPLANNED`, `CHANGE_CODE_FILE_NEW`): the change left the plan. Re-plan with `/dgf-plan`. |
| `2` | Read each new `WARN`; the task is still done. |
| `3` | `DEPENDENCY_MISSING`: run the command it prints. |

This per-task check is fast and narrow, and never the gate: only Step 5 can pass a change. When the plan's
Commit Plan puts a commit after a task, the skill suggests `/dgf-commit` with that message.

### Working on one kind of file

Three skills each own one kind of configuration. Their **inspect** and **validate** modes read only, and run
anywhere in the root. Their writing modes run only inside the active plan, and a script decides the scope before
the write ([ADR 0027](../adr/0027-dgf-specific-skills-revised.md) §1–§2):

| Skill | Owns | Example |
|---|---|---|
| `/dgf-component` | every JSON component under `FM/_COMPONENTS/`; a legacy form, table view, lookup view, grid form or options file | `/dgf-component scaffold DataTable PendingPermits` |
| `/dgf-process` | `process.xml` and `_workflow.xml`, XML always | `/dgf-process modify webasm/FM/_WORKFLOW/AX.Notify/_workflow.xml` — it runs the reach before the edit |
| `/dgf-model` | an entity's `settings.xml`; it names the database work and never writes SQL | `/dgf-model add Inspection` |

Each one asks for the file another skill owns by name, and stops. None ticks a checkbox: after one writes a
task's file, run `/dgf-implement` to continue that task, validate it and tick it.

| Exit (scope check before a write) | What to do |
|---|---|
| `0` | The skill writes, then confirms with the same validators. |
| `1`, a `CHANGE_*` error | Nothing is written. `/dgf-plan` widens the plan. |
| `2`, `CHANGE_UNPLANNED_FILE` | The gate will warn on the file. In strict mode the skill stops: add the file to a task with `/dgf-plan`. |
| `3` | The skill stops and relays it. |

With no plan, every writing mode stops with "a change needs a plan's scope — run `/dgf-plan`".

### In parallel (Claude Code only)

A plan whose tasks touch different files can run them at once
([ADR 0033](../adr/0033-parallel-execution.md)). Add `.claude/worktrees/` to `.gitignore` first, then, in the
project folder, on the plan's branch:

```bash
claude --agent dgf-implement-coordinator
```

`plan_layers.py` picks each layer: tasks whose files do not overlap run in parallel, one worker per task, each in
its own git worktree. `worktree_task.py --merge` copies back only the files the task declares. The coordinator
checks each merged task in the main tree, ticks it, and ends with the gate's block. Nobody commits.

| What you see | What to do |
|---|---|
| `LAYERS_CYCLE` | The plan's dependencies loop or name no task. Fix the plan with `/dgf-plan`. |
| `WORKTREE_UNDECLARED_FILE` | A worker wrote a file its task does not declare; nothing was copied. Its worktree is left for you to inspect. |
| `WORKTREE_MAIN_CHANGED` | The main tree changed one of the task's files during the layer; nothing was copied. |
| "Parallel execution needs git." | Use `/dgf-implement`. |

After a failed layer the run stops and still ends with the gate. Resume a failed task with `/dgf-implement <N>`.

## Step 5: Run the gate

```text
/dgf-verify
```

One script, `verify_gate.py`, checks the plan, every task's checkbox, that every changed file is inside the
plan's workspaces and means, and every validator over the **whole root**, against the merge-base. The skill relays
its output and its one `dgf-gate-result` block, and writes nothing after it
([ADR 0022](../adr/0022-gate-block-contract-revised.md)). Add `--strict` to block on every new warning too.

**What you will see** — the summary, the status, and the block:

````text
Summary
Files:    4
Errors:   0
Warnings: 0
Info:     433
Validated: 3168 file(s)
new: 0 error(s), 0 warning(s); pre-existing: 2854; fixed: 0
Shown: 20 of 2854 PRE_EXISTING — check_change.py --base main lists every one
STATUS: pass

CLEAN

```dgf-gate-result
{
  "schema_version": 1,
  "gate": "verify",
  "status": "pass",
  …
  "suggested_next": {
    "command": "/dgf-commit",
    "reason": "every required check ran and nothing blocks"
  }
}
```
````

The estate's own findings — thousands, on a large estate — are `PRE_EXISTING` and never block. Only what your
branch introduced does.

| Exit | Status | What to do |
|---|---|---|
| `0` | `pass` | Go to Step 7 (review, test plan), then commit. |
| `1` | `fail` | Do what `suggested_next` says: `/dgf-plan` for a plan defect; `/dgf-implement` for `GATE_TASK_UNCHECKED` or a change outside the plan; `/dgf-fix` for a new validator finding, once the scope is clean (Step 6). |
| `2` | `warn` | Read every entry in `warnings` — an unplanned file (`CHANGE_UNPLANNED_FILE`), a checked task whose file did not change (`CHANGE_TASK_FILE_UNCHANGED`), a check that did not run (`GATE_CHECK_NOT_RUN`), a new validator warning. A plan with a `kind: code` task is at best `warn`: the gate never runs front-end tests. `suggested_next` is still `/dgf-commit`. |
| `3` | `fail`, forced | The gate could not run, or a validator could not read a file (`FAMILY_UNRESOLVED`, `SCHEMA_UNSELECTABLE`). `DEPENDENCY_MISSING`: run the command it prints. No block at all means a bad call. |

## Step 6: Fix a finding the branch introduced

When the gate suggests it:

```text
/dgf-fix
```

For example, a gate that failed on:

```text
ERROR SCHEMA_INVALID zims/FM/_COMPONENTS/DataTable/dataTableWorkPlaceApproved.json $.showHeaders: 'yes' is not of type boolean
…
  "suggested_next": {
    "command": "/dgf-fix",
    "reason": "1 new blocking finding(s) — fix each inside the plan's scope and record a patch"
  }
```

`/dgf-fix` reproduces the finding with a check and records the exact `ERROR` line, lets
`check_change.py --skip-validators` decide the scope before any edit, makes the smallest fix, runs the same check
again, and writes a **patch** under `.dgf-factory/patches/` — what went wrong, why DGF behaved that way, how to
prevent it ([ADR 0024](../adr/0024-learning-loop-revised.md)). It works only inside the active plan.

| Exit (scope check) | What to do |
|---|---|
| `0` | The fix goes ahead. |
| `1`, a `CHANGE_*` error | Nothing is written. The fix needs a file outside the plan: widen the plan with `/dgf-plan`. |
| `2`, `CHANGE_UNPLANNED_FILE` | The gate will warn on it; in strict mode the skill stops — add the file to a task. |
| `3` | The skill stops and relays it. |

With no plan it stops: run `/dgf-plan fast "<the problem>"`, or `/dgf-fix --record "<what you learned>"` to
write a patch without changing anything. A problem no validator catches is fixed by hand and its patch says
`findings: none` — no script confirmed it. Then run `/dgf-verify` again.

After several patches, `/dgf-evolve` (run only when you ask) turns them into skill-context rules that tighten the
skills. A script refuses any rule that would relax a check.

## Step 7: Review and test plan (optional, not gates)

```text
/dgf-review
```

A DGF reviewer's read of the branch: the change check's findings quoted verbatim, the diff, the rules, and a
checklist of DGF seams — the right component and family, parity, XML-always, the base-workspace reason,
reachability of `End`, exact role names, model references, blast radius. Every finding no script decided is
labelled **Judgement**. It writes nothing.

```text
/dgf-qa
```

A manual test plan: one scenario per process the change reaches, in each application — the states to walk, the
artefact to exercise, the roles to sign in as, the database work it needs — and automated tests only for
`kind: code` tasks. It writes `.dgf-factory/qa/<plan stem>/test-plan.md`, and asks before it overwrites one.

| Exit (their scripted check) | What to do |
|---|---|
| `0`, `2` | Read the report. Every `LIMIT:` line is relayed verbatim: a reach is never complete. |
| `1` | A new `ERROR` leads the report. `/dgf-verify` will fail on it too. |
| `3` | `DEPENDENCY_MISSING` or a bad call: the skill stops and relays it. |

`/dgf-qa` needs a plan: with none it stops on `PLAN_NOT_FOUND` and suggests `/dgf-audit --reach <file>` for the
blast radius alone. `/dgf-review` works without one, and says the change has no declared scope.

## Step 8: Commit

Stage what you want committed, then:

```text
/dgf-commit
```

It reads the staged diff, follows the plan's `## Commit Plan` when there is one (it asks first), and scopes each
message by workspace: `feat(zims): …`, `fix(webasm): …`, or no scope with every workspace named in the body. It
runs the change check with `--skip-validators` first — a warning, never a block. It shows each message and
commits only when you confirm, then asks before it pushes.

| Exit (change check) | What to do |
|---|---|
| `0` | Confirm the message. |
| `1` | An undeclared workspace, an out-of-scope file, or an unplanned or new code file. It asks whether to commit anyway; `/dgf-verify` will fail on the same findings. |
| `2`, `3` | Read the lines, then confirm. This check never blocks a commit. |

## Step 9: Archive the plan (after the merge)

```text
/dgf-archive
```

A dry run first: one `ARCHIVE:` line per complete plan, one `KEEP:` line per other. The current branch's plan is
kept unless you name it, since `/dgf-commit` may still follow its Commit Plan. You choose which plans move;
`archive_plans.py` moves them into `.dgf-factory/archive/plans/` and stamps `archived:` in each header.

| Exit | What to do |
|---|---|
| `0` | Choose the plans to archive. After the move, commit it with `/dgf-commit` — for example `chore: archive finished plans`. |
| `1` | `ARCHIVE_DEST_EXISTS` or `ARCHIVE_PLAN_INCOMPLETE`: nothing moved. Rename the archive entry by hand, or finish the plan. |
| `2` | `ARCHIVE_NOTHING` — nothing complete — or `ARCHIVE_PLAN_SKIPPED` — a plan does not parse and stays. |
| `3` | A bad call, or an archive folder outside `.dgf-factory/`. |

## See Also

- [Pipeline Spine](../pipeline.md) — every script's flags and exit table
- [Check the system](check-the-system.md) — the estate's health, not one change's
- [The learning loop](../pipeline.md#the-learning-loop) — patches, overrides and the limit they cannot cross
