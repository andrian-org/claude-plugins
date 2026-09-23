---
id: 0002
title: Process verification is structural today, semantic by our own validators
status: superseded-by-0006
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: []
tags: [validation, process, gates]
---

# 0002 — Process verification is structural today, semantic by our own validators

Closes [blueprint](../blueprint.md) open question **#5**: *what does verification look like
for a process? Is there a way to execute a process definition headlessly?*

## Context

Read from the DotGov Framework repository on **2026-09-21**, and re-verified the same day
before this ADR was accepted. The answer is asymmetric in a way the blueprint did not
anticipate: **structure is deterministic and headless today; semantics are checkable by
nothing DGF ships.**

### Structure is already solved, and needs no engine build

- `src/Tools/dgf-mcp/Tools/ValidateXmlTool.cs` L36-44 — `ValidateProcessXml` and
  `ValidateWorkflowXml` each call `validator.Validate(xml, "<artifact>.xsd")` and nothing
  else.
- `src/Tools/dgf-mcp/Services/XsdValidationService.cs` is the whole engine: an
  `XmlReaderSettings` with `ValidationType.Schema` plus a cached `XmlSchemaSet`. There is
  **no semantic pass of any kind**.
- `src/Tools/dgf-mcp/DgfMcpServer.csproj` contains **zero `<ProjectReference>`** — its XSDs,
  JSON schemas and wiki pages are committed assets. The MCP server builds and runs
  standalone; no part of the DGF engine has to compile for XSD validation to happen.

### Semantics are not solved, and the gap is provable rather than merely observed

`process.xsd` declares the two halves of a state graph:

- `StateType` (L44-53) — `State` with a required `@name`, nested under `States`.
- `TransitionType` (L137-143) — `Transition` with a required `@state`, the name of the state
  being transitioned to, nested under `State/Transitions` and under `OnStart/Transitions`.

So "a transition points at a state" is structurally part of the model. But the file contains
**no `xs:key`, `xs:keyref` or `xs:unique`** — zero occurrences, counted 2026-09-21. XSD
therefore cannot verify that a `Transition/@state` names a declared `State/@name`.

Nothing else covers it either:

- `src/Tools/dgf-mcp/Services/XmlCrossReferenceValidator.cs:94` rejects process outright —
  `"Unsupported artifactType: … Supported: form, settings, workflow."` Its workflow coverage
  is `BASE:X.Y` reference resolution only: no reachability, no handler existence, no
  state-graph analysis.
- `src/Core/DGF.Explorer/Services/DiagnosticCheckService.cs` has `ValidateWorkflow` and
  `ValidateHandler`, but its process entry point `ValidateProcessWfAndFrm` (L514) has its
  process path commented out, and its only dispatch site is commented too — L680:
  `/*case "PROCESS": ValidateProcessWfAndFrm(controlName); break;*/`. It requires
  `IDataAccessLayer`, and its only reference anywhere in the repository is its DI
  registration.

Together that is a closed proof: **a transition to a nonexistent state is unreported by
everything DGF ships.** It is dead at run time and silent at authoring time.

### Execution is not headless

`src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs` can deserialize a
`process.xml` with only `WorkspaceSettings` and `IFileSerializationService`. But *stepping*
a process runs through `src/Core/DGF.OM/Process/StateProcess/InstanceHandler.cs`
`GetProcessMapAsync`, which needs a case record and therefore the database. The de-facto
"does it run" check is the browser, via the Playwright suite under
`tests/src/specs/solutions/`.

### Negative results, recorded so they are not re-searched

- **No test project for the MCP server.** No `*.csproj` in the repository references
  `DgfMcpServer`.
- **No process regression corpus.** No fixture directory of known-bad process files exists.
- **No process support in the cross-reference validator**, per `XmlCrossReferenceValidator.cs:94`
  above.

## Decision

**A process is "verified" when it is XSD-valid *and* passes the semantic checks this plugin
implements itself. XSD-valid alone is necessary, never sufficient, and a gate may never
imply semantic validity it did not check.**

### 1. XSD-valid is necessary, not sufficient

A structural failure is always `blocking: true` — a process that does not match its grammar
cannot be reasoned about further, so semantic checks are skipped rather than run on a
malformed tree.

A structural pass alone does **not** produce `status: "pass"`. It produces a pass only for
the checks that actually ran. To make that honest rather than a matter of prose, the
`dgf-gate-result` block carries an additive optional field:

```json
"checks_run": ["xsd-structure", "dead-transition", "unreachable-state"]
```

Consumers that do not know the field ignore it, so `schema_version` stays `1` and
last-block-wins parsing is unchanged. A gate that omits a check must not be readable as
having passed it. This is implemented under roadmap milestone 10 ("Gate Contract Wired").

### 2. The semantic checks this plugin commits to

All operate on an existing `process.xml` without a database and without the engine.

