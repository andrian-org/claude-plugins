---
name: dgf-model
description: Inspect, validate, add or modify a DGF entity — FM/_DATA/<entity>/settings.xml, its fields and its extract, relation and slavegrid references — checking every reference the way its loader resolves it, and naming the database work a change needs without writing SQL. Writes only inside the active plan's scope. Use for "add an entity", "add a field", "change this entity", "check the data model", "which forms use this entity", "what does this table need in the database".
argument-hint: "[inspect | validate | add | modify] <entity or settings.xml>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference mcp__plugin_dgf-factory_dgf-mcp__search_docs
disable-model-invocation: false
version: 0.1.0
---

# DGF Model — Inspect, Validate, Add or Modify an Entity

Work on one entity: the folder `FM/_DATA/<Entity>/` and its `settings.xml` — its data source, its
fields, and the references its fields make (`extract`, `relation`, `slavegrid`, `binding`).
**Inspect** and **validate** only read. **Add** writes a new `settings.xml` and **modify** edits one,
and both work only inside the active plan's scope, decided by a script before the write
(ADR 0023 §1).

**The references are checked the way each loader resolves them** (`knowledge/data-model.md` §3):
a table's name is cleaned before `BASE:` is tested, a dialog has no base path, and a missing table
or dialog throws while a missing view, grid or form is generated and written into the workspace —
unless that generation throws, which depends on the table's fields (§3.6).
`validate_model.py` blocks only where the loader throws (ADR 0023 §3).

**The schema is not in the workspaces root.** An entity's `datasource` names a database table or
view, and a relation's `table` a junction table (`knowledge/data-model.md` §1, §3.3): a change to
either is database work in the consumer's own database project (§5 there). This skill names that
work and never writes SQL (ADR 0010 §3).

AI Factory has no data-model skill. This one takes `/dgf-fix`'s shape for writing — plan first,
scope by script, confirm by the same check — and emits no gate block: the gate is `/dgf-verify`.

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
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf-model --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
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
| `inspect <entity or settings.xml>`, or one alone | **Inspect** — read-only |
| `validate <files>` or `validate --all` | **Validate** — read-only |
| `add <entity>` | **Add** — a new `settings.xml`, inside the plan |
| `modify <entity or settings.xml>` | **Modify** — an existing one, inside the plan |
| anything else | Ask which mode, naming the four |

An entity named without a path is `<ws>/FM/_DATA/<Entity>/settings.xml`. When it exists in more
than one workspace, list each and ask which.

### Step 1: Inspect (read-only)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_config.py" "<root>/<file>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_model.py" --workspaces-root "<root>" "<root>/<file>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_root.py" --workspaces-root "<root>" --reach <root-relative file>
```

- `validate_config.py` checks the file against `settings.xsd`:

  | Exit | Action |
  |---|---|
  | `0` | Relay the `FAMILY:` line: `xsd`. |
  | `1` | `XML_MALFORMED` → the file does not parse: relay it. Every break of `settings.xsd` is exit `2`, since that grammar lags the runtime. |
  | `2` | Relay every `WARN`. `XSD_LAGS_RUNTIME` is advisory: that grammar lags the runtime (ADR 0016). |
  | `3` | `FAMILY_UNRESOLVED` → the file's own defect: it does not parse as XML, or its root is one no XSD reads — the message says which. Relay it, and inspect on: `validate_model.py` still reads the file, and reports a file that does not parse as `XML_MALFORMED`. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other → **STOP** and relay it. |

- `validate_model.py` checks every reference (the table in Step 2).
- `audit_root.py` names, per application, the processes that reach the entity — through a form it
  owns, or a workflow step that loads its table — and its direct referrers: every other entity
  whose `extract` or `slavegrid` names it, every form that belongs to it, and every workflow step
  that names its table:

  | Exit | Action |
  |---|---|
  | `0` | Relay its `PROCESS:` and `REFERRER:` lines per application, and the `LIMIT:` line verbatim: a reach is never complete. |
  | `3` | `AUDIT_REACH_NOT_ARTIFACT` → the path is not an entity's `settings.xml` under the root, exactly as written — check its case against the file on disk, which the message names — and say so; `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim; `SCHEMA_UNSELECTABLE` naming a schema dialect → **STOP**: the plugin cannot read one of its own schemas — run `/dgf-doctor` and reinstall; `AUDIT_CHECK_FAILED` → **STOP** and relay it with the lines before it: a check raised, so the reach is incomplete. Otherwise a usage error on stderr — a path that is absolute or leaves the root, or a root with no application — → **STOP** and relay it. |

Then read the file and list its fields — name, `type`, and any `extract`, `relation`, `slavegrid` or
`binding` — and its `datasource` name, which is **a database object outside the root**. A `type`
must be a `FieldTypeEnum` member exactly (`knowledge/data-model.md` §2): any other value stops the
whole entity loading.

