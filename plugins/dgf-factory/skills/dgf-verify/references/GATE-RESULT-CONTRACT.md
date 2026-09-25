# dgf-verify — Gate Result Contract

`/dgf-verify` ends its report with exactly one fenced `dgf-gate-result` JSON block, and writes
nothing after it. A caller parses the **last** such block and nothing else — never the prose.

This is the milestone-9 block: AI Factory's base fields, in AI Factory's shape, so it stays
compatible with the `aif-gate-result` contract.

## The block

```dgf-gate-result
{
  "schema_version": 1,
  "gate": "verify",
  "status": "fail",
  "blocking": true,
  "blockers": [
    {"id": "task-3", "severity": "error", "file": ".dgf-factory/plans/feature-zims-inspection-fee.md",
     "summary": "Task 3 is not checked"},
    {"id": "DEAD_TRANSITION", "severity": "error", "file": "zims/FM/_PROCESS/Apply/process.xml",
     "summary": "`Review` moves to `Archive`, which is neither a declared state nor `End`"}
  ],
  "affected_files": [".dgf-factory/plans/feature-zims-inspection-fee.md", "zims/FM/_PROCESS/Apply/process.xml"],
  "suggested_next": {"command": "/dgf-implement", "reason": "one task remains and the change adds a blocking finding"}
}
```

| Field | Rule |
|---|---|
| `schema_version` | `1` |
| `gate` | `"verify"` |
| `status` | `pass`, `warn` or `fail` — computed from the table below, never judged |
| `blocking` | `true`: a `fail` stops a commit, a merge or a hand-off |
| `blockers` | the findings that make the status what it is: `{id, severity, file, summary}` |
| `affected_files` | every file the gate cites — blockers' files, and the plan — root-relative, sorted, no duplicates |
| `suggested_next` | `{command, reason}`, `command` from the allowlist below |

The block is JSON only: no comments, no trailing commas, no prose inside the fence.

## Status — computed from the scripts' exits

| Input | Status |
|---|---|
| any script exit `3`, or a required check not run because a script could not run | `fail` |
| any exit `1`: a new blocking finding, a plan defect, an undeclared workspace, an unchecked task | `fail` |
| any exit `2`; a required check reported `NOT RUN`; or a check that cannot run by design, such as `frontend-tests` for a plan with `kind: code` tasks (ADR 0010 §2) | `warn` |
| otherwise | `pass` |

The worst row wins. **Strict mode** (`--strict`, or `workflow.verify_mode: strict`): a **new**
warning is `fail`. A `PRE_EXISTING` or `FIXED` finding never is, in any mode.

## Blockers

| What | `id` | `severity` | `file` |
|---|---|---|---|
| an unchecked task | `task-<N>` | `error` | the plan |
| an `ERROR` line from `check_plan.py` or `check_change.py` — a new finding | its code | `error` | the finding's file |
| a script that exited `3` | `<script>-exit-3` | `error` | the plan |
| a required check reported `NOT RUN` | `not-run-<check>` | `warning` | the plan |
| strict mode only: a new `WARN` line | its code | `warning` | the finding's file |

`summary` is the finding's message, shortened to one sentence where it runs long. Warnings that
do not block stay in the prose report, not in `blockers`. `INFO` lines — `PRE_EXISTING`,
`FIXED`, `PLAN_OVERLAP_UNREADABLE` — are never blockers.

## Required checks

The gate never reads as having passed a check that did not run. These must have run:

| Check | From |
|---|---|
| `plan-header`, `plan-tasks`, `plan-files` | `check_plan.py` |
| `change-scope`, `change-means` | `check_change.py` — both need git and a merge-base |
| `baseline` | `check_change.py` — needs git and a merge-base; without it every finding counts as new |
| `validators` | `check_change.py` — the whole-root validator run; `NOT RUN` only if skipped |

Each one reported as `NOT RUN` becomes a `not-run-<check>` blocker of severity `warning`, and the
report keeps its `NOT RUN` line and reason. A validator's own per-file `NOT RUN` lines — a check
that does not apply to that kind of file, such as `json-format (annotation-only, ADR 0015)` —
are kept in the prose and are not blockers.

## `suggested_next.command`

| Command | When |
|---|---|
| `/dgf-plan` | the plan itself is defective: `check_plan.py` exited `1` or reported `PLAN_UNREADABLE`, or there is no plan |
| `/dgf-implement` | tasks remain unchecked, or the change has new blocking findings to fix |
| `/dgf-commit` | `pass` or `warn` |
| `null` | the gate could not run — a missing dependency or a usage error; the reason says what to do |

## Not yet emitted

Milestone 10 ("Gate Contract Wired") adds these fields and the `scripts/lib/gate_result.py` that
builds the block. `/dgf-verify` does not emit them yet, and a caller must not expect them:

- `schema_family` — which family each validated file resolved to;
- `checks_run` — the check ids that ran, so a narrowed run is visible in the block itself;
- `affected_components` — the components the change touches;
- `affected_processes` — the processes the change touches.
