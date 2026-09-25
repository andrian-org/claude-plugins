# dgf-plan — Plan File Format (fast and full)

The single-file plan format, decided in ADR 0017. `check_plan.py` reads it exactly; anything
it cannot read is `PLAN_UNREADABLE` with a line number. For an ultra bundle, read
`ULTRA-FORMAT.md` — its `index.md` uses this same header and task format.

## Where the file goes

| Mode | Path (relative to the workspaces root) | `branch` |
|---|---|---|
| fast | `paths.plan` — default `.dgf-factory/PLAN.md` | the current branch, or `none` off-branch |
| full | `paths.plans/<stem>.md` — default `.dgf-factory/plans/<stem>.md` | `<branch_prefix><slug>` |

`<stem>` is the `branch` with every `/` replaced by `-`: branch `feature/zims-inspection-fee` is
`feature-zims-inspection-fee.md`. The filename carries no workspace. Plan ids are always this
stem, never a sequence number.

## The header — flat YAML frontmatter

```yaml
---
plan_format: 1
mode: full                          # fast | full | ultra
branch: feature/zims-inspection-fee # "none" only for a fast plan made off-branch
created: 2026-09-25                 # YYYY-MM-DD
affects_workspaces: [zims, webasm]  # workspace directory names; never empty
base_workspace_reason: "The fee DataSource is shared by every application's payment page"
---
```

Only this flat subset of YAML is read:

