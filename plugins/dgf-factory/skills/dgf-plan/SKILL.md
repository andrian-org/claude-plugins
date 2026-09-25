---
name: dgf-plan
description: Plan a change to a DGF estate — a fast, full or ultra plan that says which workspaces it touches and, per task, whether it composes configuration or writes a little JavaScript or CSS, and why. Use for "plan a DGF change", "dgf plan", "new feature", "plan this change", "plan the workflow change", "ultra plan".
argument-hint: "[fast | full | ultra] <description>"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) Bash(git *) Agent AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__search_docs mcp__plugin_dgf-factory_dgf-mcp__how_to_build mcp__plugin_dgf-factory_dgf-mcp__get_recipes_for mcp__plugin_dgf-factory_dgf-mcp__get_component_doc
disable-model-invocation: false
version: 0.1.2
---

# DGF Plan — Plan a Change to the Estate

Turn a request into a plan `/dgf-implement` can execute without re-deciding anything: which
workspaces change, which artifacts, in which family, and — for the rare task that is not
configuration — why configuration cannot express it.

A DGF system is mostly configuration. The order of means is fixed (ADR 0010): modern JSON
under `FM/_COMPONENTS/` first, legacy XML where no JSON alternative exists, and a little
JavaScript or CSS only where configuration cannot. C#, TypeScript, Angular, SQL and plugin
assemblies are never a task.

This skill ports AI Factory's `/aif-plan`, step for step. It drops Handoff, worktrees and
`--parallel`, research context, roadmap linkage, sequential ids, and the testing, logging and
docs questions: the validators are a DGF plan's tests.

## Workflow

### Step 0: Load context

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --root-only
```

- Exit `1` (`ROOT_NOT_SET_UP`) → **STOP**: "run `/dgf` in the workspaces root first".
  `ROOT_AMBIGUOUS` → **STOP** and ask which root.
- Exit `0` → the `ROOT:` line is `<root>`. Read `<root>/.dgf-factory/config.yaml` and
  `<root>/.dgf-factory/DESCRIPTION.md`. Keep `paths.plan`, `paths.plans`, `git.*` and
  `language.*`. Use `language.ui` to talk and `language.artifacts` to write the plan.
- Read `<root>/.dgf-factory/skill-context/dgf-plan/SKILL.md` if it exists. An override may add
  rules and tighten checks. It never relaxes a STOP, an exit-code row, the gate's status table, a
  Critical Rule or Artifact Ownership, and never makes this skill install anything, skip a script,
  or write outside its own artifacts. Name the override in your report, and quote any rule in it
  you did not apply because it would relax one of these.

### Step 0.1: Git state

Never run `git init`.

- `git.enabled: false` → no branch is created and no overlap is checked. A full or ultra plan
  still gets a `branch` value (Step 1.2): it names the plan.
- `git.enabled: true` → confirm with `git -C "<root>" rev-parse --is-inside-work-tree`. If that
  fails, warn and continue as `git.enabled: false`.

### Step 0.2: Arguments and mode

- A leading `fast`, `full` or `ultra` is the mode, and is removed. The rest is the description.
- Keep the description **verbatim** as `original_user_request` — only outer whitespace
  trimmed. It goes into `## Original Request` unchanged: not rewritten, not translated.
- No mode token → ask, with `AskUserQuestion`: **Full** (recommended — a branch and a richer
  plan) or **Fast** (a single `PLAN.md`, no branch). Ultra is chosen only by its token.
- No description → ask for one, and keep the answer verbatim.

