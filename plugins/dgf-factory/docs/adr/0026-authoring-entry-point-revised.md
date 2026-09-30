---
id: 0026
title: Brownfield-first, scoped to the whole workspaces root — and the scaffold generates a new application from an empty folder
status: accepted
date: 2026-09-29
deciders: [Andrian Mamei]
supersedes: [0004]
tags: [scope, planning, roadmap, scaffold]
---

# 0026 — Brownfield-first, scoped to the whole workspaces root — and the scaffold generates a new application from an empty folder

**Status: accepted** (2026-09-29, Andrian Mamei). The decider chose five points on 2026-09-29, while
`/dgf-scaffold` was planned (`.ai-factory/plans/feature-dgf-scaffold.md`): the plan is full; the branch is
stacked on `feature/dgf-specific-skills`; the command creates an application from scratch in an empty folder —
API hosts, Docker, the database, the workspaces, the documentation, authentication and the workspace artefacts
the request describes; the database is generated too, SSDT SQL included; and estate conventions stay out — the
content is DGF-generic. The rest was drawn from the evidence below and accepted with that plan. This ADR
restates [ADR 0004](0004-authoring-entry-point.md) in full with its section numbers, and reverses one section:
§2, "`/dgf-scaffold` drives a template; it does not emit files", no longer holds, because no template exists.

## Context

