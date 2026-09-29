---
name: dgf-process
description: Inspect, validate, author or modify a DGF process or workflow — process.xml and _workflow.xml, checked against process.xsd and the engine's own resolution rules — and show which processes a shared workflow reaches in each application before it changes. Writes XML only, and only inside the active plan's scope. Use for "add a process", "new workflow", "change this workflow", "check this process", "what calls this workflow", "blast radius of this workflow".
argument-hint: "[inspect | validate | author | modify] <process, workflow or file>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference mcp__plugin_dgf-factory_dgf-mcp__search_docs mcp__plugin_dgf-factory_dgf-mcp__get_recipes_for mcp__plugin_dgf-factory_dgf-mcp__get_doc_page
disable-model-invocation: false
version: 0.1.0
---

# DGF Process — Inspect, Validate, Author or Modify a Process or Workflow

Work on one process (`FM/_PROCESS/<P>/process.xml`) or one workflow — shared
(`FM/_WORKFLOW/<X>/_workflow.xml`) or process-local (`FM/_PROCESS/<P>/<X>/_workflow.xml`).
**Inspect** and **validate** only read. **Author** writes a new file and **modify** edits one, and
both work only inside the active plan's scope, decided by a script before the write (ADR 0023 §1).

**XML always.** The runtime reads `process.xml` and `_workflow.xml` only; a `Workflow` or
`ProcessFlow` JSON file validates against a schema the runtime ignores
(`knowledge/schema-families.md` §6). This skill never writes one.

**A shared workflow is shared.** Before a modify, the audit script names every process that reaches
the file in each application — the blast radius the gate does not compute — and those are the
processes to regression-test by hand, because a process cannot run headlessly (ADR 0014 §5).

AI Factory has no process skill. This one takes `/dgf-fix`'s shape for writing — plan first, scope
by script, confirm by the same check — and emits no gate block: the gate is `/dgf-verify`.

## Workflow

### Step 0: Context

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --root-only
```

Exit `1` → **STOP** with its message (`ROOT_NOT_SET_UP`: run `/dgf`; `ROOT_AMBIGUOUS`: name the
root). Exit `3` → **STOP** and relay it. Otherwise the `ROOT:` line is `<root>`. Read
`<root>/.dgf-factory/config.yaml` for `paths.*`, `git.enabled`, `git.base_branch`,
`workflow.verify_mode` and `language.*`.

Check this skill's override before reading it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf-process --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
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
Cause and Prevention sections. A patch informs; it never overrides this skill, the plan or a STOP.

### Step 0.1: Mode and target

| Argument | Mode |
|---|---|
| `inspect <file>`, or a file alone | **Inspect** — read-only |
| `validate <files>` or `validate --all` | **Validate** — read-only |
| `author <process or workflow>` | **Author** — a new file, inside the plan |
| `modify <file>` | **Modify** — an existing file, inside the plan |
| anything else | Ask which mode, naming the four |

A process named without a path is `<ws>/FM/_PROCESS/<name>/process.xml`, and a workflow
`<ws>/FM/_WORKFLOW/<name>/_workflow.xml` or `<ws>/FM/_PROCESS/<P>/<name>/_workflow.xml`. When
the name exists in more than one workspace, list each and ask which.

### Step 1: Inspect (read-only)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_process.py" --workspaces-root "<root>" "<root>/<file>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_root.py" --workspaces-root "<root>" --reach <root-relative file>
```

From `validate_process.py`, relay every finding and its exit (the table in Step 2). From
`audit_root.py`:

