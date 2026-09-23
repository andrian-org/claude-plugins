---
id: 0010
title: /dgf-implement composes configuration, modern JSON first, and writes JS or CSS only where configuration cannot
status: accepted
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: []
tags: [pipeline, implement, scope, schemas]
---

# 0010 — `/dgf-implement` composes configuration, modern JSON first, and writes JS or CSS only where configuration cannot

**Status: accepted** (2026-09-23, Andrian Mamei). It closes [blueprint](../blueprint.md) open
question **#4**. It also meets roadmap milestone 9's ("Pipeline Spine") precondition that this
ADR be accepted first, since milestone 9 writes `/dgf-implement`.

## Context

Blueprint question #4: *how much of a DGF system is code the agent writes versus configuration
it composes? If mostly configuration, "implement a task" means something quite different from
AI Factory's assumption, and `/dgf-implement` needs reshaping.*

Its 2026-09-19 answer said **mostly configuration**, and that today the configuration is XML
for the five legacy artifact types. It did not say what `/dgf-implement` then does, or which
configuration it prefers when more than one would do.

Evidence, read 2026-09-23. DGF paths are relative to the DGF repository root at `aa1d5c4c2`.

- **Configuration dominates the authored surface.** A workspace's behaviour lives under `FM/`
  (`_PROCESS`, `_WORKFLOW`, `_COMPONENTS`, `_DATA`, `_LOOKUP`, `_PROFILE`), per
  `src/Core/DGF.Kernel/WorkspaceSettings.cs`. The shipped samples under
  `src/samples/workspaces/` hold 318 `_workflow.xml` files under `FM/_WORKFLOW/`, 785
  `_form.xml` files, and 23 processes ([ADR 0006](0006-process-verification-revised.md)).
- **Modern components are JSON files under `FM/_COMPONENTS/`, and they already sit next to the
  XML.** The same samples hold 385 `.json` files under `FM/_COMPONENTS/` in `dgf`, `zims` and
  `webasm`. `src/Components/DGF.Components.Shared/ComponentFileLoadService.cs:14` fixes the
  extension to `.json`. Lines 20–25 resolve `<workspace>/FM/_COMPONENTS/<componentType>/<name>.json`,
  and a `BASE:` prefix resolves the same path in the base workspace `webasm`. Data sources and
  endpoints load the same way (`src/Core/DGF.DataSources/DataSourceLoader.cs:28-29`,
  `src/Core/DGF.DataSources/Endpoints/EndpointFactory.cs:26-32`).
- **Runtime parity is decided per component.** `docs/wiki/AI-Authoring/format-coverage.md` rows
  1–67 say whether the runtime parses JSON for each component: ✓ for most, ◐ (partial) for
  seven — Booking, CorporateAccount, EligibilityCriteria, Form, PayComponent, Query and Uploader
  — and ✗ for ProcessFlow (line 60) and Workflow (line 86). Line 103 says the five legacy
  artifact types (form, workflow, process, settings, view) *"have no JSON equivalent today. The
  runtime reads only XML."*
- **DGF states its AI policy in two scopes.** `format-coverage.md:15` says Wave-1 AI *"generates
  XML for everything"*. Line 138 limits it to *"all five legacy artifact types"*.
  [ADR 0005](0005-default-team-rules.md) rule 1 and [ADR 0011](0011-schema-parity-authority.md)
  (proposed) both use the line-138 scope.
- **The configuration is checkable.** [ADR 0006](0006-process-verification-revised.md) and
  [ADR 0007](0007-validator-runtime.md) give it a deterministic structural and semantic gate.
- **Code exists, and DGF is working to remove it.** The samples carry JavaScript in
  `webasm/js/`, `webasm/FM/js/` and `zims/js/`, CSS in `zims/css/`, and three per-form
  `_form.js` files under `FM/_DATA/<table>/_forms/<form>/`. `src/Core/DGF.Domain/Data/Form/FormManager.cs:183-188`
  loads a form's script from the `_form.js` beside it, or from a `scriptPath` under the
  workspace root. The UI shell injects `assets/js/formhelper.js`, `assets/js/formshared.js` and
  `assets/styles/custom.css` at start-up (`src/DGF.UI/src/app/components/app/app.component.ts:191-200`).
  61 of the 69 vendored JSON schemas carry a `CssClass` property (`knowledge/schemas/json/`).
  DGF's research folder `docs/Research/get-rid-of-js/` states the objective *"Replace all
  imperative JavaScript logic in eCouncil form files with declarative DGF configuration"*
  (`00-executive-summary.md:4`); its strategy is marked *"Proposed"*
  (`Form-JS-Elimination-Strategy.md:3`).
- **Other code is real too.** DGF loads C# plugins (`src/Plugins/UserTracker`;
  `src/Directory.Build.props:29` refers to "client plugin DLLs"), and the framework itself is
  .NET 10 and Angular 19.2.
- **ADR 0005 rule 2** already forbids behaviour that belongs in a declarative spec from being
  smuggled in as script. That is a boundary on code *inside* `FM/` artifacts, not a ban on code.
