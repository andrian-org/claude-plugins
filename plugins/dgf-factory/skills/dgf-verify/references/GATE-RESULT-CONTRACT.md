# dgf-verify — Gate Result Contract

`/dgf-verify` ends its report with exactly one fenced `dgf-gate-result` JSON block, and writes
nothing after it. A caller parses the **last** such block and nothing else — never the prose.

The block is computed by `scripts/verify_gate.py` and built by `scripts/lib/gate_result.py`, the
one builder every gate uses (ADR 0022). Nobody writes it by hand, and the model never edits it.
It keeps AI Factory's base fields and `schema_version: 1`, so anything built on the
`aif-gate-result` contract can still read it.

## The block

```dgf-gate-result
{
  "schema_version": 1,
  "gate": "verify",
  "status": "fail",
  "blocking": true,
  "blockers": [
    {"id": "task-3", "severity": "error", "file": ".dgf-factory/plans/feature-zims-inspection-fee.md",
     "line": 58, "schema_family": null, "summary": "Task 3 is not checked: Hide the fee panel until payment is confirmed"},
    {"id": "DEAD_TRANSITION", "severity": "error", "file": "zims/FM/_PROCESS/Apply/process.xml", "line": 41,
     "schema_family": "xsd", "summary": "`Review` moves to `Archive`, which is neither a declared state nor `End`"}
  ],
  "warnings": [
    {"id": "not-run-frontend-tests", "severity": "warning", "file": ".dgf-factory/plans/feature-zims-inspection-fee.md",
     "line": null, "schema_family": null, "summary": "frontend-tests did not run: the project's own CI runs its frontend tests, never the gate — ADR 0010 §2"}
  ],
  "affected_files": [".dgf-factory/plans/feature-zims-inspection-fee.md", "zims/FM/_PROCESS/Apply/process.xml"],
  "checks_run": ["plan-header", "plan-tasks", "plan-commits", "plan-files", "plan-routes", "plan-overlap",
                 "change-scope", "change-means", "change-planned", "validators", "baseline", "xsd-structure"],
  "schema_family": {"json": 212, "xsd": 364},
  "affected_components": [
    {"workspace": "zims", "artifact": "form", "name": "Inspection/Apply",
     "file": "zims/FM/_DATA/Inspection/_forms/Apply/_form.xml", "change": "M"}
  ],
  "affected_processes": [{"workspace": "zims", "name": "Apply", "reference": "Apply"}],
  "suggested_next": {"command": "/dgf-implement",
                     "reason": "1 task(s) unchecked; then 1 new blocking finding(s) for /dgf-fix"}
}
```

| Field | Rule |
|---|---|
| `schema_version` | `1` |
| `gate` | `"verify"` |
| `status` | `fail` if `blockers` is not empty, else `warn` if `warnings` is not empty, else `pass` — computed, never judged |
| `blocking` | `true` exactly when `status` is `fail`; a `fail` stops a commit, a merge or a hand-off |
| `blockers` | only what blocks: entries, below |
| `warnings` | every non-blocking warning, and every required check that did not run |
| `affected_files` | every file an entry names, plus the plan — root-relative, sorted, no duplicates |
| `checks_run` | every check that ran, in order, across all the scripts |
| `schema_family` | `{"json": <n>, "xsd": <n>}`, the files the validators read per resolved family; `"unresolved": <n>` only when there are any |
| `affected_components` | the configuration the change touched outside process folders, in both families: `{workspace, artifact, name, file, change}` |
| `affected_processes` | each process whose `<ws>/FM/_PROCESS/<name>/` folder holds a changed file: `{workspace, name, reference}`; a `webasm` process's reference is `BASE:<name>` |
| `suggested_next` | `{command, reason}`, `command` from the allowlist below |

The block is JSON only: no comments, no trailing commas, no prose inside the fence.

## Entries

An entry is `{id, severity, file, line, schema_family, summary}`. `file` is root-relative, `line` an
integer or `null`, and `summary` the finding's message, cut to 240 characters with `…`.
`schema_family` is `"json"` or `"xsd"` for a validator finding — the family of its file — and
`null` for any other.

| Finding | List | `id` | `severity` | `file` | `schema_family` |
|---|---|---|---|---|---|
| `GATE_TASK_UNCHECKED` | `blockers` | `task-<N>` | `error` | the plan | `null` |
| `GATE_STRICT_WARNING` | `blockers` | the promoted finding's code | `warning` | its file | its file's family |
| `GATE_CHECK_NOT_RUN` | `warnings` | `not-run-<check>` | `warning` | the plan | `null` |
| any other `ERROR` line | `blockers` | its code | `error` | its file — the plan, for a plan finding | the file's family for a validator finding, else `null` |
| any other `WARN` line, not promoted | `warnings` | its code | `warning` | its file | as above |
| `INFO` — `PRE_EXISTING`, `FIXED`, `PLAN_OVERLAP_UNREADABLE`, … | never | | | | |

