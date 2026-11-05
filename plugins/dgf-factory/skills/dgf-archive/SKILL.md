---
name: dgf-archive
description: Archive finished dgf-factory plans — list every plan with its progress, ask which complete ones to archive, and move them into the archive folder with an archived date stamped in each header, through a script, so nothing is moved by hand. Use for "archive plans", "archive completed plans", "archive finished plans", "clean up plans", "dgf archive".
argument-hint: "[<plan path>…]"
allowed-tools: Read Glob Grep Bash(python3 "{{dgf_runtime}}/scripts/archive_plans.py"*) Bash(python3 "{{dgf_runtime}}/scripts/locate_plan.py"*) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
---

# DGF Archive — Finished Plans Out of the Way

Plans accumulate under `paths.plans`. This skill moves the finished ones into `paths.archive/plans/`, so
plan discovery, the overlap check and the next `/dgf-plan` see only the plans still in flight.

**One script decides and moves: `archive_plans.py`.** It reads every plan with the same parser the gate uses,
calls a plan complete only when it has at least one task and every task is checked, stamps
`archived: <date>` into its header from its own clock, and moves it — an ultra bundle's directory as a whole.
This skill grants itself no write tool: it runs the script, asks the user, and reports (ADR 0032 §1, §3). It
runs no version-control command either; the move is a delete and an add in the working tree, which
`/dgf-commit` commits like any other change.

It ports AI Factory's `/aif-archive`. The roadmap trimming is dropped — dgf-factory keeps no roadmap in an
estate — and the move is the script's, never the model's.

## Workflow

### Step 0: Context

```bash
python3 "{{dgf_runtime}}/scripts/locate_plan.py" --root-only
```

| Exit | Action |
|---|---|
| `0` | The `ROOT:` line is `<root>`. Continue. |
| `1` | **STOP** with its message: `ROOT_NOT_SET_UP` → run `/dgf`; `ROOT_AMBIGUOUS` → name the root. |
| `3` | **STOP** and relay it: the call is wrong. |

Read `<root>/.dgf-factory/config.yaml` for `paths.plans`, `paths.plan`, `paths.archive` (default
`.dgf-factory/archive/` when the key is absent — an older config has none) and `language.ui`.

### Step 1: The dry run

```bash
python3 "{{dgf_runtime}}/scripts/archive_plans.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>" --archive-dir "<paths.archive>"
```

When the user named plans as arguments, add `--plan <path>…` with each, root-relative. Without `--apply` the
script writes nothing. Capture the exit code before anything reads the output: a pipe would report the pipe's
own.

The script prints one line per plan:

- `ARCHIVE: <src> -> <dest> progress=<d>/<t>` — complete; it would move to `<dest>`.
- `KEEP: <src> progress=<d>/<t>` — not complete, or `progress=unreadable`: it does not parse.
- `KEEP: <src> progress=<d>/<t> — the current branch's plan; name it with --plan` — complete, but kept:
  `/dgf-commit` still follows its Commit Plan. It is archived only when named.

| Exit | Action |
|---|---|
| `0` | Continue to Step 2 with every `ARCHIVE:` line. |
| `1` | `ARCHIVE_DEST_EXISTS` — a plan's destination is already in the archive, or two plans share one. Quote each `ERROR` line verbatim. That plan cannot be archived until its archive entry is renamed by hand; this skill never moves or deletes it. `ARCHIVE_PLAN_INCOMPLETE` — a plan named as an argument has an unchecked task: quote it and leave it out. Continue to Step 2 with the `ARCHIVE:` lines no `ERROR` line names; none left → **STOP** and report. |
| `2` | `ARCHIVE_NOTHING` — no plan to archive. Report every `KEEP:` line; when one is the current branch's plan, continue to Step 2 with it alone, else **STOP**. `ARCHIVE_PLAN_SKIPPED` — a plan does not parse, or is a symlink, and stays where it is: name it, then continue with the `ARCHIVE:` lines. |
| `3` | **STOP** and relay it: the call is wrong — a path that is not root-relative, an archive folder outside `.dgf-factory/`, or a named plan that is no plan. |

