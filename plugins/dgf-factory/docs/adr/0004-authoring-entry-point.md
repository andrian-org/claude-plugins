---
id: 0004
title: Brownfield-first, scoped to the whole workspaces root
status: accepted
date: 2026-09-21
deciders: [Andrian Mamei]
supersedes: []
tags: [scope, planning, roadmap]
---

# 0004 — Brownfield-first, scoped to the whole workspaces root

Closes [blueprint](../blueprint.md) open question **#3**: *is "build a system from scratch"
the dominant case? If yes, `/dgf-scaffold` moves to phase 1.*

## Context

This question is not answerable from any repository — it is a fact about how dotGov
delivers work. It was closed by a structured interview with the user on **2026-09-21**.

The answers:

1. **Greenfield versus brownfield:** *mostly brownfield.* Most work extends systems that
   already exist.
2. **How a new system is bootstrapped when one does start:** *from a template or generator* —
   never from nothing.
3. **The unit of work a skill should operate on:** *the whole workspaces root.*

Question 3 was asked against the real on-disk layout, read from
`src/Core/DGF.Kernel/WorkspaceSettings.cs` and `src/samples/workspaces/` on 2026-09-21:

```text
<DGF_WORKSPACES_ROOT_PATH>/
├── webasm/          ← BaseWorkspaceName: the shared base every workspace falls back to
│   └── FM/{_PROCESS,_WORKFLOW,_COMPONENTS,_DATA,_LOOKUP,_PROFILE,_DATACALLS,Templates}
├── zims/            ← one application
├── dgf/
└── applibs/  applibs-zims/  applibs-lm/  applibs-zma/  applibs-ecouncils/
```

Three properties of that layout made the scope question consequential:

- **The base workspace is a real inheritance chain.** `WorkspaceSettings.FmPath` resolves
  inside the selected workspace; `FmBasePath` resolves inside `webasm`. An artifact under
  `webasm/FM/` is live in **every** application.
- **`BASE:X.Y` references cross the boundary by design** — `XmlCrossReferenceValidator`
  resolves them into the base workspace, so even a workspace-scoped validator must read
  outside its own unit.
- **`WorkspaceName` is a single configuration value.** A running application is exactly one
  workspace; "the whole solution" is a repository concept, not a runtime one.

### What could not be established

**The template or generator could not be located in first-party DGF.** Searched on
2026-09-21: no `dotnet new` template config (`.template.config`) exists anywhere in the
repository, and `src/Core/DGF.Templates.OpenXml` is OpenXml *document* templating, unrelated
to project bootstrap. The bootstrap path the user described is therefore either an internal
artifact outside this repository or an existing solution used as a baseline. Identifying it
is a prerequisite for designing `/dgf-scaffold`, and is recorded as a follow-up rather than
guessed at.

## Decision

**dgf-factory is brownfield-first. A skill's unit of work is the whole workspaces root, and
`/dgf-scaffold` stays in roadmap milestone 12 — reshaped as a template driver rather than a
file emitter.**

### 1. Brownfield is the default path, not a mode

Reconnaissance-first planning is the normal path through `/dgf-plan`: read the existing
workspaces, locate the artifacts a change touches, then plan against them. Greenfield is the
exception and is handled by a dedicated skill, not by a branch inside every skill.

**`/dgf-scaffold` does not move to phase 1.** The blueprint's conditional — *"If yes,
`/dgf-scaffold` moves to phase 1"* — evaluates to no. It stays in milestone 12, after the
pipeline spine, the knowledge base, the validators and the DGF-specific skills.

### 2. `/dgf-scaffold` drives a template; it does not emit files

Because new systems always start from a template or generator, a scaffold skill that emits
its own directory tree would compete with that tool and drift from it. Its job is instead to
**run the existing bootstrap path and then make the result correct**: interview for the
inputs the template needs, invoke it, and verify the output against this plugin's validators.

### 3. The unit of work is the whole workspaces root

`/dgf-plan`, `/dgf-implement`, `/dgf-verify` and `/dgf-audit` treat the entire workspaces
root as their scope — every workspace, plus `webasm` and the `applibs*` libraries.

- `.dgf-factory/` lives **once, at the workspaces root**, not per workspace.
- A change under `webasm/FM/` is verified against **every** consuming workspace, because they
  are all in scope.
- `BASE:X.Y` references always resolve, since the base workspace is never outside the unit.
- The blast-radius graph `/dgf-audit` computes spans applications, which is the only scope at
  which "what does this base artifact break" is answerable.

A narrowing filter (for example `--workspace zims`) is permitted **for iteration speed only**.
A narrowed run is explicitly **not sufficient to pass a gate**: the gate's authoritative scope
is the whole root, and a narrowed result must say so in `checks_run` rather than report a
clean pass. See [ADR 0002](0002-process-verification.md) §1.

## Alternatives considered

- **One workspace, base readable.** Recommended during the interview and **not chosen**.
  It matches `WorkspaceName` being a single runtime value and keeps context proportional to
  one application, but it cannot verify that a `webasm/FM/` edit is safe for the other
  applications that inherit it — it can only warn that one happened.
- **A single artifact.** Smallest and most composable. Rejected: every semantic check ADR 0002
  commits to needs siblings — a dead-transition check needs the other states, handler
  resolution needs the component registry — so a one-file unit would leave the gate at
  XSD-valid, which ADR 0002 already ruled insufficient.
- **Greenfield-first with `/dgf-scaffold` in phase 1.** Rejected by the interview: it would
  front-load the roadmap with the rarer case and delay the brownfield reconnaissance path
  that most work actually needs.

## Consequences

### Positive

- **Cross-application consistency becomes checkable at all.** A base-workspace change is
  verified against every consumer rather than merely flagged — the single strongest reason
  for this scope.
- **No boundary-crossing special cases.** `BASE:` resolution, shared `applibs*` libraries and
  the inheritance chain are all inside the unit, so no validator needs an "outside my scope"
  branch.
- **The roadmap is settled.** Milestone 12 keeps `/dgf-scaffold`; nothing reorders.
- **`/dgf-audit` is worth building.** Its blast-radius graph only has meaning at this scope.

### Negative

- **Context cost scales with application count.** Every plan and every gate run pays for all
  workspaces. On a root with many applications this is the dominant cost of the pipeline, and
  it grows as the estate grows. This was named during the interview and accepted.
- **One plan ledger is shared across teams working on different applications.** Single-writer
  artifact ownership was designed for one project; at this scope, two teams touching two
  applications share `.dgf-factory/plans/`. Contention is a real risk, not a theoretical one.
- **Gate runs are slower**, which pushes people toward the narrowing filter and therefore
  toward narrowed results that do not constitute a pass. The `checks_run` discipline in
  ADR 0002 is what keeps that honest, and it depends on being applied.
- **The scaffold skill is blocked on an unidentified dependency.** It cannot be designed until
  the template or generator is located.

### Follow-ups

- **Identify the bootstrap template or generator** — which tool, where it lives, what inputs
  it takes. Blocking prerequisite for milestone 12; it is not in first-party DGF.
- Decide how `.dgf-factory/plans/` avoids cross-team contention at workspaces-root scope
  before the pipeline spine ships (milestone 9). Candidates: per-application plan id prefixes,
  or a plan-level `affects_workspaces` field. Not decided here.
- Specify the narrowing filter's interaction with `checks_run` when the gate contract is wired
  (milestone 10).
