---
id: 0028
title: Six shipped defaults for dotGov DGF systems, and sign-in chosen per estate
status: accepted
date: 2026-10-05
deciders: [Andrian Mamei]
supersedes: [0005]
tags: [rules, conventions, enforcement, auth]
---

# 0028 — Six shipped defaults for dotGov DGF systems, and sign-in chosen per estate

Restates [ADR 0005](0005-default-team-rules.md) in full, with its three errata folded in. One
thing changes: **rule 5 is no longer a default.** Sign-in is a choice `/dgf` asks for — any
number of the methods a host can read, or none — and nothing is assumed when the estate has
not said. Every other rule, and every enforcement tag, is unchanged.

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
because whole-root scope ([ADR 0026](0026-authoring-entry-point-revised.md)) made it newly
relevant.

**The user accepted all seven candidates and rejected none.** A candidate list where
everything is accepted has not been discriminating: the boundary between "ships as a default"
and "discovered per project" was not exercised by that interview. ADR 0005 named the first
project that contradicts a default as the test, and its demotion path as the response.

**The auth default has now failed that test, on two counts.**

1. **It is not a fact about DGF.** ADR 0005 took "JWT Bearer plus OIDC via Azure AD and DGPass"
   from the framework's `AGENTS.md` tech-stack line. The host's own code says otherwise
   (`knowledge/application-layout.md` §5, read at DGF `1.1.11` on 2026-09-30; sources in
   `provenance/knowledge/application-layout.md` §5: `AuthenticationExtensions.cs:49-286`,
   `AuthController.cs:26-143`). Cookie authentication is always on; DGPass OIDC is added only when
   `Authentication:DGPassOIDC` exists, Azure AD OIDC only when `Authentication:AzureOIDC` exists, and
   the local `basic` sign-in only when `Authentication:Basic:Enabled` is true. **No other inbound
   scheme is read from settings — there is no JWT bearer** (a grep of the source for `Jwt`,
   `ApiKey`, `Kerberos`, `Negotiate` and `AddGoogle`, recorded in the same ledger).
