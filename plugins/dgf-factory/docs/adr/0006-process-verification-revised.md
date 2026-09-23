---
id: 0006
title: Process verification — structure with a runtime-divergence allowance, semantics by our own validators
status: accepted
date: 2026-09-23
deciders: [Andrian Mamei]
supersedes: [0002]
tags: [validation, process, gates]
---

# 0006 — Process verification: structure with a runtime-divergence allowance, semantics by our own validators

Supersedes ADR 0002. It still closes [blueprint](../blueprint.md) open question **#5**:
*what does verification look like for a process? Is there a way to execute a process
definition headlessly?*

ADR 0002's central finding is unchanged and is restated here: **structure is headless
today; semantics are checked by nothing DGF ships; execution needs a database.** What
changed is that ADR 0002's rules were run against the processes DGF itself ships, and they
failed. A gate built from them would have blocked processes the runtime accepts and flagged
defects that are not defects.

## Context

Read from the DotGov Framework repository at commit `aa1d5c4c2` on **2026-09-23**. Paths
are relative to the DGF repository root. "The samples" means the 23 files matching
`src/samples/workspaces/*/FM/_PROCESS/*/process.xml`.

### Carried forward from ADR 0002 — re-verified 2026-09-23

- **Structure needs no engine.** `src/Tools/dgf-mcp/Tools/ValidateXmlTool.cs` L36 and L43 —
  `ValidateWorkflowXml` and `ValidateProcessXml` each call
  `validator.Validate(xml, "<artifact>.xsd")` and nothing else.
  `src/Tools/dgf-mcp/DgfMcpServer.csproj` has zero `<ProjectReference>`.
- **The grammar cannot express the state graph.** `process.xsd` declares `StateType` at
  L44-53 (required `@name`) and `TransitionType` at **L127-133** (required `@state`). It has
  no `xs:key`, `xs:keyref` or `xs:unique`. The file is 135 lines long and unchanged since
  `b459e52bc` (2026-05-19); ADR 0002 cited `TransitionType` as L137-143, which was never
  right.
- **No shipped validator covers process semantics.**
  `src/Tools/dgf-mcp/Services/XmlCrossReferenceValidator.cs:94` rejects process as an
  unsupported artifact type. `src/Core/DGF.Explorer/Services/DiagnosticCheckService.cs`
  has its process path commented out at L680.
- **Execution is not headless.** Stepping a process runs through
  `src/Core/DGF.OM/Process/StateProcess/InstanceHandler.cs` against a case record in the
  database.

### What ADR 0002's rules do to the samples

Each rule was applied exactly as ADR 0002 §2 wrote it.

| rule as ADR 0002 wrote it | samples flagged | why |
|---|---|---|
| dead transition | **23 / 23** | every one transitions to `End`, which no sample declares |
| unreachable state (walk from `OnStart`) | **17 / 23** | states are entered by routes the walk does not see |
| XSD failure is blocking | **2 / 23** | the XSD lags the runtime model |

A rule that fails every file DGF ships is not a check. Each failure has a cause in the
engine:

**`End` is a terminal state the runtime reserves.** `InstanceHandler.cs` L367 skips state
lookup when the requested state is `End`, and L392 completes the instance instead of
entering a state. L291 and L409 do the same for internal-state chains. `End` is never
declared, because it is not a state — it is the instruction to stop.

**States are entered without a declared transition.**

- A workflow `<StateProcess mode="CHANGE_STATE" process="…" state="…" applyforstates="…">`
  step moves an instance to any named state:
  `src/Core/DGF.DataViewer/Workflow/SequenceWorkflow.cs` L552-558 calls
  `StateProcessClient.WorkflowGoToStateAsync` (`src/Core/DGF.DataViewer/Process/StateProcessClient.cs:922`).
  The samples hold 21 such steps in 15 workflows, all with literal values, and `process`
  may be `BASE:`-prefixed — for example
  `src/samples/workspaces/webasm/FM/_WORKFLOW/Incident_Process_OnHoldCancel/_workflow.xml:19`.
  `RecordState899`, the most frequent target (6 steps), is also one of the states the walk
  flagged as unreachable.
- `InstanceHandler.GoToStateAsync` (L334) checks only that the requested state *exists*
  (L367-372). It does not check that the current state declares a transition to it.
- `InstanceHandler.StartWorkflowInstanceAsync` (L250-259) starts an instance at a
  caller-named `initialState`.
- A state's `<OnTimeout interval="…" state="…">` moves the instance on timeout
  (`InstanceHandler.cs` L352-358). It binds `@state` directly
  (`src/Core/DGF.Domain/Process/StateProcess/TimeoutStateEvent.cs` L7-11) and is **absent
  from `process.xsd`**. No sample uses it.

**The XSD lags the runtime deserializer.** The two failing samples use constructs that
`XmlSerializer` binds:

