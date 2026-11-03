---
id: 0035
title: "No skill pre-approves git, and each script rule names one script"
status: accepted
date: 2026-11-03
deciders: [Andrian Mamei]
supersedes: []
tags: [security, permissions, skills]
---

# 0035 — No skill pre-approves git, and each script rule names one script

**Status: accepted** (2026-11-03, Andrian Mamei), under the delegation recorded in
[ADR 0032](0032-quality-and-authoring-skills.md): the security check the decider asked for found the two grants
below, and the fix was drawn from the evidence, not put to the decider.

## Context

Read on **2026-11-03** from this repository, by a security review that ran each case.

- **`Bash(git *)` is a shell.** `/dgf`, `/dgf-plan`, `/dgf-implement` and `/dgf-commit` pre-approved it, because
  `git -C "<root>" <subcommand>` cannot be narrowed below it (`docs/skill-authoring.md`, before this ADR). The same
  rule pre-approves `git -c alias.tidy="!<any command>" tidy` and `git -c core.fsmonitor="<any command>" status`:
  both ran a command of the reviewer's choosing with no prompt. A skill reads text anyone who commits to the estate
  can write — an override, the rules file, `RESEARCH.md`, a patch — so a sentence there that steers the model into
  such a call needed no approval from anyone.
- **`Bash(python3 "{{dgf_runtime}}/scripts/*)` matches a walk out of the folder.** The `*` matches
  `scripts/../../FM/x.py`, so any `.py` file in the estate ran pre-approved. A rule that names the script cannot be
  walked out of: `scripts/check_change.py/../x.py` does not resolve, because a file is not a directory.
- **Pre-approval is convenience, not capability.** A command no rule matches still runs after the user approves it
  (`docs/skill-authoring.md`, "it pre-approves, it never restricts"). Dropping a rule costs a prompt, not a feature.

## Decision

1. **No skill pre-approves any git command.** Every git command a skill runs is shown to the user and approved in
   the harness's own prompt. The skills' text is unchanged: they still run the same commands.
2. **Each script rule names one script**: `Bash(python3 "{{dgf_runtime}}/scripts/<name>.py"*)`, one per script the
   skill or its references call, and `Bash(bash "{{dgf_runtime}}/scripts/security-scan.sh" *)` for the scan.
3. `tests/test_skill_contracts.py` holds both: no rule starts with `git`, and every Bash rule names one script.
4. The override limit (`scripts/lib/overrides.py` `FORBIDDEN`), which the rules check reuses, refuses shell
   execution constructs — `sh -c`, `git -c`, command-running git config keys, `rm -r`, `python -c`, `node -e`,
   command substitution — so such a rule never reaches a reader.

5. **The installer trusts nothing a repository ships**, by the same security check:
   - a write never follows a link: the temporary file has a random name and is opened exclusively without
     following links (`cli/fsops.mjs`), a target that is a link is refused, and a link at an install target is a
     conflict that is never read or diffed (`cli/plan.mjs`);
   - a receipt entry must lie where setup installs for its owner — under `.dgf-factory/runtime/`, or the owning
     harness's skills, agents or former folders — and never in a `.git` folder; setup, `status` and `uninstall`
     refuse any other receipt, the doctor blocks on it (`INSTALL_RECEIPT_ENTRY_MISPLACED`), and the change checks
     never let such an entry hide a change (`INSTALL_RECEIPT_ENTRY_IGNORED`);
   - a committed `.dgf-factory/runtime/.venv` is never run by setup or the doctor (`INSTALL_VENV_COMMITTED`);
   - no XML reader expands a DTD, and JSON nested too deep to read is a finding, not a traceback.

## Alternatives considered

- **Narrow git rules with a leading `*`** (`Bash(git -C * status*)`). Rejected: the `*` before the subcommand also
  matches `-c alias.x=…`, and Claude Code warns about the form.
- **Run git without `-C`**, so `Bash(git status *)` could match. Rejected: the session's folder is not always the
  root, porcelain paths are then relative to another folder, and `git diff --output=<file>` still writes.
- **A git wrapper script** exposing only the operations the skills use. Not rejected — the right next step, and a
  follow-up: it would restore the pre-approval for read-only git with a script deciding each argument.

## Consequences

### Positive

- No text in an estate can run a command through a dgf-factory skill without the user seeing it.
- No file in an estate runs as a pre-approved script.

### Negative

- `/dgf`, `/dgf-plan`, `/dgf-implement` and `/dgf-commit` prompt once per git command.
- **A script reached through the venv trusts the venv.** Each validator re-runs itself under
  `.dgf-factory/runtime/.venv` (ADR 0031) without asking git whether it is committed; setup and the doctor do ask.
  The runtime's own scripts are committed too, by ADR 0029, so a repository that can plant a venv can plant a
  script: the receipt's hashes, which the doctor checks, are the defence for both.
- **A parallel worker writes its own sync record**, so a worker steered off its prompt could hide a concurrent
  main-tree edit to a file its task declares. It still cannot reach a file the task does not declare (ADR 0033).

### Follow-ups

- **A git wrapper script** (`scripts/git_step.py`) for the read-only queries — status, diff names, the current
  branch, the remote's default — and the few writes the skills make, each argument checked, so they can be
  pre-approved again by name.