### Step 2: Validate (read-only)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_model.py" --workspaces-root "<root>" <files, or --all>
```

| Exit | Meaning |
|---|---|
| `0` | Clean: every reference resolves, and `Table.InitFields` accepts the entity's key and fields — as far as the checks ran. A `NOT RUN: entity-load` line means the file holds a DTD, or does not parse once decoded as the runtime decodes it, and its load was not checked: relay it. |
| `1` | Blocked — `MODEL_REFERENCE_UNRESOLVED` (a table or dialog the loader throws on, an `extract` with neither `table` nor `dialog`, a `slavegrid` with no `table`, a grid folder that exists without its `_grid.xml` while the table has a `default` grid, or a missing view or grid the runtime cannot generate: a view whose table has no `Text` field besides its key, or names and titles that leave the generated file unparsable), `MODEL_ENTITY_UNLOADABLE` (`Table.InitFields` throws on the file's own fields or key — a field with no `name`, two fields of one name, no `primarykey`, or a key that names no field — so the entity loads nowhere), `MODEL_CELL_UNBOUND` (a form cell that names no field, so the form does not load), or `XML_MALFORMED` |
| `2` | Warnings — `MODEL_REFERENCE_TEMPLATED` (the runtime generates the missing view or grid and writes it into the workspace), `MODEL_REFERENCE_APP_DEPENDENT` (a webasm entity whose target only some applications have), `CASE_ONLY_MATCH` |
| `3` | **STOP** and relay it — a usage error, `SCHEMA_UNSELECTABLE`, or `DEPENDENCY_MISSING` with its install command |

Relay the `NOT RUN:` lines too: a relation's table and an entity's data source are database objects,
and no check reads them. Suggest `/dgf-plan` for a defect worth fixing, or `/dgf-fix` when a plan
already covers the file.

### Step 3: Add and modify — the plan

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
| `0` | Continue. Keep its `AFFECTS:` and `TASK:` lines, and read the plan's `## Scope`. |
| `1` | **STOP.** Relay every `ERROR` line: `/dgf-plan` repairs a plan. |
| `2` | Continue, and surface every `WARN` line. |
| `3` | **STOP** and relay it. |

**The partition** (ADR 0023 §2): this skill writes an entity's `settings.xml` only. A form, view,
grid form or options file → **STOP**: `/dgf-component`'s. A process or workflow → **STOP**:
`/dgf-process`'s.

### Step 4: Scope — decided by the script, before the write

For add, `A:<file>`; for modify, `M:<file>`. A deletion is never this skill's — **STOP**, and have
`/dgf-plan` plan it.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed M:<file> --skip-validators
```

| Exit | Action |
|---|---|
| `0` | Continue to Step 5. |
| `1` | A `CHANGE_*` error — an undeclared workspace, an out-of-scope file. **STOP** before writing anything: `/dgf-plan` widens the plan. |
| `2` | `CHANGE_UNPLANNED_FILE` → the gate will warn on this file. Under strict mode (`workflow.verify_mode: strict`) the gate would block on it — **STOP**, and have `/dgf-plan` add it to a task. `CHANGE_TASK_FILE_UNCHANGED` is expected here — ignore it. Surface any other `WARN` line. |
| `3` | **STOP** and relay it. |

**Without git, take a baseline now, before the write.** With no git the change check has no base
tree, so it counts every finding in the root as new (ADR 0018 §5) — an old defect in another entity
included. Run the whole-root check Step 6 will run, once, with the same `A:` or `M:`, and keep its
`ERROR` and `WARN` lines: they are the root as it was before the write.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed M:<file>
```

| Exit | Action |
|---|---|
| `0`, `1`, `2` | Keep every `ERROR` and `WARN` line, and continue to Step 5. |
| `3` | An `ERROR FAMILY_UNRESOLVED` line is a file in the root that parses as neither family — a finding like the others: keep it, and continue. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other → **STOP** and relay it. |

### Step 5: Write

- **Add:** the path comes from the `legacy-artifacts` row:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route_means.py" settings
  ```

  | Exit | Action |
  |---|---|
  | `0` | The `ROUTE:` line gives the pattern, `<workspace>/FM/_DATA/<table>/settings.xml`. |
  | `3` | **STOP** and relay it: no route is ever guessed. |

  **If the file exists → STOP**: add never overwrites. Start from
  `${CLAUDE_PLUGIN_ROOT}/skills/dgf-model/templates/settings.xml`, and replace every `Example`.
- **Modify:** edit only the file Step 4 checked.

Take every fact from `knowledge/data-model.md` and the DGF docs MCP (`get_xml_property_reference`,
`search_docs`), never from memory: a `primarykey` the table needs, a `uimask` on every field, a
`type` that is a `FieldTypeEnum` member, and a reference the loader can resolve.

### Step 6: Confirm

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_config.py" "<root>/<file>"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_model.py" --workspaces-root "<root>" "<root>/<file>"
```

