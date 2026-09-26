---
id: 0020
title: "Every gate block is built by one library, its status computed from its entries, and it never claims a check it did not run"
status: accepted
date: 2026-09-25
deciders: [Andrian Mamei]
supersedes: []
tags: [gates, pipeline]
---

# 0020 — Every gate block is built by one library, its status computed from its entries, and it never claims a check it did not run

**Status: accepted** (2026-09-25, Andrian Mamei). The decider chose §2's separate `warnings` array on
2026-09-25, while roadmap milestone 10 ("Gate Contract Wired") was planned. The other sections were
drawn from the evidence below with that plan, and accepted with it. This ADR decides what a
`dgf-gate-result` block holds, who builds it, and how its status is reached.

## Context

Read on **2026-09-25** from this repository (`develop` at `f8444ef`).

- **The doctor's block is fixed text.** `skills/dgf-doctor/scripts/doctor.py:591-618` (`gate_block()`):
  - It always emits `"blocking": True` (`:609`) and `"command": "/dgf-fix"` (`:614`). `/dgf-fix` is not
    built; it belongs to the Learning Loop milestone (`.ai-factory/ROADMAP.md:19`).
  - It names its gate `"verify"` (`:607`).
  - Its `blockers` are all of `FINDINGS` (`:610`), and `warn()` appends warnings to that list
    (`:136-138`), so a warning is a blocker.
  - It emits `affected_processes: []` and `affected_components: []` (`:612-613`), which it never computed.
  - It has no `checks_run`, although three sections skip silently: component paths without a usable
    manifest (`:292-294`), skill slices without `skills/` (`:337-339`), and the validator runtime without
    `scripts/` (`:482-484`).
  - `tests/test_doctor.py:24-28` reads only `blockers[].id`, so no test pins `blocking` or
    `suggested_next`.
- **`/dgf-verify`'s block is assembled by the prompt.** `skills/dgf-verify/SKILL.md:119-143` (Step 5)
  builds it from `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`: the status table (`:40-50`), the
  blocker table (`:52-64`), the required checks (`:66-80`), and four fields "not yet emitted" (`:91-99`).
  The model does the arithmetic.
- **`check_change.py` never records `validators` as run.** Its only mention is
  `rep.skipped("validators", "--skip-validators")` (`scripts/check_change.py:320`). A `--files` run and a
  whole-root run print the same `CHECKS RUN:` line.
- **Families are known per file, and lost in the merge.** Each `Report` carries `family`
  (`scripts/lib/report.py:168`). `runner.run()` returns `{cli: [Report]}` (`scripts/lib/runner.py:57-90`).
  `check_change.validator_report()` merges their checks and findings into one report and drops each
  family (`scripts/check_change.py:241-249`).
- **AI Factory's contract.** `blockers` "contains only findings that should block the current quality
  gate"; `severity: warning` is used "only when policy treats a warning-class finding as blocking"; each
  gate "may document a narrower subset" of next commands, and `null` is allowed
  (`.claude/skills/aif-verify/references/GATE-RESULT-CONTRACT.md:63-66`).
- **What earlier decisions left to this milestone.**
  - [ADR 0014](0014-process-verification-runtime-resolution.md) §5 adds `checks_run` as an optional
    field, keeps `schema_version` at `1`, and assigns it to milestone 10
    (`docs/adr/0014-process-verification-runtime-resolution.md:303-305`).
  - [ADR 0004](0004-authoring-entry-point.md) says a narrowed run "must say so in `checks_run`"
    (`docs/adr/0004-authoring-entry-point.md:97-100`), and leaves the specification as a follow-up
    (`:150`).
  - [ADR 0018](0018-change-relative-gates.md)'s follow-up: `checks_run` "will record `baseline` as run or
    not run" (`docs/adr/0018-change-relative-gates.md:144`).
  - [ADR 0016](0016-legacy-xsd-lag.md): an `XSD_LAGS_RUNTIME` warning still records `xsd-structure` as
    run (`docs/adr/0016-legacy-xsd-lag.md:61`).
- **The blueprint's gate schema** puts `schema_family` (`json | xsd | both`) on each blocker, and adds
  `affected_processes` and `affected_components` to the block (`docs/blueprint.md:325-347`).
