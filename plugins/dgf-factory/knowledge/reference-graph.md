---
dgf_version: "1.1.11"
read_date: 2026-09-27
---

# Reference graph — every reference a configuration file makes, as the engine resolves it

Structural facts: stamp only. Each row of §1 is one kind of reference — an **edge** from one
configuration file to another — read from the runtime class that binds it and the manager that loads
its target. §2 says how each `Resolves as` value turns a reference into a file, and §3 what a static
walk of these edges cannot see. The files read are in the maintainer provenance ledger for this file.

## 1. The edges

<!-- machine-read: reference-edges -->
| Edge | From | Element | Attribute | Condition | To | Resolves as | When absent | When empty | Reach | Checked by |
|---|---|---|---|---|---|---|---|---|---|---|
| `process-action` | `process` | `OnStart State Transition` | `action` | — | `workflow` | `action` | `throws` | `unknown` | `follow` | `validate_process.py` |
| `multitask-settings` | `process` | `States/State` | `name` | — | `multitask` | `multitask-file` | `skipped` | `unknown` | `follow` | — |
| `multitask-action` | `multitask` | `TaskGroup` | `action expiredaction postviewaction` | — | `workflow` | `action` | `throws` | `unknown` | `follow` | `validate_process.py` |
| `validation-flow` | `process` | `Process` | `validationFlow` | — | `workflow` | `workflow-name` | `throws` | `unknown` | `follow` | `validate_process.py` |
| `change-state-process` | `workflow` | `StateProcess` | `process` | `mode-change-state` | `process` | `process-name` | `caught` | `unknown` | `none` | `validate_process.py` |
| `start-process` | `workflow` | `StateProcess` | `process` | `mode-start-info` | `process` | `process-name` | `caught` | `unknown` | `none` | — |
| `sub-workflow` | `workflow` | `SubWorkflow/Settings` | `workflow` | — | `workflow` | `workflow-name` | `throws` | `unknown` | `follow` | — |
| `invoke-table` | `workflow` | `Invoke/Settings` | `table` | `control-form` | `settings` | `table-name` | `throws` | `unknown` | `end` | — |
| `invoke-form` | `workflow` | `Invoke/Settings` | `table+form` | `control-form` | `form` | `invoke-form` | `template` | `unknown` | `follow` | — |
| `record-table` | `workflow` | `UpdateRecord/Settings CreateRecord/Settings` | `table` | — | `settings` | `table-name` | `throws` | `unknown` | `end` | — |
| `record-form` | `workflow` | `UpdateRecord/Settings CreateRecord/Settings` | `table+form` | — | `form` | `form` | `template` | `unknown` | `follow` | — |
| `island-table` | `workflow` | `XmlIsland/Settings` | `table` | `fieldset-non-empty` | `settings` | `table-name` | `throws` | `unknown` | `end` | — |
| `datasource-step` | `workflow` | `DataSourceStep` | `DataSourceName` | — | `component` | `datasource` | `throws` | `none` | `end` | — |
| `form-table` | `form` | — | — | — | `settings` | `owning-table` | `throws` | — | `end` | `validate_model.py` |
| `extract-table` | `settings` | `field/extract` | `table` | — | `settings` | `table-name` | `throws` | `none` | `none` | `validate_model.py` |
| `extract-view` | `settings` | `field/extract` | `table+view` | — | `lookup-view` | `lookup-view` | `template` | `none` | `none` | `validate_model.py` |
| `extract-dialog` | `settings` | `field/extract` | `dialog` | `extract-no-table` | `lookup-dialog` | `lookup-dialog` | `throws` | `throws` | `none` | `validate_model.py` |
| `slavegrid-table` | `settings` | `field/slavegrid` | `table` | — | `settings` | `table-name` | `throws` | `throws` | `none` | `validate_model.py` |
| `slavegrid-grid` | `settings` | `field/slavegrid` | `table+grid` | — | `grid-form` | `grid` | `template` | `throws` | `none` | `validate_model.py` |
| `layout-child` | `component` | `content[]` | `path` | — | `component` | `component-file` | `skipped` | `unknown` | `none` | `resolve_components.py` |
| `reference-component` | `component` | `ReferenceComponent` | `componentName` | — | `component` | `component-file` | `skipped` | `unknown` | `none` | `resolve_components.py` |

