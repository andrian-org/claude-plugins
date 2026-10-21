---
id: 0005
title: Seven shipped defaults for dotGov DGF systems
status: accepted
date: 2026-09-21
deciders: [Andrian Mamei]
supersedes: []
tags: [rules, conventions, enforcement]
---

# 0005 — Seven shipped defaults for dotGov DGF systems

Closes [blueprint](../blueprint.md) open question **#7**: *which dotGov-specific rules
should ship as defaults in `RULES.md` rather than being discovered per project?*

## Context

Not answerable from any repository — this is a question about what is true of *every*
dotGov DGF system rather than discovered per project. Closed by a structured interview with
the user on **2026-09-21**.

Candidates were seeded from first-party evidence so the question was answerable rather than
open-ended: the XML-always generation policy from `docs/wiki/AI-Authoring/format-coverage.md`,
the auth and test stack from the framework's `AGENTS.md`, the declarative-composition model,
and the workspace layout constants in `src/Core/DGF.Kernel/WorkspaceSettings.cs`. One further
candidate — base-workspace edits needing justification — was added during the interview
because [ADR 0004](0004-authoring-entry-point.md)'s workspaces-root scope made it newly
relevant.

**The user accepted all seven candidates and rejected none.**

That is worth stating plainly rather than reading as a strong result. A candidate list where
everything is accepted has not been discriminating: the boundary between "ships as a default"
and "discovered per project" was not exercised by this interview, so it remains untested. The
first real project that contradicts one of these is the test, and the demotion path in
§"Consequences" exists for exactly that.

## Decision

**Seven rules ship as defaults. Each is tagged with how it is enforced, and the tag is part
of the rule — a rule with no enforcement path is a preference, and must be labelled as one.**

This ADR decides the **content** of the default rule set. It does **not** write `RULES.md`:
`paths.rules_file` is owned by `/dgf-rules`, and writing it here would breach single-writer
artifact ownership.

### Authoring conventions

| # | rule | enforcement |
|---|---|---|
| 1 | **XML-always for the five legacy artifact types.** Generate XML for form, workflow, process, settings and view regardless of partial JSON schema parity. | **script** |
| 2 | **Declarative behaviour only.** Behaviour in `FM/` artifacts is composed through DataFetcher and `EventBase` verbs, not hand-written JavaScript. | **gate** |
| 3 | **Base-workspace edits need explicit justification.** A change under the base workspace (`webasm/`) is live in every application and must be named in the plan and verified against all consumers. | **gate** |
| 4 | **DGF-seam scope discipline.** Rules and review findings address DGF seams — components, specs, bindings, processes — not general C#, SQL or Angular style. | **prompt-only** |

Rule 1 is scriptable because `format-coverage.md` states the policy and the artifact types
are enumerable: a form, workflow, process, settings or view authored as JSON is a finding.

Rule 2 needs care to state correctly. **Workspaces legitimately contain JavaScript** —
`js/` directories exist in real workspaces (`webasm/js`, `zims/js`, `dgf/js`, read
2026-09-21). The rule is therefore **not** "no JavaScript in a workspace". It scopes to `FM/`
artifacts: behaviour that belongs in a declarative spec must not be smuggled into it as
inline script. A `js/` directory is out of scope of this rule.

Rule 3 is a gate rather than a script because it needs two inputs: the changed-file set *and*
the plan. Detecting the edit is trivial; deciding it was justified is not.

Rule 4 is prompt-only and is labelled so. It is the rule that keeps the corpus from drifting
into a generic style guide, and nothing can check it mechanically.

### Shipped stack facts

| # | fact | enforcement |
|---|---|---|
| 5 | **Auth:** JWT Bearer plus OIDC via Azure AD and DGPass. | prompt-only |
| 6 | **Test stack:** xUnit + FluentAssertions + Moq/NSubstitute (backend); Jest and Playwright (frontend). | prompt-only |
| 7 | **Workspace layout:** `FM/_PROCESS`, `_WORKFLOW`, `_COMPONENTS`, `_DATA`, `_LOOKUP`, `_PROFILE` and `Services`, plus `_STORAGE` at the workspace root — naming and casing. | **script** |

These ship so that skills stop re-deriving them at every setup. Rule 7 is scriptable because
the directory names are framework constants in `WorkspaceSettings.cs` — `Fm = "FM"`,
`Process = "_PROCESS"`, `Workflow = "_WORKFLOW"`, `Components = "_COMPONENTS"`,
`Data = "_DATA"`, `Lookup = "_LOOKUP"`, `Profile = "_PROFILE"`, `Services = "Services"`
(joined under `FM/`), and `StoragePath = "_STORAGE"` (joined under the workspace root, not
`FM/` — `WorkspaceSettings.cs` L50) — not a convention someone wrote down.

