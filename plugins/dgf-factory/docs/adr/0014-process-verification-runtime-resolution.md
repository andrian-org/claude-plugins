---
id: 0014
title: Process verification — structure with a runtime-divergence allowance, semantics resolved the way the runtime resolves them
status: accepted
date: 2026-09-24
deciders: [Andrian Mamei]
supersedes: [0006]
tags: [validation, process, gates]
---

# 0014 — Process verification: structure with a runtime-divergence allowance, semantics resolved the way the runtime resolves them

Supersedes ADR 0006, which superseded ADR 0002. It still closes [blueprint](../blueprint.md)
open question **#5**: *what does verification look like for a process? Is there a way to execute
a process definition headlessly?*

The central finding is unchanged: **structure is headless today; semantics are checked by
nothing DGF ships; execution needs a database.** So is most of ADR 0006: structure with a
runtime-divergence allowance, `End` as a reserved terminal state, unreachable-state as a warning,
and in-process validation against vendored schemas. All of it is restated below.

One thing changes: **how a reference is resolved.** ADR 0006 §2 resolved every `WORKFLOW:` value
"under `FM/_WORKFLOW` of the owning workspace, or — when `BASE:`-prefixed — of `webasm`". That
was written before the engine's resolution code was read. The rules were then run over DGF's
own samples, and they block 62 of 172 references that the runtime can load. This ADR replaces
them with the engine's own rules: which path a reference names, and which workspace "selected"
means when a base-workspace process runs inside an application.

## Context

Read from the DotGov Framework repository at commit `aa1d5c4c2` on **2026-09-24**. Paths are
relative to the DGF repository root. "The samples" means the workspaces under
`src/samples/workspaces/`: the base workspace `webasm` (12 processes) and two applications, `dgf`
(2) and `zims` (13). Together they hold 23 `FM/_PROCESS/<P>/process.xml` files.

### Carried forward from ADR 0006 — re-verified 2026-09-24

- **Structure needs no engine.** `src/Tools/dgf-mcp/Tools/ValidateXmlTool.cs` L36 and L43 —
  `ValidateWorkflowXml` and `ValidateProcessXml` each call
  `validator.Validate(xml, "<artifact>.xsd")` and nothing else.
  `src/Tools/dgf-mcp/DgfMcpServer.csproj` has zero `<ProjectReference>`.
- **The grammar cannot express the state graph.** `process.xsd` declares `StateType` at L44-53
  (required `@name`) and `TransitionType` at L127-133 (required `@state`). It has no `xs:key`,
  `xs:keyref` or `xs:unique`.
- **No shipped validator covers process semantics.**
  `src/Tools/dgf-mcp/Services/XmlCrossReferenceValidator.cs:94` rejects process as an unsupported
  artifact type. `src/Core/DGF.Explorer/Services/DiagnosticCheckService.cs` has its process path
  commented out at L680.
- **Execution is not headless.** Stepping a process runs through
  `src/Core/DGF.OM/Process/StateProcess/InstanceHandler.cs` against a case record in the database.

### What ADR 0002's rules did to the samples — carried forward

| rule as ADR 0002 wrote it | samples flagged | why |
|---|---|---|
| dead transition | **23 / 23** | every one transitions to `End`, which no sample declares |
| unreachable state (walk from `OnStart`) | **17 / 23** | states are entered by routes the walk does not see |
| XSD failure is blocking | **2 / 23** | the XSD lags the runtime model |

**`End` is a terminal state the runtime reserves.** `InstanceHandler.cs` L367 skips state lookup
when the requested state is `End`, and L392 completes the instance instead of entering a state.
L291 and L409 do the same for internal-state chains. `End` is never declared, because it is not a
state — it is the instruction to stop. State lookup is ordinal:
`src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs:68` compares `s.Name.Equals(name)`.

**States are entered without a declared transition.**

- A workflow `<StateProcess mode="CHANGE_STATE" process="…" state="…" applyforstates="…">` step
  moves an instance to any named state: `src/Core/DGF.DataViewer/Workflow/SequenceWorkflow.cs`
  L552-558 calls `StateProcessClient.WorkflowGoToStateAsync`
  (`src/Core/DGF.DataViewer/Process/StateProcessClient.cs:922`). The samples hold 21 such steps.
