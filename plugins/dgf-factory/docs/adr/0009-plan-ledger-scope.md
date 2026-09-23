---
id: 0009
title: One plan ledger at workspaces-root scope, partitioned by affected workspaces
status: proposed
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: []
tags: [planning, scope, ownership]
---

# 0009 — One plan ledger at workspaces-root scope, partitioned by affected workspaces

**Status: proposed.** This ADR sets out the options and a recommendation. It decides nothing
until it is accepted, which must happen **before roadmap milestone 9 ("Pipeline Spine")**,
because `/dgf-plan` writes the ledger this ADR is about.

## Context

[ADR 0004](0004-authoring-entry-point.md) made the whole workspaces root the unit of work and
put `.dgf-factory/` there **once**, not per workspace. Its Negative consequences name the cost:

> One plan ledger is shared across teams working on different applications. Single-writer
> artifact ownership was designed for one project; at this scope, two teams touching two
> applications share `.dgf-factory/plans/`. Contention is a real risk, not a theoretical one.

Its follow-up leaves the question open: *"Candidates: per-application plan id prefixes, or a
plan-level `affects_workspaces` field. Not decided here."*

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

## Options

### A. Per-application plan-id prefix

`plans/zims-<slug>.md`, `plans/webasm-<slug>.md`. It sorts and filters by application and needs
no new field.

- It breaks branch-based discovery unless branch names carry the same prefix.
- It encodes one application per plan, which is false for exactly the plans that matter: a
  base-workspace change affects every application.

### B. Plan-level `affects_workspaces` field plus an overlap check — recommended

Every plan declares, in its header, the workspaces it touches:

```yaml
affects_workspaces: [zims, webasm]
```

`/dgf-plan` writes it from the reconnaissance it already does. A deterministic check, run by
`/dgf-plan` and `/dgf-verify`, lists every **other** active plan whose set intersects this one.
A plan touching `webasm` is treated as intersecting every plan. Overlap is a **warning**
(exit `2`), not a lock: two teams may knowingly work in parallel, but never unknowingly.

- Filenames and branch-based discovery stay unchanged.
- It gives [ADR 0006](0006-process-verification-revised.md)'s whole-root checks, and
  [ADR 0005](0005-default-team-rules.md)'s rule 3 (base-workspace edits need justification), a
  declared scope to check against.
- The field can be wrong. `/dgf-verify` compares it with the files the branch actually changed
  and fails when the diff reaches a workspace the plan did not declare.

### C. A ledger per workspace under one root

`.dgf-factory/plans/<workspace>/…`. It gives the strongest isolation.

- It reintroduces the boundary ADR 0004 removed: a plan touching `zims` and `webasm` has no
  single home.
- Branch-based discovery must search every subdirectory.

## Decision

**Recommended, not yet accepted:** Option **B**. Keep one ledger at the workspaces root, keep
slug ids and branch-based discovery, and add a mandatory `affects_workspaces` list to every
plan. A deterministic overlap check warns when active plans share a workspace, treating
`webasm` as shared with all. `/dgf-verify` blocks when the branch's diff reaches a workspace
the plan did not declare.

Reject `sequential` ids at workspaces-root scope. Duplicate numbers are certain whenever two
teams plan from the same base.

## Alternatives considered

Options A and C above. A third — **do nothing and rely on git conflicts** — is rejected in
advance: plan files rarely conflict textually, so two overlapping plans would merge cleanly
and nobody would learn that they overlapped.

## Consequences

### Positive

- The contention ADR 0004 named becomes visible at plan time, not at merge time.
- Declared scope gives rule 3 and the whole-root gates something to check against.

### Negative

- One more field for `/dgf-plan` to get right, and one more check to maintain.
- Overlap is only warned, so the contention risk is surfaced, not removed.
- Treating `webasm` as shared with everything will warn often on an estate where base edits are
  common.

### Follow-ups

- **Accept, amend or reject this ADR before milestone 9 starts.** Until then, milestone 9 must
  not fix a plan-header format.
- Decide whether `affects_workspaces` includes the `applibs*` libraries or only application
  workspaces and `webasm`.
