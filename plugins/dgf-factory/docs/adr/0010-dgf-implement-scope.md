---
id: 0010
title: /dgf-implement composes configuration first and routes code as a bounded exception
status: proposed
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: []
tags: [pipeline, implement, scope]
---

# 0010 — `/dgf-implement` composes configuration first and routes code as a bounded exception

**Status: proposed.** It would close [blueprint](../blueprint.md) open question **#4**, which
is marked only "substantially answered" there. It must be accepted **before roadmap
milestone 9 ("Pipeline Spine")**, because milestone 9 writes `/dgf-implement`.

## Context

Blueprint question #4: *how much of a DGF system is code the agent writes versus configuration
it composes? If mostly configuration, "implement a task" means something quite different from
AI Factory's assumption, and `/dgf-implement` needs reshaping.*

Its current answer, from 2026-09-19, says **mostly configuration**, and today that
configuration is XML for the five legacy artifact types. It does not say what `/dgf-implement`
then does, which is the part that shapes the skill. So the blueprint's header claim that all
seven questions are closed was not true for #4.

Evidence, read 2026-09-23:

- **Configuration dominates the authored surface.** A workspace's behaviour lives under `FM/`
  (`_PROCESS`, `_WORKFLOW`, `_COMPONENTS`, `_DATA`, `_LOOKUP`, `_PROFILE`), per
  `src/Core/DGF.Kernel/WorkspaceSettings.cs`. The shipped samples hold 23 processes and dozens of
  workflows under `src/samples/workspaces/*/FM/`.
- **The configuration has a generation policy.** DGF's
  `docs/wiki/AI-Authoring/format-coverage.md:138` sets Wave-1 policy: *"AI generates XML for all
  five legacy artifact types, regardless of partial JSON parity."*
- **The configuration is checkable.** [ADR 0006](0006-process-verification-revised.md) and
  [ADR 0007](0007-validator-runtime.md) give it a deterministic structural and semantic gate.
- **Code exists too, and is real.** Workspaces contain `js/` directories (`webasm/js`,
  `zims/js`, `dgf/js` — [ADR 0005](0005-default-team-rules.md) rule 2). DGF loads C# plugins
  (`src/Plugins/UserTracker`; `src/Directory.Build.props:29` refers to "client plugin DLLs"),
  and the framework itself is .NET 10 and Angular 19.2.
- **ADR 0005 rule 2** already forbids behaviour that belongs in a declarative spec from being
  smuggled in as script. That is a boundary on code *inside* `FM/` artifacts, not a ban on code.

## Options

### A. Configuration-composer, code as a bounded exception — recommended

`/dgf-implement` treats a task as a composition of `FM/` artifacts by default:

1. resolve the family;
2. read the existing artifacts;
3. compose the change as XML under the Wave-1 policy;
4. run the ADR 0006 gate after each task.

A task that genuinely needs code — a C# plugin, a `js/` file, an Angular change — is allowed
only when the plan marks it `kind: code` with the reason configuration cannot express it. The
skill then applies ordinary code practice, and the code task's verification is the project's
own test stack (ADR 0005 rule 6), not the DGF gate.

### B. Symmetric: code and configuration as equals

`/dgf-implement` keeps AI Factory's code-first loop and adds configuration as one more file
type.

- It is the smallest change from the reference pipeline.
- It loses the default that matters most on a configuration-dominant estate: code becomes the
  easy path, and rule 2 is left to catch the result after the fact.

### C. Configuration only; code handed off

`/dgf-implement` refuses code tasks and hands them to a general coding flow.

- It is the cleanest boundary.
- A single feature often needs both — a process change plus a small plugin hook — and splitting
  it across two tools loses the plan's single ledger.

## Decision

**Recommended, not yet accepted:** Option **A**. `/dgf-implement` is a configuration-composer
by default. It composes and validates `FM/` artifacts task by task against the
ADR 0006/0007 gate, and admits code only for plan tasks explicitly marked `kind: code` with a
stated reason, verified by the project's test stack rather than the DGF gate.

## Alternatives considered

Options B and C above.

## Consequences

### Positive

- The default path matches what a DGF system mostly is, and every default task lands under a
  deterministic gate.
- Code is visible in the plan as an exception with a reason, which makes rule 2 reviewable.

### Negative

- `kind: code` is a judgement the planner makes. A planner that marks too much as code
  reintroduces Option B by the back door.
- Code tasks get a weaker gate than configuration tasks: the project's tests, where they exist.

### Follow-ups

- **Accept, amend or reject before milestone 9.** On acceptance, update blueprint question #4's
  answer to link this ADR and remove its pending line.
- Define the `kind` field alongside [ADR 0009](0009-plan-ledger-scope.md)'s plan-header fields,
  so milestone 9 fixes the plan header once.
