---
dgf_version: "1.1.11"
read_date: 2026-09-25
review_date: 2026-09-22
---

# Composition specs — how a consumer application is assembled from DGF

A DGF system is composed, not coded: consumer applications declare their forms, flows,
views and settings in artifacts under a workspace, and wire components together with
events. This file holds the facts about where those artifacts live, what the five legacy
ones are, how components talk to each other, how a workspace's own script and style reach
the UI, and — as a **policy** fact carrying `review_date` — which format a generator must
emit today.

§1–§3 and §5 are structural. §4 is policy.

## 1. Workspace layout — where artifacts live

From DGF's `WorkspaceSettings` class. Every workspace has an `FM` directory
(`WorkspaceSettings.Fm`), and the artifact directories sit under it as constants:

| Constant | Value | Holds |
|---|---|---|
| `Fm` | `FM` | The root for everything below |
| `Process` | `_PROCESS` | `process.xml` state-machine definitions, one folder per process |
| `Workflow` | `_WORKFLOW` | `_workflow.xml` sequences, one folder per workflow |
| `Components` | `_COMPONENTS` | Component configuration, DataSources, endpoints and site maps |
| `Lookup` | `_LOOKUP` | Lookup definitions |
| `Data` | `_DATA` | Data table definitions |
| `Profile` | `_PROFILE` | Profile tree definitions |
| `Services` | `Services` | No underscore |

Resolved paths: `FmPath = <WorkspaceRootPath>/FM`, and each path above is
`Path.Combine(FmPath, <constant>)`.

**One constant sits outside `FM`.** `StoragePath = "_STORAGE"` is joined to the workspace root,
not to `FM`: `WorkspaceStoragePath = Path.Combine(WorkspaceRootPath, StoragePath)`.

**Three constants are declared and used by nothing.** `DataSources = "_DataSources"`,
`SiteMaps = "_SiteMaps"` and `Endpoints = "_EndPoints"` exist in `WorkspaceSettings`, but no code
builds a path from them. DataSources are read from `_COMPONENTS/DataSource/` (`DataSourceLoader`),
endpoints from `_COMPONENTS/Endpoints/` (`EndpointFactory`), and site maps from `_COMPONENTS/`
itself (`ComponentFileLoadService`).

### 1.1 The base workspace

`BaseWorkspaceName = "webasm"`. `FmBasePath = <WorkspacesRootPath>/webasm/FM` resolves in
the **base** workspace, where `FmPath` resolves in the **selected** one.

Five artifact paths have explicit base variants in the source:

- `BaseWorkflowPath = Path.Combine(FmBasePath, Workflow)`
- `ProcessBasePath = Path.Combine(FmBasePath, Process)`
- `DataBasePath = Path.Combine(FmBasePath, Data)`
- `ComponentsBasePath = Path.Combine(FmBasePath, Components)`
- `ProfileBasePath = Path.Combine(FmBasePath, Profile)`

So an artifact of these kinds placed in `webasm` is reachable from every application that
inherits from it, when it is referenced with a `BASE:` prefix. This file states only what the
source shows; `_LOOKUP` and `Services` have no base variant.

### 1.2 What sits beside the workspaces

The workspaces root is the directory `WorkspaceSettings` reads from the
`DGF_WORKSPACES_ROOT_PATH` environment variable, or else from the `WorkspacesRootPath`
setting; its constructor throws when neither is set. A workspace is a directory under that
root, selected by the `WorkspaceName` setting (default `default`), and every artifact path
above is built under its `FM` directory.

**`applibs*` folders are not workspaces.** DGF's sample workspaces root also holds five
`applibs*` folders (`applibs`, `applibs-ecouncils`, `applibs-lm`, `applibs-zims`,
`applibs-zma`). DGF's workspaces readme describes them as "plugin assemblies
(`CustomAssembliesPath`), per consumer": the folder that `ApplicationConfig.CustomAssembliesPath`
names, which `AssemblyLoader` reads through the `ApplicationConfig:CustomAssembliesPath`
setting. Every one of them holds only `.dll` files, and none has an `FM` directory.
`WorkspaceSettings` never names them, so no workspace path resolves into one.

**The base workspace need not come from the same repository.** A deployment mounts each
workspace into the root on its own. DGF's sample deployment for ZIMS mounts the `zims`
workspace from the ZIMS repository and `webasm` from a different repository; the sample for
eCouncil mounts both from the application's repository. So the repository that holds an
estate's workspaces may not contain `webasm`, and a `BASE:` reference cannot be resolved
from that repository alone.

## 2. The five legacy artifacts — XML-only, no JSON equivalent

From DGF's format-coverage page, §"Legacy XML-only artifacts"
(`get_doc_page('AI-Authoring/format-coverage.md')`). *"These five artifact types have no
JSON equivalent today. The runtime reads only XML."*

| Artifact | Grammar | Status (verbatim) |
|---|---|---|
| `_form.xml` | `form.xsd` | XML-only (Form JSON parity is partial) |
| `_workflow.xml` | `workflow.xsd` | XML-only. Largest remaining migration. |
| `process.xml` | `process.xsd` | XML-only. |
| `settings.xml` | `settings.xsd` | XML-only. Entity field declarations. |
| `_view.xml` and `_grid.xml` (3 subtypes) | `table-view.xsd`, `lookup-view.xsd`, `grid-form.xsd` | XML-only |

