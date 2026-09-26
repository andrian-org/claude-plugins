---
name: dgf-implement
description: Execute a dgf-factory plan task by task — compose DGF configuration (modern JSON first, legacy XML where the route says so, a little JavaScript or CSS only for kind code tasks), validate each task against the merge-base, and tick the plan's checkboxes. Use for "implement the plan", "dgf implement", "continue implementation", "execute the plan", "next task".
argument-hint: "[--list] [@plan] [task-id | status]"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) Bash(git *) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_component_doc mcp__plugin_dgf-factory_dgf-mcp__get_json_schema_details mcp__plugin_dgf-factory_dgf-mcp__get_component_examples mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference
disable-model-invocation: false
version: 0.2.0
---

# DGF Implement — Execute the Plan

Carry out the plan `/dgf-plan` wrote, one task at a time. Every decision — workspace, file,
family, reference, reason — is already in the plan. This skill composes what it says, checks
each task with the validators, and ticks the checkbox. **The executor never re-decides:** when
the estate disagrees with the plan, it stops and reports the drift.

What it writes is configuration: component JSON under `FM/_COMPONENTS/`, legacy XML where the
route says XML, and a little JavaScript or CSS only for a `kind: code` task, only in a file the
plan names. It never writes C#, TypeScript, Angular, SQL or plugin source (ADR 0010 §3).

This skill ports AI Factory's `/aif-implement`. It drops Handoff, `TaskList` mirroring (the
plan's checkboxes are the only ledger), `--without-plan` (every change needs the scope only a
plan carries), research drift, roadmap and docs checkpoints, and worktree merging.

## Workflow

### Step 0: Arguments

| Argument | Meaning |
|---|---|
| (none) | the next task of the discovered plan |
| `--list` | `locate_plan.py --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>" --list` — print every plan with its progress, then **STOP**. Change nothing. |
| `@<path>` | this plan entrypoint — a `.md` file, an ultra bundle directory, or its `index.md` — instead of discovery |
| `<N>` | start at Task N, if its dependencies are checked |
| `status` | Steps 0–2 only: show progress, then **STOP** |

### Step 0.0: Resume

Rebuild state from disk, never from memory — the user may have run `/clear`. This step needs
the root and the plan, so run it once Steps 0.1–1 have found them. With git, one command per
call:

```bash
git -C "<root>" status --porcelain
```

```bash
git -C "<root>" log --oneline -10
```

Compare the plan's checkboxes (Step 2) with what changed. Changes to an unchecked task's files
mean that task was started: re-read its files before continuing it. If the tree holds changes
that no task of this plan lists, show them and ask: commit them first (`/dgf-commit`), stash
them, or cancel. Never discard them.

### Step 0.1: Context

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --root-only
```

Exit `1` → **STOP** with its message (`ROOT_NOT_SET_UP`: run `/dgf`). Otherwise read
`<root>/.dgf-factory/config.yaml` and `DESCRIPTION.md`.

An override holds project rules that apply to every file this skill writes.
Check this skill's override before reading it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf-implement --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
```

| Exit | Action |
|---|---|
| `0` | `OVERRIDE: none` → there is no override. Otherwise read the file it names, and apply it. |
| `1` | **Refused.** Do not read or apply it. Name it in your report with each `ERROR` line; the shipped rules alone apply. |
| `2` | Read and apply it. Judge each rule an `OVERRIDE_TOUCHES_LIMIT` line names against the limit below. |
| `3` | **STOP** and relay it: the call is wrong. |

An override may add rules and tighten checks. It never relaxes a STOP, an exit-code row, the status a gate script
computes, a Critical Rule or Artifact Ownership, and never makes this skill install anything, skip a script, or write
outside its own artifacts. Name the override in your report, and quote any rule in it you did not apply because it
would relax one of these.

Then read the last 10 files in `<root>/<paths.patches>` by name, if there are any — their Root
Cause and Prevention sections — and avoid what they record. A patch informs; it never overrides
this skill, the plan or a STOP.

### Step 0.2: Find the plan

