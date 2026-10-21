---
id: 0018
title: "A gate blocks on what the branch introduced: findings are compared with the merge-base"
status: accepted
date: 2026-09-25
deciders: [Andrian Mamei]
supersedes: []
tags: [gates, verification, brownfield, validators]
---

# 0018 — A gate blocks on what the branch introduced: findings are compared with the merge-base

**Status: accepted** (2026-09-25, Andrian Mamei). The decider chose this option on 2026-09-25 while
roadmap milestone 9 ("Pipeline Spine") was planned, from the three options in §Alternatives. It
decides how `/dgf-verify` and `/dgf-implement` read the validators' findings on an estate that
already has errors.

## Context

Read on **2026-09-25** from this repository (`develop` at `a3e02a3`). DGF paths are relative to the
DGF repository root at `aa1d5c4c2`.

- **The gate's scope is the whole root.** [ADR 0004](0004-authoring-entry-point.md) makes the plugin
  brownfield-first (`docs/adr/0004-authoring-entry-point.md:64-72`) and makes the whole workspaces
  root the unit of work: "A narrowed run is explicitly **not sufficient to pass a gate**"
  (`:85-100`). A gate therefore validates every file in the root, not just the files a branch
  touched.
- **Real estates already carry errors.** [ADR 0014](0014-process-verification-runtime-resolution.md)
  found two true defects in DGF's own samples
  (`docs/adr/0014-process-verification-runtime-resolution.md:178-190`):
  `zims/FM/_PROCESS/ZIMS4_InspectionBorder/process.xml` names an absent workflow, and
  `zims/FM/_WORKFLOW/Expert.MoveTaskTo/_workflow.xml` moves to an undeclared state.
  `tools/known-good-exceptions.txt` records 60 `EXCEPTION` lines and 8 `EXPECTED_EXTERNAL` lines
  that the validators raise on those samples: 71 errors excused by `EXCEPTION` and 9 by
  `EXPECTED_EXTERNAL` (its header, lines 8–13). Every one is a real finding in a file the runtime
  serves. A developer's estate has no such file, so a whole-root gate on an estate like the samples
  fails on the first run, whatever the branch did.
- **Scoping to changed files is not enough either.** A branch can break a file it never touched:
  deleting a workflow makes every untouched process that names it unresolved, and a `CHANGE_STATE`
  step fails when the process it targets loses a state. The process checks resolve references
  across files and workspaces (ADR 0014 §2), which is why the gate runs over the whole root.
- **The validators run in-process and return reports.** `validate_config.validate_file`,
  `resolve_components.check_file`, `validate_process.check_file` and
  `process_checks.check_workflow` each return a `Report`. `tools/run_known_good.py:144-167`
  (`run_validators`) composes them over a root. `scripts/lib/cli.py:77-82` (`display`) makes a
  report's file path relative to the working directory, and some messages embed a resolved path
  (`scripts/lib/process_checks.py:231, 310`), so the same finding reads differently at two roots.
- **What git can produce.** `git merge-base HEAD <ref>` names the commit a branch started from.
  `git archive` writes a tree but applies the repository's `.gitattributes` — `export-ignore` drops
  files and `export-subst` rewrites them — so its output can differ from the commit.
  `git ls-tree -r` and `git cat-file --batch` read the commit's blobs exactly.

## Decision

**A gate blocks on the findings a branch introduced. The validators run on the working tree and on
the merge-base tree, over the same scope, and a finding present at both is reported as pre-existing
and never blocks.**

### 1. The two trees

- The **merge-base** is `git merge-base HEAD <base>`, where `<base>` is the plan's base branch
  (`git.base_branch` in `.dgf-factory/config.yaml`), passed to `scripts/check_change.py --base`.
- The **base tree** is materialised blob by blob: `git ls-tree -r -z <merge-base> -- <root relative
  to the git top level>` lists it, and `git cat-file --batch` streams each blob into a temporary
  directory that is removed on exit. Symlinks (mode `120000`) and submodules (`160000`) are skipped
  and counted. Every written path must stay inside the temporary directory. Nothing in the working
  tree changes.
- **Not `git archive`**: its export attributes would make the base tree disagree with the commit.

### 2. The same runner, the same scope

- One runner, `scripts/lib/runner.py`, runs every validator over a root. It is the runner that was
  `tools/run_known_good.py`'s `run_validators`; that tool now imports it, so the known-good corpus
  and the gate cannot drift apart.
- By default the scope is the whole root (`/dgf-verify`). With `--files`, each listed file is routed
  to the same validators at both trees, wherever the file exists.
- `/dgf-implement` runs the check per task with `--files <the task's files>`. That is a fast
  pre-check and **never passes a gate**: the gate is `/dgf-verify`'s whole-root run (ADR 0004 §3).

### 3. The finding key

- A finding's key is `(code, root-relative file, normalised message)`. Normalising replaces the
  absolute root path, and its working-directory-relative form, with `<root>`.
- **The line number is not in the key.** Lines inserted above a pre-existing finding move it; they
  do not make it new.
- Keys are compared as **multisets**. A second copy of a key that exists at the merge-base is new.

### 4. What is reported

| finding | reported as | exit |
|---|---|---|
| in the working tree and not at the merge-base | its own code — **new** | its own |
| in both | `PRE_EXISTING`, the message carrying the original code | `0` (INFO) |
| at the merge-base and not in the working tree | `FIXED` | `0` (INFO) |

The summary reads `new: <e> error(s), <w> warning(s); pre-existing: <p>; fixed: <f>`.

### 5. When there is no baseline

With no git, no merge-base, or a failure reading the base tree, the report says
`NOT RUN: baseline (<reason>; every finding counts as new)`, and every finding is judged as new.
Without a baseline the gate is stricter, never looser.

## Alternatives considered

- **Validate only the changed files.** Rejected: it misses what the branch breaks elsewhere —
  a deleted workflow that an untouched process names — which is the reason ADR 0004 scopes the gate
  to the whole root.
- **Block on any finding in the root.** Rejected: every estate like DGF's samples fails on the first
  run, whatever the branch did. A gate that always fails is bypassed, and then it protects nothing.
- **A stored baseline file** — record today's findings once and compare against the file. Rejected:
  it goes stale as the base branch moves, it is one more artifact to own and merge, and it excuses
  whatever was true when it was written, which [ADR 0016](0016-legacy-xsd-lag.md) rejects for DGF's
  own form baseline.
- **Keys with line numbers.** Rejected: every edit above a pre-existing finding would make it new,
  so the gate would block on findings the branch did not cause.

## Consequences

### Positive

- A brownfield estate can pass the gate on its first branch, and a branch is judged on its own
  changes.
- A cross-file break — a reference the branch left dangling in a file it never touched — still
  blocks.
- Pre-existing findings stay visible, counted and listed, instead of disappearing into an
  exceptions file.
- A fix to a pre-existing finding is credited as `FIXED`.

### Negative

- **Two whole-root validator runs per verify.** The cost is measured on DGF's samples when the
  baseline is implemented; caching is a follow-up, not built in advance.
- **A pre-existing finding made worse without a new key passes.** An error whose message does not
  change — for example a second defect in a state that already fails — reads as pre-existing.
- **The gate depends on git.** Without it, every finding blocks.
- Two identical messages in one file count as one key each; a branch that fixes one copy and adds
  another elsewhere in the file reads as unchanged.

### Follow-ups

- Measure the two runs on DGF's samples when `check_change.py --base` lands, and add a caching
  follow-up if one verify run takes more than 60 seconds.
- Milestone 10's gate block adds `checks_run`, which will record `baseline` as run or not run.