- **From a path to an artifact.**
  - The `legacy-artifacts` table is `knowledge/composition-specs.md:112-122`. A process-local workflow is
    described only in prose (`:124`).
  - `scripts/inventory_root.py:38, 51-59` already maps a workspace-relative path to an artifact, and holds
    `PROCESS_LOCAL_WORKFLOW` (`:41`).
  - `workspace.process_reference()` names a `webasm` process `BASE:<process>`
    (`scripts/lib/workspace.py:214-216`).
  - No `Report` carries a component or process name (`scripts/lib/report.py:165-171`).
- **The size of a whole-root run.** The pipeline spine's walk over DGF's samples validated 3,116 files
  per tree and found 2,552 pre-existing findings in 5.2 s
  (`.ai-factory/archive/plans/feature-pipeline-spine.md:1157-1160`).
- **The doctor is stdlib-only and loads a shared module by path.** `doctor.py:543-551` loads
  `scripts/lib/knowledge.py` with `importlib`, which is why that module imports nothing from its package
  (`scripts/lib/knowledge.py:11-12`). The doctor's tests run a full copy of the plugin
  (`tests/test_doctor.py:31-37`).

## Decision

**Every `dgf-gate-result` block is built by one library, `scripts/lib/gate_result.py`. It computes
`status` and `blocking` from two lists — `blockers` and `warnings` — and it refuses a block that claims
a required check it did not run. The verify gate is a script, `scripts/verify_gate.py`, and the skills
relay its block verbatim.**

The block, with every field:

```dgf-gate-result
{
  "schema_version": 1,
  "gate": "verify",
  "status": "fail",
  "blocking": true,
  "blockers": [
    {"id": "DEAD_TRANSITION", "severity": "error", "file": "zims/FM/_PROCESS/Apply/process.xml", "line": 41,
     "schema_family": "xsd", "summary": "`Review` moves to `Archive`, which is neither a declared state nor `End`"}
  ],
  "warnings": [
    {"id": "not-run-frontend-tests", "severity": "warning", "file": ".dgf-factory/plans/feature-zims-fee.md",
     "line": null, "schema_family": null, "summary": "frontend-tests did not run: the project's own CI runs them"}
  ],
  "affected_files": [".dgf-factory/plans/feature-zims-fee.md", "zims/FM/_PROCESS/Apply/process.xml"],
  "checks_run": ["plan-header", "plan-tasks", "plan-files", "plan-routes", "plan-commits", "change-scope",
                 "change-means", "change-planned", "baseline", "validators"],
  "schema_family": {"json": 212, "xsd": 364},
  "affected_components": [],
  "affected_processes": [{"workspace": "zims", "name": "Apply", "reference": "Apply"}],
  "suggested_next": {"command": "/dgf-implement", "reason": "the change adds a blocking finding"}
}
```

### 1. One builder, and what it refuses

`scripts/lib/gate_result.py` builds and validates every block. It is stdlib-only and imports nothing from
its own package, so the doctor can load it by path, as it loads `knowledge.py`. It takes no `status` and
no `blocking` as input. It raises `GateContractError`, naming the rule broken, for a contradictory block:

- a gate it does not know, or a command outside that gate's allowlist (§8), or an empty reason;
- an entry with no `id`, or a `severity` other than `error` or `warning`; a `warnings` entry claimed as
  an `error`; a `schema_family` other than `json`, `xsd` or `null`;
- required checks with no `checks_run`;
- a required check that neither ran nor has a `not-run-<check>` entry, or that has both;
- a `schema_family` count that is not a non-negative integer, or is keyed by anything other than `json`,
  `xsd` and `unresolved`.

A caller that has nothing to build — a gate that could not run at all — emits no block, and a consumer
reads a missing block as a gate that did not run.

### 2. Status and `blocking`

- **`blockers` holds only what blocks**, as AI Factory's contract requires. A separate **`warnings`**
  array holds every non-blocking warning and every required check that did not run.
- `status` is `fail` if any blocker, else `warn` if any warning, else `pass`.
- `blocking` is `status == "fail"`, for every gate.

### 3. The entry and `affected_files`

- An entry is `{id, severity, file, line, schema_family, summary}`. `file` is root-relative; `line` is an
  integer or `null`. `summary` is capped at 240 characters, cut with `…`.
