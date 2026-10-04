[← Getting Started](getting-started.md) · [Back to README](../README.md) · [Architecture →](architecture.md)

# The Pipeline Spine, the Learning Loop and the DGF-Specific Skills

Five skills — the **spine** — take a change to a DGF estate from a request to a commit. Two more —
the **learning loop** — fix what the gate finds and turn each fix into a rule that tightens the
spine's next run. Four **DGF-specific skills** work on one kind of configuration each — components,
processes and workflows, entities — and audit the whole root, including a change's blast radius.
Every decision a script can make is made by a script; the skills decide only what needs judgement.

```text
/dgf  ──►  /dgf-plan  ──►  /dgf-implement  ──►  /dgf-verify  ──►  /dgf-commit
 set up     plan the       compose, task by     the gate: plan,    conventional
 the root   change         task, and validate   change, baseline   commits
                                                  │     ▲
                                                  ▼     │
                                                /dgf-fix ──► patches/ ──► /dgf-evolve ──► skill-context/
                                                fix inside              distil into rules the
                                                the plan                ten skills check, then apply

/dgf-component  /dgf-process  /dgf-model     inspect and validate anywhere; write one kind of
                                             file each, only inside the plan's scope
/dgf-audit                                   the root's health, and the processes a file reaches
```

The unit of work is the **whole workspaces root**, not one workspace
([ADR 0026](adr/0026-authoring-entry-point-revised.md)). A change in `webasm` is live in every
application, and a change in one file can break a file it never touched, so the gate always
looks at the whole root.

## The five skills

| Skill | Does | Scripts it runs | Writes |
|---|---|---|---|
| `/dgf` | Finds the root, inventories it, asks for the estate's DGF version | `locate_plan.py --setup`, `check_override.py`, `inventory_root.py` | `.dgf-factory/config.yaml`, `.dgf-factory/DESCRIPTION.md` |
| `/dgf-plan` | Plans a change — fast, full or ultra — on its own branch | `locate_plan.py --root-only`, `check_override.py`, `inventory_root.py`, `route_means.py`, `check_plan.py --overlap` | the plan |
| `/dgf-implement` | Executes the plan one task at a time, validating each | `locate_plan.py`, `check_override.py`, `check_plan.py`, `validate_config.py`, `route_means.py`, `check_change.py --files` | the task's workspace files, and its checkbox |
| `/dgf-verify` | The gate: tasks done, change inside the plan, no new finding across the root | `locate_plan.py`, `check_override.py`, `inventory_root.py`, `verify_gate.py` | nothing — it relays the `dgf-gate-result` block `verify_gate.py` computes |
| `/dgf-commit` | Conventional commits scoped by workspace, following the plan's Commit Plan | `locate_plan.py`, `check_override.py`, `check_change.py --skip-validators` | git history, after confirmation |

