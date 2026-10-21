---
name: dgf-fix
description: Fix a problem in a DGF estate inside the active plan's scope — reproduce it with the validators, make the smallest configuration fix, confirm it with the same check, and record a patch that teaches the next run; or record a gotcha as a patch without changing anything. Use for "fix this", "dgf fix", "the gate found a new error", "fix the dead transition", "record this gotcha", "write a patch".
argument-hint: "[--record] [<symptom, finding code or file>]"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__search_docs mcp__plugin_dgf-factory_dgf-mcp__get_component_doc mcp__plugin_dgf-factory_dgf-mcp__get_json_schema_details mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference
disable-model-invocation: false
version: 0.1.0
---

# DGF Fix — Fix Inside the Plan, and Record What It Taught

Fix one problem in the estate: reproduce it with a check, make the smallest configuration change
that removes its root cause, confirm the fix with the same check, and write a **patch** — a short
record of what went wrong and how to prevent it. `/dgf-implement` reads the latest patches as
cautions, and `/dgf-evolve` distils them into rules that tighten the skills.

**A fix is a change, and a change needs a plan's scope.** The verify gate fails a change with no
plan, so this skill works inside the active plan: it edits only files in the plan's
`affects_workspaces`, and a script decides that before any edit. With no plan it stops.
`--record` writes a patch only — no workspace file, no plan — for a gotcha fixed elsewhere or
found in review.