### Step 1: Reconnaissance

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/inventory_root.py" --workspaces-root "<root>"
```

Its `WORKSPACE:` lines are the **only** names `affects_workspaces` may use. An `applibs*`
folder is never one. On exit `3`, **STOP**.

Then launch Explore subagents in parallel with the `Agent` tool (`subagent_type: Explore`) —
one or two for full, two or three for ultra, none for fast when DESCRIPTION.md is enough. Give
each the root and a DGF-shaped question; they return summaries, never whole files:

- **Artifacts.** "Under `<root>`, find the processes (`<ws>/FM/_PROCESS/<P>/process.xml`),
  workflows (`FM/_WORKFLOW/<X>/_workflow.xml`, or process-local `FM/_PROCESS/<P>/<X>/`), forms
  (`FM/_DATA/<table>/_forms/<form>/_form.xml`) and component JSON (`FM/_COMPONENTS/<Type>/`)
  related to <domain terms>. Report paths, element names and states."
- **References.** "Which files reference <artifacts>? Process `action` values
  (`WORKFLOW:<name>`, `WORKFLOW:/<name>`), `BASE:` prefixes, CHANGE_STATE steps, and component
  references by `type` + `name`. For anything in `webasm`, list each application workspace that
  uses it."
- **How DGF builds it.** Ask the DGF docs MCP, yourself: `search_docs`, `how_to_build`,
  `get_recipes_for` and `get_component_doc` for the components the change needs.

How a reference resolves is in `${CLAUDE_PLUGIN_ROOT}/knowledge/process-model.md` §2 and
`${CLAUDE_PLUGIN_ROOT}/knowledge/json-reader.md` §2.1. Cite those files; do not restate their
rules from memory.

### Step 1.2: Identifier

- **Full or ultra:** a slug of the description — lower-case, hyphens, at most 50 characters —
  and `branch: <git.branch_prefix><slug>`. The stem is the branch with `/` → `-`: the plan is
  `<paths.plans>/<stem>.md`, or the bundle `<paths.plans>/<stem>/index.md`.
- **Fast:** `<paths.plan>`, and `branch` is the current branch, or `none` when there is none.
- **If a plan already exists at that path, or in the other shape for the same stem,** ask:
  refine it, replace it, or choose another slug. Never write a second plan for one stem.

### Step 1.3: Questions

Ask, in one `AskUserQuestion`, only what the evidence has not settled:

- constraints the plan must respect;
- when `webasm` is in scope: **why the base workspace must change** — it becomes
  `base_workspace_reason`, and every application sees the change (ADR 0005 rule 3);
- which of two plausible components or workspaces the user means, when reconnaissance found
  both.

### Step 1.4: Branch (full and ultra, when `git.enabled` and `git.create_branches`)

When refining a plan whose branch already exists, check that branch out
(`git -C "<root>" checkout <branch>`) and skip the rest of this step. Otherwise run one command
per call. First:

```bash
git -C "<root>" status --porcelain
```

If the tree is dirty, ask whether to commit it first (`/dgf-commit`), stash it
(`git -C "<root>" stash push -m "dgf-plan: before <branch>"`), or carry it onto the new branch.
Never discard it. Then:

```bash
git -C "<root>" checkout <git.base_branch>
```

```bash
git -C "<root>" pull origin <git.base_branch>
```

```bash
git -C "<root>" checkout -b <branch>
```

A failed `pull` (no remote, offline) is a warning; continue from the local base branch.

### Step 2: Analyse

For each artifact the change touches:

1. **Choose its workspace.** An application's own behaviour lives in that application. Put a
   file in `webasm` only when every application must see it, and say why.
2. **Existing or new.** An existing file is edited in the family it is in. Converting it from
   XML to JSON is a migration, and a migration is its own task.
3. **Route every new file:**

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route_means.py" <ComponentType, loader folder or legacy artifact type>
   ```

   For a file under `FM/_COMPONENTS/<Folder>/`, pass `<Folder>`: a ComponentType, or one of the
   loader folders `DataSource`, `Template` and `Endpoints`. Exit `0` or `2` prints
   `ROUTE: json|xml <where> — <reason>`: record that line in `## Affected Artifacts`, and name
   the file exactly where it says, the folder spelled as printed. Exit `2` is `PARITY_PARTIAL`: the JSON is read, and the part the row names is an
   XML artifact of its own. Exit `3` (`ROUTE_NO_ROW`) means no family can be chosen for that
   name: **STOP** and report it; never default to JSON.
4. **Choose `kind`.** `config` for every JSON or XML file. `code` only when no component
   property, `EventBase` verb (`${CLAUDE_PLUGIN_ROOT}/knowledge/composition-specs.md` §3.1) or
   DataFetcher can express the change. Its `reason` names the configuration route tried and
   cites the component doc, the schema or the verb list. "Quicker in JavaScript" is not a
   reason.
5. **Code goes only where something loads it** (`code-places`,
   `${CLAUDE_PLUGIN_ROOT}/knowledge/composition-specs.md` §5): a form's `_form.js`, new or
   existing; or an **existing** file under a workspace's `js/`, `FM/js/` or `css/`. A new file
   there loads nothing until a deployment mounts it — plan it under `## Scope` as out of scope.
6. **Anything that needs C#, TypeScript, Angular, SQL, a plugin assembly or deployment
   configuration** goes under `## Scope` as out of scope, for a general coding flow. It never
   becomes a task.

### Step 3: Deeper exploration (full and ultra)

Resume the Step 1 agents, or launch new ones, until every artifact has evidence: its current
elements, keys and states; everything that references it; and, for a `webasm` change, every
application that consumes it. Ultra needs this evidence for every task (`ULTRA-FORMAT.md`,
Required Detail Gate).

