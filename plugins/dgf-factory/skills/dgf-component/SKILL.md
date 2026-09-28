---
name: dgf-component
description: Inspect, validate or scaffold a DGF component — modern JSON under FM/_COMPONENTS or a legacy form, view, grid or options file — in both schema families and parity-aware, writing only inside the active plan's scope. Use for "add a component", "check this component", "is this component valid", "scaffold a DataTable", "what uses this component".
argument-hint: "[inspect | validate | scaffold] <file, Type/name or Type>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_component_doc mcp__plugin_dgf-factory_dgf-mcp__get_json_schema_details mcp__plugin_dgf-factory_dgf-mcp__get_component_examples mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference mcp__plugin_dgf-factory_dgf-mcp__build_form_xml
disable-model-invocation: false
version: 0.1.0
---

# DGF Component — Inspect, Validate or Scaffold a Component, in Both Families

Work on one piece of component configuration: a modern JSON component under
`FM/_COMPONENTS/<Type>/<name>.json`, or a legacy form, table view, lookup view, grid form or
options file under `FM/_DATA/<table>/`. **Inspect** and **validate** only read, and run anywhere
in a workspaces root. **Scaffold** writes one new file, and only inside the active plan's scope,
decided by a script before the write (ADR 0023 §1).

Every file keeps its family, and a passing JSON schema is not the runtime reading JSON: parity is
checked by the script, not assumed. A process or a workflow is `/dgf-process`'s to write, and an
entity's `settings.xml` is `/dgf-model`'s (ADR 0023 §2).

AI Factory has no component skill: it is framework-agnostic. This skill takes the shape of
`/dgf-fix` for writing — plan first, scope by script, confirm by the same check — and adds the
DGF docs MCP for composition. It emits no gate block: the gate is `/dgf-verify`.

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
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf-component --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
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
| `inspect <file or Type/name>`, or a file alone | **Inspect** — read-only |
| `validate <files or directories>` | **Validate** — read-only |
| `scaffold <Type> [<name>]` | **Scaffold** — writes one new file, inside the plan |
| anything else | Ask which mode, naming the three |

A `Type/name` target is found by an exact-case glob of `<root>/*/FM/_COMPONENTS/<Type>/<name>.json`.
List **every** match — the same name in two workspaces is two files — and ask which one when there
is more than one. No match → say so, and offer `scaffold`.

### Step 1: Inspect (read-only)

Run each, and relay what it says:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_config.py" "<root>/<file>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_components.py" "<root>/<file>"
```

| Exit | Action |
|---|---|
| `0` | Relay the `FAMILY:` line — the file's family, `json` or `xsd` — and any `INFO` line. |
| `1` | Relay every `ERROR` line: each is a defect the file has now. Inspect on. |
| `2` | Relay every `WARN`. `PARITY_NOT_RUNTIME` or `PARITY_PARTIAL` → the runtime does not read this component from JSON, or reads part of it from XML: say it plainly, whatever the schema says. `XSD_LAGS_RUNTIME` is advisory: the legacy grammar lags the runtime (ADR 0016). |
| `3` | `FAMILY_UNRESOLVED` → the file's own defect: it parses as neither family — not XML or JSON at all, or XML whose root no XSD reads; the message says which. Relay it, and inspect on: the route, the reach and, for a form, `validate_model.py` still apply. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other → **STOP** and relay it. |

For the route a new component of this type would take, and its parity row:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route_means.py" <Type or legacy artifact>
```

| Exit | Action |
|---|---|
| `0` | Relay the `ROUTE:` line: the family and where a new one would go. |
| `2` | Relay it with its `PARITY_PARTIAL` warning: part of the component is still read from XML. |
| `3` | `ROUTE_NO_ROW` → say that no route is known for the type, and inspect on without one. |

For what uses it — the processes that reach the file in each application, and its direct
referrers:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_root.py" --workspaces-root "<root>" --reach <root-relative file>
```

| Exit | Action |
|---|---|
| `0` | Relay its `PROCESS:` and `REFERRER:` lines per application, any `AUDIT_REFERENCE_DYNAMIC` note, and its `LIMIT:` line verbatim: a reach is never complete. |
| `3` | `AUDIT_REACH_NOT_ARTIFACT` → the path is not a configuration file under the root, exactly as written — check its case against the file on disk, which the message names — and say so; `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim; `SCHEMA_UNSELECTABLE` naming a schema dialect → **STOP**: the plugin cannot read one of its own schemas — run `/dgf-doctor` and reinstall; `AUDIT_CHECK_FAILED` → **STOP** and relay it with the lines before it: a check raised, so the reach is incomplete. Otherwise a usage error on stderr — a path that is absolute or leaves the root, or a root with no application — → **STOP** and relay it. |

