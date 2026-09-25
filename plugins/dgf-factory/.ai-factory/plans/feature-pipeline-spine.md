# Implementation Plan: Pipeline Spine

Branch: feature/pipeline-spine
Created: 2026-09-25
Refined: 2026-09-25 — `/aif-improve`: base tree read blob by blob, not through `git archive`; lazy `lxml` import in the
runner; route-check folder rules; `code-places` allowed values; YAML-safe skill frontmatter checked by the doctor;
setup commit without a plan; a skill-contract test; dependencies of Tasks 10 and 12 corrected
Base: `develop` at `a3e02a3`. `config.yaml` names `main` as `git.base_branch`, but `main` (`0e28010`) is 44
commits behind `develop` and lacks milestones 6–8 (manifest, doctor, knowledge base, validators, ADRs 0006–0016),
which this plan builds on. The branch is cut from `develop` and merges back into it, as milestone 8's did.

## Original Request

**Pipeline Spine** — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit` with DGF domain content over the AI Factory step structure. The plan header carries ADR 0009's `affects_workspaces` and ADR 0010's per-task `kind: config | code` with a `reason`. `/dgf-implement` composes modern JSON under `FM/_COMPONENTS/` first, legacy XML only where no JSON alternative exists, and a little JS/CSS only for `kind: code` tasks ([ADR 0009](../docs/adr/0009-plan-ledger-scope.md), [ADR 0010](../docs/adr/0010-dgf-implement-scope.md), both accepted 2026-09-23)

## Settings

- **Testing: yes.** A stdlib `unittest` suite under `tests/` for every new script and library module, run from the
  plugin root with `python3 -m unittest discover -s tests -t .` (prefer `.venv/bin/python` when it exists). Every
  new blocking or exit-3 finding code gets a known-bad fixture under `tests/fixtures/known-bad/`, per the corpus
  contract in `tests/test_known_bad.py` (E10). Tests that need `git` skip when it is absent; tests that need `lxml`
  or `jsonschema` skip through `helpers.have_dependencies()`.
- **Logging: verbose.** No logging framework (`.ai-factory/rules/base.md` §Logging). Every new script accepts
  `--verbose` and honours `DEBUG=1` / `LOG_LEVEL=debug` through `lib.report.set_verbose()` / `report.debug()`.
  Trace lines are `DEBUG [<module>.<function>] <message> key=value …` on **stderr**; report lines go to **stdout**;
  usage errors go through the single `report.fail(code, message)` path. Each skill tells the user to re-run a
  failing script with `--verbose`.
- **Docs: yes.** A mandatory documentation checkpoint at completion, run through `/aif-docs` (Task 19).
- **Decisions taken while planning** (Andrian Mamei, 2026-09-25; recorded as accepted ADRs in Phase 1):
  - **D1: a gate blocks on what the branch introduced.** Validators run on the working tree and on the merge-base
    tree. A finding also present at the merge-base is reported as pre-existing and never blocks (→ ADR 0018).
  - **D2: `kind: code` may create or edit a form's `_form.js`, and edit, but never create, a file already under a
    workspace's `js/`, `FM/js/` or `css/`.** Nothing inside the workspaces root loads a new file there (E14–E15)
    (→ ADR 0017).
  - **D3: `/dgf-plan` ships all three modes** — fast, full and ultra — so the header and task format is defined
    once for both plan shapes (→ ADR 0017).
  - **D4: `/dgf` asks for the estate's DGF version and records it** in `.dgf-factory/config.yaml`. `unknown` is
    allowed and reported as a warning. The version gate itself waits, because no knowledge fact carries an
    `applies:` range yet (E17) (→ ADR 0019).
- **Decisions the planner took from evidence** (recorded in the same ADRs; reverse any at review):
  - **D5: `applibs*` are not workspaces.** They hold plugin assemblies (`.dll`) and no `FM/` (E13), so they never
    appear in `affects_workspaces`, and a change under them is out of scope (ADR 0010 §3). This closes ADR 0009's
    open follow-up (→ ADR 0017).
  - **D6: the overlap check scans the working tree and every local and remote-tracking branch tip**, without
    fetching. An *active* plan is one that parses and has at least one unchecked task (→ ADR 0017).
  - **D7: milestone 9's `/dgf-verify` gate block carries only AI Factory's base fields.** `schema_family`,
    `checks_run`, `affected_components` and `affected_processes` are milestone 10 ("Gate Contract Wired"), as is
    `scripts/lib/gate_result.py` (DD11).
- **Scope.** Five skills, the scripts they need to stay deterministic, three ADRs, two knowledge facts, doctor
  updates, and documentation. **Out of scope:** the gate-block builder and its DGF-specific fields (milestone 10),
  `/dgf-fix` and `/dgf-evolve` (milestone 11), `/dgf-improve`, `/dgf-roadmap`, `/dgf-explore` and every other skill,
  subagents and worktree parallelism (milestone 13), Handoff integration (none is planned), and the DGF version
  gate itself (ADR 0013 §4, first table).

## Roadmap Linkage

Milestone: "Pipeline Spine"
Rationale: This plan implements the milestone as written, and it closes the follow-ups ADRs 0009, 0010 and 0013
left for it: the plan-header format, whether `applibs*` count as workspaces, where custom JS and CSS may go, and
how the pipeline learns an estate's DGF version.

## Task Ledger Note

The checkbox list under `## Tasks` is the **single** progress ledger. `/aif-implement` updates the checkboxes here
and nowhere else.

## Evidence Base

Read on 2026-09-25 from this repository (`develop` at `a3e02a3`) and from the DGF repository at `aa1d5c4c2`
(`develop`). DGF paths are relative to the DGF root. This is evidence for maintainers; **no DGF path below may be
copied into a shipped file** (ADR 0012). Shipped files cite `knowledge/`, a DGF docs MCP call, or a type name.

**This repository**

- **E1 — ADR 0009's decision.** `affects_workspaces` is mandatory in every plan header and never empty. A plan may
  span workspaces. Ids stay `slug`, and `sequential` is not permitted. A deterministic overlap check, run by
  `/dgf-plan` and `/dgf-verify`, warns (exit `2`, never `1`), and `webasm` intersects every plan. `/dgf-verify`
  fails (exit `1`) when the diff reaches an undeclared workspace (`docs/adr/0009-plan-ledger-scope.md:48-71`). Its
  follow-ups defer the header format to milestone 9 and leave `applibs*` open (`:95-98`).
- **E2 — ADR 0010's decision.** The order of means is JSON under `FM/_COMPONENTS/`, then legacy XML, then a little
  JS/CSS as `kind: code` with a `reason` (`docs/adr/0010-dgf-implement-scope.md:89-118`). The reason names the
  configuration route that was tried and cites the component doc, the schema or the `EventBase` verb list
  (`:122-125`). Code goes in `js/`, `css/` or a form's `_form.js`, and CSS reaches a component through `CssClass`
  (`:126-128`). C#, TypeScript, Angular, SQL and framework or plugin source are out of scope: `/dgf-plan` writes no
  such task, and `/dgf-implement` stops with exit `1` (`:136-141`). An existing artifact is edited in the family it
  is in, and a migration is its own task (`:115-118`). The follow-up to verify how `js/` and `css/` reach the UI is
  open (`:212-214`).
- **E3 — ADR 0004's scope.** The unit of work is the whole workspaces root, and `.dgf-factory/` lives once at that
  root. A narrowed run is never sufficient to pass a gate (`docs/adr/0004-authoring-entry-point.md:85-100`).
- **E4 — ADR 0005's rules.** Rule 1 (XML-always for the five legacy types) is enforced by *script*. Rule 2 (no
  behaviour smuggled into `FM/` as script) and rule 3 (a base-workspace edit needs a justification named in the plan
  and verification against every consumer) are enforced by *gate* (`docs/adr/0005-default-team-rules.md:47-66`).
- **E5 — `scripts/route_means.py`.** `route_means.py <name> [--verbose]`: `<name>` is a ComponentType member or a
  legacy artifact type, in any case. It prints `ROUTE: json|xml <where> — <reason>`, and exits `0`, `2` (◐) or `3`
  (`ROUTE_NO_ROW`). It never answers `code` (`scripts/route_means.py:1-27`, `route()` at `:61-95`).
- **E6 — `scripts/lib/workspace.py`.** `BASE_WORKSPACE = "webasm"`. `applications(root)` is every directory under
  the root with an exact-case `FM/`, except `webasm`, so `applibs*` (no `FM/`) are already excluded. It also
  provides `owning_workspace(path)`, `workspaces_root(path, override)` and `exact_child()` (`workspace.py:28-62`).
- **E7 — `scripts/lib/report.py`.** `CODES` is the single source of each finding code's exit code
  (`report.py:32-64`). `Finding(code, severity, file, line, message)` and `Report.add()` refuse unknown codes
  (`:82-113`). `render()` prints the header, `FAMILY:` lines, `CHECKS RUN:`, `NOT RUN:`, findings, a summary and
  the verdict (`:149-176`).
- **E8 — the validators run in-process.** `validate_config.validate_file(path, options)`,
  `resolve_components.check_file(path, options)`, `validate_process.check_file(path, root)`, and
  `process_checks.check_workflow(path, tree, rep, root)` all return `Report` objects.
  `tools/run_known_good.py:144-167` (`run_validators`) composes them over a root with `cli.collect()`,
  `process_checks.processes_under()` and `workflows_under()`. `cli.display()` makes a report's file path
  cwd-relative (`scripts/lib/cli.py:77`), and some messages embed resolved paths (`process_checks.py:231, 310`).
- **E9 — the doctor.** `SHIPPED_DIRS` (`doctor.py:59`). `EXPECTED_SLICES = ("dgf-doctor", "dgf-component",
  "dgf-process", "dgf-audit")` omits every spine slice (`:104`). Each slice needs `SKILL.md`, a `name` equal to its
  directory, a non-empty `description` and an `allowed-tools` key, read by a **flat-key** frontmatter parser
  (`:335-358`), so multi-line YAML values do not parse. `gate_block()` emits `schema_version`, `gate`, `status`,
  `blocking`, `blockers`, `affected_files`, `affected_processes: []`, `affected_components: []` and
  `suggested_next` (`:509-536`).
- **E10 — the known-bad corpus contract.** Each case is `tests/fixtures/known-bad/<case>/` with a synthetic
  `workspaces/` tree and an `expected.json` holding `{"cli", "args", "exit", "codes"}`. The CLI runs from the case
  directory. `exit` must be `1` or `3`, and the corpus must have at least 24 cases (`tests/test_known_bad.py:1-40`;
  e.g. `route-no-row/expected.json`).
- **E11 — `tools/check-dual-schema-docs.sh`.** Section 2 requires every doc in `REQUIRED_DOCS` that says "schema"
  to name both families. Section 5 requires an index row and valid frontmatter for every ADR. Section 6 runs the
  doctor, section 7 the stamp check, and section 8 the unit tests. It asserts no skill or milestone counts.
- **E12 — the AI Factory spine skills** (`.claude/skills/`). `aif-plan/SKILL.md` has 933 lines,
  `aif-implement` 1052, `aif-verify` 578, `aif-commit` 279 and `aif` 782. Handoff mode takes about 70–90 lines of
  `aif-plan` and 110–130 of `aif-implement`. `aif-verify` Step 4.2.1 and `references/GATE-RESULT-CONTRACT.md` define
  the block: `schema_version`, `gate`, `status`, `blocking`, `blockers[{id, severity, file, summary}]`,
  `affected_files`, and `suggested_next{command, reason}` from a fixed allowlist. `aif-implement`, `aif-verify` and
  `aif-commit` repeat the same branch-stem plan-discovery algorithm near-verbatim. The plan template, which puts
  `Branch:` and `Created:` in prose lines, is `aif-plan/references/TASK-FORMAT.md`; the bundle format is
  `ULTRA-FORMAT.md`.

**DGF** (verified 2026-09-25)

- **E13 — `applibs*` are plugin-assembly folders.** `src/samples/workspaces/readme.md:12`: "`applibs*/` | plugin
  assemblies (`CustomAssembliesPath`), per consumer". All five sample `applibs*` folders hold only `.dll` files and
  have no `FM/`. `CustomAssembliesPath` is `src/Core/DGF.Kernel/Configuration/ApplicationConfig.cs:8`, read by
  `src/Core/DGF.Kernel/Extensions/AssemblyLoader.cs:13`. `WorkspaceSettings.cs` never mentions them.
- **E14 — the UI loads exactly three custom files.** `src/DGF.UI/src/app/components/app/app.component.ts:191-207`
  (`setUpCustomFiles`) injects `assets/js/formhelper.js`, `assets/js/formshared.js` and
  `assets/styles/custom.css`. `angular.json`'s `assets` globs copy nothing from a workspace. Deployments
  bind-mount a workspace's own file over those container paths: `src/samples/DGF.Compose/docker-compose.zims.yml:58-59`
  maps `workspaces/zims/js/formhelper.js` and `js/forms.shared.js`, and `:61` (commented out) maps a `custom.css`
  from outside the workspace. `docker-compose.ecouncil.yml:62,106` maps `workspaces/webasm/FM/js/formhelper.js`.
  The mapping lives in deployment configuration, outside the workspaces root.