- `affected_files` is every file an entry names, plus any file the gate adds — the plan, for `verify` —
  sorted, with no duplicates.
- The block is `json.dumps(…, indent=2)`, which escapes control characters, so no summary can close the
  fence.

### 4. `checks_run`, required checks and narrowing

- `checks_run` is the ordered union of the check ids that ran.
- Each gate names its **required checks**. A required check that did not run is a `not-run-<check>`
  warning, and its summary carries the script's reason.
- The check **`validators` means the whole-root validator run.** A `--files` run records it `NOT RUN`
  ("narrowed to N file(s) by --files"), so a narrowed run can never read as a pass. This is the
  specification ADR 0004 left to this milestone.
- `baseline` is recorded as run or not run, as ADR 0018 foresaw. A check that ran and warned — ADR 0016's
  `xsd-structure` — is still a check that ran.

### 5. `schema_family`

- At block level, `{"json": <n>, "xsd": <n>}` counts the files the validators read, per resolved family.
  It carries `"unresolved": <n>` only when there are any.
- On each entry, `schema_family` is `"json"`, `"xsd"` or `null`: the family of the file a validator
  finding is in, and `null` for a finding that is not a validator's.
- The blueprint's `"both"` is dropped: a finding is in one file, and a file resolves to one family.

### 6. The footprint: `affected_components` and `affected_processes`

These are **the change's own footprint** — the configuration it added, edited, deleted or renamed. They
are not its blast radius: which processes reach a changed shared workflow is `/dgf-audit`'s question
(milestone 12).

- `affected_processes`: each `{workspace, name, reference}` whose `<ws>/FM/_PROCESS/<name>/` folder holds a
  changed file — its `process.xml`, a process-local workflow, or anything else in it. `reference` is the
  process's reference form, so a `webasm` process reads `BASE:<name>`.
- `affected_components`: `{workspace, artifact, name, file, change}` for every other changed configuration
  file, in both families. `artifact` is `component` for `FM/_COMPONENTS/…json`, the `legacy-artifacts`
  row's artifact for a legacy file, `form` for a changed `_form.js`, and `configuration` for a
  configuration file matching no shape. A legacy form, view or settings file is a component-bearing
  artifact, not an omission. Global `js/`, `FM/js/` and `css/` files are code places, not components.
- A rename is its old path deleted and its new path added. Paths outside a known workspace are skipped.

### 7. Absent means not computed

A field the gate did not compute is **left out** of the block, never emitted empty; `[]` means "computed,
and none". The doctor reads no estate, so its block omits `schema_family`, `affected_components` and
`affected_processes`. It emits `checks_run`.

### 8. Gate ids and allowlists

| Gate | Built by | `suggested_next.command` |
|---|---|---|
| `verify` | `scripts/verify_gate.py` | `/dgf-plan`, `/dgf-implement`, `/dgf-commit`, `null` |
| `doctor` | `skills/dgf-doctor/scripts/doctor.py` | `null` — a broken install is fixed by hand |

The doctor's gate is no longer `verify`. `/dgf-fix` joins an allowlist when milestone 11 builds it.

### 9. The verify gate is a script, and strict mode

- `scripts/verify_gate.py` finds the root and the plan, runs `check_plan.py`'s and `check_change.py`'s
  checks in-process, audits the tasks, computes the status and prints the one block, last. `/dgf-verify`
  relays it, as `/dgf-doctor` relays `doctor.py`'s. The contract's status table stops being arithmetic done
  by the model.
- Its required checks are `plan-header`, `plan-tasks`, `plan-files`, `plan-routes`, `plan-commits`,
  `change-scope`, `change-means`, `change-planned`, `baseline` and `validators`, plus `frontend-tests` when
  any task is `kind: code`. `frontend-tests` never runs in the gate (ADR 0010 §2), so it is always a
  warning. `plan-overlap` is not required.
- `suggested_next`, first match wins: `null` when the gate could not run (a missing dependency, a
  malformed knowledge table, no root, an ambiguous or unconfirmed plan); `/dgf-plan` for a plan defect —
  including `PLAN_COMMITS_INVALID` — or no plan; `/dgf-implement` for an unchecked task, a change error or
  a strict-mode promotion; `/dgf-commit` for `pass` and `warn`.