How to read a row:

- **`From` and `To`** name the file an edge leaves and the file it reaches:
  - `process` — `FM/_PROCESS/<P>/process.xml`;
  - `multitask` — a MultiTask settings file, `FM/_PROCESS/<P>/<State>.xml` whose root is
    `MultiTaskSettings`;
  - `workflow` — a `_workflow.xml`, shared (`FM/_WORKFLOW/<X>/`) or process-local
    (`FM/_PROCESS/<P>/<X>/`);
  - `settings` — an entity's `FM/_DATA/<E>/settings.xml`;
  - `form` — `FM/_DATA/<E>/_forms/<f>/_form.xml`;
  - `lookup-view` — `FM/_DATA/<E>/_lookupviews/<v>/_view.xml`;
  - `lookup-dialog` — `FM/_LOOKUP/<d>/_dialog.xml`;
  - `grid-form` — `FM/_DATA/<E>/_gridforms/<g>/_grid.xml`;
  - `component` — a JSON file under `FM/_COMPONENTS/`.
- **`Element`** names where the reference sits. In an XML file, `A` is any element named `A`, the root
  included, and `A/B` is an element `B` whose parent is an `A`. Space-separated values are
  **alternatives**, each its own edge. The **step** of an XML edge is the parent in `A/B`, and the
  element itself in `A`. In a component file, `content[]` is each direct child of a layout
  component's `content` array, and `ReferenceComponent` is each component whose type is that member,
  found by the walk `json-reader.md` §2 describes. `—` is the file itself.
- **`Attribute`** names the value. Space-separated values are alternatives, each its own edge. `a+b` is
  **one composite reference**: its parts are passed, in order, to the `Resolves as` rule. `—` is no
  value.
- **`Condition`**, when not `—`, must hold on the step for the edge to exist:
  - `control-form` — the `Invoke`'s `control`, upper-cased, is `FORM` (`HumanWorkflow.ProcessInvokeAsync`);
  - `fieldset-non-empty` — the `XmlIsland` has at least one `FieldSet/Field`
    (`SequenceWorkflow` loads its table only then);
  - `extract-no-table` — the `extract` has no `table`, or an empty one: only then is the dialog loaded
    (`LookUpViewManager.LoadDefaultView`);
  - `mode-change-state` — the `StateProcess`'s `mode` is exactly `CHANGE_STATE`;
  - `mode-start-info` — the `StateProcess`'s `mode` is exactly `START` or `INFO`. Any other mode does
    nothing, so it is no reference.
- **`When absent`** is what the runtime does when the target does not exist:
  - `throws` — the loader throws, and the request or step fails;
  - `template` — the runtime builds the file from a default or from the entity's fields and **writes it
    into the workspace**;
  - `caught` — the step catches the failure and records `_HasError_` in its output, and the workflow
    goes on;
  - `skipped` — the runtime ignores the missing target, or a missing target is not a reference at all;
  - `unknown` — not established. No check blocks on it.

  `template` has exceptions that depend on the workspace, not the edge, and each one makes that one
  reference throw ([`data-model.md`](data-model.md) §3.2, §3.6, §4):
  - a missing form or grid whose **folder exists**, when the table has a `default` of that kind: the
    runtime copies it, and the copy throws into a folder that exists;
  - a missing view whose table has **no `Text` field besides its key**: the view the runtime would
    generate has no field to show;
  - a missing form, when the table has **no `default` form** and a field has **no `uimask`**: the form
    the runtime would generate cannot be built;
  - a missing view, grid or form the runtime would generate, when the names and titles it pastes in,
    unescaped, leave the generated file unparsable — a bare `&` or `<`, or a `"` that closes an
    attribute where what follows does not parse (`knowledge/data-model.md` §3.6).
