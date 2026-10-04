---
name: dgf
description: Set up dgf-factory for a DGF workspaces root — inventory the workspaces, record the estate's DGF version, and write .dgf-factory/config.yaml and DESCRIPTION.md. Use for "set up dgf-factory", "dgf setup", "initialise the workspaces root", "configure dgf", "start using dgf-factory".
argument-hint: "[workspaces-root]"
allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) Bash(git *) AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_release_notes
disable-model-invocation: false
version: 0.2.0
---

# DGF — Set Up a Workspaces Root

Prepare one DGF workspaces root for the pipeline: find it, count what it holds, ask the few
things no file states, and write the two artifacts every other `dgf-*` skill reads.

The unit of work is the **whole workspaces root**, and `.dgf-factory/` lives there once — not
per workspace. The estate is brownfield: this skill reads what is on disk and never scaffolds.

This skill ports AI Factory's `/aif` Mode 1 ("analyze an existing project"). It installs no
skills and writes no MCP configuration: the plugin ships both. It writes no `AGENTS.md` and no
rules file.

## Workflow

### Step 0: Locate the root

With an argument, it is the workspaces root:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<argument>" --setup
```

Without one:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --setup
```

Capture the exit code before any pipe.

| Exit | Meaning | Action |
|---|---|---|
| `0`, `ROOT: <path>` | a `.dgf-factory/config.yaml` exists | **A re-run.** The root is that path. Read the existing config and DESCRIPTION.md; Step 5 edits them |
| `0`, `NEW ROOT: <path>` | no config yet | **A first run.** The root is that path — the argument, else the working directory. Continue; this is not an error |
| `1`, `ROOT_AMBIGUOUS` | several roots below the working directory | **STOP.** List them and ask the user to re-run `/dgf <root>` |
| `3` | usage error — the argument is not a directory | **STOP.** Show the message |

### Step 0.1: Load overrides

On a re-run, pass the config's `paths.skill_context` and `paths.patches`. On a first run there is
no config yet: pass the template's values, `.dgf-factory/skill-context/` and
`.dgf-factory/patches/`. An applied override's rules apply to everything this skill writes.

Check this skill's override before reading it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_override.py" --workspaces-root "<root>" --skill dgf --skill-context-dir "<paths.skill_context>" --patches-dir "<paths.patches>"
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

