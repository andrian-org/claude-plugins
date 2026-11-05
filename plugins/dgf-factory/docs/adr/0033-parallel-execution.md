---
id: 0033
title: "Parallel execution: a Claude Code coordinator dispatches one task per worktree worker, and scripts decide the layers, the sync and the merge"
status: accepted
date: 2026-11-03
deciders: [Andrian Mamei]
supersedes: []
tags: [parallelism, agents, worktrees, delivery, implement]
---

# 0033 — Parallel execution: a Claude Code coordinator dispatches one task per worktree worker, and scripts decide the layers, the sync and the merge

**Status: accepted** (2026-11-03, Andrian Mamei), under the same delegation as
[ADR 0032](0032-quality-and-authoring-skills.md): the choices were drawn from the evidence below and not put to
the decider one by one.

This ADR decides milestone **Parallel Execution** — "coordinator and worktree-isolated workers" — for
`/dgf-implement`'s work: which harness gets it, which agents ship, which questions scripts decide, and how
`dgf-factory setup` installs an agent. `/dgf-implement` itself is unchanged and stays the way every harness
implements a plan.

## Context

Read on **2026-11-03** from this repository and AI Factory 2.21.0 (`<npm root -g>/ai-factory/`).

- **AI Factory's design.** `subagents/claude/agents/implement-coordinator.md` builds a dependency graph from
  `(depends on …)`, dispatches one `implement-worker` per ready task — `isolation: worktree`, `maxTurns: 16` —
  at most four at a time, then "merge[s] worktree branches sequentially". It runs the coordinator as a
  top-level session, `claude --agent implement-coordinator`, where `tools: Agent(<name>)` limits which agents it
  may spawn (`docs/blueprint.md` Part 1 §4; Claude Code's sub-agents documentation, read 2026-11-03).
- **Its merge has no defined input.** Its workers "do not create commits", so a worker's branch holds none of
  its edits; and a worktree is checked out from a commit, so a worker in layer two does not see layer one's
  uncommitted, merged work. Both gaps are prose a model must bridge.
- **A subagent's worktree is not at the caller's commit.** Claude Code creates it under
  `<repo>/.claude/worktrees/<name>/` on a branch `worktree-<name>`, from the remote default branch
  (`worktree.baseRef: "fresh"`) unless the project sets `"head"`; only without a remote does it start from local
  `HEAD` (Claude Code's worktrees documentation, read 2026-11-03). With agent teams enabled, a named subagent may
  run as a teammate in the caller's own directory unless the call itself passes `isolation: "worktree"`.
- **Git reports what a byte compare cannot.** With `core.autocrlf=true` a checkout differs from its blob byte for
  byte; `status --porcelain` paths are relative to the git toplevel even under `-C <subdir>`; a rename prints new
  before old unless `--no-renames`; and the main tree lists each linked worktree under `.claude/worktrees/` as one
  untracked entry (git 2.54, read in scratch repositories on 2026-11-03).
- **Worktrees are Claude Code's.** AI Factory ships Codex and Antigravity agents too, but neither declares a
  worktree: `subagents/codex/agents/implement-worker.toml` says "keep edits tightly scoped" and runs in the
  caller's tree. Two such workers editing one tree at once is the collision isolation exists to prevent.
- **A dgf-factory plan already carries the footprint.** Every task lists `files` and `deletes`, root-relative
  (ADR 0017), and `lib/plan.py` parses them with `depends`. Whether two tasks can run at once is decidable:
  their dependencies are met and their files are disjoint.
- **The runtime finds its venv beside its scripts** (`scripts/lib/runtime.py`, ADR 0031): a worker that calls
  the main checkout's `.dgf-factory/runtime/scripts/*.py` by absolute path runs them in the main venv, which
  a worktree never holds (`.venv/` is ignored).
- **`dgf-factory setup` installs only `SKILL.md` per harness** (`cli/plan.mjs`); `AGENTS.md` lists `agents/`
  as "not yet created", and `cli/harnesses.mjs` already records each harness's `agentsDir`.
- **The blueprint ranks this last**: "the flashiest part and the least load-bearing" (Part 2 §"Build order").

## Decision

### 1. Claude Code only

The agents ship for Claude Code and install into `.claude/agents/`. Every other harness implements with
`/dgf-implement`, one task at a time, as today. A harness gains agents when it has worktree isolation and a
verified agent format; that is a new ADR row, not an edit here.

### 2. Two agents

| Agent | Runs as | Does |
|---|---|---|
| `dgf-implement-coordinator` | `claude --agent dgf-implement-coordinator`, top level | finds the plan, asks `plan_layers.py` for the next layer, dispatches one worker per parallel task in a single message, merges each worker with `worktree_task.py --merge`, runs the per-task check in the main tree, ticks the plan, and ends with the verify gate |
| `dgf-implement-worker` | `isolation: worktree`, one task | syncs the main tree into its worktree with `worktree_task.py --sync`, implements its one task by `/dgf-implement`'s Step 3, runs the per-task check, and reports; never ticks the plan, commits, or edits a file the task does not list |

A layer with one task, or a task `plan_layers.py` holds serial, is implemented by the coordinator itself,
in the main tree. No sidecar agents ship: the DGF checks that matter are scripts, and the coordinator runs
them.

### 3. Scripts decide

| Script | Decides | Exit |
|---|---|---|
| `scripts/plan_layers.py` | the next layer: the unchecked tasks whose `depends` are all checked, split into a parallel batch of tasks with pairwise disjoint `files` and `deletes` — at most `--max-parallel`, default 4 — and the tasks held serial, each with why: a shared file, no declared files, or the cap | `0` / `1` a cycle or a missing dependency / `3` usage |
| `scripts/worktree_task.py --sync` | moves a clean worktree's own branch to the main tree's `HEAD` (a dirty one at another commit is refused), then copies the main tree's uncommitted state under the workspaces root — modified, added, untracked-and-not-ignored, deleted — into it, except `.dgf-factory/runtime/`; refuses a worktree that is not a linked worktree of the same repository; records what it copied in the worktree's own git directory, where no status sees it and no commit can take it | `0` / `1` / `3` |
| `scripts/worktree_task.py --merge` | the worker's change is every path where the worktree differs from what `--sync` left; each must be in the task's `files` (added or modified) or `deletes` (deleted), the main tree's `HEAD` must still be the synced one, and the main tree's copy must still be what was synced — else nothing is copied; then it copies (mode kept) and deletes, and with `--cleanup` removes the worktree and its branch, leaving a locked one in place | `0` / `1` / `3` |

`lib/git.py` stays read-only; the three commands that change a repository — moving the worktree's branch,
removing the worktree, deleting its branch — live in `lib/worktree.py`, and only `worktree_task.py` calls them.

So the coordinator's merge is a script's: a worker that touched an undeclared file — the plan included — is
refused, and a main tree that changed under a layer is refused, before a byte moves.

### 4. The pipeline's other rules hold

- **The executor never re-decides.** The worker follows `/dgf-implement` Step 3 to the letter, and its drift
  STOPs return to the coordinator as a failed task.
- **One ledger, one writer.** Only the coordinator ticks a checkbox, after the merge and after
  `check_change.py --files` passes in the main tree.
- **No commits.** Neither agent commits. The run ends with `verify_gate.py`'s block, relayed verbatim, and
  the user commits with `/dgf-commit`.
- **Git is required.** Without git there is no worktree: the coordinator STOPs and names `/dgf-implement`.
- **Stop on failure.** A failed or refused task stops the run after its layer is merged; nothing advances.

### 5. Installing an agent

The package gains `agents/`, shipped (`package.json` `files`, `doctor.py`'s `SHIPPED_DIRS`). `agents/claude/<name>.md`
installs at `<agentsDir>/<name>.md` for the `claude` harness, rendered as a skill is (`{{dgf_runtime}}` → the
project-relative runtime) and recorded in the receipt with the harness as owner, so `status`, re-running
setup, and `uninstall` treat it like a skill. An agent the runtime needs is never copied into the runtime.

## Alternatives considered

- **Port AI Factory's coordinator as written.** Rejected: its merge and its layer-two visibility are prose (§Context).
- **Workers commit, the coordinator cherry-picks.** Rejected: commits are `/dgf-commit`'s, grouped by the plan's
  Commit Plan; WIP commits would leave the user history to rewrite.
- **Ship Codex and Antigravity agents too.** Rejected for now: without isolation, parallel workers share a tree.
- **Add a `--parallel` mode to `/dgf-implement`.** Rejected for now: a skill's own session can spawn subagents,
  but only a top-level `claude --agent` session restricts *which* agents it spawns (`Agent(<name>)`), and the
  coordinator's turn budget and tools are its own, not the skill's. A skill mode stays a follow-up.

## Consequences

### Positive

- **Independent tasks run at once**, and a plan's `files` — already checked by `check_plan.py` — is the
  only input the scheduler needs.
- **A worker cannot widen its task's scope**: the merge refuses an undeclared file, including the plan.
- **Layer two sees layer one** without a commit.

### Negative

- **Claude Code only.**
- **A plan that under-declares its files runs serially or is refused**, where `/dgf-implement` would only warn
  (`CHANGE_UNPLANNED_FILE`).
- **The worktrees live in the project** (`.claude/worktrees/`), which setup cannot add to `.gitignore`; it prints
  the step instead.
- **The worktree's working copy is a full checkout**, so a large estate pays a checkout per worker.
- **Agent behaviour is not testable here**: the scripts are, the dispatch is not.

### Follow-ups

- Codex or Antigravity agents, once either has worktree isolation.
- A `--parallel` hint from `/dgf-plan` when a plan's first layer has two or more independent tasks.
