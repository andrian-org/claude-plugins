# Implementation Plan: Parallel Execution

Branch: none (worked on `main`'s working tree; the user commits)
Created: 2026-11-03

## Original Request

"plan, improve, implement, and verify each unresolved roadmap item … do it yourself without asking me" — roadmap
milestone **Parallel Execution**: coordinator and worktree-isolated workers.

## Settings

- Testing: yes — unittest for both scripts over temporary git repositories with real linked worktrees
  (`git worktree add`); node tests for the agent install
- Logging: `report.debug` on stderr; the CLI's `log.debug`
- Docs: `docs/pipeline.md` §parallel, `docs/getting-started.md`, README, AGENTS.md

## Roadmap Linkage

Milestone: "Parallel Execution"

## Decisions

[ADR 0033](../../docs/adr/0033-parallel-execution.md): Claude Code only; `dgf-implement-coordinator` (top level)
and `dgf-implement-worker` (`isolation: worktree`); `plan_layers.py` decides the layer; `worktree_task.py`
syncs the main tree into a worktree and merges a worker back, refusing an undeclared file or a main tree that
changed; no commits; git required; setup installs `agents/claude/*.md` into `.claude/agents/`.

## Interfaces

Codes are pre-registered in `scripts/lib/report.py`: `LAYERS_CYCLE` (1), `LAYERS_SERIAL` (0, INFO),
`WORKTREE_NOT_LINKED` (3), `WORKTREE_HEAD_MISMATCH` (1), `WORKTREE_SYNC_MISSING` (1),
`WORKTREE_UNDECLARED_FILE` (1), `WORKTREE_MAIN_CHANGED` (1).

### `scripts/plan_layers.py`

```
plan_layers.py --workspaces-root <root> --plan <entrypoint> [--max-parallel <n>] [--verbose]
```

- Parse with `lib/plan.py` (`plan.parse`, `Task.files`, `Task.deletes`, `Task.depends`, `Task.checked`), ultra
  bundles included. `--max-parallel` default 4, range 1–8, else usage error.
- Ready = unchecked tasks whose every `depends` is a checked task. A `depends` that names no task, or a set of
  unchecked tasks that can never become ready, is `LAYERS_CYCLE` naming the tasks.
- The batch: ready tasks in task order, each admitted when its `files ∪ deletes` is non-empty and disjoint from
  every admitted task's, until the cap. Every other ready task prints `LAYERS_SERIAL` with why: `shares <path>
  with task <n>`, `declares no files`, or `over --max-parallel <n>`.
- Lines: header `PLAN LAYERS`; `PLAN: <path> progress=<d>/<t>`; `READY: <n>,…` (or `READY: none`);
  `PARALLEL: <n>,…` (the batch, possibly one task); `SERIAL: <n> — <why>` per held task;
  `REMAINING: <n>` unchecked tasks not yet ready. `CHECKS RUN: plan-parse, layers`. Exit 0 also when the plan is
  complete (`READY: none`, `REMAINING: 0`).
- A plan `check_plan.py` would refuse is not this script's business: it parses what it can and reports a parse
  error as `check_plan.py` would (exit 3, `PLAN_UNREADABLE` / `PLAN_FORMAT_UNSUPPORTED`).

### `scripts/worktree_task.py`

```
worktree_task.py --sync  --from <main workspaces root> --worktree <dir inside the worker's worktree> [--verbose]
worktree_task.py --merge --from <worker's workspaces root> --to <main workspaces root> --plan <main plan entrypoint> --task <n> [--cleanup] [--verbose]
```

- Both modes resolve each side's git toplevel (`lib/git.toplevel`) and refuse (`WORKTREE_NOT_LINKED`, exit 3) unless
  the two share one git common dir (`git rev-parse --git-common-dir`) and the worktree side is a *linked*
  worktree, not the main one. Add the small `lib/git.py` helpers this needs (common dir, `worktree list
  --porcelain`, `status --porcelain=v1 -z --untracked-files=all`, `worktree remove`, `branch -D`), each through
  `_run` with a `module_fn`.
- `--sync`: refuses `WORKTREE_HEAD_MISMATCH` unless both `HEAD`s are the same commit. The main tree's dirty set is
  `status --porcelain -z --untracked-files=all` (ignored files excluded), minus anything under
  `.dgf-factory/runtime/` and `.dgf-factory/parallel/`. Copies each modified/added/untracked file (bytes,
  mode bits), removes each deleted one, then writes `<worktree toplevel>/.dgf-factory/parallel/sync.json`:
  `{"head": <sha>, "main": <main toplevel>, "files": {<toplevel-relative path>: <sha256 or null for deleted>}}`.
  Prints `MAIN: <path>`, `WORKTREE: <path>`, `WORKTREE ROOT: <the worker's workspaces root>` (the main workspaces
  root's path relative to its toplevel, under the worktree's toplevel), `SYNCED: <n> file(s), <d> deletion(s)`.