A promoted warning appears once, in `blockers`. When the gate could not run, the finding that
stopped it is a blocker under its own code — `DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE`,
`PLAN_UNREADABLE`, `PLAN_FORMAT_UNSUPPORTED` — and the script exits `3`.

## Required checks

The gate never reads as having passed a check that did not run. These must run:

| Check | From |
|---|---|
| `plan-header`, `plan-tasks`, `plan-files`, `plan-routes`, `plan-commits` | `check_plan.py` |
| `change-scope`, `change-means`, `change-planned` | `check_change.py` — they need git and a merge-base, or `--changed` |
| `baseline` | `check_change.py` — needs git and a merge-base; without it every finding counts as new |
| `validators` | `check_change.py` — **the whole-root validator run** |
| `frontend-tests` | required when any task is `kind: code`; the gate never runs it (ADR 0010 §2) |

`plan-overlap` is not required. Each required check that did not run is a `not-run-<check>`
entry in `warnings`, carrying the script's reason, and the report keeps its `NOT RUN` line. A
validator's own per-file `NOT RUN` lines — a check that does not apply to that kind of file — stay
in the prose.

**Narrowing.** `check_change.py --files` records `validators` as `NOT RUN (narrowed to N file(s) by
--files …)`, so a narrowed run can never read as a pass. That is `/dgf-implement`'s per-task
pre-check, never the gate.

## Absent versus empty

A field the gate did not compute is **left out**; `[]` means "computed, and none".

- `schema_family` is present when the validators ran.
- `affected_components` and `affected_processes` are present when there is a changed set — `--base`
  with git and a merge-base, or `--changed`. They are the change's own footprint, not its blast
  radius: a changed shared workflow is listed, not the processes that call it.
- A gate that stopped before any check — no root, no plan, an unconfirmed plan — has
  `checks_run: []`.

## Strict mode

`--strict`, or `workflow.verify_mode: strict`: every `WARN` line `check_change.py` reports is
promoted to a blocker, severity `warning`, through `GATE_STRICT_WARNING`. They are new by
construction, since a pre-existing finding is `INFO`. `check_plan.py`'s warnings are never
promoted, and neither are `PRE_EXISTING` or `FIXED`.

## `suggested_next.command`

The first match wins:

| Command | When |
|---|---|
| `null` | the gate could not run: `DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE`, `ROOT_NOT_SET_UP`, `ROOT_AMBIGUOUS`, `PLAN_AMBIGUOUS` or `GATE_PLAN_UNCONFIRMED`. The reason names the fix: the install command, `run /dgf`, or `pass --plan` |
| `/dgf-plan` | there is no plan (`PLAN_NOT_FOUND`), or `check_plan.py` reported an error — including `PLAN_UNREADABLE`, `PLAN_FORMAT_UNSUPPORTED` and `PLAN_COMMITS_INVALID` |
| `/dgf-implement` | a task is unchecked, a change check (`check_change.py`'s own report — `CHANGE_*`) reported an error, or strict mode promoted a change-check warning. When validator findings also block, the reason adds "then <n> new blocking finding(s) for /dgf-fix" |
| `/dgf-fix` | every task is checked and the scope is clean, but a validator reported a new error, or strict mode promoted a new validator warning: "<n> new blocking finding(s) — fix each inside the plan's scope and record a patch" |
| `/dgf-commit` | `pass` or `warn` |
| `null` | the gate failed on a finding no command fixes — read the blockers |

Scope comes before findings, because `/dgf-fix` works only inside a scope the change checks accept,
and unchecked tasks come first, because a finding may sit in a file an unfinished task still
changes. A promoted warning follows the report its original came from — by identity, never by code
(ADR 0022 §9). The doctor's allowlist is `null` alone: a broken install is fixed by hand, never by
`/dgf-fix` (ADR 0022 §8).

## Exit codes

The script's exit agrees with the block: `0` `pass`, `1` `fail`, `2` `warn`, and `3` when a
finding forces it — the gate could not run, or a validator could not read a file
(`FAMILY_UNRESOLVED`, `SCHEMA_UNSELECTABLE`) — and then the status is `fail`. A usage error —
a bad argument, or a plan outside the workspaces root — is exit `3` with **no** block: a caller
reads a missing block as a gate that did not run.
