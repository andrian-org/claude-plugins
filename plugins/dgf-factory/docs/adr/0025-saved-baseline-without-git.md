---
id: 0025
title: "Without git, a writing skill's confirm compares with a baseline check_change.py saved before the write"
status: accepted
date: 2026-09-28
deciders: [Andrian Mamei]
supersedes: []
tags: [gates, baseline, skills, no-git]
---

# 0025 — Without git, a writing skill's confirm compares with a baseline check_change.py saved before the write

**Status: accepted** (2026-09-28, Andrian Mamei). The decider chose, on 2026-09-28, to let a script tell
a writing skill's new findings from the root's old ones when the root has no git, over the two
alternatives put to them: keeping the comparison in the skills' prose, or narrowing the skills' check
to the file they wrote. The rest was drawn from the evidence below. This ADR decides how
`check_change.py` saves a run before a write and settles the run after it against that one, who may
pass the two flags, and what it refuses. It leaves [ADR 0018](0018-change-relative-gates.md) as it
stands: the gate's baseline is the merge-base tree, and without one every finding counts as new.

## Context

Read on **2026-09-28** from this repository (`feature/dgf-specific-skills` at `26edf71`).

- **The whole root after a write, without git, blamed the change for the root's old defects.**
  `/dgf-process` modify and `/dgf-model` add and modify confirm a write over the whole root, because a
  renamed state breaks the `CHANGE_STATE` steps of workflows the edit never touched
  ([ADR 0014](0014-process-verification-runtime-resolution.md) §2), and a removed field unbinds forms
  ([ADR 0023](0023-dgf-specific-skills.md) §1, §3). Without git, `check_change.py --changed` has no base
  tree, so it counts every finding as new (ADR 0018 §5). The seventh `/aif-verify` found both skills
  stopping on an untouched `webasm` entity's old unresolved `extract`: modify and add could not finish in
  any estate that holds an error, and DGF's samples hold 109
  (`.ai-factory/patches/2026-09-28-14.33.md`).
- **The first fix put the comparison in prose, and the prose could not carry it.** The skills took a
  baseline run before the write and told the model to treat a finding with the same code, file and
  message as pre-existing. `.ai-factory/rules/base.md:147` says "Anything a script can decide must never
  be left to the model", and this comparison is `lib/baseline.py`'s `compare()`. The eighth
  `/aif-verify` also found the exit wrong: the script still counted every finding as new, so one old
  malformed file anywhere in the root — `FAMILY_UNRESOLVED`, an exit-`3` code — made every run after
  the write exit `3`. The exit-`1` row that stops on a new cross-file break was then never reached.
- **The comparison already exists.** `baseline.compare(head, base, head_root, base_root)` keys a
  finding as `(code, root-relative file, normalised message)` without its line, compares keys as
  multisets, and passes INFO through (ADR 0018 §3–§4). `check_change.settle()` turns its result into
  `PRE_EXISTING` and `FIXED` lines and keeps a new finding's code and exit. A saved run's findings,
  keyed with their root already removed, can be handed to it with no root left to remove.
- **ADR 0018 decides the gate's baseline, and a saved run is never the gate's.** Its §1 names the
  merge-base tree, and its §5 says what a gate does without one. `verify_gate.py` calls
  `check_change.run()` with a merge-base; it has no write to take a baseline before. A writing skill's
  confirm is not a gate: `/dgf-verify` still judges the change afterwards, on the merge-base or, without
  git, with every finding new.

## Decision

**Without git, a writing skill that confirms over the whole root saves the run before its write with
`check_change.py --save-baseline`, and settles the run after it with `--baseline`, exactly as the gate
settles a run against the merge-base tree. The gate passes neither flag.**

### 1. The two flags

- `--save-baseline FILE` and `--baseline FILE` take a `--changed` set, and exclude each other.
- With `--base` either one is exit `3`: there the baseline is the merge-base tree (ADR 0018). With
  `--skip-validators` either one is exit `3`: a baseline is the validators' findings.

### 2. The saving run judges no validator finding

- The validators run as usual. Every finding but INFO is written to `FILE`, keyed as
  `baseline.key()` keys it, with its line. So are the resolved root and the `--files` scope.
- None of them is reported, so the run's exit is the change checks' alone. An old defect cannot stop
  a write before it starts.
- The report prints `BASELINE: saved <n> finding(s) — <e> error(s), <w> warning(s) — to <FILE>`, and
  `NOT RUN: baseline` saying that this run is one.

### 3. The comparing run settles as the gate does

- The saved findings are the base of `baseline.compare()`.
  - A finding at both is `PRE_EXISTING`, and one only in the saved run is `FIXED`; both are INFO.
  - A new finding keeps its code and its exit.
  - `baseline` is under `CHECKS RUN`.
- The key is ADR 0018 §3's. A message that the write itself changed reads as new, as it would at the
  gate: a `webasm` reference's list of applications, or a template reason that quotes a renamed key.

### 4. A baseline that cannot stand is refused

`BASELINE_UNUSABLE` (exit `3`), and no validator runs, when the file:

- is missing, is not JSON, or is not in this format;
- was saved for another workspaces root, or over another `--files` scope;
- holds a finding whose code no validator writes.

A refused baseline never falls back to "every finding counts as new": the caller asked for a
comparison and gets none, and says so.

### 5. Where the file lives

The skills write it to `<root>/.dgf-factory/baseline.json`, the pipeline's own directory:

- the change checks ignore it (ADR 0017 §6);
- the validators' walk never reads it.

Each save overwrites it.

### 6. Who passes the flags

- `/dgf-process` passes them for an author and a modify, and `/dgf-model` for an add and a modify: the
  writes they confirm over the whole root.
- `/dgf-component`'s scaffold confirms the new file alone (`--files`) and needs no baseline.
- `/dgf-verify` and `verify_gate.py` pass neither. A test holds `verify_gate.py` to that.

## Alternatives considered

- **The comparison in the skills' prose.** Rejected by the decider: `rules/base.md:147`, and the
  eighth `/aif-verify` showed the prose cannot fix the script's exit. An old exit-`3` file still masked
  a new break.
- **Narrow the confirm to the written file without git**, as `/dgf-fix` and `/dgf-implement` do.
  Rejected by the decider: it loses ADR 0014 §2's catch in the skill, leaving a renamed state's broken
  `CHANGE_STATE` steps to the gate.
- **Copy the root before the write, and compare two trees.** Rejected: a skill pre-approves no copy,
  and an estate's root is large. The saved findings are the part of a copy the comparison needs.
- **Supersede ADR 0018.** Rejected: what the gate decides is unchanged. A saved run is never the gate's
  baseline, and §5 still holds for every run that is given none.

## Consequences

### Positive

- Without git, a writing skill tells its change's findings from the root's old ones, by the script,
  with the exit computed from the new ones. An old malformed file no longer masks a new break.
- The two skills' confirm rows are the same with git and without it: the script has already done the
  comparison.

### Negative

- **A write without git runs the whole-root validators twice.**
- **A file is left in `.dgf-factory/`.** It is overwritten by the next save, and no check reads it.
- **Nothing proves when the baseline was saved.** A caller that saves after its write compares a tree
  with itself. The skills order the two calls; the script cannot see the order.
- **The key's sensitivity to message text is inherited.** A finding whose message the write changed
  reads as new, here as at the gate.

### Follow-ups

- `/dgf-implement`'s task with `deletes` runs the whole root without git and no baseline
  (`skills/dgf-implement/SKILL.md` Step 3.4). It could save one before the task's first write, as the
  roadmap's follow-up records.