The Artifact column gives each filename as the runtime loader opens it. The format-coverage page
itself writes `_process.xml` and `view.xml`; the loaders open `process.xml`, `_view.xml` and
`_grid.xml`, and the loader wins (`naming-conventions.md` §2).

`options.xsd` and `profile.xsd` exist but are **outside Wave-1 validator scope** — legacy
`<options>` lists and profile tree definitions respectively.

### 2.1 Where each legacy grammar's file lives

One row per grammar file. Folders are relative to the workspace root; the three view grammars
share the root element `view` and are told apart only by the folder their file sits in.

<!-- machine-read: legacy-artifacts -->
| Artifact | Filename | Folder | Grammar |
|---|---|---|---|
| `process` | `process.xml` | `FM/_PROCESS/<process>/` | `process.xsd` |
| `workflow` | `_workflow.xml` | `FM/_WORKFLOW/<workflow>/` | `workflow.xsd` |
| `form` | `_form.xml` | `FM/_DATA/<table>/_forms/<form>/` | `form.xsd` |
| `settings` | `settings.xml` | `FM/_DATA/<table>/` | `settings.xsd` |
| `table-view` | `_view.xml` | `FM/_DATA/<table>/_views/<view>/` | `table-view.xsd` |
| `lookup-view` | `_view.xml` | `FM/_DATA/<table>/_lookupviews/<view>/` | `lookup-view.xsd` |
| `grid-form` | `_grid.xml` | `FM/_DATA/<table>/_gridforms/<grid>/` | `grid-form.xsd` |
| `options` | `_options.xml` | `FM/_DATA/<table>/` | `options.xsd` |

A workflow may also be process-local, at `FM/_PROCESS/<process>/<workflow>/_workflow.xml`. A form
name may contain `/`, so a `_form.xml` can sit more than one folder below `_forms/`. `profile.xsd`
has no row: it declares attributes named `xmlns:xsi` and `xmlns:xsd`, which are not valid XSD
names, so it does not compile, and no loader for its files was read.

Note the asymmetry with `schema-families.md` §6: `Workflow` and `ProcessFlow` *do* have
generated JSON schemas (`WorkflowConfiguration`, `ProcessFlowConfiguration`), yet the
runtime reads `_workflow.xml` and `process.xml` exclusively. A schema existing is not the
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

## 5. Custom script and style delivery

Structural, like §1–§3. Where a workspace's own JavaScript and CSS are read from, and which
of those files the UI loads.

**A form's own script.** `FormManager.GetFormScriptContent` reads `_form.js` from the form's
own folder, beside its `_form.xml`, when the form names no `scriptPath`. When it names one, it
reads that path joined to the workspace root instead. Nothing else has to change for a new
`_form.js` to be read.

**The UI shell loads exactly three custom files.** At start-up the Angular shell's app
component (`setUpCustomFiles`) adds `assets/js/formhelper.js`, `assets/js/formshared.js` and
`assets/styles/custom.css` to the page. The shell's build ships its own default copy of each
under its `assets` folder, and its build configuration copies nothing from a workspace.

**A deployment replaces those defaults with a bind-mount.** DGF's sample deployment
configurations mount a workspace file over each shell path: an application workspace's
`js/formhelper.js` and `js/forms.shared.js`, or the base workspace's `FM/js/formhelper.js`,
onto the two script paths, and a `custom.css` kept outside the workspaces root onto the style
path (commented out in one of the two samples). The mapping lives in the deployment's own
configuration, outside the workspaces root, and names one file per shell path.

So a file under a workspace's `js/`, `FM/js/` or `css/` reaches the UI only when a
deployment mounts it. Editing a mounted file changes what the UI loads. A **new** file there is
loaded by nothing until a deployment is changed to mount it, and that change is outside the
workspaces root.

**Static mounts are for linked content, not for these files.** The API also serves the
selected workspace's root at `/application` and the base workspace's root at `/webasm` as
static files, for content a form links to. The shell's three files are not read from them.

<!-- machine-read: code-places -->
| Place | Path | Filename | Extension | Loaded by | New file loaded |
|---|---|---|---|---|---|
| `form-script` | `FM/_DATA/<table>/_forms/<form>/` | `_form.js` | `.js` | read by `FormManager.GetFormScriptContent` beside the form's `_form.xml` | yes |
| `global-script` | `js/` | — | `.js` | a deployment bind-mount onto the shell's `assets/js/formhelper.js` or `assets/js/formshared.js` | no |
| `global-script-base` | `FM/js/` | — | `.js` | the same bind-mount; DGF's samples keep the base workspace's `formhelper.js` here | no |
| `global-style` | `css/` | — | `.css` | a deployment bind-mount onto the shell's `assets/styles/custom.css` | no |

- **Path** is relative to the workspace. A `<name>` placeholder stands for exactly one path
  segment, except a placeholder that ends the path, which stands for one or more: a form name
  may contain `/` (§2.1), and its `_form.js` sits beside its `_form.xml`.
- **Filename** is the one file name the place holds, or `—` for any file with the row's
  extension at any depth below the path.
- **New file loaded** says whether a file that does not exist yet is read once it is written,
  with no change outside the workspaces root.

## See Also

- [`README.md`](README.md) — the stamping convention this file follows
- [`schema-families.md`](schema-families.md) — the parity table this policy overrides
- [`naming-conventions.md`](naming-conventions.md) — the file and folder names above, as rules
- [`component-catalogue.md`](component-catalogue.md) — `DataFetcher` among the 34
