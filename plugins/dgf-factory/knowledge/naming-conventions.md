---
dgf_version: "1.1.11"
read_date: 2026-09-24
---

# Naming conventions — the names DGF expects, as rules a generator must honour

Structural facts: stamp only. Deliberately short — only rules read directly from DGF
source; the files read are in the maintainer provenance ledger for this file. Nothing here is
inferred from how a name *looks*.

## 1. Workspace directories

From DGF's `WorkspaceSettings` class. The casing is **not** uniform, and a generator must
reproduce each name exactly:

| Where | Exact name |
|---|---|
| Under `<workspace>/FM/` | `_PROCESS` `_WORKFLOW` `_COMPONENTS` `_LOOKUP` `_DATA` `_PROFILE` `Services` |
| Directly under `<workspace>/`, **not** under `FM/` | `FM` itself, and `_STORAGE` (`WorkspaceStoragePath` joins it to the workspace root) |

Do not normalise these to one casing. On Linux, where DGF runs, `_Workflow` is not the workflow
directory; `_WORKFLOW` is.

**Three constants are declared but used by nothing the engine runs.** `WorkspaceSettings` also
declares `DataSources = "_DataSources"`, `SiteMaps = "_SiteMaps"` and `Endpoints = "_EndPoints"`,
and no code reads a path built from them. They are **not** directories a generator should create.
DataSources load from `_COMPONENTS/DataSource/` (`DataSourceLoader`), endpoints from
`_COMPONENTS/Endpoints/` (`EndpointFactory`), and site maps from `_COMPONENTS/` itself.

The base workspace is named `webasm` (`BaseWorkspaceName`).

## 2. Legacy artifact filenames

Each filename as the runtime loader opens it — the loader named in the last column builds the
path, and nothing else is looked for:

| Artifact | Filename | Folder, under `<workspace>/FM/` | Loader |
|---|---|---|---|
| Process | `process.xml` | `_PROCESS/<process>/` | `ProcessManager` |
| Workflow | `_workflow.xml` | `_WORKFLOW/<workflow>/`, or `_PROCESS/<process>/<workflow>/` for a process-local workflow | `WorkflowManager` |
| Form | `_form.xml` | `_DATA/<table>/_forms/<form>/` | `FormManager` |
| Settings | `settings.xml` | `_DATA/<table>/` | `TableManager` |
| Table view | `_view.xml` | `_DATA/<table>/_views/<view>/` | `ViewManager` |
| Lookup view | `_view.xml` | `_DATA/<table>/_lookupviews/<view>/` | `LookUpViewManager` |
| Grid form | `_grid.xml` | `_DATA/<table>/_gridforms/<grid>/` | `EditableGridManager` |
| Options | `_options.xml` | `_DATA/<table>/` | `StaticOptionReader` |

Two of them carry **no** leading underscore — `process.xml` and `settings.xml` — and the rest do.
The two view subtypes share the filename `_view.xml`; the folder above it (`_views` or
`_lookupviews`) is what tells them apart. A generator that emits `_process.xml`, `_settings.xml`,
`view.xml` or `form.xml` has produced a file the runtime will not find.

DGF's own format-coverage page (`get_doc_page('AI-Authoring/format-coverage.md')`) labels two of
these `_process.xml` and `view.xml`. The loaders open `process.xml` and `_view.xml`, and the
loader wins.

## 3. Component type names

The `type` value in a component configuration is a `ComponentType` enum member name,
**PascalCase, exact** — `ComboBox`, `DataFetcher`, `EligibilityCriteria`, `PowerBi`,
`SignaturePadSig100`. The full set of 67 is in `component-catalogue.md`; a name outside it
is not a component.

Case matters in the *authoring* surface even where DGF's own lookups are lenient:
`SchemaIndexService` lowercases its index key, so `combobox` resolves a schema — but the
runtime's `ComponentType` is an enum, and `nameof(ComponentType.ComboBox)` is the registered
key. Emit the enum spelling.

## 4. Generated JSON schema filenames

From the MCP's `SchemaIndexService`: a component's schema is `<ComponentType>Configuration.schema.json`,
and the index key is that filename with the `Configuration.schema.json` suffix stripped.
The one allow-listed exception is `componentValidator.schema.json`, which has no
`Configuration` infix because it is a cross-cutting contract, not a per-component config.

One generated filename is shell-hazardous: ``NumberConfiguration`1.schema.json`` contains a
backtick. Quote every schema path in every script.

## 5. Custom form cells

From `format-coverage.md`, `Form` row: custom cells follow the **`control_xxx`** pattern.
The row records them as one of the reasons the JSON-form path lacks parity with `_form.xml`.
This file records the pattern's existence and prefix only; the full grammar is in
`schemas/xsd/form.reference.json` and `form.xsd`.

## Not in this file

Anything inferred rather than read. `_LOOKUP` presumably holds `*.xml` lookups and
`_DATA` presumably holds table definitions, but no source read for this milestone states
the *file* naming inside those directories, so it is not asserted.

## See Also

- [`README.md`](README.md) — the stamping convention this file follows
- [`composition-specs.md`](composition-specs.md) — what lives in each directory named above
- [`component-catalogue.md`](component-catalogue.md) — the 67 type names
