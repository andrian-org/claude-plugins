---
name: dgf-doctor
description: Check that dgf-factory is installed correctly in this project and report what it can see. Use for "is dgf-factory working", "skills not loading", "check the install", "dgf doctor", "why is the skill not firing", "did setup work".
allowed-tools: Read Bash(python3 "{{dgf_runtime}}/skills/dgf-doctor/scripts/*)
disable-model-invocation: false
version: 0.3.0
---

# DGF Doctor — Installation Check

Answer one question: **is dgf-factory installed correctly in this project, and what can it see?**

The answer comes from a script, not from reading files. Structure is statically
checkable, so checking it by eye is a defect — the model can miss a malformed
frontmatter block, the script cannot.

This skill reports installability, not completeness. Build progress is `INFO`
lines that never affect the verdict.

`dgf-factory setup` installed this project: the runtime under `.dgf-factory/runtime/`, a
`SKILL.md` per skill in each harness's folder, and a receipt, `.dgf-factory/install.json`,
recording every file it wrote with two hashes. The doctor checks the install against that
receipt.

## Workflow

### Step 1: Run the structural check

```bash
python3 "{{dgf_runtime}}/skills/dgf-doctor/scripts/doctor.py"
```

Always `{{dgf_runtime}}`, from the project root — where the harness found this skill. Never an
absolute path: the project is committed and cloned elsewhere.

Capture the exit code **before** any pipe. `cmd | tail` returns `tail`'s status, which
would turn every failure into a pass.

When the user is asking why a specific check failed, re-run with a trace:

```bash
DEBUG=1 python3 "{{dgf_runtime}}/skills/dgf-doctor/scripts/doctor.py"
```

### Step 2: Act on the exit code

| Code | Meaning | What you do |
|------|---------|-------------|
| `0` | clean | Continue to Step 3. dgf-factory is correctly installed. |
| `1` | blocked | **STOP.** Relay the findings verbatim. Do not repair anything. |
| `2` | warnings | Continue to Step 3, and surface **every** warning to the user. |
| `3` | usage error, or no gate builder | **STOP.** The invocation is wrong, or the install is incomplete. |

On `1`, the install is broken, a slice will not register, or a shipped file names a
path into the DGF repository (`DGF_PATH`). A developer's install has no DGF checkout, so
such a path points at nothing. Report what the script found and stop there — repairing it
silently hides the fault from the person who has to fix the install. The install's own
findings:

- **`INSTALL_FILE_MISSING`** (error, exit `1`) — a file the receipt lists is not on disk.
- **`INSTALL_HARNESS_INCOMPLETE`** (error, exit `1`) — a chosen harness lacks a skill.
- **`INSTALL_RECEIPT_UNREADABLE`** (error, exit `1`) — `.dgf-factory/install.json` cannot be read.
- **`INSTALL_FILE_EDITED`** (warning, exit `2`) — an installed file was edited. Setup keeps the
  edit and will not update that file; say so.
- **`INSTALL_VERSION_DRIFT`** (warning, exit `2`) — the `dgf-factory` CLI on PATH is a different
  version from the one that installed this project; `dgf-factory setup` updates it.

Two more blocking findings mean a skill will misbehave once loaded:

- **`RUNTIME_PATH_DANGLING`** (error, exit `1`) — a shipped Markdown file cites a runtime
  path that does not exist, so the skill that runs it fails at that step.
- **`LINK_LEAVES_SHIPPED`** (error, exit `1`) — a shipped Markdown file links a file that is
  not installed (ADR 0030 §3).
- **`SKILL_FRONTMATTER_YAML`** (error, exit `1`) — an unquoted frontmatter value that YAML
  reads differently from this check, or not at all (it starts with `[`, `{`, `*`, `&`, `!`,
  `%`, `@`, a backtick, `|` or `>`, or holds `: ` or ` #`). The skill may not load.

The same exit code also covers the validators under `scripts/`:

- **`VALIDATOR_DEPS_MISSING`** (warning, exit `2`) — `lxml` or `jsonschema` is not installed,
  so every validator exits `3` until it is. The warning carries the exact install command;
  relay it verbatim. Never run it yourself: re-running `dgf-factory setup` is the user's step.
- **`REQUIREMENTS_UNPINNED`** (error, exit `1`) — `scripts/requirements.txt` is missing, or a
  requirement is not pinned to one version with a `sha256` hash.
- **`KNOWLEDGE_TABLE`** (error, exit `1`) — a machine-read table in `{{dgf_runtime}}/knowledge/` is missing or
  malformed, so the validators that read it refuse to run.

A section that could not run — no `skills/`, no `scripts/` — is a `NOT RUN` line and a
`not-run-<section>` warning, exit `2`. It is never a silent pass. A runtime with no `scripts/`
has no gate builder either, so its own doctor exits `3`.

On `3`, either the script was called incorrectly, or the runtime's own
`scripts/lib/gate_result.py` — which builds the gate block — is missing, does not load, or
lacks what the doctor calls. Show
the stderr message. For a bad call, do not retry with guessed arguments. For a missing builder,
no block is printed: say `dgf-factory setup` must be re-run.

### Step 3: Relay the report

Pass the script's output through **verbatim**, including its closing
`dgf-gate-result` block, and write **nothing after it**.

The block is built by `scripts/lib/gate_result.py` (ADR 0022), never by you. It holds:

- `gate: "doctor"` — this is not a verify gate, and a doctor pass is not a verified change;
- `status`, and `blocking: true` only on a `fail`;
- errors in `blockers`, and warnings — including each `not-run-<section>` — in `warnings`;
- `checks_run`, the sections that ran;
- `suggested_next.command` always `null`: a broken install is fixed by re-running
  `dgf-factory setup` or by hand, never by `/dgf-fix`, then the doctor is re-run.

It has no `schema_family`, `affected_components` or `affected_processes`: the doctor reads no
estate, and a field it did not compute is left out rather than emitted empty.

Callers parse only the final gate block. A second block written by this prompt — even a
summarising one — silently overrides the deterministic verdict. Last block wins.

If the user asked a narrower question ("is the Claude skill folder complete?"), answer it *before* the
relayed report, never after it.

## Execution Rules

### DO:

- ✅ Run the script and report what it returns
- ✅ Quote findings verbatim, with their file and line
- ✅ Surface every warning on exit `2`, not just the first
- ✅ Offer `DEBUG=1` when the user asks why a check failed
- ✅ Distinguish "not yet built" (`INFO`, expected) from "broken" (`ERROR`)

### DON'T:

- ❌ Diagnose by reading files instead of running the script
- ❌ Repair anything the script reported — this skill is read-only
- ❌ Write any text after the `dgf-gate-result` block
- ❌ Claim a check the script did not run
- ❌ Treat an unbuilt slice as a fault
- ❌ Run `pip` or install the validators' dependencies — relay the command instead
- ❌ Hardcode a path to the script instead of using `{{dgf_runtime}}`

## Artifact Ownership

- **Owns:** nothing. This skill writes no artifact.
- **Reads:** the install receipt, the installed files, the skill slices and the runtime, via the script.
- **Modifies:** nothing, ever. It is a pure diagnostic.

## Critical Rules

1. **The script decides, not the prompt.** Never substitute a judgement for a check.
2. **Never repair what the script reported.** Report and stop; fixing belongs elsewhere.
3. **Never claim a check that did not run.** A gate that reads as having passed a check
   it skipped is worse than no gate.
4. **Exactly one gate block, and it is the script's.** Write nothing after it.
5. **`{{dgf_runtime}}` always.** A machine-specific path works for its author and
   nobody else.

## See Also

Maintainer documentation in the dgf-factory repository, not installed with the tool:

- `docs/skill-authoring.md` — the contract this skill follows
- `docs/architecture.md` — where a slice's files belong
