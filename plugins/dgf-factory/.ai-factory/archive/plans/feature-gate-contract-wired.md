---
archived: 2026-09-26
---
# Implementation Plan: Gate Contract Wired

Branch: feature/gate-contract-wired
Created: 2026-09-25
Refined: 2026-09-25 — `/aif-improve`:

- the ultra template's Commit Plan example is made consistent with its tasks;
- the Commit Plan parser never raises, accepts quoted messages, and checks only a range's ends;
- `test_report`'s pinned severities cover the new codes;
- the doctor's negative assertions read both lists;
- the gate fixtures carry a `config.yaml`, and a no-`lxml` `--help` test is added;
- the input refusal takes plain values, `run()` gains `skip_reason=`, and the plan is parsed once for the task audit;
- `artifact_inside()` is added for the inventory;
- missing doc anchors are added, and Task 11 depends on Task 6.

Base: `develop` at `f8444ef`. `config.yaml` names `main` as `git.base_branch`, but `main` (`0e28010`) is 65 commits
behind `develop` and lacks milestones 6–9, which this plan builds on. The branch is cut from `develop` and merges
back into it, as milestone 9's did.

## Original Request

**Gate Contract Wired** — `dgf-gate-result` blocks carrying `schema_family`, `checks_run`, affected components and affected processes, last-block-wins; a gate may never read as having passed a check it did not run. `scripts/lib/gate_result.py` builds every block, the doctor's included — today the doctor's always reports `"blocking": true` and suggests the unbuilt `/dgf-fix`, even on a pass — with `blocking` true exactly when `status` is `fail`. Also: `check_plan.py` checks that a plan's Commit Plan groups agree with its task numbering, which is still left to the model ([ADR 0014](../docs/adr/0014-process-verification-runtime-resolution.md); follow-ups in `plans/feature-pipeline-spine.md`)

## Settings

- **Testing: yes.** A stdlib `unittest` test for every new module, check and finding code, run from the plugin root
  with `python3 -m unittest discover -s tests -t .` (prefer `.venv/bin/python` when it exists). Every new blocking
  code gets a known-bad fixture under `tests/fixtures/known-bad/` (E10). Tests that need `git` skip through
  `helpers.have_git()`, and tests that need `lxml` or `jsonschema` skip through `helpers.have_dependencies()`. A
  test that asserts an exact finding list must pass under an interpreter without either (`.ai-factory/RULES.md`).
- **Logging: verbose.** No logging framework (`.ai-factory/rules/base.md` §Logging). New code traces through
  `report.debug("<module>.<function>", message, key=value…)`, shown on **stderr** under `--verbose`, `DEBUG=1` or
  `LOG_LEVEL=debug`. `scripts/lib/gate_result.py` imports nothing from its package, so it keeps its own `_debug()`,
  shaped like `scripts/lib/knowledge.py:97-101`. Report lines go to stdout, usage errors through `report.fail()`.
- **Docs: yes.** A mandatory documentation checkpoint at completion (Task 12).
- **Decisions** (→ ADR 0020, Task 1). D1 is the user's (Andrian Mamei, 2026-09-25). D2–D12 are the planner's, taken
  from the evidence below; reverse any of them at review.
  - **D1 — Warnings get their own array.** `blockers` holds only what blocks, as AI Factory's contract requires
    (E5). A new `warnings` array holds every non-blocking warning and every required check that did not run. The
    status is then a function of the two lists: `fail` if any blocker, `warn` if any warning, else `pass`.
  - **D2 — One builder.** `scripts/lib/gate_result.py` builds and validates every block. It is stdlib-only and imports
    nothing from its own package, so the doctor loads it by path, the way it loads `knowledge.py` (E11). It
    refuses a contradictory block by raising `GateContractError`: a command outside the gate's allowlist, a
    required check that neither ran nor has a `not-run-<check>` entry, a warning-severity entry claimed as an
    error. It takes no `status` or `blocking` as input; it computes both.
  - **D3 — `blocking` is `status == "fail"`,** for every gate.
  - **D4 — `checks_run`, required checks, and narrowing.** `checks_run` is the ordered union of the check ids that
    ran. Each gate names its required checks. A required check that did not run is a `not-run-<check>` warning
    carrying the script's reason. The check `validators` means **the whole-root validator run**: a `--files` run
    records it `NOT RUN` ("narrowed to N file(s) by --files"), so a narrowed run can never read as a pass. This is
    the "narrowing filter's interaction with `checks_run`" that ADR 0004 left to this milestone (E6).
  - **D5 — `schema_family` at two levels.** At block level, `{"json": <files>, "xsd": <files>}` counts the files the
    validators read, per resolved family. It carries `"unresolved"` only when there are any. On each entry,
    `schema_family` is `"json"`, `"xsd"` or `null`, the family of the file a validator finding is in. The
    blueprint's `"both"` is dropped: a finding is in one file, and a file resolves to one family (E4, E7).
  - **D6 — `affected_components` and `affected_processes` are the change's own footprint**: the configuration it
    added, edited, deleted or renamed. They are not its blast radius, which is `/dgf-audit`'s (milestone 12). They
    cover both families: a legacy form, view or settings file is an affected component-bearing artifact, not an
    omission (DD4).
  - **D7 — Absent means not computed; `[]` means none.** A field the gate did not compute is left out of the block,
    never emitted empty. The doctor reads no estate, so it omits `schema_family`, `affected_components` and
    `affected_processes`. It emits `checks_run`.
  - **D8 — Gate ids and allowlists.** `verify` allows `/dgf-plan`, `/dgf-implement`, `/dgf-commit` and `null`, as
    today. The doctor's gate id becomes `doctor`, and its allowlist is `null` alone: a broken install is fixed by
    hand. `/dgf-fix` joins an allowlist only when milestone 11 builds it.
  - **D9 — The verify gate is a script.** `scripts/verify_gate.py` runs `check_plan.py`'s and `check_change.py`'s
    checks in-process, audits the tasks, computes the status and prints the one block. `/dgf-verify` relays its
    output verbatim, the way `/dgf-doctor` relays `doctor.py`'s. The status table in `GATE-RESULT-CONTRACT.md`
    stops being arithmetic done by the model (E2).
  - **D10 — The Commit Plan check.** `check_plan.py` gains `plan-commits`. `PLAN_COMMITS_INVALID` (error) covers a
    line of the wrong shape, a group numbered out of order, a range naming a task that does not exist, and a task
    in no group or in two. `PLAN_COMMITS_MISSING` (warning) covers five or more tasks with no Commit Plan (E8).
  - **D11 — The entry shape.** An entry is `{id, severity, file, line, schema_family, summary}`, and `summary` is
    capped at 240 characters. `affected_files` is every file an entry names, plus the plan for `verify`, sorted
    and unique.
  - **D12 — Strict mode is unchanged.** It promotes every `WARN` line that `check_change.py` reports into
    `blockers`. Those are new by construction, because pre-existing findings are `INFO`. It never promotes
    `check_plan.py`'s warnings.

## Roadmap Linkage