- `webasm/FM/_PROCESS/PrintDeliver/process.xml` and `dgf/FM/_PROCESS/DGF.Demo.EService/process.xml`
  use `State/@ftitle` (3 times), `State/@type="StoredProcedure"` (not in `StateTypeEnum`), and
  `<StoredProcedureActivity>` inside `OnInit` (the XSD allows only `UpdateRecord` and `Task`).
- The runtime model binds attributes and elements the XSD lacks:
  `src/Core/DGF.Domain/Process/StateProcess/State.cs` L13 `fdesc`, L16 `ftitle`, L37
  `OnTimeout`; `Process.cs` L20 `hideDesc`; `AbstractStateEvent.cs` L10
  `StoredProcedureActivity`.

**"Handler resolution" was aimed at the wrong registry.** All 172 `action` values in the
samples are `WORKFLOW:` references such as `WORKFLOW:/Step1.CaseOfficer.Draft` or
`WORKFLOW:/BASE:AX.StartWalkinCase`. They name workflows under `_WORKFLOW`, not components,
so they resolve against the workflow tree of the workspace and of `webasm` — not the
component registry ADR 0002 made this check wait for. The samples hold 44 `BASE:`-bearing
attributes: 40 `@action`, 1 `@validationFlow`, 1 `Process/@table`, 2 `Field/@value`.

**Two references ADR 0002 missed.** `Process/@validationFlow` names a workflow too (for
example `BASE:EDefaultProcessValidation` in the `webasm` samples). And `SubProcess` exists
only as a value of `StateTypeEnum`: no sample uses it, and nothing under
`src/Core/DGF.Domain/Process` or `src/Core/DGF.OM/Process` refers to it, read 2026-09-23.

## Decision

**A process is "verified" when it passes this plugin's structural check and the semantic
checks below, each reported in `checks_run`. Structure is judged against the grammar the
runtime actually reads, not only against `process.xsd`. A gate never implies a check it did
not run, and never blocks on a construct the runtime accepts.**

### 1. Structure — XSD, with a runtime-divergence allowance

Validate against the vendored `process.xsd`. Then classify each failure:

- **Blocking** (exit `1`) — any XSD failure *not* explained by the divergence list. The
  tree cannot be reasoned about, so the semantic checks are skipped.
- **`xsd-runtime-divergence` warning** (exit `2`) — a failure on a construct the runtime
  deserializer binds. The report names the construct and the model file that binds it.

The divergence list is a **stamped structural fact** in `knowledge/`, derived only from the
`[XmlElement]` / `[XmlAttribute]` bindings in `State.cs`, `Process.cs`,
`AbstractStateEvent.cs` and the classes they reference. It is never derived from "what the
samples happen to use": a list built that way would excuse any typo that one file happened
to contain. Writing it is milestone 8 work.

`checks_run` records `xsd-structure` in both cases, so a divergence warning is still a
check that ran.

### 2. Semantic checks

All run on files under the workspaces root, without a database or the engine.

| check | rule | severity |
|---|---|---|
| **dead transition** | every `Transition/@state` under `OnStart/Transitions` and `States/State/Transitions`, and every `State/OnTimeout/@state`, names a declared `States/State/@name` **or the reserved `End`** | blocking |
| **unreachable state** | every `States/State/@name` is reachable from an entry set of `OnStart` transitions ∪ `OnTimeout` edges ∪ every `CHANGE_STATE` target naming this process anywhere under the workspaces root | **warning** — `StartWorkflowInstanceAsync` can start at any state, and no static scan sees that |
| **workflow-reference resolution** | every `WORKFLOW:` value in `@action` on `OnStart`, `State` and `Transition` resolves under `FM/_WORKFLOW` of the owning workspace, or — when `BASE:`-prefixed — of `webasm` | blocking |
| **validation-flow resolution** | `Process/@validationFlow` resolves the same way | blocking |
| **change-state target resolution** | every workflow `<StateProcess mode="CHANGE_STATE">` has a `process` that resolves (`BASE:` into `webasm`), and its `state` and each `;`-separated `applyforstates` entry names a declared state of that process or `End` | blocking |

Workflow-reference resolution replaces ADR 0002's "handler resolution" and absorbs most of
its "process `BASE:` references" row. Of the 44 `BASE:`-bearing attributes in the samples,
40 are `@action` and 1 is `@validationFlow`, which the two rows above cover. The other 3 —
one `Process/@table` and two `UpdateRecord/Assign/Field/@value` — name data, not workflows,
and are **not covered yet**: resolving a table needs the `_DATA` tree, and a `Field/@value`
is an expression, not always a reference.

Change-state target resolution is the dead-transition defect seen from the other side. A
workflow that moves an instance to a state the process no longer declares fails at run
time — `InstanceHandler.cs` L371 throws `New state '…' information not found` — and at
authoring time nothing reports it.

**`SubProcess` references are deferred, not committed.** No evidence says what a
`SubProcess` state references or how the runtime resolves it. It gets a check when that
evidence exists.

