[← Getting Started](getting-started.md) · [Back to README](../README.md) · [Architecture →](architecture.md)

# The Pipeline Spine

Five skills take a change to a DGF estate from a request to a commit. Every decision a script
can make is made by a script; the skills decide only what needs judgement.

```text
/dgf  ──►  /dgf-plan  ──►  /dgf-implement  ──►  /dgf-verify  ──►  /dgf-commit
 set up     plan the       compose, task by     the gate: plan,    conventional
 the root   change         task, and validate   change, baseline   commits
```

The unit of work is the **whole workspaces root**, not one workspace
([ADR 0004](adr/0004-authoring-entry-point.md)). A change in `webasm` is live in every
application, and a change in one file can break a file it never touched, so the gate always
looks at the whole root.

## The five skills

| Skill | Does | Scripts it runs | Writes |
|---|---|---|---|
| `/dgf` | Finds the root, inventories it, asks for the estate's DGF version | `locate_plan.py --root-only`, `inventory_root.py` | `.dgf-factory/config.yaml`, `.dgf-factory/DESCRIPTION.md` |
| `/dgf-plan` | Plans a change — fast, full or ultra — on its own branch | `locate_plan.py --root-only`, `inventory_root.py`, `route_means.py`, `check_plan.py --overlap` | the plan |
| `/dgf-implement` | Executes the plan one task at a time, validating each | `locate_plan.py`, `check_plan.py`, `validate_config.py`, `route_means.py`, `check_change.py --files` | the task's workspace files, and its checkbox |
| `/dgf-verify` | The gate: tasks done, change inside the plan, no new finding across the root | `locate_plan.py`, `inventory_root.py`, `verify_gate.py` | nothing — it relays the `dgf-gate-result` block `verify_gate.py` computes |
| `/dgf-commit` | Conventional commits scoped by workspace, following the plan's Commit Plan | `locate_plan.py`, `check_change.py --skip-validators` | git history, after confirmation |

`/dgf-doctor` sits beside them: it checks that the plugin itself is installed correctly.

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
| `skill-context/<skill>/SKILL.md` | a person, for now | the matching skill, which applies it as an override that may only tighten: it never relaxes a STOP, an exit-code row, the gate's status table, a Critical Rule or Artifact Ownership, and the skill names the override it read |
| `patches/` | milestone 11 (`/dgf-fix`) | `/dgf-implement`, read if present |

`config.yaml` is written from `skills/dgf/references/config-template.yaml`:

```yaml
dgf:
  version: "1.1.15"          # the DGF version this estate runs, or "unknown" (ADR 0019)
language: {ui: en, artifacts: en}
paths:
  plan: .dgf-factory/PLAN.md
  plans: .dgf-factory/plans/
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

All five are stdlib-only Python, except that `check_change.py` and `verify_gate.py` need `lxml`
and `jsonschema` to run the validators. Each takes `--verbose`.

| Script | Decides | Usage |
|---|---|---|
| `locate_plan.py` | The workspaces root (the nearest `.dgf-factory/config.yaml`), and the active plan: the branch's, else the one active plan, else the fast plan | `[--workspaces-root R] [--plans-dir D] [--fast-plan F] [--branch B] [--root-only \| --list]` |
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
merge-base the baseline is `NOT RUN` and every finding counts as new: stricter, never looser.

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
- A field the gate did not compute is left out, never emitted empty.

The contract is `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`.

## See Also

- [Getting Started](getting-started.md#trying-the-spine) — running the spine's scripts on a copy of DGF's samples
- [Skill Authoring](skill-authoring.md#reading-a-validators-output) — the output lines each script prints
- [Decision Records](adr/README.md) — ADRs 0009, 0010, 0017, 0018, 0019 and 0020, which shape the spine