- `key: value`, `key: "quoted value"` (escape `"` as `\"` and `\` as `\\`), and
  `key: [a, b]` flow lists, whose items may be quoted.
- Blank lines, and `#` comments outside quotes.
- **Nothing else.** No nested maps, no `- item` block lists, no multi-line values, no single
  quotes. A value containing `: ` must be double-quoted.

The keys are exactly these six, plus `archived`, which is reserved and ignored. Any other key is
`PLAN_FIELD_INVALID`.

| Key | Rule | Finding when wrong |
|---|---|---|
| `plan_format` | `1` | `PLAN_FORMAT_UNSUPPORTED` |
| `mode` | `fast`, `full` or `ultra` | `PLAN_FIELD_INVALID` |
| `branch` | the plan's branch; `none` only on a fast plan; the stem of a full plan | `PLAN_FIELD_INVALID`, `PLAN_BRANCH_MISMATCH` |
| `created` | a real `YYYY-MM-DD` date | `PLAN_FIELD_INVALID` |
| `affects_workspaces` | a non-empty list; each a directory under the root with an exact-case `FM/`, or `webasm` | `PLAN_FIELD_MISSING`, `PLAN_UNKNOWN_WORKSPACE` |
| `base_workspace_reason` | required when `webasm` is listed: why every application must see this change | `PLAN_BASE_REASON_MISSING` |

An `applibs*` folder is never a workspace: it holds plugin assemblies and no `FM/`
(`${CLAUDE_PLUGIN_ROOT}/knowledge/composition-specs.md` §1.2).

## The body — sections in this order

```markdown
# Implementation Plan: <name>

## Original Request
<the user's words, verbatim — only when the user gave a request>

## Scope
<why each workspace in affects_workspaces is in; what is out of scope and why>

## Affected Artifacts
| Artifact | Workspace | State | Family | Route evidence |
|---|---|---|---|---|

## Commit Plan
<only when there are 5 or more tasks>

## Tasks

## Risks
```

- **Scope** names every need this plugin does not implement — C#, TypeScript or Angular, SQL,
  plugin assemblies, a new deployment bind-mount — as out of scope for a general coding flow.
  None of them becomes a task.
- **Affected Artifacts** lists every file the tasks touch. `State` is `existing` or `new`.
  `Family` is `json` or `xml` for configuration — `validate_config.py`'s `FAMILY:` line calls the
  XML family `xsd`; either spelling will do — and `code` for a code place. For an existing file
  the evidence is its family as it is on disk; for a new one it is the `ROUTE:` line
  `route_means.py` printed.
- **Commit Plan** groups tasks into commits every 3–5 tasks, each with a conventional-commit
  message.

## Tasks

A task is a checkbox line under `## Tasks`, optionally grouped under `### Phase N: <name>`
headings, followed by field bullets indented two spaces:

```markdown
- [ ] Task 3: Hide the fee panel until the gateway confirms payment (depends on 1, 2)
  - kind: code
  - reason: No EventBase verb reads the gateway callback (knowledge/composition-specs.md §3.1)
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.js
```

| Field | Rule |
|---|---|
| `Task N:` | a unique integer; `(depends on N, M)` names existing tasks and forms no cycle |
| `kind:` | mandatory: `config` or `code` |
| `reason:` | mandatory for `code`: the configuration route tried, and why it cannot express the change, citing the component doc, the schema or the `EventBase` verb list. "Quicker in JavaScript" is not a reason. Optional for `config` |
| `files:` | the files the task creates or edits, comma-separated, relative to the workspaces root with `/`; the first segment is a workspace listed in `affects_workspaces` |
| `deletes:` | the files the task removes |

A task needs `files:`, `deletes:` or both. Other indented lines under a task — notes, steps —
are allowed and ignored by the scripts.

## Which files a task may name

Every path is in exactly one class (ADR 0017 §3). Where script and style may go is read from
the `code-places` table in `${CLAUDE_PLUGIN_ROOT}/knowledge/composition-specs.md` §5.

| Class | Paths | May appear in |
|---|---|---|
| config | `<ws>/FM/**/*.json`, `<ws>/FM/**/*.xml` | a `kind: config` task |
| code | a form's `_form.js`; `.js` under `<ws>/js/` or `<ws>/FM/js/`; `.css` under `<ws>/css/` | a `kind: code` task — a **new** file only for `_form.js`; files under `js/`, `FM/js/` and `css/` are edited, never created |
| excluded | `.cs .csproj .sln .ts .tsx .sql .dll .exe .html .cshtml .razor`, or anything under `applibs*` | no task — name the need under `## Scope` |
| other | anything else | a warning; this plugin does not author it |

A new configuration file must follow its route:

- **Component JSON** goes under `<ws>/FM/_COMPONENTS/<Type>/`, where `<Type>` is spelled exactly
  as the ComponentType member or the loader folder (`DataTable`, `DataSource` — not
  `datasource`), and only when `route_means.py <Type>` answers `json`. The loader folders —
  `DataSource`, `Template`, `Endpoints` — are always JSON: their loaders read nothing else
  (`${CLAUDE_PLUGIN_ROOT}/knowledge/json-reader.md` §4). A name may continue into subfolders
  (`Page/SiteMap/loginPage.json`); a file directly under `_COMPONENTS/` is the site map.
- **The five legacy types** — form, workflow, process, settings, view — stay XML, at the folder
  and filename `route_means.py` prints. Never `_form.json` or `process.json`.
- An **existing** file is edited in the family it is in. Moving it from XML to JSON is a
  migration, and a migration is its own task.

## A worked example

```markdown
---
plan_format: 1
mode: full
branch: feature/zims-inspection-fee
created: 2026-09-25
affects_workspaces: [zims, webasm]
base_workspace_reason: "The fee DataSource is shared by every application's payment page"
---

# Implementation Plan: Inspection fee on the application form

## Original Request

Show the inspection fee on the ZIMS application form, and hide it until payment is confirmed.

## Scope

- `webasm`: the fee DataSource is shared by every application's payment page, so it lives in
  the base workspace and is referenced as `BASE:InspectionFee`.
- `zims`: the application form shows the fee.
- Out of scope: the payment gateway's callback endpoint is C# in the gateway plugin — a general
  coding flow.

## Affected Artifacts

| Artifact | Workspace | State | Family | Route evidence |
|---|---|---|---|---|
| `webasm/FM/_COMPONENTS/DataSource/InspectionFee.json` | webasm | new | json | `` ROUTE: json <workspace>/FM/_COMPONENTS/DataSource/<name>.json — `DataSource` is a loader folder: DataSourceLoader reads it as JSON (knowledge/json-reader.md §4) `` |
| `zims/FM/_DATA/Inspection/_forms/Apply/_form.xml` | zims | existing | xml | on disk as `_form.xml` |
| `zims/FM/_DATA/Inspection/_forms/Apply/_form.js` | zims | new | code | a form's own script (`code-places`, `form-script`) |

## Tasks

### Phase 1: Fee data
- [ ] Task 1: Add the inspection-fee DataSource
  - kind: config
  - files: webasm/FM/_COMPONENTS/DataSource/InspectionFee.json
- [ ] Task 2: Show the fee on the application form (depends on 1)
  - kind: config
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.xml

### Phase 2: Behaviour
- [ ] Task 3: Hide the fee panel until the gateway confirms payment (depends on 2)
  - kind: code
  - reason: No EventBase verb reads the gateway callback (knowledge/composition-specs.md §3.1), and toggleVisible needs a value the form does not hold
  - files: zims/FM/_DATA/Inspection/_forms/Apply/_form.js

## Risks

- Every application's payment page reads the new DataSource once it is referenced; only
  `zims` references it in this plan.
```

`check_plan.py` on this plan prints one `TASK:` line per task and `PROGRESS: 0/3`. Because
`webasm` is listed, the overlap check reports every other active plan (`PLAN_OVERLAP`, a
warning).