The script checks only constants the engine **uses**. `WorkspaceSettings.cs` also declares
`DataSources = "_DataSources"`, `SiteMaps = "_SiteMaps"` and `Endpoints = "_EndPoints"`, but
nothing under `src/Core` references them — endpoints load from `_COMPONENTS/Endpoints`
(`src/Core/DGF.DataSources/Endpoints/EndpointFactory.cs:26`) — so requiring those directories
would flag every real workspace. `_DATACALLS` exists on disk in `webasm/FM/` but is not a
framework constant at all.

Rules 5 and 6 are **defaults, not invariants.** `/dgf` setup may record a per-project override
in `DESCRIPTION.md`, and where it does, the project wins. Shipping them as defaults saves the
common case from re-derivation; it does not assert that no dotGov system differs.

### Rejected as project-specific

**None.** The rejection column is empty, and §"Context" says why that is a weak result rather
than a clean one.

## Alternatives considered

- **Ship nothing; discover everything per project.** Maximally safe against a wrong default.
  Rejected: it re-pays the same derivation cost on every project and makes the plugin's claim
  to "already know DGF" hollow for exactly the facts that are stable.
- **Ship the rules without enforcement tags.** Simpler to write. Rejected: an unenforceable
  rule stated alongside a scripted one reads as equally binding, and the corpus then cannot be
  audited for how much of it is actually checked. Tagging makes the prompt-only rules honest
  about what they are.
- **Ship rules 5 and 6 as invariants rather than overridable defaults.** Rejected: neither was
  tested against a system that differs, and an invariant that turns out to be wrong is much
  harder to unwind than a default that a project overrides.

## Consequences

### Positive

- **Setup gets cheaper and more consistent.** Seven facts that would otherwise be re-derived,
  or derived differently, per project.
- **Four of seven are mechanically enforceable** — rules 1 and 7 by script, rules 2 and 3 by
  gate — so the default set is not purely advisory.
- **Rule 3 closes a real hole opened by ADR 0004.** Whole-root scope makes base-workspace edits
  both possible to detect and important to justify.

### Negative

- **Nothing was rejected, so the default/project-specific boundary is untested.** The set may
  be over-inclusive, and that will only surface when a project contradicts one.
- **Three of seven rules are prompt-only** (rules 4, 5 and 6), which means close to half the
  default set rests on instruction-following rather than enforcement — the same honest
  trade-off the blueprint records for the pipeline as a whole.
- **Rule 1 is a Wave-1 policy, not a permanent truth.** `format-coverage.md` describes it as
  current. When JSON parity broadens it becomes wrong, and being scripted makes it *more*
  disruptive to change, not less.
- **Rule 2's boundary needs judgement.** "Behaviour that belongs in a spec" is not a crisp
  line, and the gate will produce false positives on legitimate `js/` usage if that scoping is
  implemented carelessly.

### Follow-ups

- **`/dgf-rules` writes `RULES.md`** from this decided set. This ADR is its input; it does not
  do the writing.
- **Demotion path:** when a project contradicts a shipped default, record the counter-example,
  demote the rule to project-discovered, and supersede this ADR rather than editing it.
- Re-run this question once three or more real projects have used the plugin — that is when
  the boundary can actually be drawn from evidence instead of from candidates.
- Tag rule 1 with a review date when the knowledge base lands, per [ADR 0003](0003-version-gating.md)
  §2's treatment of policy facts.

## Errata

Corrections of fact that do not change what this ADR decides. See
[the ADR contract](README.md) §"Errata".

- **2026-09-23** — §Consequences said "three of seven" rules were mechanically enforceable and
  "four of seven" were prompt-only. This ADR's own enforcement tables tag rules 1 and 7
  *script* and rules 2 and 3 *gate*, so it is **four** enforceable and **three** prompt-only
  (rules 4, 5 and 6). Both bullets are corrected in place. Source: the two tables in
  §Decision.
- **2026-09-23** — §Decision and §Follow-ups named `/aif-rules` as the owner of `RULES.md`.
  `aif-*` skills are build-time reference material that this plugin does not ship
  ([ADR 0001](0001-independent-plugin-with-ai-factory-derived-architecture.md) §2), so in a
  consumer's project the owner is **`/dgf-rules`**, which is what the blueprint's answer to
  question #7 already said. Source: `docs/blueprint.md` question #7; roadmap milestone
  "Quality & Authoring Skills".
- **2026-09-23** — Rule 7 omitted two directory constants the engine uses: `Services`, joined
  under `FM/` (`src/Core/DGF.Kernel/WorkspaceSettings.cs:64`, used by
  `src/Core/DGF.Domain/Workflow/RecordsServiceWorkflowManager.cs:12`), and `_STORAGE`, joined
  under the **workspace root** (`WorkspaceSettings.cs:50`, used by
  `src/Core/DGF.OM/Providers/DbRowProvider.cs:166`). Both are added. The three other declared
  constants — `_DataSources`, `_SiteMaps`, `_EndPoints` — are referenced nowhere under
  `src/Core` and are deliberately **not** added. Read at DGF commit `aa1d5c4c2` on 2026-09-23.
  The rule's decision — layout names and casing are framework constants, checked by script —
  is unchanged.