- **`When empty`** is what the runtime does when the value — for a composite, its first part — is empty
  or missing:
  - `none` — nothing is loaded: the runtime skips the step or takes another branch, so an empty value is
    no reference. An `extract` with no `table` loads its dialog instead ([`data-model.md`](data-model.md)
    §3.2), and a `DataSourceStep` with no name is a no-op;
  - `throws` — the loader is given the empty name and throws. An `extract` with neither `table` nor
    `dialog` throws `Lookup table/view or dialog not defined` (§3.2 there), and a `slavegrid` with no
    `table` throws in `TableManager.LoadAsync` (§3.1 there);
  - `unknown` — not established, so an empty value is read as no reference, and no check blocks on it;
  - `—` — the row names no attribute.
- **`Reach`** says how a walk from a process treats the edge: `follow` reaches the target and walks on
  through it; `end` reaches the target and stops there; `none` does not walk the edge, which still
  names its source as a referrer of the target.
- **`Checked by`** names the plugin validator that reports the edge when it resolves nowhere, or `—`
  when none does.
- **An empty value is a reference only where `When empty` is `throws`**, or where the step's own
  `Assign` sets the run-time name that replaces it (§3.1). An empty form, view or grid part of a
  composite is `default` (§2), and so is a grid name of only spaces.
- **Case.** Every file is looked up exactly: on Linux, where DGF runs, a name matches byte for byte.

## 2. How a reference resolves

A running application has one **selected** workspace; `webasm` is the **base**. A reference in a
`webasm` file that the selected workspace decides is resolved in whichever application runs it.

| Resolves as | Rule |
|---|---|
| `action` | A process or MultiTask `action`: [`process-model.md`](process-model.md) §2.3, then §2.2. Only a `WORKFLOW:` action is a workflow reference; a bare name is process-local |
| `workflow-name` | A workflow name used **verbatim** — no process-local prefix — by `WorkflowManager.GetWorkPath` ([`process-model.md`](process-model.md) §2.2). A `SubWorkflow`'s target is loaded this way (`HumanWorkflow.OnSubWorkflow`), exactly as `validationFlow` is (§2.4 there) |
| `process-name` | `ProcessManager.GetWorkPath` ([`process-model.md`](process-model.md) §2.5) |
| `multitask-file` | `<the process's folder>/<state name>.xml`, and only when that file exists with root `MultiTaskSettings` ([`process-model.md`](process-model.md) §2.7). A state with no such file is not a MultiTask state, so it names nothing |
| `table-name` | `TableManager`: clean the name, then test `BASE:` in any case ([`data-model.md`](data-model.md) §3.1) |
| `form` | `FormManager.LoadAsync(table, form)`: the table as `table-name`, then `_forms/<form>/_form.xml` in its folder; an empty form is `default` ([`data-model.md`](data-model.md) §4) |
| `invoke-form` | As `form`, after cutting the form name at its first `/READONLY`, which the form control strips and reads as the read-only flag (`FormControl.InitFormFromConfigurationAndCreateRowHandler`) |
| `lookup-view` | `LookUpViewManager.LoadAsync(table, view)`: the table as `table-name`, then `_lookupviews/<view>/_view.xml` in its folder; an empty view is `default` ([`data-model.md`](data-model.md) §3.2) |
| `lookup-dialog` | `LookUpDialogManager`: `FM/_LOOKUP/<dialog>/_dialog.xml` in the selected workspace only — no `BASE:` form, no cleaning ([`data-model.md`](data-model.md) §3.2) |
| `grid` | `EditableGridManager.LoadAsync(table, grid)`: the table as `table-name`, then `_gridforms/<grid>/_grid.xml` in its folder; an empty grid, or one of only spaces, is `default` ([`data-model.md`](data-model.md) §3.4) |
| `owning-table` | The entity whose folder holds the form: `FM/_DATA/<E>/settings.xml` beside `_forms/`, in the form's own workspace ([`data-model.md`](data-model.md) §4) |
| `datasource` | `DataSourceLoader`: `FM/_COMPONENTS/DataSource/<name>.json`, `BASE:` in any case, subfolders allowed — the component-file rule with the member `DataSource`. An empty name is a no-op, not a reference |
| `component-file` | `ComponentFileLoadService`: `FM/_COMPONENTS/<member>/<name>.json` ([`json-reader.md`](json-reader.md) §2.1) |