- **The decider's direction** (Andrian Mamei, 2026-09-23):
  - `/dgf-implement` is mostly configuration.
  - Modern JSON components under `*/FM/_COMPONENTS/` take priority.
  - XML is used only for components with no JSON alternative.
  - A little JavaScript and custom CSS is allowed only when configuration cannot implement the
    plan.
  - DGF will move every component to JSON, and XML will become obsolete.

  The last point is a direction, not a dated DGF commitment. `format-coverage.md` names the
  migration: Workflow is *"the largest remaining migration"* (line 86), ProcessFlow's *"JSON
  path [is] planned for Wave 2/3"* (line 60), and line 126 names the migration-progress KPI.
  It gives no date.

## Decision

**`/dgf-implement` composes configuration. It prefers modern JSON components under
`FM/_COMPONENTS/`, falls back to legacy XML only where no JSON alternative exists, and writes a
little JavaScript or CSS only where configuration cannot express the plan. It writes nothing
else.**

### 1. The order of means

For each task, `/dgf-implement` uses the first means that can express the change:

| # | Means | Where | Used when |
|---|---|---|---|
| 1 | Modern JSON component configuration | `<workspace>/FM/_COMPONENTS/<Type>/<name>.json` | The component's runtime-parity row says the runtime parses JSON: ✓ or ◐ |
| 2 | Legacy XML artifact | `FM/_PROCESS/`, `FM/_WORKFLOW/`, `FM/_DATA/<table>/` | The artifact is one of the five legacy types, or the component's row is ✗ |
| 3 | A little JavaScript or CSS (`kind: code`, §2) | the workspace's `js/` and `css/` locations, a form's `_form.js` | Neither 1 nor 2 can express the change, and the plan says why |
| — | Anything else | — | Out of scope (§3) |

- **The route is resolved per component, never defaulted.** It is read from the component's
  row in the shipped runtime-parity table (`knowledge/schema-families.md` §6), which is drawn
  from `format-coverage.md` and tracked against it by digest. A component with no row stops
  with exit `3`; `/dgf-implement` does not guess a family. An existing file's family is still
  resolved before it is parsed (ADR 0011, `.ai-factory/rules/base.md` §"DGF Schema Handling").
- **Where a modern component and a legacy artifact could both express the need, the modern
  component wins.**
- **The five legacy types stay XML, Form included.** Form's row 19 is ◐, but `format-coverage.md`
  lists `_form.xml` among the five legacy types (lines 103, 107), and ADR 0005 rule 1 still
  holds. A new form is `_form.xml` until rule 1 is superseded.
- **A ◐ component's configuration is JSON; the part its row names as XML-only is an XML
  artifact.** Uploader's large-file workflow, for example, is a `_workflow.xml`. The JSON still
  raises the exit-`2` parity warning that `.ai-factory/rules/base.md` §"DGF Schema Handling"
  sets for every ◐ row. That is intended: it tells the reviewer which part of the feature is
  still XML.
- **An existing artifact is edited in the family it is in.** The estate is brownfield
  ([ADR 0004](0004-authoring-entry-point.md)), and it already mixes the families: the samples
  hold six `_form.json` files beside the 785 `_form.xml` files. Moving an artifact from XML to
  JSON is a migration. It is its own plan task and is never a side effect of another change.

### 2. Code: a little JavaScript or CSS, only when configuration cannot

- **A task writes code only when the plan marks it `kind: code` with a `reason`.** The reason
  names the configuration route that was tried and why it cannot express the change. It cites
  the component doc, the schema, or the `EventBase` verb list
  (`knowledge/composition-specs.md` §3.1). "Quicker in JavaScript" is not a reason.
- **The code is JavaScript or CSS, and nothing else.** It goes where the workspace already keeps
  such files: `js/`, `css/`, or a form's `_form.js`. CSS reaches a component through its
  `CssClass` property.
- **"A little" means the smallest script or stylesheet that fills the named gap.** It must not
  re-implement behaviour that DataFetcher and the `EventBase` verbs can express (ADR 0005
  rule 2). `kind: code` gives rule 2's gate a declared reason to check against.
- **Verification.** The configuration the code serves still passes the ADR 0006 gate. The code
  itself is verified by the project's frontend tests where they exist (ADR 0005 rule 6). Where
  none exist, the gate reports that check as not run. It never reads as passed.

### 3. What `/dgf-implement` does not write

C#, TypeScript and Angular code, SQL, and framework or plugin source are out of scope.
`/dgf-plan` does not write a task that needs them. If `/dgf-implement` meets one, it stops that
task with exit `1` and reports what code the plan needs, without writing it. That work belongs
to a general coding flow outside this plugin.

### 4. Built for XML to shrink

- The route comes from the shipped parity table. When a `format-coverage.md` row changes to ✓
  and the table is re-vendored, `/dgf-implement` routes that component to JSON with no skill
  change.