### Step 1: Inventory

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/inventory_root.py" --workspaces-root "<root>"
```

| Exit | Action |
|---|---|
| `0` | Continue. |
| `2` | Continue, and relay every `WARN` line. `BASE_WORKSPACE_ABSENT`: the base workspace is mounted from elsewhere, so `BASE:` references cannot be checked here (`${CLAUDE_PLUGIN_ROOT}/knowledge/composition-specs.md` §1.2). `VALIDATOR_DEPS_MISSING`: relay its install command **verbatim** — never run `pip` yourself. |
| `3` | **STOP.** `ROOT_NO_WORKSPACE`: this is not a DGF workspaces root. Say so, and ask for the right directory. An empty folder, or one with no DGF application yet, is `/dgf-scaffold`'s, not this skill's: suggest it. A scaffolded application keeps its workspaces in `workspaces/`: when the root has that folder, suggest `/dgf workspaces`. |

Keep the output: Step 5 pastes its `WORKSPACE:` and `NOT A WORKSPACE:` lines into
DESCRIPTION.md, and Step 3 shows its `KNOWLEDGE:` line. A failing script is re-run with
`--verbose` when the user asks why.

### Step 2: Git

Read the inventory's `GIT:` line.

- `GIT: none` → `git.enabled: false`. Warn that without git three things do not run: plan
  discovery by branch, the overlap check between plans, and the merge-base baseline, so every
  validator finding will count as new.
- Otherwise `git.enabled: true`. The default base branch is the remote's HEAD:

  ```bash
  git -C "<root>" symbolic-ref --short refs/remotes/origin/HEAD
  ```

  `origin/main` means `main`. When that fails, use the branch the inventory reports.

### Step 3: Ask

On a re-run, ask only about what the user wants to change, and show the current values.

Ask in at most **two** `AskUserQuestion` calls — the tool takes four questions per call.

**Call 1:**

1. **The estate.** Offer a name built from the git top level's directory name and the
   application workspaces, and let the user type the name and one sentence of purpose.
2. **The DGF version this estate runs** (ADR 0019). Show the knowledge stamp from the
   inventory's `KNOWLEDGE:` line. Options: the stamp's version, `unknown`, and a typed `X.Y.Z`.
   Nothing in a workspaces root states it, so never infer it.
3. **The base branch** — the Step 2 default first. Skip when `git.enabled` is false.
4. **The branch prefix** — `feature/` first. Skip when `git.enabled` is false.

**Call 2 — stack overrides:** the plugin's defaults are auth by JWT Bearer plus OIDC via Azure
AD and DGPass, and tests in xUnit + FluentAssertions + Moq/NSubstitute (backend) with Jest and
Playwright (frontend). Options: keep both defaults, or record an override for either. They are
defaults, not invariants; the estate's answer wins.

**Language.** When the existing config sets `language.ui` and `language.artifacts`, keep them.
Otherwise use the language the user writes in for both, and say so in Step 7.

### Step 4: Compare the declared version

- **`unknown`:** warn that a future version gate cannot compare facts with this estate, and
  that the warning will stand in DESCRIPTION.md until `/dgf` is re-run with a version.
- **Newer than the knowledge stamp:** say that the shipped facts were read at an older DGF
  release, and offer the DGF docs MCP's `get_release_notes("since:<stamp>")` so the user can
  read what changed. Do not edit the knowledge base.
- **Equal or older:** no note.

The version is recorded, not checked. No fact carries an `applies:` range yet, so no gate uses
it today.

### Step 5: Write the artifacts

Create `<root>/.dgf-factory/` if it is missing.

1. **`config.yaml`** from `${CLAUDE_PLUGIN_ROOT}/skills/dgf/references/config-template.yaml`.
   Fill every `{{…}}` placeholder; quote the version (`"1.1.15"` or `"unknown"`). Without git,
   write `base_branch: main` and `branch_prefix: feature/` anyway: a full plan's `branch` still
   names the plan. There is no
   `plan_id_format` key: plan ids are always the branch name.
2. **`DESCRIPTION.md`** from `${CLAUDE_PLUGIN_ROOT}/skills/dgf/references/description-template.md`.
   One table row per `WORKSPACE:` line, with its counts copied exactly; one bullet per
   `NOT A WORKSPACE:` line; every inventory `WARN` line under the table. `{{VERSION_NOTE}}` is
   the Step 4 warning, or empty.

**On a re-run,** never rewrite either file wholesale. Show the user a diff of the values that
change, then `Edit` only the keys and sections this skill manages: `dgf.version`, `language`,
`git.*`, the Purpose, DGF version, Workspaces root and Stack sections. Leave every other line
as the user left it.

Write both files in `language.artifacts`.

### Step 6: Check `.gitignore`

Plans travel with branches, so `.dgf-factory/` is committed.

```bash
git -C "<root>" check-ignore -q .dgf-factory/config.yaml
```

Exit `0` means the file is ignored: warn that plans and the config will not reach other
branches, and show the `.gitignore` line that matches (`git -C "<root>" check-ignore -v …`).
Do not edit `.gitignore`. Skip this step when `git.enabled` is false.

### Step 7: Next steps

Report, in `language.ui`: the root, the workspaces found, the declared version and any
warning, and the two files written. Then suggest, in order:

1. **`/dgf-commit`** to commit `.dgf-factory/` — stage it first
   (`git -C "<root>" add .dgf-factory/`). It works without a plan; the message it suggests is
   `chore(dgf): set up dgf-factory`. Commit on the base branch, so every branch
   cut from it carries the config.
2. **`/dgf-plan <what to change>`** to plan the first change.
3. **`/dgf-doctor`** if a skill does not fire, or a script cannot run.

## Execution Rules

### DO:

- ✅ Take the root from `locate_plan.py`, and the counts from `inventory_root.py`
- ✅ Relay every inventory warning, and the install command verbatim
- ✅ Ask for the DGF version, and record `unknown` when the user does not know it
- ✅ Show a diff and edit only managed keys on a re-run
- ✅ Say what will not run when there is no git

### DON'T:

- ❌ Count workspaces, processes or forms by reading directories yourself — the inventory decides
- ❌ Infer the DGF version from schemas, package files, image tags or the UI build
- ❌ Run `pip`, or install anything
- ❌ Create workspaces, plans, `AGENTS.md`, rules files, `.mcp.json` or anything under a workspace
- ❌ Edit `.gitignore`
- ❌ Treat an `applibs*` folder as a workspace

## Artifact Ownership

- **Owns:** `<root>/.dgf-factory/config.yaml` and `<root>/.dgf-factory/DESCRIPTION.md`.
- **Reads:** the workspaces root, through `locate_plan.py` and `inventory_root.py`; git metadata.
- **Writes nothing else.** Plans belong to `/dgf-plan`; nothing under a workspace is touched.

## Critical Rules

1. **The scripts decide the root and the counts.** A count typed from a directory listing is a
   guess.
2. **The DGF version is declared, never inferred** (ADR 0019). `unknown` is a valid answer and
   a standing warning.
3. **One `.dgf-factory/` per workspaces root**, at the root — never inside a workspace.
4. **A re-run edits; it never overwrites.** The user's own lines in these files survive.
5. **Nothing is installed.** A missing dependency is reported with its command, and stops there.
6. **`${CLAUDE_PLUGIN_ROOT}` always** for the plugin's own scripts and templates.