- A `mode="START"` step starts an instance at its `state` attribute:
  `SequenceWorkflow.cs` L542-543 passes it to `Workflow_StartSilentAsync`. All 15 `START` steps in
  the samples leave `state` empty, so the process's default start applies.
- `InstanceHandler.GoToStateAsync` (L334) checks only that the requested state *exists*
  (L367-372). It does not check that the current state declares a transition to it.
- `InstanceHandler.StartWorkflowInstanceAsync` (L250-259) starts an instance at a caller-named
  `initialState`.
- A state's `<OnTimeout interval="…" state="…">` moves the instance on timeout
  (`InstanceHandler.cs` L350-358). It binds `@state` directly
  (`src/Core/DGF.Domain/Process/StateProcess/TimeoutStateEvent.cs` L7-11) and is **absent from
  `process.xsd`**. No sample uses it.

**The XSD lags the runtime deserializer.** The two failing samples use constructs that
`XmlSerializer` binds:

- `webasm/FM/_PROCESS/PrintDeliver/process.xml` uses `State/@type="StoredProcedure"` (not in
  `StateTypeEnum`; `State.Type` is a plain `string`, `State.cs` L50-51) and
  `<StoredProcedureActivity>` inside `OnInit` (the XSD allows only `UpdateRecord` and `Task`).
- `dgf/FM/_PROCESS/DGF.Demo.EService/process.xml` uses `State/@ftitle`, 3 times.
- The runtime model binds attributes and elements the XSD lacks:
  `src/Core/DGF.Domain/Process/StateProcess/State.cs` L13 `fdesc`, L16 `ftitle`, L37 `OnTimeout`;
  `Process.cs` L20 `hideDesc`; `AbstractStateEvent.cs` L10 `StoredProcedureActivity`.

**The references are workflows, not components.** The samples hold 198 `action` attributes: 172
`WORKFLOW:` references and 26 empty. None names anything else. `Process/@validationFlow` names a
workflow too (`BASE:EDefaultProcessValidation` in `webasm`). `SubProcess` exists only as a value
of `StateTypeEnum`: no sample uses it, and nothing under `src/Core/DGF.Domain/Process` or
`src/Core/DGF.OM/Process` refers to it.

### How the engine turns a reference into a path — new

**A workflow name becomes a path in exactly one way per form, with no fallback.**
`src/Core/DGF.OM/Workflow/WorkflowManager.cs` L15-40, `GetWorkPath(name)`:

| name | path |
|---|---|
| `BASE:X` | `BaseWorkflowPath/X` — `webasm/FM/_WORKFLOW/X` |
| `/X` | `WorkflowPath/X` — the **selected** workspace's `FM/_WORKFLOW/X` |
| `P/X` | `ProcessPath/P/X` — the selected workspace's `FM/_PROCESS/P/X` |
| `BASE:P/X` | `ProcessBasePath/P/X` — `webasm/FM/_PROCESS/P/X` |

A bare `X` with no `/` falls through to `WorkflowPath/X`. `LoadWorkflowAsync` (L53-58) appends
`_workflow.xml`, and `Exists` (L92-96) is `File.Exists` on that literal path. On Linux, where DGF
runs, that is case-sensitive. The paths come from `src/Core/DGF.Kernel/WorkspaceSettings.cs`
L44-62: `WorkflowPath` and `ProcessPath` hang off the selected workspace's `FmPath`, and
`BaseWorkflowPath` and `ProcessBasePath` off `webasm`'s `FmBasePath`.

**A process `@action` becomes a workflow name in two steps.**
`StateProcessClient.cs` L824-846, `ResolveUiSettings`: the value is cut at the first `;`, then
split on `:`. `WORKFLOW:BASE:X` and `WORKFLOW:/BASE:X` both normalise to `BASE:X`, so the two
spellings are one form. Then L585-595, `RenderUiControlAsync`, case `"WORKFLOW"`: a name starting
with `BASE:` is used as is; a name starting with `/` is used as is; any other name `X` becomes
`<processName>/X`, which is **process-local**. `processName` is the process as it was referenced,
so it may itself be `BASE:P`, and then `BASE:P/X` lands in `webasm`'s `_PROCESS/P/X`.

In the samples, the 172 `WORKFLOW:` values are 114 `/X`, 25 `/BASE:X`, 15 `BASE:X` and 18 bare
`X`.