- **E15 — per-form script.** `src/Core/DGF.Domain/Data/Form/FormManager.cs:183-196` (`GetFormScriptContent`)
  reads `_form.js` beside the form, or a `scriptPath` joined to `WorkspaceSettings.WorkspaceRootPath`.
- **E16 — static mounts.** `src/DGF.API/ConfigureServices.cs:365-383` serves `/application` from the workspace
  root and `/webasm` from the base workspace root, for content forms link to. The shell's three files do not use
  them. *Re-read before writing it as a fact (Task 5).*
- **E17 — nothing in a workspaces root states a DGF version.** Not `settings.xml`, not `sitemap.json` (its
  `"version": "1.0.0"` is the site map's own), not the workspace readmes. The UI's `version`
  (`src/DGF.UI/src/app/interfaces/app-settings.type.ts:8`) is the container's build version, stamped by
  `src/DGF.UI/Dockerfile:1,27-30`. This plugin's `knowledge/` has no `applies:` range outside `knowledge/README.md`
  (grep, 2026-09-25).
- **E18 — `webasm` may live in another repository.** `docker-compose.zims.yml:23` mounts `webasm` from
  `${ZAMOFFICE_REPO_PATH}`, while `zims` comes from `${ZIMS_REPO_PATH}`. `docker-compose.ecouncil.yml:21` mounts it
  from the application's own repository. So an estate's workspaces root may not contain `webasm`.
- **E19 — the root.** `DGF_WORKSPACES_ROOT_PATH`, else `WorkspacesRootPath`, else an exception;
  `WorkspaceName` defaults to `"default"` (`src/Core/DGF.Kernel/WorkspaceSettings.cs:29-39`).
- **E20 — legacy artifact files and component JSON match the shipped tables.** The loaders
  (`FormManager.cs:20,24`, `WorkflowManager.cs:58`, `ProcessManager.cs:21`, `TableManager.cs:14`,
  `ViewManager.cs:13,16`, `ComponentFileLoadService.cs:16-32`) agree with `knowledge/composition-specs.md` §2.1
  (`legacy-artifacts`) and `knowledge/json-reader.md` §2.1 and §4 (`component-folders`).

## Design Decisions

### DD1 — What the port keeps and what it drops

"Lift the AI Factory SKILL.md structure wholesale and swap the domain content" (`docs/blueprint.md` §"Build
order" 3). Each skill keeps its AI Factory step numbering and gate discipline, so a reader can diff the two. What
changes:

| AI Factory mechanic | In the spine | Why |
|---|---|---|
| Handoff mode (`HANDOFF_*`, `mcp__handoff__*`) | **dropped** | No Handoff integration; ADR 0001 takes no dependency on other tooling |
| `--parallel`, worktrees, `--list`/`--cleanup` of worktrees, sidecar agents | **dropped** | Milestone 13 ("Parallel Execution") |
| `workflow.plan_id_format: sequential` | **dropped** — ids are always `slug` | ADR 0009 forbids `sequential` at workspaces-root scope |
| Research context (`RESEARCH.md`, SHA256 drift) | **dropped** | No `/dgf-explore` until milestone 14; promote on second use |
| Roadmap linkage, `/aif-improve` refinement | **dropped** | No `/dgf-roadmap` or `/dgf-improve` exists |
| Testing / Logging / Docs preference questions | **dropped** | A consumer plan composes configuration. The validators are its tests, config has no logging, Playwright tests are TypeScript (ADR 0010 §3), and `/dgf-docs` is milestone 14 |
| `TaskCreate` / `TaskList` mirroring | **dropped** | The plan's checkboxes are the single ledger |
| `--without-plan` inline mode | **dropped** | Every change needs `affects_workspaces`, which only a plan carries |
| skills.sh installation, security scan, MCP templates, `AGENTS.md` generation (`/aif`) | **dropped** | The plugin ships its skills and its MCP server |
| `skill-context/<skill>/SKILL.md` override loading | **kept** (read-if-present) | Architecture idea #5; milestone 11 then needs no edit to the spine |
| Past patches (`patches/`) in `/dgf-implement` Step 0.1 | **kept** (read-if-present) | Same |
| fast / full / ultra, `index.md` + phase files, "executor never re-decides" | **kept** (D3) | Architecture idea #2 |
| Branch-based discovery, checkbox ledger, resume after `/clear` | **kept**; discovery moves into a script (DD5) | It is decidable, so it is a script, not four prose copies (E12) |
| Gate block, last block wins, suggested-next allowlist | **kept** in `/dgf-verify` (DD11) | Architecture idea #3 |
| `language.ui` / `language.artifacts` | **kept**; `technical_terms` dropped | Config-as-relocation; cheap |
| Commit-plan grouping, conventional commits, push prompt | **kept** in `/dgf-commit` | Framework-agnostic |

### DD2 — The artifact root and its config

- `.dgf-factory/` sits **once at the workspaces root** (ADR 0004 §3). It is committed: ADR 0009's overlap check and
  branch-based discovery depend on plans travelling with branches. `/dgf` warns if `.gitignore` excludes it.
- `.dgf-factory/config.yaml` is owned by `/dgf` and read by every spine skill. Its template ships as
  `skills/dgf/references/config-template.yaml`:

  ```yaml
  # dgf-factory configuration — written by /dgf, read by every dgf-* skill.
  # Paths are relative to the workspaces root, the directory that holds .dgf-factory/.
  dgf:
    version: "1.1.15"          # the DGF version this estate runs, or "unknown" (ADR 0019)
  language:
    ui: en
    artifacts: en
  paths:
    description: .dgf-factory/DESCRIPTION.md
    plan: .dgf-factory/PLAN.md          # fast plans
    plans: .dgf-factory/plans/          # full plans and ultra bundles
    patches: .dgf-factory/patches/      # read-if-present (milestone 11 writes them)
    skill_context: .dgf-factory/skill-context/
  git:
    enabled: true
    base_branch: main
    create_branches: true
    branch_prefix: feature/
    skip_push_after_commit: false
  workflow:
    verify_mode: normal                 # normal | strict
  ```

  There is no `plan_id_format` key: ids are always `slug` (ADR 0009).
- **Scripts never read the config.** Skills read it with `Read` and pass values as arguments (`--plans-dir`,
  `--fast-plan`, `--base`). The standard library has no YAML parser, and a validator must not guess a key.
- `.dgf-factory/DESCRIPTION.md` is owned by `/dgf`. It holds the estate's name and purpose, the declared DGF
  version, the inventory table from `inventory_root.py` (DD9), and any per-project overrides of ADR 0005's rules 5
  and 6 (auth, test stack), which ADR 0005 lets setup record there. Its template ships as
  `skills/dgf/references/description-template.md`.

### DD3 — The plan file format (ADR 0017 §1–§2)

The **header is YAML frontmatter**, the shape ADR 0009 used (`affects_workspaces: [zims, webasm]`), restricted to a
flat subset that a stdlib parser reads exactly: `key: scalar`, `key: "quoted scalar"`, `key: [a, b]`. Anything
else is `PLAN_UNREADABLE` (exit `3`) with the line number.

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

- `base_workspace_reason` is **required when, and only when, `webasm` is listed** (ADR 0005 rule 3 needs "a
  justification named in the plan").
- Allowed keys are exactly these six plus `archived` (reserved for a future archive skill, accepted and ignored).
  Any other key is `PLAN_FIELD_INVALID`, per the rules' "reject unknown keys".
- An ultra bundle carries the same frontmatter in `index.md` with `mode: ultra`. That field is the bundle marker;
  there is no HTML-comment marker.
- **Body sections**, in order: `# Implementation Plan: <name>`, `## Original Request` (verbatim, when the user gave
  one), `## Scope` (why each workspace is in; what is out of scope and needs a general coding flow, ADR 0010 §3),
  `## Affected Artifacts` (a table of existing and new artifacts with workspace, family and route evidence),
  `## Commit Plan` (5+ tasks), `## Tasks`, `## Risks`.

**Tasks** are the AI Factory checkbox lines, each followed by indented field bullets:

```markdown
## Tasks

### Phase 1: Fee data
- [ ] Task 1: Add the inspection-fee DataSource
  - kind: config
  - files: zims/FM/_COMPONENTS/DataSource/InspectionFee.json
- [ ] Task 2: Show the fee on the application form (depends on 1)
  - kind: config
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.xml
- [ ] Task 3: Hide the fee panel until the gateway confirms payment (depends on 2)
  - kind: code
  - reason: No EventBase verb reads the gateway callback (knowledge/composition-specs.md §3.1), and toggleVisible needs a value the form does not hold
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.js
```

- `Task N:` ids are unique integers. `(depends on N, M)` names existing ids.
- `kind:` is `config` or `code`, and it is mandatory.
- `reason:` is mandatory for `code`, and optional (and informational) for `config`.
- `files:` is a comma-separated list of paths **relative to the workspaces root**, with `/` separators, whose first
  segment is a workspace name. It lists the files the task creates or edits. `deletes:` lists the files it
  removes. A task needs at least one of the two.
- In an ultra bundle, the task lines and their field bullets live **only in `index.md`**; the phase files hold the
  detail. The task title may be a link to its phase section.
- The file stem of a full plan or ultra directory is `branch` with every `/` replaced by `-` (ADR 0009: filenames
  carry no workspace).

### DD4 — File classes and code places (ADR 0017 §3–§4)

Every path a plan names, and every path a branch changes under the root, falls into exactly one class:

| class | rule | in a plan task | in a branch diff |
|---|---|---|---|
| **config** | under `<ws>/FM/`, extension `.json` or `.xml` | `kind: config` only | checked by the validators |
| **code** | matches a row of the `code-places` table (Task 5): a form's `_form.js`; a `.js` under `<ws>/js/` or `<ws>/FM/js/`; a `.css` under `<ws>/css/` | `kind: code` only; a new file is allowed **only** for `_form.js` (D2) | must be listed by a `kind: code` task |
| **excluded** | extension in `.cs .csproj .sln .ts .tsx .sql .dll .exe .html .cshtml .razor`, or anything under an `applibs*` folder | never (ADR 0010 §3) | blocks |
| **other** | anything else in a workspace: images, templates, readmes | warned, not authored | warned |

- Changes under `<root>/.dgf-factory/` are the pipeline's own artifacts and are ignored by every check.
- Which folders load a script is a **DGF fact**, so it is read from the `code-places` machine-read table in
  `knowledge/composition-specs.md` (Task 5), never hard-coded. The excluded extension list is **this plugin's
  policy** (ADR 0010 §3, restated in ADR 0017), so it is a constant in `scripts/lib/plan.py`.
- `applibs*` are not workspaces (D5). `workspace.applications()` already excludes them (E6). A plan that names one
  gets `PLAN_UNKNOWN_WORKSPACE` with a message saying it is a plugin-assembly folder.

### DD5 — `scripts/locate_plan.py` and `scripts/check_plan.py`

**`locate_plan.py`** — stdlib plus `git`; one definition of discovery for four skills (E12).

```
locate_plan.py [--workspaces-root R] [--plans-dir D] [--fast-plan F] [--branch B] [--root-only | --list] [--verbose]
```

1. **Root.** When `--workspaces-root` is absent, the root is the nearest directory holding
   `.dgf-factory/config.yaml`: first the working directory and its ancestors, then its descendants to depth 4,
   skipping dot-directories other than `.dgf-factory` and skipping `node_modules`. It prints `ROOT: <path>`. No
   match is `ROOT_NOT_SET_UP` (exit `1`, "run /dgf"). Several matches are `ROOT_AMBIGUOUS` (exit `1`, listing them).
   `--root-only` stops here.
2. **Plan.** `D` defaults to `.dgf-factory/plans` and `F` to `.dgf-factory/PLAN.md`, both relative to the root.
   The branch is `--branch`, or else `git branch --show-current` run in the root. The stem is the branch with `/`
   replaced by `-`. It checks `<D>/<stem>/index.md`, then `<D>/<stem>.md`:
   - both exist → `PLAN_AMBIGUOUS` (exit `1`);
   - one exists → `PLAN: <path> mode=<frontmatter mode> source=branch` (exit `0`);
   - neither → the lone entrypoint in `D` (a root `*.md` or a direct `*/index.md`) → `PLAN_FALLBACK` (exit `2`,
     `source=lone`); else `F` if it exists → `PLAN_FALLBACK` (`source=fast`); several candidates →
     `PLAN_AMBIGUOUS` (exit `1`); none → `PLAN_NOT_FOUND` (exit `1`, "run /dgf-plan").
3. `--list` prints `PLAN: <path> mode=<m> progress=<done>/<total>` for every entrypoint in `D` and `F`, and exits
   `0`.

**`check_plan.py`** — stdlib plus `git` (for `--overlap`) plus `lib.knowledge` for the route check.

```
check_plan.py <plan-entrypoint> --workspaces-root R [--overlap] [--verbose]
```

Output follows `docs/skill-authoring.md` §"Reading a validator's output", with plan lines in place of `FAMILY:`
lines, as `route_means.py` does with `ROUTE:`:

```
Plan check
PLAN: .dgf-factory/plans/feature-zims-inspection-fee.md mode=full format=1 branch=feature/zims-inspection-fee
AFFECTS: zims, webasm
TASK: 1 [ ] kind=config files=zims/FM/_COMPONENTS/DataSource/InspectionFee.json
TASK: 3 [ ] kind=code depends=2 files=zims/FM/_DATA/Inspection/_forms/Apply/_form.js
PROGRESS: 0/3
CHECKS RUN: plan-header, plan-tasks, plan-files, plan-routes, plan-overlap
NOT RUN: …
<findings>
<summary>
<verdict>
```

| check id | code | exit | when |
|---|---|---|---|
| — | `PLAN_UNREADABLE` | 3 | no frontmatter, or a line outside the flat subset |
| — | `PLAN_FORMAT_UNSUPPORTED` | 3 | `plan_format` is not `1` |
| plan-header | `PLAN_FIELD_MISSING` | 1 | `plan_format`, `mode`, `branch`, `created` or `affects_workspaces` absent, or the list is empty |
| plan-header | `PLAN_FIELD_INVALID` | 1 | an unknown key, a `mode` outside fast/full/ultra, a `created` that is no `YYYY-MM-DD` date, `branch: none` on a full or ultra plan |
| plan-header | `PLAN_UNKNOWN_WORKSPACE` | 1 | a listed name is neither `webasm` nor in `workspace.applications(root)`; for an `applibs*` name the message says it is a plugin-assembly folder |
| plan-header | `PLAN_BASE_REASON_MISSING` | 1 | `webasm` is listed and `base_workspace_reason` is absent or empty |
| plan-header | `PLAN_BRANCH_MISMATCH` | 1 | full or ultra: the file stem is not the branch with `/` → `-` |
| plan-tasks | `PLAN_NO_TASKS` | 1 | `## Tasks` is missing or holds no checkbox task |
| plan-tasks | `PLAN_TASK_INVALID` | 1 | a duplicate id, an unknown dependency, a missing or unknown `kind`, or neither `files` nor `deletes` |
| plan-tasks | `PLAN_CODE_REASON_MISSING` | 1 | a `kind: code` task with no `reason` |
| plan-tasks | `PLAN_ULTRA_BROKEN` | 1 | ultra: a Phase Index or task link names a phase file that does not exist or is not a direct child of the bundle |
| plan-files | `PLAN_FILE_UNDECLARED_WORKSPACE` | 1 | a file's first segment is not in `affects_workspaces`, or is not a workspace at all |
| plan-files | `PLAN_KIND_MISMATCH` | 1 | a config task lists a code file, or a code task lists a config file |
| plan-files | `PLAN_OUT_OF_SCOPE` | 1 | an excluded file (DD4) |
| plan-files | `PLAN_CODE_FILE_NEW` | 1 | a code task lists a `js/`, `FM/js/` or `css/` file that does not exist yet (D2) |
| plan-files | `PLAN_NOT_AUTHORED` | 2 | an *other*-class file |
| plan-routes | `PLAN_ROUTE_MISMATCH` | 1 | a **new** file whose family contradicts the route: JSON under `_COMPONENTS/<Type>/` for a ✗ type; a new legacy artifact written as `.json` (ADR 0005 rule 1); an `.xml` under `_COMPONENTS/` |
| plan-routes | `PLAN_ROUTE_UNKNOWN` | 1 | a new file under `_COMPONENTS/<Folder>/` whose folder is neither a loader folder in the `component-folders` table nor a ComponentType with a parity row |
| plan-routes | `PARITY_PARTIAL` (existing) | 2 | a new JSON file for a ◐ type |
| plan-overlap | `PLAN_OVERLAP` | 2 | another active plan's set intersects this one's, or either contains `webasm` |
| plan-overlap | `PLAN_OVERLAP_UNREADABLE` | 0 (INFO) | a plan on another ref does not parse; it is skipped and named |

- **Existing files are not routed.** An existing artifact is edited in its own family (ADR 0010 §1), so
  `plan-routes` applies to files that do not exist yet.
- The route logic reuses `route_means.route()` (import the function; do not shell out), and the loader folders
  (`DataSource`, `Template`, `Endpoints`) come from the `component-folders` table in `knowledge/json-reader.md` §4.
  `route_means` and everything it imports (`cli`, `knowledge`, `json_resolve`, `prepass`, `report`) are stdlib, so
  `check_plan.py` needs no `lxml`.
- **Folder rules for a new file under `FM/_COMPONENTS/`.** The type is the **first** segment below `_COMPONENTS/`;
  a component name may itself contain `/` (e.g. `Page/SiteMap/loginPage.json`). A file directly under
  `_COMPONENTS/` belongs to the `(root)` row (the site map). A folder that matches a ComponentType member only
  when case is ignored is `PLAN_ROUTE_MISMATCH` ("folder case"): the loader builds the path from the member's own
  spelling, and Linux matches exactly (`knowledge/json-reader.md` §4).
- **A new legacy artifact written as JSON** is a file whose name is a `legacy-artifacts` Filename with `.xml`
  replaced by `.json`, inside that row's Folder (e.g. `_forms/<form>/_form.json`). It is `PLAN_ROUTE_MISMATCH`
  (ADR 0005 rule 1).
- **Why `PLAN_ROUTE_UNKNOWN` is exit `1` when `route_means.py` gives `3` for the same condition:** a plan is an
  artifact the planner can fix, so a folder with no route is a plan defect. `route_means.py` is asked a question
  it cannot answer, which is a usage error. ADR 0017 §6 records this.
- When `webasm` is listed but the root has no `webasm/FM/` (E18), the `PLAN_UNKNOWN_WORKSPACE` message says so, and
  names the inventory's `BASE_WORKSPACE_ABSENT`.
- Without `--overlap`, or outside a git work tree, `plan-overlap` is `NOT RUN` with its reason.

### DD6 — The overlap check (ADR 0017 §5, D6)

- **Scanned:** the working tree, plus the tip of every ref under `refs/heads/` and `refs/remotes/`
  (`git for-each-ref`). At each tip it reads `.dgf-factory/plans/*.md`, `.dgf-factory/plans/*/index.md` and
  `.dgf-factory/PLAN.md`, via `git ls-tree` and `git show <ref>:<path>`, with the root's path relative to the git
  top level. Blobs with the same object id are read once.
- **Excluded:** the plan under check itself — the same path in the working tree, and the same path at any ref whose
  name ends in its `branch` — and every plan with no unchecked task.
- **No fetch.** Remote-tracking refs are as fresh as the last fetch, and the report says so on a `NOT RUN`-style
  note line, `OVERLAP SOURCES: <n> refs scanned; remote refs as of the last fetch`. `/dgf-plan` offers to run
  `git fetch` first; the script never does.
- Each overlap is one `PLAN_OVERLAP` finding naming the other plan's path, its ref, and the shared workspaces
  (`webasm` named as "shared with every plan").

### DD7 — `scripts/check_change.py` (ADR 0017 §6, ADR 0018)

```
check_change.py --workspaces-root R --plan P (--base REF | --changed STATUS:PATH ...) [--files PATH ...] [--skip-validators] [--verbose]
```

- `--base REF`: the merge-base of `HEAD` and `REF`. The changed set is the working tree against the merge-base —
  `git diff --name-status -M <merge-base>` plus `git ls-files --others --exclude-standard` as `A` — limited to paths
  under the root, minus `.dgf-factory/`.
- `--changed A:path M:path D:path …`: an explicit changed set, root-relative. The baseline is `NOT RUN` because
  there is no base tree, so every validator finding counts as new. This mode exists for tests and the known-bad
  corpus.
- `--files`: the validator scope, root-relative. It defaults to the whole root (`/dgf-verify`); `/dgf-implement`
  passes the task's files.
- `--skip-validators`: run only the scope, means and planned checks. `/dgf-commit` uses it; it needs no `lxml`.
- It prints `BASE: <sha> (<REF>)`, `CHANGED: <n>`, and one `CHANGE: <A|M|D|R> <path> class=<class> workspace=<ws>`
  line per file, then the standard sections.

| check id | code | exit | when |
|---|---|---|---|
| change-scope | `CHANGE_UNDECLARED_WORKSPACE` | 1 | a changed file's workspace is not in `affects_workspaces` (ADR 0009) |
| change-scope | `CHANGE_OUTSIDE_WORKSPACE` | 2 | a changed file under the root sits in no workspace and is not excluded |
| change-means | `CHANGE_OUT_OF_SCOPE` | 1 | an excluded file changed, including anything under `applibs*` (ADR 0010 §3) |
| change-means | `CHANGE_CODE_UNPLANNED` | 1 | a code file changed that no `kind: code` task lists (ADR 0005 rule 2, ADR 0010 §2) |
| change-means | `CHANGE_CODE_FILE_NEW` | 1 | a file was added under `js/`, `FM/js/` or `css/` (D2) |
| change-planned | `CHANGE_UNPLANNED_FILE` | 2 | a config or other file changed that no task lists |
| change-planned | `CHANGE_TASK_FILE_UNCHANGED` | 2 | a checked task's `files` entry is unchanged, or a `deletes` entry still exists |
| change-planned | `CHANGE_NOT_AUTHORED` | 2 | an *other*-class file changed |
| baseline | *(the validator's own code)* | its own | a finding present in the working tree and absent at the merge-base — **new** |
| baseline | `PRE_EXISTING` | 0 (INFO) | a finding present at both; the message carries the original code |
| baseline | `FIXED` | 0 (INFO) | a finding at the merge-base that the branch removed |

The validators need `lxml` and `jsonschema`: without `--skip-validators`, a missing dependency is exit `3` through
`deps.require()`. The summary line reads
`new: <e> error(s), <w> warning(s); pre-existing: <p>; fixed: <f>`.

### DD8 — The baseline comparison (ADR 0018, D1)

- **The base tree** is materialised blob by blob. `git ls-tree -r -z <merge-base> -- <root relative to the top
  level>` lists it, and `git cat-file --batch` streams each blob into a `tempfile.TemporaryDirectory()`, which is
  removed on exit. **Not `git archive`:** it applies the estate's `.gitattributes` (`export-ignore` drops files,
  `export-subst` rewrites them), and the base tree would then disagree with the commit. Symlinks (mode `120000`)
  and submodules (`160000`) are skipped and counted in a DEBUG trace. Every written path is checked to stay inside
  the temporary directory. Nothing in the working tree changes.
- **The same runner at both trees.** Whole root: `process_checks.processes_under()`, `workflows_under()` and
  `cli.collect([root])`, as in `tools/run_known_good.py:144-167`. That runner **moves** into
  `scripts/lib/runner.py` (`run(root, files=None) → {cli name: [Report]}, unresolved`), and
  `run_known_good.py` imports it — the tools-may-import-shipped rule (`.ai-factory/ARCHITECTURE.md` §Dependency
  Rules). With `--files`, each file is routed to the same validators, at both trees, where the file exists.
  `process_checks` imports `lxml` at module top (`process_checks.py:32`), so `runner.py` imports it and the
  validator modules **inside `run()`**, after `deps.require()`. `--skip-validators` and `--help` must work without
  `lxml`.
- **The finding key** is `(code, root-relative file, normalised message)`. To normalise, replace the absolute root
  path and its `cli.display()` form with `<root>`, and drop the line number. The line is not in the key, so an edit
  above a pre-existing finding does not make it new. Keys are compared as **multisets** (`collections.Counter`): a
  second copy of an existing finding is new.
- **No git, no merge-base, or an archive failure** → `NOT RUN: baseline (<reason>; every finding counts as new)`.
  The gate is stricter, never looser.
- **What it cannot see:** a pre-existing finding the branch makes worse without changing its key. ADR 0018 records
  this as a cost.
- `/dgf-implement` runs it per task with `--files <task files>`. That is a fast pre-check, never the gate. The
  gate is `/dgf-verify`'s whole-root run (ADR 0004).

### DD9 — `scripts/inventory_root.py`

```
inventory_root.py --workspaces-root R [--verbose]
```

Stdlib only; used by `/dgf` (DESCRIPTION inventory) and `/dgf-plan` (reconnaissance, valid workspace names).

```
Workspaces root inventory
ROOT: /estate/Web/workspaces
WORKSPACE: webasm role=base processes=12 workflows=… components=… forms=… settings=… views=… form_scripts=… global_scripts=… global_styles=…
WORKSPACE: zims role=application …
NOT A WORKSPACE: applibs-zims (plugin assemblies — .dll files, no FM/)
GIT: toplevel=/estate branch=develop root=Web/workspaces        (or GIT: none)
KNOWLEDGE: dgf_version=1.1.11
VALIDATORS: dependencies present                                  (or missing: lxml, jsonschema)
```

| code | exit | when |
|---|---|---|
| `ROOT_NO_WORKSPACE` | 3 | no directory under the root has an exact-case `FM/` |
| `BASE_WORKSPACE_ABSENT` | 2 | no `webasm/FM/` under the root; `BASE:` references cannot resolve here (E18) |
| `VALIDATOR_DEPS_MISSING` | 2 | `deps.missing()` is non-empty; the message carries `deps.install_command()` verbatim |

Counts come from the `legacy-artifacts` table's filenames (forms, settings, views), `process.xml` and
`_workflow.xml` under their folders, `*.json` under `FM/_COMPONENTS/`, and the `code-places` table. It confirms
that `lib.cli` and `lib.knowledge` import no third-party package before it uses them.

### DD10 — The estate's DGF version (ADR 0019, D4)

`/dgf` asks for it, shows the knowledge stamp (`KNOWLEDGE: dgf_version=…` from the inventory), and writes
`dgf.version` as a quoted `X.Y.Z` or `unknown`. When the declared version is newer than the stamp, it says the
facts were read at an older release and offers `get_release_notes("since:<stamp>")`. `unknown` is a warning that it
repeats in DESCRIPTION.md. The gate that compares the version with `applies:` ranges is a follow-up. It has no
input until a behavioural fact exists (E17), and when it lands it reads `dgf.version`.

### DD11 — `/dgf-verify`'s gate block in milestone 9 (D7)

- **Fields:** exactly AI Factory's base block (E12), fenced as `dgf-gate-result` — `schema_version: 1`,
  `gate: "verify"`, `status`, `blocking: true`, `blockers[{id, severity, file, summary}]`, `affected_files`,
  `suggested_next{command, reason}`. It is the last thing in the output, and callers read the last block (ADR 0014
  §5, `docs/skill-authoring.md` §"Gate blocks").
- **Status is computed, never judged:**

  | input | status |
  |---|---|
  | any script exit `3`, or a required check not run because a script could not run | `fail` |
  | any exit `1`: a new blocking finding, a plan defect, an undeclared workspace, an unchecked task | `fail` |
  | any exit `2`, or a check that cannot run by design (for example `frontend-tests`, ADR 0010 §2) | `warn` |
  | otherwise | `pass` |

  In `strict` mode (`workflow.verify_mode` or `--strict`), a **new** warning is `fail`; `PRE_EXISTING` never is.
- **`suggested_next.command` allowlist:** `/dgf-plan` (the plan itself is defective), `/dgf-implement` (tasks remain
  or new findings need fixing), `/dgf-commit` (`pass` or `warn`), or `null`.
- **Required checks** are `plan-header`, `plan-tasks`, `plan-files`, `change-scope`, `change-means`, `baseline` and
  the validators' own. A required check that is `NOT RUN` appears as a blocker of severity `warning`, and the prose
  keeps every `NOT RUN` line. The block never reads as having passed a check that did not run.
- `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md` records the milestone-10 fields as **not yet emitted**.

### DD12 — The doctor

- `EXPECTED_SLICES` becomes, in roadmap order: `dgf-doctor`, `dgf`, `dgf-plan`, `dgf-implement`, `dgf-verify`,
  `dgf-commit`, `dgf-component`, `dgf-process`, `dgf-audit`.
- **New check, `PLUGIN_PATH_DANGLING` (error, exit `1`):** every `${CLAUDE_PLUGIN_ROOT}/<path>` in a shipped
  Markdown file must name an existing file or directory under the plugin. A token ends at whitespace, a quote, a
  backtick or `)`. Tokens containing `<`, `*`, `{` or a second `$` are templates and are skipped. Five new skills
  cite about twenty plugin paths, and a typo in one is a silent runtime failure.
- **New check, `SKILL_FRONTMATTER_YAML` (error, exit `1`):** the doctor's parser is flat (`doctor.py:189-207`), but
  Claude Code reads the block as YAML. An **unquoted** value that starts with `[ { * & ! % @` or a backtick, or that
  contains `: ` or ` #`, parses differently or fails, so the skill may not load. Four of the five new skills have an
  `argument-hint` beginning with `[`. The check is in section 3 (skill slices).

### DD13 — New knowledge (Task 5)

- `knowledge/composition-specs.md` gains **§1.2 "What sits beside the workspaces"** (E13, structural) and **§5
  "Custom script and style delivery"** (E14–E16, structural), with a machine-read table:

  ```markdown
  <!-- machine-read: code-places -->
  | Place | Path | Extension | Loaded by | New file loaded |
  |---|---|---|---|---|
  | form-script | FM/_DATA/<table>/_forms/<form>/ | .js | the form's own script, `_form.js` beside `_form.xml` (`FormManager.GetFormScriptContent`) | yes |
  | global-script | js/ | .js | a deployment bind-mount onto the shell's `assets/js/formhelper.js` or `assets/js/formshared.js` | no |
  | global-script-base | FM/js/ | .js | the same, used for `webasm` | no |
  | global-style | css/ | .css | a deployment bind-mount onto the shell's `assets/styles/custom.css` | no |
  ```

  The form-script row's filename is exactly `_form.js`; the table states it in prose, and `lib/plan.py` matches that
  filename. Paths are relative to the workspace. **A `<name>` placeholder stands for exactly one path segment**,
  and the prose says so. The facts never name a skill (`.ai-factory/ARCHITECTURE.md` §Dependency Rules).
- The table is registered in `scripts/lib/knowledge.py` `TABLES` with its allowed values,
  `{"Extension": {".js", ".css"}, "New file loaded": {"yes", "no"}}` (the third element each entry already takes,
  `knowledge.py:23-60`), and in `knowledge/README.md` §7. Its sources are added to
  `provenance/knowledge/composition-specs.md` with fresh `sha256` digests.

### DD14 — Skill authoring constraints

- Frontmatter values are **single-line** (the doctor's flat parser, E9), with `name`, `description` (trigger
  phrases), `argument-hint`, `allowed-tools`, `disable-model-invocation: false` and `version: 0.1.0`. They must
  also be **valid YAML scalars**: quote any value that starts with `[` (every `argument-hint` here) or contains `: `.
  The doctor enforces this as `SKILL_FRONTMATTER_YAML` (DD12).
- `allowed-tools` never grants bare `Bash`: `Bash(python3 *)`, `Bash(git *)`. **Verify before writing** two names:
  the subagent tool (`Agent`; AI Factory 2.18.1 lists `Task`) and the tool names a plugin-shipped MCP server
  exposes. Check `.claude/skills/plugin-structure/` and ask the `claude-code-guide` agent. If an MCP tool name
  cannot be verified, leave it out of `allowed-tools`; the normal permission prompt then applies.
- Every script call is `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py" …`, with the exit code captured before
  any pipe. Every fact is cited from `knowledge/` or a DGF docs MCP call, never inlined (the architecture's
  anti-patterns). No DGF repository path, ever (ADR 0012; the doctor blocks on it).
- Each SKILL.md ends with `## Execution Rules` (DO / DON'T), `## Artifact Ownership` and `## Critical Rules`, like
  `skills/dgf-doctor/SKILL.md`.

## Commit Plan

- **Commit 1** (after tasks 1–4): `docs(adr): decide the plan format, change-relative gates and the declared DGF version`
- **Commit 2** (after task 5): `feat(knowledge): record applibs folders and custom script delivery`
- **Commit 3** (after tasks 6–9): `feat(scripts): add plan discovery, plan checks and the root inventory`
- **Commit 4** (after tasks 10–11): `feat(scripts): add the change check with a merge-base baseline`
- **Commit 5** (after task 12): `feat(doctor): expect the spine slices, check plugin paths and YAML-safe frontmatter`
- **Commit 6** (after tasks 13–14): `feat(skills): add /dgf setup and /dgf-plan`
- **Commit 7** (after tasks 15–17): `feat(skills): add /dgf-implement, /dgf-verify and /dgf-commit`
- **Commit 8** (after tasks 18–20): `docs: document the pipeline spine and mark the milestone done`

## Tasks

### Phase 1: Decisions

- [x] **Task 1: Write ADR 0017 — the plan file format.**
  Create `docs/adr/0017-plan-file-format.md`, status `accepted`, date 2026-09-25, deciders `[Andrian Mamei]`,
  `supersedes: []`, following `docs/adr/README.md` §"Section contract".
  - *Title:* "The plan file: a frontmatter header, per-task kind, reason and files, and edit-only global scripts".
  - *Context* (cite, don't recall): E1, E2, E4, E6, E12, E13, E14, E15, E16 (re-read), with DGF paths at
    `aa1d5c4c2` and the read date.
  - *Decision:* §1 the header (DD3); §2 tasks and fields (DD3); §3 file classes and the excluded list (DD4); §4
    `applibs*` are not workspaces (D5); §5 active plans and overlap sources (DD6); §6 which script decides what —
    `locate_plan.py`, `check_plan.py`, `check_change.py` (DD5, DD7); §7 ids stay `slug`, and stem = branch with `/`
    → `-`. §6 also records why `PLAN_ROUTE_UNKNOWN` is exit `1` while `route_means.py` returns `3` for the same
    condition (DD5).
  - *Alternatives:* prose header lines like AI Factory; per-task YAML blocks; `kind` per phase; new files allowed in
    `js/`/`css/` (rejected: E14); `_form.js` only (rejected: estates really do edit the global scripts); `applibs*`
    as workspaces (rejected: E13); overlap on the working tree only (rejected: it cannot see the unmerged branches
    ADR 0009 exists to reveal); fetching before a scan (rejected: validators make no network calls).
  - *Consequences* with negatives: a stricter plan grammar; stale remote refs hide plans; a new global script
    needs deployment work outside the plugin; `scriptPath` stays unused.
  - *Follow-ups:* `scriptPath`'s declaring attribute; whether non-JSON/XML files under `FM/` (templates) are
    configuration.
  - It closes ADR 0009's and ADR 0010's format and code-place follow-ups by reference. **Do not edit ADR 0009 or
    0010**: follow-ups are not decisions, and the contract permits only errata.
  - Files: `docs/adr/0017-plan-file-format.md`.

- [x] **Task 2: Write ADR 0018 — gates block on what the branch introduced.**
  Create `docs/adr/0018-change-relative-gates.md`, `accepted`, 2026-09-25.
  - *Title:* "A gate blocks on what the branch introduced: findings are compared with the merge-base".
  - *Context:* ADR 0004's whole-root scope and brownfield default; ADR 0014's two true sample defects;
    `tools/known-good-exceptions.txt` as proof that real estates carry errors; E8.
  - *Decision:* DD8 in full — the key, the multiset, the base tree read blob by blob with `git ls-tree` and
    `git cat-file --batch` (not `git archive`, whose export attributes alter the tree), `--files` versus whole root,
    no git meaning every finding counts, `PRE_EXISTING` and `FIXED` as INFO, and that implement's file-scoped run
    never passes a gate (ADR 0004 §3).
  - *Alternatives:* the three options put to the decider (changed files only; any finding in the root); a stored
    baseline file (it goes stale, and it is another artifact to own); per-line keys (rejected: every edit above a
    finding would make it new).
  - *Consequences:* two whole-root runs per verify (measured in Task 11); a finding made worse without a new key
    passes; the gate depends on `git`.
  - Files: `docs/adr/0018-change-relative-gates.md`.

- [x] **Task 3: Write ADR 0019 — the estate's DGF version is declared at setup.**
  Create `docs/adr/0019-declared-dgf-version.md`, `accepted`, 2026-09-25.
  - *Context:* E17, plus ADR 0013's follow-up "Decide how the version gate learns a developer's DGF version"
    (`docs/adr/0013-version-gating-provenance-ledger.md:259-260`).
  - *Decision:* DD10. `/dgf` asks, and records `dgf.version` in `.dgf-factory/config.yaml` as a quoted `X.Y.Z` or
    `unknown`. The future version gate reads only that key, and treats `unknown` as ADR 0013 §4's "cannot be
    determined" row (exit `2`).
  - *Alternatives:* the UI container's build version (not reachable from the root, and not DGF's version); the
    estate repository's git tags (the estate's, not DGF's); asking on every run; inferring from which schemas
    validate (1.1.14 and 1.1.15 validate the same JSON — ADR 0013 §Context).
  - *Consequences:* a declared value can be wrong or go stale, and nothing checks it against a deployment.
  - Files: `docs/adr/0019-declared-dgf-version.md`.

- [x] **Task 4: Index the three ADRs and pass the decision-record checks.** (depends on 1, 2, 3)
  - Add rows 0017–0019 to `docs/adr/README.md` §Index, with Status `accepted` and a *Decides* cell each. Extend its
    §"See Also" if it names ADR groups.
  - Run `tools/check-dual-schema-docs.sh`. Sections 5 and 5b must pass. Record the verdict, and fix any
    frontmatter or link it reports.
  - Files: `docs/adr/README.md`.
  - <!-- Commit checkpoint: tasks 1-4 -->

### Phase 2: Knowledge

- [x] **Task 5: Record `applibs*` and custom script delivery as stamped facts, with a `code-places` table.**
  (depends on 4)
  - **Re-read each source at the DGF checkout's current HEAD before writing** (E13–E16), and compute its `sha256`
    with `shasum -a 256`. If HEAD is not `aa1d5c4c2`, say so in the ledger's prose. If a source disagrees with
    the evidence base, **STOP and report**. Do not write the fact.
  - `knowledge/composition-specs.md`: add §1.2 "What sits beside the workspaces" (E13) and §5 "Custom script and
    style delivery" (E14–E16), with the `code-places` table from DD13. Cite by type and file name —
    `FormManager.GetFormScriptContent`, the UI shell's start-up, deployment bind-mounts — **never by DGF path**.
    Set `read_date: 2026-09-25`. Keep `review_date` (§4 is still the only policy fact).
  - `provenance/knowledge/composition-specs.md`: add `ApplicationConfig.cs`, `AssemblyLoader.cs`, the samples'
    `workspaces/readme.md`, `app.component.ts`, `angular.json`, `nginx-ng.conf`, `docker-compose.zims.yml`,
    `docker-compose.ecouncil.yml` and `ConfigureServices.cs`, each with `path` and `sha256`. Refresh
    `FormManager.cs`'s digest if it changed.
  - `scripts/lib/knowledge.py`: register `code-places` in `TABLES` with its exact header cells and the allowed
    values in DD13, following the existing entries' shape.
  - `knowledge/README.md` §7: add the table's row.
  - `tests/test_knowledge.py`: the table loads, has its four rows keyed by `Place`, a renamed header fails as
    `KnowledgeTableError`, and so does a `New file loaded` of `Yes`.
  - Verify: `python3 tools/check_knowledge_stamps.py` exits `0`;
    `python3 tools/check_drift.py <dgf-root>` is CLEAN; the doctor's section 6 counts one more table; the unit
    suite passes.
  - Logging: none new. The loader's existing `report.debug` trace covers the table.
  - Files: `knowledge/composition-specs.md`, `provenance/knowledge/composition-specs.md`, `knowledge/README.md`,
    `scripts/lib/knowledge.py`, `tests/test_knowledge.py`.
  - <!-- Commit checkpoint: task 5 -->

### Phase 3: Plan scripts

- [x] **Task 6: Add the finding codes and a read-only git helper.** (depends on 5)
  - `scripts/lib/report.py` `CODES`: add every code in DD5, DD7 and DD9 with the exit shown — `ROOT_NOT_SET_UP`,
    `ROOT_AMBIGUOUS`, `PLAN_NOT_FOUND`, `PLAN_AMBIGUOUS` (1), `PLAN_FALLBACK` (2), the `PLAN_*` table,
    `CHANGE_*`, `PRE_EXISTING`, `FIXED` and `PLAN_OVERLAP_UNREADABLE` (0), `ROOT_NO_WORKSPACE` (3),
    `BASE_WORKSPACE_ABSENT` and `VALIDATOR_DEPS_MISSING` (2). No existing code changes severity.
  - `scripts/lib/git.py` (new, stdlib `subprocess`, read-only, `git -C <dir>` always, never a shell): `available()`,
    `toplevel(path)`, `current_branch(path)`, `merge_base(path, ref)`, `changed(path, merge_base)` → `[(status,
    path)]` (name-status with `-M`, plus untracked as `A`), `refs(path)` (`for-each-ref refs/heads refs/remotes`),
    `ls_tree(path, ref, prefix)`, `show(path, ref, relpath)` → bytes, and `materialise(path, commit, prefix, dest)`
    (DD8: `git ls-tree -r -z` then `git cat-file --batch`, never `git archive`). It writes regular blobs only,
    skipping and counting symlinks and submodules, and refuses any path that would land outside `dest`. A
    failure raises `GitError(message)`; callers turn it into a `NOT RUN` line or `report.fail(3, …)`, never an
    unhandled traceback.
  - `tests/test_git.py`: builds temp repos with `subprocess` (`git init -b main`, config `user.name`/`user.email`
    locally, commits, branches). It covers each function, a rename, untracked files, a detached HEAD
    (`current_branch → None`), and `GitError` outside a repo. For `materialise`, a `.gitattributes` with
    `export-ignore` must **not** drop the file, and a symlink is skipped. The class skips when `git` is absent.
  - Logging: `report.debug("git.<fn>", …)` with the argv and exit code of every git call.
  - Files: `scripts/lib/report.py`, `scripts/lib/git.py`, `tests/test_git.py`, `tests/test_report.py` (every new
    code has a known exit).

- [x] **Task 7: Add the plan parser.** (depends on 6)
  - `scripts/lib/plan.py` (new, stdlib): `parse(path) → Plan` or raise `PlanFormatError(line, message)`.
    `Plan{path, header: dict, mode, tasks: [Task], phase_links: [str]}` and
    `Task{id, title, checked, kind, reason, files: [str], deletes: [str], depends: [int], line}`.
    - The frontmatter reader implements DD3's flat subset exactly: `key: value`, quoted values with `\"` escapes,
      `[a, b]` flow lists of bare or quoted items, `#` comments outside quotes, and blank lines. Anything else
      raises with the line number.
    - Tasks: lines matching `^- \[( |x)\] (?:\*\*)?Task (\d+):` under `## Tasks`, up to the next `## ` heading.
      Field bullets are the following lines indented two or more spaces that match `^\s+- (kind|reason|files|deletes):\s*(.*)$`.
      `(depends on 1, 2)` comes from the task line. Link markup in a title is reduced to its text.
    - Ultra: `phase_links` are the relative links under `## Phase Index`.
    - `classify(rel_path, root) → "config" | "code" | "excluded" | "other"` (DD4). Code places come from
      `knowledge.load("code-places")`, where a `<name>` placeholder matches exactly one path segment (DD13).
      `EXCLUDED_EXTENSIONS` is a module constant with a comment citing ADR 0010 §3.
    - `workspace_of(rel_path)` → the first path segment.
  - `tests/test_plan.py`: header subset edge cases (a quoted colon, an empty list, a comment, a nested map →
    error); full, fast and ultra examples; field bullets; depends; checked state; bold task titles; each class,
    including an `applibs-zims/x.dll` path and a new `_form.js`.
  - Logging: `report.debug("plan.parse", …)` with the header keys and task count; `plan.classify` with each
    decision.
  - Files: `scripts/lib/plan.py`, `tests/test_plan.py`, `tests/fixtures/unit/plans/*.md`.

- [x] **Task 8: Add `check_plan.py`.** (depends on 7)
  - `scripts/check_plan.py`: the CLI, checks, output and codes of DD5 and DD6, built on `lib.plan`,
    `lib.workspace`, `lib.git`, `lib.knowledge` and `route_means.route()`. Parse errors map to `PLAN_UNREADABLE` or
    `PLAN_FORMAT_UNSUPPORTED` (exit `3`). Output goes through `report.render`-compatible printing with the
    `PLAN:` / `AFFECTS:` / `TASK:` / `PROGRESS:` / `OVERLAP SOURCES:` lines first. Module docstring: purpose,
    usage and the exit-code contract, as `route_means.py` has.
  - Implement DD5's folder rules exactly: the first segment below `_COMPONENTS/` is the type; a direct child is the
    `(root)` row; a case-only folder match is `PLAN_ROUTE_MISMATCH`; legacy-as-JSON is detected by
    Filename-with-`.json` inside the row's Folder; the `webasm`-absent message on `PLAN_UNKNOWN_WORKSPACE`.
  - `tests/test_check_plan.py`: every code in DD5's table via `helpers.run_cli` on temp roots, plus each folder rule
    (a nested component name, a site map at the root, `_COMPONENTS/datasource/` against the member `DataSource`,
    `_form.json`, and `webasm` absent). Overlap: a temp repo
    with two branches whose plans share `zims`; one that lists only `webasm`; a completed plan ignored; the same
    blob on a local and a remote ref counted once; an unreadable plan on a ref reported as INFO; no git → `NOT RUN`.
  - Known-bad cases, one directory each under `tests/fixtures/known-bad/` with `expected.json` per E10:
    `plan-unreadable` (3), `plan-format-unsupported` (3), `plan-field-missing`, `plan-field-invalid`,
    `plan-unknown-workspace-applibs`, `plan-base-reason-missing`, `plan-branch-mismatch`, `plan-no-tasks`,
    `plan-task-invalid`, `plan-code-reason-missing`, `plan-ultra-broken`, `plan-file-undeclared-workspace`,
    `plan-kind-mismatch`, `plan-out-of-scope`, `plan-code-file-new`, `plan-route-mismatch`,
    `plan-route-unknown`. They are synthetic and never copied from DGF.
  - Logging: `report.debug("check_plan.<check>", …)` per check with counts; each overlap candidate with its ref and
    decision.
  - Files: `scripts/check_plan.py`, `tests/test_check_plan.py`, `tests/fixtures/known-bad/plan-*/`.

- [x] **Task 9: Add `locate_plan.py` and `inventory_root.py`.** (depends on 7)
  - `scripts/locate_plan.py`: DD5 steps 1–3. `--list` reads progress through `lib.plan`; an entrypoint that does
    not parse is listed with `progress=unreadable`.
  - `scripts/inventory_root.py`: DD9 — stdlib only, never imports `lxml` or `jsonschema` (assert it in a test by
    running with those modules blocked through `sys.modules` injection in a subprocess).
  - Tests: `tests/test_locate_plan.py` — root found from a subdirectory and from an ancestor; depth limit; ambiguous
    roots; each discovery branch, with `--branch` given (no git needed) and from a temp repo's current branch; a
    detached HEAD falling back. `tests/test_inventory_root.py` — counts on a synthetic root, an `applibs` folder
    holding a `.dll`, no `webasm`, no workspace (exit 3), dependencies missing (simulated), and the knowledge stamp
    line.
  - Known-bad: `locate-root-not-set-up`, `locate-root-ambiguous`, `locate-plan-not-found`, `locate-plan-ambiguous`
    (`--branch` passed in `args`), `inventory-root-no-workspace` (3).
  - Logging: `report.debug` for each candidate path checked and each directory classified.
  - Files: `scripts/locate_plan.py`, `scripts/inventory_root.py`, `tests/test_locate_plan.py`,
    `tests/test_inventory_root.py`, `tests/fixtures/known-bad/locate-*/`, `tests/fixtures/known-bad/inventory-*/`.
  - <!-- Commit checkpoint: tasks 6-9 -->

### Phase 4: Change scripts

- [x] **Task 10: Add `check_change.py` — scope, means and planned checks.** (depends on 7)
  - `scripts/lib/runner.py` (new): move `run_validators` out of `tools/run_known_good.py:144-167` unchanged in
    behaviour, as `run(root, files=None)`. `tools/run_known_good.py` imports it. Its output on DGF's samples must be
    unchanged: run `python3 tools/run_known_good.py <dgf-root>` before and after, and compare the verdicts and
    warning counts. **Import `process_checks` and the validator modules inside `run()`**, after `deps.require()`:
    `process_checks.py:32` imports `lxml` at module top, and `check_change.py --skip-validators` and `--help` must
    not need it.
  - `scripts/check_change.py`: DD7's CLI and the `change-scope`, `change-means` and `change-planned` checks, with
    `--changed` and `--base` (changed-set part only; the baseline lands in Task 11). Validators run on the
    `--files` scope or the whole root through `lib.runner`. In this task, every finding counts as new, and
    `baseline` is `NOT RUN (not implemented yet)` — Task 11 replaces this.
  - `tests/test_check_change.py`: each code in the scope, means and planned rows, in `--changed` mode; `.dgf-factory/`
    changes ignored; `--skip-validators` and `--help` run in a subprocess with `lxml` and `jsonschema` blocked
    through `sys.modules` injection.
  - Known-bad: `change-undeclared-workspace`, `change-out-of-scope-applibs`, `change-code-unplanned`,
    `change-code-file-new`, and `change-new-dead-transition` (`--changed M:…/process.xml`, exit `1`,
    `DEAD_TRANSITION`).
  - Logging: `report.debug("check_change.classify", …)` per changed path; per-check counts.
  - Files: `scripts/lib/runner.py`, `tools/run_known_good.py`, `scripts/check_change.py`,
    `tests/test_check_change.py`, `tests/test_run_known_good.py` (still passes), `tests/fixtures/known-bad/change-*/`.

- [x] **Task 11: Add the merge-base baseline, and dry-run it on DGF's samples.** (depends on 10)
  - `scripts/lib/baseline.py` (new): DD8. `compare(head_reports, base_reports, head_root, base_root) → (new,
    pre_existing, fixed)`, with the key and multiset rules. `check_change.py --base` materialises the base tree
    through `git.materialise`, runs `lib.runner` at both trees on the same scope, prints the new findings with their
    own codes, and prints `PRE_EXISTING` and `FIXED` as INFO. A `GitError` makes `baseline` `NOT RUN` with its
    reason.
  - `tests/test_baseline.py` (temp git repos; skips without `git` or the dependencies):
    - a pre-existing error in an untouched file is INFO and exits `0`;
    - an added dead transition exits `1`;
    - **deleting a workflow that an untouched process references is a new `WORKFLOW_UNRESOLVED`** — the case D1
      exists for;
    - a fixed pre-existing error is INFO `FIXED`;
    - lines inserted above a pre-existing finding keep it pre-existing;
    - a duplicated finding is new;
    - `--files` limits the run;
    - no merge-base (an unrelated `--base`) is `NOT RUN` and every finding counts.
  - **Dry run.** Copy DGF's `src/samples/workspaces` into a temporary directory. `git init -b main` it, set
    `user.name` and `user.email` locally, commit, and branch.
    Add a `.dgf-factory/plans/feature-dry-run.md` per DD3 with `affects_workspaces: [dgf]` and one config task.
    Make that change plus one defect: a transition to an undeclared state in a `dgf` process. Run
    `check_change.py --workspaces-root <tmp> --plan … --base main`. **Expect:** exactly the introduced
    `DEAD_TRANSITION` as new; ADR 0014's two true defects among `PRE_EXISTING`; no `CHANGE_*` blocker. Record the
    wall-clock time of the two runs and the counts in this plan's `## Follow-ups found during implementation`. If
    one verify run takes more than 60 s on the samples, add a caching follow-up, but do not build it.
  - Logging: `report.debug("baseline.compare", …)` with the key counts; the materialised tree's blob count and
    write time.
  - Files: `scripts/lib/baseline.py`, `scripts/check_change.py`, `tests/test_baseline.py`, this plan (Follow-ups).
  - <!-- Commit checkpoint: tasks 10-11 -->

### Phase 5: Doctor

- [x] **Task 12: Expect the spine slices, check plugin paths, and check that frontmatter is YAML-safe.** (depends on 5)
  - `skills/dgf-doctor/scripts/doctor.py`: `EXPECTED_SLICES` per DD12. Add `PLUGIN_PATH_DANGLING` (error) as a
    check in the portability section, scanning every shipped `.md` file per DD12's token rule. It emits one
    finding per dangling token, with file and line. Add `SKILL_FRONTMATTER_YAML` (error) to `check_skill_slice`,
    per DD12, one finding per offending key.
  - `skills/dgf-doctor/SKILL.md`: add `PLUGIN_PATH_DANGLING` and `SKILL_FRONTMATTER_YAML` to Step 2's list of
    what exit `1` covers.
  - `tests/test_doctor.py`: expected slices reported present or not yet built; a dangling path is an error with
    file:line; a template token (`<Type>`, `*`) is skipped; an existing path is clean; an unquoted
    `argument-hint: [x]` and an unquoted `description: a: b` are errors; their quoted forms and
    `allowed-tools: Read Bash(python3 *)` are clean.
  - Verify: the doctor on this plugin is CLEAN or has only the known `VALIDATOR_DEPS_MISSING` warning when the
    dependencies are absent.
  - Logging: `trace()` for each token checked (the doctor's existing `DEBUG=1` path).
  - Files: `skills/dgf-doctor/scripts/doctor.py`, `skills/dgf-doctor/SKILL.md`, `tests/test_doctor.py`.
  - <!-- Commit checkpoint: task 12 -->

### Phase 6: Skills

Each skill: before writing it, read the AI Factory source it ports end to end. Keep its step numbering, apply
DD1's keep/drop table, then apply DD14. Every script call and every exit-code table matches Phases 3–4 exactly.
Paths are always `${CLAUDE_PLUGIN_ROOT}/…`, and there are no DGF paths. After each skill, run the doctor: it must
stay CLEAN, which includes `DGF_PATH` and `PLUGIN_PATH_DANGLING`.

- [x] **Task 13: Write `/dgf` — setup.** (depends on 12)
  Port from `.claude/skills/aif/SKILL.md`, keeping only Mode 1 ("analyze existing project"), reshaped for a
  workspaces root.
  - `skills/dgf/SKILL.md`, with steps:
    - **0 Locate:** `locate_plan.py --root-only`. When a `.dgf-factory/config.yaml` already exists this is a re-run;
      otherwise take the root from the argument or the working directory.
    - **1 Inventory:** `inventory_root.py --workspaces-root R`. On exit `3`, STOP ("not a workspaces root"). Relay
      `BASE_WORKSPACE_ABSENT` and `VALIDATOR_DEPS_MISSING` (with the install command, verbatim; never run `pip`).
    - **2 Git:** read `GIT:` from the inventory. With no repository, set `git.enabled: false`, and warn that
      overlap, discovery by branch and the baseline will not run.
    - **3 Ask (one `AskUserQuestion`):** the estate's name and purpose; the DGF version (D4, showing the knowledge
      stamp); the base branch (default from git); the branch prefix; stack overrides of ADR 0005 rules 5–6.
    - **4 Write:** `config.yaml` from `references/config-template.yaml`, and `DESCRIPTION.md` from
      `references/description-template.md`, with the inventory pasted as a table. On a re-run, show a diff and
      edit only managed keys with `Edit`. Never rewrite a file wholesale without confirmation.
    - **5 `.gitignore`:** warn if `.dgf-factory/` is ignored.
    - **6 Next steps:** commit `.dgf-factory/` with `/dgf-commit`, which works without a plan (Task 17). Its
      branch step checks out the base, and plans travel with branches (DD2). Then `/dgf-plan`, and `/dgf-doctor`.
  - Also: the declared-version comparison (DD10); `## Artifact Ownership` — owns `.dgf-factory/config.yaml` and
    `.dgf-factory/DESCRIPTION.md`, writes nothing else.
  - Frontmatter: `allowed-tools: Read Write Edit Glob Grep Bash(python3 *) Bash(git *) AskUserQuestion`;
    `argument-hint: "[workspaces-root]"`; triggers such as "set up dgf-factory", "dgf setup", "initialise the
    workspaces root", "configure dgf".
  - Files: `skills/dgf/SKILL.md`, `skills/dgf/references/config-template.yaml`,
    `skills/dgf/references/description-template.md`.

- [x] **Task 14: Write `/dgf-plan` — fast, full and ultra.** (depends on 13)
  Port from `.claude/skills/aif-plan/SKILL.md` and its `references/`.
  - `skills/dgf-plan/SKILL.md`, with steps:
    - **0 Context:** `locate_plan.py --root-only`, `config.yaml`, `DESCRIPTION.md`, and the skill-context override
      if present. No config → STOP ("run /dgf").
    - **0.1 Git state.**
    - **0.2 Arguments and mode:** `fast|full|ultra`; with none given, ask full versus fast only; ultra is opt-in by
      token. Keep the `original_user_request` contract.
    - **1 Reconnaissance:** `inventory_root.py`. Then 1–3 Explore subagents with DGF-shaped prompts: the processes,
      workflows, forms and components the feature touches; what references them (`WORKFLOW:`, `BASE:`,
      `type` + `name`); how DGF builds it, via the DGF docs MCP (`search_docs`, `how_to_build`,
      `get_recipes_for`, `get_component_doc`).
    - **1.2 Identifier:** slug → `feature/<slug>`; the stem is the branch with `-`. If a plan already exists for the
      stem, ask: refine, replace, or rename.
    - **1.3 Questions:** constraints; when `webasm` is in scope, the base-workspace reason.
    - **1.4 Branch:** first `git status --porcelain`. If the tree is dirty, ask whether to commit it (`/dgf-commit`),
      stash it, or carry it onto the new branch; never discard it. Then `git checkout <base>`,
      `git pull origin <base>`, `git checkout -b`.
    - **2 Analyse:** for each artifact, choose its workspace. For each new component or artifact, run
      `route_means.py <Type|artifact>` and record the `ROUTE:` line in Affected Artifacts. Choose `kind`; `code`
      needs a reason citing `knowledge/composition-specs.md` §3.1, the component doc or the schema, and "quicker in
      JavaScript" is not one. A C#, TypeScript, SQL or assembly need goes under `## Scope` → out of scope, never
      into a task (ADR 0010 §3).
    - **3 Deeper exploration.**
    - **4 Tasks.**
    - **5 Save** per `references/PLAN-FORMAT.md` or `references/ULTRA-FORMAT.md`.
    - **5.1 Check:** `check_plan.py <plan> --workspaces-root R --overlap`. On exit `1`, fix the plan (this skill owns
      it) and re-run, at most 3 times, then STOP with the findings. On exit `2`, surface every `PLAN_OVERLAP` and
      `PARITY_PARTIAL`. On exit `3`, STOP. Offer `git fetch` before the overlap run.
    - **6 Next steps.**
  - `references/PLAN-FORMAT.md`: DD3 and DD4 as the fast/full template with a worked example.
  - `references/ULTRA-FORMAT.md`: port AI Factory's `ULTRA-FORMAT.md`. The frontmatter replaces the marker, tasks
    and fields live only in `index.md`, and the phase file sections are Objective, Current-Artifact Evidence
    (paths, element names, existing family), Files to Change, and per task Intent, Steps, Route (the `ROUTE:` line),
    Validation (the exact `check_change.py --files …` command) and Acceptance. Carry over the Required Detail Gate
    and the Consumer Contract ("the executor stops on drift").
  - Frontmatter: `allowed-tools: Read Write Edit Glob Grep Bash(python3 *) Bash(git *) Agent AskUserQuestion`, plus
    the verified dgf-mcp tool names (DD14); `argument-hint: "[fast | full | ultra] <description>"`; triggers
    "plan a DGF change", "dgf plan", "new feature", "plan this change".
  - Files: `skills/dgf-plan/SKILL.md`, `skills/dgf-plan/references/PLAN-FORMAT.md`,
    `skills/dgf-plan/references/ULTRA-FORMAT.md`.
  - <!-- Commit checkpoint: tasks 13-14 -->

- [x] **Task 15: Write `/dgf-implement` — the composition state machine.** (depends on 14)
  Port from `.claude/skills/aif-implement/SKILL.md` and `references/IMPLEMENTATION-GUIDE.md`.
  - `skills/dgf-implement/SKILL.md`, with steps:
    - **0 State.**
    - **0.0 Resume** after `/clear`: `git status`, `git log`, and the plan's checkboxes versus the changed files.
    - **0.1 Context:** config, DESCRIPTION, the skill-context override and past patches, both if present.
    - **0.2 Find:** `locate_plan.py`. On exit `1`, STOP with its message. On exit `2`, say which fallback applied,
      and ask before proceeding.
    - **1 Load:** `check_plan.py <plan> --workspaces-root R`. On exit `1`, STOP: the plan is defective, so
      `/dgf-plan` must fix it — the executor never re-decides.
    - **2 Progress:** from the `TASK:` and `PROGRESS:` lines.
    - **3 Execute the next unchecked task whose dependencies are checked:**
      - **3.1 Read** the task (and its phase section for ultra). If the artifacts differ from the plan's evidence,
        STOP and report the drift.
      - **3.2 Route each file:** an existing file is edited in its resolved family (run `validate_config.py` on it
        and read `FAMILY:`), never converted. A new file must match `route_means.py`: `json` under
        `FM/_COMPONENTS/<Type>/`, `xml` for a legacy artifact. On exit `2`, surface `PARITY_PARTIAL`. On exit `3`,
        STOP. A `kind: code` file is written only in the places `check_plan` accepted. A file outside the task's
        `files` and `deletes` is never touched: STOP, and ask for a re-plan.
      - **3.3 Compose:** consult `knowledge/` (component catalogue, JSON reader, composition specs, EventBase
        verbs), the vendored schemas under `${CLAUDE_PLUGIN_ROOT}/knowledge/schemas/`, and the DGF docs MCP
        (`get_component_doc`, `get_json_schema_details`, `get_component_examples`,
        `get_xml_property_reference`). Write the files. `deletes` uses `git rm`.
      - **3.4 Validate:**
        `check_change.py --workspaces-root R --plan P --base <git.base_branch> --files <task files>`. Fix **new**
        errors in the files this task wrote, at most 3 attempts, then STOP with the findings. Mention
        `PRE_EXISTING` findings, and never fix them unasked.
      - **3.5 Mark** `- [ ]` → `- [x]` in the plan entrypoint. This is the only write to the plan.
      - **3.6 Commit checkpoint:** when the Commit Plan says so, suggest `/dgf-commit`.
    - **4 Session persistence.**
    - **5 Completion:** suggest `/dgf-verify`.
    - Also `--list` (`locate_plan.py --list`), `@<plan>` and `status` arguments.
  - ADR 0010 §3 as a Critical Rule: meeting a need for C#, TypeScript, SQL or an assembly stops the task with exit-1
    semantics, reports what code is needed, and writes nothing.
  - `references/IMPLEMENTATION-GUIDE.md`: progress display, blocker handling, the per-task validate loop, resume.
  - Frontmatter: `allowed-tools: Read Write Edit Glob Grep Bash(python3 *) Bash(git *) AskUserQuestion`, plus the
    verified dgf-mcp tools; `argument-hint: "[--list] [@plan] [task-id | status]"`; triggers "implement the plan",
    "dgf implement", "continue implementation", "execute the plan".
  - Files: `skills/dgf-implement/SKILL.md`, `skills/dgf-implement/references/IMPLEMENTATION-GUIDE.md`.

- [x] **Task 16: Write `/dgf-verify` — the change gate.** (depends on 15)
  Port from `.claude/skills/aif-verify/SKILL.md` and its `references/`.
  - `skills/dgf-verify/SKILL.md`, with steps:
    - **0.0 Config.**
    - **0.1 Gate contract:** read `references/GATE-RESULT-CONTRACT.md`.
    - **0.2 Find:** `locate_plan.py`.
    - **0.3 Plan:** `check_plan.py --overlap`.
    - **1 Task completion audit:** every checkbox checked; each unchecked task is a blocker.
    - **2 The change:** `check_change.py --workspaces-root R --plan P --base <git.base_branch>`, the whole root.
      Quote every `ERROR` line; surface every `WARN`; list `PRE_EXISTING` as a count plus the first 20 lines.
    - **3 Code tasks:** list each `kind: code` task with its reason for the reviewer (ADR 0005 rule 2).
      `frontend-tests` is `NOT RUN`: the project's CI runs them (ADR 0010 §2, ADR 0014 §5).
    - **4 Base workspace:** when `webasm` is declared, restate the reason, and confirm the whole-root run covered
      every application (ADR 0005 rule 3).
    - **5 Report:** status by DD11's table; then the gate block, and nothing after it.
    - Also `--strict`.
  - The skill is **read-only**: no `Write` or `Edit` in its tools.
  - `references/GATE-RESULT-CONTRACT.md`: DD11 — the fields, the status table, the allowlist, the required checks,
    and the milestone-10 fields marked not yet emitted.
  - Frontmatter: `allowed-tools: Read Glob Grep Bash(python3 *) Bash(git *) AskUserQuestion`;
    `argument-hint: "[--strict]"`; triggers "verify the change", "dgf verify", "check my work", "did we miss
    anything".
  - Files: `skills/dgf-verify/SKILL.md`, `skills/dgf-verify/references/GATE-RESULT-CONTRACT.md`.

- [x] **Task 17: Write `/dgf-commit` — conventional commits.** (depends on 15)
  Port from `.claude/skills/aif-commit/SKILL.md`.
  - `skills/dgf-commit/SKILL.md`, with steps:
    - **1 Analyse** staged changes.
    - **2 Plan:** `locate_plan.py`. Read the Commit Plan. On `PLAN_NOT_FOUND`, continue without one: skip Step 3's
      grouping and Step 4's check, and say so in one line. This is the path for committing `.dgf-factory/` right
      after `/dgf`, where the suggested message is `chore(dgf): set up dgf-factory`. `ROOT_NOT_SET_UP`,
      `ROOT_AMBIGUOUS` and `PLAN_AMBIGUOUS` still STOP.
    - **3 Group** per the Commit Plan.
    - **4 Warn-only gate:**
      `check_change.py --workspaces-root R --plan P --base <base> --skip-validators`. On exit `1`, show the findings
      and ask whether to commit anyway, since `/dgf-verify` will fail on them.
    - **5 Type.**
    - **6 Scope:** the single workspace touched (`feat(zims): …`), `webasm` for the base, and when several are
      touched, no scope, with the workspaces named in the body.
    - **7 Message.**
    - **8 Commit.**
    - **9 Push prompt,** unless `git.skip_push_after_commit`.
  - It never modifies the plan.
  - Frontmatter: `allowed-tools: Read Glob Grep Bash(git *) Bash(python3 *) AskUserQuestion`;
    `argument-hint: "[scope or context]"`; triggers "commit", "dgf commit", "save changes", "create commit".
  - Files: `skills/dgf-commit/SKILL.md`.
  - <!-- Commit checkpoint: tasks 15-17 -->

### Phase 7: Integration and documentation

- [x] **Task 18: Walk the spine's scripts end to end on a scratch estate.** (depends on 16, 17)
  - Reuse Task 11's scratch copy, or make a fresh one. Run in skill order:
    - `inventory_root.py`;
    - `locate_plan.py --root-only`;
    - a hand-written **ultra** bundle per `skills/dgf-plan/references/ULTRA-FORMAT.md`, with
      `affects_workspaces: [dgf, webasm]` and a `base_workspace_reason`, one `config` task per family (a JSON
      component, a legacy `_form.xml` edit) and one `code` task editing an existing `js/` file;
    - `check_plan.py --overlap`, with a second branch holding an overlapping plan;
    - the changes;
    - `check_change.py --base main`;
    - `check_change.py --skip-validators`.
  - **Expect:** exit `2` from `check_plan` (`PLAN_OVERLAP`, plus `PARITY_PARTIAL` if the component is ◐), and exit
    `0` or `2` from `check_change`, with no new errors.
  - Then introduce each of: an undeclared workspace edit, a new `js/` file, and a `.cs` file. Each must block with
    its code.
  - Record commands, exits and surprises in `## Follow-ups found during implementation`. Fix script defects here.
    A format defect goes back into ADR 0017 **as an erratum only if it is a fact**; otherwise, STOP and ask.
  - Run the doctor over the plugin: all nine expected slices, CLEAN.
  - **Add `tests/test_skill_contracts.py`**, which keeps the prompts and the scripts from drifting apart (R1):
    - every backticked token in shipped skill Markdown (`skills/**/*.md`) that matches `^[A-Z][A-Z0-9]*(_[A-Z0-9]+)+$`
      is a key of `report.CODES`, or a finding id `doctor.py` emits (collect them from its `error(`/`warn(` calls).
      A short allowlist covers non-code tokens such as environment variables (`DGF_WORKSPACES_ROOT_PATH`,
      `LOG_LEVEL`), with a comment per entry;
    - every `--flag` that follows a `${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py` call on the same line appears in that
      script's `--help` output.
  - Scratch repositories are made with `git init -b main` and a local `user.name`/`user.email`.
  - Files: this plan (Follow-ups); `tests/test_skill_contracts.py`; fixes in the scripts from Phases 3–4 and in
    the skills from Phase 6, as needed.

- [x] **Task 19: Documentation checkpoint.** (depends on 18)
  Run `/aif-docs` with this scope:
  - **New `docs/pipeline.md`:** the five skills and how a change flows; `.dgf-factory/` and its config; the plan
    format for readers (ADR 0017); the scripts and their exit codes; change-relative gates (ADR 0018); the declared
    version (ADR 0019); the milestone-10 gate fields as not yet emitted. Name both schema families wherever it says
    "schema" (E11 section 2). Add it to `REQUIRED_DOCS` in `tools/check-dual-schema-docs.sh`.
  - `README.md` and `AGENTS.md`: the structure tree (five skills, four scripts, `lib/git.py`, `lib/plan.py`,
    `lib/runner.py`, `lib/baseline.py`); "Not yet created"; Key Entry Points; a link to `docs/pipeline.md`.
  - `docs/getting-started.md`: trying the spine on a copy of DGF's samples.
  - `docs/architecture.md` and `.ai-factory/ARCHITECTURE.md`: which slices exist now; `lib/gate_result.py` is still
    milestone 10.
  - `docs/skill-authoring.md` §"Reading a validator's output": the `PLAN:`/`TASK:`/`CHANGE:`/`WORKSPACE:`/`ROOT:`
    lines, and `PRE_EXISTING`/`FIXED`.
  - `.ai-factory/DESCRIPTION.md` §"Current State" and the facts table: E13, E14, E17 and E18 as verified facts.
  - Verify: `tools/check-dual-schema-docs.sh` passes all sections (at most the known warning baseline), and the
    unit suite passes.
  - Files: `docs/pipeline.md`, `README.md`, `AGENTS.md`, `docs/getting-started.md`, `docs/architecture.md`,
    `docs/skill-authoring.md`, `.ai-factory/ARCHITECTURE.md`, `.ai-factory/DESCRIPTION.md`,
    `tools/check-dual-schema-docs.sh`.

- [x] **Task 20: Mark the milestone done.** (depends on 19)
  - Once `/aif-verify` passes on this branch, change `.ai-factory/ROADMAP.md`'s "Pipeline Spine" to `- [x]`, relink
    ADRs 0017–0019 in its line, and add `| Pipeline Spine | <date> |` to `## Completed`. Evidence: the verify
    result and the doctor's nine-slice report.
  - Files: `.ai-factory/ROADMAP.md`.
  - <!-- Commit checkpoint: tasks 18-20 -->

## Risks

- **R1 — Prompt length.** Five long prompt-programs rest on instruction-following. *Mitigation:* discovery, plan
  validity, routing, scope, means and the baseline are all scripts. The prompts decide only what needs judgement.
  `tests/test_skill_contracts.py` (Task 18) fails when a prompt quotes a finding code or a flag the scripts do not
  have.
- **R2 — Baseline cost.** Two whole-root validator runs per `/dgf-verify`. *Mitigation:* Task 11 measures it on
  DGF's samples. Caching is a follow-up, not built speculatively.
- **R3 — `webasm` outside the estate's root** (E18). `BASE:` references then never resolve. *Mitigation:* the
  inventory warns (`BASE_WORKSPACE_ABSENT`), and the baseline keeps pre-existing unresolved references from
  blocking. A *new* `BASE:` reference still blocks, which is honest: it cannot be verified.
- **R4 — Plugin MCP tool names.** If `allowed-tools` names are wrong, they pre-approve nothing. *Mitigation:*
  DD14's verification step. An unverified name is omitted, never guessed.
- **R5 — Stale remote refs** hide other teams' plans from the overlap check. *Mitigation:* the report says how
  fresh its sources are, and `/dgf-plan` offers a fetch.
- **R6 — A strict plan grammar.** A hand edit in richer YAML becomes `PLAN_UNREADABLE`. *Mitigation:* an exact
  line-numbered message, and `/dgf-plan` re-runs the check after every save.
- **R7 — Code-place facts depend on deployment configuration** outside the root (E14; the sample `custom.css`
  mapping is commented out). *Mitigation:* the table says "a deployment bind-mount", not "always loaded", and
  global files are edit-only.
- **R8 — `kind: code` is a judgement** (ADR 0010, Negative). *Mitigation:* a mandatory reason, listed for the
  reviewer by `/dgf-verify`. A size budget stays a follow-up.
- **R9 — Until milestone 10, the gate block is prompt-assembled.** *Mitigation:* its status comes from a
  mechanical table of exit codes (DD11), and every `NOT RUN` stays visible.

## Follow-ups

- Milestone 10: `scripts/lib/gate_result.py`; `schema_family`, `checks_run`, `affected_components`,
  `affected_processes`; the narrowing filter's interaction with `checks_run` (ADR 0004).
- `scriptPath`: find the attribute that declares it, and decide whether a new file it names is permissible.
- The version gate itself, once a behavioural fact with `applies:` exists; it reads `dgf.version` (ADR 0019).
- Whether files under `FM/` that are not JSON or XML (templates) count as configuration.
- Whether estates commonly lack `webasm` (E18). If they do, consider a `--base-workspace <path>` option.
- The baseline's two trees differ in one way (found by `/aif-verify`, 2026-09-25): the working-tree run
  validates git-ignored and symlinked files, which the materialised base tree never holds, so a
  finding in one always counts as new. That is stricter, never looser. Decide whether the head run
  should skip what `git ls-files --others --ignored --exclude-standard` lists, and symlinks.
- A size budget for `kind: code` (ADR 0010 follow-up), after the first real plans.

## Follow-ups found during implementation

<!-- Tasks 11 and 18 record their dry-run commands, exits, timings and surprises here. -->

- **Task 5 — `code-places` has a `Filename` column (deviation from DD13).** A form name may contain
  `/` (`knowledge/composition-specs.md` §2.1; e.g. `webasm/FM/_DATA/PWF_Process/_forms/ASP.Net/…/designer.aspx/`),
  and `FormManager.GetXmlWorkPath` joins it unsplit, so `_form.js` can sit several folders below
  `_forms/`. DD13's "a placeholder is exactly one segment" would miss those forms. The table's rule
  is now: a placeholder is one segment, except one that ends the path, which is one or more.
  `_form.js` is the form-script row's `Filename` cell (`—` elsewhere, meaning any file with the
  extension at any depth) instead of a constant in `lib/plan.py`, so the fact stays in `knowledge/`
  (DD4). Header: `Place | Path | Filename | Extension | Loaded by | New file loaded`.
- **Task 6 — `lib/git.py` paths are relative to the directory given.** Every call runs as
  `git -C <root>`, and `diff --relative`, `ls-files`, `ls-tree` and `<ref>:./<path>` all read and
  print paths relative to it, so no function takes a top-level prefix. `changed()` returns
  `Change(status, path, old)`: a rename keeps its old path, which DD7's scope check needs.
- **Task 8 — two additions to DD5.** A dependency cycle is `PLAN_TASK_INVALID` (an executor could
  never start it). For the overlap scan, a full or ultra plan's own path at *any* ref is the plan
  itself (its stem is its branch), not only at refs ending in its branch; `PLAN.md` still counts
  per content. `report.render()` gained `lines=` and `summary=` so `check_plan.py` and
  `check_change.py` print their own leading lines through the one renderer.
- **Task 9 — a finished plan is never a discovery fallback** (DD5 step 2 counted every
  entrypoint). After a few merges `plans/` holds other branches' completed plans, and a lone
  completed plan would otherwise be offered as this branch's. The inventory counts exact-case
  files only: DGF's samples hold 339 `_workflow.xml` (ADR 0016's 341 includes two
  `_workflow.XML`, which a Linux runtime never opens).
- **Task 5 — E14 refined.** The UI shell ships its own default `formhelper.js`, `formshared.js` and
  `custom.css` under `src/DGF.UI/src/assets/`; a deployment bind-mount replaces them. The ledger
  lists all three. `docker-compose.ecouncil.yml:65` mounts a live `custom.css` from outside the
  workspaces root (only the ZIMS one is commented out).
- **Task 3 — E17 line numbers.** The UI version is stamped at `src/DGF.UI/Dockerfile:1, 30, 36-42`,
  not `:27-30`; `app-settings.type.ts:9`, not `:8`. ADR 0019 cites the corrected lines.
- **Task 10 — the runner moved unchanged.** `tools/run_known_good.py <dgf-root>` printed byte-identical
  output before and after `scripts/lib/runner.py` took over (CLEAN; 71 excused by `EXCEPTION`, 9 by
  `EXPECTED_EXTERNAL`). One addition: the runner drops validate_config's
  `NOT RUN: process-semantics (run validate_process.py)` for a file it also gave to validate_process,
  since that pointer is then satisfied; the known-good tool never printed it.
- **Task 11 — each validator pass runs with the working directory at its tree's root**, so a finding's
  file, and every path a message shows through `cli.display()`, is root-relative at both trees. The
  key then only has to strip absolute root forms (`baseline.root_forms`: absolute and symlink-resolved
  only — a relative form such as `.` would be stripped from every message).
- **Task 11 — dry run on DGF's samples** (`aa1d5c4c2`, 2026-09-25). A copy of `src/samples/workspaces`
  in the scratchpad, `git init -b main`, committed, branch `feature/dry-run`; plan
  `.dgf-factory/plans/feature-dry-run.md` with `affects_workspaces: [dgf]` and one checked config task on
  `dgf/FM/_PROCESS/DGF.Demo.EService/process.xml`; that file's signing transition retitled, and a
  `<Transition state="Archive">` added to `Issue`.
  `check_change.py --workspaces-root <copy> --plan <plan> --base main` → **exit 1**. New: exactly one
  error, `DEAD_TRANSITION dgf/FM/_PROCESS/DGF.Demo.EService/process.xml:120`. Pre-existing: 2552, among
  them ADR 0014's two true defects (`WORKFLOW_UNRESOLVED` at `ZIMS4_InspectionBorder/process.xml` L5
  and L20, `CHANGE_STATE_STATE_UNDECLARED` at `Expert.MoveTaskTo/_workflow.xml` L15). Fixed: 0. No
  `CHANGE_*` finding. 3116 files validated per tree. **Wall-clock 5.2 s** for the materialise and both
  runs (one known-good run alone is 2.1 s), far under the 60 s threshold, so no caching follow-up.
- **Task 12 — two small widenings of DD12.** A plugin-path token that contains an ellipsis (`…` or `...`)
  is a template too: the doctor's own SKILL.md prose cites `${CLAUDE_PLUGIN_ROOT}/…`. A token also ends
  at `]`, and trailing `.,;:` are dropped, so prose punctuation is not read as part of a path.
  `SKILL_FRONTMATTER_YAML` also flags an unquoted `|` or `>` (a block scalar the flat parser would read
  as that one character).
- **Tasks 13–14 — tool names verified (DD14, R4).** The `claude-code-guide` agent confirmed from the
  Claude Code docs (2026-09-25): the subagent tool is `Agent` (renamed from `Task` in v2.1.63; `Task`
  still works as an alias; `code.claude.com/docs/en/sub-agents.md`); a plugin's MCP tools are
  `mcp__plugin_<plugin>_<server>__<tool>`, so `mcp__plugin_dgf-factory_dgf-mcp__<tool>`, usable in
  `allowed-tools` (`code.claude.com/docs/en/mcp.md`); `Bash(python3 *)` with a space is the prefix form
  (`code.claude.com/docs/en/skills.md`). Each skill lists only the dgf-mcp tools it calls, no wildcard.
- **Task 14 — `check_plan.py` checks more of an ultra bundle.** The Required Detail Gate's integrity
  list had three statically checkable items left to the prompt: an orphan phase file, a task with
  zero or several `## Task N` sections (or a section with no task), and a task checkbox in a phase
  file. All three are now `PLAN_ULTRA_BROKEN` (Rules: determinism before prompting).
- **Task 14 — Step 5.1 treats `PLAN_UNREADABLE` and `PLAN_FORMAT_UNSUPPORTED` like exit `1`**: the
  skill wrote that header, so it fixes it within the same three attempts. Every other exit `3` still
  stops. The plan said "On exit 3, STOP" without distinguishing.
- **Tasks 13–14 — no-git estates.** A full or ultra plan still carries `branch: <prefix><slug>` as its
  name when `git.enabled` is false; no branch is created, and `locate_plan.py` falls back to the lone
  active plan.
- **Task 15 — `/dgf-implement` without git** validates a task with `check_change.py --changed A:/M:/D:…`
  built from what the task wrote (no baseline, so every finding in its files counts as new), and asks the
  user to delete a `deletes` file itself: the skill's only delete is `git rm`.
- **Task 16 — the required `validators` check is the whole-root run** (`NOT RUN` only when skipped). A
  validator's per-file `NOT RUN` lines (`json-format (annotation-only)`, `component-types (a Process
  document names no component types)`) are not-applicable notes; counting them as required would make
  every verify `warn`. `GATE-RESULT-CONTRACT.md` states this, and the blocker id forms (`task-<N>`, the
  finding's code, `not-run-<check>`, `<script>-exit-3`).
- **Task 17 — `/dgf-commit` keeps AI Factory's rule against AI co-author trailers**, as ported. Commits
  made while building this plugin carry the session's attribution; the rule governs the shipped skill.
- **Task 18 — end-to-end walk** (2026-09-25, a fresh scratchpad copy of DGF's samples at `aa1d5c4c2`,
  `git init -b main`, `.dgf-factory/config.yaml` committed on `main` as `/dgf` would write it):
  - `inventory_root.py` → exit `0`: `dgf`, `webasm` (base), `zims`; `GIT: … root=.`; dependencies present.
  - `locate_plan.py --root-only` from `dgf/FM/` → exit `0`, the root found by ancestor search.
  - An ultra bundle on `feature/e2e-apply-button` (`affects_workspaces: [dgf, webasm]` with a
    `base_workspace_reason`): Task 1 a new `dgf/FM/_COMPONENTS/Button/ApplyNow.json`, Task 2 an edit to
    the existing `EServiceApply/_form.xml`, Task 3 `kind: code` editing the existing
    `webasm/js/forms.shared.js`. `locate_plan.py` → `mode=ultra source=branch`, exit `0`.
  - `check_plan.py --overlap`, with `feature/other` holding an active plan on `[dgf]` → **exit `2`**, one
    `PLAN_OVERLAP` naming `feature-other.md` at `feature/other` and `webasm`. No `PARITY_PARTIAL`: Button
    is ✓ (parity row 4).
  - Per task, `check_change.py --base main --files <file>` → exit `0` each (the `.js` file is validated
    by nothing: `Validated: 0`). Checkboxes ticked; `locate_plan.py --list` → `progress=3/3`.
  - `check_change.py --base main` (the gate run) → **exit `0`**: `CHANGED: 3`, new 0/0, pre-existing
    2552, 3117 files validated, 5.2 s. `--skip-validators` → exit `0`, `NOT RUN: validators`, `baseline`.
  - Each alone, then reverted: an edit in `zims` → exit `1` `CHANGE_UNDECLARED_WORKSPACE`; a new
    `webasm/js/new-helper.js` → exit `1` `CHANGE_CODE_FILE_NEW` and `CHANGE_CODE_UNPLANNED`; a
    `Handler.cs` under `dgf/FM/_DATA/` → exit `1` `CHANGE_OUT_OF_SCOPE`. Clean again → exit `0`.
  - The doctor: all nine expected slices reported (six present, three not yet built), CLEAN.
  - No script defect and no format defect found. Two observations, both intended: an undeclared file is
    reported twice (`CHANGE_UNDECLARED_WORKSPACE`, error, and `CHANGE_UNPLANNED_FILE`, warning); and the
    gate run prints the validators' per-file `NOT RUN` lines, which `GATE-RESULT-CONTRACT.md` keeps in
    the prose and out of the blockers.
  - `tests/test_skill_contracts.py` passes; planting an unknown code and an unknown flag in a skill made
    it fail on both, naming file and line.
- **`/aif-verify`, first pass (2026-09-25) — six blocking defects, all fixed in this branch.** Two
  independent read-only audits (Tasks 1–12, Tasks 13–19), plus the checks:
  - **B1:** `route_means.py` exited 3 for the loader folders `DataSource`, `Template` and `Endpoints`,
    which `check_plan.py` accepts, so `/dgf-plan` and `/dgf-implement` would stop on a new
    DataSource — the format's own worked example. `route_means.py` now routes a loader folder to
    `json` (rule 1a, from the `component-folders` table), and the skills pass the folder name.
  - **B2:** `@<bundle-dir>` reached `check_plan.py` as a directory (exit 3). `lib.plan.entrypoint()`
    now resolves a bundle directory to its `index.md` for `check_plan.py` and `check_change.py`.
  - **B3:** a deletes-only task gave `check_change.py` an empty `--files` (exit 3). `/dgf-implement` now
    runs a task with `deletes` over the whole root, the only run that shows what the removal broke.
  - **B4:** a missing `plan_format` was `PLAN_FORMAT_UNSUPPORTED` (exit 3, "`plan_format: None`"); it is
    now `PLAN_FIELD_MISSING`, and the other header checks still run.
  - **B5:** `git.materialise` deadlocked when a blob write or read failed with many objects still queued
    (the feeder was joined before git's output pipe closed), and let an `OSError` escape as a traceback.
    Git is now killed first when the stream is abandoned, and write errors are `GitError`. The new test
    hangs against the old code (killed by a 60 s alarm) and passes in 3 s against the new.
  - **B6:** `test_unquoted_yaml_indicators_block` failed under a Python without `lxml`, because the
    doctor also warns `VALIDATOR_DEPS_MISSING` there.
  - Also fixed: `check_change.py` split a bare `affects_workspaces: zims` into letters; a file listed by
    two tasks was routed twice; quoted flow-list items could not hold `,` or `]`; the doctor's
    plugin-path check is now exact-case and its YAML check also flags `- `, a trailing `:` and an
    unclosed quote; the inventory's git line survives a top-level spelled differently;
    `test_baseline`'s duplicate test now duplicates one key; `test_skill_contracts` reads `\`
    continuation lines; and prompt and doc nitpicks (no-git config defaults, staging `.dgf-factory/`
    before `/dgf-commit`, refining on an existing branch, `--list` paths, Step 0.0 order, the ultra
    Commit Plan's place, the family spellings, the known-bad count).
- **Task 20 — evidence.** `/aif-verify` passed on the second pass (2026-09-25): 427 tests on the venv, OK
  under the system interpreter without `lxml`; doctor CLEAN with all nine expected slices reported (six
  present); stamps, drift (255 sources) and the known-good run CLEAN, the last byte-identical to before
  the runner moved; the docs check at its known dependency-warning baseline.
