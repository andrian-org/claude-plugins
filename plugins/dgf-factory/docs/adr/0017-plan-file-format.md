---
id: 0017
title: "The plan file: a frontmatter header, per-task kind, reason and files, and edit-only global scripts"
status: accepted
date: 2026-09-25
deciders: [Andrian Mamei]
supersedes: []
tags: [planning, plan-format, scope, implement]
---

# 0017 — The plan file: a frontmatter header, per-task kind, reason and files, and edit-only global scripts

**Status: accepted** (2026-09-25, Andrian Mamei). [ADR 0009](0009-plan-ledger-scope.md) and
[ADR 0010](0010-dgf-implement-scope.md) left the plan-header format, per-task `kind`, the status of
the `applibs*` folders and the places custom code may go to roadmap milestone 9 ("Pipeline Spine").
Milestone 9 writes `/dgf-plan`, `/dgf-implement`, `/dgf-verify` and `/dgf-commit`, which all read
the plan, so the format is fixed before any of them is written.

## Context

Read on **2026-09-25** from this repository (`develop` at `a3e02a3`) and from the DGF repository at
`aa1d5c4c2` (`develop`). DGF paths are relative to the DGF repository root.

**What the earlier decisions require of the plan.**

- ADR 0009 §Decision (`docs/adr/0009-plan-ledger-scope.md:48-71`): every plan header carries a
  mandatory, never-empty `affects_workspaces` list, shown there as YAML
  (`affects_workspaces: [zims, webasm]`). A plan may span workspaces. Ids stay `slug`, and
  `sequential` is not permitted. A deterministic overlap check, run by `/dgf-plan` and `/dgf-verify`,
  warns (exit `2`, never `1`), and `webasm` intersects every plan. `/dgf-verify` fails (exit `1`)
  when the diff reaches an undeclared workspace. Its follow-ups (`:95-98`) defer the header format to
  milestone 9 and leave open whether `applibs*` count as workspaces.
- ADR 0010 §1–§3 (`docs/adr/0010-dgf-implement-scope.md:89-141`): the order of means is JSON under
  `FM/_COMPONENTS/`, then legacy XML, then a little JavaScript or CSS as `kind: code` with a
  `reason` that names the configuration route tried and cites the component doc, the schema or the
  `EventBase` verb list (`:122-125`). Code goes in `js/`, `css/` or a form's `_form.js` (`:126-128`).
  C#, TypeScript, Angular, SQL and framework or plugin source are out of scope: `/dgf-plan` writes no
  such task and `/dgf-implement` stops with exit `1` (`:136-141`). An existing artifact is edited in
  the family it is in (`:115-118`). Its follow-up to verify how `js/` and `css/` reach the UI is open
  (`:212-214`).
- [ADR 0005](0005-default-team-rules.md) rules 2 and 3 (`docs/adr/0005-default-team-rules.md:47-66`)
  are *gate* rules: behaviour must not be smuggled into `FM/` as script, and a base-workspace edit
  needs "explicit justification … named in the plan". Rule 3 "needs two inputs: the changed-file set
  *and* the plan".

**What the inherited pipeline does.** AI Factory's plan template
(`.claude/skills/aif-plan/references/TASK-FORMAT.md:31-32`) puts `Branch:` and `Created:` on prose
lines, and its tasks are checkbox lines with an optional `(depends on N, M)` suffix (`:66-75`). An
ultra bundle is marked by an HTML comment, `<!-- aif:plan-mode:ultra -->`
(`.claude/skills/aif-plan/references/ULTRA-FORMAT.md:33, 197`). `/aif-implement`, `/aif-verify` and
`/aif-commit` each repeat the same branch-to-filename discovery algorithm in prose. Nothing in the
format is machine-checked.

**What this repository already provides.** `scripts/lib/workspace.py:28` fixes
`BASE_WORKSPACE = "webasm"`, and `applications(root)` (`:52-62`) returns every directory under the
root with an exact-case `FM/`, except `webasm`. `scripts/route_means.py:61-95` (`route()`) answers
`json` or `xml` for a ComponentType member or a legacy artifact type, and exit `3` (`ROUTE_NO_ROW`)
for neither; it never answers `code`.