**`Process/@validationFlow` is a workflow name used verbatim.** `StateProcessClient.cs` L136-150
passes it to `BackgroundWorkflowService` as `name`, with no process-local prefix. So `BASE:X` is
`webasm`'s `_WORKFLOW/X` and a bare `X` is the selected workspace's `_WORKFLOW/X`.

**A process is located the same way.**
`src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs` L12-22: an unprefixed `P` is
`ProcessPath/P`, and `BASE:P` is `ProcessBasePath/P`. There is no fallback. The file is exactly
`process.xml`. `process.schema` beside it is designer and monitoring metadata, which the engine
does not read to run the process. A `CHANGE_STATE` step's `process` resolves through the same
`ProcessManager`.

**`CHANGE_STATE` compares strings ordinally and does not trim.** `SequenceWorkflow.cs` L522 and
the `switch` at L540-558 compare `mode` with `"CHANGE_STATE"` exactly, so `change_state` is not a change-state
step. `applyforstates` is `Split(';')`, with no trim, and each token is compared with the current
state by `Array.IndexOf` (`StateProcessClient.cs:937`). A token with a leading space never
matches. The flow-component engine does the same:
`src/Components/Extensions/DGF.FlowComponents/WorkFlow/Engine/Core/StepExecution/Handlers/StateProcessStepHandler.cs`
L196-198.

**Other files carry the same reference strings.** A MultiTask state's settings are read from
`FM/_PROCESS/<P>/<State>.xml` (`src/Core/DGF.Domain/Process/StateProcess/MultiTaskSettings.cs`
L25-42). Its root is `MultiTaskSettings`, and each `TaskGroup` element carries `action`,
`expiredaction` and `postviewaction` (`MultiTaskGroup.cs` L7-17). `StateProcessClient.cs`
L868-897 uses them in place of the state's `@action`. No sample has one. `OpenHandler` files sit
flat under `_PROCESS/<name>.xml` (`OpenHandler.cs` L28-39), and `Process/@table` names
`_DATA/<table>/settings.xml` (`TableManager.cs` L16-22).

### What "selected workspace" means for a base-workspace process — new

`WorkspaceSettings` has one selected workspace per running application. A process in `webasm` is
reached as `BASE:P` from an application, so it runs with **that application** selected. Its `/X`
reference resolves in the running application's `_WORKFLOW`, not in `webasm`'s. The same holds for
its bare `@validationFlow`, and for a workflow in `webasm`'s `_WORKFLOW` whose `CHANGE_STATE` step
names an unprefixed process. The resolution is app-dependent: it can pass in one application and
fail in the next.

### What ADR 0006 §2's rules do to the samples — measured 2026-09-24

A scratch dry run applied ADR 0006's rules and the engine's rules to all 172 `WORKFLOW:` values:

| where the reference resolves | count |
|---|---|
| `FM/_WORKFLOW` of the owning workspace | 110 |
| only process-locally (`_PROCESS/<P>/X`) | 18 |
| `/X` in a `webasm` process, only in the `zims` application | 29 |
| nowhere | 15 |

ADR 0006 §2 as written blocks the 18 process-local references and the 29 app-dependent ones on
top of the 15 unresolved ones: **62 of 172**. Of the 15 that resolve nowhere, 13 are `/X` values
in `webasm`'s `Process1`–`Process3`. The other 2 are a true defect:
`zims/FM/_PROCESS/ZIMS4_InspectionBorder/process.xml` L5 and L20 name
`WORKFLOW:/InspectionBorderOrOutSide`, which `zims/FM/_WORKFLOW` does not contain.

The other semantic rules held up. With `End` exempt and `OnTimeout` included, there are **0**
dead transitions. With the full entry set, 15 states in 15 of the 23 processes are unreachable.
All 21 `CHANGE_STATE` steps use `mode="CHANGE_STATE"`. Their unresolved targets are exactly ADR
0006's 8 absent processes, plus **1 true defect**:
`zims/FM/_WORKFLOW/Expert.MoveTaskTo/_workflow.xml` L15 moves `BASE:ExpertReview` to
`RecordState13`, and `webasm/FM/_PROCESS/ExpertReview/process.xml` declares only `RecordState5`,
`RecordState6`, `RecordState7`, `RecordState8` and `IfElse6`.

## Decision

