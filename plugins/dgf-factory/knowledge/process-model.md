---
dgf_version: "1.1.11"
read_date: 2026-09-24
---

# Process model — what the runtime binds, and how a process reference resolves

Structural facts: stamp only. How DGF's state-process engine reads a `process.xml`, where it
differs from `process.xsd`, and how each reference a process or a workflow makes is turned into a
file path. The files read are in the maintainer provenance ledger for this file. Everything here
is read from the engine's model classes and managers, never from what the shipped samples happen
to contain.

## 1. Where the runtime model and `process.xsd` diverge

The engine reads `process.xml` with `XmlSerializer` into the `Process` model. `process.xsd`
describes the same file, but not every construct the model binds. Each row below is a construct
that an `[XmlAttribute]`, `[XmlElement]`, `[XmlArray]` or `[XmlArrayItem]` binding in the model
reads, and that `process.xsd` does not allow. The classes read are `Process`, `State`,
`Transition`, `AbstractStateEvent`, `TimeoutStateEvent`, `InitStateEvent`, `FinalizeStateEvent`,
`AbstractActivity`, `UpdateRecord`, `Task`, `ModuleActivity`, `SendMailActivity`,
`StoredProcedureActivity`, `MultiTask` and `Field`.

- `Kind` is `attribute` (an attribute the XSD owner does not declare), `element` (a child element
  the XSD owner does not declare) or `enum-relaxed` (the XSD restricts the attribute to an
  enumeration, and the model binds a plain `string`).
- `XSD owner` is the `process.xsd` complex type the construct belongs to.
- `Binding` is the model type and the XML name it binds.

<!-- machine-read: process-divergence -->
| Construct | Kind | XSD owner | Binding |
|---|---|---|---|
| `Process/@hideDesc` | attribute | `ProcessType` | `Process.hideDesc` |
| `OnStart/@fdesc` | attribute | `OnStartType` | `State.fdesc` |
| `OnStart/@ftitle` | attribute | `OnStartType` | `State.ftitle` |
| `OnStart/@internal` | attribute | `OnStartType` | `State.internal` |
| `OnStart/@type` | attribute | `OnStartType` | `State.type` |
| `OnStart/OnInit` | element | `OnStartType` | `State.OnInit` |
| `OnStart/OnFinalize` | element | `OnStartType` | `State.OnFinalize` |
| `OnStart/OnTimeout` | element | `OnStartType` | `State.OnTimeout` |
| `State/@fdesc` | attribute | `StateType` | `State.fdesc` |
| `State/@ftitle` | attribute | `StateType` | `State.ftitle` |
| `State/@type` | enum-relaxed | `StateType` | `State.type` |
| `State/OnTimeout` | element | `StateType` | `State.OnTimeout` |
| `Transition/@description` | attribute | `TransitionType` | `Transition.description` |
| `Transition/@icon` | attribute | `TransitionType` | `Transition.icon` |
| `OnInit/ModuleActivity` | element | `OnInitType` | `AbstractStateEvent.Activities` |
| `OnInit/SendMailActivity` | element | `OnInitType` | `AbstractStateEvent.Activities` |
| `OnInit/StoredProcedureActivity` | element | `OnInitType` | `AbstractStateEvent.Activities` |
| `OnInit/MultiTask` | element | `OnInitType` | `AbstractStateEvent.Activities` |
| `OnFinalize/ModuleActivity` | element | `OnFinalizeType` | `AbstractStateEvent.Activities` |
| `OnFinalize/SendMailActivity` | element | `OnFinalizeType` | `AbstractStateEvent.Activities` |
| `OnFinalize/StoredProcedureActivity` | element | `OnFinalizeType` | `AbstractStateEvent.Activities` |
| `OnFinalize/MultiTask` | element | `OnFinalizeType` | `AbstractStateEvent.Activities` |
| `Task/@duedate` | attribute | `TaskType` | `Task.duedate` |
| `Task/@user` | attribute | `TaskType` | `Task.user` |
| `Task/@state` | enum-relaxed | `TaskType` | `Task.state` |
| `Task/Assign` | element | `TaskType` | `AbstractActivity.Assign` |

Notes on the rows:

- **`OnStart` is a `State`.** `Process.OnStart` is typed `State`, so everything a state binds is
  read under `OnStart` too — including `OnInit`, `OnFinalize` and `OnTimeout`. The XSD's
  `OnStartType` declares only `Transitions` and four attributes.
- **A state event's activities are one list.** `AbstractStateEvent.Activities` binds six element
  names — `UpdateRecord`, `ModuleActivity`, `SendMailActivity`, `StoredProcedureActivity`, `Task`
  and `MultiTask` — named after their types. `process.xsd` allows only `UpdateRecord` and `Task`.
- **`OnTimeout`** is a `TimeoutStateEvent`: `@interval` (a `TimeSpan` string), `@state` (the
  state to move to) and the same activity list.
- **`State/@type` and `Task/@state`** are plain strings in the model. `StoredProcedure` is a state
  type the engine uses; the XSD's `StateTypeEnum` lists `Task`, `SWITCH` and `SubProcess` only.

What the list does **not** cover, stated as facts about the serializer:

- `XmlSerializer` reads a class's child elements **in any order**, and a list member in any
  number. `process.xsd` fixes the order and count inside `OnInit` (`UpdateRecord`, then `Task`, at
  most one each) and `OnFinalize` (`Task`, then `UpdateRecord`). An event whose activities are out
  of that order is read by the runtime and rejected by the XSD.
