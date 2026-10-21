---
name: dgf-audit
description: Audit a whole DGF workspaces root — the validators' health, the reference graph from processes through workflows to forms, entities and components, and the role names in use — or show a change's blast radius, the processes that reach a file in each application. Read-only. Use for "audit the estate", "blast radius", "what reaches this workflow", "which processes use this", "impact of this change".
argument-hint: "[--reach <file>… | --branch] [--app <name>]"
allowed-tools: Read Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
---

# DGF Audit — The Estate's Health, and a Change's Blast Radius

Two reports, both read-only, from one script, `audit_root.py`:

- **The whole root:** every validator's counts, each validator `ERROR`, the reference graph of each
  application — processes, workflows, forms, entities, components — with the references no validator
  checks that resolve nowhere, the shared workflows no traced reference reaches, and every role name
  the root uses.
- **Blast radius:** for named files, or every file a branch changed, the processes that reach each
  one in each application, and its direct referrers.

The graph is resolved by the engine's own rules, per application: a `webasm` file is read as each
application reads it (ADR 0027 §4). **Blast radius is a report, not a gate.** This skill writes
nothing and emits no `dgf-gate-result` block; the verify gate's `affected_processes` stays the
change's own footprint (ADR 0022 §6).

**A reach is never complete.** A static walk cannot see names assigned at run time, processes chosen
from the database, open handlers, or entry points outside processes. Every report carries a
`LIMIT:` line that says so, and this skill relays it every time (`knowledge/reference-graph.md` §3,
ADR 0027 §8).

AI Factory has no audit skill: its framework-agnostic gates stop at the change. This one asks what
the change reaches.

## Workflow

### Step 0: Context

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --root-only
```

Exit `1` → **STOP** with its message (`ROOT_NOT_SET_UP`: run `/dgf`; `ROOT_AMBIGUOUS`: name the
root). Exit `3` → **STOP** and relay it. Otherwise the `ROOT:` line is `<root>`. Read
`<root>/.dgf-factory/config.yaml` for `paths.*`, `git.enabled`, `git.base_branch` and `language.ui`.

Check this skill's override before reading it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf-audit --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
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

### Step 1: Mode

| Argument | Command |
|---|---|
| (none) | the whole-root audit: `audit_root.py --workspaces-root "<root>"` |
| `--reach <file>…` | `audit_root.py --workspaces-root "<root>" --reach <file>…`, each file root-relative |
| `--branch` | with `git.enabled`: `audit_root.py --workspaces-root "<root>" --base "<git.base_branch>"`. Without it → **STOP**, and ask for `--reach` and the files |
| `--app <name>` | passed through with any of the above: the audit covers that application and `webasm` only |

Run it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_root.py" --workspaces-root "<root>" --reach <file>
```

— with `--base "<git.base_branch>"` for `--branch`, with no mode flag for the whole root, and with
`--app <name>` when one was given. Capture the exit code before anything reads the output: a pipe
would report the pipe's own.

| Exit | Action |
|---|---|
| `0` | Clean, or INFO only. Summarise (Step 2). |
| `1` | A validator `ERROR` in the root. Summarise, leading with the errors. |
| `2` | Warnings: `AUDIT_REFERENCE_UNRESOLVED`, `CASE_ONLY_MATCH`, or `AUDIT_NARROWED` when `--app` narrowed the audit. Summarise. |
| `3` | **STOP** and relay it: `AUDIT_REACH_NOT_ARTIFACT` (a `--reach` path that is not a configuration file under the root), `DEPENDENCY_MISSING` with its install command verbatim, `SCHEMA_UNSELECTABLE` naming a schema dialect (a vendored schema the validators cannot read — the plugin's defect: run `/dgf-doctor` and reinstall), `AUDIT_CHECK_FAILED` (a check raised; relay the report so far, and say the audit is incomplete), or a usage error. |

### Step 2: Summarise

Relay the script's findings, then summarise in `language.ui`:

- **Blast radius, per application:** each `PROCESS:` line — the process's reference and its chain —
  as the processes to regression-test by hand, since a process cannot run headlessly (ADR 0014 §5).
  Each `REFERRER:` line, one level deep. A `NONE:` line means no *traced* reference reaches the file,
  not that nothing does. A `NOT AUDITED:` line names a file whose own application `--app` left out:
  nothing was walked for it, so say that its reach is unknown and suggest the run without `--app`.
  An `AUDIT_REFERENCE_DYNAMIC` line marks a chain through a name set at run time: the step may load
  another file.
- **The unresolved references:** each `AUDIT_REFERENCE_UNRESOLVED` line — a reference no validator
  checks yet, with the applications it fails in — and every validator `ERROR`.
- **The unreached shared workflows:** the `AUDIT_WORKFLOW_UNREACHED` lines, as **candidates**, never as
  dead code: an entry point outside processes may start them.
- **The roles:** each `ROLE:` line, as an unchecked inventory. Quote each name exactly as the line
  does — `" B"`, with its leading space, is a different role from `"B"`, and the runtime splits
  `roles` on `,` without trimming (`knowledge/permissions.md` §2.1). Nothing in the root declares
  roles, so no name is checked (§1 there).
- **Every `LIMIT:` line, verbatim.**
- A narrowed audit (`AUDIT_NARROWED`) covers one application and `webasm`: say that the other
  applications were not audited.
- The override applied or refused.

### Step 3: Next

- A defect in the estate → `/dgf-plan` to plan its fix.
- A blast radius → the processes to regression-test, and `/dgf-plan` when the change is still being
  planned, so its tasks name them.

## Execution Rules

### DO:

- ✅ Relay the script's output, and its exit code, captured before any pipe
- ✅ Report reach per application, with every `LIMIT:` line verbatim
- ✅ Quote each role name exactly as the script prints it
- ✅ Call unreached workflows candidates, not dead code

### DON'T:

- ❌ Write, edit or delete any file
- ❌ Call a reach complete, or read a `NONE:` line as "nothing reaches it"
- ❌ Emit a `dgf-gate-result` block — blast radius is not a gate
- ❌ Check role names against a list — there is none in the root

## Artifact Ownership

- **Writes:** nothing.
- **Reads:** `.dgf-factory/config.yaml`, its override after `check_override.py`, and the script's
  output.

## Critical Rules

1. **Read-only.** No file is written, and no gate block is emitted.
2. **A reach is never complete.** Every `LIMIT:` line is relayed verbatim.
3. **Per application.** A `webasm` file is reached differently in each application.
4. **Roles are an inventory.** Nothing in the root declares one.
5. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts.