2. **Estates differ in which providers they enable, including none.** The `dgf` sample and the
   local stack use `basic` alone (`knowledge/application-layout.md` §5, the `auth-schemes`
   table). The Split Bill demo estate signs in with local basic only, with no OIDC block
   (`docs/demo/splitbill/appsettings.splitbill.json`, the `Authentication` section;
   `docs/demo/interview-guide.md`, where setup is answered "override auth with local basic
   sign-in"). An application that serves only
   anonymous pages configures no provider at all. A default of "Azure AD and DGPass" is the
   wrong answer for each of them, and offering it first invites the user to accept it.

The setup question that carried the default (`skills/dgf/SKILL.md` Step 3, Call 2, before
2026-10-05) offered "keep both defaults" as its first option, so a user who clicked through
recorded a sign-in stack the estate does not have.

The test-stack default (rule 6) has met no counter-example and stays.

## Decision

**Six rules ship as defaults. Each is tagged with how it is enforced, and the tag is part
of the rule — a rule with no enforcement path is a preference, and must be labelled as one.
Sign-in ships no default: `/dgf` asks which methods the estate uses.**

This ADR decides the **content** of the default rule set. It does **not** write `RULES.md`:
`paths.rules_file` is owned by `/dgf-rules`, and writing it here would breach single-writer
artifact ownership. Rule numbers are kept from ADR 0005 so citations of "rule 3" still mean
what they meant.

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
| 5 | **Sign-in: no default.** `/dgf` asks which of `basic`, `dgpass` and `azure` the estate uses — any number of them — or `none`, and records the answer in `DESCRIPTION.md`. Nothing is preselected or recommended. | prompt-only |
| 6 | **Test stack:** xUnit + FluentAssertions + Moq/NSubstitute (backend); Jest and Playwright (frontend). | prompt-only |
| 7 | **Workspace layout:** `FM/_PROCESS`, `_WORKFLOW`, `_COMPONENTS`, `_DATA`, `_LOOKUP`, `_PROFILE` and `Services`, plus `_STORAGE` at the workspace root — naming and casing. | **script** |

Rule 7 is scriptable because the directory names are framework constants in
`WorkspaceSettings.cs` — `Fm = "FM"`, `Process = "_PROCESS"`, `Workflow = "_WORKFLOW"`,
`Components = "_COMPONENTS"`, `Data = "_DATA"`, `Lookup = "_LOOKUP"`, `Profile = "_PROFILE"`,
`Services = "Services"` (joined under `FM/`, `WorkspaceSettings.cs:64`, used by
`src/Core/DGF.Domain/Workflow/RecordsServiceWorkflowManager.cs:12`), and
`StoragePath = "_STORAGE"` (joined under the workspace root, not `FM/` —
`WorkspaceSettings.cs:50`, used by `src/Core/DGF.OM/Providers/DbRowProvider.cs:166`) — not a
convention someone wrote down. Read at DGF commit `aa1d5c4c2` on 2026-09-23.

The script checks only constants the engine **uses**. `WorkspaceSettings.cs` also declares
`DataSources = "_DataSources"`, `SiteMaps = "_SiteMaps"` and `Endpoints = "_EndPoints"`, but
nothing under `src/Core` references them — endpoints load from `_COMPONENTS/Endpoints`
(`src/Core/DGF.DataSources/Endpoints/EndpointFactory.cs:26`) — so requiring those directories
would flag every real workspace. `_DATACALLS` exists on disk in `webasm/FM/` but is not a
framework constant at all.

**Rule 5 is a question, not a default.** The method names are the shell's login-method names
and the host's login endpoint challenges the scheme a method names
(`knowledge/application-layout.md` §5), so the answer maps one-to-one onto the settings
sections an application enables. `none` means no sign-in method; it cannot be combined with a
method. An answer the user types outside the three names is recorded verbatim — the estate's
answer wins, and the plugin does not claim to know every host.

**Rule 6 is a default, not an invariant.** `/dgf` setup may record a per-project override in
`DESCRIPTION.md`, and where it does, the project wins. Shipping it saves the common case from
re-derivation; it does not assert that no dotGov system differs.

### Rejected as project-specific

**Rule 5's former content** — "Auth: JWT Bearer plus OIDC via Azure AD and DGPass" — demoted
by the path ADR 0005 laid down, for the reasons in §Context.

## Alternatives considered

- **Ship nothing; discover everything per project.** Maximally safe against a wrong default.
  Rejected: it re-pays the same derivation cost on every project and makes the plugin's claim
  to "already know DGF" hollow for exactly the facts that are stable.
- **Ship the rules without enforcement tags.** Simpler to write. Rejected: an unenforceable
  rule stated alongside a scripted one reads as equally binding, and the corpus then cannot be
  audited for how much of it is actually checked.
- **Ship rule 6 as an invariant rather than an overridable default.** Rejected: it was not
  tested against a system that differs, and an invariant that turns out to be wrong is much
  harder to unwind than a default that a project overrides.
- **Keep an auth default, corrected to what DGF reads** — for example `basic`, the sample's
  choice. Rejected: the methods are independent switches an estate turns on, and the sample's
  choice is a local-stack convenience, not a statement about production estates. Any single
  default would be the first option a hurried user accepts, which is the failure §Context
  records.
- **Correct ADR 0005 with an erratum.** Rejected: removing the default changes what the ADR
  decides, which the ADR contract says is never an erratum.
- **Detect the sign-in methods from the estate's settings.** Rejected for setup: `/dgf` inventories
  workspaces, not hosts, so it has no host settings to read, and a host's `appsettings` files are
  per-environment, so what one file enables is not what the estate runs.

## Consequences

### Positive

- **No setup records a sign-in stack the estate does not have.** The question has no answer
  until the user gives one.
- **The recorded methods name real settings sections**, so a plan or a scaffold that reads
  `DESCRIPTION.md` can act on them without translating a prose stack line.
- **Setup stays cheaper and more consistent** for the six rules that remain defaults.
- **Four of six are mechanically enforceable** — rules 1 and 7 by script, rules 2 and 3 by
  gate.
- **Rule 3 closes a real hole opened by whole-root scope.** Base-workspace edits are both
  possible to detect and important to justify.

### Negative

- **Setup asks one more real question.** A user who wants to skip it cannot: there is no
  default to accept.
- **Rule 5 rests on the answer, not on evidence.** Nothing checks that the recorded methods
  match the hosts' settings; a wrong answer is recorded as faithfully as a right one.
- **Three rules are prompt-only** (rules 4, 5 and 6) — the same honest trade-off the blueprint
  records for the pipeline as a whole.
- **Rule 1 is a Wave-1 policy, not a permanent truth.** `format-coverage.md` describes it as
  current. When JSON parity broadens it becomes wrong, and being scripted makes it *more*
  disruptive to change, not less.
- **Rule 2's boundary needs judgement.** "Behaviour that belongs in a spec" is not a crisp
  line, and the gate will produce false positives on legitimate `js/` usage if that scoping is
  implemented carelessly.
- **The default/project-specific boundary is still largely untested.** One rule has been
  demoted; the others have met no counter-example yet, which is not the same as being right.

### Follow-ups

- **`/dgf-rules` writes `RULES.md`** from this decided set. This ADR is its input; it does not
  do the writing.
- **Demotion path:** when a project contradicts a shipped default, record the counter-example,
  demote the rule to project-discovered, and supersede this ADR rather than editing it.
- Re-run this question once three or more real projects have used the plugin — that is when
  the boundary can actually be drawn from evidence instead of from candidates.
- Tag rule 1 with a review date, per [ADR 0013](0013-version-gating-provenance-ledger.md)'s
  treatment of policy facts.
- When the knowledge base's sign-in facts are re-read at a newer DGF release, re-check that the
  three method names in rule 5 are still the whole set.