- `XmlSerializer` **skips** an attribute or element that no member binds. Such a construct is not
  read, so it is not in the list: to the runtime it does not exist.
- `XmlSerializer` requires no attribute. `process.xsd` requires several (`Process/@title`,
  `@table`, `@keyName`, `@allowBack`, `@allowHistory`, `@assignTasks`; `OnStart/@action`;
  `State/@name`; `Transition/@state`). A missing one is bound as its default.
- `Process/@regardingType` is an `int` in the model and `xs:string` in the XSD: the XSD accepts
  values the runtime cannot parse.

## 2. How a reference resolves

### 2.1 The workspaces

A running DGF application has one **selected** workspace, and `webasm` is the **base** workspace
(`WorkspaceSettings.BaseWorkspaceName`). Paths come from `WorkspaceSettings`:

| Name | Path |
|---|---|
| `WorkflowPath` | `<selected>/FM/_WORKFLOW` |
| `ProcessPath` | `<selected>/FM/_PROCESS` |
| `BaseWorkflowPath` | `webasm/FM/_WORKFLOW` |
| `ProcessBasePath` | `webasm/FM/_PROCESS` |

A process in `webasm` is reached as `BASE:<process>` from an application, and runs with that
application selected. So "the selected workspace" of a `webasm` process is whichever application
runs it.

Existence is `File.Exists` on the built path. On Linux, where DGF runs, it is case-sensitive, and
no manager falls back to another location when a file is missing.

### 2.2 A workflow name becomes a path

`WorkflowManager.GetWorkPath(name)` has exactly one branch per form. `LoadWorkflowAsync` then
appends `_workflow.xml`.

| Name | Path |
|---|---|
| `BASE:X` | `BaseWorkflowPath/X` |
| `/X` | `WorkflowPath/X` |
| `P/X` — contains `/`, not first | `ProcessPath/P/X` |
| `BASE:P/X` | `ProcessBasePath/P/X` |
| `X` — no `/` | `WorkflowPath/X` |

### 2.3 A process `action` becomes a workflow name

`StateProcessClient.ResolveUiSettings` reads an `action` value (on `OnStart`, a `State` or a
`Transition`): it keeps the part before the first `;`, splits it on `:`, and takes the first part
as the kind and the second as the name. `WORKFLOW:BASE:X` and `WORKFLOW:/BASE:X` both yield the
name `BASE:X`. A kind other than `WORKFLOW` (for example `FORM`) is not a workflow reference.

`StateProcessClient.RenderUiControlAsync` then turns a `WORKFLOW` name into the name
`WorkflowManager` loads, where `processName` is the process as it was referenced — `P`, or
`BASE:P` for a process in `webasm`:

| Name | Workflow name loaded |
|---|---|
| `BASE:X` | `BASE:X` |
| `/X` | `/X` |
| any other `X` | `processName/X` — **process-local** |

So a bare name resolves inside the process's own folder: `ProcessPath/P/X` for an application
process, and `ProcessBasePath/P/X` for a `webasm` one.

### 2.4 `Process/@validationFlow`

The value is a workflow name used **verbatim**, with no process-local prefix, and loaded by
`WorkflowManager` (§2.2). `BASE:X` is `webasm`'s `_WORKFLOW/X`; a bare `X` is the selected
workspace's `_WORKFLOW/X`.

### 2.5 A process name becomes a path

`ProcessManager.GetWorkPath(name)`: an unprefixed `P` is `ProcessPath/P`, and `BASE:P` is
`ProcessBasePath/P`. The file is exactly `process.xml`. The `process.schema` file beside it is
designer and monitoring metadata; the engine does not read it to run the process.

### 2.6 A workflow's `StateProcess` step

A workflow's `<StateProcess mode="…" process="…" state="…" applyforstates="…">` step drives a
process from a workflow:

- `process` resolves through `ProcessManager` (§2.5). In a workflow owned by `webasm`, an
  unprefixed `process` resolves in whichever application runs the workflow.
- `mode` is compared ordinally: only `CHANGE_STATE`, `START` and `INFO` are acted on, and
  `change_state` is none of them.
- **`CHANGE_STATE`** moves a running instance to `state`. The target must exist in the process, or
  the engine throws `New state '…' information not found`. `applyforstates` is split on `;` with
  **no trimming**, and each token is compared ordinally with the instance's current state; an
  empty token matches no state, and a token with a leading space matches no state either.
- **`START`** starts a new instance, at `state` when it is set.

### 2.7 MultiTask settings

A MultiTask state reads `FM/_PROCESS/<process>/<state>.xml` through `ProcessManager.GetWorkPath`.
Its root is `MultiTaskSettings`, and each `TaskGroup` carries `action`, `expiredaction` and
`postviewaction`. These replace the state's own `action` for a task, and are read by §2.3 like it.

## 3. The reserved `End`

`End` is not a state. A transition, an `OnTimeout` or a `CHANGE_STATE` whose target is `End`
completes the instance instead of entering a state, and the engine skips the state lookup for it.
No process declares a state named `End`, and none needs to. State names are compared ordinally, so
`end` is an ordinary, undeclared state name, not the reserved one.

## See Also

- [`README.md`](README.md) — the stamping convention and the machine-read table contract (§7)
- [`composition-specs.md`](composition-specs.md) — where `process.xml` and `_workflow.xml` live
- [`naming-conventions.md`](naming-conventions.md) — the filenames the loaders open
- [`schemas/MANIFEST.md`](schemas/MANIFEST.md) — the vendored `process.xsd`