### 3. Validation runs against vendored schemas, in-process — carried forward

Verification loads the XSDs vendored under `knowledge/schemas/xsd/` and validates
in-process. It does **not** require a locally booted MCP server. A gate that needs a network
service or a running server cannot be relied on in CI or offline. The hosted MCP at
`https://dgf-mcp.dotgov.uk/mcp` stays useful for documentation and as a cross-check, never
as the gate's dependency.

This creates a re-vendor obligation, discharged by [ADR 0008](0008-version-gating-revised.md):
the vendored set's `MANIFEST.md` records the DGF commit, and a per-file digest makes drift
detectable. Which process runs the validation — its language and its dependencies — is
[ADR 0007](0007-validator-runtime.md).

### 4. Nothing replaces execution in the gate — carried forward

A process cannot be executed headlessly, so **this plugin's gates make no claim about
runtime behaviour.** The claim is bounded: *this process matches the grammar the runtime
reads and is free of the defects listed in `checks_run`.*

Browser-driven verification stays **out of the gate**. Declaring browser MCP servers costs
roughly 12,000 tokens of tool schema per session, which is why `.ai-factory/DESCRIPTION.md`
excludes them. Execution-level confidence remains the job of DGF's Playwright suite under
`tests/src/specs/solutions/`, run by CI and by humans.

The `dgf-gate-result` block carries the additive optional field
`"checks_run": ["xsd-structure", "dead-transition", …]`. Consumers that do not know the
field ignore it, so `schema_version` stays `1`. It is implemented under roadmap milestone 10.

## Alternatives considered

- **Keep ADR 0002 and add the `End` exemption as an erratum.** Rejected. The exemption
  changes what the dead-transition rule decides, unreachable-state changes severity, and
  structure stops being "XSD-valid or blocked". Those are decisions, and
  [the ADR contract](README.md) routes decisions through supersession.
- **Treat XSD-valid as necessary, as ADR 0002 did.** Rejected on the evidence: 2 of 23
  shipped samples would be blocked for using constructs the runtime reads. A gate that
  blocks valid input trains people to bypass it.
- **Drop the XSD and validate against the runtime model directly.** Considered. It would be
  exact, but it means reimplementing `XmlSerializer`'s binding rules for every model class.
  The divergence list gets the same answer for the constructs that actually diverge, at a
  fraction of the cost, and keeps the XSD as the primary grammar.
- **Keep unreachable-state blocking, using the wider entry set.** Rejected: the wider set
  still misses `StartWorkflowInstanceAsync`, so a blocking result could still be wrong. A
  warning that is sometimes noise is honest; a block that is sometimes wrong is not.
- **Add `xs:keyref` to `process.xsd` upstream.** Still the correct long-term fix for dead
  transitions, still an upstream change on an upstream schedule. Kept as a follow-up.

## Consequences

### Positive

- **The rules survive contact with DGF's own processes.** The shipped samples become a
  corpus the checks must pass, not a corpus they fail.
- **One real defect class is now covered from both sides.** A dangling state name is caught
  whether it is written in the process or in a workflow that drives it.
- **Verification stays offline, fast and CI-safe**, and `checks_run` keeps omissions visible.

### Negative

- **The divergence list is a new thing to maintain.** Every re-vendor must re-derive it, and
  a stale list either blocks a newly supported construct or excuses a removed one.
- **Unreachable-state is advisory.** A state that truly cannot be entered is reported, not
  blocked. Some real dead states will ship.
- **Change-state resolution reads every workflow in the workspaces root.** It is only
  possible because of [ADR 0004](0004-authoring-entry-point.md)'s scope, and it pays that
  scope's context cost on every run.
- **We are still writing validators DGF arguably should own**, and the XSD lag is a second
  upstream gap we now work around rather than fix.
- **No gate covers runtime behaviour.** A process can pass every check and still fail in the
  browser. This limit is permanent.

### Follow-ups

- **Known-good corpus (milestone 8).** The 23 samples must produce zero errors; warnings are
  allowed and listed. The samples are an **incomplete** workspaces root — their workflows
  target `ZIMS4_*` processes that are not in `src/samples/` — so the corpus run declares
  those as expected-external and reports them. It must not pass them silently.
- **Known-bad corpus (milestone 8).** One fixture per blocking row above. A validator with
  no failing fixture has not been tested.
- Write the divergence list as a stamped fact under `knowledge/` (milestone 8).
- Report upstream to the DGF team: `process.xsd` lags the runtime model (`fdesc`, `ftitle`,
  `hideDesc`, `OnTimeout`, `StoredProcedure`, `StoredProcedureActivity`), and propose
  `xs:key` / `xs:keyref` for `State/@name` ↔ `Transition/@state`.
- Decide the `SubProcess` check once its reference semantics are found in the engine.
- Decide whether `Process/@table` `BASE:` references get a resolution check against
  `_DATA`, and whether any `Field/@value` form is a statically resolvable reference.