Each runs `check_override.py` before it reads its skill-context override (see
[The learning loop](#the-learning-loop)). `/dgf-doctor` sits beside them: it checks that the
plugin itself is installed correctly.

What a change is made of is fixed by [ADR 0010](adr/0010-dgf-implement-scope.md): modern
JSON component configuration under `FM/_COMPONENTS/` first, legacy XML where no JSON
alternative exists, and a little JavaScript or CSS only where configuration cannot express the
change. C#, TypeScript, Angular, SQL and plugin assemblies are out of scope: a plan names them
under `## Scope`, and no task writes them.

## `.dgf-factory/` — the pipeline's artifacts

`.dgf-factory/` sits **once, at the workspaces root**, and is committed: plans travel with
their branches, and the overlap check reads other branches' plans.

| Path | Owner | Read by |
|---|---|---|
| `config.yaml` | `/dgf` | every skill |
| `DESCRIPTION.md` | `/dgf` | `/dgf-plan`, `/dgf-implement` |
| `PLAN.md` | `/dgf-plan` (fast plans) | `/dgf-implement` (checkboxes only), `/dgf-verify`, `/dgf-commit` |
| `plans/<stem>.md`, `plans/<stem>/` | `/dgf-plan` (full plans, ultra bundles) | the same |
| `patches/<YYYY-MM-DD-HH.mm>-<slug>.md` | `/dgf-fix` — append-only | `/dgf-implement`, `/dgf-fix`, `/dgf-component`, `/dgf-process` and `/dgf-model` (the latest ten, as cautions), `/dgf-evolve` (the new ones, through `check_patches.py --cursor`) |
| `skill-context/<skill>/SKILL.md` | `/dgf-evolve` | `check_override.py`, then the matching skill — one of the ten readers, only when the check accepts it — as an override that may only tighten |
| `evolutions/` | `/dgf-evolve` — a log per run, and `patch-cursor.json` | `/dgf-evolve`, through `check_patches.py --cursor` |

`config.yaml` is written from `skills/dgf/references/config-template.yaml`:

```yaml
dgf:
  version: "1.1.15"          # the DGF version this estate runs, or "unknown" (ADR 0019)
language: {ui: en, artifacts: en}
paths:
  description: .dgf-factory/DESCRIPTION.md
  plan: .dgf-factory/PLAN.md
  plans: .dgf-factory/plans/
  patches: .dgf-factory/patches/
  skill_context: .dgf-factory/skill-context/
  evolutions: .dgf-factory/evolutions/
git:
  enabled: true
  base_branch: main
  branch_prefix: feature/
workflow:
  verify_mode: normal         # normal | strict
```

The scripts never read it. The skills read it and pass its values as arguments: the standard
library has no YAML parser, and a validator must not guess a key.

## The plan file

The format is decided by [ADR 0017](adr/0017-plan-file-format.md); the skill's own template is
`skills/dgf-plan/references/PLAN-FORMAT.md`. A plan is Markdown with a flat YAML header:

```yaml
---
plan_format: 1
mode: full                          # fast | full | ultra
branch: feature/zims-inspection-fee # the file stem: branch with / → -
created: 2026-09-25
affects_workspaces: [zims, webasm]  # never empty
base_workspace_reason: "The fee DataSource is shared by every application's payment page"
---
```

Only `key: value`, `key: "quoted"` and `key: [a, b]` are read — no nested maps, no block
lists. `base_workspace_reason` is required whenever `webasm` is listed. `affects_workspaces`
names workspaces only: an `applibs*` folder holds plugin assemblies and has no `FM/`, so it is
never one.

Each task is a checkbox with field bullets:

```markdown
- [ ] Task 3: Hide the fee panel until the gateway confirms payment (depends on 2)
  - kind: code
  - reason: No EventBase verb reads the gateway callback (knowledge/composition-specs.md §3.1)
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.js
```

`kind` is `config` or `code`; `code` needs a `reason`. `files` and `deletes` are relative to
the workspaces root, with `/`. A path that is absolute, names a drive, uses `\`, or has an
empty, `.` or `..` segment is `PLAN_PATH_INVALID` (exit `1`): `webasm/FM/../../x.json` would
otherwise read as `webasm` configuration while naming a file outside the root, where the change
gate never looks. Every other path falls in one class:

| Class | Paths | In a plan |
|---|---|---|
| config | `<ws>/FM/**/*.json`, `<ws>/FM/**/*.xml` | `kind: config` |
| code | a form's `_form.js`; `.js` under `js/` or `FM/js/`; `.css` under `css/` | `kind: code` — only `_form.js` may be **new**; the others are edit-only |
| excluded | `.cs .csproj .sln .ts .tsx .sql .dll .exe .html .cshtml .razor`, anything under `applibs*` | never |
| other | anything else | warned, not authored |

Why edit-only: the UI shell loads exactly three custom files, and a deployment bind-mounts a
workspace's file over each. Nothing inside the workspaces root makes the UI load a **new** file
under `js/` or `css/` (`knowledge/composition-specs.md` §5). A form's `_form.js` is read beside
its `_form.xml`, so a new one works.

A new configuration file must follow its route: component JSON under
`FM/_COMPONENTS/<Type>/` only where `route_means.py <Type>` says `json` — always, for the loader
folders `DataSource`, `Template` and `Endpoints` — and the five legacy
types — form, workflow, process, settings, view — always as XML. Existing files keep their
family. The route reads the runtime-parity table, so the check covers both schema families:
the modern JSON schemas and the legacy XSD grammars.

An **ultra** bundle is `plans/<stem>/index.md` plus phase files. `index.md` carries the same
header with `mode: ultra`, and holds every task line; the phase files hold the detail and never
a checkbox (`skills/dgf-plan/references/ULTRA-FORMAT.md`).

## The scripts

The spine's five are stdlib-only Python, except that `check_change.py` and `verify_gate.py` need
`lxml` and `jsonschema` to run the validators. Each takes `--verbose`. The loop's two are in
[The learning loop](#the-learning-loop).

| Script | Decides | Usage |
|---|---|---|
| `locate_plan.py` | The workspaces root (the nearest `.dgf-factory/config.yaml`), and the active plan: the branch's, else the one active plan, else the fast plan | `[--workspaces-root R] [--plans-dir D] [--fast-plan F] [--branch B] [--root-only \| --setup \| --list]` |
| `inventory_root.py` | Each workspace and its counts, what is not a workspace, git position, the knowledge stamp, validator dependencies | `--workspaces-root R` |
| `check_plan.py` | The header, tasks, the Commit Plan's groups (`plan-commits`), each file's class and workspace, the route of each new file, the ultra bundle's integrity, and (with `--overlap`) other active plans | `<plan> --workspaces-root R [--overlap]` |
| `check_change.py` | The branch's changed files against the plan, and the validators' findings against the merge-base | `--workspaces-root R --plan P (--base REF \| --changed S:PATH …) [--files …] [--skip-validators]` |
| `verify_gate.py` | The gate: finds the root and the plan, runs `check_plan.py`'s and `check_change.py`'s checks in-process, audits the tasks, computes the status, prints the one `dgf-gate-result` block | `[--workspaces-root R] [--plans-dir D] [--fast-plan F] [--branch B] [--plan P] [--base REF \| --changed S:PATH …] [--no-overlap] [--strict]` |

| Exit | `locate_plan.py` | `inventory_root.py` | `check_plan.py` | `check_change.py` | `verify_gate.py` |
|---|---|---|---|---|---|
| `0` | found | a root with a base workspace, validators ready | sound | inside the plan; nothing new | `pass` |
| `1` | `ROOT_NOT_SET_UP`, `ROOT_AMBIGUOUS`, `PLAN_NOT_FOUND`, `PLAN_AMBIGUOUS` | — | a plan defect (`PLAN_*`, including `PLAN_COMMITS_INVALID`) | `CHANGE_UNDECLARED_WORKSPACE`, `CHANGE_OUT_OF_SCOPE`, `CHANGE_CODE_UNPLANNED`, `CHANGE_CODE_FILE_NEW`, or a new blocking validator finding | `fail`: any of those, `GATE_TASK_UNCHECKED`, `GATE_STRICT_WARNING`, `GATE_PLAN_UNCONFIRMED` |
| `2` | `PLAN_FALLBACK` | `BASE_WORKSPACE_ABSENT`, `VALIDATOR_DEPS_MISSING` | `PLAN_OVERLAP`, `PARITY_PARTIAL`, `PLAN_NOT_AUTHORED`, `PLAN_COMMITS_MISSING` | an unplanned or untouched file, a new validator warning | `warn`: any of those, `GATE_CHECK_NOT_RUN` |
| `3` | usage | `ROOT_NO_WORKSPACE` | `PLAN_UNREADABLE`, `PLAN_FORMAT_UNSUPPORTED` | usage — including a `--files` or `--changed` path that leaves the root, and a `--base` that starts with `-` — an unreadable plan, `DEPENDENCY_MISSING` | could not run — `DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE`, an unreadable plan — or a validator could not read a file (`FAMILY_UNRESOLVED`, `SCHEMA_UNSELECTABLE`), with a `fail` block; a usage error, with no block |

The overlap check reads `.dgf-factory/plans/` at the tip of every local and remote-tracking
branch. It never fetches, so remote branches are as fresh as the last `git fetch`; `/dgf-plan`
offers one. Overlap is a warning, never a block ([ADR 0009](adr/0009-plan-ledger-scope.md)).
Another branch's plan is named, never quoted: `PLAN_OVERLAP_UNREADABLE` gives its path, its
refs and the line that failed to parse, because anyone who can push a branch writes that text,
and the model reads the script's output. A path or ref over 120 characters is cut.

## Change-relative gates

Real estates already carry errors: DGF's own samples raise hundreds of validator findings. A
gate that blocked on every finding in the root would fail every branch.
[ADR 0018](adr/0018-change-relative-gates.md) makes it block only on what the branch
introduced:

1. `check_change.py --base main` finds the merge-base of `HEAD` and `main`.
2. It writes the base tree into a temporary directory, blob by blob (`git ls-tree` +
   `git cat-file --batch` — never `git archive`, whose export attributes alter files).
3. It runs the same validators, over the same scope, at the working tree and at the base tree.
4. A finding at both is `INFO PRE_EXISTING`; one only at the base is `INFO FIXED`; every other
   finding keeps its code and its exit.

Findings are compared by code, root-relative file and message — not by line, so an edit above
a finding does not make it new — and as a multiset, so a second copy is new. Without git or a
merge-base the baseline is `NOT RUN` and every finding counts as new: stricter, never looser. A
writing skill without git brings its own, saved before its write (`--save-baseline`, `--baseline`;
[ADR 0025](adr/0025-saved-baseline-without-git.md)); the gate never does.

On a copy of DGF's samples, a branch that added one dead transition got exactly one new error
among 2552 pre-existing findings, in about 5 seconds for both runs.

`/dgf-implement` runs the check with `--files <the task's files>` after each task. That is a
fast pre-check and never the gate: only `/dgf-verify`'s whole-root run can pass one.

## The declared DGF version

Nothing in a workspaces root states which DGF release it runs, so `/dgf` asks and records it
as `dgf.version` ([ADR 0019](adr/0019-declared-dgf-version.md)). `unknown` is allowed and
stays a warning. When the declared version is newer than the knowledge base's stamp, `/dgf`
says the shipped facts were read at an older release and offers the DGF docs MCP's
`get_release_notes`. The version gate that compares it with a fact's `applies:` range is a
follow-up: no behavioural fact carries one yet.

## The gate block

`/dgf-verify` relays `verify_gate.py`'s output, which ends with one `dgf-gate-result` block and
nothing after it ([ADR 0022](adr/0022-gate-block-contract-revised.md)). The block is built by
`scripts/lib/gate_result.py`, the one builder every gate uses — the doctor's included:

- `schema_version`, `gate`, `status`, `blocking`, `blockers`, `warnings`, `affected_files`,
  `checks_run`, `schema_family`, `affected_components`, `affected_processes`, `suggested_next`.
- **The status is computed from two lists**: `fail` with any blocker, `warn` with any warning,
  `pass` otherwise; `blocking` is `true` only on `fail`. `blockers` holds only what blocks. A
  required check that did not run — `baseline` without a merge-base, `validators` without the
  dependencies, `frontend-tests` for a `kind: code` task — is a `not-run-<check>` warning.
- Each validator finding carries its file's `schema_family`, `json` or `xsd`, and the block counts
  the files the validators read per family.
- `affected_components` and `affected_processes` are the change's own footprint, in both
  families — not its blast radius, which is `/dgf-audit`'s.
- `--strict` promotes every new `WARN` line from the change check to a blocker.
- `suggested_next` names the command that fixes the first thing blocking: `/dgf-plan` for the
  plan, `/dgf-implement` for an unchecked task or a change outside the plan, `/dgf-fix` for a
  finding the branch introduced once the scope is clean, `/dgf-commit` on `pass` or `warn`.
- A field the gate did not compute is left out, never emitted empty.

The contract is `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`.

## The learning loop

The gate finds what the branch broke; the loop makes the next branch less likely to break it
([ADR 0024](adr/0024-learning-loop-revised.md)).

| Skill | Does | Scripts it runs | Writes |
|---|---|---|---|
| `/dgf-fix` | Fixes one problem **inside the active plan's scope**: reproduces it with a check, lets `check_change.py --skip-validators` decide the scope before any edit, makes the smallest fix, re-runs the check. With no plan it stops. `--record` writes a patch with no change | `locate_plan.py`, `check_plan.py`, `check_override.py`, `check_change.py`, `validate_config.py`, `route_means.py`, `check_patches.py` | the files the fix touches, inside the plan's scope; one patch |
| `/dgf-evolve` | Distils the new patches into skill-context rules; runs only when asked, asks before writing, reads no override of its own | `locate_plan.py --root-only`, `check_patches.py --cursor`, `check_override.py` | overrides, an evolution log, the cursor |

**A patch** is `patches/<YYYY-MM-DD-HH.mm>-<slug>.md`: a title, seven field bullets — `date`,
`plan`, `workspaces`, `files`, `findings`, `dgf_version`, `severity` — and five sections: Problem,
Root Cause, Solution, Prevention, Tags. The timestamp sorts patches by time; the slug keeps two
branches' fixes from colliding when they merge. A patch is never edited, and it is data: nothing in
it overrides a skill or a STOP. `findings: none` marks a problem no validator catches — a candidate
for a new one. The format is `skills/dgf-fix/references/PATCH-FORMAT.md`.

**An override** is `skill-context/<skill>/SKILL.md` in a fixed template — `# Project Rules for
/<skill>`, one `## Rules`, and `### <name>` rules each holding one `- source:` (the patches it came
from) and one `- rule:`. The format is `skills/dgf-evolve/references/OVERRIDE-FORMAT.md`.

**The cursor** is `evolutions/patch-cursor.json`, `{"processed": [<names>], "updated": …}`: a set
of names, one per line, not a high-water mark — branches merge patches into one ledger in any
order, and a mark would skip a patch dated before it but merged after it. A run for one skill marks a
patch processed only when it handled every point in it; a patch still holding a point for another
skill stays new.

**The limit.** An override may add rules and tighten checks. It never relaxes a STOP, an exit-code
row, the status a gate script computes, a Critical Rule or Artifact Ownership, and never makes a
skill install anything, skip a script, or write outside its own artifacts. Anyone who commits to the
estate can write an override, so ten skills — the five of the spine, `/dgf-fix` and the four
DGF-specific skills — run `check_override.py` before reading theirs, and `/dgf-evolve` runs it on every file it writes. The
check refuses what a script can see: a gate block, a flag other than `--strict` or `--verbose`, a
tool grant, an install or download, a history-rewriting git command, a path outside the root — read as
ASCII first, with invisible, control and look-alike characters refused outright, and quoted text
limited to the template's two lines. It
cannot see a relaxation in plain words, so a rule naming a word the limit protects is handed to the
skill's judgement, and the committed diff is reviewed.

| Exit | `check_patches.py` | `check_override.py` |
|---|---|---|
| `0` | every patch well-formed, or none | apply it — or `OVERRIDE: none` |
| `1` | a malformed patch: `PATCH_NAME_INVALID`, `PATCH_UNREADABLE`, `PATCH_FIELD_MISSING`, `PATCH_FIELD_INVALID`, `PATCH_SECTION_INVALID` — never read as a lesson, never marked processed | **refused**: `OVERRIDE_UNREADABLE`, `OVERRIDE_SHAPE`, `OVERRIDE_SOURCE_MISSING`, `OVERRIDE_FORBIDDEN` — the skill does not read it, and runs on its shipped rules |
| `2` | `PATCH_CURSOR_UNREADABLE` — every well-formed patch counts as new | `OVERRIDE_TOUCHES_LIMIT` — apply it, and judge each flagged rule |
| `3` | usage: no root, or a patch outside the patches directory | usage: no root, or a skill name that is not a plain name |

Both are stdlib-only, never write, and need no `config.yaml` — `/dgf` checks its override before
the config exists.

**The gate's new row.** `verify_gate.py` suggests `/dgf-fix` when every task is checked and the
change checks are clean but a validator reports a new error, or strict mode promotes a new validator
warning ([ADR 0022](adr/0022-gate-block-contract-revised.md) §9). An unchecked task or a change
outside the plan still goes to `/dgf-implement` first, and the reason adds "then <n> new blocking
finding(s) for /dgf-fix". The doctor never suggests `/dgf-fix`: a broken install is reinstalled, not
fixed in the estate.

## The DGF-specific skills

Four skills work on the estate's configuration itself ([ADR 0027](adr/0027-dgf-specific-skills-revised.md)).
Their read-only modes — inspect, validate, audit — run anywhere in a root. Their writing modes run
only inside the active plan, as `/dgf-fix` does: `locate_plan.py` finds the plan, `check_plan.py`
checks it, and `check_change.py --changed … --skip-validators` decides the scope **before** the write.
None of them ticks a checkbox — `/dgf-implement` owns the ledger — deletes a file, converts a file's
family, or emits a gate block. `/dgf-process` and `/dgf-model` confirm every write over the whole
root. Without git there is no merge-base, so the script saves a baseline first ([ADR
0025](adr/0025-saved-baseline-without-git.md)):

- `check_change.py --save-baseline` before the write keeps the root's findings, unjudged;
- `--baseline` after it settles against them exactly as the gate settles against a merge-base — an
  old finding is `INFO PRE_EXISTING`, and a new one keeps its exit.

The key is the gate's own (code, file, message), so a finding whose message the write changed reads
as new here as it would at the gate. An example is a `webasm` reference whose list of applications
now differs. The gate never takes a saved baseline.

| Skill | Does | Scripts it runs | Writes |
|---|---|---|---|
| `/dgf-component` | Inspects, validates or scaffolds a component — JSON under `FM/_COMPONENTS/`, or a legacy form, view, grid form or options file — in both families, parity-aware | `locate_plan.py --root-only`, `check_override.py`, `validate_config.py`, `resolve_components.py`, `route_means.py`, `audit_root.py --reach`, `validate_model.py` (forms), and the plan and scope scripts | one new component file per scaffold |
| `/dgf-process` | Inspects, validates, authors or modifies a process or workflow, XML always; runs the reach **before** a modify, and the whole-root change check after it | `locate_plan.py --root-only`, `check_override.py`, `validate_process.py`, `audit_root.py --reach`, `audit_root.py --skip-validators`, `route_means.py`, and the plan and scope scripts | `process.xml`, `_workflow.xml` |
| `/dgf-model` | Inspects, validates, adds or modifies an entity; names the database work a change needs, and never writes SQL | `locate_plan.py --root-only`, `check_override.py`, `validate_config.py`, `validate_model.py`, `audit_root.py --reach`, `route_means.py`, and the plan and scope scripts | an entity's `settings.xml` |
| `/dgf-audit` | The whole root's health, or a file's blast radius | `locate_plan.py --root-only`, `check_override.py`, `audit_root.py` | nothing |

**One writer per artifact.** Each writing skill writes only what it owns, and STOPs on anything
else, naming the owner:

| Artifact | Owner |
|---|---|
| `process`, `workflow` (shared or process-local) | `/dgf-process` |
| `settings` | `/dgf-model` |
| every JSON component under `FM/_COMPONENTS/`, and `form`, `table-view`, `lookup-view`, `grid-form`, `options` | `/dgf-component` |

`/dgf-implement` and `/dgf-fix` still write any of them for a plan task or a fix.

**Two scripts.** Both need `lxml` and `jsonschema`, and take `--verbose`:

| Script | Decides | Usage |
|---|---|---|
| `validate_model.py` | The references an entity's `settings.xml` and a `_form.xml` make — each resolved the way its loader resolves it — that `Table.InitFields` accepts an entity's key and fields, and that every bound cell of a form names a field. One of the runner's four validators, so the gate and the known-good run check the model | `[--workspaces-root R] (--all \| <settings.xml \| _form.xml>…)` |
| `audit_root.py` | The whole-root audit — validator counts over the root's configuration, the reference graph of each application, unresolved references no validator checks, unreached shared workflows, the role inventory — or the reach of named or changed files | `--workspaces-root R [--reach PATH… \| --base REF \| --changed S:PATH…] [--app NAME] [--skip-validators]` |

| Exit | `validate_model.py` | `audit_root.py` |
|---|---|---|
| `0` | every reference resolves, `Table.InitFields` accepts the entity's key and fields, and every bound cell names a field — as far as the checks ran: `NOT RUN: form-cells` when the form's entity `settings.xml` does not parse, `NOT RUN: entity-load` when the file holds a DTD or does not parse once decoded as the runtime decodes it | clean, or INFO only (`AUDIT_WORKFLOW_UNREACHED`, `AUDIT_REFERENCE_DYNAMIC`) |
| `1` | `MODEL_REFERENCE_UNRESOLVED` — a table or dialog the loader throws on, an empty one where it throws, a grid folder that exists without its file while the table has a `default` grid, or a missing view or grid that cannot be generated — `MODEL_ENTITY_UNLOADABLE` — `Table.InitFields` throws on the entity's key or fields — `MODEL_CELL_UNBOUND`, `XML_MALFORMED` | a validator `ERROR` in the root |
| `2` | `MODEL_REFERENCE_TEMPLATED` — the runtime generates the missing view or grid and writes it into the workspace — `MODEL_REFERENCE_APP_DEPENDENT`, `CASE_ONLY_MATCH` | `AUDIT_REFERENCE_UNRESOLVED`, `CASE_ONLY_MATCH`, `AUDIT_NARROWED` |
| `3` | usage, `SCHEMA_UNSELECTABLE`, `DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE` | usage, `AUDIT_REACH_NOT_ARTIFACT` — including a path that matches only in case — `DEPENDENCY_MISSING`, `KNOWLEDGE_TABLE`, `SCHEMA_UNSELECTABLE` for a vendored schema whose dialect the validators cannot read, `AUDIT_CHECK_FAILED` — a check raised, and the report so far says which — `--skip-validators` with a reach |

A JSON file outside every `FM/` is a draft: a validator's own call checks it by its `type`, but no
loader reads it, so the audit leaves it out of its validator run and says so in a `NOT RUN: drafts`
line.

**A model reference blocks only where its loader throws.** Which references there are, how each
resolves and what the runtime does when its target is missing are the `reference-edges` table in
`knowledge/reference-graph.md` §1, read from the engine's loaders. A table name is cleaned before
`BASE:` is tested, a dialog has no base path, and a missing view, grid or form is generated rather
than thrown on — except where the workspace makes that fail: a form or grid folder that exists
while the table has a `default` to copy, a view whose table has no `Text` field besides its key, a
form generated with no `default` whose table has a field without a `uimask`, or names and titles
the generated file pastes in, unescaped, that leave it unparsable (`knowledge/data-model.md` §3–§4).
`validate_model.py` blocks on those for views and grids. An entity whose own load throws is blocked
on its `settings.xml`, once; a reference into it still resolves, since its file is there. A workflow's form references are no
validator's yet: `audit_root.py` reports them, never as a gate. An empty name is a reference only where the row's `When empty` is
`throws`: an `extract` with neither `table` nor `dialog`, and a `slavegrid` with no `table`.

**Blast radius is `/dgf-audit`'s, and it is a report, not a gate.** The verify gate's
`affected_processes` stays the change's own footprint (ADR 0022 §6). `audit_root.py` builds one
reference graph per application — that application plus `webasm`, with a `webasm` file read as that
application reads it — and walks it forward from every process: along process actions,
`validationFlow`, MultiTask actions and `SubWorkflow` calls, to the forms those workflows invoke or
record through, their entities, and the data sources they name. An entity's references to other
entities are listed as referrers, not walked. Nothing is stored: the graph is rebuilt from the files
on each run.

**Its limits.** A static walk cannot see names assigned at run time (`_WORKFLOWNAME_`,
`_FORMNAME_`, `_TABLENAME_`), processes chosen from the database, open handlers, or entry points
outside processes — `_PROFILE` trees, sitemaps, `_form.xml` and view `WORKFLOW:` strings, JSON
`workflow` components. Every reach report ends with a `LIMIT:` line that says so, a chain through a
run-time name is flagged `AUDIT_REFERENCE_DYNAMIC`, and an unreached shared workflow is a
candidate, never proof of dead code. Roles are listed, never checked: nothing in the root declares
one (`knowledge/permissions.md` §1).

## Starting an application

`/dgf-scaffold` is the one command that runs before the pipeline has anything to run on. It creates a new
DGF application in an **empty folder**, and hands the new workspaces root to `/dgf`; every change after that is
brownfield work for `/dgf-plan` and `/dgf-implement` ([ADR 0026](adr/0026-authoring-entry-point-revised.md)
§1–§2, [ADR 0027](adr/0027-dgf-specific-skills-revised.md) §7). DGF ships no bootstrap template or generator,
so the skill generates the application itself, from templates this plugin ships, DGF-generic:

```text
empty folder + "an inspections app for two directorates: a permit register and an approval service, DGPass sign-in"
  0 empty?     design.py --empty-only                                 (script)
  1 design     the model turns the request into docs/application.json
  2 check      names, references, data model, SQL types; what is open; every default   (design.py)
  3 survey     ask only what is open; back to 2
  4 confirm    the defaults (DEFAULT: lines) and the tree (generate.py --dry-run)
  5 generate   solution + database + workspaces + artefacts, from shipped templates   (generate.py)
  6 check      secrets, structure, routes, and the validators over the generated files (generate.py --check)
  7 report     how to run it, every value to fill in, next: /dgf <folder>/workspaces
```

It does nothing in a folder that is not empty (only a `.git` folder and `docs/application.json` are allowed),
and it adds nothing to an existing application. It reads and writes no `.dgf-factory/`, checks no override
and reads no patches, since there is no root and no plan.

**What is generated.** One thin host project per API, on the `DGF.API` package, with an `appsettings.json` and one
`appsettings.<Deployment>.json` per deployment; an SDK-style `Microsoft.Build.Sql` database project with the
application's tables, an `aspnet_Applications` row per instance and the roles; the workspaces, each with the
minimum a new application needs (a route table whose landing route is not `/`, a `/login` route and page, the
application map, a profile tree per router) and a `register`, `service` or `page` pattern per module; a compose
stack with traefik, SQL Server, Redis and Seq; and the documentation. The design file stays in `docs/`, and the
generator run from it into a new empty folder reproduces the application.

**Never literal.** A secret, a host, a feed, a registry and an image tag are each a `${VAR}`, declared in
`docker/.env.example` and `docs/configuration.md`. The application does not run until they are filled, and until
four things DGF pins no consumer artifact for are supplied: the base workspace, the image that publishes the
framework's database baseline, the DGF UI image, and a NuGet feed serving `DGF.API`.

**Two scripts and a check.** Both scripts are slice-local (`skills/dgf-scaffold/scripts/`), need neither
`lxml` nor `jsonschema` (only `--check` runs the validators, which do), and take `--verbose`:

| Script | Decides | Usage |
|---|---|---|
| `design.py` | The folder is empty; the design's names, references, options, data model and column types; what is open; every default | `--folder DIR [--empty-only] [--knowledge-dir DIR]` |
| `generate.py` | Renders the design into the folder — everything in memory first, then staged and moved into place, and undone on any failure; `--dry-run` prints the targets; `--check` is the post-generation check | `--folder DIR [--dry-run \| --check]` |

| Exit | `design.py` | `generate.py` |
|---|---|---|
| `0` | complete: nothing is open, nothing conflicts | written, planned, or sound |
| `1` | a conflict: `SCAFFOLD_DIR_NOT_EMPTY`, `SCAFFOLD_NAME_INVALID`, `SCAFFOLD_OPTION_INVALID`, `SCAFFOLD_REFERENCE_INVALID`, `SCAFFOLD_MODEL_INVALID`, `SCAFFOLD_SQL_TYPE_UNKNOWN` | `SCAFFOLD_TARGET_EXISTS`; or, from `--check`, `SCAFFOLD_LITERAL_SECRET`, `SCAFFOLD_VAR_UNDECLARED`, `SCAFFOLD_STRUCTURE_INVALID`, `SCAFFOLD_ROUTE_UNRESOLVED`, `SCAFFOLD_VALIDATION_FAILED` |
| `2` | values are open: one `SCAFFOLD_ASK` each, and a `DEFAULT:` line per default | — |
| `3` | `SCAFFOLD_DESIGN_UNREADABLE`, or usage | `SCAFFOLD_DESIGN_INCOMPLETE`, `SCAFFOLD_TEMPLATE_MISSING`, `SCAFFOLD_WRITE_FAILED`, `DEPENDENCY_MISSING` from `--check` |

**The post-generation check decides; the skill relays it.** In order: the secrets and variables (every value of a
key that names a secret is one `${VAR}`, every variable used is declared in both places, every placeholder in an
`appsettings` file is set by the compose service that runs it); the structure of the files no validator reads
(the application maps, the profile trees and their node files, against the `workspace-minimum` table); the routes
(every route names a page that exists, by exact case; the landing route is first and is not `/`; `/login` has a
login page); and `validate_config.py`, `resolve_components.py` and `validate_model.py` — and `validate_process.py`
when there is a process — over the generated workspaces, never over the copied base and never with `--all`. INFO
is allowed, and so is `NO_SCHEMA` on a `sitemap.json`, which every site map gets. A failed check is a generator
defect: the skill stops and quotes it, and never patches the output.

**What it does not know.** The solution files — C#, SQL, compose, MSBuild — pass no validator; they are held only
by the check and, where `dotnet` and Docker exist, by a real build. The instance model is the framework's own: an
instance is a `WorkspaceName` with its own `aspnet_Applications` row, and isolation between instances is by the
`ApplicationId` column alone. See [DESIGN-FORMAT.md](../skills/dgf-scaffold/references/DESIGN-FORMAT.md) for the
design file, and `knowledge/application-layout.md` for the framework facts every template rests on.

## See Also

- [Getting Started](getting-started.md#trying-the-spine) — running the spine's scripts on a copy of DGF's samples, and trying the loop
- [Skill Authoring](skill-authoring.md#reading-a-validators-output) — the output lines each script prints
- [Decision Records](adr/README.md) — ADRs 0009, 0010, 0017, 0018, 0019 and 0022, which shape the spine, 0024, which decides the loop, and 0027, which decides the DGF-specific skills and designs `/dgf-scaffold`, with 0026 beside it for the scope