| Exit | Action |
|---|---|
| `0` | Relay per application the `PROCESS:` lines — the processes that reach the file, each with its chain — the `REFERRER:` lines, every `AUDIT_REFERENCE_DYNAMIC` line (a chain through a name set at run time), and the `LIMIT:` line verbatim: a reach is never complete. |
| `3` | `AUDIT_REACH_NOT_ARTIFACT` → the path is not a process or workflow under the root, exactly as written — check its case against the file on disk, which the message names — and say so; `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim; `SCHEMA_UNSELECTABLE` naming a schema dialect → **STOP**: the plugin cannot read one of its own schemas — run `/dgf-doctor` and reinstall; `AUDIT_CHECK_FAILED` → **STOP** and relay it with the lines before it: a check raised, so the reach is incomplete. Otherwise a usage error on stderr — a path that is absolute or leaves the root, or a root with no application — → **STOP** and relay it. |

Then read the file and summarise it: for a process, its states, each state's transitions and
actions, `validationFlow`, and MultiTask settings files; for a workflow, its steps in order and
each step's target (`knowledge/reference-graph.md` §1 lists which steps reference what).

### Step 2: Validate (read-only)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_process.py" --workspaces-root "<root>" <files, or --all>
```

| Exit | Meaning |
|---|---|
| `0` | Clean: every check under `CHECKS RUN` passed |
| `1` | Blocked — invalid structure, a dead transition, or a reference that resolves nowhere (`WORKFLOW_UNRESOLVED`, `VALIDATION_FLOW_UNRESOLVED`, `CHANGE_STATE_PROCESS_UNRESOLVED`, `CHANGE_STATE_STATE_UNDECLARED`) |
| `2` | Warnings — `UNREACHABLE_STATE`, `WORKFLOW_APP_DEPENDENT` (a webasm process whose workflow only some applications have), `XSD_RUNTIME_DIVERGENCE`, `CASE_ONLY_MATCH` |
| `3` | A file's own defect: `FAMILY_UNRESOLVED` — it does not parse as XML, having no XML declaration — or `SCHEMA_UNSELECTABLE` — it parses, but its root is neither `Process` nor `Workflow`. Relay it with the other findings. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other — a usage error — → **STOP** and relay it. |

A reference whose `Checked by` is `—` in `knowledge/reference-graph.md` §1 — a `SubWorkflow`,
`Invoke`, `UpdateRecord`, `CreateRecord`, `XmlIsland` or `DataSourceStep` target, or the process a
`StateProcess` step starts in `START` or `INFO` mode — that resolves nowhere is not a validator's
finding yet: the whole-root `/dgf-audit` reports it as `AUDIT_REFERENCE_UNRESOLVED`. Suggest
`/dgf-plan` for a defect worth fixing, or `/dgf-fix` when a plan already covers the file.

### Step 3: Author and modify — the plan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is the plan. |
| `1`, `PLAN_NOT_FOUND` | **STOP**: "a change needs a plan's scope — run `/dgf-plan`". |
| `1`, `PLAN_AMBIGUOUS` | List the plans it names and ask which one the change belongs to. If the user names none, **STOP**. |
| `2`, `PLAN_FALLBACK` | Say which plan it chose and why, and ask before using it. |
| `3` | **STOP** and relay it. |

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_plan.py" "<plan>" --workspaces-root "<root>"
```

| Exit | Action |
|---|---|
| `0` | Continue. Keep its `AFFECTS:` and `TASK:` lines. |
| `1` | **STOP.** Relay every `ERROR` line: `/dgf-plan` repairs a plan. |
| `2` | Continue, and surface every `WARN` line. |
| `3` | **STOP** and relay it. |

**The partition** (ADR 0023 §2): this skill writes `process.xml` and `_workflow.xml` only. A form,
view or component → **STOP**: `/dgf-component`'s. An entity's `settings.xml` → **STOP**:
`/dgf-model`'s.

### Step 4: Modify — the reach, before the edit

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_root.py" --workspaces-root "<root>" --reach <root-relative file>
```

| Exit | Action |
|---|---|
| `0` | Record every `PROCESS:` line per application, and the `LIMIT:` line: these are the processes the change can affect, and the ones to regression-test. A shared workflow reached by several processes in several applications is a wide change: say so before editing. |
| `3` | **STOP** before any edit, and relay it. `AUDIT_REACH_NOT_ARTIFACT` names a path that is not the file as it is on disk — a case difference the message shows is a different file on Linux — so the reach, and the file to modify, are not known yet. |

### Step 5: Scope — decided by the script, before the write