**What the `applibs*` folders are.** `src/samples/workspaces/readme.md:12`: "`applibs*/` | plugin
assemblies (`CustomAssembliesPath`), per consumer". All five sample folders (`applibs`,
`applibs-ecouncils`, `applibs-lm`, `applibs-zims`, `applibs-zma`) hold only `.dll` files — 11, 12,
7, 11 and 10 — and none has an `FM/`. `CustomAssembliesPath` is declared at
`src/Core/DGF.Kernel/Configuration/ApplicationConfig.cs:8` and read through the
`ApplicationConfig:CustomAssembliesPath` key at `src/Core/DGF.Kernel/Extensions/AssemblyLoader.cs:13`.
`src/Core/DGF.Kernel/WorkspaceSettings.cs` never mentions them. [ADR 0004](0004-authoring-entry-point.md)
§3 (`docs/adr/0004-authoring-entry-point.md:85-88`) includes "the `applibs*` libraries" in the unit of
work; it does not say they are workspaces.

**How custom script and style reach the UI.**

- The UI shell loads exactly three custom files at start-up:
  `src/DGF.UI/src/app/components/app/app.component.ts:191-207` (`setUpCustomFiles`) injects
  `assets/js/formhelper.js`, `assets/js/formshared.js` and `assets/styles/custom.css`. The shell
  ships its own default copy of each under `src/DGF.UI/src/assets/`, and `src/DGF.UI/angular.json:26-33`
  copies `src/assets` and a PDF viewer's assets — nothing from a workspace.
- A deployment replaces those defaults with a bind-mount.
  `src/samples/DGF.Compose/docker-compose.zims.yml:58-59` maps `workspaces/zims/js/formhelper.js`
  and `js/forms.shared.js` onto the two script paths; `:61`, commented out, maps a `custom.css` from
  outside the workspace. `docker-compose.ecouncil.yml:62-65` maps `webasm/FM/js/formhelper.js`,
  `ecouncil/js/ui.forms.shared.js`, and a `custom.css` from outside the workspaces root. The mapping
  lives in deployment configuration, outside the workspaces root, and names one file per target
  path.
- A form's own script is read by `src/Core/DGF.Domain/Data/Form/FormManager.cs:183-196`
  (`GetFormScriptContent`): `_form.js` beside the form when no `scriptPath` is given, otherwise the
  `scriptPath` joined to `WorkspaceSettings.WorkspaceRootPath`. So a **new** `_form.js` is loaded
  with no other change.
- `src/DGF.API/ConfigureServices.cs:365-383` (re-read 2026-09-25) serves `/application` from the
  workspace root and `/webasm` from the base workspace root as static files, for content a form links
  to. The shell's three files do not come from these mounts.

So nothing inside a workspaces root makes the UI load a **new** file under `js/`, `FM/js/` or
`css/`. Editing one of the files a deployment already mounts does reach the UI.

## Decision

**A plan is a Markdown file with a flat YAML frontmatter header and checkbox tasks, each carrying
`kind`, an optional or required `reason`, and the files it touches, relative to the workspaces root.
Three scripts decide everything about a plan that can be decided. `applibs*` folders are not
workspaces, and `kind: code` may create a form's `_form.js` but only edit an existing file under
`js/`, `FM/js/` or `css/`.**

### 1. The header

The header is YAML frontmatter restricted to a flat subset a standard-library parser reads exactly:
`key: scalar`, `key: "quoted scalar"` (with `\"` escapes) and `key: [a, b]` flow lists of bare or
quoted items, with blank lines and `#` comments outside quotes. Anything else — a nested map, a block
list, a multi-line scalar — is `PLAN_UNREADABLE` (exit `3`) with its line number.

```yaml
---
plan_format: 1
mode: full                          # fast | full | ultra
branch: feature/zims-inspection-fee # "none" only for a fast plan made off-branch
created: 2026-09-25
affects_workspaces: [zims, webasm]  # workspace directory names under the root; never empty
base_workspace_reason: "The fee DataSource is shared by every application's payment page"
---
```

- The keys are exactly `plan_format`, `mode`, `branch`, `created`, `affects_workspaces` and
  `base_workspace_reason`, plus `archived`, which is reserved for a future archive skill and is
  accepted and ignored. Any other key is `PLAN_FIELD_INVALID`.
- `plan_format` is `1`. Any other value is `PLAN_FORMAT_UNSUPPORTED` (exit `3`), so a later format
  change is detected rather than misread.
- `base_workspace_reason` is required when, and only when, `webasm` is listed. It is ADR 0005 rule
  3's "justification named in the plan".
- An ultra bundle carries the same frontmatter in its `index.md`, with `mode: ultra`. That field is
  the bundle marker; there is no HTML-comment marker.
