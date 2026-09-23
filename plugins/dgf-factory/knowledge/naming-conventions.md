---
dgf_version: "1.1.11"
read_date: 2026-09-22
---

# Naming conventions — the names DGF expects, as rules a generator must honour

Structural facts: stamp only. Deliberately short — only rules read directly from DGF
source; the files read are in the maintainer provenance ledger for this file. Nothing here is
inferred from how a name *looks*.

## 1. Workspace directories

Under `<workspace>/FM/`, from DGF's `WorkspaceSettings` class. The casing is **not** uniform, and a
generator must reproduce each constant exactly:

| Kind | Exact name |
|---|---|
| All-caps with leading underscore | `_PROCESS` `_WORKFLOW` `_COMPONENTS` `_LOOKUP` `_DATA` `_PROFILE` `_STORAGE` |
| Mixed case with leading underscore | `_DataSources` `_SiteMaps` `_EndPoints` |
| No underscore | `Services`, and the root `FM` itself |

Do not normalise these to one casing. `_DATASOURCES` and `_datasources` are not the
DataSources directory; `_DataSources` is.

The base workspace is named `webasm` (`BaseWorkspaceName`).

## 2. Legacy artifact filenames

From `format-coverage.md` §"Legacy XML-only artifacts":

| Artifact | Filename | Note |
|---|---|---|
| Form | `_form.xml` | Leading underscore |
| Workflow | `_workflow.xml` | Leading underscore |
| Process | `_process.xml` | Leading underscore |
| Settings | `settings.xml` | **No** underscore |
| View | `view.xml` | **No** underscore; three grammar subtypes share the name |

Three of the five carry a leading underscore and two do not. A generator that emits
`_settings.xml` or `form.xml` has produced a file the runtime will not find.

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