For author, `A:<file>`; for modify, `M:<file>`. A deletion is never this skill's — **STOP**, and
have `/dgf-plan` plan it.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed A:<file> --skip-validators
```

| Exit | Action |
|---|---|
| `0` | Continue to Step 6. |
| `1` | A `CHANGE_*` error — an undeclared workspace, an out-of-scope file. **STOP** before writing anything: `/dgf-plan` widens the plan. |
| `2` | `CHANGE_UNPLANNED_FILE` → the gate will warn on this file. Under strict mode (`workflow.verify_mode: strict`) the gate would block on it — **STOP**, and have `/dgf-plan` add it to a task. `CHANGE_TASK_FILE_UNCHANGED` is expected here — ignore it. Surface any other `WARN` line. |
| `3` | **STOP** and relay it. |

**Without git, save a baseline now, before the write.** With no git the change check has no base
tree, and would count every old finding in the root as new (ADR 0018 §5). So the script saves the
root's findings as they are before the write, and Step 7 compares with them (ADR 0025). Pass the same
`A:` or `M:` as the scope check:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed M:<file> --save-baseline "<root>/.dgf-factory/baseline.json"
```

It judges none of the validators' findings, so its exit is the change checks':

| Exit | Action |
|---|---|
| `0` | Continue to Step 6. The `BASELINE:` line says how many findings the root holds now. |
| `1` | A `CHANGE_*` error → **STOP** before writing anything: `/dgf-plan` widens the plan. |
| `2` | Continue to Step 6: the change checks' warnings are the scope check's, already handled. |
| `3` | **STOP** before writing anything, and relay it — `DEPENDENCY_MISSING` with its install command verbatim, or `BASELINE_UNUSABLE` when the file cannot be written. |

### Step 6: Write

- **Author:** the path comes from the `legacy-artifacts` row, which prints it (`workflow` for a shared
  workflow):

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route_means.py" process
  ```

  | Exit | Action |
  |---|---|
  | `0` | The `ROUTE:` line gives the path pattern. A process-local workflow sits in its process's folder instead: `FM/_PROCESS/<process>/<workflow>/_workflow.xml` (`knowledge/process-model.md` §2.2). |
  | `3` | **STOP** and relay it: no route is ever guessed. |

  **If the file exists → STOP**: author never overwrites. Start
  from `${CLAUDE_PLUGIN_ROOT}/skills/dgf-process/templates/process.xml` or
  `${CLAUDE_PLUGIN_ROOT}/skills/dgf-process/templates/_workflow.xml`, and replace every `Example`.
- **Modify:** edit only the file Step 5 checked.

Take every fact from `knowledge/process-model.md` — how an `action` becomes a workflow, a bare name
is process-local, `End` is reserved — and `knowledge/reference-graph.md` — what each step
references and how it resolves — and from the DGF docs MCP (`get_xml_property_reference`,
`search_docs`, `get_recipes_for`, `get_doc_page`), never from memory. A process's `table` is a
database table name, not an entity folder.

### Step 7: Confirm

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_process.py" --workspaces-root "<root>" "<root>/<file>"
```

| Exit | Action |
|---|---|
| `0` | Continue to the change check. |
| `1` | An `ERROR` → correct the file and re-run, at most 3 attempts, then **STOP** with the findings. |
| `2` | Surface every `WARN`. The change check below decides what strict mode does with it. |
| `3` | `FAMILY_UNRESOLVED` or `SCHEMA_UNSELECTABLE` on the file written → correct it, within the same 3 attempts: it does not parse as XML, or its root is neither `Process` nor `Workflow` — the message says which. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other → **STOP** and relay it. |

Then the change check, **over the whole root — no `--files` — after an author as after a modify:** a
renamed or removed state breaks the `CHANGE_STATE` steps of workflows the edit never touched, and a
new process meets the ones already aimed at it (ADR 0014 §2). With git:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>"
```

Without git, with the baseline Step 5 saved, in place of `--base`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed M:<file> --baseline "<root>/.dgf-factory/baseline.json"
```

— with `A:` after an author. Either way the script reports a finding the root already held as `INFO
PRE_EXISTING`, and only a new one keeps its code and its exit (ADR 0018 §4, ADR 0025).