- The exit code agrees with the status: `0` pass, `2` warn, `1` fail, and `3` when a finding forces it.
- **Strict mode is unchanged.** It promotes every `WARN` line `check_change.py` reports into `blockers`.
  Those are new by construction, because a pre-existing finding is `INFO`. It never promotes
  `check_plan.py`'s warnings. A promoted entry keeps `severity: warning`, as AI Factory's contract says a
  policy-promoted warning does.

## Alternatives considered

- **A builder CLI the model feeds.** Rejected: the model would transcribe findings into its arguments,
  which is the arithmetic this ADR takes away from it.
- **Warnings kept in `blockers`.** Rejected: AI Factory's contract keeps `blockers` to what blocks, and
  the doctor's block shows what breaks when it does not — every warning reads as a blocker.
- **Warnings kept in the prose only.** Rejected: a caller parses the block, never the prose, so a
  warning the block omits is invisible to every orchestrator.
- **A per-file family map in the block.** Rejected: a whole-root run over DGF's samples reads 3,116
  files; counts carry the fact, and each entry names its own file's family.
- **Blast radius in `affected_processes`.** Rejected: it needs the process graph `/dgf-audit` builds in
  milestone 12, and a footprint that reads as a blast radius under-reports.
- **Empty arrays for fields not computed.** Rejected: `[]` reads as "none", which is the false claim the
  contract exists to prevent.
- **Keeping `gate: "verify"` for the doctor.** Rejected: an orchestrator would read a doctor pass as a
  verified change.
- **A `gate_result.py` that imports `report`.** Rejected: the doctor loads it by path, where a package
  import cannot resolve.

## Consequences

### Positive

- Every status is computed by a script, and a skipped check is visible in the block itself.
- A narrowed validator run can never read as a gate pass.
- The doctor's block stops suggesting a command that does not exist, and stops blocking on a pass.
- A consumer can tell a JSON finding from an XSD finding, and see which configuration the change touched.

### Negative

- **`/dgf-verify`'s milestone-9 block changes.** `not-run-*` entries move from `blockers` to `warnings`,
  and new warnings are listed where they were prose. `schema_version` stays `1`, because every change is
  additive or re-classifies an entry, but a consumer that counted `blockers` counts fewer.
- A consumer that knows only AI Factory's gate ids does not know `doctor`.
- A plugin copy without `scripts/` now warns (`not-run-validator-runtime`) instead of passing silently.
- `verify_gate.py` couples to `check_plan.py`'s and `check_change.py`'s functions, not just their exit
  codes. Their CLI output is pinned by tests so the coupling cannot drift unseen.
- The footprint is not the blast radius: a change to a shared workflow lists the workflow, not the
  processes that call it.

### Follow-ups

- `/dgf-fix` joins the `verify` and `doctor` allowlists when milestone 11 builds it.
- `/dgf-commit` could read the parsed Commit Plan from a script instead of parsing prose.
- This ADR answers [ADR 0004](0004-authoring-entry-point.md)'s narrowing follow-up (§4) and
  [ADR 0018](0018-change-relative-gates.md)'s `checks_run` follow-up (§4). Neither ADR is edited: a
  follow-up is not a decision.

## Errata

- **2026-09-25** — §Consequences (Negative) said "A plugin copy without `scripts/` now warns
  (`not-run-validator-runtime`) instead of passing silently". That holds when another copy's doctor
  checks it. A copy's own doctor loads its builder from its own `scripts/lib/gate_result.py` (§1), so
  without `scripts/` it exits `3` with no block. Source: `skills/dgf-doctor/scripts/doctor.py`
  (`load_gate_builder()`, and `resolve_root()` with no argument); found by review before merge.
- **2026-09-26** — §Context left out what the tests pin, which the plan cites as its evidence for the
  gate's tests. Each of the 51 known-bad cases runs from its own directory, exits `1` or `3`, and reports
  every code it expects and no `ERROR` it does not (`tests/test_known_bad.py:44, 60-68`).
  `tests/test_skill_contracts.py` reads finding codes from `report.CODES` (`:62`) and flags from each
  called script's `--help` (`:55`, `:103-106`), and names the spine scripts the skills must call (`:110`).
  Nothing decided rests on it. Source: those files at `develop` `f8444ef`; found by `/aif-verify`.
