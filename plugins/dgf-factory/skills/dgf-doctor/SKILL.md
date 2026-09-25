---
name: dgf-doctor
description: Check that the dgf-factory plugin is installed correctly and report what it can see. Use for "is dgf-factory working", "plugin not loading", "check plugin install", "dgf doctor", "why is the skill not firing".
allowed-tools: Read Bash(python3 *)
disable-model-invocation: false
version: 0.1.0
---

# DGF Doctor — Plugin Installation Check

Answer one question: **is this plugin installed correctly, and what can it see?**

The answer comes from a script, not from reading files. Structure is statically
checkable, so checking it by eye is a defect — the model can miss a malformed
frontmatter block, the script cannot.

This skill reports installability, not completeness. Unbuilt milestones are `INFO`
lines that never affect the verdict, so a correct-but-unfinished plugin is `CLEAN`.

## Workflow

### Step 1: Run the structural check

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-doctor/scripts/doctor.py"
```

Always `${CLAUDE_PLUGIN_ROOT}`. Never an absolute path, never a path relative to the
working directory — the plugin runs from wherever the user installed it.

Capture the exit code **before** any pipe. `cmd | tail` returns `tail`'s status, which
would turn every failure into a pass.

When the user is asking why a specific check failed, re-run with a trace:

```bash
DEBUG=1 python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-doctor/scripts/doctor.py"
```

### Step 2: Act on the exit code

| Code | Meaning | What you do |
|------|---------|-------------|
| `0` | clean | Continue to Step 3. The plugin is correctly installed. |
| `1` | blocked | **STOP.** Relay the findings verbatim. Do not repair anything. |
| `2` | warnings | Continue to Step 3, and surface **every** warning to the user. |
| `3` | usage error | **STOP.** The invocation is wrong, not the plugin. |

On `1`, the plugin cannot load, a slice will not register, or a shipped file names a
path into the DGF repository (`DGF_PATH`). A developer's install has no DGF checkout, so
such a path points at nothing. Report what the script found and stop there — repairing it
silently hides the fault from the person who has to fix the install. Two more blocking
findings mean a skill will misbehave once loaded:

- **`PLUGIN_PATH_DANGLING`** (error, exit `1`) — a shipped Markdown file cites a
  `${CLAUDE_PLUGIN_ROOT}/…` path that does not exist in the plugin, so the skill that runs
  it fails at that step.
- **`SKILL_FRONTMATTER_YAML`** (error, exit `1`) — an unquoted frontmatter value that YAML
  reads differently from this check, or not at all (it starts with `[`, `{`, `*`, `&`, `!`,
  `%`, `@`, a backtick, `|` or `>`, or holds `: ` or ` #`). The skill may not load.

The same exit code also covers the validators under `scripts/`:

- **`VALIDATOR_DEPS_MISSING`** (warning, exit `2`) — `lxml` or `jsonschema` is not installed,
  so every validator exits `3` until it is. The warning carries the exact install command;
  relay it verbatim. The plugin cannot install anything itself, and neither may you.
- **`REQUIREMENTS_UNPINNED`** (error, exit `1`) — `scripts/requirements.txt` is missing, or a
  requirement is not pinned to one version with a `sha256` hash.
- **`KNOWLEDGE_TABLE`** (error, exit `1`) — a machine-read table in `knowledge/` is missing or
  malformed, so the validators that read it refuse to run.

On `3`, the script was called incorrectly. Show its stderr message; do not retry with
guessed arguments.

### Step 3: Relay the report

Pass the script's output through **verbatim**, including its closing
`dgf-gate-result` block, and write **nothing after it**.

Callers parse only the final gate block. A second block written by this prompt — even a
summarising one — silently overrides the deterministic verdict. Last block wins.

If the user asked a narrower question ("is the manifest OK?"), answer it *before* the
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
- ❌ Treat an absent `knowledge/`, `agents/` or unbuilt slice as a fault
- ❌ Run `pip` or install the validators' dependencies — relay the command instead
- ❌ Hardcode a path to the script instead of using `${CLAUDE_PLUGIN_ROOT}`

## Artifact Ownership

- **Owns:** nothing. This skill writes no artifact.
- **Reads:** the plugin's own manifest, skill slices and shipped files, via the script.
- **Modifies:** nothing, ever. It is a pure diagnostic.

## Critical Rules

1. **The script decides, not the prompt.** Never substitute a judgement for a check.
2. **Never repair what the script reported.** Report and stop; fixing belongs elsewhere.
3. **Never claim a check that did not run.** A gate that reads as having passed a check
   it skipped is worse than no gate.
4. **Exactly one gate block, and it is the script's.** Write nothing after it.
5. **`${CLAUDE_PLUGIN_ROOT}` always.** A machine-specific path works for its author and
   nobody else.

## See Also

- [Skill Authoring](../../docs/skill-authoring.md) — the contract this skill follows
- [Architecture](../../docs/architecture.md) — where a slice's files belong
