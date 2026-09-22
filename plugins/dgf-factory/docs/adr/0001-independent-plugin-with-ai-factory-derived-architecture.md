---
id: 0001
title: Independent plugin with AI Factory-derived architecture
status: accepted
date: 2026-09-21
deciders: [Andrian Mamei]
supersedes: []
tags: [delivery, architecture, provenance]
---

# 0001 — Independent plugin with AI Factory-derived architecture

## Context

This ADR records a decision the user made on **2026-09-21**. It does not reason toward
that decision, and it does not reopen it.

Before that date, this plugin's `.ai-factory/DESCRIPTION.md` carried an "accepted risk"
section instructing a future reader to reconcile this work with a separate DGF
agent-tooling effort, or to record why the divergence was intentional. That instruction
left the delivery model formally undecided: every later milestone had to be read as
provisional, because a reconciliation could have changed the packaging, the skill corpus,
and the knowledge layout all at once.

The user closed it directly:

> Ignore completely [that effort], it is not something that we must follow, not at all. We
> will start a completely new implementation with architecture that we bring from
> ai-factory.

The overlap between the two efforts was measured on 2026-09-21 before this was recorded.
This paragraph exists so a later reader knows the overlap was **assessed and set aside**,
not overlooked.

## Decision

**`dgf-factory` ships as an independent Claude Code plugin in the `dotgov` marketplace,
and its pipeline architecture derives from AI Factory 2.18.1.**

Two halves, both explicit.

### 1. Independent delivery

`dgf-factory` is delivered through `.claude-plugin/plugin.json` plus an entry in
`../../.claude-plugin/marketplace.json`, alongside `doc-coverage-audit`. It takes **no
dependency** on any other DGF agent-tooling effort: no shared artifacts, no shared skill
corpus, no obligation to track another repository's ADR series, and no requirement that
another tool be installed for this one to work.

Other repositories' ADRs are not constraints on this plugin. Where their reasoning is
useful it may be read, but it is not binding and is not cited as authority.

### 2. AI Factory-derived architecture

The pipeline architecture is carried over from AI Factory 2.18.1. Named explicitly, from
[`docs/blueprint.md`](../blueprint.md) §"What stays: all five core ideas":

1. **Single-writer artifact ownership** — every artifact has exactly one owning command;
   everything else treats it as read-only input.
2. **Planner/executor split** — `index.md` + phase-file bundles, with checkboxes living
   only in `index.md`, and an executor forbidden from re-deciding architecture.
3. **Machine-readable gate blocks** — a final fenced `dgf-gate-result` block with
   `schema_version: 1` and last-block-wins parsing.
4. **Worktree-isolated parallel workers** under a coordinator.
5. **The learning loop** — fix → patch → evolve → skill-context override.

Plus config-as-relocation, warmup/resume, the archive lifecycle and the grounded gate.

**This is a derivation, not a dependency.** The `aif-*` corpus under `.claude/` is
installer-managed reference material used to *build* this plugin; it is not shipped with
it. The plugin ships its own `dgf-*` skills, and nothing at runtime requires AI Factory to
be installed for `dgf-factory` to work.

## Alternatives considered

The delivery model was decided by the user rather than selected from options, so this
section records what was on the table when the question was still open, not a comparison
run for this ADR.

- **Ship as an extension of a generic agent-factory pipeline.** Keeps `injections[]` —
  extending generic skills without forking them — and avoids duplicating pipeline
  mechanics. Rejected by the user's direction: it makes this plugin's roadmap depend on
  another effort's release cadence and architectural choices.
- **Vendor an existing DGF skill corpus and adapt it.** Fastest start. Rejected for the
  same reason, plus it would import decisions whose evidence this repository does not hold
  and cannot re-verify.

## Consequences

### Positive

- **The delivery path is unblocked.** `.claude-plugin/plugin.json` plus a marketplace entry
  is now a settled route, which unblocks roadmap milestones 6 ("Plugin Manifest & Walking
  Skeleton") and 15 ("Marketplace Release").
- **Every later milestone is now definite rather than provisional.** No milestone needs a
  "pending reconciliation" caveat.
- **Evidence is self-contained.** Every fact this plugin relies on is sourced from
  first-party DGF — the engine under `src/Core`, the MCP server under `src/Tools/dgf-mcp`,
  the shipped schemas, and `docs/wiki/`. Nothing depends on another tool's interpretation
  of those sources.

### Negative

- **Pipeline mechanics are duplicated, not shared.** The step structure, gate discipline and
  ledger mechanics are re-expressed here. A fix to AI Factory's pipeline does not propagate
  to this plugin; it has to be ported deliberately, or not at all.
- **No `injections` mechanism.** Extending a generic skill means writing this plugin's own
  skill, not layering onto someone else's. That is more work per skill and more surface to
  keep correct.
- **The knowledge base and validators are built, not vendored.** Roadmap milestones 7
  ("DGF Knowledge Base") and 8 ("Deterministic Validators") stand as written, with their
  full cost. Nothing is inherited.
- **Duplicated effort across the organisation is real and accepted.** Another effort covers
  overlapping ground. This decision does not claim that is efficient — it claims the
  independence is worth it.

### Follow-ups

- Register the plugin in `../../.claude-plugin/marketplace.json` (milestone 15).
- **What would reverse this:** a named requirement that `dgf-factory` and another dotGov
  agent-tooling effort share a single skill corpus or a single install path — for example a
  decision that the organisation ships exactly one DGF agent toolchain. Absent that named
  trigger, this ADR is not reopened.
