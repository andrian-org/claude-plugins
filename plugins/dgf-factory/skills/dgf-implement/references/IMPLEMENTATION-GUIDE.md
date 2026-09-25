# dgf-implement — Implementation Reference

## Progress display

Build it from `check_plan.py`'s `TASK:` and `PROGRESS:` lines, never from memory.

```
┌──────────────────────────────────────────────────────────┐
│ Plan: .dgf-factory/plans/feature-zims-inspection-fee.md  │
│ Affects: zims, webasm                                    │
├──────────────────────────────────────────────────────────┤
│ ✅ #1 [config] Add the inspection-fee DataSource          │
│ 🔄 #2 [config] Show the fee on the application form  ←   │
│ ⏳ #3 [code]   Hide the fee panel until payment (dep 2)  │
├──────────────────────────────────────────────────────────┤
│ Progress: 1/3                                            │
└──────────────────────────────────────────────────────────┘
```

`🔄` marks the task about to run; a task whose dependencies are not all checked waits, whatever
its number.

## The per-task loop

```
read the task (and its phase file, for ultra)
  └─ evidence disagrees with the estate? ───────────────► STOP: report the drift
route each file
  ├─ existing → validate_config.py → FAMILY: … → edit in that family
  ├─ new config → route_means.py → ROUTE: … must match the plan's path ─► else STOP
  └─ kind: code → only the file the plan names
compose → write the files (deletes: git rm)
  └─ needs C#/TS/SQL/assembly/deployment? ─────────────► STOP: report what code is needed
check_change.py --base <base> --files <task files>
  ├─ exit 0/2 → tick the checkbox → commit checkpoint? → next task
  ├─ exit 1, new ERROR in the task's files → fix → re-run (at most 3 attempts) → else STOP
  ├─ exit 1, CHANGE_* → STOP: the change left the plan
  └─ exit 3 → STOP: relay it (a missing dependency's install command verbatim)
```

## Reading `check_change.py`

| Line | Meaning for the task |
|---|---|
| `CHANGE: A <path> class=config workspace=zims` | one changed file, its class and workspace |
| `ERROR <CODE> <file>:<line> …` | a **new** finding — the branch introduced it |
| `WARN <CODE> …` | a new warning: surface it |
| `INFO PRE_EXISTING <file> [<CODE>] …` | present before the branch: count it, do not fix it |
| `INFO FIXED <file> [<CODE>] …` | the branch removed it |
| `NOT RUN: baseline (…)` | no merge-base: every finding counted as new |
| `new: <e> error(s), <w> warning(s); pre-existing: <p>; fixed: <f>` | the summary to report |

The change set spans the whole branch, not only this task: an earlier task's unplanned file
still shows here. The validators, though, ran only on `--files`.

## Handling a blocker

```
⚠️ Task 2 stopped

Reason: drift — the plan says `Panel name="Payment"` exists in
zims/FM/_DATA/Inspection/_forms/Apply/_form.xml; the form has no such panel.

Options:
1. Re-plan with /dgf-plan (recommended)
2. Stop here
```

Offer a re-plan, not a workaround. The only in-skill recovery is fixing a **new** validator
error in a file the task wrote, within three attempts.

## Resuming after `/clear`

1. `locate_plan.py` finds the plan again from the branch.
2. `check_plan.py` re-reads its checkboxes: the first unchecked task with checked dependencies
   is next.
3. `git status --porcelain` shows what is half-done: re-read those files before continuing.
4. For ultra, re-read the active task's whole phase file, even if it was read before.

```
Session 1:
  /dgf-plan full show the inspection fee on the application form
  → branch feature/zims-inspection-fee; plan with 3 tasks; check_plan exits 2 (PLAN_OVERLAP: webasm)
  /dgf-implement
  → Task 1 composed, validated (exit 0), ticked
  → session ends

Session 2:
  /dgf-implement
  → PLAN: .dgf-factory/plans/feature-zims-inspection-fee.md mode=full source=branch
  → PROGRESS: 1/3 — continues at Task 2
  → Tasks 2 and 3 composed, validated, ticked
  → suggests /dgf-verify, then /dgf-commit
```
