---
id: 0009
title: One plan ledger at workspaces-root scope, partitioned by affected workspaces
status: accepted
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: []
tags: [planning, scope, ownership]
---

# 0009 — One plan ledger at workspaces-root scope, partitioned by affected workspaces

**Status: accepted** (2026-09-23, Andrian Mamei). This satisfies the precondition roadmap
milestone 9 ("Pipeline Spine") places on it: `/dgf-plan` writes the ledger this ADR is about.

## Context

[ADR 0004](0004-authoring-entry-point.md) made the whole workspaces root the unit of work and
put `.dgf-factory/` there **once**, not per workspace. Its Negative consequences name the cost:

> One plan ledger is shared across teams working on different applications. Single-writer
> artifact ownership was designed for one project; at this scope, two teams touching two
> applications share `.dgf-factory/plans/`. Contention is a real risk, not a theoretical one.

Its follow-up leaves open how the shared ledger is partitioned.

What the inherited pipeline provides, read from this repository on 2026-09-23:

- **Plan ids.** `.ai-factory/config.yaml` `workflow.plan_id_format` accepts `slug` (the default,
  derived from the branch name) and `sequential` (`<NNNN>_<stem>`). `timestamp` and `uuid` are
  reserved and behave like `slug`. `sequential` numbers from the highest existing prefix in the
  plans directory, so two branches cut from the same base allocate the **same** number. The
  files coexist after merge, because their stems differ, but the numbering stops being unique.
- **Discovery is branch-based.** `/aif-implement`, `/aif-improve` and `/aif-verify` find the
  active plan by converting the current branch name to a filename stem. One branch, one plan.
- **Single-writer ownership** (blueprint §"What stays") means `/dgf-plan` owns every plan file.
  It does not say which *team* owns one.

Two properties of DGF shape the answer (ADR 0004 §Context):

- A change under `webasm/FM/` is live in **every** application, so any plan touching the base
  workspace overlaps every other plan in principle.
- A running application is exactly one workspace (`WorkspaceName` is a single value), so most
  plans touch one application plus, sometimes, the base.

## Decision

**Keep one plan ledger at the workspaces root and scope each plan with a mandatory
`affects_workspaces` list.**

Every plan declares, in its header, the workspaces it touches:

```yaml
affects_workspaces: [zims, webasm]
```

- `/dgf-plan` writes the list from the reconnaissance it already does. It is never empty.
- **A plan may affect several workspaces at once.** This is intended. A change that spans
  applications, or that touches the base workspace together with the applications that rely
  on it, is one plan on one branch. It is not split into one plan per workspace.
- Plan ids stay `slug`, and discovery stays branch-based. Filenames carry no workspace.
  `sequential` ids are not permitted at workspaces-root scope, because two teams planning from
  the same base are certain to allocate the same number.
- A deterministic overlap check, run by `/dgf-plan` and `/dgf-verify`, lists every other active
  plan whose set intersects this one. `webasm` intersects every plan. An overlap exits `2`
  (warning), never `1`. It locks nothing: two teams may knowingly work in parallel, but never
  unknowingly. Git does not do this on its own. Plan files rarely conflict textually, so two
  overlapping plans would merge cleanly and nobody would learn that they overlapped.
- `/dgf-verify` compares the list with the files the branch actually changed, and fails with
  exit `1` when the diff reaches a workspace the plan did not declare. A plan may declare more
  than its diff touches, but not less.

## Consequences

### Positive

- The contention ADR 0004 named becomes visible at plan time, not at merge time.
- A change that spans workspaces is an ordinary plan, not a special case.
- Filenames and branch-based discovery stay exactly as inherited.
- Declared scope gives [ADR 0006](0006-process-verification-revised.md)'s whole-root checks, and
  [ADR 0005](0005-default-team-rules.md)'s rule 3 (base-workspace edits need justification),
  something to check against.

### Negative

- One more field for `/dgf-plan` to get right, and one more check to maintain.
- A multi-workspace plan is a larger unit of review and rollback. It overlaps more plans, so it
  raises more warnings.
- Overlap is only warned, so the contention risk is surfaced, not removed.
- Treating `webasm` as shared with everything will warn often on an estate where base edits are
  common.

### Follow-ups

- Milestone 9 defines the plan-header format with `affects_workspaces`, alongside
  [ADR 0010](0010-dgf-implement-scope.md)'s `kind` field.
- Still open: decide whether `affects_workspaces` includes the `applibs*` libraries or only
  application workspaces and `webasm`.