- The body sections, in order, are `# Implementation Plan: <name>`, `## Original Request` (verbatim,
  when the user gave one), `## Scope`, `## Affected Artifacts`, `## Commit Plan` (five or more tasks),
  `## Tasks` and `## Risks`. Only `## Tasks` and, for ultra, `## Phase Index` are read by a script.

### 2. Tasks and their fields

Tasks are AI Factory's checkbox lines, each followed by indented field bullets:

```markdown
## Tasks

### Phase 1: Fee data
- [ ] Task 1: Add the inspection-fee DataSource
  - kind: config
  - files: zims/FM/_COMPONENTS/DataSource/InspectionFee.json
- [ ] Task 2: Hide the fee panel until the gateway confirms payment (depends on 1)
  - kind: code
  - reason: No EventBase verb reads the gateway callback (knowledge/composition-specs.md §3.1)
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.js
```

- `Task N:` ids are unique integers. `(depends on N, M)` names existing ids.
- `kind:` is `config` or `code`, and it is mandatory on every task.
- `reason:` is mandatory for `kind: code` and informational for `kind: config`.
- `files:` is a comma-separated list of the files the task creates or edits, relative to the
  workspaces root, with `/` separators, whose first segment is a workspace name. `deletes:` lists the
  files it removes. A task has at least one of the two.
- In an ultra bundle the task lines and their fields live **only in `index.md`**; the phase files
  hold the detail, and `index.md` stays the single progress ledger.

### 3. File classes

Every path a plan names, and every path a branch changes under the root, is in exactly one class:

| class | rule | in a plan task | in a branch diff |
|---|---|---|---|
| **config** | under `<ws>/FM/`, extension `.json` or `.xml` | `kind: config` only | checked by the validators |
| **code** | a row of the `code-places` table in `knowledge/composition-specs.md` §5: a form's `_form.js`, a `.js` under `<ws>/js/` or `<ws>/FM/js/`, a `.css` under `<ws>/css/` | `kind: code` only | must be listed by a `kind: code` task |
| **excluded** | extension `.cs .csproj .sln .ts .tsx .sql .dll .exe .html .cshtml .razor`, or anything under an `applibs*` folder | never | blocks |
| **other** | anything else in a workspace: images, templates, readmes | warned, not authored | warned |

- Which folders load a script is a **DGF fact**, so the scripts read it from the `code-places`
  machine-read table, never from a constant.
- The excluded list is **this plugin's policy** — ADR 0010 §3 restated as extensions — so it is a
  constant in the plan library.
- `kind: code` may **create** only a form's `_form.js`, because `GetFormScriptContent` loads a new
  one with no other change. It may **edit** an existing file under `js/`, `FM/js/` or `css/`, and it
  may never create one there, because nothing inside the workspaces root makes the UI load a new
  file (§Context). A new global script needs deployment work outside this plugin.
- Changes under `<root>/.dgf-factory/` are the pipeline's own artifacts and every check ignores them.

### 4. `applibs*` folders are not workspaces

A directory under the root is a workspace when it has an exact-case `FM/`. `applibs*` folders hold
plugin assemblies and no `FM/`, so they never appear in `affects_workspaces`, and a change under one
is out of scope (ADR 0010 §3). A plan that names one fails `PLAN_UNKNOWN_WORKSPACE` with a message
saying it is a plugin-assembly folder. ADR 0004 §3's scope still reads them: they are in the root,
just never authored.

### 5. Active plans and the overlap sources

- An **active** plan is one that parses and has at least one unchecked task.
- The overlap check scans the working tree and the tip of every ref under `refs/heads/` and
  `refs/remotes/`, reading `.dgf-factory/plans/*.md`, `.dgf-factory/plans/*/index.md` and
  `.dgf-factory/PLAN.md` at each tip through `git ls-tree` and `git show`. A blob seen on several
  refs is read once. It excludes the plan under check — the same path in the working tree and at any
  ref whose name ends in its `branch` — and every plan with no unchecked task.
- The check **never fetches**. Its report says how many refs it scanned and that remote refs are as
  fresh as the last fetch. `/dgf-plan` offers the fetch; the script does not run it.
- Each overlap is one `PLAN_OVERLAP` warning (exit `2`) naming the other plan, its ref and the shared
  workspaces. A plan on another ref that does not parse is `PLAN_OVERLAP_UNREADABLE`, reported and
  skipped.

