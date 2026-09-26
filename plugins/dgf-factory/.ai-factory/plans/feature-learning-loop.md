# Implementation Plan: Learning Loop

Branch: feature/learning-loop
Created: 2026-09-26
Refined: 2026-09-26 — `/aif-improve`:

- `/dgf-fix` decides its scope with `check_change.py --changed … --skip-validators` before any edit (E18);
- `check_patches.py` takes a patch as an ordinary path, like `check_plan.py`'s plan;
- `overrides.py` builds its outside-root markers from pieces, so the doctor's sweep stays quiet (E19);
- a test guards that the whole-root walk never reads `.dgf-factory/` (E20);
- the doctor test edit names its tuple;
- `docs/pipeline.md`'s skills table and config example are completed in Task 10.

Base: `develop` at `a614682`. `config.yaml` names `main` as `git.base_branch`, but `main` is 74 commits behind
`develop` and lacks milestones 6–10, which this plan builds on. The branch is cut from `develop` and merges back into
it, as milestones 9 and 10 did.

## Original Request

- [ ] **Learning Loop** — `/dgf-fix` and `/dgf-evolve`, turning DGF gotchas into patches and skill-context overrides. An override may only tighten a skill — add rules and checks, never relax a STOP, an exit-code row, the gate's status table or a Critical Rule — because anyone who commits to the estate can write one; `/dgf-evolve` writes within that limit. The limit's wording still names "the gate's status table", which ADR 0020 removed — the status is now the contract's computed `status` rule — so restate it in the five skills, the `OVERRIDE_LIMIT` test, `docs/pipeline.md` and `docs/blueprint.md` when this milestone decides the limit. `/dgf-fix` joins the `verify` and `doctor` gate allowlists once it exists ([ADR 0020](../docs/adr/0020-gate-block-contract.md) §8)

## Settings

- **Testing: yes.** A stdlib `unittest` test for every new module, script, finding code and rule, run from the plugin
  root with `python3 -m unittest discover -s tests -t .` (prefer `.venv/bin/python` when it exists). Every new
  blocking code gets a known-bad case under `tests/fixtures/known-bad/`. Tests that need `git` skip through
  `helpers.have_git()`; tests that need `lxml` or `jsonschema` skip through `helpers.have_dependencies()`. A test that
  asserts an exact finding list must pass under an interpreter without either (`.ai-factory/RULES.md`). The two new
  scripts are stdlib-only, and their tests prove it with `helpers.run_cli_blocking()`.
- **Logging: verbose.** No logging framework (`.ai-factory/rules/base.md` §Logging). New code traces through
  `report.debug("<module>.<function>", message, key=value…)`, shown on **stderr** under `--verbose`, `DEBUG=1` or
  `LOG_LEVEL=debug`. Report lines go to stdout, usage errors through `report.fail()`. Skills do not log; they relay
  script output.
