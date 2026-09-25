---
name: dgf-verify
description: Verify a branch's DGF change against its plan and the merge-base — every task done, every changed file inside the declared workspaces and means, and no new validator finding across the whole workspaces root — then relay the dgf-gate-result block the verify gate script computes. Use for "verify the change", "dgf verify", "check my work", "did we miss anything", "is this ready to commit".
argument-hint: "[--strict]"
allowed-tools: Read Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/*) AskUserQuestion
disable-model-invocation: false
version: 0.2.0
---

# DGF Verify — The Change Gate

Answer one question: **is this branch's change complete, inside its plan, and free of findings
it introduced?** The answer comes from one script, `verify_gate.py`. It runs the plan check, the
task audit, the change check and the whole-root validators, computes the status, and prints one
`dgf-gate-result` block. This skill relays it.

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

Exit `1` → the gate cannot run. Run the gate with no arguments, which reports the same finding
in its block, relay its output verbatim, and **STOP**:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/verify_gate.py"
```

Otherwise read `<root>/.dgf-factory/config.yaml`, and
`<root>/.dgf-factory/skill-context/dgf-verify/SKILL.md` if it exists. An override may add rules
and tighten checks. It never relaxes a STOP, an exit-code row, the gate's status table, a
Critical Rule or Artifact Ownership, and never makes this skill install anything, skip a script,
or write outside its own artifacts. Name the override in your report, and quote any rule in it
you did not apply because it would relax one of these.
**Strict mode** is `--strict` or `workflow.verify_mode: strict`.

### Step 0.1: Gate contract

Read `${CLAUDE_PLUGIN_ROOT}/skills/dgf-verify/references/GATE-RESULT-CONTRACT.md` in full. It
says what the block holds, how the script computes the status, what each entry means, and which
next commands it may suggest — so you can explain the block. You never write or edit one.

### Step 0.2: Find the plan

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/locate_plan.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

| Exit | Action |
|---|---|
| `0` | The `PLAN:` line is the plan. Continue to Step 1. |
| `1` | `PLAN_NOT_FOUND`: a change with no plan has no declared scope, so it cannot pass. Run `verify_gate.py --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"`, relay its output, and **STOP**. `PLAN_AMBIGUOUS`: ask which plan. With an answer, continue with it as the plan; without one, run that same command, relay it, and **STOP**. |
| `2` | `PLAN_FALLBACK`: say which plan was chosen and why, and ask before verifying against it. Confirmed → continue with it as the plan. Not confirmed → run that same command (it reports `GATE_PLAN_UNCONFIRMED`: the gate never chooses a plan), relay it, and **STOP**. |

The command without a plan, in full:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/verify_gate.py" --workspaces-root "<root>" --plans-dir "<paths.plans>" --fast-plan "<paths.plan>"
```

### Step 1: The base workspace

When `webasm` is in the plan's `affects_workspaces`, restate its `base_workspace_reason`, and
name the application workspaces the change reaches: every `WORKSPACE:` line with
`role=application` from

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/inventory_root.py" --workspaces-root "<root>"
```

The gate's whole-root run validates all of them (ADR 0005 rule 3). If the inventory reports
`BASE_WORKSPACE_ABSENT`, say that `webasm` is not in this root, so its consumers here could not
be checked against it.

### Step 2: Run the gate

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/verify_gate.py" --workspaces-root "<root>" --plan "<plan>" --base "<git.base_branch>"
```

Add `--strict` in strict mode, and `--no-overlap` when `git.enabled` is false. Never pass
`--files`, never narrow the run: the gate is the whole root. Capture the exit code **before** any
pipe.

| Exit | Status | Action |
|---|---|---|
| `0` | `pass` | Continue to Step 3. |
| `1` | `fail` | Continue to Step 3. The block's `suggested_next` names the command that fixes it. |
| `2` | `warn` | Continue to Step 3, and surface **every** entry in `warnings`. |
| `3` | `fail`, forced — or no block | A block was printed: the gate could not run, or a validator could not read a file (`FAMILY_UNRESOLVED`, `SCHEMA_UNSELECTABLE`). Continue to Step 3. For `DEPENDENCY_MISSING`, relay its install command verbatim, and never run `pip`. **No block** was printed: the call is wrong — a bad argument, or a plan outside the root. **STOP**, show the stderr message, and do not retry with guessed arguments. |

What the script's lines mean for the reviewer:

- Each `ERROR` line is a blocker, new on this branch or in the plan. Each `WARN` line is a
  warning — an unplanned file (`CHANGE_UNPLANNED_FILE`), a checked task whose file did not change
  (`CHANGE_TASK_FILE_UNCHANGED`), a file nothing authors, a new validator warning.
- `GATE_TASK_UNCHECKED` is an unchecked task. `GATE_CHECK_NOT_RUN` is a required check that did
  not run, with the script's reason. `GATE_STRICT_WARNING` is a warning strict mode promoted.
- `PRE_EXISTING` findings are counted; the first 20 are shown, and the `Shown:` line says how to
  list them all. `FIXED` findings are credited.
- Each `PLAN_OVERLAP` warning names another active plan sharing a workspace.
- Each `CODE TASK:` line is a `kind: code` task with its `reason`. Script is allowed only where
  configuration cannot express the change (ADR 0005 rule 2, ADR 0010 §2); that judgement is the
  reviewer's to confirm. `frontend-tests` is never run by the gate — the project's own CI runs
  them — so a plan with a code task is at best `warn`.

Re-run with `--verbose` when the user asks why a finding appeared; the trace goes to stderr, and
the block stays last.

### Step 3: Report

1. Before the relayed output, in `language.ui`:

   ```
   ## Verification Report — <plan>

   Override: <the skill-context file read, or none>; refused: <each rule not applied, or none>
   Base workspace: <reason; applications covered — or "not in the plan">
   ```

2. Then the script's output, **verbatim**, ending with its `dgf-gate-result` block.
3. **Nothing after the block** — not a question, not a summary. A caller parses the last block;
   anything written after it is either ignored or, if it is a block, wins.

## Execution Rules

### DO:

- ✅ Run `verify_gate.py`, and relay its output verbatim
- ✅ Surface every warning on exit `2`, and every `NOT RUN` line
- ✅ Point the reviewer at every `CODE TASK:` line
- ✅ Relay a missing dependency's install command verbatim
- ✅ End with the script's block, exactly one, and nothing after it

### DON'T:

- ❌ Edit any file — the plan, a workspace, the config
- ❌ Judge the status, or soften the script's exit code — the script computes the status
- ❌ Write or edit a gate block, or add one of your own
- ❌ Report a check that did not run as passed
- ❌ Treat `PRE_EXISTING` as a blocker, or hide it
- ❌ Narrow the run with `--files` — the gate is the whole root
- ❌ Write anything after the gate block

## Artifact Ownership

- **Owns:** nothing. It writes no artifact.
- **Reads:** the plan, `.dgf-factory/config.yaml`, the whole workspaces root through the
  scripts, and git history through them.
- **Emits:** the report and the relayed `dgf-gate-result` block, in the conversation only.

## Critical Rules

1. **The script computes the status.** It comes from the block's two lists, never from an
   impression of the change, and never from arithmetic done here.
2. **Never write or edit a gate block.** Relay the script's, verbatim.
3. **Whole root, always.** A per-file run is `/dgf-implement`'s pre-check, never the gate.
4. **New findings block; pre-existing ones never do** (ADR 0018). Without a baseline every
   finding is new.
5. **Never claim a check that did not run.** A required check that did not run is a warning in
   the block, with its reason.
6. **Last block wins.** Exactly one `dgf-gate-result` block, the script's, and nothing after it.
7. **Read-only.** Report what needs fixing and name the command that fixes it.