**A process is "verified" when it passes this plugin's structural check and the semantic checks
below, each reported in `checks_run`. Structure is judged against the grammar the runtime actually
reads. References are resolved by the engine's own rules — one path per form, exact case, no
fallback — and a reference whose result depends on which application runs it is a warning that
names the applications. A gate never implies a check it did not run, and never blocks on a
construct the runtime accepts.**

### 1. Structure — XSD, with a runtime-divergence allowance — carried forward

Validate against the vendored `process.xsd`. Then classify each failure:

- **Blocking** (exit `1`) — any XSD failure *not* explained by the divergence list. The tree
  cannot be reasoned about, so the semantic checks are skipped and reported as not run.
- **Runtime-divergence warning** (exit `2`) — a failure on a construct the runtime deserializer
  binds. The report names the construct and the model member that binds it, e.g. `State.ftitle`.

The divergence list is a **stamped structural fact** in `knowledge/`, derived only from the
`[XmlElement]` / `[XmlAttribute]` / `[XmlArray]` / `[XmlArrayItem]` bindings in `State.cs`,
`Process.cs`, `AbstractStateEvent.cs`, `Transition.cs`, `TimeoutStateEvent.cs` and the classes
they reference. It is never derived from "what the samples happen to use": a list built that way
would excuse any typo that one file happened to contain.

`checks_run` records `xsd-structure` in both cases, so a divergence warning is still a check that
ran.

### 2. Semantic checks

All run on files under the workspaces root, without a database or the engine.

| check | rule | severity |
|---|---|---|
| **dead transition** | every `Transition/@state` under `OnStart/Transitions` and `States/State/Transitions`, and every `State/OnTimeout/@state`, names a declared `States/State/@name` **or the reserved `End`**, compared ordinally | blocking |
| **unreachable state** | every `States/State/@name` is reachable from an entry set of `OnStart` transitions ∪ `OnTimeout` targets ∪ the `state` of every `CHANGE_STATE` step, and every non-empty `state` of a `START` step, that names this process anywhere under the workspaces root | **warning** — `StartWorkflowInstanceAsync` can start at any state, and no static scan sees every caller |
| **workflow-reference resolution** | every `WORKFLOW:` value in `@action` on `OnStart`, `State` and `Transition`, and in a MultiTask `TaskGroup`'s `action`, `expiredaction` and `postviewaction`, resolves by §3 | blocking; app-dependent is a warning |
| **validation-flow resolution** | `Process/@validationFlow` resolves by §3, used verbatim as a workflow name | blocking; app-dependent is a warning |
| **change-state target resolution** | every workflow `<StateProcess mode="CHANGE_STATE">` has a `process` that resolves by §3, and its `state` and each non-empty `;`-separated `applyforstates` token, **untrimmed**, names a declared state of that process or `End`, compared ordinally | blocking; app-dependent is a warning |

`applyforstates` names *source* states — the states the step applies from — so they are not in
the unreachable-state entry set.

An empty `@action` names nothing, so workflow-reference resolution skips it. A value whose prefix
is not `WORKFLOW:` (for example `FORM:`) is not a workflow reference and is skipped too; the report
counts the skipped values as not run, never as passed. A step whose `mode` is not exactly
`CHANGE_STATE` is not a change-state step.

Change-state target resolution is the dead-transition defect seen from the other side. A workflow
that moves an instance to a state the process no longer declares fails at run time —
`InstanceHandler.cs` L371 throws `New state '…' information not found` — and at authoring time
nothing reports it.

### 3. Resolution — the engine's rules, one path per form

For a process `P` in workspace `W`: when `W` is an application, `P` is reached as `P`; when `W` is
`webasm`, it is reached as `BASE:P` from every application.

| reference | `W` is an application | `W` is `webasm` |
|---|---|---|
| `WORKFLOW:BASE:X` or `WORKFLOW:/BASE:X` | `webasm/FM/_WORKFLOW/X/_workflow.xml` | same |
| `WORKFLOW:/X` | `W/FM/_WORKFLOW/X/_workflow.xml` | `A/FM/_WORKFLOW/X/_workflow.xml` for **every** application `A` |
| `WORKFLOW:X` (bare, process-local) | `W/FM/_PROCESS/P/X/_workflow.xml` | `webasm/FM/_PROCESS/P/X/_workflow.xml` |
| `@validationFlow` `BASE:X` | `webasm/FM/_WORKFLOW/X/_workflow.xml` | same |
| `@validationFlow` bare `X` | `W/FM/_WORKFLOW/X/_workflow.xml` | every application, as `/X` |
| `CHANGE_STATE` `process="BASE:Q"`, in a workflow owned by `W` | `webasm/FM/_PROCESS/Q/process.xml` | same |
| `CHANGE_STATE` `process="Q"`, in a workflow owned by `W` | `W/FM/_PROCESS/Q/process.xml` | every application, as `/X` |

