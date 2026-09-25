---
name: dgf-verify
description: Verify a branch's DGF change against its plan and the merge-base — every task done, every changed file inside the declared workspaces and means, and no new validator finding across the whole workspaces root — then emit a dgf-gate-result block. Use for "verify the change", "dgf verify", "check my work", "did we miss anything", "is this ready to commit".
argument-hint: "[--strict]"
allowed-tools: Read Glob Grep Bash(python3 *) Bash(git *) AskUserQuestion
disable-model-invocation: false
version: 0.1.0
---

# DGF Verify — The Change Gate

Answer one question: **is this branch's change complete, inside its plan, and free of findings
it introduced?** The answer comes from three scripts, and ends in one `dgf-gate-result` block
whose status is computed from their exit codes.

The gate's scope is the **whole workspaces root** (ADR 0004): a change in one file can break a
file it never touched. Findings the estate already had are compared away against the
merge-base (ADR 0018): they are reported as `PRE_EXISTING`, and never block.

This skill is **read-only.** It changes no file — not the plan, not a workspace. Fixing belongs
to `/dgf-implement`, and a defective plan to `/dgf-plan`.

It ports AI Factory's `/aif-verify`. Its build, test and lint steps become the validators; its
context gates, Handoff and roadmap checks are dropped.

## Workflow

### Step 0.0: Config

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --root-only
```

Exit `1` → the gate cannot run: report it, and end with a `fail` block whose
`suggested_next.command` is `null` (`ROOT_NOT_SET_UP`: run `/dgf`). Otherwise read
`<root>/.dgf-factory/config.yaml`, and `<root>/.dgf-factory/skill-context/dgf-verify/SKILL.md`
if it exists. **Strict mode** is `--strict` or `workflow.verify_mode: strict`.

### Step 0.1: Gate contract

Read `${CLAUDE_PLUGIN_ROOT}/skills/dgf-verify/references/GATE-RESULT-CONTRACT.md` in full. It
fixes the block's fields, how status is computed, what a blocker is, the required checks, and
the allowlist of next commands. Follow it exactly.

### Step 0.2: Find the plan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is the plan. |
| `1` | `PLAN_NOT_FOUND`: a change with no plan has no declared scope, so it cannot pass. Report it and end with a `fail` block, next command `/dgf-plan`. `PLAN_AMBIGUOUS`: ask which plan, or end with a `fail` block, next command `null`. |
| `2` | `PLAN_FALLBACK`: say which plan was chosen and why, and ask before verifying against it. |

### Step 0.3: Check the plan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_plan.py" "<plan>" --workspaces-root "<root>" --overlap
```

Leave out `--overlap` when `git.enabled` is false. Keep the exit code and every finding. Exit
`1` is a defective plan (next command `/dgf-plan`). Each `PLAN_OVERLAP` warning names another
active plan sharing a workspace: list them all. The `TASK:` lines feed Step 1.

### Step 1: Task completion audit

From the `TASK:` lines: every task must be `[x]`. Each unchecked task is a `task-<N>` blocker,
severity `error` (next command `/dgf-implement`). Report the count as `done/total`.

### Step 2: The change

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_change.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>"
```

No `--files`: the gate is the whole root. Capture the exit code before any pipe. Then:

- **Quote every `ERROR` line verbatim.** Each is new on this branch.
- **Surface every `WARN` line** — an unplanned file (`CHANGE_UNPLANNED_FILE`), a checked task
  whose file did not change (`CHANGE_TASK_FILE_UNCHANGED`), a file nothing authors, a new
  validator warning.
- **`PRE_EXISTING`:** give the count, and the first 20 lines. **`FIXED`:** give the count.
- **Keep every `NOT RUN` line.** `change-scope`, `change-means` and `baseline` are `NOT RUN`
  without git or a merge-base; each is a `not-run-<check>` blocker, and then every validator
  finding counted as new.
- Exit `3` is a gate that could not run — most often `DEPENDENCY_MISSING`: relay the install
  command verbatim, and end with a `fail` block, next command `null`. Never run `pip`.

Re-run with `--verbose` when the user asks why a finding appeared.

### Step 3: Code tasks

List each `kind: code` task with its `reason`, for the reviewer: script is allowed only where
configuration cannot express the change (ADR 0005 rule 2, ADR 0010 §2), and that judgement is
the reviewer's to confirm. `frontend-tests` is `NOT RUN`: the project's own CI runs its
frontend tests, where they exist. With any `kind: code` task, that makes the status at least
`warn` — never `pass`.

### Step 4: The base workspace

When `webasm` is in `affects_workspaces`, restate the plan's `base_workspace_reason`, and name
the application workspaces the change reaches: every `WORKSPACE:` line with
`role=application` from

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/inventory_root.py" --workspaces-root "<root>"
```

Step 2's whole-root run validated all of them (ADR 0005 rule 3). If the inventory reports
`BASE_WORKSPACE_ABSENT`, say that `webasm` is not in this root, so its consumers here could not
be checked against it.

### Step 5: Report

1. The report, in `language.ui`:

   ```
   ## Verification Report — <plan>

   Tasks: <done>/<total>
   Plan check: exit <n> — <findings>
   Change: <CHANGED count> files; new: <e> error(s), <w> warning(s); pre-existing: <p>; fixed: <f>
   Not run: <every NOT RUN line, with its reason>
   Code tasks: <task, reason> …
   Base workspace: <reason; applications covered>

   ### Blocking
   <every blocker, verbatim>

   ### Warnings
   <every WARN line>
   ```

2. The status, from the contract's table — the worst row wins. In strict mode a new warning is
   `fail`.
3. **The `dgf-gate-result` block, last.** Nothing — not a question, not a summary — after it.

## Execution Rules

### DO:

- ✅ Run the three scripts, and build the status from their exit codes
- ✅ Quote every `ERROR`, surface every `WARN`, keep every `NOT RUN`
- ✅ Count `PRE_EXISTING` findings, and show the first 20
- ✅ List every `kind: code` task with its reason
- ✅ End with exactly one `dgf-gate-result` block

### DON'T:

- ❌ Edit any file — the plan, a workspace, the config
- ❌ Judge the status, or soften a script's exit code
- ❌ Report a check that did not run as passed
- ❌ Treat `PRE_EXISTING` as a blocker, or hide it
- ❌ Narrow the run with `--files` — the gate is the whole root
- ❌ Emit fields the contract marks as not yet emitted
- ❌ Write anything after the gate block

## Artifact Ownership

- **Owns:** nothing. It writes no artifact.
- **Reads:** the plan, `.dgf-factory/config.yaml`, the whole workspaces root through the
  scripts, and git history.
- **Emits:** the report and the `dgf-gate-result` block, in the conversation only.

## Critical Rules

1. **The scripts decide; the status is arithmetic.** It comes from the contract's table and
   the exit codes, never from an impression of the change.
2. **Whole root, always.** A per-file run is `/dgf-implement`'s pre-check, never the gate.
3. **New findings block; pre-existing ones never do** (ADR 0018). Without a baseline every
   finding is new.
4. **Never claim a check that did not run.** A required `NOT RUN` check is a blocker.
5. **Last block wins.** Exactly one `dgf-gate-result` block, and nothing after it.
6. **Read-only.** Report what needs fixing and name the command that fixes it.