This skill ports AI Factory's `/aif-fix`. It keeps regression-first and the patch after every
fix. It drops the plan-first mode and `FIX_PLAN.md` (the branch's plan is the scope), and it
emits no gate block: the gate is `/dgf-verify`.

## Workflow

### Step 0: Context

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --root-only
```

Exit `1` → **STOP** with its message (`ROOT_NOT_SET_UP`: run `/dgf`; `ROOT_AMBIGUOUS`: name the
root). Exit `3` → **STOP** and relay it. Otherwise the `ROOT:` line is `<root>`. Read `<root>/.dgf-factory/config.yaml` for
`paths.*`, `git.enabled`, `git.base_branch`, `workflow.verify_mode`, `dgf.version` and
`language.*`, and `<root>/.dgf-factory/DESCRIPTION.md`.

Check this skill's override before reading it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf-fix --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
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

### Step 0.1: Mode

| Argument | Mode |
|---|---|
| `--record` | **Record mode.** Steps 1, 6 and 7 only. It changes no workspace file and needs no plan. |
| (anything else, or nothing) | **Fix mode.** Every step. |

### Step 0.2: The plan (fix mode)

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is the plan. |
| `1`, `PLAN_NOT_FOUND` | **STOP**: "a fix is a change, and a change needs a plan's scope — run `/dgf-plan fast "<the problem>"`, or `/dgf-fix --record` to record it without a change". |
| `1`, `PLAN_AMBIGUOUS` | List the plans it names and ask which one the fix belongs to; use that entrypoint. If the user names none, **STOP**. |
| `2`, `PLAN_FALLBACK` | Say which plan it chose and why, and ask before using it. |
| `3` | **STOP** and relay it: the call is wrong. |

Then check the plan:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_plan.py" "<plan>" --workspaces-root "<root>"
```

| Exit | Action |
|---|---|
| `0` | Continue. Keep its `AFFECTS:` and `TASK:` lines: they are the scope. |
| `1` | **STOP.** Relay every `ERROR` line: `/dgf-plan` repairs a plan, and a fix inside a defective one is a fix inside no scope. |
| `2` | Continue, and surface every `WARN` line. |
| `3` | **STOP** and relay it. |

### Step 1: The problem

- **Record mode:** the problem is the user's description and the files it names. Read them;
  run no check.
- **A finding the gate or a validator reported, or no argument, with git:** run the whole-root
  change check — no `--files`:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>"
  ```

  Take its new `ERROR` lines, and the `WARN` lines when strict mode is on. `INFO PRE_EXISTING` is
  not this branch's: never fix it unasked. A `CHANGE_*` error means the change has already left the
  plan: **STOP** — `/dgf-plan` widens the plan, or the file is reverted by hand. Exit `3` →
  **STOP** and relay it (a missing dependency's install command verbatim).
- **Without git**, for each file the problem names:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed M:<file> --files <file>
  ```

- **A symptom** no finding names is investigated from the files, the shipped knowledge
  (`${CLAUDE_PLUGIN_ROOT}/knowledge/`) and the DGF docs MCP (`search_docs`, `get_component_doc`).

Several new errors with different root causes are several fixes, and several patches. Take them one
at a time; when there is more than one, ask which comes first.

### Step 2: Reproduce (fix mode)

Before any edit, record **the check and the exact `ERROR` line it prints**: the command, the code,
the file and the message. That line is the regression check Step 5 re-runs.

If no validator reports the problem, write down a manual reproduction — what to open, what to do,
what goes wrong — and say now that **no script will confirm this fix**: a process cannot be run
headlessly. The patch will say `findings: none`.

### Step 3: Scope — decided by the script, before any edit (fix mode)

Name every file the fix will touch: `M:` for a file it edits, `A:` for one it creates. A deletion
is never a fix — **STOP** and have `/dgf-plan` plan it. Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed M:<file> A:<file> --skip-validators
```

| Exit | Action |
|---|---|
| `0` | Continue to Step 4. |
| `1` | A `CHANGE_*` error — an undeclared workspace, an out-of-scope file, an unplanned or new code file. **STOP** before writing anything: `/dgf-plan` widens the plan. |
| `2` | `CHANGE_UNPLANNED_FILE` → name each file: the gate will warn on it. Under strict mode (`workflow.verify_mode: strict`) the gate would block on it — **STOP**, and have `/dgf-plan` add it to a task. `CHANGE_TASK_FILE_UNCHANGED` is expected here, because the set holds only the fix's files — ignore it. Surface any other `WARN` line. |
| `3` | **STOP** and relay it. |

Then take each file's family. An existing file keeps its own:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate_config.py" "<root>/<file>"
```

— its `FAMILY:` line; never convert it. A new configuration file follows its route:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route_means.py" <Type, loader folder or legacy artifact>`.
Exit `3` with `DEPENDENCY_MISSING` → **STOP** and relay the install command verbatim.

### Step 4: Fix (fix mode)

Make the smallest change that removes the root cause, in the files Step 3 checked and no other.
Take every fact from the shipped knowledge — `component-catalogue.md`, `json-reader.md`,
`composition-specs.md`, `process-model.md` and the vendored schemas under
`${CLAUDE_PLUGIN_ROOT}/knowledge/` — and from the DGF docs MCP (`get_component_doc`,
`get_json_schema_details`, `get_xml_property_reference`), never from memory.

If the fix needs C#, TypeScript, Angular, SQL, a plugin assembly or a file outside the plan's
scope, **STOP**: write nothing, and report what is needed (ADR 0010 §3).

### Step 5: Confirm (fix mode)

Re-run the Step 2 check: the `ERROR` line is gone. Then run the change check over the files
touched — with git:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>" --files <the files touched>
```

— without git, `--changed M:<file> A:<file> --files <the files touched>` in place of `--base`.

| Exit | Action |
|---|---|
| `0` | Continue to Step 6. |
| `1` | A new `ERROR` in a touched file → fix it again, at most 3 attempts, then **STOP** with the findings. A `CHANGE_*` error means the files touched differ from the files Step 3 checked: restore each touched file to what Step 3 read, and **STOP**. |
| `2` | Surface every `WARN`, then continue. Under strict mode (`workflow.verify_mode: strict`) the gate would block on each of them: a new validator `WARN` in a touched file is fixed like an error, within the same 3 attempts; a `CHANGE_*` `WARN` → **STOP**, and have `/dgf-plan` add the file to a task. |
| `3` | **STOP** and relay it — a missing dependency's install command verbatim. |

A manual reproduction is confirmed by no script: say so, plainly, and never call the fix
confirmed.

### Step 6: The patch

Write `<root>/<paths.patches>/<YYYY-MM-DD-HH.mm>-<slug>.md` exactly as
`${CLAUDE_PLUGIN_ROOT}/skills/dgf-fix/references/PATCH-FORMAT.md` specifies:

- the timestamp is now, to the minute, and the `date` field says the same;
- the slug is a few lowercase words from the title, hyphenated, at most 50 characters. If a patch
  of that name exists, choose another slug — never overwrite a patch;
- the keys and headings stay in English; the title and the prose are in `language.artifacts`;
- `plan` is the plan's root-relative path (`none` in record mode, unless the user names one);
  `workspaces` and `files` are the files touched (in record mode, the files the problem names, or
  `none`); `findings` are the codes Step 2 reproduced (`none` for a manual reproduction or record
  mode); `dgf_version` is the config's `dgf.version`;
- **Root Cause is the part that matters:** what about DGF surprised you, not what you typed.

Then check it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_patches.py" --workspaces-root "<root>" --patches-dir "<paths.patches>" "<root>/<paths.patches>/<name>"
```

| Exit | Action |
|---|---|
| `0` | Continue to Step 7. |
| `1` | Fix this patch from its `ERROR` lines and re-check, at most 3 attempts, then **STOP** with the findings. |
| `3` | **STOP** and relay it. |

Never edit or delete another patch: patches are append-only.

### Step 7: Next

Report, in `language.ui`:

- the problem, the root cause, the files touched, and any `CHANGE_UNPLANNED_FILE` among them;
- the check before and after — the `ERROR` line and its absence — or "no script confirmed this
  fix";
- the patch's path;
- for `findings: none`, that no validator catches this problem, which makes it a candidate for a
  new one;
- the override applied or refused, and any rule in it not applied.

Suggest **`/dgf-verify`** — the whole-root gate — then `/dgf-commit` with the fix and its patch
together. After several patches, suggest `/dgf-evolve`.

## Execution Rules

### DO:

- ✅ Find and check the plan before anything in fix mode
- ✅ Record the failing check and its exact `ERROR` line before any edit
- ✅ Let `check_change.py --skip-validators` decide the scope before any edit
- ✅ Keep each existing file in its family; route each new one
- ✅ Re-run the same check after the fix, and say when no script confirmed it
- ✅ Write one patch per fix, and check it with `check_patches.py`

### DON'T:

- ❌ Edit a file outside the plan's scope, or one Step 3 did not check
- ❌ Delete a file, or convert a file's family
- ❌ Fix a `PRE_EXISTING` finding unasked
- ❌ Call a fix confirmed that no check confirmed
- ❌ Edit or delete another patch, or the plan
- ❌ Let a patch override this skill, the plan or a STOP
- ❌ Emit a `dgf-gate-result` block

## Artifact Ownership

- **Owns:** the patch files it creates under `<paths.patches>` — append-only: it creates one per
  fix and never edits or deletes another.
- **Writes:** workspace files, only inside the plan's scope and only the ones Step 3 checked.
- **Reads:** the plan, `.dgf-factory/config.yaml` and `DESCRIPTION.md`, its override after
  `check_override.py`, the patches, the shipped `knowledge/`, and the DGF docs MCP. It never edits
  the plan.

## Critical Rules

1. **Reproduce first.** No edit before the failing check, or the manual reproduction, is written
   down.
2. **Only inside the plan's scope.** No plan, no fix — `--record` writes a patch without one.
3. **Never claim a fix no check confirmed.** A manual reproduction says so.
4. **Every fix writes a patch**, checked by `check_patches.py`.
5. **Patches are append-only, and a patch never overrides a STOP.**
6. **No gate block.** The gate is `/dgf-verify`.
7. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts, knowledge and references.