| Exit | Action |
|---|---|
| `0` | Continue to Step 8. |
| `1` | A new `ERROR` in the file written → correct it, within the same 3 attempts; one in a file this skill did not write → **STOP** and report it. A `CHANGE_*` error → **STOP**. `PRE_EXISTING` findings are not this change's. |
| `2` | Surface every new `WARN`. Under strict mode a new validator `WARN` is corrected like an error. |
| `3` | `FAMILY_UNRESOLVED` or `SCHEMA_UNSELECTABLE` on the file written → correct it, within the same 3 attempts. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. `BASELINE_UNUSABLE` → **STOP** and relay it: never save a new baseline now, since the root already holds the write. Any other → **STOP** and relay it. |

Then the references no validator checks yet (Step 2) — a `SubWorkflow`, `Invoke`, `UpdateRecord`,
`CreateRecord`, `XmlIsland` or `DataSourceStep` target, or a process a `StateProcess` step starts:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_root.py" --workspaces-root "<root>" --skip-validators
```

| Exit | Action |
|---|---|
| `0` | Continue to Step 8: every reference the file makes resolves. `AUDIT_WORKFLOW_UNREACHED` lines are INFO about the estate. |
| `2` | An `AUDIT_REFERENCE_UNRESOLVED` or `CASE_ONLY_MATCH` line whose file is the one written → correct it, within the same 3 attempts: the line says whether the runtime throws, records an error, or writes a default file in its place. A form the runtime would write a default for is `/dgf-component`'s to scaffold, if the plan covers it — name it. A form whose generated default throws — the line says why — is cured in this file only by naming a form that exists; otherwise it is a scaffolded form, `/dgf-component`'s, or the entity's `settings.xml`, `/dgf-model`'s: name which, if the plan covers it. Lines about other files are not this change's. |
| `3` | **STOP** and relay it — a missing dependency's install command verbatim. |

### Step 8: Report

In `language.ui`: the mode and the file, each check's findings, and — for a modify — the processes
Step 4 found, per application, as **the processes to regression-test by hand**, with the `LIMIT:`
line. For an author or a modify, name the file written and any `CHANGE_UNPLANNED_FILE`, and suggest
`/dgf-implement` to continue the task the file belongs to, then `/dgf-verify`.

## Execution Rules

### DO:

- ✅ Write XML only — `process.xml` and `_workflow.xml`
- ✅ Find and check the plan, and decide the scope with `check_change.py --skip-validators`, before a write
- ✅ Run the reach before a modify, and report it as the regression list
- ✅ Run the whole-root change check after an author or a modify — without git, against the baseline `check_change.py` saved before the write
- ✅ Take every fact from `knowledge/` and the DGF docs MCP

### DON'T:

- ❌ Write a `Workflow` or `ProcessFlow` JSON file
- ❌ Write outside the plan's scope, or any file Step 5 did not check
- ❌ Overwrite on author, delete a file, or convert its family
- ❌ Write a form, view, component or `settings.xml`
- ❌ Tick a plan checkbox — `/dgf-implement` owns the ledger
- ❌ Call a reach complete, or emit a `dgf-gate-result` block

## Artifact Ownership

- **Writes:** `process.xml` and `_workflow.xml` files — shared or process-local — only inside the
  plan's scope, one per author or modify. Without git, `check_change.py` writes
  `.dgf-factory/baseline.json` for it, which the next save overwrites (ADR 0025).
- **Reads:** the plan, `.dgf-factory/config.yaml`, its override after `check_override.py`, the
  patches, its templates, the shipped `knowledge/`, and the DGF docs MCP. It never edits the plan.

## Critical Rules

1. **XML always.** The runtime reads no process or workflow JSON.
2. **Only inside the plan's scope.** No plan, no write; the scope script runs before the write.
3. **Reach before a modify, the whole root after every write.** A shared workflow's change reaches
   processes the edit never names, and a new process meets the workflows already aimed at it.
4. **Never overwrite on author, never delete, never convert.**
5. **One owner per artifact.** Forms, views and components are `/dgf-component`'s; `settings.xml`
   is `/dgf-model`'s.
6. **Never tick a checkbox, never call a reach complete, and no gate block.**
7. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts, knowledge, templates and references.