The general rule is the composition in §Context: the value becomes a workflow name by
`ResolveUiSettings` and `RenderUiControlAsync`, and the name becomes a path by `GetWorkPath`. The
table is that composition for the forms the samples use. Every other form is resolved by the same
composition, never by a guess.

- **No fallback.** A reference resolves where its form says or not at all. A process-local
  reference is not retried in `_WORKFLOW`, and an application reference is not retried in
  `webasm`.
- **Exact case.** Existence is decided by comparing directory entries by name, as `File.Exists`
  does on Linux. A reference that resolves only on a case-insensitive filesystem is its own
  warning, `CASE_ONLY_MATCH`, naming the entry that differs. It does not pass silently on macOS,
  and it does not block a case the runtime might still serve on Windows.
- **App-dependent is a warning** (D2). When a `webasm` process's reference resolves per
  application, it passes if it resolves in every application under the root. Otherwise it is
  `WORKFLOW_APP_DEPENDENT` (exit `2`), naming the applications it resolves in and those it does
  not. It never blocks: an application that never runs the process never loads the workflow, and
  nothing in the workspaces root says which applications do. It is reported, never passed
  silently.
- **The workspaces root.** A file's owning workspace is the directory directly above its `FM/`,
  and the root is that workspace's parent. The applications are every directory under the root
  with an `FM/`, except `webasm`.

### 4. Validation runs against vendored schemas, in-process — carried forward

Verification loads the XSDs vendored under `knowledge/schemas/xsd/` and validates in-process. It
does **not** require a locally booted MCP server. A gate that needs a network service or a running
server cannot be relied on in CI or offline. The hosted MCP at `https://dgf-mcp.dotgov.uk/mcp`
stays useful for documentation and as a cross-check, never as the gate's dependency.

This creates a re-vendor obligation, discharged by
[ADR 0013](0013-version-gating-provenance-ledger.md): the vendored set's provenance ledger records
the DGF commit, and a per-file digest makes drift detectable. Which process runs the validation —
its language and its dependencies — is [ADR 0015](0015-validator-runtime-and-json-reader.md).

### 5. Nothing replaces execution in the gate — carried forward

A process cannot be executed headlessly, so **this plugin's gates make no claim about runtime
behaviour.** The claim is bounded: *this process matches the grammar the runtime reads and is free
of the defects listed in `checks_run`.*

Browser-driven verification stays **out of the gate**. Declaring browser MCP servers costs roughly
12,000 tokens of tool schema per session, which is why `.ai-factory/DESCRIPTION.md` excludes them.
Execution-level confidence remains the job of DGF's Playwright suite under
`tests/src/specs/solutions/`, run by CI and by humans.

The `dgf-gate-result` block carries the additive optional field
`"checks_run": ["xsd-structure", "dead-transition", …]`. Consumers that do not know the field
ignore it, so `schema_version` stays `1`. It is implemented under roadmap milestone 10.

## Alternatives considered

- **Keep ADR 0006 and correct the resolution rules by erratum.** Rejected. Resolving process-local
  references, and turning app-dependent references from blocks into warnings, change what the
  checks decide. [The ADR contract](README.md) routes decisions through supersession.
- **Keep ADR 0006 §2 as written** — `_WORKFLOW` of the owning workspace, or `webasm` for `BASE:`.
  Rejected on the measurement: it blocks 62 of 172 references in DGF's own samples, 47 of them
  loadable by the runtime.
- **Resolve a reference anywhere it could be found** — owning workspace, then `webasm`, then any
  application. Rejected. The engine has no fallback, so a reference found only by the fallback
  fails at run time. That is a false negative, the failure a gate exists to prevent.
- **Block an app-dependent reference** unless it resolves in every application. Rejected: 29
  references in the samples resolve in `zims` and not in `dgf`, and nothing in the workspaces
  root says `dgf` runs those processes. A block that is sometimes wrong trains people to bypass it.
- **Pass an app-dependent reference if it resolves in any application.** Rejected: it hides the
  applications in which the reference fails, which is exactly what a base-workspace change breaks.