- `--merge`: reads `sync.json` (absent → `WORKTREE_SYNC_MISSING`). The base of a path is its `sync.json` entry,
  else `HEAD`'s blob, else absent. The worker's change is every path (excluding the two directories above) whose
  worktree content differs from its base — found from the worktree's own `status --porcelain` plus the
  `sync.json` keys. Each must be root-relative-in `task <n>`'s `files` or `deletes` (convert toplevel-relative
  to workspaces-root-relative), else `WORKTREE_UNDECLARED_FILE` per path; and the main tree's current copy must
  equal the base, else `WORKTREE_MAIN_CHANGED` per path. Any finding → nothing is copied, exit 1. Otherwise copy
  (write to a temporary file beside the target, then `os.replace`) or delete each, printing
  `MERGED: <A|M|D> <workspaces-root-relative path>`; then with `--cleanup`, `git worktree remove --force <worktree
  toplevel>` and `git branch -D <its branch>` (from `worktree list --porcelain`), printing `REMOVED: <path>
  (<branch>)`. `CHECKS RUN: worktree-linked, sync-record, scope, main-unchanged, merge`.

### The agents (`agents/claude/`)

- `dgf-implement-coordinator.md` — frontmatter `name`, `description` (with "run with `claude --agent
  dgf-implement-coordinator`"), `tools: Agent(dgf-implement-worker), Read, Write, Edit, Glob, Grep, Bash`,
  `model: inherit`, `maxTurns: 60`, `skills: [dgf-implement, dgf-verify]`. Body: runtime check (no `Agent` tool →
  stop with the AI Factory sentence adapted); `locate_plan.py`; `check_plan.py`; git required; loop: `plan_layers.py`
  → one task: implement it in the main tree by `/dgf-implement` Step 3 and tick it; several: dispatch all workers
  in one message, each prompt carrying the absolute main workspaces root, the absolute runtime
  (`<main project>/{{dgf_runtime}}`), the plan path, the task number, `git.base_branch`; then per worker in task
  order `worktree_task.py --merge … --cleanup`, then `check_change.py --files` in the main tree, then tick; any
  failure stops after the layer. End: `verify_gate.py`, relay its block verbatim, name `/dgf-commit`.
- `dgf-implement-worker.md` — `isolation: worktree`, `maxTurns: 30`, `tools: Read, Write, Edit, Glob, Grep, Bash`,
  `skills: [dgf-implement]`. Body: first `python3 "<runtime>/scripts/worktree_task.py" --sync --from "<main root>"
  --worktree .` and take `WORKTREE ROOT:`; then `/dgf-implement` Step 3 for its one task with `<root>` the
  worktree root and every script called as `python3 "<runtime>/scripts/…"`; deletes by removing the file (no
  `git rm`: the merge reads content); never tick, never commit, never edit an unlisted file; report `task`,
  `WORKTREE ROOT`, files written, the check's exit and its new findings verbatim, and `status: done | failed`.

### Install (`cli/`)

- `cli/plan.mjs`: `PAYLOAD_DIRS` unchanged (agents are not runtime files); `desiredFiles` adds, for each chosen
  harness with an `agentsDir` and a package folder `agents/<harness.id>/`, each `*.md` at
  `<agentsDir>/<name>.md`, `owner: harness.id`, rendered with `renderSkill` (token replaced; body invocations
  rewritten for that harness). An `agentNames(packageRoot, harnessId)` helper beside `skillNames`.
- `package.json` `files` gains `agents`; `skills/dgf-doctor/scripts/doctor.py` `SHIPPED_DIRS` gains `agents`;
  `tools/check_package.py` expects it. The doctor's install check counts an installed agent like a skill if it
  checks harness files by receipt (read it first).
- `status`/`uninstall` need no change if they work from the receipt by owner — verify with a test.

## Improve pass (2026-11-03) — binding corrections; where they disagree with the sections above, these win

Each was verified by an independent review in scratch repositories (git 2.54) or quoted from Claude Code's
sub-agents and worktrees documentation and this repository's code. ADR 0033 is amended to match.

1. **Base commit.** A Claude Code subagent worktree (`<repo>/.claude/worktrees/<name>/`, branch `worktree-<name>`)
   starts from the remote default branch unless `worktree.baseRef: "head"`. So `--sync`: when the worktree has no
   change of its own and its `HEAD` differs from main's, move the worktree's own branch to main's `HEAD` sha
   (`git -C <worktree> reset --hard <sha>`); `WORKTREE_HEAD_MISMATCH` only for a dirty worktree at another
   commit. `--merge` also refuses (`WORKTREE_HEAD_MISMATCH`) when main's `HEAD` no longer equals the recorded one.
2. **The coordinator passes `isolation: "worktree"` on every Agent call** as well as the worker's frontmatter.
3. **Linked-worktree test:** `git rev-parse --path-format=absolute --git-dir --git-common-dir`, compared with
   `Path.resolve()`; linked when git-dir ≠ common-dir; both sides must share the common dir.
4. **Status:** `git --no-optional-locks status --porcelain=v1 -z --untracked-files=all --no-renames -- <workspaces
   root relative to toplevel>`; paths are toplevel-relative (say so in the helper's docstring); skip entries ending
   in `/` and anything under `.claude/worktrees/`. ` D` (unstaged delete), `D ` and `??` all handled.
5. **CRLF (`core.autocrlf=true` is set globally on this machine):** never compare main's bytes with a `HEAD` blob.
   For a path not in the sync record, main is unchanged when the path is absent from main's current status; for a
   synced path, compare sha256 with the record.
6. **Exclusions** are relative to the workspaces root: `<root>/.dgf-factory/runtime/` and nothing else under
   `.dgf-factory/` is special — but the plan file and every other `.dgf-factory/` file still count as changes, so a
   worker that touches the plan is refused. **The sync record lives in the worktree's git dir:**
   `<git rev-parse --absolute-git-dir>/dgf-sync.json` — no status sees it, it cannot be committed, `worktree remove`
   deletes it. (No `.dgf-factory/parallel/`.)
7. **Modes and links:** `shutil.copymode` onto the temporary file before `os.replace`; on sync copy a symlink as a
   link (`os.readlink`/`os.symlink`); on merge refuse a symlink (as `git.materialise` skips links,
   `lib/git.py:166`) — report it as `WORKTREE_UNDECLARED_FILE` with "a symlink is never merged". Create parent
   folders for new files. A path in `files` must be added or modified; a path in `deletes` must be deleted.
8. **Cleanup:** `git worktree remove --force` fails on a locked worktree (Claude Code locks it while the agent
   runs): report `REMOVED: none — <path> is locked` and leave it (exit unaffected). `worktree list --porcelain -z`:
   a `detached` worktree has no branch to delete; strip `refs/heads/` otherwise.
9. **`lib/git.py` is read-only by contract** (`git.py:8-10`): the changing commands (`reset --hard`, `worktree
   remove`, `branch -D`) go in a new `scripts/lib/worktree.py` using `git._run` (returns stdout bytes, raises
   `GitError`). Read-only helpers (common dir, status) may go in either; prefer `lib/worktree.py` to keep `git.py`
   untouched (another agent may be adding to it).
10. **Plan parsing:** `plan.parse` raises only `PlanFormatError(line, message)` → `PLAN_UNREADABLE` exit 3 as
    `check_plan.py:667-668` does. `PLAN_FORMAT_UNSUPPORTED`: move `SUPPORTED_FORMAT` (`check_plan.py:57`) into
    `lib/plan.py` (re-export from check_plan so nothing else breaks) and check it in `plan_layers.py`. Ultra tasks
    are in `index.md`; `plan_layers.py` prints each ready ultra task's phase file (`PHASE: <n> <path>`) so the
    coordinator can pass it to the worker.
11. **Agents:**
    - both: `permissionMode: acceptEdits`; the four dgf-mcp tools `dgf-implement` uses
      (`mcp__dgf-mcp__get_component_doc`, `get_json_schema_details`, `get_component_examples`,
      `get_xml_property_reference`) in `tools:`;
    - the coordinator calls `python3 "{{dgf_runtime}}/scripts/…"` (relative, it runs in the project root);
    - the worker calls `python3 "<main project>/{{dgf_runtime}}/scripts/…"` — written exactly so, so the contract
      tests' `SCRIPT_CALL` regex sees it — and its text says why: the worktree's runtime has no `.venv`, and the
      preloaded `/dgf-implement`'s relative paths would lead there;
    - the coordinator's prompt to a worker carries the main project root, the main workspaces root, the plan path,
      the task number, the ultra phase file if any, and `git.base_branch`.
12. **Setup:** `nextSteps` (`cli/commands/setup.mjs:162-168`) prints, when `claude` is chosen, "add
    `.claude/worktrees/` to .gitignore" and names `.claude/agents/` among the files to commit. `preview.mjs:31`'s
    group label may mention agents. Doctor: `check_harness_skills` needs no completeness check for agents (they are
    not runtime files); the missing/edited checks already cover them — confirm with a test.
13. **Contract tests (integration, not this task):** `skill_markdown()` will include `agents/**/*.md`;
    `relative_to(SKILLS)` → `PLUGIN_ROOT`; a test that both agents' `tools:` include the MCP tools.

## Tasks

- [x] Task 1: `scripts/plan_layers.py` + `tests/test_plan_layers.py` — ready/serial/cycle/cap/complete, ultra.
- [x] Task 2: `lib/git.py` helpers + `scripts/worktree_task.py` + `tests/test_worktree_task.py` — real linked
  worktrees: sync copies dirty/untracked/deleted and skips runtime and ignored files; HEAD mismatch; not linked;
  merge copies only declared files; undeclared (incl. the plan) refused with nothing copied; main changed
  refused; `--cleanup` removes worktree and branch; `--help` lists every flag. (independent of 1)
- [x] Task 3: `agents/claude/dgf-implement-coordinator.md`, `agents/claude/dgf-implement-worker.md`. (depends on 1, 2)
- [x] Task 4: install — `cli/plan.mjs`, `package.json`, doctor `SHIPPED_DIRS`, `tools/check_package.py`, node tests
  in `tests/cli/plan.test.mjs`/`setup.test.mjs` (claude gets `.claude/agents/dgf-implement-*.md`, gemini none;
  uninstall removes them), and `tests/test_skill_contracts.py` extended (or a new test) so the agents' script
  calls, flags and codes are held to the scripts like a skill's. (depends on 3)
- [x] Task 5: docs — `docs/pipeline.md` (parallel section), `docs/getting-started.md`, README, AGENTS.md (structure:
  `agents/` created; entry points), ADR index row for 0033, ROADMAP tick.
- [x] Task 6: verify — full Python suite, node suite, doc check, `tools/check_package.py`, `tools/smoke_install.sh`
  (it must install the agents for claude).

## Done means

The two scripts tested over real worktrees; the two agents shipped and installed for Claude Code by setup and
removed by uninstall; contract tests hold the agents' script calls; every check green.