### Step 4: Tasks

- One deliverable per task, in dependency order, with `(depends on N)` where it matters.
- Each task has `kind`, a `reason` when `kind: code`, and the `files` it creates or edits and
  the files it `deletes`, relative to the root.
- Five or more tasks → a `## Commit Plan` with a commit every 3–5 tasks, in conventional-commit
  form, scoped by workspace (`feat(zims): …`).
- No report, summary or "verify" task: `/dgf-verify` is the check.

### Step 5: Save

Write the plan exactly as `${CLAUDE_PLUGIN_ROOT}/skills/dgf-plan/references/PLAN-FORMAT.md`
specifies for fast and full, or as `${CLAUDE_PLUGIN_ROOT}/skills/dgf-plan/references/ULTRA-FORMAT.md`
for ultra. For ultra, write the phase files first and `index.md` last, so its Phase Index and
task links match them. Create the plans directory if it is missing.

### Step 5.1: Check the plan

For a full or ultra plan with git, offer `git -C "<root>" fetch` first: the overlap check reads
remote branches only as fresh as the last fetch, and it never fetches. Then:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_plan.py" "<plan entrypoint>" --workspaces-root "<root>" --overlap
```

Leave out `--overlap` when `git.enabled` is false.

| Exit | Action |
|---|---|
| `0` | Continue. |
| `1` | The plan is defective, and this skill owns it: fix every `ERROR` and run the check again. After 3 attempts, **STOP** and relay the findings. |
| `2` | Continue, and surface every `WARN` line: each `PLAN_OVERLAP` (another active plan shares a workspace; `webasm` is shared with every plan), `PARITY_PARTIAL`, `PLAN_NOT_AUTHORED`, `PLAN_COMMITS_MISSING` (five or more tasks and no Commit Plan — write one). |
| `3` | `PLAN_UNREADABLE` or `PLAN_FORMAT_UNSUPPORTED` is a header this skill wrote: fix it within the same 3 attempts. Any other exit `3` — a usage error, a malformed knowledge table — **STOP** and relay it. |

Re-run a failing check with `--verbose` when the cause is unclear.

### Step 6: Next steps

Report the plan's path, its mode, its task count, the workspaces it affects, and every warning
from Step 5.1. Then suggest:

1. **`/dgf-commit`** to commit the plan — stage it first (`git -C "<root>" add .dgf-factory/`) —
   so it travels with the branch and other plans' overlap checks can see it.
2. **`/dgf-implement`** to execute it.

Full and ultra plans stop here: the user reviews the plan before anything is implemented.

## Execution Rules

### DO:

- ✅ Take workspace names from the inventory, and routes from `route_means.py`
- ✅ Keep the user's request verbatim in `## Original Request`
- ✅ Give every `kind: code` task a reason that cites the doc, the schema or the verb list
- ✅ Name out-of-scope needs under `## Scope`
- ✅ Run `check_plan.py` after every save, and fix what it reports

### DON'T:

- ❌ Guess a family, or default a new component to JSON — `route_means.py` decides
- ❌ Write a task for C#, TypeScript, Angular, SQL, an assembly or deployment configuration
- ❌ Plan a new file under `js/`, `FM/js/` or `css/`
- ❌ List an `applibs*` folder in `affects_workspaces`
- ❌ Convert an existing file's family as a side effect of another task
- ❌ Write outside `.dgf-factory/` — planning changes no workspace file
- ❌ Discard uncommitted work to cut a branch

## Artifact Ownership

- **Owns:** the plan artifacts — `<paths.plan>` for fast, `<paths.plans>/<stem>.md` for full,
  and `<paths.plans>/<stem>/` for ultra.
- **Reads:** `.dgf-factory/config.yaml` and `DESCRIPTION.md` (owned by `/dgf`), the workspaces,
  the shipped `knowledge/`, and the DGF docs MCP.
- **Never writes** a workspace file, the config, DESCRIPTION.md, or another branch's plan.

## Critical Rules

1. **Scripts decide what they can.** Workspace names, routes, the plan's validity and its
   overlaps come from the scripts, not from judgement.
2. **Configuration first** (ADR 0010). JSON where the route says json, XML where it says xml,
   code only with a reason.
3. **`affects_workspaces` is never empty, and never short.** A plan may declare more than its
   diff touches, never less; `/dgf-verify` fails an undeclared workspace.
4. **The executor never re-decides.** Everything `/dgf-implement` needs — file, family,
   reference, reason — is in the plan, or the plan is not finished.
5. **One plan per branch,** named by the branch. Ids are never numbered.
6. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts and references.