- **Docs: yes.** A mandatory documentation checkpoint at completion (Task 10), routed through `/aif-docs`.
- **Decisions** (→ ADR 0021 and ADR 0022, Tasks 1–2). D1–D4 are the user's (Andrian Mamei, 2026-09-26). D5–D18 are the
  planner's, taken from the evidence below; reverse any of them at review.
  - **D1 — `/dgf-fix` works inside the active plan.** A fix is a change, and a change needs a plan's scope: the
    verify gate fails a change with no plan (E3). `/dgf-fix` finds the plan through `locate_plan.py`, checks it with
    `check_plan.py`, and edits only inside the plan's `affects_workspaces`. With no plan it **STOPs** and suggests
    `/dgf-plan fast`. A `--record` mode writes a patch only — no workspace file, no plan — for a gotcha fixed
    elsewhere or found in review. No script's discovery changes; there is no `FIX_PLAN.md`.
  - **D2 — Verify only.** `/dgf-fix` joins the `verify` gate's allowlist. The gate suggests it when every task is
    checked and the change's scope is clean, but a validator finding the branch introduced still blocks — an `ERROR`,
    or a validator warning strict mode promoted. Unchecked tasks and change-check errors stay with `/dgf-implement`.
    The doctor's allowlist stays `null`: a broken plugin install is reinstalled, not fixed in the estate. ADR 0022
    records why this departs from the roadmap's "verify and doctor" (DD8).
  - **D3 — A script checks every override, on both sides.** `scripts/check_override.py` decides what a script can
    decide: the override's shape, a patch behind every rule, and no forbidden construct. Every skill that reads an
    override runs it first, and an override it refuses is **not read or applied**. `/dgf-evolve` runs it on every
    file it writes. The limit sentence stays for what needs judgement (DD3–DD5).
  - **D4 — The limit's wording.** "the gate's status table" becomes "the status a gate script computes", in the six
    readers, the `OVERRIDE_LIMIT` test, `docs/pipeline.md`, `docs/blueprint.md` and `docs/skill-authoring.md` (DD5).
  - **D5 — The patch.** `<paths.patches>/<YYYY-MM-DD-HH.mm>-<slug>.md`. The timestamp sorts patches as AI Factory's do
    (E8). The slug stops two fixes made in the same minute, on two branches of one shared ledger, from colliding on
    merge (E14). Its field bullets and five sections have fixed English names so scripts can read them, and its prose
    is written in `language.artifacts`. A patch is append-only: `/dgf-fix` creates one and never edits or deletes
    another (DD1).
  - **D6 — `scripts/check_patches.py`** checks one or every patch, and with `--cursor` says which are new. It never
    writes (DD2).
  - **D7 — The override.** `<paths.skill_context>/<skill>/SKILL.md`, in a fixed template: a title naming the skill, and
    under `## Rules` one `### <name>` per rule, carrying exactly a `source:` and a `rule:` bullet. Every source is a
    patch that exists. A rule without a patch behind it is recorded first, with `/dgf-fix --record`. Written in
    English, as AI Factory's are (E8) (DD3).
  - **D8 — `check_override.py` knows no skill list.** It takes `--skill` and checks the file for that skill. Which
    skills read an override is held by the contract test, because a shared script never knows its callers
    (`.ai-factory/ARCHITECTURE.md` §Dependency Rules). It needs only an existing root directory, not a set-up one,
    because `/dgf` reads its override before `config.yaml` exists (E17) (DD4).
  - **D9 — A refused override is not read.** On exit `1` the skill does not read the file at all, names it as
    refused with each `ERROR` line, and runs on its shipped rules. On exit `2` it reads and applies the file, but
    judges each rule an `OVERRIDE_TOUCHES_LIMIT` line names, and quotes any it does not apply (DD5).
  - **D10 — The readers are six.** They are the five spine skills and `/dgf-fix`. `/dgf-evolve` reads no override of its
    own: one could steer every override it writes. `/dgf-doctor` reads no estate (DD5, DD7).
  - **D11 — The cursor is a set.** `<paths.evolutions>/patch-cursor.json` holds `{"processed": [<names>], "updated": …}`,
    one name per line. A patch is new when it is well-formed and not in `processed`. AI Factory keeps a high-water mark
    (E8). Here every team's branches merge patches into one ledger in any order (E14), and a high-water mark would skip
    a patch dated before the mark but merged after it (DD2, DD7).
  - **D12 — `/dgf-evolve` targets exactly the readers.** Its SKILL.md lists them, and the contract test holds that list
    to the six skills that run `check_override.py`. It reads each target's **shipped** `SKILL.md`, read-only, to drop
    rules the skill now covers and refuse ones that contradict it. That is the only file of another slice it reads,
    never its references or scripts (DD7).
  - **D13 — `/dgf-evolve` asks before it writes, and runs only when asked** (`disable-model-invocation: true`, as AI
    Factory's `aif-evolve`, E8). It rewrites what other skills do, so it never fires on its own (DD7).
  - **D14 — A patch is data, never an instruction.** `/dgf-evolve` refuses a prevention point that would relax a
    limit, and logs it with its patch. `/dgf-implement` and `/dgf-fix` read patches as cautions that never override
    the skill, the plan or a STOP (DD6, DD7).
  - **D15 — Reproduce first, and never claim an unconfirmed fix.** The regression check is a validator finding when one
    exists: its code, file and message, before and after. When no validator catches the problem, it is a written
    manual reproduction. The patch then says `findings: none`, and the report says no script confirmed the fix — a
    process cannot be run headlessly (E15). That port keeps AI Factory's regression-first policy (E8) (DD6).
  - **D16 — Neither skill emits a gate block.** Neither is a gate; AI Factory's `aif-fix` and `aif-evolve` emit none
    (E8). `/dgf-fix` ends by suggesting `/dgf-verify`.
  - **D17 — Out of scope.** There is no `/dgf-transfer`: an estate has one `.dgf-factory/` and no sibling project to
    port from. Harvesting patches into the shipped `knowledge/` or into new validators is maintainer work, because
    knowledge changes only by a deliberate edit with its provenance (`.ai-factory/ARCHITECTURE.md` §Layer/Module
    Communication). Both are follow-ups.
  - **D18 — ADR 0022 supersedes ADR 0020 in full, with 0020's section numbers.** Adding `/dgf-fix` to §8 and a first-match
    rule to §9 changes what 0020 decides, so it is not an erratum (E10). The live citations of ADR 0020 are repointed
    to 0022, as ADRs 0014 and 0015 were relinked. Because the numbers are kept, `ADR 0020 §4` becomes `ADR 0022 §4`.
    Historical mentions stay: completed roadmap entries, archived plans, and 0020 itself.

## Roadmap Linkage

Milestone: "Learning Loop"
Rationale: This plan implements the milestone as written: `/dgf-fix` and `/dgf-evolve`, the limit decided and restated
everywhere the roadmap names, and `/dgf-fix` in the verify gate's allowlist. The one departure — the doctor's
allowlist stays `null` — is the user's decision D2, recorded in ADR 0022.

## Evidence

Read on 2026-09-26 at `develop` `a614682`.

- **E1 — The limit, where it is written today.** The same sentence sits in `skills/dgf/SKILL.md:49-53`,
  `skills/dgf-plan/SKILL.md:38-42`, `skills/dgf-implement/SKILL.md:65-70`, `skills/dgf-verify/SKILL.md:42-47` and
  `skills/dgf-commit/SKILL.md:29-35`. `tests/test_skill_contracts.py:115-118` pins it as `OVERRIDE_LIMIT`, and
  `:124-133` requires it in every skill whose text holds `skill-context/`, which must be exactly those five.
  It is paraphrased at `docs/pipeline.md:48`, `docs/blueprint.md:291` and `docs/skill-authoring.md:224`. Its origin
  is the spine's security plan: finding M2 (`.ai-factory/PLAN.md:26`), decision D6 (`:50-53`) and Task 5
  (`:132-146`). Every copy says "the gate's status table", which ADR 0020 §9 retired (`docs/adr/0020-gate-block-contract.md:196-199`).
- **E2 — The allowlists.** ADR 0020 §8 (`docs/adr/0020-gate-block-contract.md:185-192`): `verify` allows
  `/dgf-plan`, `/dgf-implement`, `/dgf-commit`, `null`; `doctor` allows `null`; "`/dgf-fix` joins an allowlist when
  milestone 11 builds it". §Follow-ups (`:256`) names both allowlists. `scripts/lib/gate_result.py:33` holds `GATES`.
  `scripts/verify_gate.py:380-401` (`suggest()`) never returns `/dgf-fix`; its last line returns `null`, "a finding no
  command fixes". `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md:118-127` is the table. Tests use `/dgf-fix` as
  the example of a refused command (`tests/test_gate_result.py:68-72`, `:200-210`). The doctor's output must never
  hold it (`tests/test_doctor.py:72`, `:81`). A new dead transition expects `/dgf-implement` (`tests/test_verify_gate.py:330-339`).
- **E3 — Nothing fixes a gate finding once every task is checked.** The gate sends a new blocking finding to
  `/dgf-implement` (`scripts/verify_gate.py:391-396`). But `/dgf-implement` touches no file its task does not list
  (`skills/dgf-implement/SKILL.md:142-143`), fixes only new errors in the current task's files (`:189-192`), and on
  completion only suggests `/dgf-verify` (`:216-219`). A change with no plan cannot pass the gate:
  `PLAN_NOT_FOUND` → `/dgf-plan` (`scripts/verify_gate.py:387-388`; `skills/dgf-verify/SKILL.md:65`).
- **E4 — The gate can tell a validator finding from a scope finding.** `check_change.run()` puts the change checks in
  `outcome.reports[0]` (`scripts/check_change.py:390-396`) and appends the merged validator report after it
  (`:370-374`). Strict mode records each promotion as `(GATE_STRICT_WARNING finding, the WARN finding it promotes)`
  (`scripts/verify_gate.py:244-251`).
- **E5 — The pipeline's own files are never part of a change.** `PIPELINE_DIR = ".dgf-factory"`, "every check ignores
  them" (`scripts/lib/plan.py:47`, `:436-437`). `check_change.py` ignores them (`:6`, `:152`). A patch or an override
  committed on a branch therefore never trips the change gate.
- **E6 — The paths are already reserved.** `skills/dgf/references/config-template.yaml:9-14` has `patches` and
  `skill_context`; there is no `evolutions` key. `docs/pipeline.md:48-49` names the owners "a person, for now" and
  "milestone 11 (`/dgf-fix`)". `docs/architecture.md:167` gives `patches/` to `/dgf-fix`, "consumed by `/dgf-evolve`".
  The spine kept the read side "so milestone 11 needs no spine edit"
  (`.ai-factory/archive/plans/feature-pipeline-spine.md:186-187`, `:213-214`).
- **E7 — `/dgf-implement` already reads patches.** It reads "the last 10 files in `<root>/<paths.patches>` by name",
  taking their Root Cause and Prevention sections (`skills/dgf-implement/SKILL.md:71-72`, `:246-247`). The name must
  sort by time, and the section names are fixed.
- **E8 — AI Factory's loop** (`.claude/skills/aif-fix/SKILL.md`, `.claude/skills/aif-evolve/SKILL.md`):
  - regression-first (`aif-fix:15-33`);
  - a patch after every fix, named `YYYY-MM-DD-HH.mm.md`, holding a title, `Date`, `Files`, `Severity`, then
    Problem, Root Cause, Solution, Prevention and Tags (`aif-fix:544-642`, name `:556-557`, template `:563-602`);
  - a plan-first mode writing `FIX_PLAN.md` (`aif-fix:209-298`);
  - a cursor, `patch-cursor.json`, that is a high-water mark `last_processed_patch` with a tail-5 overlap guard
    (`aif-evolve:130-171`);
  - a skill-context template of `### <rule>`, `**Source**`, `**Rule**`, always in English (`aif-evolve:494-510`), and
    an evolution log (`:541-562`);
  - the user asked before anything is applied (`aif-evolve:394-463`);
  - `disable-model-invocation: true` and `Bash(git *)` only (`aif-evolve:1-7`);
  - neither skill emits a gate block.
  - In AI Factory "the skill-context rule wins" on conflict (`.claude/skills/aif-plan/SKILL.md:150-164`), and
    `aif-transfer` alone limits what an override may weaken.
- **E9 — No ADR decides the loop.** ADR 0001 names it in one bullet (`docs/adr/0001-independent-plugin-with-ai-factory-derived-architecture.md:65`).
  The design is in prose only: `docs/blueprint.md:163-181` (AI Factory's, where an override wins outright), `:290-291`,
  `:318-320`, and build order `:359` ("ship these early even if crude"). `README.md:45` and `:72-73` promise it.
- **E10 — Supersession is always full.** A decision is reversed by a successor that restates every valid section,
  and the old ADR changes only `status` and `date` (`docs/adr/README.md:62-71`). An erratum may not change the
  decision, and corrections to a superseded ADR go in its successor's Context (`:73-90`).
  `tools/check-dual-schema-docs.sh` section 5b checks the chain (`:425-500`). When 0006 and 0007 were superseded,
  live citations were relinked (`.ai-factory/archive/plans/feature-deterministic-validators.md:346`, `:375-376`, `:399`).
  22 files cite ADR 0020 today.
- **E11 — What the contract tests hold.**
  - Every backticked code a skill quotes must be in `report.CODES`, the doctor's ids, or `NOT_CODES`
    (`tests/test_skill_contracts.py:60-69`).
  - Every script a skill calls must exist, and every flag it passes must be in that script's `--help` (`:94-106`).
  - The spine scripts are named (`:108-112`), and `READ_ONLY` skills pre-approve no git (`:139`, `:176-182`).
  - Every `python3 "${CLAUDE_PLUGIN_ROOT}/…"` call must match one of the skill's own `Bash(…)` rules (`:164-174`).
  - The doctor checks each slice's frontmatter (`skills/dgf-doctor/scripts/doctor.py:389-432`), and lists its build
    progress from `EXPECTED_SLICES` (`:124-125`), where neither new skill appears.
- **E12 — The known-bad corpus.** 55 cases. Each runs from its directory, exits `1` or `3`, reports every code it
  expects and no other error (`tests/test_known_bad.py:1-8`, `:52-68`). The corpus scan reads every fixture as UTF-8
  (`:46-50`), so a fixture holding invalid UTF-8 would crash it. `tests/test_report.py:40-70` pins each spine code's
  exit.
- **E13 — Script conventions.** Codes and their exits live in `scripts/lib/report.py` `CODES`. A report is rendered by
  `report.render(lines=…)`, fails through `report.fail()`, and traces through `report.debug()`. `lib/cli.py:14-20`
  exits `3` on a bad argument. `scripts/locate_plan.py` is the model for a stdlib discovery script.
  `lib/plan.path_problem()` (`scripts/lib/plan.py:400`) and `split_paths()` (`:377`) already validate root-relative
  paths.
- **E14 — One ledger, many teams.** `.dgf-factory/` lives "once, at the workspaces root" (`docs/adr/0004-authoring-entry-point.md:90`),
  and "two teams touching two applications share" it (`:135-136`). ADR 0009 keeps it at root scope.
- **E15 — A process cannot be executed headlessly** (`.ai-factory/DESCRIPTION.md:112`;
  `docs/adr/0014-process-verification-runtime-resolution.md:292-294`, §5).
- **E16 — Every reader already pre-approves the plugin's scripts.** The `allowed-tools` of `dgf`, `dgf-plan`,
  `dgf-implement`, `dgf-verify` and `dgf-commit` each hold `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*)`, so a
  `check_override.py` call needs no new permission.
- **E17 — `/dgf` reads its override before a config exists.** On a first run the root has no `.dgf-factory/config.yaml`
  (`skills/dgf/SKILL.md:39-44`), yet Step 0.1 reads the override (`:47-53`).
- **E18 — A change set can be checked before it exists.** `check_change.py --changed` takes `A:`, `M:` and `D:` paths
  and classifies them by status alone. `parse_changed()` never checks that a file exists
  (`scripts/check_change.py:91-99`), and `refuse()` only rejects a path that leaves the root (`:102-113`). With
  `--skip-validators` it runs only the scope, means and planned checks, and needs neither `lxml` nor `jsonschema`
  (`skills/dgf-commit/SKILL.md:103-104`). Checked tasks whose files are not in the set warn
  `CHANGE_TASK_FILE_UNCHANGED` (`:236-242`).
- **E19 — The doctor warns on a home-directory marker in any shipped line.** `ABSOLUTE_PATH_MARKERS` is built from
  pieces, `_SEP + "Users" + _SEP` (`skills/dgf-doctor/scripts/doctor.py:83`), so the doctor's own text does not match.
  The sweep over every shipped file warns `ABSOLUTE_PATH` on a line holding one (`:457-459`).
- **E20 — The whole-root walk skips `.dgf-factory/` only because it is a dot-directory.** `runner.targets()` collects
  configuration with `cli.collect([root])` (`scripts/lib/runner.py:42`), which drops every dot-directory
  (`scripts/lib/cli.py:62`). A `.json` outside every `FM/` is otherwise validated as a draft component (`:31-43`),
  which is what `patch-cursor.json` is.

## Design

### DD1 — The patch, and `scripts/lib/patches.py`

A patch is `<paths.patches>/<YYYY-MM-DD-HH.mm>-<slug>.md`, for example
`.dgf-factory/patches/2026-09-26-14.30-review-moves-to-undeclared-state.md`:

```markdown
# `Review` moves to a state the process never declares

- date: 2026-09-26 14:30
- plan: .dgf-factory/plans/feature-zims-fee.md
- workspaces: zims
- files: zims/FM/_PROCESS/Apply/process.xml
- findings: DEAD_TRANSITION
- dgf_version: 1.1.15
- severity: high

## Problem
The gate blocked the branch: `Review` moved to `Archive`, which is neither a declared state nor `End`.

## Root Cause
The state was renamed `Archived` in the process, but the transition kept the old name. The runtime resolves a
transition's `state` by exact name, so the case would stop at `Review`.

## Solution
The transition now names `Archived`.

## Prevention
A task that renames a state lists every file with a transition to it; `validate_process.py` over the process
folder shows a dead transition before the gate does.

## Tags
#process #transition #rename
```

```python
NAME = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(\d{2})\.(\d{2})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md\Z")   # slug ≤ 50
FIELDS = ("date", "plan", "workspaces", "files", "findings", "dgf_version", "severity")
SECTIONS = ("Problem", "Root Cause", "Solution", "Prevention", "Tags")
SEVERITIES = ("low", "medium", "high", "critical")
NONE = "none"
TITLE_MAX = 120

@dataclass
class Patch:
    name: str; title: str; fields: dict; sections: dict   # section name -> text

def parse(path, rel, rep) -> Patch | None        # every problem is a finding in `rep`; None when unreadable
def read_cursor(path) -> (set | None, str | None)  # (processed names, problem); a missing file is (set(), None)
```

Rules — each an error unless marked:

- The name matches `NAME`, and its slug is at most 50 characters → else `PATCH_NAME_INVALID`.
- The file is UTF-8 → else `PATCH_UNREADABLE`, and nothing more is checked.
- The first non-blank line is `# <title>`, with a title of 1–120 characters → else `PATCH_FIELD_MISSING` (`title`).
- The field bullets `- <key>: <value>` follow the title, each key once, in any order. A missing key is
  `PATCH_FIELD_MISSING`; an unknown or repeated key is `PATCH_FIELD_INVALID`. Values:
  - `date`: `YYYY-MM-DD HH:mm`, a real date, equal to the name's timestamp;
  - `plan`: `none`, or a path under `.dgf-factory/` that `plan.path_problem()` accepts (it need not still exist:
    plans are archived);
  - `workspaces`: `none`, or comma-separated names, each one plain segment, never `applibs*`, never `.dgf-factory`;
  - `files`: `none`, or comma-separated paths `plan.path_problem()` accepts, each in a listed workspace. `files` is
    `none` whenever `workspaces` is;
  - `findings`: `none`, or comma-separated codes in `report.CODES`;
  - `dgf_version`: `unknown` or `\d+\.\d+\.\d+`;
  - `severity`: one of `SEVERITIES`.
  - Any other value is `PATCH_FIELD_INVALID`, naming the key.
- The `## ` sections are exactly `SECTIONS`, in order, each with non-blank text. `## ` inside a fence is not a
  heading. A missing, empty, repeated, out-of-order or unknown section is `PATCH_SECTION_INVALID`.
- Every word of `## Tags` matches `#[a-z0-9][a-z0-9-]*` → else `PATCH_SECTION_INVALID`.
- `read_cursor`: a missing file is nothing processed. Anything but a JSON object whose `processed` is a list of
  strings (with `updated` a string) is a problem, which `check_patches.py` reports as `PATCH_CURSOR_UNREADABLE`
  (warning).

Traces: `report.debug("patches.parse", "parsed", name=…, fields=n, sections=n, findings=n)`, and
`report.debug("patches.read_cursor", "read", processed=n)` or `"unreadable", why=…`.

### DD2 — `scripts/check_patches.py`

```
check_patches.py --workspaces-root R [--patches-dir D] [--cursor C] [PATCH ...] [--verbose]
```

- `R` must be an existing directory → else exit `3`. It need not hold a config (D8).
- `D` defaults to `.dgf-factory/patches/` and `C` has no default; both are relative to `R`.
- Each `PATCH` is an ordinary path — absolute, or relative to the working directory, like `check_plan.py`'s plan
  argument. It must resolve to a file directly in `R/D` → else exit `3`. `--patches-dir` and `--cursor` stay relative to
  `R`, like `locate_plan.py --plans-dir`. With no `PATCH`, every `*.md` directly in `R/D` is checked, sorted by name.
  A missing `R/D` is zero patches, exit `0`. A known-bad case therefore passes
  `workspaces/.dgf-factory/patches/<name>.md` from its directory.
- With `--cursor`, each well-formed patch is `new` or `processed`. A malformed one is `malformed` and never `new`. A
  name in `processed` that the directory no longer holds is traced, never reported.
- It never writes: not a patch, not the cursor.

```
Patch check
PATCHES: .dgf-factory/patches/ total=3 new=1 processed=1 malformed=1
PATCH: 2026-09-26-14.30-review-moves-to-undeclared-state.md state=new severity=high findings=DEAD_TRANSITION title="`Review` moves to a state the process never declares"
CHECKS RUN: patch-name, patch-fields, patch-sections, patch-cursor
ERROR PATCH_SECTION_INVALID .dgf-factory/patches/2026-09-25-09.00-x.md:14 `## Prevention` is empty
…summary, verdict
```

`state=` appears only with `--cursor`, and `patch-cursor` only runs with it. Every line goes through `report.one_line()`,
because a title is text anyone who commits can write. Exit: `0` every patch well-formed; `1` a malformed patch; `2`
`PATCH_CURSOR_UNREADABLE`; `3` usage. Stdlib only. Traces: `report.debug("check_patches.main", "checked", total=…,
new=…, malformed=…)`.

### DD3 — The override, and `scripts/lib/overrides.py`

`<paths.skill_context>/<skill>/SKILL.md`:

```markdown
# Project Rules for /dgf-plan

> Written by /dgf-evolve from the estate's patches. Each rule may only tighten /dgf-plan (ADR 0021).
> Updated: 2026-09-26 15:00

## Rules

### A task that renames a state lists every transition to it
- source: 2026-09-26-14.30-review-moves-to-undeclared-state.md
- rule: When a task renames a process state, list in the same task every process and workflow file whose
  transition or `CHANGE_STATE` step names the old state.
```

```python
TITLE = "# Project Rules for /{skill}"
MAX_RULES, MAX_RULE_CHARS, MAX_NAME_CHARS, MAX_BYTES = 40, 600, 100, 32768
ALLOWED_FLAGS = ("--strict", "--verbose")
# Built from pieces, as doctor.py's ABSOLUTE_PATH_MARKERS are (E19): a literal home-directory marker in this shipped
# file would make every doctor run warn ABSOLUTE_PATH.
_SEP = "/"
OUTSIDE_ROOT = "|".join(re.escape(m) for m in (".." + _SEP, "..\\", "~" + _SEP, _SEP + "Users" + _SEP,
                                               _SEP + "home" + _SEP))
FORBIDDEN = (   # (id, compiled pattern, why) — each pinned by a test
    ("gate-block", r"dgf-gate-result", "a rule never writes, edits or adds a gate block"),
    ("flag", r"(?<![\w-])--(?!(?:strict|verbose)(?![\w-]))[a-z][a-z-]*", "a flag other than --strict or --verbose narrows or skips a check"),
    ("tool-grant", r"allowed-tools|Bash\(|disable-model-invocation", "a rule never grants a tool"),
    ("install", r"\b(?:pip3? install|python3? -m pip|uv (?:pip|add)|npm (?:install|i)\b|brew install|apt-get|curl |wget )", "a rule never installs or downloads anything"),
    ("git-write", r"\bgit (?:push|reset|clean|checkout|switch|rebase|rm|restore|stash)\b", "a rule never rewrites history or discards work"),
    ("outside-root", OUTSIDE_ROOT, "a rule never names a path outside the workspaces root"),
)
LIMIT_WORDS = ("stop", "exit", "status", "block", "blocking", "blocker", "warn", "warning", "critical rule",
               "artifact ownership", "not run", "pre_existing", "skip", "ignore", "optional", "unless", "instead",
               "allow", "permit", "relax", "bypass", "waive")

@dataclass
class Rule:
    name: str; sources: list; text: str; line: int

def parse(path, rel, skill, rep) -> list | None    # the rules, or None; OVERRIDE_UNREADABLE / OVERRIDE_SHAPE in rep
def check_sources(rules, patches_dir, rel, rep)    # OVERRIDE_SOURCE_MISSING
def check_rules(rules, rel, rep)                   # OVERRIDE_FORBIDDEN (error), OVERRIDE_TOUCHES_LIMIT (warning)
```

Shape — each an `OVERRIDE_SHAPE` error, at its line:

- The file is at most `MAX_BYTES` and UTF-8 (else `OVERRIDE_UNREADABLE`, and nothing more is checked).
- The first non-blank line is exactly `TITLE` for the directory's skill.
- Only blank lines and `> ` lines come before one `## Rules`. There is no other `#`, `##` or `####` heading, and no text
  outside a rule.
- Each rule is `### <name>` (1–100 characters, unique), then one `- source: …` bullet and one `- rule: …` bullet. The
  rule's text may continue on lines indented by two or more spaces. Nothing else is inside a rule.
- There are 1–40 rules, each rule's text at most 600 characters. No fence (a line starting ```` ``` ```` or `~~~`)
  and no HTML comment (`<!--`) appear anywhere: either could hide text from a reviewer, or carry a block.

Sources: each `source:` is a comma-separated list of one or more patch names, each matching `patches.NAME` and present
in the patches directory → else `OVERRIDE_SOURCE_MISSING`, naming the patch.

Forbidden: a rule's name or text matching a `FORBIDDEN` pattern is `OVERRIDE_FORBIDDEN`, naming the construct and why.
A rule naming a word in `LIMIT_WORDS` (case-insensitive, word-bounded) is `OVERRIDE_TOUCHES_LIMIT`: one warning per
rule, listing the words. The script cannot tell a tightening rule that names `STOP` from one that relaxes it; the
reading skill decides.

Traces: `report.debug("overrides.parse", "parsed", skill=…, rules=n)`, and `report.debug("overrides.check_rules",
"forbidden", rule=…, construct=…)` for each refusal.

### DD4 — `scripts/check_override.py`

```
check_override.py --workspaces-root R --skill S [--skill-context-dir D] [--patches-dir P] [--verbose]
```

- `R` must be an existing directory → else exit `3` (D8).
- `S` must match `[a-z0-9]+(?:-[a-z0-9]+)*` → else exit `3`, so a skill name cannot hold a path.
- `D` defaults to `.dgf-factory/skill-context/` and `P` to `.dgf-factory/patches/`, both relative to `R`.
- The override is `R/D/S/SKILL.md`. When it is absent the script prints `OVERRIDE: none`, `CLEAN` and exits `0`.

```
Override check
OVERRIDE: .dgf-factory/skill-context/dgf-plan/SKILL.md skill=dgf-plan rules=1
RULE: 1 line=7 sources=1 name="A task that renames a state lists every transition to it"
CHECKS RUN: override-shape, override-sources, override-forbidden, override-limit
…findings, summary, verdict
```

Shape runs first. When the shape fails, the other three checks are `NOT RUN` with the reason "the override did not
parse". Exit: `0` apply; `1` refused — do not read or apply it; `2` apply, and judge each flagged rule; `3` usage.
It never writes, and it reads nothing but the override and the patches directory's names. Stdlib only.
Traces: `report.debug("check_override.main", "checked", skill=…, found=…, rules=n, exit=…)`.

### DD5 — The shared read step, in each of the six readers

Each reader's "Read `…/skill-context/<skill>/SKILL.md` if it exists. An override may …" becomes, word for word except
the skill name:

````markdown
Check this skill's override before reading it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill <skill> --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
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
````

`/dgf` has no config on a first run. It then passes `.dgf-factory/skill-context/` and `.dgf-factory/patches/`, the
template's values. Each reader's report line keeps "Override: <file, or none>; refused: <each rule not applied, or
none>". A refused override is named there as `refused (<codes>)`.

### DD6 — `/dgf-fix`

```yaml
name: dgf-fix
description: Fix a problem in a DGF estate inside the active plan's scope — reproduce it with the validators, make the smallest configuration fix, confirm it with the same check, and record a patch that teaches the next run; or record a gotcha as a patch without changing anything. Use for "fix this", "dgf fix", "the gate found a new error", "fix the dead transition", "record this gotcha", "write a patch".
argument-hint: "[--record] [<symptom, finding code or file>]"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__search_docs mcp__plugin_dgf-factory_dgf-mcp__get_component_doc mcp__plugin_dgf-factory_dgf-mcp__get_json_schema_details mcp__plugin_dgf-factory_dgf-mcp__get_xml_property_reference
disable-model-invocation: false
version: 0.1.0
```

No git rule: every git read it needs is made by `check_change.py`, and it deletes nothing.

- **Step 0: Context.** Run `locate_plan.py --root-only` (exit `1` → **STOP**, run `/dgf`). Read the config, then check
  and read the override (DD5, `--skill dgf-fix`). Read the last 10 patches by name — their Root Cause and Prevention —
  as cautions. A patch informs; it never overrides this skill, the plan or a STOP (D14).
- **Step 0.1: Mode.** `--record` → Steps 1, 6 and 7 only, which change no workspace file and need no plan. Otherwise
  fix mode.
- **Step 0.2: The plan** (fix mode). Run `locate_plan.py` with the config's paths:
  - `0` → the plan;
  - `1` `PLAN_NOT_FOUND` → **STOP**: "a fix is a change, and a change needs a plan's scope — run
    `/dgf-plan fast "<the problem>"`, or `/dgf-fix --record` to record it without a change";
  - `PLAN_AMBIGUOUS` → ask, or **STOP**;
  - `2` `PLAN_FALLBACK` → ask before using it.

  Then run `check_plan.py "<plan>" --workspaces-root "<root>"`: `1` → **STOP**, because `/dgf-plan` repairs a plan;
  `2` → surface the warnings; `3` → **STOP**. Keep its `AFFECTS:` and `TASK:` lines.
- **Step 1: The problem.**
  - With git, and no argument, a finding code or a file: run the whole-root change check,
    `check_change.py --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>"`, with no `--files`, and take
    its new `ERROR` lines. A `CHANGE_*` error means the change left the plan: **STOP** — `/dgf-plan` widens it, or
    the file is reverted by hand.
  - Without git, run `check_change.py … --changed M:<file> --files <file>` for each file the problem names.
  - A symptom is investigated from the files, `${CLAUDE_PLUGIN_ROOT}/knowledge/` and the DGF docs MCP.
- **Step 2: Reproduce** (D15). Record the check, and the exact `ERROR` line it prints, before any edit. If no validator
  reports the problem, write down a manual reproduction and say that no script will confirm the fix. `--record` skips
  this step.
- **Step 3: Scope — decided by the script, before any edit** (E18). Name every file the fix will touch — `M:` for one it
  edits, `A:` for one it creates; a deletion is never a fix (**STOP**: re-plan) — and run:

  ```bash
  python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --changed M:<file> A:<file> --skip-validators
  ```

  | Exit | Action |
  |---|---|
  | `0` | Continue to Step 4. |
  | `1` | A `CHANGE_*` error — an undeclared workspace, an out-of-scope file, an unplanned or new code file. **STOP** before writing anything: `/dgf-plan` widens the plan. |
  | `2` | `CHANGE_UNPLANNED_FILE` → name each file, because the gate will warn on it. Under strict mode (`workflow.verify_mode: strict`) the gate would block on it: **STOP**, and have `/dgf-plan` add it. `CHANGE_TASK_FILE_UNCHANGED` is expected here, since the set holds only the fix's files — ignore it. |
  | `3` | **STOP** and relay it. |

  Then take each file's family: an existing file keeps its own (`validate_config.py`'s `FAMILY:` line), and a new
  configuration file follows `route_means.py`.
- **Step 4: Fix.** Make the smallest change that removes the root cause. Take every fact from the shipped knowledge and
  the DGF docs MCP, never from memory. Never fix a `PRE_EXISTING` finding unasked.
- **Step 5: Confirm.** Re-run the Step 2 check: the finding is gone. Then run
  `check_change.py … --files <the files touched>`:
  - `0` → continue;
  - `1` → a new `ERROR` in a touched file: fix it again, at most 3 attempts, then **STOP**. A `CHANGE_*` error
    means the files touched differ from the files Step 3 checked: restore each touched file to what Step 3 read, and
    **STOP**;
  - `2` → surface every `WARN`;
  - `3` → **STOP** and relay it (a missing dependency's install command verbatim).

  A manual reproduction is confirmed by no script: say so.
- **Step 6: The patch.** Write `<paths.patches>/<YYYY-MM-DD-HH.mm>-<slug>.md` as
  `${CLAUDE_PLUGIN_ROOT}/skills/dgf-fix/references/PATCH-FORMAT.md` specifies. Its prose is in `language.artifacts`,
  its keys and headings in English. `dgf_version` comes from the config, `findings` from the codes Step 2 reproduced
  (`none` for a manual reproduction or `--record`), and `plan` is the plan's path, or `none`. Then run
  `check_patches.py --workspaces-root "<root>" --patches-dir "<paths.patches>" "<patch>"`: `1` → fix the patch, at
  most 3 attempts, then **STOP**; `3` → **STOP**. Never edit or delete another patch.
- **Step 7: Next.** Report:
  - the problem, the root cause, the files touched and the unplanned ones;
  - the check before and after — or "no script confirmed this";
  - the patch's path;
  - for `findings: none`, that no validator catches this problem, which makes it a candidate for a new one.

  Suggest `/dgf-verify`, the whole-root gate, then `/dgf-commit` with the fix and its patch together. After several
  patches, suggest `/dgf-evolve`.
- **Execution Rules**, **Artifact Ownership** — owns the patch files it creates (append-only); writes workspace files
  only inside the plan's scope; reads the plan, config, override, patches, `knowledge/` and the MCP; never edits the
  plan — and **Critical Rules**:
  1. Reproduce first.
  2. Only inside the plan's scope.
  3. Never claim a fix no check confirmed.
  4. Every fix writes a patch.
  5. Patches are append-only, and a patch never overrides a STOP.
  6. No gate block — the gate is `/dgf-verify`.
  7. `${CLAUDE_PLUGIN_ROOT}` always.

`references/PATCH-FORMAT.md` holds DD1's template, the field table, what each section is for — Root Cause is the most
valuable: what about DGF surprised you — and one worked example. The worked example is walked through
`check_patches.py` (RULES.md rule 4).

### DD7 — `/dgf-evolve`

```yaml
name: dgf-evolve
description: Distil the estate's patches into skill-context overrides that tighten the dgf-* skills — rules and checks added, never a STOP, an exit code or a gate's status relaxed — each checked by a script before any skill applies it. Use for "evolve", "dgf evolve", "learn from the patches", "update the skill rules", "distil the patches".
argument-hint: "[<skill> | all]"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion
disable-model-invocation: true
version: 0.1.0
```

The SKILL.md carries one machine-read line, which the contract test holds to the six readers:

```markdown
**Targets:** `dgf`, `dgf-commit`, `dgf-fix`, `dgf-implement`, `dgf-plan`, `dgf-verify`
```

It also carries the writer's limit, word for word (pinned as `OVERRIDE_WRITER_LIMIT`):

> Every rule you write may only tighten its skill: add a rule or a check. It never relaxes a STOP, an exit-code row,
> the status a gate script computes, a Critical Rule or Artifact Ownership, and never makes a skill install anything,
> skip a script, or write outside its own artifacts. Refuse a prevention point that would, and log it with its patch.

- **Step 0: Context.** Find the root, and read the config: `paths.patches`, `paths.skill_context`, and
  `paths.evolutions` (default `.dgf-factory/evolutions/` when a config predates it). It reads **no override of its
  own** (D10). The argument names one target (`plan` → `dgf-plan`), `all`, or nothing, which means all. Anything else
  → **STOP**, naming the targets.
- **Step 1: The patches.** Run
  `check_patches.py --workspaces-root "<root>" --patches-dir "<paths.patches>" --cursor "<paths.evolutions>patch-cursor.json"`:
  - `0` → continue;
  - `1` → each malformed patch is not read and never marked processed; name each one, and continue with the rest;
  - `2` `PATCH_CURSOR_UNREADABLE` → say every well-formed patch counts as new, and continue;
  - `3` → **STOP**.

  With no new patch, offer Step 3's review of stale rules alone, or **STOP**.
- **Step 2: The prevention points.** Read each new patch's Problem, Root Cause and Prevention. Build a registry with
  one row per actionable point — patch, point, target skill(s). A point that would relax the limit is refused and
  logged, never written (D14).
- **Step 3: The current overrides.** For each target, run `check_override.py` (DD5, `--skill <target>`).
  - `1` → the file is refused as it stands. This skill owns it, so repairing it is part of this run — for example
    dropping a rule whose patch was removed.
  - `0` / `2` → read it.

  Read the target's shipped `${CLAUDE_PLUGIN_ROOT}/skills/<target>/SKILL.md`, read-only, never its references or
  scripts (D12). Propose removing a rule the shipped skill now covers, or one that contradicts it.
- **Step 4: Proposed rules.** One prevention point becomes one rule: specific, checkable, in English, citing its
  patches. It must tighten (the writer's limit). Prefer a rule that makes the skill run a check it already has, or
  refuse something, over advice.
- **Step 5: Present, and ask.** Per target, show the rules to add, change and remove, and the refused points with their
  reasons. Then ask with `AskUserQuestion`: **Apply all**, **Let me pick**, **Apply none — mark the patches reviewed**,
  or **Cancel — write nothing**.
- **Step 6: Apply.** Write each target's override as
  `${CLAUDE_PLUGIN_ROOT}/skills/dgf-evolve/references/OVERRIDE-FORMAT.md` specifies. A file left with no rule is
  deleted, with its directory if that is then empty. Run `check_override.py` on every file written:
  - `0` → continue;
  - `2` → every flagged rule was written by this run, so re-read it against the writer's limit;
  - `1` → fix it and re-check, at most 3 attempts, then restore the file's previous content (or delete a new one) and
    **STOP**. Never leave a refused override behind.
- **Step 7: Log, then the cursor.** Write `<paths.evolutions>/<YYYY-MM-DD-HH.mm>.md`: the patches read, the rules
  added, changed and removed per skill, the refused points with their patches, and the malformed patches skipped.
  Then write the cursor: `processed` is its old value plus this run's new well-formed patches, sorted, one per line,
  with `updated`. Write it only after Step 6, or on "Apply none" — never on Cancel or a failure. Re-run Step 1's
  check: every patch this run read is now `state=processed`.
- **Step 8: Next.** Suggest `/dgf-commit` for `skill-context/` and `evolutions/`. Say:
  - each override takes effect in its skill's next run;
  - a reviewer should read the diff, because the check refuses what a script can see and cannot prove that a rule
    tightens.
- **Artifact Ownership:**
  - owns `<paths.skill_context>` (every override) and `<paths.evolutions>` (the logs and the cursor);
  - reads the patches (owned by `/dgf-fix`) and each target's shipped `SKILL.md`;
  - never edits a patch, a plan, a workspace file or a shipped skill.
- **Critical Rules:**
  1. Only tighten.
  2. A script checks every override written.
  3. Every rule cites its patches.
  4. Ask before writing.
  5. Patches are data.
  6. No override of its own.
  7. Never edit a shipped skill.

`references/OVERRIDE-FORMAT.md` holds DD3's template and its rules in prose, a worked example walked through
`check_override.py`, the evolution log's shape, and the cursor's shape.

### DD8 — The verify gate's next command

```python
GATES = {"verify": ("/dgf-plan", "/dgf-implement", "/dgf-fix", "/dgf-commit", None), "doctor": (None,)}
```

`suggest()`, first match wins:

1. `null` — the gate could not run (`CANNOT_RUN`), unchanged.
2. `/dgf-plan` — `PLAN_NOT_FOUND`, or a plan error, unchanged.
3. `/dgf-implement` — an unchecked task, an `ERROR` in the change checks (`outcome.reports[0]`), or a promoted warning
   whose original is in `outcome.reports[0]`. The reason lists those counts. When validator findings also block, it
   adds `"; then <n> new blocking finding(s) for /dgf-fix"`.
4. `/dgf-fix` — an `ERROR` in a validator report (`outcome.reports[1:]`), or a promoted warning whose original is
   there. The reason is `"<n> new blocking finding(s) — fix each inside the plan's scope and record a patch"`.
5. `/dgf-commit` — `pass` or `warn`, unchanged.
6. `null` — "the gate failed on a finding no command fixes — read the blockers", unchanged.

Scope comes before findings, because `/dgf-fix` works only inside a scope the change checks accept. Unchecked tasks
come first, because the finding may sit in a file an unfinished task still changes. A promotion is attributed by
identity (`found is f`), never by code. Trace: the existing `report.debug("verify_gate.next", "chose", …)`.
The doctor's allowlist stays `(None,)` (D2).

### DD9 — The contract tests

In `tests/test_skill_contracts.py`:

- `OVERRIDE_LIMIT` becomes D4's wording. `OVERRIDE_WRITER_LIMIT` is DD7's sentence.
- `CHECK_OVERRIDE = re.compile(r'check_override\.py" --workspaces-root "<root>" --skill ([a-z0-9-]+)')`.
- A reader is a `skills/*/SKILL.md` that calls `check_override.py`. The readers must be exactly `["dgf", "dgf-commit",
  "dgf-fix", "dgf-implement", "dgf-plan", "dgf-verify"]`. Each passes `--skill` its own directory name, holds
  `OVERRIDE_LIMIT`, and never says "override this file".
- Every SKILL.md whose text holds `skill-context/` or `skill_context` is a reader or `dgf-evolve`. So no skill reads an
  override unchecked.
- `dgf-evolve` holds `OVERRIDE_WRITER_LIMIT`, its `**Targets:**` line names exactly the readers, and it calls
  `check_override.py` with no literal `--skill dgf-evolve`.
- `NO_GIT = READ_ONLY + ("dgf-evolve", "dgf-fix")` replaces `READ_ONLY` in the no-git test.
- `test_the_skills_call_the_spine_scripts` also names `check_override.py` and `check_patches.py`.

## Commit Plan

- **Commit 1** (after tasks 1–2): `docs(adr): decide the learning loop, and let the verify gate suggest /dgf-fix`
- **Commit 2** (after tasks 3–4): `feat(scripts): check patches and skill-context overrides`
- **Commit 3** (after task 5): `feat(skills): check every override with a script before a skill applies it`
- **Commit 4** (after tasks 6–7): `feat: add /dgf-fix, and suggest it for a finding the branch introduced`
- **Commit 5** (after task 8): `feat(skills): add /dgf-evolve`
- **Commit 6** (after tasks 9–10): `docs: document the learning loop and mark the milestone done`

## Tasks

### Phase 1: Decisions

- [x] **Task 1: Write ADR 0021 — the learning loop — and index it.**
  Create `docs/adr/0021-learning-loop.md`, status `accepted`, date the day it is written, deciders `[Andrian Mamei]`,
  `supersedes: []`, tags `[learning, pipeline, overrides]`, following `docs/adr/README.md` §"Section contract".
  - *Title:* "The learning loop: /dgf-fix records patches inside a plan's scope, and /dgf-evolve writes overrides a
    script checks, which may only tighten a skill".
  - *Context* (cite, don't recall): E1, E3, E5–E9, E11, E14–E17, with paths, lines and the read date.
  - *Decision*, as sections:
    - §1 patches (D5, DD1);
    - §2 `/dgf-fix` (D1, D15, D16);
    - §3 overrides and their owner (D7);
    - §4 the limit, restated in D4's words, for readers and for the writer (DD5, DD7);
    - §5 `check_override.py` (D3, D8, D9) — what it decides, what it flags for judgement, and what it cannot prove;
    - §6 `/dgf-evolve` (D10–D14);
    - §7 the gate — `/dgf-fix` in verify's allowlist and not the doctor's, decided in ADR 0022 §8–§9 (D2);
    - §8 out of scope (D17).
  - *Alternatives:*
    - `FIX_PLAN.md` as AI Factory has it, and planless fixes (both put to the user; rejected, E3);
    - a prompt-only limit, and a writer-side script only (put to the user; rejected: anyone can hand-write an override);
    - a reader list inside `check_override.py` (rejected: a shared script never knows its callers);
    - AI Factory's high-water-mark cursor (rejected, E14);
    - overrides that win outright (rejected, E1's M2);
    - `/dgf-evolve` reading its own override (rejected, D10);
    - `/dgf-evolve` editing shipped skills, as `aif-evolve` edits custom ones (rejected: the plugin is installed
      read-only, and ADR 0001 keeps its skills its own);
    - a lexical check presented as a proof of tightening (rejected: it is stated as a filter, not a proof).
  - *Consequences:*
    - Positive: a hand-written override that grants a tool, narrows the gate or smuggles a block is never read; every
      rule traces to a patch; the gate names the command that fixes a finding.
    - Negative: the check is lexical, so plain-worded relaxation passes it to the reader's judgement and the reviewer's
      diff; a refused override leaves a skill on its shipped rules; readers gain a script call; the cursor can conflict
      on merge (one name per line keeps it a line-merge, and an unreadable cursor rescans everything); a fix needs a plan
      first.
    - Follow-ups: harvesting patches into `knowledge/` and validators; `/dgf-transfer`; `/dgf-commit` placing a patch in
      its Commit Plan group.
  - Add row 0021 to `docs/adr/README.md` §Index, and extend its §"See Also" line on ADR groups.
  - Run `bash tools/check-dual-schema-docs.sh`: sections 5 and 5b must pass.
  - Logging: none — documentation only.
  - Files: `docs/adr/0021-learning-loop.md`, `docs/adr/README.md`.

- [x] **Task 2: Write ADR 0022, superseding ADR 0020, and repoint its live citations.** (depends on 1)
  - Create `docs/adr/0022-gate-block-contract-revised.md`: status `accepted`, `supersedes: [0020]`, deciders
    `[Andrian Mamei]`, tags `[gates, pipeline]`.
    - *Title:* "Every gate block is built by one library, its status computed from its entries, and it never claims a
      check it did not run — and the verify gate sends a finding the branch introduced to /dgf-fix".
    - *Context:* restate ADR 0020's context, with its two errata folded in (E10). Add E2, E3 and E4.
    - *Decision:* restate §1–§7 of ADR 0020 as they are, keeping the section numbers (D18).
      - §8 gains `/dgf-fix` for `verify`. The doctor stays `null`, and the section says why: a doctor failure is a
        defect in the installed plugin, which `/dgf-fix` — scoped to a plan in an estate — cannot touch. This departs
        from the roadmap's "verify and doctor", by the user's decision D2.
      - §9's `suggested_next` becomes DD8's order.
    - *Alternatives:* 0020's own, plus:
      - `/dgf-fix` in the doctor's allowlist (put to the user; rejected);
      - `/dgf-fix` for every new finding, ahead of unchecked tasks (rejected: DD8's reasons);
      - attributing a promotion by code (rejected: two findings can share a code).
    - *Consequences:* 0020's, plus:
      - a new validator finding no longer routes to `/dgf-implement`;
      - a consumer that knew 0020's allowlist meets a new command.
  - Set ADR 0020's `status: superseded-by-0022` and its `date` to the day. Change nothing in its body. Update its index
    row, and add row 0022.
  - Repoint every **live** citation of ADR 0020 to ADR 0022, with the same section numbers. The files are:
    - `.ai-factory/ARCHITECTURE.md`, `.ai-factory/DESCRIPTION.md` and `.ai-factory/RULES.md` (rule 7, the gate-block builder rule);
    - `AGENTS.md` (three places, and its Agent Rules list: 0020 joins the superseded history, 0021 and 0022 join the
      decisions);
    - `docs/architecture.md`, `docs/pipeline.md` and `docs/skill-authoring.md` (two places);
    - `scripts/check_change.py`, `scripts/lib/gate_result.py`, `scripts/lib/plan.py`, `scripts/lib/report.py` and
      `scripts/verify_gate.py` (five places);
    - `skills/dgf-doctor/SKILL.md`, `skills/dgf-doctor/scripts/doctor.py` (three places) and
      `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`;
    - `tests/test_doctor.py`, `tests/test_gate_result.py`, `tests/test_plan.py` and `tests/test_verify_gate.py`;
    - `.ai-factory/ROADMAP.md`, only in the open "DGF-Specific Skills" entry (§6).

    Leave alone:
    - the completed roadmap entries;
    - `docs/blueprint.md:349`, which is dated history;
    - the archived plans;
    - ADR 0020 itself.

    Then run
    `grep -rn "ADR 0020\|0020-gate-block" skills scripts knowledge tests docs AGENTS.md .ai-factory --include=*.md --include=*.py`.
    Each hit left must be one of those four.
  - Run `bash tools/check-dual-schema-docs.sh` (sections 5 and 5b) and the test suite: all green. Only citations moved.
  - Logging: none — documentation and comments only.
  - Files: `docs/adr/0022-gate-block-contract-revised.md`, `docs/adr/0020-gate-block-contract.md` (frontmatter only),
    `docs/adr/README.md`, and the files listed above.

### Phase 2: The checks

- [x] **Task 3: Add `scripts/lib/patches.py` and `scripts/check_patches.py`.** (depends on 1)
  - Implement DD1 and DD2. Add to `report.CODES`, under a comment `# the learning loop (check_patches.py,
    check_override.py; ADR 0021)`:
    - `PATCH_NAME_INVALID`, `PATCH_UNREADABLE`, `PATCH_FIELD_MISSING`, `PATCH_FIELD_INVALID` and
      `PATCH_SECTION_INVALID` → `EXIT_BLOCKED`;
    - `PATCH_CURSOR_UNREADABLE` → `EXIT_WARNINGS`.
  - `patches.py` imports only `report` and `plan` from its package. `check_patches.py` uses `cli.parser()`, so a bad
    argument is exit `3`. Neither imports `lxml` or `jsonschema`.
  - Logging: DD1's and DD2's `report.debug` lines; every rejected path argument is traced before `report.fail()`.
  - Tests:
    - `tests/test_patches.py` for the parser, on in-memory and temp files:
      - DD1's example is clean;
      - each field rule, and each section rule, including a `## ` inside a fence and a bad tag;
      - a date that disagrees with the name;
      - `workspaces: none` with `files` set;
      - an unknown finding code;
      - invalid UTF-8;
      - `read_cursor` on a missing file, a valid one, a non-object, and a list of numbers.
    - `tests/test_check_patches.py` for the CLI:
      - a patch named relative to the working directory and one named absolutely both resolve;
      - a patch outside `R/D`, and a missing `R`, each exit `3`;
      - a missing patches directory → exit `0`, `total=0`;
      - `--cursor` states `new` / `processed` / `malformed`, and a processed name that is gone is not reported;
      - an unreadable cursor → exit `2` with every well-formed patch `new`;
      - a title holding a newline prints on one line;
      - `run_cli_blocking` proves no third-party import;
      - `--help` lists every flag;
      - the whole-root walk never reads `.dgf-factory/` (E20): on a root holding
        `.dgf-factory/evolutions/patch-cursor.json` and `.dgf-factory/patches/<a patch>`, `cli.collect([root])` —
        the configuration list `runner.targets()` uses — returns no path under `.dgf-factory/`. This pins the
        dot-directory skip the cursor now depends on. It calls `cli.collect()` rather than `runner.targets()`, because
        `lib/process_checks.py:32` imports `lxml` and the test must run without it.
  - Known-bad cases under `tests/fixtures/known-bad/`, each with `"cli": "check_patches.py"` and its patch passed as
    `workspaces/.dgf-factory/patches/<name>.md` from the case directory:
    - `patch-name-invalid`, `patch-field-missing`, `patch-field-invalid`, `patch-section-invalid`;
    - `patch-unreadable`, holding invalid UTF-8. Change `tests/test_known_bad.py`'s DGF-path scan to
      `read_text(encoding="utf-8", errors="replace")`, so such a fixture can exist (E12).
  - `tests/test_report.py`: a `LearningCodes` class pins each new code's exit.
  - Files: `scripts/lib/patches.py`, `scripts/check_patches.py`, `scripts/lib/report.py`, `tests/test_patches.py`,
    `tests/test_check_patches.py`, `tests/test_report.py`, `tests/test_known_bad.py`,
    `tests/fixtures/known-bad/patch-*/`.

- [x] **Task 4: Add `scripts/lib/overrides.py` and `scripts/check_override.py`.** (depends on 3)
  - Implement DD3 and DD4. Add to `report.CODES`, in the same block:
    - `OVERRIDE_UNREADABLE`, `OVERRIDE_SHAPE`, `OVERRIDE_SOURCE_MISSING` and `OVERRIDE_FORBIDDEN` → `EXIT_BLOCKED`;
    - `OVERRIDE_TOUCHES_LIMIT` → `EXIT_WARNINGS`.
  - `overrides.py` imports `report` and `patches` (for `NAME`) only. Its outside-root markers are built from pieces
    (DD3, E19). After the task, `python3 skills/dgf-doctor/scripts/doctor.py` reports no `ABSOLUTE_PATH`.
  - Logging: DD3's and DD4's `report.debug` lines.
  - Tests:
    - `tests/test_overrides.py`:
      - DD3's example is clean when its patch exists;
      - each shape rule at its line — title for another skill, a second `##`, text outside a rule, a missing or extra
        bullet, a duplicate name, 41 rules, a 601-character rule, a fence, `<!--`, invalid UTF-8, over `MAX_BYTES`;
      - a missing source patch, and a source that is not a patch name;
      - every `FORBIDDEN` entry, one test each, including that `--strict` and `--verbose` pass and `--strict-mode` does
        not;
      - `LIMIT_WORDS` matching word-bounded and case-insensitive, one warning per rule.
    - `tests/test_check_override.py`:
      - an absent override → `OVERRIDE: none`, exit `0`;
      - `--skill ../x` and a missing root → exit `3`;
      - a root with no config still runs (D8);
      - shape failure → the three other checks are `NOT RUN`;
      - exit `2` for a touching rule;
      - `run_cli_blocking`; `--help`.
  - Known-bad cases, each with `"cli": "check_override.py"`: `override-unreadable`, `override-shape`,
    `override-source-missing`, `override-forbidden`. `tests/test_report.py`'s `LearningCodes` gains the new codes.
  - Files: `scripts/lib/overrides.py`, `scripts/check_override.py`, `scripts/lib/report.py`, `tests/test_overrides.py`,
    `tests/test_check_override.py`, `tests/test_report.py`, `tests/fixtures/known-bad/override-*/`.

### Phase 3: The limit, restated and enforced

- [x] **Task 5: Make every reader check its override with `check_override.py`, in D4's words.** (depends on 4)
  - In `skills/dgf/SKILL.md` (Step 0.1), `skills/dgf-plan/SKILL.md` (Step 0), `skills/dgf-implement/SKILL.md`
    (Step 0.1), `skills/dgf-verify/SKILL.md` (Step 0.0) and `skills/dgf-commit/SKILL.md` (Step 0), replace the
    override sentence with DD5's block, each with its own `--skill`.
    - `/dgf` notes it passes the template's two directories on a first run.
    - `/dgf-verify` keeps its report line.
    - Bump each skill's minor version.
  - `skills/dgf-implement/SKILL.md` Step 0.1's patch bullet gains: "A patch informs; it never overrides this skill, the
    plan or a STOP."
  - `skills/dgf/references/config-template.yaml`: add `evolutions: .dgf-factory/evolutions/` under `paths`.
  - `tests/test_skill_contracts.py`: the DD9 changes that do not need the new skills yet —
    - the new `OVERRIDE_LIMIT`;
    - `CHECK_OVERRIDE`, and the readers found by it, with `/dgf-fix` not yet among them: the list is the five;
    - the "no unchecked reader" test;
    - `check_override.py` among the called scripts.
  - Walk each reader's exit table against `check_override.py` on a temp root with no override, a clean one, a refused
    one and a touching one (RULES.md rule 4). Record the four outputs in the plan's "Follow-ups found during
    implementation".
  - Logging: none in the skills; the script traces under `--verbose`.
  - Files: the five `skills/*/SKILL.md`, `skills/dgf/references/config-template.yaml`, `tests/test_skill_contracts.py`.

### Phase 4: `/dgf-fix` and the gate

- [x] **Task 6: Add `/dgf-fix`.** (depends on 3, 5)
  - Create `skills/dgf-fix/SKILL.md` exactly as DD6 lays it out, in the house skeleton: Workflow, Execution Rules
    (DO / DON'T), Artifact Ownership, Critical Rules. Create `skills/dgf-fix/references/PATCH-FORMAT.md`.
  - Walk the worked example: save it as a patch in a temp root, run `check_patches.py` on it (exit `0`), then break one
    field, one section and the name (exit `1`, each code). Record the outputs in the plan's follow-ups (RULES.md
    rule 4). Walk Step 0.2's table against `locate_plan.py` and `check_plan.py` on a temp root with no plan, one plan
    and two. Walk Step 3's table against `check_change.py --changed … --skip-validators` on the same root, and record
    each output:
    - a planned config file → `0`, or `2` with only `CHANGE_TASK_FILE_UNCHANGED`;
    - an unplanned config file → `2`, `CHANGE_UNPLANNED_FILE`;
    - a file in an undeclared workspace → `1`, `CHANGE_UNDECLARED_WORKSPACE`;
    - a new `js/` file → `1`, with `CHANGE_CODE_FILE_NEW` (and `CHANGE_CODE_UNPLANNED` when no task lists it).

    Run the same calls under `run_cli_blocking`, to prove no third-party import.
  - `tests/test_skill_contracts.py`: readers become the six, `NO_GIT` gains `dgf-fix`, and `check_patches.py` joins the
    called scripts.
  - `skills/dgf-doctor/scripts/doctor.py`: `EXPECTED_SLICES` gains `dgf-fix` and `dgf-evolve`, after `dgf-commit`.
    `tests/test_doctor.py`'s `test_expected_slices_report_present_or_not_yet_built` (`:171-177`) checks a fixed tuple of
    names; add `dgf-fix` and `dgf-evolve` to it.
  - Run `python3 skills/dgf-doctor/scripts/doctor.py`: exit `0`, or `2` with only `VALIDATOR_DEPS_MISSING`.
  - Logging: none in the skill; it relays every script line it acts on.
  - Files: `skills/dgf-fix/SKILL.md`, `skills/dgf-fix/references/PATCH-FORMAT.md`, `tests/test_skill_contracts.py`,
    `skills/dgf-doctor/scripts/doctor.py`, `tests/test_doctor.py`.

- [x] **Task 7: Let the verify gate suggest `/dgf-fix`.** (depends on 2, 6)
  - `scripts/lib/gate_result.py`: DD8's `GATES`, and its docstring's allowlist line.
  - `scripts/verify_gate.py`: `suggest()` as DD8, with a helper `_split(run)` returning (change-check errors, validator
    errors, change promotions, validator promotions). Update the docstring's "Exit codes" and "The block" paragraphs.
    Keep the `verify_gate.next` trace.
  - `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`: the `suggested_next.command` table gains the `/dgf-fix`
    row, and the `/dgf-implement` row narrows to tasks and change checks. The example block's reason reads
    "1 task(s) unchecked; then 1 new blocking finding(s) for /dgf-fix". `skills/dgf-verify/SKILL.md` Step 2's `1` row
    stays as it is: the block names the command.
  - Tests:
    - `tests/test_gate_result.py`:
      - the refused-command example becomes `/dgf-evolve`;
      - `verify` accepts `/dgf-fix`;
      - `doctor` still refuses `/dgf-fix` (the `:206` trace test keeps it).
    - `tests/test_verify_gate.py`:
      - the new dead transition → `/dgf-fix`, with the reason naming a patch;
      - an unchecked task plus a new dead transition → `/dgf-implement`, with the reason naming both;
      - `CHANGE_UNDECLARED_WORKSPACE` plus a new finding → `/dgf-implement`;
      - `--strict` with a new `UNREACHABLE_STATE` → `GATE_STRICT_WARNING` → `/dgf-fix`, while the existing
        `CHANGE_UNPLANNED_FILE` promotion still → `/dgf-implement`;
      - tests needing the validators sit under `have_dependencies()`.
    - `tests/test_doctor.py`'s `assertNotIn("/dgf-fix", out)` stays.
  - Logging: `report.debug("verify_gate.next", "chose", command=…, why=…)` as today, plus
    `report.debug("verify_gate.split", "split", scope=n, findings=n, promoted_scope=n, promoted_findings=n)`.
  - Files: `scripts/lib/gate_result.py`, `scripts/verify_gate.py`,
    `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`, `tests/test_gate_result.py`, `tests/test_verify_gate.py`.

### Phase 5: `/dgf-evolve`

- [ ] **Task 8: Add `/dgf-evolve`.** (depends on 4, 6)
  - Create `skills/dgf-evolve/SKILL.md` exactly as DD7 lays it out, with the `**Targets:**` line and the writer's limit.
    Create `skills/dgf-evolve/references/OVERRIDE-FORMAT.md`: the override template and rules, the worked example, the
    evolution log's shape, and the cursor's shape.
  - Walk it on a temp root holding two patches (one malformed) and no cursor:
    - Step 1's check → exit `1`, one `new`, one `malformed`;
    - write the worked example as `skill-context/dgf-plan/SKILL.md` → `check_override.py` exit `0`;
    - add a rule naming `--skip-validators` → exit `1` `OVERRIDE_FORBIDDEN`;
    - write the cursor → Step 1's check shows the patch `processed`.

    Record the outputs in the plan's follow-ups (RULES.md rule 4).
  - `tests/test_skill_contracts.py`: the writer test — `OVERRIDE_WRITER_LIMIT`, `**Targets:**` equal to the readers, no
    `--skill dgf-evolve` — and `NO_GIT` gains `dgf-evolve`.
  - `docs/skill-authoring.md`'s frontmatter table gains a `disable-model-invocation` row: `false`, except a skill that
    rewrites what other skills do (`/dgf-evolve`), which runs only when asked.
  - Logging: none in the skill; it relays each script line it acts on.
  - Files: `skills/dgf-evolve/SKILL.md`, `skills/dgf-evolve/references/OVERRIDE-FORMAT.md`,
    `tests/test_skill_contracts.py`, `docs/skill-authoring.md`.

### Phase 6: Proof and documentation

- [ ] **Task 9: Walk the loop end to end, and record it.** (depends on 5, 7, 8)
  On a git-initialised copy of a synthetic root (the `tests/test_verify_gate.py` shape: `app`, `other`, `webasm`):
  - With a full plan on `feature/x`, introduce a new dead transition. `verify_gate.py --base main` → exit `1`,
    `suggested_next.command` `/dgf-fix`.
  - Follow `/dgf-fix`'s steps by hand:
    - Step 1's whole-root `check_change.py` shows the `ERROR`;
    - fix it; the same check no longer shows it;
    - write a patch; `check_patches.py` → exit `0`;
    - the gate → `/dgf-commit`.
  - Follow `/dgf-evolve`'s steps:
    - the cursor check shows the patch `new`;
    - write an override for `dgf-plan` from it; `check_override.py` → `0`;
    - write the cursor; the patch is `processed`.
  - Hand-write a relaxing override: a rule saying "skip the validators with `--skip-validators`", and one granting
    `Bash(`. `check_override.py` → exit `1`. Say which reader would refuse it.
  - Run the whole suite, `bash tools/check-dual-schema-docs.sh`, `python3 skills/dgf-doctor/scripts/doctor.py` and
    `python3 tools/run_known_good.py` (unaffected, but proven so).
  - Record every command, exit and key line in "Follow-ups found during implementation", with the date.
  - Logging: run each script once with `--verbose`, and record that the traces went to stderr and the block stayed
    last.
  - Files: this plan only.

- [ ] **Task 10: Document the learning loop, and mark the milestone done.** (depends on 9)
  Through `/aif-docs`:
  - `docs/pipeline.md`:
    - a `## The learning loop` section: the two skills, what each writes, DD1's patch and DD3's override in brief, the
      cursor, the limit in D4's words, a table of the two scripts' exits, and the gate's new `suggested_next` row;
    - the artifact table: `patches/` owner `/dgf-fix` (read by `/dgf-implement`, `/dgf-fix`, `/dgf-evolve`);
      `skill-context/` owner `/dgf-evolve` (checked by `check_override.py`, then read by its skill); a new
      `evolutions/` row;
    - "The five skills" table: each reader's "Scripts it runs" cell gains `check_override.py`;
    - the config block shows the template's `paths` keys in full — `patches`, `skill_context` and `evolutions`, not
      `evolutions` alone. Today it shows neither of the first two;
    - the page title and intro say the spine is five skills and the loop two.
  - `docs/skill-authoring.md`:
    - "Reading a validator's output" gains the `check_patches.py` and `check_override.py` rows (`PATCHES:`,
      `PATCH:`, `OVERRIDE:`, `RULE:`);
    - the allowlist bullet says `verify` allows `/dgf-fix`, and `doctor` stays `null`;
    - the ship checklist says "an override is checked with `check_override.py` and read with the shared limit";
    - "Body structure" says the context step checks and reads the skill's override (DD5's block).
  - `docs/architecture.md`: the ownership table's `skill-context/` and `evolutions/` rows.
  - `docs/blueprint.md`: rows `:290-291` restated in D4's words, marked `*(corrected <date>)*` with the day's date.
  - `docs/getting-started.md`: a short "trying the loop" beside "trying the spine" — the two scripts on a temp root.
  - `README.md`: replace "Still to come" with what `/dgf-fix` and `/dgf-evolve` do, and add them to the pipeline
    example.
  - `AGENTS.md`: the structure tree (the two skills, the two scripts, `lib/patches.py`, `lib/overrides.py`), the
    overview and "Not yet created", and Key Entry Points (`check_override.py`, `lib/overrides.py`, ADR 0021).
  - `.ai-factory/DESCRIPTION.md` Current State, and `.ai-factory/ARCHITECTURE.md`:
    - the folder tree, and "The tree is the target shape";
    - a Dependency Rules line: `/dgf-evolve` reads a target's shipped `SKILL.md`, read-only, and a shared script never
      lists its callers.
  - `.ai-factory/ROADMAP.md`:
    - mark Learning Loop `[x]`, restating its text in D4's words, noting the doctor decision (ADR 0022), and adding a
      Completed row;
    - move the plan's follow-ups that no open milestone owns into §Follow-ups.
  - Run `bash tools/check-dual-schema-docs.sh` and the suite: all green.
  - Logging: none — documentation only.
  - Files: the documents listed above.

## Risks

- **R1 — The check is lexical.** It refuses the relaxations a script can see: a tool grant, a narrowing flag, a gate
  block, an install, a destructive git command, a path out of the root. It cannot see a relaxation in plain words
  ("treat a dead transition as fine"). That is why `OVERRIDE_TOUCHES_LIMIT` hands every rule naming a protected word to
  the reader's judgement, why the limit sentence stays, and why ADR 0021 says the check is a filter, not a proof. The
  override is committed, so review of its diff is the last line.
- **R2 — False refusals.** A tightening rule that names a forbidden construct — a git command, a flag — is refused
  whole. The skill then runs on its shipped rules and says so. `FORBIDDEN` is a named list with a test per entry, so a
  false refusal is fixed by narrowing one pattern.
- **R3 — Every reader now runs a script first.** An exit `3` from `check_override.py` STOPs the skill. Its arguments are
  pinned by the contract test (flags in `--help`, the skill name its own), and it needs no config (D8), so the only
  exit `3` is a wrong call.
- **R4 — The cursor conflicts when two branches evolve.** One name per line keeps it a line-merge. A bad merge reads as
  `PATCH_CURSOR_UNREADABLE`, and everything counts as new. Re-reading patches re-proposes only rules Step 3 already
  finds, so the cost is time, not wrong rules.
- **R5 — `/dgf-commit` asks where a patch goes.** A patch maps to no Commit Plan group, so Step 3 asks. That is
  correct, but clumsy. It is a follow-up.
- **R6 — The repoint sweep touches 20 files.** A missed citation still resolves, because ADR 0020 remains, superseded.
  It just points at history. Task 2's grep lists every survivor.

## Follow-ups

- Harvest patches into the shipped `knowledge/`, and turn `findings: none` patches into validators (maintainer work, D17).
- `/dgf-transfer`, if estates ever share rules across roots (D17).
- `/dgf-commit` could place `.dgf-factory/patches/` files with the fix they record.
- `/dgf-implement` could read patches through `check_patches.py`, and skip malformed ones.

## Follow-ups found during implementation

- **Task 2 (2026-09-26) — the sweep's survivors.** Beyond the four the task names, the grep also keeps:
  ADR 0021 and ADR 0022, which name ADR 0020 as the decision they build on or supersede; ADR 0020's own
  index row in `docs/adr/README.md`; and `.ai-factory/ROADMAP.md`'s open Learning Loop entry, which Task 10
  restates. `.ai-factory/ROADMAP.md` §Follow-ups' "Gate entry summaries" line cited ADR 0020 §3 as a live
  rule, so it was repointed to ADR 0022 §3 with the "DGF-Specific Skills" entry.
- **Task 3 (2026-09-26) — lines split on `\n` only.** `patches.parse()` splits on `\n`, not `str.splitlines()`,
  which also breaks at U+2028, `\x1c`–`\x1e` and `\x85`: a title holding one would have been cut, and its tail
  read as a stray field line. `overrides.py` reads the same way. The CLI test pins it.
- **Task 3 (2026-09-26) — `Files:` counts the cursor.** With `--cursor`, `check_patches.py`'s summary counts the
  cursor as one more file, because it is a report of its own (it carries `patch-cursor` and its warning). The
  `PATCHES:` line holds the patch counts the skills read.
- **Task 4 (2026-09-26) — two tightenings beyond DD3.** `check_rules()` also checks the `> ` quoted lines, which a
  reading skill reads too: without it, a quoted line could carry `--skip-validators` past the check. And
  `LIMIT_WORDS` also match a plural or past form (`STOPs`, `skipped`, `allowed`, `waived`), still word-bounded, so
  `stopwatch` does not. `parse()` returns an `Override(rules, quoted)`; `check_rules(rules, rel, rep, quoted=())`
  keeps DD3's signature.
- **Task 5 (2026-09-26) — the readers' exit table, walked** against `check_override.py --workspaces-root <tmp>
  --skill dgf-plan --skill-context-dir ".dgf-factory/skill-context/" --patches-dir ".dgf-factory/patches/"` (the
  table is the same in all five readers), with one patch in the patches directory:
  1. no override → `OVERRIDE: none — no .dgf-factory/skill-context/dgf-plan/SKILL.md`, `CLEAN`, exit `0` — row `0`,
     no override;
  2. DD3's example → `OVERRIDE: … skill=dgf-plan rules=1`, `RULE: 1 line=8 sources=1 name="A task that renames a
     state lists every transition to it"`, `CLEAN`, exit `0` — row `0`, read and apply;
  3. plus a rule "Run check_change.py with --skip-validators for speed." → `ERROR OVERRIDE_FORBIDDEN …:13 rule
     \`Narrow the gate\` holds \`--skip-validators\` (flag)`, and `WARN OVERRIDE_TOUCHES_LIMIT …:13 … names \`skip\``,
     `BLOCKED`, exit `1` — row `1`, refused;
  4. instead a rule "STOP when a renamed state still has a transition to its old name." → `WARN
     OVERRIDE_TOUCHES_LIMIT …:13 rule \`Stop on a renamed state\` names \`stop\``, `WARNINGS`, exit `2` — row `2`,
     read, apply and judge the rule (it tightens);
  5. `--skill ../x` → stderr `--skill is not a skill name …`, exit `3` — row `3`, **STOP**.
- **Task 6 (2026-09-26) — PATCH-FORMAT.md's worked example, walked.** Saved as a patch in a temp root,
  `check_patches.py --workspaces-root <tmp> --patches-dir ".dgf-factory/patches/" <tmp>/.dgf-factory/patches/<name>`
  → `PATCHES: .dgf-factory/patches/ total=1 malformed=0`, `CLEAN`, exit `0` (also `0` under `run_cli_blocking`).
  Broken one way at a time, each exit `1`: `severity: urgent` → `PATCH_FIELD_INVALID …:9`; the Prevention text
  deleted → `PATCH_SECTION_INVALID …:21 \`## Prevention\` is empty`; the name `2026-09-26-14.30.md` →
  `PATCH_NAME_INVALID`; `date: 2026-09-26 14:31` → `PATCH_FIELD_INVALID …:3 … disagrees with the name's timestamp`;
  a `- owner: me` bullet → `PATCH_FIELD_INVALID …:10`; a `\xff` byte → `PATCH_UNREADABLE … not UTF-8 at byte 46`.
  The reference's table holds these exact lines. (DD1's example puts Prevention at line 20; the worked example's
  Root Cause runs to two lines, so it is 21.)
- **Task 6 (2026-09-26) — Step 0.2's table, walked** on a temp root of `test_check_change.py`'s shape (`app`,
  `other`, `webasm`), `locate_plan.py --workspaces-root <tmp> --plans-dir ".dgf-factory/plans/" --fast-plan
  ".dgf-factory/PLAN.md"`: no plan → `ERROR PLAN_NOT_FOUND … run /dgf-plan`, exit `1`; the branch's plan →
  `PLAN: … mode=full source=branch`, exit `0`; two active plans and no branch plan → `ERROR PLAN_AMBIGUOUS … 2 plans
  are active … name one`, exit `1`; one active plan and no branch plan → `WARN PLAN_FALLBACK … source=lone`, exit
  `2`. `check_plan.py` on the plan → `AFFECTS: app`, two `TASK:` lines, `CLEAN`.
- **Task 6 (2026-09-26) — Step 3's table, walked** with `check_change.py --changed … --skip-validators` on the same
  root (each exit identical under `run_cli_blocking`): a planned config file → exit `0`; an unplanned config file →
  exit `2`, `WARN CHANGE_UNPLANNED_FILE`; a file in `other` → exit `1`, `ERROR CHANGE_UNDECLARED_WORKSPACE` (and
  `WARN CHANGE_UNPLANNED_FILE`); `A:app/js/new.js` → exit `1`, `ERROR CHANGE_CODE_UNPLANNED` and `ERROR
  CHANGE_CODE_FILE_NEW`. With Task 1 checked, a fix-only set → exit `2` with only `WARN CHANGE_TASK_FILE_UNCHANGED`,
  which Step 3 says to ignore.
- **Task 6 (2026-09-26) — the doctor's `/dgf-fix` assertion narrowed.** `tests/test_doctor.py` asserted that
  `/dgf-fix` appears nowhere in the doctor's output. With `dgf-fix` in `EXPECTED_SLICES`, the build progress prints
  `skills/dgf-fix/ — present`, so both assertions now read the gate block (`json.dumps(payload)`), which is what
  they guard: the doctor never suggests `/dgf-fix`.
- **Task 7 (2026-09-26) — the reason's wording.** A change-check error now reads "change-check error(s)" and a
  promoted change-check warning "change-check warning(s) promoted by --strict", where 0020's gate said "new
  blocking finding(s)" and "warning(s) promoted by --strict" for all of them: "new blocking finding(s)" now means a
  validator finding, the one `/dgf-fix` takes. `skills/dgf-verify/SKILL.md`'s intro, which said "Fixing belongs to
  `/dgf-implement`", now names both and says the block chooses; Step 2's `1` row is unchanged.