| check | rule | status |
|---|---|---|
| **dead transition** | every `States/State/Transitions/Transition/@state` and `OnStart/Transitions/Transition/@state` resolves to some `States/State/@name` | **first target** — proven uncovered |
| **unreachable state** | every `States/State/@name` is reachable by a graph walk from the `OnStart/Transitions` entry set | committed |
| **handler resolution** | every `@action` on `OnStart`, `State` and `Transition` resolves to a real handler | committed, after component resolution lands (milestone 8) |
| **process `BASE:` references** | `BASE:X.Y` references in a process resolve into the base workspace | committed — the shipped validator excludes process, and ADR 0004's workspaces-root scope makes the base workspace readable |

The dead-transition check is first not by precedent but because the gap is proven: the
grammar demonstrably cannot express it and no shipped validator covers it.

### 3. Validation runs against vendored XSDs, in-process

Verification loads XSDs vendored into this plugin under `knowledge/schemas/xsd/` and
validates in-process. It does **not** require a locally booted MCP server.

The reason is operational, not ideological: **a gate that needs a network service or a
running server is not a gate you can rely on in CI or offline.** The hosted MCP at
`https://dgf-mcp.dotgov.uk/mcp` (declared in `.mcp.json`) stays useful for documentation
lookup and as a cross-check, but it is never the gate's dependency.

That choice creates a **re-vendor obligation**, which is discharged by ADR 0003: the
vendored set carries a `MANIFEST.md` recording the DGF commit SHA, version and date, plus a
per-file digest so drift against upstream is detectable rather than silent.

### 4. Nothing replaces execution in the gate — and the gate says so

A process cannot be executed headlessly, so **this plugin's gates make no claim about
runtime behaviour.** The gate's claim is bounded and stated: *this process matches its
grammar and is free of the semantic defects listed in `checks_run`.*

Browser-driven verification stays **out of the gate**. Declaring browser MCP servers costs
roughly 12,000 tokens of tool schema per session, which `.ai-factory/DESCRIPTION.md` records
as the basis for excluding them from this project. Execution-level confidence remains the
job of the DGF repository's own Playwright suite under `tests/src/specs/solutions/`, run by
CI and by humans — not by this plugin.

## Alternatives considered

- **Treat XSD-valid as sufficient.** Cheapest, and it ships today with no new code.
  Rejected: it would let the single proven defect class — a transition to a nonexistent
  state — pass a gate labelled "verified". That is worse than no gate, because it is a gate
  that lies.
- **Boot the MCP server locally and validate over HTTP.** Attractive because
  `DgfMcpServer.csproj` has no project references, so it genuinely builds standalone.
  Rejected: it makes every gate run depend on a .NET build and a live process, and the MCP
  performs only XSD validation anyway — so the dependency buys nothing the vendored path
  does not already give.
- **Add `xs:keyref` to `process.xsd` upstream.** The correct long-term fix, and it would make
  the dead-transition check free for every DGF consumer. Not chosen as *this* plugin's
  mechanism because it is an upstream change on an upstream schedule, and this plugin cannot
  block on it. Recorded as a follow-up.
- **Drive the Playwright suite from a gate.** Would give real execution confidence. Rejected
  on the token-budget grounds above, and because it needs a database and a running
  application — reintroducing exactly the dependency that makes headless verification
  valuable.

## Consequences

### Positive

- **The gate's claim is honest and bounded.** `checks_run` makes "not checked" visible instead
  of letting a silent omission read as a pass.
- **Verification is offline, fast and CI-safe** — no network, no database, no engine build.
- **This plugin covers a real, proven gap.** The dead-transition check is not duplicated
  effort; nothing in DGF performs it.

### Negative

- **We are writing validators DGF arguably should own.** If `process.xsd` later gains
  `xs:keyref`, the dead-transition check becomes redundant work that still has to be
  maintained until it is deliberately retired.
- **Vendoring creates a drift surface.** Vendored XSDs can silently fall behind upstream.
  ADR 0003's manifest and digest make drift *detectable*, not impossible.
- **No gate covers runtime behaviour.** A process can pass every check here and still fail in
  the browser. This is a real and permanent limit of headless verification, not a temporary
  gap to be closed later.
- **`checks_run` is a local extension.** A strict consumer of the original AI Factory gate
  contract will ignore it, so the honesty it provides is only available to consumers that
  know to look.

### Follow-ups

- Propose `xs:key` / `xs:keyref` for `States/State/@name` ↔ `Transition/@state` upstream in
  `process.xsd`. Owned by the DGF team; tracked here because it would retire a check.
- Build a fixture corpus of known-bad process files alongside the validators (milestone 8) —
  none exists upstream, and a validator with no failing fixture has not been tested.
- Confirm handler resolution is statically decidable once component resolution lands; if a
  handler can be registered at run time in a way a static scan cannot see, downgrade that
  check from blocking to a warning and record why.