Notes on the rows:

- **A workflow step's `throws` holds unless the step has `hideExceptions="true"`**
  (`SequenceWorkflow.WriteErrorMessage` rethrows only then). The graph does not model it: the reference
  is still broken, and a hidden exception only moves the failure to whatever reads `_HasError_`.
- **`UpdateRecord` and `CreateRecord`** load through `FormManager.LoadAsync(table, form)`
  (`SequenceWorkflow`), so their table throws and their form is `template`. They skip the save when the
  step's assigned data is empty, which a static walk cannot know.
- **`StateProcess/@table`** is a database table name, handed to the process client; it is not an edge.
  **`Process/@table`** is one too: `InstanceHandler` passes it to SQL, `BASE:` stripped. No loader opens
  `_DATA` for either.
- **A `relation`'s `table`, a `binding`, and an entity's `datasource`** name database objects or
  columns, not files, and are not edges ([`data-model.md`](data-model.md) §3.3, §3.5, §1).
- **A missing component file** reads as nothing, and the component it would supply vanishes without an
  error ([`json-reader.md`](json-reader.md) §2.1) — hence `skipped`, although the plugin's component
  check still reports one.

## 3. What static reach cannot see

A walk of §1 from every process finds the files a process **can** reach through what its files say. It
does not find everything a running system reaches:

- **Names assigned at run time** (§3.1). In DGF's samples: `_WORKFLOWNAME_` 7 uses in 4 files,
  `_FORMNAME_` 21 in 15, `_TABLENAME_` 32 in 13.
- **Processes chosen from the database.** The process for a case is read from database rows by stored
  procedures such as `prc_WF_StartProcess`, and the ProcessFlow component starts one by a `ServiceID`
  (`ProcessFlowComponentService`). No file names that process.
- **Open handlers.** A process name written in brackets, `[<name>]`, opens the handler file
  `FM/_PROCESS/<name>.xml` (root `Handler`, read into `OpenHandler`) in the selected workspace, which
  picks the process at run time from the record's running instance or its `Case` rules
  (`StateProcessClient`, `InstanceHandler.ResolveOpenHandlerAsync`).
- **Entry points outside processes.** `_PROFILE` trees (`WORKFLOW:` 262, `STATEPROCESS:` 172 in the
  samples), sitemaps, `_form.xml` and view `WORKFLOW:` strings (73 in `_form.xml`), and JSON `workflow`
  components (44) start workflows no process names. A shared workflow no traced reference reaches may
  still be reached from one of these.
- **`hideExceptions`**, which turns a `throws` into a recorded error (§2).

### 3.1 Run-time names

A step's own `Assign` child is evaluated for that step, before it runs (`RoundTrip.AssignXmlDataAsync`),
and three field names replace what the step's settings name (`RoundTrip.AssignFieldAsync`,
`HumanWorkflow`). An `Assign` elsewhere in the workflow does not affect the step.

<!-- machine-read: run-time-names -->
| Name | Step | Replaces |
|---|---|---|
| `_WORKFLOWNAME_` | `SubWorkflow` | `workflow` |
| `_TABLENAME_` | `Invoke` | `table` |
| `_FORMNAME_` | `Invoke` | `form` |

- **`Step`** is the step element, and **`Replaces`** the settings attribute whose value the name
  replaces when the assignment is non-empty.
- An edge whose step is `Step`, whose own `Assign` has a `Field` named `Name`, and whose `Attribute`
  includes `Replaces` is **dynamic**: its static target may not be the one that runs. An `Invoke`'s
  form depends on its table, so `_TABLENAME_` makes its `invoke-form` edge dynamic too.
- `UpdateRecord`, `CreateRecord` and `XmlIsland` read their settings directly, so these names do not
  change what they load.

## See Also

- [`README.md`](README.md) — the stamping convention and the machine-read table contract (§7)
- [`data-model.md`](data-model.md) — entities, fields, relations, and what each loader does
- [`process-model.md`](process-model.md) — how process and workflow references resolve
- [`json-reader.md`](json-reader.md) — how component JSON is read, and component file references