Each script's exit:

| Exit | Action |
|---|---|
| `0` | Continue to the change check. |
| `1` | An `ERROR` → correct the file and re-run, at most 3 attempts, then **STOP** with the findings. A `MODEL_REFERENCE_UNRESOLVED` for a view or grid the runtime cannot generate is cured in this file by naming one that exists; otherwise it is the target table's `settings.xml` — its fields or a title — or a scaffolded view or grid, which is `/dgf-component`'s if the plan covers it: **STOP** and name which. |
| `2` | Surface every `WARN` — `XSD_LAGS_RUNTIME` is advisory, and a `MODEL_REFERENCE_TEMPLATED` view or grid is one the runtime will write into the workspace. The change check below decides what strict mode does with it. |
| `3` | `FAMILY_UNRESOLVED` → the file written does not parse as XML, or its root is one no XSD reads — the message says which: correct it, within the same 3 attempts. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other → **STOP** and relay it. |

Then the change check **over the whole root — no `--files`:** a removed or renamed field unbinds the
cells of forms the edit never touched (`knowledge/data-model.md` §4), and a removed entity breaks
every `extract` that names it (§3.2 there). With git:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>"
```

— without git, the baseline's command again, `--changed M:<file>` (or `A:<file>`) in place of
`--base`. A finding the baseline also holds, with the same code, file and message whatever its line,
was in the root before the write: it is pre-existing, as the script's own baseline would call it
(ADR 0018 §3). Only the others are new.

| Exit | Action |
|---|---|
| `0` | Continue to Step 7. |
| `1` | Take the new `ERROR` lines — without git, those the baseline does not hold; none left → continue as for `2`. A new `ERROR` → in this file, correct it within the same 3 attempts; a new `MODEL_CELL_UNBOUND` in a form → **STOP**: the form is `/dgf-component`'s, and the plan must cover it; a new `ERROR` in any other file this skill did not write — another entity's `settings.xml` included — → **STOP** and report it. A `CHANGE_*` error → **STOP**. `PRE_EXISTING` findings are not this change's. |
| `2` | Surface every new `WARN`. Under strict mode a new validator `WARN` is corrected like an error. |
| `3` | An `ERROR FAMILY_UNRESOLVED` line on the file written → correct it, within the same 3 attempts; on another file, it is pre-existing when the baseline holds it, and otherwise a new `ERROR` in a file this skill did not write. `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim. Any other → **STOP** and relay it. |

### Step 7: The database work

Name, for the change: the database table or view the `datasource` names, and each column a field
added, renamed or removed needs; for a `relation`, its junction table. If the plan's `## Scope` does
not name that database work, say so, and suggest `/dgf-plan` to widen it. **Never write SQL.**

### Step 8: Report

In `language.ui`: the mode and the file, each check's findings, the reach for an inspected entity
with its `LIMIT:` line, the database work Step 7 named, and the override applied or refused. For an
add or a modify, name the file written and any `CHANGE_UNPLANNED_FILE`, and suggest `/dgf-implement`
to continue the task the file belongs to, then `/dgf-verify`.

## Execution Rules

### DO:

- ✅ Check every reference with `validate_model.py`, which resolves it the loader's way
- ✅ Find and check the plan, and decide the scope with `check_change.py --skip-validators`, before a write
- ✅ Run the whole-root change check after a write — without git, against the baseline taken before it
- ✅ Name the database work a change needs, and whether the plan covers it
- ✅ Take every fact from `knowledge/data-model.md` and the DGF docs MCP

### DON'T:

- ❌ Write SQL, or any file outside the workspaces root
- ❌ Write outside the plan's scope, or any file Step 4 did not check
- ❌ Overwrite on add, delete a file, or convert its family
- ❌ Write a form, view, grid form, options file, process or workflow
- ❌ Tick a plan checkbox — `/dgf-implement` owns the ledger
- ❌ Emit a `dgf-gate-result` block

## Artifact Ownership

- **Writes:** an entity's `settings.xml`, only inside the plan's scope, one per add or modify.
- **Reads:** the plan, `.dgf-factory/config.yaml`, its override after `check_override.py`, the
  patches, its template, the shipped `knowledge/`, and the DGF docs MCP. It never edits the plan.

## Critical Rules

1. **A reference is checked the loader's way, and blocks only where the loader throws.**
2. **Only inside the plan's scope.** No plan, no write; the scope script runs before the write.
3. **The whole root after a write.** A removed field breaks forms the edit never names.
4. **Never write SQL.** Name the database work; the consumer's database project holds it.
5. **Never overwrite on add, never delete, never convert.**
6. **One owner per artifact.** Forms and views are `/dgf-component`'s; processes and workflows
   `/dgf-process`'s.
7. **Never tick a checkbox, and no gate block.**
8. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts, knowledge, templates and references.