### 6. Which script decides what

| script | decides | reads |
|---|---|---|
| `scripts/locate_plan.py` | the workspaces root (the nearest `.dgf-factory/config.yaml`), and the active plan by branch, then a lone plan, then the fast plan | the file system, `git branch --show-current` |
| `scripts/check_plan.py` | the header, the tasks, each file's class and workspace, the route of each **new** file, and the overlap | the plan, the root, `route_means.route()`, the `code-places`, `legacy-artifacts` and `component-folders` tables, git refs |
| `scripts/check_change.py` | the branch's changed files against the plan: scope, means, planned files, and the validators' findings relative to the merge-base ([ADR 0018](0018-change-relative-gates.md)) | the plan, `git diff`, the validators |

- **Existing files are not routed.** ADR 0010 §1 edits an existing artifact in its own family, so the
  route check applies to files that do not exist yet.
- **`PLAN_ROUTE_UNKNOWN` is exit `1`, while `route_means.py` returns `3` for the same condition** —
  a folder or name with no route. A plan is an artifact its planner can fix, so a new file under a
  folder with no route is a defect in the plan. `route_means.py` is asked a question it cannot
  answer, which is a usage error.
- The skills read `.dgf-factory/config.yaml` and pass its values to the scripts as arguments. The
  scripts never read the config: the standard library has no YAML parser, and a validator must not
  guess a key.

### 7. Identifiers

Plan ids stay `slug` (ADR 0009). The file stem of a full plan or an ultra directory is its `branch`
with every `/` replaced by `-`; a mismatch is `PLAN_BRANCH_MISMATCH`. Filenames carry no workspace.

## Alternatives considered

- **Prose header lines, as AI Factory writes them** (`Branch:`, `Created:`). Rejected: a list value
  such as `affects_workspaces` has no prose form a script reads without guessing, and ADR 0009 already
  showed the field as YAML.
- **A YAML block per task.** Rejected: a stdlib parser would then need nested maps, and the checkbox
  line that AI Factory's executor already updates would sit apart from its fields.
- **`kind` per phase instead of per task.** Rejected: one code task inside a configuration phase
  would make the whole phase `code`, and ADR 0010 §2 asks for a reason per change.
- **Allow new files under `js/`, `FM/js/` and `css/`.** Rejected: nothing in the workspaces root
  makes the UI load them (§Context), so the plan would pass and the feature would not work.
- **Allow code only in `_form.js`.** Rejected: estates do edit their global scripts — both sample
  deployments mount workspace files onto the shell's script paths — and forbidding the edit would push
  that work outside the plan.
- **Treat `applibs*` as workspaces.** Rejected: they hold `.dll` files and no `FM/`, and nothing in
  them is configuration this plugin composes.
- **Check overlap on the working tree only.** Rejected: it cannot see plans on unmerged branches,
  which are the plans ADR 0009's check exists to reveal.
- **Fetch before scanning.** Rejected: validators make no network calls
  (`.ai-factory/rules/base.md` §Determinism). A stale scan is reported as such instead.

## Consequences

### Positive

- Every field a gate needs — scope, means, reason, files, base-workspace justification — is in the
  plan and machine-checked before implementation starts.
- Plan discovery is one script instead of four prose copies, so the four skills cannot drift apart.
- A new global script that would never load is refused at plan time, not found in production.
- ADR 0009's `applibs*` question and ADR 0010's code-place question are closed with evidence.

### Negative

- The plan grammar is stricter than YAML. A hand edit in richer YAML becomes `PLAN_UNREADABLE`, and
  a planner has to learn the subset.
- Remote-tracking refs are as fresh as the last fetch, so a plan pushed since then is invisible to the
  overlap check.
- A feature that needs a new global script needs deployment work — a bind-mount — that this plugin
  cannot plan or verify.
- `scriptPath` is left unused: a form that names a script elsewhere in the workspace root cannot be
  planned, because the attribute that declares it has not been read.
- The excluded-extension list is policy, and an extension it misses is classed as *other* and only
  warned.

### Follow-ups

- Find the attribute that declares a form's `scriptPath`, and decide whether a new file it names is
  permissible.
- Decide whether files under `FM/` that are neither JSON nor XML (templates) count as configuration.
- ADR 0009's plan-header and `applibs*` follow-ups and ADR 0010's code-place follow-up are closed by
  §1–§4. Those ADRs are not edited: follow-ups are not decisions, and the contract permits only
  errata.