For a legacy form, check that its entity's `settings.xml` is there and every bound cell names one of its fields — whether the entity itself loads is its `settings.xml`'s own check (`/dgf-model`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_model.py" --workspaces-root "<root>" "<root>/<file>"
```

| Exit | Action |
|---|---|
| `0` | The form's entity `settings.xml` is there. With `form-cells` under `CHECKS RUN`, every bound cell names a field; with it under `NOT RUN`, relay that line — the cells were not checked, because that `settings.xml` does not parse, which its own validation reports. |
| `1` | Relay every `ERROR`: `MODEL_CELL_UNBOUND` is a cell the form fails to load on, `MODEL_REFERENCE_UNRESOLVED` an entity `settings.xml` that is not there, so the form does not load. |
| `2` | Relay every `WARN`. |
| `3` | **STOP** and relay it — `DEPENDENCY_MISSING` with its install command verbatim. |

Then read the component's documentation with `get_component_doc` for its type. Summarise: the
family, parity, the checks' findings, who reaches it, and what the component does.

### Step 2: Validate (read-only)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_config.py" <files or directories>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_components.py" <files or directories>
```

Both families are validated: a directory walk collects the component JSON and the legacy artifact
files alike. Relay every `ERROR` and `WARN` line, and each script's exit:

| Exit | Meaning |
|---|---|
| `0` | Clean in both checks |
| `1` | Blocked — an `ERROR` line names each defect, for example `COMPONENT_FILE_UNRESOLVED` |
| `2` | Warnings — parity, a lagging grammar, an unknown property the runtime ignores |
| `3` | `FAMILY_UNRESOLVED` → a file's own defect: it parses as neither family — the message says why. Relay it with the other findings. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other — a usage error — → **STOP** and relay it. |

Suggest `/dgf-plan` for a defect worth fixing, or `/dgf-fix` when a plan already covers the file.

### Step 3: Scaffold — the plan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is the plan. |
| `1`, `PLAN_NOT_FOUND` | **STOP**: "a new file is a change, and a change needs a plan's scope — run `/dgf-plan`". |
| `1`, `PLAN_AMBIGUOUS` | List the plans it names and ask which one the file belongs to. If the user names none, **STOP**. |
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

### Step 4: Scaffold — the route and the owner

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route_means.py" <Type or legacy artifact>
```

| Exit | Action |
|---|---|
| `0` | The `ROUTE:` line gives the family and the path pattern. |
| `2` | The same, with a `PARITY_PARTIAL` warning: part of the component is still read from XML. Say which part. |
| `3` | `ROUTE_NO_ROW` → **STOP**: no route is ever guessed. |

**The partition** (ADR 0023 §2). A route to
`process.xml` or `_workflow.xml` → **STOP**: that is `/dgf-process`'s. A route to an entity's
`settings.xml` → **STOP**: that is `/dgf-model`'s. Everything else — a JSON component, a `form`,
`table-view`, `lookup-view`, `grid-form` or `options` file — is this skill's.

Fill the path pattern: `<workspace>` is one of the plan's `affects_workspaces`, and the names come
from the user. The file's path is `<ws>/FM/…`, root-relative. **If the file exists → STOP**: a
scaffold never overwrites, and an edit belongs to a plan task (`/dgf-implement`) or to `/dgf-fix`.

### Step 5: Scaffold — scope, decided by the script before the write

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed A:<file> --skip-validators
```

| Exit | Action |
|---|---|
| `0` | Continue to Step 6. |
| `1` | A `CHANGE_*` error — an undeclared workspace, an out-of-scope file. **STOP** before writing anything: `/dgf-plan` widens the plan. |
| `2` | `CHANGE_UNPLANNED_FILE` → the gate will warn on this file. Under strict mode (`workflow.verify_mode: strict`) the gate would block on it — **STOP**, and have `/dgf-plan` add it to a task. `CHANGE_TASK_FILE_UNCHANGED` is expected here — ignore it. Surface any other `WARN` line. |
| `3` | **STOP** and relay it. |

### Step 6: Scaffold — compose and write

Compose from the DGF docs MCP and the shipped knowledge, never from memory:

- **JSON:** read `get_json_schema_details` for the component's schema and `get_component_examples`
  for its type, then write the smallest valid file. The `type` key is exact-case: the member name
  as `knowledge/json-reader.md` §2 spells it. Property names and enum member names match in any
  case (§1 there), but write them as the schema spells them — except an enum member with a custom
  JSON name, such as `LinkTarget`'s `_blank`: it is read only as that name, exactly, and never by the
  C# name the schema lists (§1's `enum-member-names` table).
- **A legacy form:** build it with `build_form_xml` from a FormSpec, then adjust it by hand from
  `get_xml_property_reference`. Every bound cell names a field of the entity
  (`knowledge/data-model.md` §4): a cell that names no field makes the form fail to load.
- **A view, grid form or options file:** from `get_xml_property_reference` and the entity's fields.

Write only the file Step 5 checked.

### Step 7: Scaffold — confirm

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_config.py" "<root>/<file>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/resolve_components.py" "<root>/<file>"
```

For a form, also:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_model.py" --workspaces-root "<root>" "<root>/<file>"
```

Each script's exit:

| Exit | Action |
|---|---|
| `0` | Continue to the change check. |
| `1` | An `ERROR` → correct the file and re-run, at most 3 attempts, then **STOP** with the findings. |
| `2` | Surface every `WARN`, a `PARITY_*` one said plainly. The change check below decides what strict mode does with it. |
| `3` | `FAMILY_UNRESOLVED` → the file written parses as neither family — JSON cut short, or XML that is not well-formed or whose root no XSD reads; the message says which: correct it, within the same 3 attempts. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other → **STOP** and relay it. |

Then the change check over the new file — with git:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>" --files <file>
```

— without git, `--changed A:<file> --files <file>` in place of `--base`.

| Exit | Action |
|---|---|
| `0` | Continue to Step 8. |
| `1` | A new `ERROR` in the file → correct it, within the same 3 attempts. A `CHANGE_*` error → **STOP**. |
| `2` | Surface every `WARN`. Under strict mode a new validator `WARN` is corrected like an error. |
| `3` | **STOP** and relay it. |

### Step 8: Report

In `language.ui`: the mode, the file or files, the family, parity, each check's findings, the
reach for an inspected file with its `LIMIT:` line, the override applied or refused, and — for a
scaffold — the file written and any `CHANGE_UNPLANNED_FILE`. After a scaffold, suggest
`/dgf-implement` to continue the task the file belongs to, then `/dgf-verify`.

## Execution Rules

### DO:

- ✅ Resolve the family first, and handle both — JSON and legacy XML
- ✅ Relay `PARITY_*` warnings: a schema that validates is not the runtime reading it
- ✅ Find and check the plan, and decide the scope with `check_change.py --skip-validators`, before a scaffold writes
- ✅ Compose from the DGF docs MCP and `knowledge/`, and confirm with the same scripts
- ✅ Relay every `LIMIT:` line of a reach, verbatim

### DON'T:

- ❌ Write outside the plan's scope, or any file Step 5 did not check
- ❌ Overwrite, delete or convert a file's family
- ❌ Write a process, a workflow or an entity's `settings.xml`
- ❌ Tick a plan checkbox — `/dgf-implement` owns the ledger
- ❌ Call a reach complete, or emit a `dgf-gate-result` block

## Artifact Ownership

- **Writes:** one new component file per scaffold — JSON under `FM/_COMPONENTS/`, or a legacy
  `form`, `table-view`, `lookup-view`, `grid-form` or `options` file — only inside the plan's scope.
- **Reads:** the plan, `.dgf-factory/config.yaml`, its override after `check_override.py`, the
  patches, the shipped `knowledge/`, and the DGF docs MCP. It never edits the plan.

## Critical Rules

1. **Both families, always, and parity from the script.** Never default to JSON; never read a
   passing schema as runtime support.
2. **Only inside the plan's scope.** No plan, no scaffold; the scope script runs before the write.
3. **Never overwrite, delete or convert.** An existing file is an edit, and an edit is a plan task's.
4. **One owner per artifact.** Processes and workflows are `/dgf-process`'s; `settings.xml` is
   `/dgf-model`'s.
5. **Never tick a checkbox, and no gate block.**
6. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts, knowledge and references.