Skip this step for `@<path>`. Otherwise, with the config's paths:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is the plan (`source=branch`). |
| `1` | **STOP** with its message: `PLAN_NOT_FOUND` → run `/dgf-plan`; `PLAN_AMBIGUOUS` → name one with `@<path>`. |
| `2` | `PLAN_FALLBACK`: say which plan it chose and why (`source=lone` or `source=fast`), and ask before using it. |

### Step 1: Load and check the plan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_plan.py" "<plan>" --workspaces-root "<root>"
```

| Exit | Action |
|---|---|
| `0` | Continue. |
| `1` | **STOP.** The plan is defective. Relay every `ERROR` line; `/dgf-plan` fixes the plan. Implementing a defective plan is re-deciding it. |
| `2` | Continue, and surface every `WARN` line. |
| `3` | **STOP.** Relay it: an unreadable header, or a usage error. |

For ultra, also read `index.md` in full: its `## Decisions` and `## Open Questions`. An open
question means the bundle is not implementation-ready — **STOP** and send it back to
`/dgf-plan`.

### Step 2: Progress

Build the display from the `TASK:` and `PROGRESS:` lines, in the format of
`${CLAUDE_PLUGIN_ROOT}/skills/dgf-implement/references/IMPLEMENTATION-GUIDE.md`. The next task
is the first unchecked one whose dependencies are all checked, or Task N when given. When no
task is unchecked, go to Step 5. For `status`, **STOP** here.

### Step 3: Execute the task

#### 3.1 Read

Read the task line and its field bullets. For ultra, read the task's **whole** phase file: its
Current-Artifact Evidence, Steps, Route, Validation and Acceptance are requirements.

Then read every file in the task's `files` that exists. If the estate disagrees with the plan's
evidence — an element, state or key it names is not there, a file it calls existing is missing,
a file it calls new exists — **STOP and report the drift**. Do not choose a new approach.

#### 3.2 Route each file

- **An existing file keeps its family.** Read it with:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_config.py" "<root>/<file>"
  ```

  and take its `FAMILY:` line. Edit it in that family; never convert it. Exit `3` with
  `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim.
- **A new configuration file follows its route.** Run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route_means.py" <Type, loader folder or legacy artifact>`
  — for a file under `FM/_COMPONENTS/<Folder>/`, pass `<Folder>` — and confirm the plan's path
  matches its `ROUTE:` line: `json` under `<ws>/FM/_COMPONENTS/<Type>/`, `xml` at the legacy
  artifact's folder and filename. A mismatch is drift: **STOP**. Exit `2` is
  `PARITY_PARTIAL`: say which part of the component stays XML. Exit `3` → **STOP**.
- **A `kind: code` file** is written only where the plan names it — a form's `_form.js`, or an
  existing file under `js/`, `FM/js/` or `css/` (`check_plan.py` accepted it). CSS reaches a
  component through its `CssClass` property.
- **A file the task does not list is never touched.** If the task cannot be done without one,
  **STOP** and ask for a re-plan.

#### 3.3 Compose

Take every fact from the shipped knowledge and the DGF docs MCP, never from memory:

- `${CLAUDE_PLUGIN_ROOT}/knowledge/component-catalogue.md` — which components the runtime
  dispatches;
- `${CLAUDE_PLUGIN_ROOT}/knowledge/json-reader.md` — how the runtime reads component JSON, and
  how a component file reference resolves (§2.1);
- `${CLAUDE_PLUGIN_ROOT}/knowledge/composition-specs.md` — artifact folders (§1–§2), the
  `EventBase` verbs and DataFetcher (§3), where script and style load from (§5);
- `${CLAUDE_PLUGIN_ROOT}/knowledge/process-model.md` — how process and workflow references
  resolve (§2), and the reserved `End` (§3);
- the vendored schemas under `${CLAUDE_PLUGIN_ROOT}/knowledge/schemas/` — `json/` for component
  JSON, `xsd/` for legacy XML;
- the DGF docs MCP: `get_component_doc`, `get_json_schema_details`, `get_component_examples`,
  `get_xml_property_reference`.