- The list of legacy types is read from `knowledge/composition-specs.md` §2, which is drawn
  from `format-coverage.md` §"Legacy XML-only artifacts". It is not written into a prompt.
- Two decisions keep the five legacy types in XML: ADR 0005 rule 1 and ADR 0011's XML-always
  clause. When DGF ships a JSON path for one of those types, those decisions are superseded for
  that type. The order of means in §1 does not change.
- The plugin keeps reading and validating XML for as long as XML is on disk. XML can be
  obsolete for new authoring and still be in every brownfield estate.

## Alternatives considered

- **Configuration first with an open code exception** — the recommendation drafted before
  acceptance. Any code (a C# plugin, a `js/` file, an Angular change) was allowed under
  `kind: code`. On acceptance the decider limited code to a little JavaScript and CSS.
- **Code and configuration as equals.** Keep AI Factory's code-first loop and add configuration
  as one more file type. It is the smallest change from the reference pipeline. It was rejected
  because on an estate that is mostly configuration it makes code the easy path, and rule 2
  would only catch the result afterwards.
- **Configuration only, all code handed off.** It is the cleanest boundary. It was rejected for
  JavaScript and CSS, because small gaps are real (the samples carry both) and handing them to a
  second tool loses the plan's single ledger. §3 adopts it for all other code.
- **XML for everything,** the literal reading of `format-coverage.md:15`. It was rejected
  because the runtime reads `_COMPONENTS` only as `.json` (`ComponentFileLoadService.cs:14`), the
  samples already author components as JSON, and it would add new XML to an estate that is
  migrating away from it.
- **JSON for every artifact that has a JSON schema.** It was rejected because Workflow and
  ProcessFlow validate against schemas the runtime ignores (`format-coverage.md` lines 60 and 86).

## Consequences

### Positive

- The default path matches what a DGF system mostly is, and every default task lands under a
  deterministic gate.
- New work lands in the format DGF is migrating towards. The estate's XML shrinks instead of
  growing.
- Code is rare, small and visible. Every `kind: code` task carries a reason a reviewer can check.
- The route is driven by data, so DGF's migration moves the plugin without a skill change.

### Negative

- `kind: code` is a judgement the planner makes. A planner that marks too much as code
  reintroduces the rejected code-first design.
- "A little" has no number. It is judged at review, not checked by a script.
- A feature that needs a C# plugin hook or an Angular change is split across two tools, and the
  plan ledger holds only its configuration half. This is the cost of handing code off, and §3
  accepts it for everything except JavaScript and CSS.
- Form is pulled two ways. The runtime reads JSON forms (row 19), but rule 1 keeps new forms in
  XML. Until rule 1 is superseded, a new form is XML even where JSON would work.
- Every ◐ component's JSON raises an exit-`2` parity warning. Those warnings will be common, and
  common warnings get ignored.
- Code tasks get a weaker gate than configuration tasks: frontend tests, where they exist.
- DGF's own Wave-1 AI tooling is described as generating XML "for everything"
  (`format-coverage.md:15`). For component configuration this plugin does not. If DGF means
  line 15 literally, the two tools produce different output for the same request.

### Follow-ups

- Milestone 9 defines the plan-header format: `kind: config | code` and `reason` per task, next to
  [ADR 0009](0009-plan-ledger-scope.md)'s `affects_workspaces`.
- Write the §1 route as a script before it is written as a prompt: component type in, means out,
  read from the shipped parity table, with exit `3` for a component with no row. It lands with
  milestone 8's parity check or milestone 9, whichever comes first.
- Extend `knowledge/schema-families.md` §6 to every `format-coverage.md` row before that script
  is written. Today it lists only the ◐ and ✗ components, so a ✓ component has no row to read.
- Verify how a workspace's `js/` and `css/` files reach the UI's `assets/js/` and
  `assets/styles/` paths. The files read here do not show it, and `/dgf-implement` must know where
  a new file goes before it writes one.
- After the first real plans, decide whether a size budget for `kind: code` is worth scripting.
- When DGF gives one of the five legacy types a JSON path, supersede ADR 0005 rule 1, and
  ADR 0011's XML-always clause, for that type.

## Errata

Corrections of fact that do not change what this ADR decides. See
[the ADR contract](README.md) §"Errata".

- **2026-09-23** — §1 and §4 said `/dgf-implement` reads its route and the legacy-type list
  from `format-coverage.md`. That is a DGF repository file. Files a developer installs carry no
  DGF paths, and a developer's install has no DGF checkout to read. `/dgf-implement` reads the
  shipped copies instead: the runtime-parity table in `knowledge/schema-families.md` §6 and the
  legacy-type list in `knowledge/composition-specs.md` §2, both drawn from `format-coverage.md`.
  The order of means and the routing rule are unchanged. A follow-up is added because §6 does
  not yet list the ✓ components. Source: `skills/dgf-doctor/scripts/doctor.py:47`
  (`SHIPPED_DIRS`), and the decider's rule of 2026-09-23 that installed files carry no DGF paths.