Milestone: "Gate Contract Wired"
Rationale: This plan implements the milestone as written, including the two open items the spine plan left for it
(the doctor's block, and the Commit Plan check).

## Evidence

Read on 2026-09-25 at `develop` `f8444ef`.

- **E1 — The doctor's block is fixed text.** `skills/dgf-doctor/scripts/doctor.py:591-618`, `gate_block()`:
  - It always emits `"blocking": True` (`:609`) and `"command": "/dgf-fix"` (`:614`), a skill that does not exist
    (`.ai-factory/ROADMAP.md:19`).
  - It uses `"gate": "verify"` (`:607`).
  - Its `blockers` are all of `FINDINGS` (`:610`), and `warn()` puts warnings there too (`:136-138`).
  - It emits `affected_processes: []` and `affected_components: []` (`:612-613`), which it never computed.
  - It has no `checks_run`, although three sections skip silently: component paths without a manifest
    (`:292-294`), skill slices without `skills/` (`:337-339`), and the validator runtime without `scripts/`
    (`:482-484`).
  - `tests/test_doctor.py:23-27` reads only `blockers[].id`, so nothing pins `blocking` or `suggested_next`.
- **E2 — `/dgf-verify`'s block is assembled by the prompt.** `skills/dgf-verify/SKILL.md:119-143` (Step 5) builds
  it from the rules in `references/GATE-RESULT-CONTRACT.md`: the status table (`:40-50`), blockers (`:52-64`),
  required checks (`:66-80`), and the four fields not yet emitted (`:91-99`).
- **E3 — `check_change.py` never records `validators` as run.** The only mention is
  `rep.skipped("validators", "--skip-validators")` (`scripts/check_change.py:320`). A `--files` run is
  indistinguishable from a whole-root run in `CHECKS RUN:`.
- **E4 — Families are known per file and lost in the merge.** `report.Report.family` (`scripts/lib/report.py:168`).
  `runner.run()` returns `{cli: [Report]}` (`scripts/lib/runner.py:57-90`). `check_change.validator_report()`
  merges checks and findings and drops each family (`scripts/check_change.py:241-249`).
- **E5 — AI Factory's contract.** `blockers` "contains only findings that should block"; `severity: warning` only
  "when policy treats a warning-class finding as blocking"; each gate documents a narrower command allowlist, and
  `null` is allowed (`.claude/skills/aif-verify/references/GATE-RESULT-CONTRACT.md`, §Rules and §"Suggested Next
  Command").
- **E6 — What earlier decisions left to this milestone.**
  - ADR 0014 §5 makes `checks_run` an additive field, keeps `schema_version` at `1`, and assigns it to milestone 10
    (`docs/adr/0014-process-verification-runtime-resolution.md:303-305`).
  - ADR 0004 says a narrowed run "must say so in `checks_run`" (`docs/adr/0004-authoring-entry-point.md:97-100`),
    and leaves the specification as a follow-up (`:150`).
  - ADR 0018's follow-up: `checks_run` "will record `baseline` as run or not run"
    (`docs/adr/0018-change-relative-gates.md:144`).
  - ADR 0016: an `XSD_LAGS_RUNTIME` warning still records `xsd-structure` as run (`docs/adr/0016-legacy-xsd-lag.md:61`).
- **E7 — The blueprint's gate schema.** `docs/blueprint.md:326-347` puts `schema_family` on each blocker
  (`json | xsd | both`), and adds `affected_processes` and `affected_components` to the block.
- **E8 — The Commit Plan is read by eye.**
  - The line shape is given only by example: `ULTRA-FORMAT.md:78-82`, `- **Commit 1** (after tasks 1–3): `…``.
    `PLAN-FORMAT.md:69-70` and `:84-85` give no shape.
  - `ULTRA-FORMAT.md:207-208`: "No script checks the Commit Plan yet."
  - `lib/plan.py` parses only `## Tasks` and `## Phase Index` (`scripts/lib/plan.py:270-296`).
  - `/dgf-commit` parses the groups by hand (`skills/dgf-commit/SKILL.md:77-92`).
  - Real plans write both `-` and `–`, and `after task N` in the singular
    (`.ai-factory/archive/plans/feature-adr-review-corrections.md:75-79`,
    `.ai-factory/archive/plans/feature-deterministic-validators.md:312-319`).
- **E9 — From a path to an artifact.**
  - The `legacy-artifacts` table is at `knowledge/composition-specs.md:112-123`. A process-local workflow is
    described only in prose (`:124-125`).
  - `scripts/inventory_root.py:38, 49-58` already maps a workspace-relative path to an artifact, and holds
    `PROCESS_LOCAL_WORKFLOW`.
  - `lib/workspace.process_reference()` names a `webasm` process `BASE:P` (`scripts/lib/workspace.py:214-216`).
  - No `Report` carries a component or process name (`scripts/lib/report.py:166-171`).
- **E10 — What the tests pin.**
  - Known-bad cases run from their directory, and use `--changed` to stay independent of git
    (`tests/fixtures/known-bad/change-undeclared-workspace/expected.json`).
  - Each case exits `1` or `3`, and reports no ERROR it did not expect (`tests/test_known_bad.py:44, 60-61`). There
    are 51 cases.
  - `tests/test_skill_contracts.py` reads finding codes from `report.CODES` (`:60-61`) and flags from each called
    script's `--help` (`:97`), and hard-codes the spine scripts (`:105`).
- **E11 — The doctor is stdlib-only and loads a shared module by path.** `doctor.py:543-551`;
  `scripts/lib/knowledge.py:11-12`. Its tests run a full copy of the plugin (`tests/test_doctor.py:31-37`).
- **E12 — The docs check does not read gate wording.** `tools/check-dual-schema-docs.sh` section 6 uses only the
  doctor's exit code (`:645-650`); section 8 runs the test suite (`:713`).

## Design

### DD1 — `scripts/lib/gate_result.py`

```python
SCHEMA_VERSION = 1
GATES = {"verify": ("/dgf-plan", "/dgf-implement", "/dgf-commit", None), "doctor": (None,)}
FAMILIES = ("json", "xsd")
SUMMARY_MAX = 240

class GateContractError(ValueError): ...

def entry(id, severity, summary, file=None, line=None, schema_family=None) -> dict
def not_run(check, reason, file=None) -> dict          # id "not-run-<check>", severity "warning"
def build(gate, blockers, warnings, command, reason, *, checks_run=None, required=(),
          extra_files=(), schema_family=None, affected_components=None, affected_processes=None) -> dict
def render(payload) -> str                              # "```dgf-gate-result\n<json indent=2>\n```"
def last_block(text) -> dict | None                     # the consumer's rule: the last fenced block wins
```

`build()` checks every rule below, and raises `GateContractError` naming the rule it broke:

- `gate` is in `GATES`, `command` is in `GATES[gate]`, and `reason` is a non-empty string.
- Every entry has a non-empty `id` and a `severity` of `error` or `warning`; every `warnings` entry is a `warning`;
  `schema_family` is in `FAMILIES` or `None`.
- `required` is non-empty only when `checks_run` is given.
- Each required check is in `checks_run`, or has a `not-run-<check>` entry, and never both.
- `schema_family` counts are non-negative ints, keyed by `FAMILIES` plus `unresolved`.

Then `status = "fail" if blockers else "warn" if warnings else "pass"`, and `blocking = status == "fail"`.
`affected_files` is the sorted, unique set of the entries' `file` values plus `extra_files`.

The keys come in a fixed order: `schema_version`, `gate`, `status`, `blocking`, `blockers`, `warnings`,
`affected_files`, then `checks_run`, `schema_family`, `affected_components` and `affected_processes` when given,
then `suggested_next`. A `summary` longer than `SUMMARY_MAX` is cut to it, ending in `…`. `render()` uses
`json.dumps(payload, indent=2)`, which escapes control characters, so no summary can break out of the fence.

### DD2 — `scripts/verify_gate.py`

```
verify_gate.py [--workspaces-root R] [--plans-dir D] [--fast-plan F] [--branch B] [--plan P]
               [--base REF | --changed S:PATH ...] [--no-overlap] [--strict] [--verbose]
```

1. **Discovery.** The root comes from `--workspaces-root`, else `locate_plan`'s ancestor and descendant search.
   The plan comes from `--plan`, else `locate_plan`'s branch discovery. Call `locate_plan`'s functions in-process
   (`explicit_root`/`find_root`, `find_plan`), never its CLI.
   - `ROOT_NOT_SET_UP`, `ROOT_AMBIGUOUS` or `PLAN_AMBIGUOUS` → `fail`, command `null`, and no check runs.
   - `PLAN_NOT_FOUND` → `fail`, command `/dgf-plan`.
   - `PLAN_FALLBACK` without `--plan` → the new `GATE_PLAN_UNCONFIRMED` (error): the gate never chooses a plan
     for the user.
   - A discovery failure builds its block with `checks_run: []` and no required checks: nothing ran, and the block
     says so.
   - `plans_dir` and `fast_plan` resolve against the root, as in `locate_plan.main()` (`root / args.plans_dir`).
2. **The call itself.** Once a plan is confirmed and neither `--base` nor `--changed` is given → `report.fail(3)`,
   with no block: the call is wrong, not the change. `--base`, `--changed` and their paths go through
   `check_change.refuse(base, files, changed)` (DD6): a `--base` starting with `-`, or a path that leaves the root,
   is exit `3`.
3. **Plan.** `check_plan.check(plan, root, overlap=not args.no_overlap)`, which returns `(Report, lines)` and no
   parsed plan. On `PLAN_UNREADABLE` or `PLAN_FORMAT_UNSUPPORTED`, skip steps 4–6: their checks are NOT RUN, "the
   plan is unreadable". Otherwise parse the plan once with `plan.parse()` for step 6's task audit.
4. **Dependencies.** If `lib.deps.missing()` returns anything → a `DEPENDENCY_MISSING` finding (exit `3`), whose
   message carries `deps.install_command()`. Step 5 then runs with `skip_validators=True` and
   `skip_reason="lxml, jsonschema not installed"`: the change checks still report, and `validators` and
   `baseline` are NOT RUN with that reason.
5. **Change.** `check_change.run(root, plan, base=…, changed=…)` (Task 7).
6. **Gate findings,** in a `Report("(gate)")`:
   - `GATE_TASK_UNCHECKED` (error) for each unchecked task in the parsed plan, at its line.
   - `GATE_STRICT_WARNING` (error) under `--strict`, for each `WARN` finding `check_change` reported.
   - `GATE_CHECK_NOT_RUN` (warning) for each required check that did not run, with the reason the script gave.
7. **Required checks:** `plan-header`, `plan-tasks`, `plan-files`, `plan-routes`, `plan-commits`,
   `change-scope`, `change-means`, `change-planned`, `baseline`, `validators`. Add `frontend-tests` when any task
   is `kind: code`. It never runs here (ADR 0010 §2), so it is always a `not-run-frontend-tests` warning.
   `plan-overlap` is not required.
8. **Output.** `report.render()` with header `Verify gate`.
   - Lines: `ROOT:`, `check_plan`'s `PLAN:`/`AFFECTS:`/`TASK:`/`PROGRESS:`/`OVERLAP SOURCES:`, `check_change`'s
     `BASE:`/`CHANGED:`/`CHANGE:`, and `CODE TASK: <N> reason="<reason>"` for each code task.
   - Findings: all of them, except that `PRE_EXISTING` and `FIXED` are cut to their first 20 each.
   - Summary: `Validated:`, `new: … pre-existing: … fixed: …`, `Shown: 20 of <n> PRE_EXISTING — check_change.py
     --base <ref> lists every one` (only when cut), and `STATUS: <status>`.
   - Then the verdict line, a blank line, and the block, **last**, with nothing after it.
9. **Exit.** `report.exit_code()` over the rendered reports. The `GATE_*` codes make it agree with the status:
   `0` pass, `2` warn, `1` fail, and `3` when a finding forces it (`DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE`,
   `PLAN_UNREADABLE`, `PLAN_FORMAT_UNSUPPORTED`). A `KnowledgeTableError` becomes a `KNOWLEDGE_TABLE` finding,
   not a traceback.

**From findings to entries:**

| Finding | List | `id` | `severity` | `file` | `schema_family` |
|---|---|---|---|---|---|
| `GATE_TASK_UNCHECKED` | blockers | `task-<N>` | error | the plan | `null` |
| `GATE_STRICT_WARNING` | blockers | the promoted finding's code | warning | its file | its file's family |
| `GATE_CHECK_NOT_RUN` | warnings | `not-run-<check>` | warning | the plan | `null` |
| any other `ERROR` line | blockers | its code | error | its file (a plan finding → the plan) | the file's family for a validator finding, else `null` |
| any other `WARN` line, not promoted | warnings | its code | warning | its file | as above |
| `INFO` (`PRE_EXISTING`, `FIXED`, `PLAN_OVERLAP_UNREADABLE`, …) | never | | | | |

Every `file` is root-relative. The plan's path is made relative to the root, not to the working directory, as
`cli.display()` would make it. A promoted warning appears once, in `blockers`.

**`suggested_next`, first match wins:**

1. `null` when the gate could not run: `DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE`, `ROOT_*`, `PLAN_AMBIGUOUS` or
   `GATE_PLAN_UNCONFIRMED`. The reason names the fix: the install command, `run /dgf`, or `pass --plan`.
2. `/dgf-plan` when `check_plan` reported an error, including `PLAN_UNREADABLE`, `PLAN_FORMAT_UNSUPPORTED` and the
   new `PLAN_COMMITS_INVALID`, or when there is no plan (`PLAN_NOT_FOUND`).
3. `/dgf-implement` for an unchecked task, a `check_change` error, or a strict-mode promotion.
4. `/dgf-commit` for `pass` or `warn`.

**Block fields:** `checks_run` is the union over every report. `schema_family` is present when the validators ran
(DD5 counts, from `check_change.run()`'s `families`). `affected_components` and `affected_processes` are present
when there is a changed set (DD4).

### DD3 — The doctor

- `CHECKS_RUN` and `NOT_RUN` lists, beside `FINDINGS`, for the six section ids: `manifest`, `component-paths`,
  `skill-slices`, `portability`, `line-endings` and `validator-runtime`. Build progress is `INFO`, not a check.
- The three silent skips in E1 become `NOT RUN` with their reason. Every section is required.
- The summary prints `CHECKS RUN:` and `NOT RUN:` lines.
- `gate_block()` becomes a call to `gate_result.build("doctor", …)`, with command `null` and the existing reasons
  (fail and warn say to fix by hand and re-run). Errors go to `blockers`; warnings and `not-run-*` entries go to
  `warnings`. `line` stays `null`: the doctor's messages carry `file:line` in their text.
- `gate_result.py` is loaded by path from the doctor's **own** plugin (`Path(__file__).resolve().parents[3]`), not
  from the root it checks. It is the doctor's machinery, not the thing checked. If it is missing or does not load
  → `fail(3, …)` naming the file, and no block: a caller treats a missing block as a gate that did not run. Load
  it in `report()`, never at import: `tests/test_known_bad.py:27-31` imports `doctor.py` for `SHIPPED_DIRS`.

### DD4 — The footprint

`lib/plan.artifact_inside(parts)` returns `(artifact, name)` for a path given as its segments inside its workspace
(`["FM", "_PROCESS", "Case", "process.xml"]`), or `None`. `lib/plan.artifact(rel_path)` wraps it for a
root-relative path by dropping the first segment. `inventory_root._artifact()` already works on workspace-relative
`inside` parts, so it is rewritten on top of `artifact_inside()` — the second use (ARCHITECTURE.md Key Principle 1):

| Path, inside its workspace | `artifact` | `name` |
|---|---|---|
| `FM/_COMPONENTS/<path>.json` | `component` | `<path>` without `.json` (`Button/ApplyNow`, `DataSource/Fee`, or the site map at `(root)`) |
| a `legacy-artifacts` row: filename and folder pattern | the row's `Artifact` (`process`, `workflow`, `form`, `settings`, `table-view`, `lookup-view`, `grid-form`, `options`) | the placeholder values joined by `/` (`Cases/Apply`) |
| `FM/_PROCESS/<process>/<workflow>/_workflow.xml` | `process-workflow` | `<process>/<workflow>` |

`PROCESS_LOCAL_WORKFLOW` moves from `inventory_root.py` to `lib/plan.py`. `inventory_root` maps
`process-workflow` to its `workflows` count, so every count stays the same.

`verify_gate.footprint(changes, known)` builds both lists. A rename counts as its old path deleted (`D`) and its
new path added (`A`). Paths outside a known workspace are skipped.

- **`affected_processes`:** each `{workspace, name, reference}` whose `<ws>/FM/_PROCESS/<name>/` folder holds a
  changed file — `process.xml`, a process-local workflow, or anything else in it. `reference` comes from
  `workspace.process_reference()`, so a `webasm` process reads `BASE:<name>`. Sorted and unique.
- **`affected_components`:** `{workspace, artifact, name, file, change}` for every other changed `config`-class
  file, with `artifact` from `plan.artifact()`. A config file matching no shape is `artifact: "configuration"`,
  named by its path under `FM/`. A changed `_form.js` names its form (`artifact: "form"`). Global `js/`,
  `FM/js/` and `css/` files are code places, not components, and are not listed. Sorted by `file`.

### DD5 — The Commit Plan

`lib/plan.py` records the section; it does not judge it:

- `Plan.commit_section` is `True` when a `## Commit Plan` heading exists.
- `Plan.commits` is a list of `Commit(line, text, number, first, last, message)`, one per line starting `- `
  under that heading and outside fences. A line of the wrong shape keeps `number=None`.
- The shape:

  ```python
  _COMMIT_LINE = re.compile(r"- \*\*Commit (\d+)\*\* \(after tasks? (\d+)(?:\s*[-–]\s*(\d+))?\): "
                            r"(?:`([^`]+)`|\"([^\"]+)\")\s*\Z")
  ```

  The message may be in backticks (this plugin's formats) or in double quotes (AI Factory's `TASK-FORMAT.md`).
  Lines not starting `- ` (prose, template placeholders) are ignored.
- **The parser never raises on a Commit Plan line.** `check_plan.py`'s overlap scan parses other branches' plans
  with `plan.parse_text()` (`scripts/check_plan.py:494`). A raise there would turn a plan with a malformed Commit
  Plan into `PLAN_OVERLAP_UNREADABLE`, hiding a real overlap.

`check_plan.check_commits(parsed, rep)` runs as check `plan-commits`, after `plan-tasks`:

- Five or more tasks, and no section or no `- ` line in it → `PLAN_COMMITS_MISSING`: "the plan has N tasks and no
  Commit Plan — the format asks for a commit every 3–5 tasks".
- A section with fewer than five tasks is checked like any other; its absence is fine.
- Each of the following is `PLAN_COMMITS_INVALID`, at its line:
  - a line of the wrong shape: "is not a Commit Plan line — the shape is `- **Commit N** (after tasks A–B):
    \`message\``" (the text shown is cut by `check_plan._shown()`);
  - Commit *k* not numbered *k*;
  - a range with `first > last`;
  - a range whose `first` or `last` is not a task. Ids missing inside a range are skipped, because `check_plan.py`
    allows gaps in the task numbering, and `after tasks 1–5` over tasks 1, 2, 3 and 5 is a fair group;
  - a group that does not start after the previous group's last task;
  - a task in no group, or in two.

### DD6 — `check_change.py`

`refuse_bad_inputs(args)` (`scripts/check_change.py:78`) becomes `refuse(base, files, changed)` over plain values.
`main()` calls it with `args.base, args.files, args.changed`, and `verify_gate.py` calls it with its own flags.

`check()` becomes `run(root, plan_path, *, base=None, changed=None, files=None, skip_validators=False,
skip_reason="--skip-validators") -> Outcome`. `skip_reason` is the reason recorded for `validators` and `baseline`
when `skip_validators` is set. `Outcome` is a dataclass holding:

- `reports` (the list `main()` renders), `lines` and `summary`;
- `changes` — the pipeline's own changes removed, or `None` when there is no changed set;
- `families` — `{root-relative file: family}` from the head run;
- `validated` — the file count;
- `parsed` — the plan, or `None` when it is unreadable.

`main()` keeps argparse, `refuse_bad_inputs()` and the render, and its output is unchanged except for one line:
- a whole-root run records `rep.ran("validators")`;
- a `--files` run records `rep.skipped("validators", f"narrowed to {n} file(s) by --files; the gate's scope is the
  whole root (ADR 0004 §3)")`;
- `--skip-validators` keeps its reason.

## Commit Plan

- **Commit 1** (after task 1): `docs(adr): decide the gate block contract`
- **Commit 2** (after tasks 2–3): `feat(scripts): build every gate block in lib/gate_result.py, the doctor's first`
- **Commit 3** (after tasks 4–6): `feat(scripts): check that a plan's Commit Plan agrees with its tasks`
- **Commit 4** (after tasks 7–10): `feat(scripts): compute the verify gate in verify_gate.py`
- **Commit 5** (after tasks 11–12): `docs: document the wired gate contract and mark the milestone done`

## Tasks

### Phase 1: Decision

- [x] **Task 1: Write ADR 0020 — the gate block contract, and index it.**
  Create `docs/adr/0020-gate-block-contract.md`, status `accepted`, date 2026-09-25, deciders `[Andrian Mamei]`,
  `supersedes: []`, tags `[gates, pipeline]`, following `docs/adr/README.md` §"Section contract".
  - *Title:* "Every gate block is built by one library, its status computed from its entries, and it never claims a
    check it did not run".
  - *Context* (cite, don't recall): E1–E7 and E9–E11, with paths, lines and the read date.
  - *Decision:* D1–D9, D11 and D12, as sections:
    - §1 the builder and its refusals (D2);
    - §2 status and `blocking` (D1, D3);
    - §3 the entry shape and `affected_files` (D11);
    - §4 `checks_run`, required checks and narrowing (D4);
    - §5 `schema_family` (D5);
    - §6 the footprint (D6);
    - §7 absent versus empty (D7);
    - §8 gate ids and allowlists (D8);
    - §9 the verify gate as a script, and strict mode (D9, D12).
    D10 is a plan-format check (ADR 0017), not a gate decision; §9 names `PLAN_COMMITS_INVALID` among the
    `/dgf-plan` routes only.
  - *Alternatives:*
    - a builder CLI the model feeds (rejected: the model would transcribe findings);
    - warnings kept in `blockers`, and warnings kept in prose only (both put to the user; rejected, E5 and E1);
    - a per-file family map (rejected: over 3,000 files per run in DGF's samples);
    - blast radius in `affected_processes` (rejected: `/dgf-audit`, milestone 12);
    - empty arrays for fields not computed (rejected: `[]` reads as "none");
    - keeping `gate: "verify"` for the doctor (rejected: an orchestrator would read a doctor pass as a verified
      change);
    - a `gate_result` that imports `report` (rejected: the doctor loads it by path, E11).
  - *Consequences:*
    - Positive: every status is computed, and a skipped check is visible in the block.
    - Negative: `/dgf-verify`'s milestone-9 block changes — `not-run-*` moves from `blockers` to `warnings`, and
      new warnings are now listed — although `schema_version` stays `1`, because every change is additive or
      re-classifies. A consumer that knows only AI Factory does not know `doctor`. A plugin copy without
      `scripts/` now warns. `verify_gate.py` couples to `check_plan`'s and `check_change`'s functions.
    - Follow-ups: `/dgf-fix` joins the allowlists in milestone 11; `/dgf-commit` could read parsed Commit Plan
      lines from a script instead of prose.
  - It answers ADR 0004's narrowing follow-up and ADR 0018's `checks_run` follow-up by reference. **Do not edit
    ADRs 0004, 0014 or 0018**: follow-ups are not decisions, and the contract allows only errata.
  - Add row 0020 to `docs/adr/README.md` §Index, Status `accepted`, and extend its §"See Also" line on ADR groups.
  - Run `tools/check-dual-schema-docs.sh`: sections 5 and 5b must pass. Fix any frontmatter or link it reports.
  - Files: `docs/adr/0020-gate-block-contract.md`, `docs/adr/README.md`.

### Phase 2: The builder, and the doctor on it

- [x] **Task 2: Add `scripts/lib/gate_result.py`.** (depends on 1)
  - Implement DD1 exactly. The module docstring states the contract in brief (D1–D4, D7, D8, D11) and that it
    imports nothing from its package.
  - `_debug("gate_result.build", "built", gate=…, status=…, blockers=n, warnings=n, checks=n)` on every build.
    `_debug("gate_result.build", "refused", rule=…)` just before each `GateContractError`.
  - `tests/test_gate_result.py`, loading the module through `importlib.util.spec_from_file_location` **in
    isolation**, never as `lib.gate_result`, so a relative import would fail the test:
    - status and `blocking` for none / warnings only / blockers only / both;
    - each refusal in DD1;
    - `summary` capped at 240 with `…`;
    - `affected_files` sorted, unique, with `extra_files`;
    - optional fields omitted when `None`, and emitted when `[]`;
    - key order;
    - `render()` then `last_block()` round-trips, and `last_block()` picks the last of two blocks;
    - a summary holding a newline and a fence stays inside one JSON string;
    - the module imports under `helpers.run_cli_blocking`-style blocking of `lxml` and `jsonschema`.
  - Files: `scripts/lib/gate_result.py`, `tests/test_gate_result.py`.

- [x] **Task 3: Build the doctor's block with `gate_result.py`.** (depends on 2)
  - Implement DD3 in `skills/dgf-doctor/scripts/doctor.py`.
    - Replace `gate_block()`, and rename `load_knowledge_module()` to `load_lib_module(root, name)`, used for both
      modules.
    - Keep `trace()` lines for each `NOT RUN`, and `trace(f"gate: loaded {path}")`.
    - The docstring gains the gate id, the block's fields, and exit `3` for a missing builder.
  - `skills/dgf-doctor/SKILL.md`:
    - Step 3 names what the block holds: `gate: "doctor"`, `blocking` only on a fail, warnings in `warnings`,
      `checks_run`, and `suggested_next.command` always `null`.
    - Step 2 gains the exit `3` row's second cause: the plugin's own `scripts/lib/gate_result.py` is missing
      (reinstall).
    - `version: 0.2.0`.
  - `tests/test_doctor.py`:
    - `gate_ids()` → `gate_entries(stdout, list_name)`;
    - every negative assertion (`assertNotIn` at `:88`, `:126` and `:158`) reads `blockers` and `warnings`
      together. A warning can no longer be in `blockers`, so `:88`'s `CRLF` check would otherwise pass vacuously;
    - the real-tree test expects `blockers == []` and, on exit `2`, `warnings` ids `== {"VALIDATOR_DEPS_MISSING"}`;
    - new: a pass block has `status: pass`, `blocking: false`, `command: null`, `gate: doctor`, the six
      `checks_run` ids, and no `schema_family`, `affected_components` or `affected_processes`;
    - a failing copy has `blocking: true`;
    - no output contains `/dgf-fix`;
    - a copy without `scripts/` → exit `2` and `not-run-validator-runtime`;
    - a copy without `scripts/lib/gate_result.py` → exit `3`, no block, stderr names the file;
    - the output ends with the block's closing fence.
  - Run `python3 skills/dgf-doctor/scripts/doctor.py` on the real tree: exit `0`, or `2` with only
    `VALIDATOR_DEPS_MISSING`.
  - Files: `skills/dgf-doctor/scripts/doctor.py`, `skills/dgf-doctor/SKILL.md`, `tests/test_doctor.py`.

### Phase 3: The Commit Plan check

- [x] **Task 4: Parse the Commit Plan in `lib/plan.py`.**
  - Implement DD5's parser half: `Commit` dataclass, `_COMMIT_LINE`, and `Plan.commit_section` and `Plan.commits`,
    filled in `parse_text()` while the heading is `Commit Plan`. `_body_sections()` already skips fences.
  - Add `commits=len(commits)` to the existing `report.debug("plan.parse", …)` line.
  - `tests/test_plan.py`:
    - an en dash, a hyphen, `after task 5`, spaces around the dash, and a double-quoted message;
    - a wrong-shaped bullet kept with `number=None`, and `parse_text()` not raising on it;
    - a placeholder line ignored;
    - a bullet inside a fence ignored;
    - no section → `commit_section` False;
    - an ultra `index.md`'s section parsed the same way.
  - Files: `scripts/lib/plan.py`, `tests/test_plan.py`.

- [x] **Task 5: Add the `plan-commits` check to `check_plan.py`.** (depends on 4)
  - Add `"PLAN_COMMITS_INVALID": EXIT_BLOCKED` and `"PLAN_COMMITS_MISSING": EXIT_WARNINGS` to `report.CODES`, in the
    plan-file group.
  - Implement DD5's check half as `check_commits()`, called from `check()` after `check_tasks()`. Add
    `plan-commits` to the module docstring's check list and its exit-`2` list.
  - `report.debug("check_plan.commits", "checked", groups=…, tasks=…, covered=…)`.
  - `tests/test_check_plan.py`, with the existing `task()`/`plan_text()` builders:
    - a good plan of five tasks in two groups;
    - a gap, an overlap, a range whose end is not a task, an out-of-order number, a reversed range, a group that
      starts early, and a wrong-shaped line — each exactly `PLAN_COMMITS_INVALID`, at the right line;
    - `after tasks 1–5` over tasks 1, 2, 3 and 5 → no finding;
    - an overlap scan whose other branch holds a malformed Commit Plan still reports `PLAN_OVERLAP`, not
      `PLAN_OVERLAP_UNREADABLE`;
    - five tasks and no section → `PLAN_COMMITS_MISSING` only;
    - four tasks and no section → nothing;
    - an ultra bundle's `index.md`.
  - `tests/test_report.py` `SpineCodes.EXPECTED` (`:45-58`) pins each code's exit: add `PLAN_COMMITS_INVALID` under
    `EXIT_BLOCKED` and `PLAN_COMMITS_MISSING` under `EXIT_WARNINGS`.
  - The known-bad case `tests/fixtures/known-bad/plan-commits-invalid/`: five tasks, groups `1–3` and `5`,
    modelled on `plan-task-invalid/`; `expected.json` → `check_plan.py`, exit `1`, codes `["PLAN_COMMITS_INVALID"]`.
  - Files: `scripts/lib/report.py`, `scripts/check_plan.py`, `tests/test_check_plan.py`, `tests/test_report.py`,
    `tests/fixtures/known-bad/plan-commits-invalid/…`.

- [x] **Task 6: Say in the plan format that a script checks the Commit Plan.** (depends on 5)
  - `skills/dgf-plan/references/PLAN-FORMAT.md` §Commit Plan: the exact line shape (DD5), one example, the
    `after task N` singular form, and that `check_plan.py` reports `PLAN_COMMITS_INVALID` (exit `1`) and
    `PLAN_COMMITS_MISSING` (exit `2`).
  - `skills/dgf-plan/references/ULTRA-FORMAT.md`:
    - `:207-208`: replace "No script checks the Commit Plan yet" with the check, under the list of what
      `check_plan.py` checks.
    - `:80-82`: the template's Commit Plan example names tasks 1–6, but the template has three tasks (`:86-98`).
      Once Task 5 lands, a bundle copied from the template fails with `PLAN_COMMITS_INVALID`. Keep only the
      placeholder line in the template (fewer than five tasks need no Commit Plan), and let `PLAN-FORMAT.md`
      §Commit Plan carry the example.
  - `skills/dgf-plan/SKILL.md` Step 5.1, whose exit-`2` row already names warning codes: add `PLAN_COMMITS_MISSING`.
    Exit `1` is generic ("fix every `ERROR`"), and needs nothing. `test_skill_contracts` checks every quoted code.
    `version: 0.1.2`.
  - `skills/dgf-commit/SKILL.md` Step 3.1: the groups follow the shape `check_plan.py` checks. When a group does not
    parse, the plan is defective: say so and suggest `/dgf-plan`, rather than guessing. `version: 0.1.2`.
  - Walk `PLAN-FORMAT.md`'s worked example, and `ULTRA-FORMAT.md`'s template instantiated as a bundle with its two
    phase files, through `check_plan.py` again (`.ai-factory/RULES.md`, rule 4). Record both exits: `0`, or `2` for
    an overlap only.
  - Files: the four Markdown files above.

### Phase 4: The verify gate

- [x] **Task 7: Give `check_change.py` a `run()` function and an honest `validators` check.**
  - Implement DD6, and keep `main()`'s output byte-identical apart from the `validators` line: diff it before and
    after on the `tests/test_check_change.py` fixtures.
  - `report.debug("check_change.run", "done", changed=…, validated=…, families=…)`.
  - `skills/dgf-implement/references/IMPLEMENTATION-GUIDE.md` (the table at `:50`): add the row
    `NOT RUN: validators (narrowed …)` — the per-task run, which is never the gate. `skills/dgf-implement/SKILL.md`:
    `version: 0.1.2`.
  - `tests/test_check_change.py`:
    - a whole-root run lists `validators` in `CHECKS RUN:`;
    - a `--files` run prints `NOT RUN: validators (narrowed to 1 file(s) …`;
    - `run()` returns `changes`, and `families` holding `xsd` for the process;
    - `run()` with `changed=` returns `changes` and no baseline;
    - `run(skip_validators=True, skip_reason="x")` records `NOT RUN: validators (x)` and `NOT RUN: baseline (x)`;
    - `refuse()` over plain values still refuses `--base -x` and a `..` path with exit `3`.
    Put the tests that run validators in the class that skips through `helpers.have_dependencies()` (`:224`).
  - Files: `scripts/check_change.py`, `tests/test_check_change.py`,
    `skills/dgf-implement/references/IMPLEMENTATION-GUIDE.md`, `skills/dgf-implement/SKILL.md`.

- [x] **Task 8: Promote path-to-artifact mapping into `lib/plan.py`.**
  - Implement DD4's `plan.artifact_inside()` and `plan.artifact()`, and a helper `placeholder_values(pattern,
    parts)`: the last placeholder may take several segments, as in `matches_folder()`. Move
    `PROCESS_LOCAL_WORKFLOW` from `inventory_root.py`.
  - Rewrite `inventory_root._artifact(inside)` on top of `artifact_inside(inside)`, mapping `process-workflow` to
    the `workflows` count.
  - `report.debug("plan.artifact", "matched", path=…, artifact=…, name=…)`.
  - `tests/test_plan.py`: each `legacy-artifacts` row, a JSON component, a nested component path, the site map, a
    process-local workflow, a form whose name holds `/`, and a non-matching config file → `None`.
  - `tests/test_inventory_root.py` must pass unchanged. Also run `python3 scripts/inventory_root.py` over a scratch
    copy of DGF's samples before and after: byte-identical.
  - Files: `scripts/lib/plan.py`, `scripts/inventory_root.py`, `tests/test_plan.py`.

- [x] **Task 9: Add `scripts/verify_gate.py`.** (depends on 2, 5, 7, 8)
  - Implement DD2 and DD4's `footprint()`.
    - Add to `report.CODES`, in a new `# the verify gate (verify_gate.py; ADR 0020)` group:
      `GATE_TASK_UNCHECKED` (1), `GATE_STRICT_WARNING` (1), `GATE_PLAN_UNCONFIRMED` (1), `GATE_CHECK_NOT_RUN` (2).
    - The docstring states the usage, the flow, the required checks, and the exit-code contract, in the house
      style of `check_change.py`. It names no DGF repository path (ADR 0012): cite ADRs and knowledge files.
    - It imports nothing third-party when it loads. `check_plan`, `check_change` and `locate_plan` are
      stdlib-only at import, and `runner` loads lazily. `test_skill_contracts` runs every called script's
      `--help`, and the suite must pass without `lxml`.
    - Add the four codes to `tests/test_report.py` `SpineCodes.EXPECTED`.
  - Traces: `report.debug("verify_gate.discover", …)`, `("verify_gate.required", "not run", check=…, why=…)`,
    `("verify_gate.status", "computed", status=…, blockers=n, warnings=n)`,
    `("verify_gate.footprint", …, components=n, processes=n)` and `("verify_gate.next", "chose", command=…,
    why=…)`.
  - `tests/test_verify_gate.py`, in the style of `tests/test_check_change.py` (`helpers.make_root`,
    `helpers.make_repo`/`commit_all` for `--base`). Every root holds `.dgf-factory/config.yaml`: `verify_gate.py`
    always checks for it, through `locate_plan.explicit_root()` (`scripts/locate_plan.py:98-104`). Each case
    asserts the exit and the parsed last block:
    - `helpers.run_cli_blocking("verify_gate.py", "--help")` → exit `0`: nothing third-party at load;
    - pass → `command: /dgf-commit`, required ⊆ `checks_run`, `schema_family.xsd ≥ 1`,
      `affected_processes == [{"workspace": "app", "name": "Case", "reference": "Case"}]`;
    - an unchecked task → `task-2`, `/dgf-implement`;
    - `PLAN_TASK_INVALID` and `PLAN_COMMITS_INVALID` → `/dgf-plan`;
    - a new `DEAD_TRANSITION` with `--base` → a blocker with `schema_family: "xsd"` and the right line, while a
      `PRE_EXISTING` one is never an entry;
    - `--changed` → `not-run-baseline` in `warnings`, status `warn`;
    - a `kind: code` task → `not-run-frontend-tests`;
    - `--strict` with `CHANGE_UNPLANNED_FILE` → in `blockers`, severity `warning`, status `fail`; without
      `--strict` → in `warnings`, status `warn`;
    - missing dependencies (`helpers.run_cli_blocking`) → exit `3`, `DEPENDENCY_MISSING`, `command: null`, and
      `change-scope` still in `checks_run`;
    - `ROOT_NOT_SET_UP`, `PLAN_NOT_FOUND` (`/dgf-plan`), `PLAN_AMBIGUOUS` (`null`), and `GATE_PLAN_UNCONFIRMED`
      (`--branch` naming no plan);
    - `--base` in a root that is not a git repository → no `affected_*` fields;
    - PRE_EXISTING cut at 20 with the `Shown:` line;
    - exactly one block, and nothing after it;
    - `footprint()` unit cases: component, `BASE:` reference, process-local workflow, `_form.js` → its form, a
      rename → D + A, `configuration`.
    Classes skip through `helpers.have_dependencies()` / `helpers.have_git()`, except the dependency-missing case.
  - Three known-bad cases, all with `--changed` (E10), each root holding `workspaces/.dgf-factory/config.yaml`.
    The existing `change-*` fixtures do not hold one, because `check_change.py` never looks:
    - `gate-task-unchecked/` → exit `1`, `GATE_TASK_UNCHECKED`;
    - `gate-strict-warning/` → `--strict` and an unplanned file, exit `1`, `GATE_STRICT_WARNING`;
    - `gate-plan-unconfirmed/` → `--branch feature/elsewhere`, one active plan, exit `1`, `GATE_PLAN_UNCONFIRMED`.
  - Files: `scripts/verify_gate.py`, `scripts/lib/report.py`, `tests/test_verify_gate.py`, `tests/test_report.py`,
    `tests/fixtures/known-bad/gate-*/…`.

- [x] **Task 10: Make `/dgf-verify` relay the script's gate, and rewrite its contract.** (depends on 9)
  - `skills/dgf-verify/SKILL.md` (`version: 0.2.0`):
    - Step 0.0 as today. On exit `1`, run `verify_gate.py` with no arguments and relay its block.
    - Step 0.2 as today. On exit `1`, `PLAN_NOT_FOUND`: run `verify_gate.py --workspaces-root … --plans-dir …
      --fast-plan …` and relay. On `PLAN_AMBIGUOUS`: ask, then either pass `--plan` or relay that run. On exit `2`:
      ask; if the user confirms, pass `--plan`, otherwise relay the unconfirmed run.
    - A single gate step: `verify_gate.py --workspaces-root … --plan … --base <git.base_branch>`, with `--strict`
      and `--no-overlap` when git is disabled. Capture the exit code before any pipe.
    - Step 4 (base workspace, from `inventory_root.py`) and the Override line are written **before** the relayed
      output.
    - Relay verbatim, and write nothing after the block.
    - DO/DON'T and Critical Rules: "the script computes the status" in place of "the status is arithmetic"; "never
      write or edit a gate block"; drop "Emit fields the contract marks as not yet emitted".
  - `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`, rewritten from ADR 0020:
    - the full block, with every field;
    - status computed from the two lists;
    - DD2's entry table;
    - the required checks, including `plan-routes`, `plan-commits`, `change-planned` and `frontend-tests`;
    - narrowing;
    - absent versus empty;
    - the `suggested_next` order;
    - the exit-3 blocker ids, which become the finding's code — `DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE`,
      `PLAN_UNREADABLE`, `PLAN_FORMAT_UNSUPPORTED` — in place of `<script>-exit-3`;
    - no "Not yet emitted" section;
    - one line saying the builder is `scripts/lib/gate_result.py`.
  - `tests/test_skill_contracts.py`: add `verify_gate.py` to the spine scripts (`:110`). Its flags must appear in
    `verify_gate.py --help`, and every `GATE_*` code the skill quotes must be in `report.CODES`.
  - Walk the skill's Step 0.0–0.2 exit tables against the script, one scratch root per row
    (`.ai-factory/RULES.md`, rule 4).
  - Files: `skills/dgf-verify/SKILL.md`, `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`,
    `tests/test_skill_contracts.py`.

### Phase 5: Proof and documentation

- [x] **Task 11: Walk the gates end to end, and record it.** (depends on 3, 6, 10)
  - Make a scratch copy of DGF's samples (`~/workspaces/dotgov/_DotGovFramework/DotGovFramework/src/samples/workspaces`,
    at the commit in `provenance/knowledge/schemas/MANIFEST.md`), run `git init -b main`, and commit
    `.dgf-factory/config.yaml`. Then, on a branch with a two-task full plan:
    - a pass: all tasks checked → exit `0`;
    - a new `DEAD_TRANSITION` → exit `1`, one blocker with `schema_family: "xsd"`, and `affected_processes` naming
      the process;
    - `--strict` with an unplanned file → exit `1`;
    - a `webasm` process edit → `reference: "BASE:<name>"`.
    Record wall-clock time against the spine's 5.2 s, and check the block's size with 2,552 pre-existing findings.
  - Doctor on the real tree: exit `0`, or `2` with `VALIDATOR_DEPS_MISSING` only.
  - `tools/run_known_good.py <dgf-root>`: byte-identical to before, since the runner is untouched.
  - `tools/check-dual-schema-docs.sh`: at its known dependency-warning baseline.
  - The suite, twice: on the venv, and under the system `python3` without `lxml`.
  - Record commands, exits, timings and surprises under `## Follow-ups found during implementation`. Fix script
    defects here.
  - Files: this plan; fixes in the scripts from Tasks 2–9.

- [x] **Task 12: Document the wired contract, and mark the milestone done.** (depends on 11)
  - `docs/skill-authoring.md` §"Gate blocks" (`:130-160`):
    - the full block;
    - the builder rule, a pointer to `lib/gate_result.py`, and "a missing block is a gate that did not run";
    - absent versus empty;
    - per-gate allowlists;
    - the doctor's block;
    - `NOT RUN: validators (narrowed …)`;
    - a `verify_gate.py` row in the table of each script's own lines (`:103-111`).
  - `docs/pipeline.md`:
    - the `/dgf-verify` row (`:26`) → `verify_gate.py`;
    - the script table (`~:140`), with a `verify_gate.py` row;
    - the exit-code table (`:142-147`): a `verify_gate.py` column, and `PLAN_COMMITS_INVALID` and
      `PLAN_COMMITS_MISSING` in `check_plan.py`'s;
    - "The gate block" (`:191-199`) → the emitted fields and ADR 0020;
    - `plan-commits` wherever `check_plan.py`'s checks are listed.
  - `docs/architecture.md`:
    - `:41`: `verify_gate.py` in the tree;
    - `:60-71`: `gate_result.py` and `verify_gate.py` rows; drop "arrives with milestone 10";
    - `:89`: `verify_gate.py` in the "Runtime validator" row.
  - `docs/getting-started.md`:
    - `:46`: `verify_gate.py` in the scripts list;
    - `:124-135`: a `verify_gate.py` row;
    - `:211` and `:230`: remove it from "not here yet", and add a `verify_gate.py` line to "Trying the spine".
  - `docs/blueprint.md` §"Gate schema": a dated *(2026-09-25)* note after the block — built by `lib/gate_result.py`;
    `warnings` added; `"both"` dropped; see ADR 0020. Do not rewrite the block.
  - `AGENTS.md`:
    - the structure tree gains `verify_gate.py` and `lib/gate_result.py`;
    - the "Not yet created" line (`:104`) loses them;
    - Key Entry Points gains rows for both;
    - the Agent Rules' ADR list gains 0020.
  - `.ai-factory/DESCRIPTION.md`:
    - "Current State": milestone 10 is built; the scripts list gains `verify_gate.py`; known-bad 51 → 55; ADRs
      0001–0020;
    - "Not yet created" loses `gate_result.py`.
  - `.ai-factory/ARCHITECTURE.md`: the tree comment (`:127`), a `verify_gate.py` line, and prose `:149-154`.
  - `README.md`: check lines `:41` and `:56` against the new block, and edit them only if wrong.
  - `.ai-factory/ROADMAP.md`: tick "Gate Contract Wired", and add `| Gate Contract Wired | <date> |` to Completed.
  - Run `tools/check-dual-schema-docs.sh` and the doctor.
  - Files: the ten files above.

## Risks

- **R1 — Consumers of the milestone-9 block see it change** (`not-run-*` moves, new warnings are listed, the doctor
  becomes `doctor`). *Mitigation:* nothing in the marketplace parses these blocks yet, `schema_version` stays `1`
  because every change is additive or re-classifies, and ADR 0020 records the change.
- **R2 — A large block.** Many new warnings, or a wide change, grow `warnings` and `affected_components`.
  *Mitigation:* summaries are capped, and `PRE_EXISTING` is never an entry. Task 11 measures it on DGF's samples.
- **R3 — `verify_gate.py` couples to two scripts' internals.** *Mitigation:* explicit `check_plan.check()` and
  `check_change.run()` functions, their CLI output pinned byte-identical, and `run_known_good.py` untouched.
- **R4 — The in-process `SystemExit` paths.** `deps.require()` and `report.fail()` exit from inside
  `runner.run()`. *Mitigation:* `verify_gate.py` probes `deps.missing()` before it runs a validator, and catches
  `KnowledgeTableError`. A test runs the gate with dependencies blocked.
- **R5 — The footprint is not the blast radius.** A shared workflow change lists the workflow, not the processes
  that call it. *Mitigation:* stated in ADR 0020 §6 and the contract; `/dgf-audit` owns reachability.
- **R6 — `PLAN_COMMITS_MISSING` makes older hand-written plans of five or more tasks warn.** *Mitigation:* a
  warning, never a block, and `/dgf-plan` always writes a Commit Plan.

## Follow-ups

- `/dgf-fix` joins the `verify` and `doctor` allowlists when milestone 11 builds it.
- `/dgf-commit` could read parsed Commit Plan groups from a script instead of parsing prose.
- Blast radius, the processes a changed shared workflow reaches, belongs to `/dgf-audit` (milestone 12).
- Carried from the spine: a test that runs `PLAN-FORMAT.md`'s worked example through `check_plan.py`, so
  `.ai-factory/RULES.md` rule 4 stops being kept by hand; the baseline's ignored-file and symlink difference;
  `Bash(git *)` in four skills (Marketplace Release).

## Follow-ups found during implementation

<!-- Tasks 6, 8, 10 and 11 record their walks, commands, exits, timings and surprises here. -->

### Task 6 — the plan formats walked through `check_plan.py` (2026-09-25)

- A scratch root (`zims/FM/_DATA/Inspection/_forms/Apply/_form.xml`, `webasm/FM/_COMPONENTS/`,
  `.dgf-factory/config.yaml`), with `PLAN-FORMAT.md`'s worked example written verbatim as
  `.dgf-factory/plans/feature-zims-inspection-fee.md`:
  `check_plan.py <plan> --workspaces-root <root>` → **exit 0**, `CHECKS RUN: plan-header, plan-tasks,
  plan-commits, plan-files, plan-routes`. Three tasks, so no Commit Plan is needed.
- `ULTRA-FORMAT.md`'s `index.md` template written verbatim as a bundle, with its two phase files
  (`phase-01-fee-data.md` holding `## Task 1`/`## Task 2`, `phase-02-behaviour.md` holding `## Task 3`):
  → **exit 0**. The template's `<only when …>` placeholder is prose and is not read.
- Surprise, fixed by Task 6: the template's old example (`after tasks 1–3`, `after tasks 4–6`) over its three
  tasks would have been `PLAN_COMMITS_INVALID` twice (Tasks 4 and 6 do not exist).
- Not done: `--overlap` (the scratch root has no git); an overlap would only add `PLAN_OVERLAP`, exit `2`.

### Task 8 — the inventory on `plan.artifact_inside()` (2026-09-25)

- `cp -R <dgf>/src/samples/workspaces <scratch>/samples` (DGF `aa1d5c4c2`), then
  `inventory_root.py --workspaces-root <scratch>/samples` before and after the rewrite: exit `0` both times,
  and `cmp` reports the two outputs **byte-identical** (dgf 1/4/88/2/12/21/1, webasm 11/137/135/338/194/515/40,
  zims 11/198/162/445/223/533/44 for processes/workflows/components/forms/settings/views/options).
- `tests/test_inventory_root.py` passes unchanged.

### Task 10 — `/dgf-verify`'s Step 0.0–0.2 rows walked against `verify_gate.py` (2026-09-25)

One scratch root per row (the `tests/test_verify_gate.py` root, no git), each run as the skill runs it:

| Row | `locate_plan.py` | `verify_gate.py` as the row says | Block |
|---|---|---|---|
| 0.0 exit 1, no config | exit 1 `ROOT_NOT_SET_UP` | no arguments, from the root: exit 1 | `fail`, `ROOT_NOT_SET_UP`, `null` |
| 0.0 exit 1, two roots below | exit 1 `ROOT_AMBIGUOUS` | no arguments, from above them: exit 1 | `fail`, `ROOT_AMBIGUOUS`, `null` |
| 0.2 exit 1, no plan | exit 1 `PLAN_NOT_FOUND` | `--workspaces-root --plans-dir --fast-plan`: exit 1 | `fail`, `PLAN_NOT_FOUND`, `/dgf-plan` |
| 0.2 exit 1, two active plans | exit 1 `PLAN_AMBIGUOUS` | the same: exit 1 | `fail`, `PLAN_AMBIGUOUS`, `null` |
| 0.2 exit 2, fallback not confirmed | exit 2 `PLAN_FALLBACK` | the same: exit 1 | `fail`, `GATE_PLAN_UNCONFIRMED` (+ `PLAN_FALLBACK` warning), `null` |
| 0.2 exit 2, fallback confirmed | exit 2 `PLAN_FALLBACK` | `--plan <it> --base main --no-overlap`: exit 1 | `fail`, `task-2`, `/dgf-implement` |

Surprise, a walk-setup error rather than a defect: a plan whose tasks are all checked is finished, so
`locate_plan.py` never offers it as a fallback (`PLAN_NOT_FOUND`); the confirmed row needs an active plan.

### Task 11 — the gates end to end (2026-09-25)

**The estate.** `cp -R` of DGF's samples at `aa1d5c4c2` (the `dgf_commit` in
`provenance/knowledge/schemas/MANIFEST.md`), `.dgf-factory/config.yaml` added, `git init -b main`, one commit;
then branch `feature/walk` with a two-task full plan (`affects_workspaces: [zims, webasm]`): Task 1 retitles
`zims/FM/_PROCESS/04.Review_Process/process.xml`, Task 2 retitles `webasm/FM/_PROCESS/ExpertReview/process.xml`.
Every run is `verify_gate.py --workspaces-root <estate> --plan <plan> --base main` on the venv (Python 3.9.6,
lxml 6.1.3), with `--overlap` on.

| Scenario | Exit | Wall-clock | Block |
|---|---|---|---|
| A — both tasks checked, both files retitled | `0` | 5.35 s | `pass`, no entries; all ten required checks in `checks_run`; `schema_family` `{"json": 385, "xsd": 2731}`; `affected_processes` `webasm`/`ExpertReview` → `BASE:ExpertReview`, `zims`/`04.Review_Process` → `04.Review_Process`; `/dgf-commit` |
| B — A plus a transition to `SubProcess8_RecordStateGone` | `1` | 5.33 s | `fail`; one blocker, `DEAD_TRANSITION` at `…/04.Review_Process/process.xml:20`, `schema_family: "xsd"`; the knock-on `UNREACHABLE_STATE` in `warnings`; `/dgf-implement` |
| C — A plus `05.Delivery_Process` retitled, no `--strict` | `2` | 5.71 s | `warn`, `CHANGE_UNPLANNED_FILE` in `warnings` |
| C with `--strict` | `1` | 5.56 s | `fail`, `GATE_STRICT_WARNING` → `CHANGE_UNPLANNED_FILE` in `blockers`, severity `warning` |

- **Timing** is the spine's 5.2 s plus 0.1–0.5 s: the gate runs the same two validator passes (3,116 files per
  tree) and adds the plan check with its overlap scan.
- **Size.** With 2,552 pre-existing findings, A's block is **1,148 bytes**: `PRE_EXISTING` is never an entry.
  The whole stdout is 75 KB, the 20 shown `PRE_EXISTING` lines and one `Shown: 20 of 2552 PRE_EXISTING` line
  included.
- **The doctor** on the real tree: exit `0` on the venv; exit `2` under the system `python3`, with
  `VALIDATOR_DEPS_MISSING` its only warning.
- **`tools/run_known_good.py <dgf-root>`**: the tool at `f8444ef` (extracted with `git archive` into the
  scratchpad) and the tool now print **byte-identical** output — `CLEAN`, 71 excused by `EXCEPTION`, 9 by
  `EXPECTED_EXTERNAL`.
- **`tools/check-dual-schema-docs.sh`**: exit `2`, its known baseline — the doctor's `VALIDATOR_DEPS_MISSING` under
  the system `python3`, and nothing else. Section 8: 530 tests, OK.
- **The suite**: 530 tests OK on the venv; 530 OK, 150 skipped, under the system `python3` without `lxml`.

Surprises, none a defect fixed here:

- The 240-character summary cap cuts the doctor's `VALIDATOR_DEPS_MISSING` entry inside the install command.
  The `WARN` line above the block carries it whole, and `/dgf-doctor` relays that line. Follow-up: consider a
  per-entry `fix` field, or a shorter summary with the command left to the prose.
- The report's `Info:` count is of the findings shown, after the cut to 20; the `pre-existing:` count is the
  full one.

### Verification — an independent review of the new scripts (2026-09-25)

Fixed, each with a regression test:

- `verify_gate.py` computed the footprint outside the `KnowledgeTableError` guard. Without the validators'
  dependencies, a malformed `legacy-artifacts` table was a traceback (exit 1, no block). The footprint is now
  computed right after the change check, and a malformed table is a `KNOWLEDGE_TABLE` blocker (exit 3, `null`).
- `doctor.py` caught only `OSError`, `SyntaxError` and `ImportError` while loading its builder. Anything else
  the file raises, or a builder without `build`/`entry`/`not_run`/`render`/`GateContractError`, is now exit 3.
- A `--plan` outside the workspaces root gave entries an absolute or cwd-relative `file`. It is now a usage
  error, exit 3, with no block.
- The Commit Plan regex's unbounded `\d+` could make `int()` raise on Python ≥ 3.11 for a 4,300-digit number —
  in another branch's plan too, during the overlap scan. Its numbers are bounded to nine digits, so such a line
  is `number=None`, never a raise. This departs from DD5's regex, for DD5's own rule.
- Wording: ADR 0020 gains an erratum (a copy without `scripts/` warns only when another copy's doctor checks
  it; its own doctor exits 3). `verify_gate.py`'s docstring, the contract and `/dgf-verify` Step 2 now say
  exit 3 also covers a validator that could not read a file (`FAMILY_UNRESOLVED`, `SCHEMA_UNSELECTABLE`), still
  with a `fail` block.

Two defects that predate this branch were found by the same review, and fixed at the user's request
(2026-09-25), each with a regression test:

- `check_plan._check_sections` read phase files with an unguarded `read_text()`: a phase file that is not
  UTF-8 was a traceback in `check_plan.py`, and so in the gate. It is now `PLAN_ULTRA_BROKEN`. The same review
  class covered the task-line and `(depends on N)` `int()` calls in `plan.py`: a number over nine digits is now
  `PlanFormatError` — `PLAN_UNREADABLE` for the plan under check, `PLAN_OVERLAP_UNREADABLE` for another
  branch's — never a crash and never a silently dropped task.
- A change that deleted a workspace's last file dropped that workspace from `workspace_names()`, so
  `check_change.py` reported `CHANGE_OUTSIDE_WORKSPACE` (a warning) where `CHANGE_UNDECLARED_WORKSPACE` (an
  error) was meant, and the footprint dropped its processes. `check_change.known_workspaces()` now adds each
  workspace a deleted `<ws>/FM/…` path proves existed — no git call, so `--changed` gets it too — and
  `Outcome.known` hands the same set to the gate's footprint. `check_change.py`'s output on the eight Task 7
  scenarios is unchanged.

After both: 539 tests OK on the venv, 539 OK (151 skipped) under the system `python3`; the doctor exit `0`; the
docs check at its baseline; the samples' scenario A still exit `0`.