### Step 2: Ask which plans to archive

Ask with `AskUserQuestion`, in `language.ui`, and never preselect:

- **The candidates:** each `ARCHIVE:` line Step 1 kept, as `<src>` with its progress and destination; and, for a
  `KEEP:` line that is the current branch's plan, a named option — `<src> (the current branch's plan: archive it
  only when its Commit Plan is done)`.
- **Two or more candidates** → `multiSelect: true`, at most 4 options a question; more candidates are split
  across questions in the same call. **One** → a single-select question: archive it, or keep it.

Nothing chosen → **STOP**: report that nothing was moved.

### Step 3: Archive the chosen plans

```bash
python3 "{{dgf_runtime}}/scripts/archive_plans.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>" --archive-dir "<paths.archive>" --plan "<src>" --apply
```

— with one `--plan` value per chosen plan, each exactly as its line printed it. Naming a plan is what archives
the current branch's. Capture the exit code before anything reads the output.

| Exit | Action |
|---|---|
| `0` | Every chosen plan moved: one `MOVED: <src> -> <dest>` line each. Report (Step 4). |
| `1` | **Refused — nothing was moved.** `ARCHIVE_DEST_EXISTS` (a destination appeared since the dry run) or `ARCHIVE_PLAN_INCOMPLETE` (a task was unchecked since). Quote each `ERROR` line verbatim and **STOP**. Never re-run with other plans unasked. |
| `2` | `ARCHIVE_PLAN_SKIPPED` — a chosen plan no longer parses, or is a symlink, and stayed where it is; the others moved. Name it, and report the `MOVED:` lines. |
| `3` | **STOP** and relay it. A failed write or move leaves that plan where it was, unchanged — unless the message says where it is instead — and names the plans moved before it: report those as moved, and the rest as where they were. |

### Step 4: Report

In `language.ui`:

- each `MOVED:` line — where the plan went, its header now stamped `archived: <date>`;
- each plan kept, and why: not complete (its progress), does not parse, the current branch's plan not chosen,
  or not chosen;
- each `ERROR` line verbatim, and what it left in place;
- that the move is a working-tree change, not yet committed. A patch whose `plan` names a moved plan stays
  valid: a patch's plan need not still exist.

### Step 5: Next

- Plans moved → `/dgf-commit` to commit the move, for example `chore: archive finished plans`.
- A plan kept because a task is unchecked → `/dgf-implement` to finish it, or `/dgf-verify` to see what is left.

## Execution Rules

### DO:

- ✅ Run the dry run first, and ask before every `--apply`
- ✅ Pass exactly the plans the user chose, as the script printed them
- ✅ Capture each exit code before any pipe, and quote every `ERROR` line verbatim
- ✅ Keep the current branch's plan unless the user names it

### DON'T:

- ❌ Move, copy, stamp, edit or delete a plan or an archive entry by hand — the script moves, or nothing does
- ❌ Archive a plan the user did not choose, or re-run a refused `--apply` with fewer plans unasked
- ❌ Call a plan complete that the script printed as `KEEP:`
- ❌ Commit the move — that is `/dgf-commit`'s

## Artifact Ownership

- **Writes:** nothing itself. `archive_plans.py` moves the plans the user chose into
  `paths.archive/plans/` and stamps `archived:` in each moved header (ADR 0032 §1).
- **Reads:** `.dgf-factory/config.yaml` and the scripts' output. It never reads a plan to judge its progress:
  the script does.

## Critical Rules

1. **The script decides and moves.** A plan is complete only when `archive_plans.py` prints it as `ARCHIVE:`.
2. **Ask first.** No `--apply` runs without the user's choice, and only for the plans chosen.
3. **A refused run moved nothing.** Exit `1` is a STOP, never a partial archive.
4. **The current branch's plan stays** unless the user names it: `/dgf-commit` still follows its Commit Plan.
5. **`{{dgf_runtime}}` always** for dgf-factory's own scripts.