Write the files. For a `deletes` entry, with git: `git -C "<root>" rm -q "<file>"`. Without
git, **STOP** and ask the user to delete it; this skill has no other delete.

If the change turns out to need C#, TypeScript, Angular, SQL, a plugin assembly or deployment
configuration, **STOP the task**: write nothing for it, and report what code the plan needs and
why. That work belongs to a general coding flow (ADR 0010 §3).

#### 3.4 Validate

With git:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>" --files <the task's files that exist>
```

**A task with `deletes`** runs the same command without `--files`: the whole root is the only run
that shows what the removal broke — a process that still names the deleted workflow, say.

Without git, give the change set yourself — `A:` for a file this task created, `M:` for one it
edited, `D:` for one it deleted:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed A:<file> M:<file> --files <the task's files that exist>
```

Again, leave out `--files` for a task with `deletes`.

| Exit | Action |
|---|---|
| `0` | Continue to 3.5. |
| `1` | A **new** `ERROR` in a file this task wrote → fix it and run the check again, at most 3 attempts, then **STOP** with the findings. A `CHANGE_*` error (an undeclared workspace, an unplanned or new code file, an out-of-scope file) → **STOP**: the change left the plan. |
| `2` | Continue; surface every new `WARN`. |
| `3` | **STOP** and relay it — a missing dependency's install command verbatim. |

`INFO PRE_EXISTING` lines were there before the branch: mention how many, and never fix them
unasked — they are not this task's. This run covers only the task's files; it is a fast check,
never the gate. `/dgf-verify`'s whole-root run is the gate. Re-run with `--verbose` when a
finding is unclear.

#### 3.5 Mark

Change the task's `- [ ]` to `- [x]` in the plan entrypoint (`index.md` for ultra), with
`Edit`, immediately. That checkbox is the only write this skill makes to the plan.

#### 3.6 Commit checkpoint

When the plan's `## Commit Plan` puts a commit after this task, suggest `/dgf-commit` with its
message. Otherwise continue with the next task (Step 2).

### Step 4: Pausing

Everything is on disk: the files and the checkboxes. To pause, say what is done and what is
next; `/dgf-implement` resumes from Step 0.0.

### Step 5: Completion

When every task is checked, report the plan, the files written, and every `PRE_EXISTING`
count, and suggest **`/dgf-verify`** — the whole-root gate — before `/dgf-commit`.

## Execution Rules

### DO:

- ✅ Check the plan with `check_plan.py` before the first task
- ✅ Read the files and, for ultra, the whole phase file before editing
- ✅ Keep each existing file in its family; route each new one
- ✅ Validate every task with `check_change.py`, and fix only the new errors in its own files
- ✅ Tick each checkbox immediately after the task validates

### DON'T:

- ❌ Re-decide a workspace, a family, a component or a reference the plan fixed
- ❌ Touch a file no task lists, or convert a file's family
- ❌ Write C#, TypeScript, Angular, SQL, plugin source or deployment configuration
- ❌ Create a file under `js/`, `FM/js/` or `css/`
- ❌ Fix `PRE_EXISTING` findings unasked
- ❌ Edit the plan beyond its checkboxes, or any other skill's artifact
- ❌ Write reports or summary files

## Artifact Ownership

- **Owns:** the plan's task checkboxes — and nothing else in the plan.
- **Writes:** the workspace files the current task lists in `files`, and removes those in
  `deletes`.
- **Reads:** the plan, `.dgf-factory/config.yaml` and `DESCRIPTION.md`, the skill-context
  override and patches when present, the shipped `knowledge/`, and the DGF docs MCP.

## Critical Rules

1. **The executor never re-decides.** Drift between the plan and the estate stops the task.
2. **Configuration first, code only as planned.** `kind: code` is the plan's decision, with its
   reason; this skill never promotes a task to code.
3. **Out-of-scope code stops the task** (ADR 0010 §3). Report what is needed; write none of it.
4. **Every task is validated** before its checkbox is ticked. A task that does not validate is
   not done.
5. **The per-task check is not the gate.** Only `/dgf-verify`'s whole-root run can pass one.
6. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts, knowledge and schemas.