- **Compare names case-insensitively,** as the macOS filesystem does. Rejected: DGF runs on Linux,
  where `File.Exists` is case-sensitive. A validator that passes a case-only match on a
  developer's Mac passes a reference that fails in production.
- **Treat XSD-valid as necessary,** as ADR 0002 did. Rejected in ADR 0006, and still: 2 of 23
  shipped samples would be blocked for constructs the runtime reads.
- **Drop the XSD and validate against the runtime model directly.** Considered in ADR 0006, still
  not chosen. It means reimplementing `XmlSerializer`'s binding rules for every model class; the
  divergence list gets the same answer for the constructs that actually diverge.
- **Keep unreachable-state blocking, using the wider entry set.** Rejected: the entry set still
  misses `StartWorkflowInstanceAsync`'s callers.
- **Add `xs:keyref` to `process.xsd` upstream.** Still the correct long-term fix for dead
  transitions, on an upstream schedule. Kept as a follow-up.

## Consequences

### Positive

- **The rules survive contact with DGF's own processes.** Every reference the runtime can load
  passes or warns. The only blocking findings left in the samples are the two true defects.
- **A base-workspace change is checked against every application that inherits it.** An
  app-dependent reference names the applications it fails in, which is the question a
  `webasm` edit has to answer ([ADR 0004](0004-authoring-entry-point.md)).
- **One real defect class is covered from both sides.** A dangling state name is caught whether it
  is written in the process or in a workflow that drives it.
- **Verification stays offline, fast and CI-safe**, and `checks_run` keeps omissions visible.

### Negative

- **`WORKFLOW_APP_DEPENDENT` will be common.** The samples produce at least 29. Common warnings
  get ignored, and a real failure in one application can hide among them.
- **The resolver mirrors engine code** — `GetWorkPath`, `ResolveUiSettings` and
  `RenderUiControlAsync` — that can change without notice. It is a stamped fact in `knowledge/`
  with a provenance ledger, so a changed source is caught by the drift check, not by a user.
- **Exact-case comparison warns on references that work on Windows.** That is the intent, but
  every such warning has to be explained.
- **The divergence list is a thing to maintain.** Every re-vendor must re-derive it, and a stale
  list either blocks a newly supported construct or excuses a removed one.
- **Unreachable-state is advisory.** A state that truly cannot be entered is reported, not
  blocked. Some real dead states will ship.
- **Change-state resolution reads every workflow in the workspaces root.** It is only possible
  because of ADR 0004's scope, and it pays that scope's context cost on every run.
- **We are still writing validators DGF arguably should own**, and the XSD lag is an upstream gap
  we work around rather than fix.
- **No gate covers runtime behaviour.** A process can pass every check and still fail in the
  browser. This limit is permanent.

### Follow-ups

- **Known-good corpus (milestone 8).** The samples are an **incomplete** workspaces root. The run
  must produce: 0 dead transitions; exactly ADR 0006's 8 absent processes as expected-external
  `CHANGE_STATE` targets — `ZIMS3_Appeal`, `ZIMS3_InvestigationBorder`, `ZIMS4_Investigation`,
  `ZIMS4_Prosecution`, `ZIMS4_Removal`, `ZIMS4_ReportOrder`, `ZIMS4_Revocation`, `ZIMS4_Visa` —
  computed by **resolution**, never by a name prefix; and the two true defects above recorded as
  evidenced exceptions. Every other error is either a validator defect or an evidenced sample
  defect. Warnings are allowed and counted.
- **Known-bad corpus (milestone 8).** One fixture per blocking row above, including each
  resolution form. A validator with no failing fixture has not been tested.
- Write the divergence list and these resolution rules as stamped facts under `knowledge/`
  (milestone 8).
- **Deferred, not committed:** `Process/@table` against `_DATA`, `OpenHandler` files, and
  `SubProcess` references. No evidence yet says what a `SubProcess` state references or how the
  runtime resolves it. Whether any `Field/@value` form is a statically resolvable reference is
  also open.
- Report upstream to the DGF team: the two true defects; `process.xsd` lags the runtime model
  (`fdesc`, `ftitle`, `hideDesc`, `OnTimeout`, `StoredProcedure`, `StoredProcedureActivity`); and
  propose `xs:key` / `xs:keyref` for `State/@name` ↔ `Transition/@state`.
