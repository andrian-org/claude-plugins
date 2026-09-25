---
name: dgf-commit
description: Commit staged DGF changes with a conventional commit message scoped by workspace, following the plan's Commit Plan when there is one, after a warn-only check that the change stays inside its plan. Use for "commit", "dgf commit", "save changes", "create commit", "commit the plan", "commit the setup".
argument-hint: "[scope or context]"
allowed-tools: Read Glob Grep Bash(git *) Bash(python3 *) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
---

# DGF Commit — Conventional Commits for a DGF Estate

Turn the staged changes into one or more [Conventional Commits](https://www.conventionalcommits.org/),
scoped by the workspace they change. When the active plan has a `## Commit Plan`, follow it.
Before committing, run the change check without the validators: it warns, it never blocks —
`/dgf-verify` is the gate.

This skill ports AI Factory's `/aif-commit`. It drops the context gates and roadmap linkage,
and adds workspace scopes and the change check. It never modifies the plan.

## Workflow

### Step 0: Context

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --root-only
```

- Exit `0` → the `ROOT:` line is `<root>`. Read `<root>/.dgf-factory/config.yaml` for
  `paths.*`, `git.base_branch`, `git.skip_push_after_commit` and `language.ui`, and
  `<root>/.dgf-factory/skill-context/dgf-commit/SKILL.md` if it exists — its rules override
  this file's where they conflict, the commit message included.
- Exit `1` → **STOP** with its message (`ROOT_NOT_SET_UP`: run `/dgf`; `ROOT_AMBIGUOUS`: name
  the root).

### Step 1: Analyse the staged changes

One command per call:

```bash
git -C "<root>" status --short
```

```bash
git -C "<root>" diff --cached --stat
```

```bash
git -C "<root>" diff --cached
```

Nothing staged → say so, show what is unstaged, and suggest what to stage. Do not stage it
unasked.

### Step 2: The plan

An argument starting with `@` is the plan. Otherwise:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is the plan. Read its `## Commit Plan` and `## Tasks`. |
| `1`, `PLAN_NOT_FOUND` | **Continue without a plan.** Skip Steps 3 and 4, and say so in one line. This is the path for committing `.dgf-factory/` right after `/dgf`. |
| `1`, `PLAN_AMBIGUOUS` | **STOP.** Ask which plan, or re-run with `@<plan>`. |
| `2`, `PLAN_FALLBACK` | Say which plan was chosen and why, and ask before using it. |

Read the plan; never edit it.

### Step 3: Group by the Commit Plan

When the plan has a `## Commit Plan`:

1. Parse each group: its number, its task range (`after tasks 1-3`) and its message.
2. Map each group's tasks to their `files` and `deletes` bullets. For an ultra plan, read each
   task's phase file too — its `## Files to Change` table and `## Task N` section. The task
   bullets in `index.md` alone are not enough to split a shared file.
3. Compare the staged paths (`git -C "<root>" diff --cached --name-only`) with the groups.
   Staged files that map to no group → **STOP** and ask how to group them.
4. Plain `git add <files>` per group is safe only when every group's files are disjoint and
   none of them also has unstaged changes (`git -C "<root>" diff --name-only`). When one file
   spans groups, or a grouped file has unstaged changes, keep each group's cached patch
   (`git diff --cached` then `git apply --cached`) or stage hunk by hunk. If that cannot be done
   with confidence, **stop before changing the staging** and offer to commit everything
   together.
5. Ask, with `AskUserQuestion`: **Follow the Commit Plan**, **Commit everything together**, or
   **Adjust the grouping**.

Without a Commit Plan, and when the staged changes mix unrelated work (two workspaces for
different reasons, a plan and a feature), suggest a split the same way.

### Step 4: The change check — warn only

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>" --skip-validators
```

`--skip-validators` runs only the scope, means and planned checks; it needs neither `lxml` nor
`jsonschema`.

- Exit `0` → continue.
- Exit `1` → show every `ERROR` line — an undeclared workspace, an out-of-scope file, an
  unplanned or new code file — and ask whether to commit anyway. Say that `/dgf-verify` will
  fail on the same findings.
- Exit `2` → show the `WARN` lines, and continue.
- Exit `3` → show it, and continue: this check never blocks a commit.

### Step 5: Type

`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci` or `chore`. A new or
changed behaviour in configuration is `feat` or `fix`, like code.

### Step 6: Scope

| The staged files change | Scope |
|---|---|
| one application workspace | its name — `feat(zims): …` |
| the base workspace only | `webasm` — `fix(webasm): …` |
| several workspaces | no scope; name every workspace in the body |
| only `.dgf-factory/config.yaml` and `DESCRIPTION.md` | `chore(dgf): set up dgf-factory` |
| only plan files under `.dgf-factory/` | `docs(plan): …` |

An argument that is not `@<plan>` is the scope, or context for the message.

### Step 7: Message

```
<type>(<scope>): <subject>

<body>

<footer>
```

- Subject under 72 characters, imperative mood, lower case after the colon, no full stop.
- The body says why, and — for several workspaces, or `webasm` — which workspaces change. For a
  plan-driven commit, name the plan's tasks it completes.
- Take a Commit Plan group's message as the starting point.

### Step 8: Commit

Show the proposed message, and ask with `AskUserQuestion`: **Commit as is**, **Edit the
message**, or **Cancel**. Commit only on confirmation:

```bash
git -C "<root>" commit -F - <<'EOF'
<message>
EOF
```

For a Commit Plan, repeat Steps 7–8 per group, staging each group before its commit.

### Step 9: Push

Skip this step when `git.skip_push_after_commit` is true. Otherwise show
`git -C "<root>" status -sb`, and ask: **Push now** or **Skip**. Push with
`git -C "<root>" push -u origin <branch>` when the branch has no upstream, else
`git -C "<root>" push`. After a split, offer the push once, after the last commit.

## Execution Rules

### DO:

- ✅ Scope each commit by the workspace it changes
- ✅ Follow the Commit Plan when the plan has one, and the user agrees
- ✅ Run the change check with `--skip-validators`, and show what it finds
- ✅ Confirm every message before committing
- ✅ Commit `.dgf-factory/` like any other change: plans travel with branches

### DON'T:

- ❌ Modify the plan, the config or any workspace file
- ❌ Block a commit on the change check — it warns; `/dgf-verify` is the gate
- ❌ Stage files the user did not stage, or change the staging when grouping is unclear
- ❌ Commit secrets or credentials
- ❌ Add a `Co-Authored-By` or any other trailer attributing the commit to an AI

## Artifact Ownership

- **Owns:** nothing. It writes git history, only after the user confirms.
- **Reads:** the staged diff, the plan, `.dgf-factory/config.yaml`.
- **Never modifies** the plan, the config, DESCRIPTION.md or a workspace file.

## Critical Rules

1. **Warn, never block.** The change check informs the user; the decision to commit is theirs.
2. **Scope by workspace.** A reader of the log sees which application — or the base — changed.
3. **The plan is read-only here.** Its checkboxes belong to `/dgf-implement`.
4. **No commit without confirmation**, and no push without asking.
5. **Never change the staging you cannot restore.** When hunks are ambiguous, stop and ask.