Read on **2026-09-21** (ADR 0004's interview and searches) and re-read on **2026-09-29** and **2026-09-30**
from this repository (`feature/dgf-scaffold`, stacked on `feature/dgf-specific-skills` at `616b666`) and from
DGF (`1d5999186`).

### The interview of 2026-09-21

ADR 0004 closed [blueprint](../blueprint.md) open question **#3** — *is "build a system from scratch" the
dominant case?* — by a structured interview:

1. **Greenfield versus brownfield:** *mostly brownfield.* Most work extends systems that already exist.
2. **How a new system is bootstrapped when one does start:** *from a template or generator* — never from
   nothing.
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

Three properties of that layout made the scope question consequential, and they are unchanged:

- **The base workspace is a real inheritance chain.** `WorkspaceSettings.FmPath` resolves inside the selected
  workspace; `FmBasePath` resolves inside `webasm`. An artifact under `webasm/FM/` is live in **every**
  application.
- **`BASE:X.Y` references cross the boundary by design** — `XmlCrossReferenceValidator` resolves them into the
  base workspace, so even a workspace-scoped validator must read outside its own unit.
- **`WorkspaceName` is a single configuration value.** A running application is exactly one workspace; "the
  whole solution" is a repository concept, not a runtime one.

### What ADR 0004 could not establish, and what is now established

ADR 0004 could not locate the template or generator in first-party DGF, and made identifying it a blocking
follow-up. [ADR 0023](0023-dgf-specific-skills.md) §7 repeated the search on 2026-09-27 and kept
`/dgf-scaffold` blocked. It was searched again on **2026-09-29**, and the answer is the same: **no bootstrap
template or generator exists.** There is no `.template.config` or `template.json`; no new-workspace, new-app or
new-tenant script; `spec-schema-examples/` holds only `.gitkeep`; and no DGF code turns a `settings.xml` into a
`CREATE TABLE`. `src/Core/DGF.Templates.OpenXml` is OpenXml *document* templating; `Dockerfile.workspace`
packages an existing workspace and creates none.

The five-application survey of 2026-09-29 (`.ai-factory/RESEARCH.md`) found why: ZamOffice, eCouncils, ZILAS,
ZMA and ZIMS are all clones of one repository's shape, and no generator produced them. Each copy carried the
source's defects with it:

- secrets in git in all five;
- environment URLs in base settings;
- a duplicated, broken `Web/Dockerfile`;
- one near-identical settings file per instance;
- one application (eCouncils) whose forked base drifted in 888 files.

So "drive a template" has nothing to drive, and "clone an existing application" copies exactly the defects the
survey lists.

### What a new application needs, from DGF

Read at DGF `1d5999186`, on 2026-09-29 and 2026-09-30. Each fact is recorded, stamped and ledgered in
`knowledge/` before any template uses it (Tasks 4 and 5 of the plan).

- **The minimum of a new app workspace** is `FM/_COMPONENTS/sitemap.json` with a landing route that is not
  `"/"`, listed first; an `_application.sitemap`, which the base does not supply; `FM/_COMPONENTS/Page/SiteMap/`;
  and a `_PROFILE/<name>/<roleGroup>/_tree.xml` per router component. The shell hard-codes `/login`, and reads
  its page's `authenticationMethods`.
- **The API does not start without an `aspnet_Applications` row** for the workspace: `WorkspaceProvider` finds
  it by `LoweredApplicationName`, and `Current` throws when none matches.
- **The database is an SDK-style `Microsoft.Build.Sql` baseline** with idempotent post-deployment scripts. The
  framework partitions its own rows by `ApplicationId`.
- **Authentication** is cookie always, DGPass OIDC and Azure AD OIDC when their `Authentication:<scheme>`
  section exists.
- **A front-office and a back-office tier are one host deployed twice**, with different settings; DGF has no
  back-office concept. Several instances over one workspace mount the same directory under each `WorkspaceName`.
- **The SQL type follows a field's `dbtype`**, derived from 86 exact-case pairs of `settings.xml` and table
  script across DGF's samples.

### What this plugin's validators do with a new workspace

Measured by a run over copies of `dgf`, with and without `webasm`, on 2026-09-30:

- every `sitemap.json` warns `NO_SCHEMA`, so its routes are never checked;
- `_application.sitemap`, `_tree.xml` and the profile node files are never collected, and naming one explicitly
  exits `3`;
- a `BASE:` reference with no base in the root is an ERROR, and `webasm` alone holds 36 `SCHEMA_INVALID` and 13
  `MODEL_CELL_UNBOUND`;
- `validate_process.py --all` with no process exits `3`.

A generated application therefore needs its own post-generation check for the files no validator reads, and
must not depend on a base being present.

### What stands from ADR 0010 and ADR 0017

[ADR 0010](0010-dgf-implement-scope.md) decides that `/dgf-implement` composes configuration — JSON first, XML
only without a JSON alternative, a little JavaScript or CSS only as a `kind: code` task — and writes no C# or
SQL. [ADR 0017](0017-plan-file-format.md) decides the plan file those skills execute. Neither concerns a folder
that has no root and no plan. This ADR reads ADR 0010 as **the scope of `/dgf-plan` and `/dgf-implement`**, not
of the plugin; [ADR 0027](0027-dgf-specific-skills-revised.md) §7 states that reading so that a reviewer can
reject it. If its closing sentence — "That work belongs to a general coding flow outside this plugin" — is read
as plugin-wide, ADR 0010 must be superseded too, and the scaffold waits for that.

## Decision

**dgf-factory is brownfield-first. A skill's unit of work is the whole workspaces root. `/dgf-scaffold`
creates a new DGF application from an empty folder — it generates the solution, the database, the workspaces,
the authentication configuration, the documentation and the workspace artefacts the request describes, from
templates this plugin ships. It never writes into a folder that is not empty, and it adds nothing to an
existing application: every change after the first is brownfield work for the pipeline.**

### 1. Brownfield is the default path, not a mode

Reconnaissance-first planning is the normal path through `/dgf-plan`: read the existing workspaces, locate the
artifacts a change touches, then plan against them. **Every change after the first is brownfield**: once
`/dgf-scaffold` has created an application and `/dgf` has set its root up, extending it is `/dgf-plan` and
`/dgf-implement`, and the scaffold is not offered for it. Greenfield is the exception and is handled by a
dedicated skill, not by a branch inside every skill.

**`/dgf-scaffold` does not move to phase 1.** The blueprint's conditional — *"If yes, `/dgf-scaffold` moves to
phase 1"* — still evaluates to no. It stays in milestone 12, after the pipeline spine, the knowledge base, the
validators and the DGF-specific skills.

### 2. `/dgf-scaffold` generates a new application itself; it drives no template

**No bootstrap template exists** (Context), so the skill does not drive one. It generates the application
itself, from templates shipped inside this plugin, and only into an empty folder:

- **Empty folder only.** The skill refuses a folder holding anything but `.git/` and `docs/application.json`.
  It reads and writes no `.dgf-factory/`, runs no override check and reads no patches, because in an empty
  folder there is no root and no plan.
- **The design is the generator's only input.** The model turns the request and the survey into
  `docs/application.json`; scripts check it and render from it. What a script can decide — names, references,
  the data model, SQL types, what is open, every default — is decided by the script, never by the model.
- **DGF-generic.** The templates carry no estate content: no payment, notification, identity-registry or
  signing integration of any one estate, no estate pipeline, no estate roles. An estate's base is supplied by
  pointing the survey's base source at it.
- **Secrets, hosts, feeds, registries and image tags are never literal.** Each is a placeholder resolved at
  run time. The survey's defects are the list of what is never copied.
- **The generator is a separate, template-only writer.** `/dgf-plan` and `/dgf-implement` still never plan or
  write C# or SQL ([ADR 0010](0010-dgf-implement-scope.md) §3); the scaffold's generator writes them only from
  shipped templates, and only into an empty folder.
- **A generated application is checked before it is reported.** A post-generation check reads the files no
  validator reads, and runs the validators over the generated files alone.
- **It then hands the new workspaces root to the pipeline**: `/dgf` sets it up, and every later change is
  brownfield.

### 3. The unit of work is the whole workspaces root

`/dgf-plan`, `/dgf-implement`, `/dgf-verify` and `/dgf-audit` treat the entire workspaces root as their scope —
every workspace, plus `webasm` and the `applibs*` libraries. **The scaffold's unit is the empty folder it
fills**, and it ends when the application is generated and checked.

- `.dgf-factory/` lives **once, at the workspaces root**, not per workspace.
- A change under `webasm/FM/` is verified against **every** consuming workspace, because they are all in scope.
- `BASE:X.Y` references always resolve, since the base workspace is never outside the unit.
- The blast-radius graph `/dgf-audit` computes spans applications, which is the only scope at which "what does
  this base artifact break" is answerable.

A narrowing filter (for example `--workspace zims`) is permitted **for iteration speed only**. A narrowed run
is explicitly **not sufficient to pass a gate**: the gate's authoritative scope is the whole root, and a
narrowed result must say so in `checks_run` rather than report a clean pass. See
[ADR 0014](0014-process-verification-runtime-resolution.md) and [ADR 0022](0022-gate-block-contract-revised.md).

## Alternatives considered

- **One workspace, base readable.** Recommended during the 2026-09-21 interview and **not chosen**. It matches
  `WorkspaceName` being a single runtime value and keeps context proportional to one application, but it
  cannot verify that a `webasm/FM/` edit is safe for the other applications that inherit it — it can only warn
  that one happened.
- **A single artifact.** Smallest and most composable. Rejected: every semantic check the process validators
  make needs siblings — a dead-transition check needs the other states, handler resolution needs the component
  registry — so a one-file unit would leave the gate at XSD-valid, which is not enough.
- **Greenfield-first with `/dgf-scaffold` in phase 1.** Rejected by the interview: it would front-load the
  roadmap with the rarer case and delay the brownfield reconnaissance path that most work actually needs.
- **Drive a template (ADR 0004 §2).** Rejected: none exists, after three searches on 2026-09-21, 2026-09-27 and
  2026-09-29. A skill blocked on a tool nobody has identified delivers nothing.
- **Clone an existing application and parameterise it.** Rejected: the five surveyed applications are the
  clones, and they copy secrets in git, environment URLs in base settings, a broken Dockerfile and a forked
  base. A clone is the research's "never copy" list.
- **An estate profile** (Zambian or any other). Declined by the decider on 2026-09-29: estate conventions
  belong to the estate, and a base is supplied by pointing the survey at it.
- **A scaffold that also adds to existing applications.** Rejected: adding is `/dgf-plan` and
  `/dgf-implement`, which read the root, plan against it and are held by the gate. A second writer for the same
  work would bypass both.
- **Supersede ADR 0010 as well.** Not needed on the reading above (§2 and Context). It is flagged, not
  assumed.

## Consequences

### Positive

- **Cross-application consistency becomes checkable at all.** A base-workspace change is verified against
  every consumer rather than merely flagged — the single strongest reason for the whole-root scope.
- **No boundary-crossing special cases.** `BASE:` resolution, shared `applibs*` libraries and the inheritance
  chain are all inside the unit, so no validator needs an "outside my scope" branch.
- **`/dgf-scaffold` is unblocked.** Milestone 12 can close, and a new application starts from a generated,
  checked shape with none of the surveyed defects.
- **`/dgf-audit` is worth building.** Its blast-radius graph only has meaning at this scope.

### Negative

- **Context cost scales with application count.** Every plan and every gate run pays for all workspaces. On a
  root with many applications this is the dominant cost of the pipeline, and it grows as the estate grows. This
  was named during the interview and accepted.
- **One plan ledger is shared across teams working on different applications.** At this scope, two teams
  touching two applications share `.dgf-factory/plans/`; [ADR 0009](0009-plan-ledger-scope.md) partitions it by
  affected workspace, and contention remains a real risk.
- **Gate runs are slower**, which pushes people toward the narrowing filter and therefore toward narrowed
  results that do not constitute a pass. The `checks_run` discipline is what keeps that honest, and it
  depends on being applied.
- **The templates can drift from DGF's samples** until the next `tools/check_drift.py` run.
- **The solution files pass no validator.** No validator reads C#, SQL, compose or MSBuild; they are checked
  only by the post-generation check and, where `dotnet` exists, one real build.
- **The application does not run until its placeholders are filled.** DGF pins no consumer image, feed or
  registry, so none can be defaulted.
- **The scaffold is a new writer of files the plugin never wrote before**: C#, SQL, compose and MSBuild. Its
  scope is the empty folder and nothing else; a reviewer who reads ADR 0010 as plugin-wide rejects §2.

### Follow-ups

- Adding to an existing application stays with `/dgf-plan` and `/dgf-implement`.
- Helm and pipelines: DGF ships no consumer pipeline, and the request names Docker.
- `BASE:` references in generated files, which a later version could allow once a base is in the root.
- `PrimaryKey` and `Checkboxlist` fields, once the vendored `settings.xsd` is re-vendored or an evidenced
  exception exists.
- The specification-driven `service` pattern (DGF's service spec v0.9 is provisional).
