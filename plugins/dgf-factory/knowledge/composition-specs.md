---
dgf_version: "1.1.11"
read_date: 2026-09-22
review_date: 2026-09-22
---

# Composition specs — how a consumer application is assembled from DGF

A DGF system is composed, not coded: consumer applications declare their forms, flows,
views and settings in artifacts under a workspace, and wire components together with
events. This file holds the facts about where those artifacts live, what the five legacy
ones are, how components talk to each other, and — as a **policy** fact carrying
`review_date` — which format a generator must emit today.

§1–§3 are structural. §4 is policy.

## 1. Workspace layout — where artifacts live

From DGF's `WorkspaceSettings` class. Every workspace has an `FM` directory
(`WorkspaceSettings.Fm`), and the artifact directories sit under it as constants:

| Constant | Value | Holds |
|---|---|---|
| `Fm` | `FM` | The root for everything below |
| `Process` | `_PROCESS` | `_process.xml` state-machine definitions |
| `Workflow` | `_WORKFLOW` | `_workflow.xml` sequences |
| `Components` | `_COMPONENTS` | Component configuration |
| `Lookup` | `_LOOKUP` | Lookup definitions |
| `Data` | `_DATA` | Data table definitions |
| `Profile` | `_PROFILE` | Profile tree definitions |
| `DataSources` | `_DataSources` | DataSource definitions — note the mixed case |
| `SiteMaps` | `_SiteMaps` | Site maps — mixed case |
| `Endpoints` | `_EndPoints` | Endpoint definitions — mixed case |
| `StoragePath` | `_STORAGE` | Workspace storage |
| `Services` | `Services` | No underscore |

Resolved paths: `FmPath = <WorkspaceRootPath>/FM`, and each artifact path is
`Path.Combine(FmPath, <constant>)`.

### 1.1 The base workspace

`BaseWorkspaceName = "webasm"`. `FmBasePath = <WorkspacesRootPath>/webasm/FM` resolves in
the **base** workspace, where `FmPath` resolves in the **selected** one.

Two artifact paths have explicit base variants in the source:

- `BaseWorkflowPath = Path.Combine(FmBasePath, Workflow)`
- `ProfileBasePath = Path.Combine(FmBasePath, Profile)`

So a workflow or profile placed in `webasm` is reachable from every application that
inherits from it. This file states only what the source shows; whether other artifact
kinds inherit the same way is not asserted here.

## 2. The five legacy artifacts — XML-only, no JSON equivalent

From DGF's format-coverage page, §"Legacy XML-only artifacts"
(`get_doc_page('AI-Authoring/format-coverage.md')`). *"These five artifact types have no
JSON equivalent today. The runtime reads only XML."*

| Artifact | Grammar | Status (verbatim) |
|---|---|---|
| `_form.xml` | `form.xsd` | XML-only (Form JSON parity is partial) |
| `_workflow.xml` | `workflow.xsd` | XML-only. Largest remaining migration. |
| `_process.xml` | `process.xsd` | XML-only. |
| `settings.xml` | `settings.xsd` | XML-only. Entity field declarations. |
| `view.xml` (3 subtypes) | `table-view.xsd`, `lookup-view.xsd`, `grid-form.xsd` | XML-only |

`options.xsd` and `profile.xsd` exist but are **outside Wave-1 validator scope** — legacy
`<options>` lists and profile tree definitions respectively.

Note the asymmetry with `schema-families.md` §6: `Workflow` and `ProcessFlow` *do* have
generated JSON schemas (`WorkflowConfiguration`, `ProcessFlowConfiguration`), yet the
runtime reads `_workflow.xml` and `_process.xml` exclusively. A schema existing is not the
runtime reading it.

## 3. Wiring components together — events and the DataFetcher

Two hand-authored standalone contracts, which DGF keeps apart from its generated schema set,
define the composition mechanism. Both are draft-07 and vendored under `schemas/standalone/`.

### 3.1 `EventBase` — one event handler entry

*"A single event handler entry in a component's `events.onValueChange` array. Targets a
component and applies an action verb, optionally gated by a `when` expression."*

Required: `action`. Optional: `componentName`, `valueExpression`, `when`, `message`,
`severity`, `propertyName`, `parameters`.

The **14 action verbs**, verbatim from the schema's `enum`:

`data` · `validate` · `schema` · `schemaAndData` · `save` · `saveAndClose` · `setValue` ·
`clearValue` · `setReadonly` · `setRequired` · `toggleVisible` · `notify` · `setProperty` ·
`abortSubmit`

A validator rejects any other verb. Do not infer verbs from component names or from other
frameworks' event vocabularies.

### 3.2 `DataFetcherConfiguration` — the headless dispatcher

*"Headless DGF component that fires a `dataSource` reactively and dispatches
`onValueChange` events to mutate other components."*

Required: `type`, `name`. Notable optional properties: `dataSource`, `dataSourcePath`,
`debounceMs`, `manualTrigger`, `silentOnError`, `parameters`, `events`, `hidden`,
`metaData`.

`DataFetcher` is one of the 34 dispatchable components in `component-catalogue.md`, so it
has a runtime service; its contract is a hand-authored standalone
file, not part of the generated set, and it is **not** synced into the MCP.

## 4. Current generation policy — XML for all five, regardless of parity

*Policy fact. Source: `format-coverage.md`, hand-maintained, `last_updated: 2026-09-09`.
Changes by decision, not by release. Re-read on every re-vendor and update `review_date`.*

Verbatim: **"Wave 1 policy: AI generates XML for all five legacy artifact types, regardless
of partial JSON parity above."**

The stated reasons: runtime support is partial and mixed-format services would fail in
production; downstream tooling expects XML on disk; and JSON-form generation has
correctness gaps until `build_form_xml` ships.

So a generator targeting a form, workflow, process, settings or view artifact **emits XML**
today — even for `Form`, whose runtime does parse JSON (`◐`). A JSON `Form` config that
validates is not wrong, but it is not what this policy says to produce.

## See Also

- [`README.md`](README.md) — the stamping convention this file follows
- [`schema-families.md`](schema-families.md) — the parity table this policy overrides
- [`naming-conventions.md`](naming-conventions.md) — the file and folder names above, as rules
- [`component-catalogue.md`](component-catalogue.md) — `DataFetcher` among the 34
