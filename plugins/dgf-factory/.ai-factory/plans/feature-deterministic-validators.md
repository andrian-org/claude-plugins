# Implementation Plan: Deterministic Validators

Branch: feature/deterministic-validators
Created: 2026-09-24
Refined: 2026-09-24 — `/aif-improve`: Phase 1 reordered (ADR 0011 accepted last); AGENTS.md relinked in Phase 1;
bytecode skipped by the doctor; `.venv` pruned from the docs check; one import scheme; XML parsed from bytes (E21);
position-preserving comment stripping; ADR 0007's libxml2 claim corrected (E18); knowledge-purity rule for Phase 2
Base: `develop` at `8936808`. `config.yaml` names `main` as `git.base_branch`, but `main` (`0e28010`) is 30
commits behind `develop` and lacks milestones 6–7 (manifest, doctor, knowledge base, ADRs 0006–0013), which this
plan builds on. The branch is cut from `develop` and merges back into it.

## Original Request

[ ] **Deterministic Validators** — Python validators under `scripts/` on `lxml` + `jsonschema`, pinned in `scripts/requirements.txt`, with a missing dependency reported as exit `3`. They resolve the schema family before parsing, resolve components, and check runtime parity against the shipped parity table in `knowledge/schema-families.md` §6 before reporting success; extend that table to every `format-coverage.md` row first, and script ADR 0010's order-of-means route from it. Also: the NJsonSchema inheritance pre-pass; ADR 0006's process checks (XSD structure with a runtime-divergence allowance, dead transition exempting `End`, unreachable state as a warning, and workflow-reference, validation-flow and change-state target resolution); known-good (DGF samples) and known-bad fixture corpora, which pass the doctor's `DGF_PATH` check or live outside the shipped directories; and the drift check, a maintainer tool in `tools/` that compares the `provenance/` ledgers against a DGF checkout. Accept ADR 0011 and correct `knowledge/naming-conventions.md` before the parity check lands ([ADR 0006](../docs/adr/0006-process-verification-revised.md), [ADR 0007](../docs/adr/0007-validator-runtime.md), [ADR 0010](../docs/adr/0010-dgf-implement-scope.md), [ADR 0012](../docs/adr/0012-no-dgf-paths-in-shipped-files.md), [ADR 0013](../docs/adr/0013-version-gating-provenance-ledger.md))

## Settings

- **Testing: yes.** The known-good and known-bad corpora the milestone requires, **plus** a stdlib `unittest` suite
  under `tests/`, run from the plugin root with `python3 -m unittest discover -s tests -t .`. The NJsonSchema
  pre-pass fixtures are written and passing **before** any other JSON check (ADR 0007 §4, carried into ADR 0015).
- **Logging: verbose.** No logging framework (`.ai-factory/rules/base.md` §Logging). Every validator and tool accepts
  `--verbose`, and also honours `DEBUG=1`, the convention `doctor.py` already uses. Verbose output is
  `DEBUG [<module>.<function>] <message> key=value …` on **stderr**. Report lines go to **stdout**. Usage errors go
  through the single `fail(code, message)` path to stderr.
- **Docs: yes.** A mandatory documentation checkpoint at completion, run through `/aif-docs` (Task 21).
- **Known-good corpus: runs against a DGF checkout.** A maintainer tool in `tools/` runs the validators over
  `<dgf>/src/samples/workspaces`. No DGF sample is vendored into this plugin.
- **Decisions taken while planning** (Andrian Mamei, 2026-09-24; recorded as accepted ADRs in Phase 1):
  - **D1: an unknown JSON property is a warning** (exit `2`, "ignored by the runtime"), not a block. It supersedes
    ADR 0007 §4's "rejected" (→ ADR 0015).
  - **D2: a `webasm` process's `WORKFLOW:/X` reference is app-dependent.** It is resolved against every application
    workspace under the root and reported as a warning naming the apps that lack `X`. It never blocks (→ ADR 0014).
  - **D3: XSD failures in the non-process legacy grammars are warnings for now.** For workflow, form, settings, the
    three view grammars and options, a failure is exit-`2` `XSD_LAGS_RUNTIME`. Only `process.xsd` gets a divergence
    list in this milestone; a list per grammar is a follow-up (→ ADR 0016).
  - **D4: ADRs 0014, 0015 and 0016 are written as `accepted`**, with D1–D3 as their decisions. No validator code is
    written until they land in Commit 1.
- **Scope.** Validators, their knowledge prerequisites, the fixture corpora, the drift check, the doctor's
  dependency probe, and propagation to documentation. **Out of scope:** the `dgf-gate-result` block and
  `checks_run` field (milestone 10 — validators print a `CHECKS RUN` line so milestone 10 can wire it), any
  `dgf-*` skill other than `/dgf-doctor`, and the developer-facing version gate (ADR 0013 §4, first table).

## Roadmap Linkage

Milestone: "Deterministic Validators"
Rationale: This plan implements the milestone as written. It also records the three decisions the milestone's
inputs turned out to need, once they were measured against DGF's own samples (E12–E14).

## Task Ledger Note

`TaskCreate` / `TaskUpdate` are not available in this session. The checkbox list under `## Tasks` is the
**single** progress ledger. `/aif-implement` updates the checkboxes here and nowhere else.

## Evidence Base

Read on 2026-09-23/24 from the DGF repository at `aa1d5c4c2` (`develop`). DGF paths are relative to its root. This is
maintainer material, so it cites DGF paths. **Shipped files never do** (ADR 0012): they cite the knowledge file that
carries the fact. Implementers cite from here, re-read before citing, and do not re-derive.

### JSON family

| # | Finding | Source |
|---|---|---|
| E1 | `format-coverage.md` (`last_updated: 2026-09-09`) has **67 rows** in its modern-JSON table. Rows use their **own names**, not `ComponentType` names: `DatePicker`, `DateTimePicker`, `TimePicker`, `TextArea`, `PayComponent`, `SiteMap`, `ProcessMonitor`, plus six DataSource rows (`ApiDataSource` … `TableDataSource`). The `Accordion` row is struck through ("Deprecated — no `IComponentConfiguration` schema exists"). ✗ rows: ProcessFlow, Workflow. ◐ rows: Booking, CorporateAccount, EligibilityCriteria, Form, PayComponent, Query, Uploader. The legacy table has 5 rows. | `docs/wiki/AI-Authoring/format-coverage.md` L25-93, L95, L105-113 |
| E2 | The runtime reads component JSON with **System.Text.Json**, using one options object: `PropertyNameCaseInsensitive = true`, `ReadCommentHandling = Skip`, `JsonStringEnumConverter(CamelCase)` (enum names parse case-insensitively), and the converters `NullableDateOnly`, `NullableTimeOnly`, `DataSource`, `Dictionary`, `DateOnly`, `Component`, `ObjectParameters`, `ComponentModel`, `AbstractStep`, `TimeOnly` and **`Boolean`**. `AllowTrailingCommas` and `NumberHandling` are not set. `UnmappedMemberHandling` is not set, so the default `Skip` applies and **unknown properties are silently ignored**. | `src/DGF.API/ConfigureServices.cs:238-258`; `src/Core/DGF.Kernel/Utils/Serialization/JsonSerializationService.cs:22,63-68` |
| E3 | `ComponentConverter` reads `type`, parses it with `Enum.TryParse(ComponentType, ignoreCase: true)`, and **returns `null` for an unknown value**: the component silently vanishes. It then selects the first reflected class whose name equals `<Type>` or `<Type>Configuration` (ignoring case), and failing that, the first class whose name *starts with* `<Type>`. So `Date` → `DatePickerConfiguration`, `Time` → `TimePicker…`, `DateTime` → `DateTimePicker…`, `Textarea` → `TextAreaConfiguration`, `Pay` → `PayComponentConfiguration`, and `ProcessMonitor` → `ProcessMonitorComponentConfiguration`. **The prefix match is order-dependent:** `Date` could also match `DateTimePickerConfiguration`. `HeaderConfiguration`'s constructor binds `ComponentType.Footer` (an upstream bug). No config class exists for `Search`, `RadioButton`, `WorkflowNew`, `DropdownTree`, `Option`, `Internal` or `Template`. | `src/Components/DGF.Components.Services/JsonConverters/ComponentConverter.cs:22-42`; `ComponentAssignableTypesCache.cs`; `…/DGF.Sitemap/Models/Configuration/HeaderConfiguration.cs:11` |
| E4 | `DataSourceConverter` dispatches on `type`, parsed case-insensitively. It has **9 discriminators and 6 classes**: `Table`/`LookupTable`/`EditableGrid` → `TableDataSource`, `Api` → `ApiDataSource`, `Static` → `StaticOptionsDataSource`, `Document` → `DocumentDataSource`, `StoredProcedure`/`RawSql` → `RawSqlDataSource`, and `Code` → `CodeDataSource`. An unknown value **throws** `JsonException`. `_COMPONENTS/DataSource/<name>.json` is deserialized straight to `IDataSource`. The MCP never indexes the DataSource schemas: `validate_component_config("ApiDataSource")` returns "Schema not found". | `src/Core/DGF.DataSources/JsonConverters/DataSourceConverter.cs:62-105`; `DataSourceLoader.cs:12-29` |
| E5 | The generated schemas declare **PascalCase** properties (`Type`, `Name`, `Placeholder`) and a PascalCase `ComponentType` enum. Their `Type` description says "lowercase or camelCase will fail validation". That is a hand-written doc comment and false for the runtime (E2, E3). The committed set comes from `ExportWith_NJsonSchema`. The runtime-faithful `ExportWith_SystemTextJson` variant is generated but never synced. Inheritance is `allOf: [{$ref: Base}, {properties, additionalProperties: false}]`, **chained** (e.g. `InputComponentConfigurationBase` → `ComponentConfigurationBase`). Nested children are `items: {$ref: "#/definitions/IComponentConfiguration"}` (a closed interface object, in 24 files) or `$ref: "#/definitions/IDataSource"` (15 files). Across `definitions`, 166 enums are `type: integer` with `x-enumNames`, and 95 are string enums. | `knowledge/schemas/json/` (e.g. `DatePickerConfiguration`, `FormConfiguration`, `PageConfiguration`); `src/Tools/SchemaExporter/Program.cs:37-142`; `ComponentConfigurationBase.cs:18-19` |
| E6 | The samples hold **385** `FM/_COMPONENTS/**/*.json` files. 32 contain `//` or `/* */` comments. 98.3% of `type` values and 99% of keys are lowercase or camelCase. Folders: DataSource (110), Page (87), Form (59), DataTable (44), Template (30), PowerBi (14), Button (14), Endpoints (6), Forms (4, `zims` only), root `sitemap*.json` (5), and 11 smaller folders. **Prototype measurements** (scratch, not committed): MCP mode (strip `additionalProperties: false`) passes 230/230 type-resolvable files. A strict case-sensitive merge passes **0/230**. Case-insensitive names and enums pass 42/230. Adding `IComponentConfiguration`/`IDataSource` dispatch passes **183/344**. The remaining failures are dominated by integer enums whose values are written as names (133), `showHeaders` on DataTables (42, not a `DataTableConfiguration` property), and string-valued booleans or numbers (46). | `src/samples/workspaces/*/FM/_COMPONENTS/` |
| E7 | **Folders with no component schema:** `Template/` holds fragments, each typed by its own `type` (`ComponentFileLoadService.cs:67-71`). `Endpoints/` deserializes to `EndpointSchema`, which has no schema (`EndpointFactory.cs:18-54`). Root `sitemap*.json` → `SiteMapConfiguration`, which has its own loader and no `type` (`ComponentFileLoadService.cs:34-53`; `SiteMapManager.cs:284`). **No loader references `Forms/`** (plural). | as cited |
| E8 | DGF's MCP validator strips `$schema` and every `additionalProperties: false`. It never case-folds the instance, and the caller supplies `componentType`. `{}` validates as a Form. `{"Type":"form"}` fails the enum, and lowercase `type` is invisible. | `src/Tools/dgf-mcp/Services/SchemaValidationService.cs:23-78,147-217`; `Tools/ValidateComponentConfigTool.cs:30-36`; live MCP, 2026-09-24 |

### Process and workflow references

| # | Finding | Source |
|---|---|---|
| E9 | **Workflow path resolution is one deterministic branch per form, with no fallback.** `WorkflowManager.GetWorkPath(name)`: `BASE:X` → `BaseWorkflowPath/X` (webasm); `/X` → `WorkflowPath/X` (the **selected** workspace); `P/X` → `ProcessPath/P/X`; `BASE:P/X` → `ProcessBasePath/P/X`. `LoadWorkflowAsync` appends `_workflow.xml`. Existence is `File.Exists` on the literal path, which is **case-sensitive on Linux**. | `src/Core/DGF.OM/Workflow/WorkflowManager.cs:15-40,58,92-123` |
| E10 | **How a process `@action` becomes a name.** `ResolveUiSettings` splits on `:` and normalises both `WORKFLOW:/BASE:X` and `WORKFLOW:BASE:X` to `BASE:X`. `RenderUiControlAsync` then applies: `BASE:X` → `BASE:X`; `/X` → `/X`; bare `X` → `<processName>/X` (**process-local**), where `processName` is the process as referenced, possibly `BASE:P`. | `src/Core/DGF.DataViewer/Process/StateProcessClient.cs:585-595,836-846` |
| E11 | `Process/@validationFlow` is used verbatim as a workflow name, **without** the process-local prefix. So `BASE:X` → webasm `_WORKFLOW`, and bare `X` → the selected workspace's `_WORKFLOW`. | `StateProcessClient.cs:136-150`; `BackgroundWorkflowService.RunWorkflow` L62-72 |
| E12 | **A process is located** by `ProcessManager.GetWorkPath`: unprefixed `P` → `ProcessPath/P` (selected workspace); `BASE:P` → `ProcessBasePath/P`. There is no fallback. The filename is exactly **`process.xml`**. `process.schema` beside it is designer and monitoring metadata; the engine never reads it. `CHANGE_STATE` resolves its `process` the same way. Its `mode` is compared ordinally with `CHANGE_STATE`. `applyforstates` is `Split(';')` with **no trim**, and each token and `state` are compared ordinally. | `src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs:12-56`; `SequenceWorkflow.cs:515-558`; `StateProcessStepHandler.cs:63,196-198`; `StateProcessClient.cs:937` |
| E13 | **Other process-borne references.** `<ws>/FM/_PROCESS/<P>/<State>.xml` (MultiTask settings) holds `MultiTaskGroup/@action`, `@expiredaction` and `@postviewaction`, which are the same `WORKFLOW:` presentation strings. `OpenHandler` files sit flat under `_PROCESS/<name>.xml`. `Process/@table` → `_DATA/<t>/settings.xml`. | `MultiTaskSettings.cs:25-42`; `MultiTaskGroup.cs:7-17`; `StateProcessClient.cs:868-897`; `OpenHandler.cs:28-39`; `TableManager.cs:16-22` |
| E14 | **ADR 0006's rules run over the 23 samples** (scratch dry run, 2026-09-24). Of 172 `WORKFLOW:` refs, 110 resolve in `_WORKFLOW` of the owning workspace, **18 only process-locally**, **29 are `/X` refs in `webasm` processes that resolve only in `zims`**, and 15 resolve nowhere. Of those 15, 13 are in `webasm` `Process1`–`Process3` (all `/X`) and 2 are `zims/FM/_PROCESS/ZIMS4_InspectionBorder/process.xml:5,20` → `WORKFLOW:/InspectionBorderOrOutSide`, absent from `zims/FM/_WORKFLOW`. ADR 0006 §2 as written therefore blocks 62/172. With `End` exempt and `OnTimeout` included, **dead transitions: 0**. **Unreachable** with the full entry set: 15 states in 15/23 processes. There are 21 `CHANGE_STATE` steps (all `mode="CHANGE_STATE"`). The absent targets are exactly ADR 0006's 8. There is **1 true positive**: `zims/FM/_WORKFLOW/Expert.MoveTaskTo/_workflow.xml:15` moves `BASE:ExpertReview` to `RecordState13`, which `webasm/FM/_PROCESS/ExpertReview/process.xml` does not declare (it declares `RecordState5/6/7/8`, `IfElse6`). | `src/samples/workspaces/` |

### XML family and filenames

| # | Finding | Source |
|---|---|---|
| E15 | **Vendored XSDs against the samples** (`xmllint` 2.9.13, 2026-09-24): process 2/23 fail (`ftitle` ×3; `type="StoredProcedure"` + `<StoredProcedureActivity>`, as ADR 0006). workflow **211/341** (675 errors). The top errors are `Field/@source` (169), unexpected `Next` (108), `Field/@text` (80), `Invoke/@controlInfo` (41), `Case/@source` (32) and `XmlIsland/@control` (31). **`StateProcess` and `ForeachRecord` are not declared at all.** table-view **242/559**, lookup-view 44/333, form 46/785 (the same 46 as DGF's own `Schemas/XSD/xsd-sample-baseline.txt`), and settings 3/429. | `knowledge/schemas/xsd/`; `src/Tools/dgf-mcp/Schemas/XSD/xsd-sample-baseline.txt`, `verify-xsd-coverage.sh` |
| E16 | **Filenames on disk.** Processes are `process.xml` (23; **0** named `_process.xml`). Views are `_view.xml` (893: 559 under `_DATA/<t>/_views/<v>/`, 333 under `_DATA/<t>/_lookupviews/<v>/`; **0** named `view.xml`). Grid forms are `_DATA/<t>/_gridforms/<G>/_grid.xml`. Settings are `_DATA/<t>/settings.xml` (429). Forms are `_DATA/<t>/_forms/<f>/_form.xml` (785). Workflows are `_workflow.xml`. The view subtype is decided by the parent folder in DGF's explorer; DGF's MCP instead takes it from the caller. `format-coverage.md` itself labels them `_process.xml` and `view.xml`. | `src/Core/DGF.Explorer/Providers/XmlTableEntitiesProvider.cs:46,62,78,122-130`; `src/Tools/dgf-mcp/Services/XmlCrossReferenceValidator.cs:285`; `Tools/ValidateXmlTool.cs:57-68` |
| E17 | **`knowledge/naming-conventions.md` is wrong in three places.** §1 lists `_STORAGE` under `FM/`, but `WorkspaceSettings.cs:50` joins it under the **workspace root**. §1 also presents `_DataSources`, `_SiteMaps` and `_EndPoints` as live directories, though nothing under `src/Core` references them (ADR 0005 errata). §2 gives `_process.xml` and `view.xml` (E16). `knowledge/composition-specs.md` §1 repeats the §1 errors ("each artifact path is `Path.Combine(FmPath, <constant>)`"), and `schema-families.md` §6 repeats the §2 filenames. | `src/Core/DGF.Kernel/WorkspaceSettings.cs:12-64`; prior plan follow-up |

### This plugin and its runtime

| # | Finding | Source |
|---|---|---|
| E18 | macOS `/usr/bin/python3` is **3.9.6**, without `lxml` or `jsonschema`. `uv` is installed. **`jsonschema` 4.25.1 and `lxml` 6.1.3 install and import on 3.9.6** (a scratch venv, 2026-09-24). **lxml bundles libxml2 2.14.6** (`etree.LIBXML_VERSION`), not the system `xmllint`'s 2.9.13, so ADR 0007's "same libxml2 engine as `xmllint`" is false. The results agree anyway: 8/9 XSDs compile (`profile.xsd` fails on `xmlns:xsi`), and 211/341 workflows and 2/23 processes fail under lxml exactly as under `xmllint`. | this machine |
| E21 | **Sample XML encodings.** 606 files under `FM/` carry an XML declaration with an encoding (596 `utf-8`, 7 `UTF-8`, 3 `utf-16`), and 379 start with a UTF-8 BOM. `webasm/FM/_DATA/AX_SF_Surveys/_forms/DeclineMessage/_form.xml` is **real UTF-16** (BOM `FF FE`) and parses only from bytes. Every `utf-16`-declared file under `zims/FM/_PROFILE/` is actually UTF-8 and fails to parse ("Blank needed here"). Those are profile files, outside the validated artifact set. Some sample filenames contain spaces. | `src/samples/workspaces/`, lxml 6.1.3 |
| E19 | `doctor.py`: `SHIPPED_DIRS = ("skills", "agents", "commands", "scripts", "knowledge", ".claude-plugin")` (L49). `DGF_PATH_PATTERN` (L75-83) is applied to **every UTF-8-decodable file** under those directories, with no extension filter and **no exemption mechanism**. §6 "Build progress" is INFO only. The gate block deliberately omits `schema_family`. `fail()` is at L95-98. An absent `scripts/` is skipped silently. | `skills/dgf-doctor/scripts/doctor.py` |
| E20 | `tools/check_knowledge_stamps.py` exposes `frontmatter_lines`, `parse_frontmatter`, `read_frontmatter`, `sha256_of`, `knowledge_files`, `SHA256_PATTERN` and `COMMIT_PATTERN`, but it is a script, not a package. `tools/vendor_schemas.py:131-136` loads `doctor.py` with `importlib.util.spec_from_file_location`, the pattern a new tool reuses. The comment on section 7 of `tools/check-dual-schema-docs.sh` names "milestone 8's drift check" as the second caller of the stamps parser. **No test infrastructure, requirements file or `pyproject` exists.** The repo root `.gitignore` does not ignore `.venv/` or `__pycache__/`. | `tools/`; `../../.gitignore` |

## Design Decisions

These are decided here, within the ADRs' latitude, so the executor never re-decides them (ARCHITECTURE.md
principle 7). If the code disagrees with one, stop and report the drift.

**DD1 — Layout.** New shipped files carry no DGF path (E19). Cite a knowledge file or a DGF type name in docstrings.

```text
scripts/                              # SHIPPED — validators skills call
├── requirements.txt                  #   uv-compiled, exact pins + hashes, Python 3.9 (Task 9)
├── validate_config.py                #   dual-family structure + parity gate           (Task 13)
├── resolve_components.py             #   component-type legality, both families        (Task 14)
├── route_means.py                    #   ADR 0010 order of means                        (Task 15)
├── validate_process.py               #   ADR 0014 structure + semantic checks           (Task 17)
└── lib/
    ├── __init__.py
    ├── report.py        # Finding, Report, exit aggregation, verdict line, DEBUG helper, ANSI constants
    ├── deps.py          # import guard: missing lxml/jsonschema → exit 3 with the install command
    ├── knowledge.py     # stdlib loader for machine-read knowledge tables (DD2)
    ├── json_reader.py   # runtime-faithful reader: BOM, comments, strict otherwise (DD5)
    ├── prepass.py       # NJsonSchema allOf merge (ADR 0015)
    ├── json_validate.py # jsonschema validator extended with runtime reader semantics + dispatch
    ├── json_resolve.py  # schema selection: index, component classes, discriminators, folders
    ├── family.py        # family detection (DD8)
    ├── xsd.py           # lxml XSD: grammar selection, process two-pass, lag classification
    ├── parity.py        # parity-table lookup and parity findings
    ├── workspace.py     # workspaces-root model and reference resolvers (ADR 0014)
    └── process_checks.py
knowledge/json-reader.md, knowledge/process-model.md   # new stamped facts (Tasks 6, 8)
provenance/knowledge/json-reader.md, …/process-model.md # their ledgers
tests/                                # NOT SHIPPED
├── helpers.py                        #   temp workspaces-root builder, CLI runner capturing exit code
├── test_*.py
└── fixtures/{unit/…, known-bad/<case>/{workspaces/…, expected.json}}
tools/run_known_good.py, tools/known-good-exceptions.txt, tools/check_drift.py, tools/requirements.in
```

**DD2 — Machine-read knowledge tables.** A script reads a Markdown table only when the line immediately above its
header row is `<!-- machine-read: <table-id> -->`. The HTML comment is invisible when rendered.
`scripts/lib/knowledge.py` (stdlib only) finds the marker, requires the **exact** header cells declared in code
for that id, and strips cell whitespace and one pair of surrounding backticks. It rejects a duplicate key column
and stops at the first non-table line. Any deviation raises `KnowledgeTableError`, which a validator turns into
exit `3` ("knowledge table `<id>` malformed — run /dgf-doctor") and the doctor reports as the error
`KNOWLEDGE_TABLE`. The contract is written into `knowledge/README.md` §7 (Task 5). Table ids: `legacy-artifacts`
(Task 5), `component-classes`, `datasource-discriminators` and `component-folders` (Task 6), `parity` (Task 7),
`process-divergence` (Task 8), and `dispatchable` (Task 14).

**DD3 — Output and exit contract.** Every validator prints, in order:

1. a header line;
2. `FAMILY: json|xsd` for each file;
3. `CHECKS RUN: <ids>`;
4. `NOT RUN: <id> (<reason>)`, repeated;
5. the findings, one per line, as `ERROR|WARN|INFO <CODE> <file>[:<line>] <message>`;
6. a summary block;
7. a final verdict line, `CLEAN|WARNINGS|BLOCKED`.

The exit code is `0`/`1`/`2`/`3` as in `.ai-factory/rules/base.md`: the worst finding across all files, and `3`
wins over everything. No `dgf-gate-result` block (milestone 10). The library functions return a `Report` object,
so tools and tests never parse the text. `format` is annotation-only, and `NOT RUN: json-format (annotation-only,
ADR 0015)` is always printed for the JSON family.

**DD4 — Finding codes** (stable ids; severity fixed here):

| Code | Sev | Code | Sev |
|---|---|---|---|
| `DEPENDENCY_MISSING` | 3 | `XSD_INVALID` (process, not explained by divergence) | 1 |
| `KNOWLEDGE_TABLE` | 3 | `XSD_RUNTIME_DIVERGENCE` (process) | 2 |
| `FAMILY_UNRESOLVED` | 3 | `XSD_LAGS_RUNTIME` (all other grammars, D3) | 2 |
| `SCHEMA_UNSELECTABLE` (no `type`, no folder rule, no override) | 3 | `XSD_NOT_COMPILABLE` (`profile.xsd`) | 2 |
| `XML_MALFORMED` | 1 | `UNKNOWN_COMPONENT` (`type` not a `ComponentType` member / not in form.xsd enumeration) | 1 |
| `SCHEMA_INVALID` | 1 | `NO_CONFIG_CLASS` (legal type, no configuration class; checked against the interface only) | 2 |
| `UNKNOWN_DISCRIMINATOR` (DataSource) | 1 | `NO_SERVICE` (legal, not among the 34) | INFO |
| `UNKNOWN_PROPERTY` (D1) | 2 | `DEAD_TRANSITION` | 1 |
| `NO_SCHEMA` (Endpoints, sitemap, unreachable folder) | 2 | `UNREACHABLE_STATE` | 2 |
| `TYPE_FOLDER_MISMATCH` | 2 | `WORKFLOW_UNRESOLVED` | 1 |
| `PARITY_NOT_RUNTIME` (✗) | 2 | `WORKFLOW_APP_DEPENDENT` (D2) | 2 |
| `PARITY_PARTIAL` (◐) | 2 | `CASE_ONLY_MATCH` (resolves only on a case-insensitive filesystem) | 2 |
| `ROUTE_NO_ROW` | 3 | `VALIDATION_FLOW_UNRESOLVED` | 1 |
| `CHANGE_STATE_PROCESS_UNRESOLVED` | 1 | `CHANGE_STATE_STATE_UNDECLARED` | 1 |

**DD5 — JSON reader semantics** (ADR 0015, facts in `knowledge/json-reader.md`):

- **Parse like the runtime (E2).** Strip one UTF-8 BOM, then remove `//` and `/* */` comments with a string-aware
  scanner that never touches a quote-delimited string. Everything else is strict JSON: a trailing comma is a parse
  failure, because `AllowTrailingCommas` is unset.
- **Names and enums are case-insensitive.** Compare property names case-insensitively in `properties`, `required`
  and `additionalProperties`. Two instance keys that differ only in case are a `SCHEMA_INVALID` error, because the
  runtime binds one of them unpredictably. String enums compare case-insensitively. An integer enum with
  `x-enumNames` accepts its integers, **or** one of its names case-insensitively (`JsonStringEnumConverter`).
- **Other converters.** Accept booleans, numbers and dictionaries **exactly as the registered converters do**
  (`BooleanConverter`, `DictionaryJsonConverter`, `ObjectParametersConverter`, …). Task 6 reads each one and
  records its read behaviour in `json-reader.md` §1. Anything a converter does not accept is `SCHEMA_INVALID`.
- **Dispatch polymorphic children by `type`** (E3, E4). A `$ref` to `#/definitions/IComponentConfiguration` is
  validated against the concrete class from `component-classes`. A `$ref` to `#/definitions/IDataSource` goes to
  `datasource-discriminators`. An unknown component `type` is `UNKNOWN_COMPONENT` (the runtime drops it; the
  catalogue says block). A legal type with no class is `NO_CONFIG_CLASS`, checked against the interface definition
  only. An unknown discriminator is `UNKNOWN_DISCRIMINATOR`.
- **Unknown properties and `required`.** An unknown property is `UNKNOWN_PROPERTY` (warning), reported once per JSON
  path. `required` is enforced as the union from the pre-pass (error).

**DD6 — Schema selection for a JSON file.** Under `FM/_COMPONENTS/`, the `component-folders` table decides:

- `DataSource/` → by discriminator;
- `Template/` → by the fragment's own `type`;
- `Endpoints/` and root `sitemap*.json` → `NO_SCHEMA`;
- a `<Type>/` folder → by the `type` value, with `TYPE_FOLDER_MISMATCH` if the value and the folder disagree;
- any folder no loader reads (e.g. `Forms/`) → `NO_SCHEMA`, naming the reason.

Outside `_COMPONENTS`, the `type` value decides. `--component-type <T>` overrides both. With nothing to go on, the
result is `SCHEMA_UNSELECTABLE` (exit `3`).

**DD7 — Parity gate.** The gate applies to a JSON document's **top-level** component type, read from `parity`:
✗ → `PARITY_NOT_RUNTIME`, ◐ → `PARITY_PARTIAL`, naming the row's XML-only part. Nested types are resolved for
legality but not parity-gated, because a row describes the file the runtime loads. A type with no `parity` row is
reported `INFO` as "no parity row". Only `route_means.py` exits `3` on a missing row. XML artifacts are what the
runtime reads, so they raise no parity finding.

**DD8 — Family detection.** Read every file as **bytes**, and sniff a BOM on the raw bytes: UTF-8 `EF BB BF`,
UTF-16 LE `FF FE`, UTF-16 BE `FE FF`. Decode only a short prefix, and only for sniffing (E21).

- **XSD family:** the sniffed prefix begins with `<?xml`, or lxml parses the **original bytes** and the root is a
  known root (from `schema-families.md` §5). lxml always receives the bytes, never a decoded string: it refuses a
  string that carries an encoding declaration, and it honours the BOM and the declaration itself.
- **JSON family:** after decoding as `utf-8-sig` and stripping comments, the text parses as a JSON **object**.
- **Otherwise** `FAMILY_UNRESOLVED` (exit `3`), reporting both parse errors. A document with an XML declaration that
  fails to parse is `XML_MALFORMED` (exit `1`).

The lxml parser is always `etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False,
huge_tree=False)`.

**DD9 — XSD grammar selection and process structure.**

- **Root → XSD, per §5.** A `view` root is resolved by its parent folder: `_views` → table-view, `_lookupviews` →
  lookup-view, `_gridforms` → grid-form. `--view-kind table|lookup|grid` overrides. If the kind is still
  undecidable, the result is `SCHEMA_UNSELECTABLE`. A `Tree` root is `XSD_NOT_COMPILABLE` and not run.
- **Process structure runs in two passes** (ADR 0014 §1). Pass 1 validates against the vendored `process.xsd`. If
  it fails, pass 2 validates against an **extended** XSD built in memory from `process.xsd` plus the
  `process-divergence` rows. Each row is added as an optional attribute, an optional child element of type
  `xs:anyType` with lax processing, or an enumeration relaxed to `xs:string`.
  - Every pass-2 error is `XSD_INVALID`, and the semantic checks are then `NOT RUN (structure invalid)`.
  - Every pass-1 error with no pass-2 counterpart, matched on line and element, is `XSD_RUNTIME_DIVERGENCE`. It
    names the construct and its binding type, e.g. `State.ftitle`.
- **Every other grammar is validated once;** each error is `XSD_LAGS_RUNTIME` (D3).

**DD10 — Workspaces-root model** (ADR 0014 §2).

- The **owning workspace** `W` of a file is the path segment directly above its `FM/`. The **root** is `W`'s
  parent, overridable with `--workspaces-root`.
- The **application workspaces** are every directory under the root that has an `FM/`, **except** `webasm`.
- **Existence is exact-case.** Resolution compares directory entries by name (`os.scandir`), never
  `Path.exists()`, which is case-insensitive on APFS. A case-only match is `CASE_ONLY_MATCH`.

For a process `P` in workspace `W`, reached as `P` if `W` is an application and as `BASE:P` if `W` is `webasm`:

| Reference form | `W` is an application | `W` is `webasm` |
|---|---|---|
| `WORKFLOW:BASE:X` / `WORKFLOW:/BASE:X` | `webasm/FM/_WORKFLOW/X/_workflow.xml` | same |
| `WORKFLOW:/X` | `W/FM/_WORKFLOW/X/_workflow.xml` | **every** app `A`: `A/FM/_WORKFLOW/X/_workflow.xml`. All resolve → pass; otherwise `WORKFLOW_APP_DEPENDENT`, listing the apps that resolve and those that don't (D2) |
| `WORKFLOW:X` (bare) | `W/FM/_PROCESS/P/X/_workflow.xml` | `webasm/FM/_PROCESS/P/X/_workflow.xml` |
| `@validationFlow` `BASE:X` / bare `X` | webasm `_WORKFLOW/X` / `W/FM/_WORKFLOW/X` | webasm `_WORKFLOW/X` / every app, as `/X` above |
| `CHANGE_STATE` `process="BASE:Q"` / `"Q"` in a workflow in `W` | `webasm/FM/_PROCESS/Q/process.xml` / `W/FM/_PROCESS/Q/process.xml` | webasm / every app, as `/X` above |

An empty `@action` is skipped. So is a value whose prefix is not `WORKFLOW:` (e.g. `FORM:`); the latter is
counted in `NOT RUN: form-reference`. `MultiTaskGroup` actions in `P/<State>.xml` are resolved like `@action` when
the file exists. `Process/@table`, `OpenHandler` and `SubProcess` are not covered yet (ADR 0014 follow-ups).

**DD11 — Semantic checks** (ADR 0014 §2).

- **Dead transition** checks every `Transition/@state` under `OnStart/Transitions` and `States/State/Transitions`,
  and every `State/OnTimeout/@state`, against the declared states plus `End`.
- **Unreachable state.** The entry set is `OnStart` transitions, `OnTimeout` targets, and the `state` attribute of
  every `CHANGE_STATE` step naming this process anywhere under the root. `applyforstates` are *source* states, so
  they are not in it. Anything unreachable is a warning.
- **Change-state target resolution** runs over every `_workflow.xml` in `FM/_WORKFLOW/*/` and `FM/_PROCESS/*/*/`.
  `mode` must equal `CHANGE_STATE` exactly. `state` and each **untrimmed**, non-empty `applyforstates` token must
  name a declared state or `End`, compared ordinally (E12).

**DD12 — Known-good run** (`tools/run_known_good.py <dgf-root>`).

- **Inputs.** It walks `<dgf-root>/src/samples/workspaces` and runs `validate_process --all`, then
  `validate_config` and `resolve_components` on every component JSON and every legacy XML artifact (E16 names). It
  imports `scripts/lib` directly, which ARCHITECTURE.md permits for tools.
- **It passes only when all of these hold:**
  - zero errors outside `tools/known-good-exceptions.txt`;
  - the resolution-computed set of unresolved `CHANGE_STATE` processes equals the file's `EXPECTED_EXTERNAL` names;
  - every exception still reproduces (a stale entry fails).
- **Output.** It prints warning counts per code as the baseline summary.
- **Checkout drift.** If the checkout's HEAD differs from `dgf_commit` in `provenance/knowledge/schemas/MANIFEST.md`,
  the expected-set assertions downgrade to warnings.
- **Exceptions file format:**
  - `EXCEPTION <CODE> <sample-relative-path> <key> -- <reason and evidence>`
  - `EXPECTED_EXTERNAL <process-name>`
  - `#` comments.

**DD13 — Dependencies and install.**

- `tools/requirements.in` lists `lxml` and `jsonschema`.
- `scripts/requirements.txt` is generated from it with
  `uv pip compile tools/requirements.in --universal --python-version 3.9 --generate-hashes -o scripts/requirements.txt`.
- Install command, as `deps.py` prints it and the docs show it:
  `python3 -m pip install --user --require-hashes -r "<plugin>/scripts/requirements.txt"`. `deps.py` prints it with
  the absolute path it resolved at run time.
- Contributors use a `.venv/` at the plugin root. The repo root `.gitignore` gains `.venv/` and `__pycache__/`.

## Commit Plan

- **Commit 1** (after tasks 1–4): `docs(adr): accept 0011; supersede 0006 and 0007; record the XSD-lag policy`
- **Commit 2** (after tasks 5–8): `docs(knowledge): correct names, extend the parity table, add reader and process facts`
- **Commit 3** (after tasks 9–10): `feat(scripts): pin validator dependencies and probe them from the doctor`
- **Commit 4** (after tasks 11–13): `feat(scripts): dual-family config validator with the NJsonSchema pre-pass`
- **Commit 5** (after tasks 14–15): `feat(scripts): component resolution and the order-of-means route`
- **Commit 6** (after tasks 16–17): `feat(scripts): process structure and semantic checks`
- **Commit 7** (after tasks 18–20): `test: known-bad and known-good corpora; feat(tools): drift check`
- **Commit 8** (after task 21): `docs: document the validators and propagate the new decisions`

Every commit must leave `bash tools/check-dual-schema-docs.sh` and `python3 skills/dgf-doctor/scripts/doctor.py` at
exit `0`, or `2` with the dependency warning only. From Commit 3 on, `python3 -m unittest discover -s tests -t .`
must also pass inside `.venv/`.

## Tasks

### Phase 1: Decisions

Order matters. ADR 0011 is accepted **last**. Once accepted it can change only by erratum, and its Options B links
ADR 0006, so it is finalized after its successors exist.

- [x] **Task 1: Write ADR 0014, "Process verification — structure with a runtime-divergence allowance, semantics
  resolved the way the runtime resolves them"** (`supersedes: [0006]`, `accepted`, 2026-09-24).
  - **Restate every still-valid section of 0006** (full supersession, `docs/adr/README.md`): Context carried forward,
    §1 structure with the divergence allowance, the §2 checks, §3 vendored in-process validation, §4 no runtime
    claim.
  - **Replace 0006 §2's resolution rules** with DD10's table and its evidence, E9–E13. The Context must show the
    measurement that forced it (E14: 62/172 blocked). It must include the two true positives
    (`Expert.MoveTaskTo` → `RecordState13`; `InspectionBorderOrOutSide`), and D2 as the decision for `/X` in
    `webasm` processes.
  - **Add:** `CASE_ONLY_MATCH`; `MultiTaskGroup` actions; exact, untrimmed `applyforstates` comparison;
    `CHANGE_STATE` app-dependence for workflows owned by `webasm`.
  - **Follow-ups:** a known-good corpus whose expectations come from E14. That is 0 dead transitions, the 8
    expected-external targets, and the true positives recorded as evidenced exceptions. It also includes the
    known-bad list (Task 18) and `Process/@table` / `OpenHandler` / `SubProcess` as deferred.
  - Set 0006 to `superseded-by-0014` with `date: 2026-09-24`; its body is unchanged. Add the index row.
  - In `docs/blueprint.md`, the Q5 `ANSWERED` block (L380) gains "Revised (2026-09-24)", and its link moves to
    0014. `tools/check-dual-schema-docs.sh` §5b fails if an `ANSWERED` line still links 0006.
  - Relink `docs/dgf-knowledge.md:152` to 0014.
  - **Relink `AGENTS.md` L141-144** ("Process verification and version gating are decided by …") to 0014 and 0013,
    and add 0006 to the superseded list. AGENTS.md is loaded into every implementation session, and it is edited
    directly in feature commits (`8477ef3`, `dfa4d95`). The rest of the AGENTS.md update stays in Task 21.
  - Leave the accepted ADRs' bodies and `.ai-factory/` alone: the ADR bodies are historical, and the
    `.ai-factory/` hits go to Task 21. ADR 0011 is handled in Task 4.

  Files: `docs/adr/0014-process-verification-runtime-resolution.md`, `docs/adr/0006-…md` (frontmatter only),
  `docs/adr/README.md`, `docs/blueprint.md`, `docs/dgf-knowledge.md`, `AGENTS.md`. Logging: n/a (prose).

- [x] **Task 2: Write ADR 0015, "Validators run on Python with lxml and jsonschema, and read JSON the way the
  runtime does"** (`supersedes: [0007]`, `accepted`, 2026-09-24).
  - **Restate all of 0007:** the Python 3.9 floor, lxml, jsonschema with the dialect chosen per file, pinned and
    never auto-installed, a missing dependency as exit `3`, the stdlib-only doctor and stamps tool, `profile.xsd`
    excluded, and `format` as annotation-only.
  - **Correct a false fact while restating.** 0007 says lxml runs the "same libxml2 engine as `xmllint`". lxml 6.1.3
    **bundles libxml2 2.14.6**; the system `xmllint` is 2.9.13 (E18). Restate it with the measurement: the results
    agree, because 8/9 XSDs compile under both (`profile.xsd` fails) and 211 workflows and 2 processes fail under
    both. The validator's authority is lxml's bundled engine, never `xmllint`.
  - **Replace §4 with the pre-pass plus runtime reader semantics:** DD5, with evidence E2–E8.
  - **The decision D1:** an unknown property is a warning, because the runtime skips it.
  - **Alternatives.** Schema-literal PascalCase (0/230 samples pass). MCP parity, stripping `additionalProperties`
    (validates nothing, as `{}` shows). Blocking on unknown properties (0007 as written). Validating against the
    unsynced `ExportWith_SystemTextJson` output (not vendored, and not what the MCP serves).
  - **Consequences.** The pre-pass and dispatch are the plugin's to maintain. The converter prefix match is
    order-dependent (E3). Measured pass rates go in the Context (E6).
  - Set 0007 to `superseded-by-0015` and add the index row. Relink `docs/dgf-knowledge.md:153` and the "validator
    runtime" wording in `AGENTS.md`'s Agent Rules to 0015, and add 0007 to the superseded list.
  - The blueprint links 0007 nowhere (grep 2026-09-24), so no `ANSWERED` block changes.

  Files: `docs/adr/0015-validator-runtime-and-json-reader.md`, `docs/adr/0007-…md` (frontmatter only),
  `docs/adr/README.md`, `docs/dgf-knowledge.md`, `docs/dgf-schemas.md`, `AGENTS.md`. Logging: n/a (prose).

- [x] **Task 3: Write ADR 0016, "Legacy XSDs other than process lag the runtime; their failures warn until each has
  a divergence list"** (`supersedes: []`, `accepted`, 2026-09-24).
  - **Context:** E15, with the per-grammar rates, the top workflow error kinds, and DGF's own form baseline
    (`xsd-sample-baseline.txt`, `verify-xsd-coverage.sh` 11b).
  - **Decision (D3):** `XSD_LAGS_RUNTIME` (exit `2`) for workflow, form, settings, the three view grammars and
    options. `checks_run` still records `xsd-structure`, and the report says the result is advisory.
  - **Alternatives:** blocking (62% of workflows); per-grammar divergence lists now (the workflow model's size); DGF's
    baseline approach (it excuses whatever the samples contain, which ADR 0006 rejected for process).
  - **Follow-ups:** a divergence list per grammar, ordered by failure rate (workflow first); upstream reports.
  - Add the index row.

  Files: `docs/adr/0016-legacy-xsd-lag.md`, `docs/adr/README.md`. Logging: n/a (prose).

- [x] **Task 4: Accept ADR 0011.** (depends on 1, 2)
  - It is `proposed`, so it may be edited freely before acceptance (`docs/adr/README.md` §Errata).
  - First, make its Decision say that shipped files read the **shipped** parity table, `knowledge/schema-families.md`
    §6, drawn from `format-coverage.md` and tracked by digest. Match ADR 0010's erratum and ADR 0012.
  - Repoint its ADR 0006 link (Options B, "§3 already rules out a network dependency") to ADR 0014 §3.
  - Then set `status: accepted`, `date: 2026-09-24`. Replace the "Status: proposed" paragraph with
    "**Status: accepted** (2026-09-24, Andrian Mamei)", and "Recommended, not yet accepted" with the bolded
    one-line decision.
  - Update its index row in `docs/adr/README.md`, and the See Also line in `docs/dgf-schemas.md:355` ("the
    proposed decision record" → "the decision record").
  - The citations from `AGENTS.md` and `.ai-factory/rules/base.md` that 0011's follow-ups ask for are made in
    Task 21, through their owners.

  Files: `docs/adr/0011-schema-parity-authority.md`, `docs/adr/README.md`, `docs/dgf-schemas.md`. Logging: n/a
  (prose).

<!-- Commit checkpoint: tasks 1-4. Run tools/check-dual-schema-docs.sh; it must exit 0. -->

### Phase 2: Knowledge prerequisites

Every task here updates the file's `read_date` to `2026-09-24`, and its provenance ledger with every DGF file read,
each with its `sha256` (`shasum -a 256`). Shipped text names DGF types and MCP calls only (ADR 0012). Each task ends
with `python3 tools/check_knowledge_stamps.py` → 0 and the doctor → `DGF_PATH`-clean.

- **A new knowledge file carries the full stamp:** `dgf_version: "1.1.11"` (never a tag value; `knowledge/README.md`
  §1.1) and `read_date`. Add `review_date` only for a policy fact. `check_version_agreement` warns when stamps
  disagree.
- **Knowledge states facts only.** It never names a script, a finding code, a task, a DD number or a pipeline step
  (ARCHITECTURE.md, "Knowledge that knows the pipeline"). The `<!-- machine-read: <id> -->` marker is the only
  coupling between a knowledge file and the code that reads it. Vocabulary such as `by-type` or `enum-relaxed`
  describes DGF, not the validator.

- [x] **Task 5: Write the machine-read-table contract, then correct `knowledge/naming-conventions.md` and the same
  facts where they are repeated** (DD2, E16, E17).
  - **The contract comes first,** because this task introduces the first machine-read table. Write DD2 into
    `knowledge/README.md` as a new §7, "Machine-read tables". Cover the marker, exact headers, what the loader
    strips, and that a malformed table blocks the doctor. §6 keeps saying the README is the only unstamped file.
  - **§1:** `_STORAGE` is joined under the workspace root, not `FM/`. `_DataSources`, `_SiteMaps` and `_EndPoints`
    are declared by `WorkspaceSettings` but referenced by nothing the engine runs; endpoints load from
    `_COMPONENTS/Endpoints`. State that they are **not** directories a generator should create.
  - **§2:** give each filename **as the runtime loader opens it**, read from the loaders: `process.xml`
    (`ProcessManager`), `_workflow.xml` (`WorkflowManager`), `_form.xml`, `settings.xml` (`TableManager`),
    `_view.xml` under `_views/` and `_lookupviews/`, and `_grid.xml` under `_gridforms/`. Confirm each in
    `View`/`LookUpViewManager`/`AbstractView` and the form and grid loaders before writing it, and stamp it
    **structural**. Add the `<table>/_forms/<form>/`, `_views/<view>/`, `_lookupviews/<view>/` and
    `_gridforms/<grid>/` folder rule.
  - Add one sentence saying that DGF's format-coverage page labels two of them `_process.xml` and `view.xml`, and that
    the loader wins.
  - Fix §2's warning sentence ("A generator that emits `_settings.xml` or `form.xml` …") so it no longer states
    wrong names.
  - **Apply the same corrections** to `knowledge/composition-specs.md`: §1's table and "each artifact path is
    `Path.Combine(FmPath, …)`" sentence, and §2's Artifact column. Also correct the legacy-filename sentence in
    `knowledge/schema-families.md` §6.
  - **Add a `legacy-artifacts` machine-read table** (DD2) to `composition-specs.md` §2, with header
    `| Artifact | Filename | Folder | Grammar |` and one row per grammar file (the view row splits into three).
  - Update the three ledgers.

  Files: `knowledge/naming-conventions.md`, `knowledge/composition-specs.md`, `knowledge/schema-families.md`,
  `provenance/knowledge/{naming-conventions,composition-specs,schema-families}.md`. Logging: n/a (prose).

- [x] **Task 6: Write `knowledge/json-reader.md` — how the runtime reads a component JSON file** (structural,
  E2–E7). (depends on 5)
  - **§1 Reader options.** List every `ConfigureJsonOptions` setting that changes what is **accepted**. Read each
    registered converter's `Read` method (`BooleanConverter`, `DictionaryJsonConverter`,
    `ObjectParametersConverter`, `ComponentModelConverter`, `AbstractStepJsonConverter`, the Date/Time converters)
    and state exactly which JSON token shapes it accepts. This is what DD5 implements; do not guess one.
  - **§2 Component dispatch.** State the `ComponentConverter` rule. Add `<!-- machine-read: component-classes -->`
    `| ComponentType | Configuration schema | Bound by |` with all 67 members (excluding `None`).
    - `Bound by` is `name` (exact or `+Configuration`), `prefix`, or `none`.
    - Where the prefix match is order-dependent (at least `Date` vs `DateTime…`), record the class whose constructor
      passes that `ComponentType` to its base, and name the ambiguity in prose.
    - Record `HeaderConfiguration`'s `Footer` binding as a known upstream defect.
  - **§3 DataSource discriminators.** `<!-- machine-read: datasource-discriminators -->` `| Discriminator | Schema |`
    with the 9 → 6 rows. An unknown value throws.
  - **§4 Component folders.** `<!-- machine-read: component-folders -->` `| Folder | Loader | Selection |`, where
    `Selection` is `by-type`, `by-discriminator`, `fragment-by-type` or `none`. Rows: `DataSource`, `Template`,
    `Endpoints`, `(root) sitemap*.json`, `(any other ComponentType name)` → `by-type`, and `(unreferenced)` →
    `none`. Name `Forms/` as the observed unreferenced case.
  - Write the ledger, `provenance/knowledge/json-reader.md`.

  Files: `knowledge/json-reader.md`, `provenance/knowledge/json-reader.md`. Logging: n/a (prose).

- [x] **Task 7: Extend the parity table to all 67 rows.** (depends on 5, 6)
  - Replace `knowledge/schema-families.md` §6's three-row summary with the `<!-- machine-read: parity -->` table
    `| # | Row | ComponentType | Schema | Runtime | XML-only part |`, holding **every** `format-coverage.md` row in
    its own order and numbering (E1).
    - `ComponentType` is the enum member(s) the row describes, from Task 6's `component-classes`. It is `—` for the
      DataSource rows, `SiteMap` and the struck `Accordion`.
    - `Schema` is the vendored file name.
    - `Runtime` is the verbatim symbol `✓`/`◐`/`✗`; `—` for `Accordion`, noted as deprecated.
    - `XML-only part` is the row's own words for every ◐ and ✗ row, and empty otherwise.
  - Keep the legend and the "only authority" paragraph. Add a paragraph listing the `ComponentType` members that have
    **no** row (derived from `component-classes`), because `route_means.py` exits `3` on them.
  - Re-read the page with `get_doc_page('AI-Authoring/format-coverage.md')` and the checkout, and update
    `review_date`. Update the ledger (the page digest; `ComponentConverter.cs` for the mapping).

  Files: `knowledge/schema-families.md`, `provenance/knowledge/schema-families.md`. Logging: n/a (prose).

- [x] **Task 8: Write `knowledge/process-model.md` — the divergence list and reference resolution** (structural,
  ADR 0014).
  - **§1** is `<!-- machine-read: process-divergence -->` `| Construct | Kind | XSD owner | Binding |`.
    - `Kind` is `attribute`, `element` or `enum-relaxed`.
    - `XSD owner` is the `process.xsd` complexType, or the content model a child element goes into.
    - `Binding` is the model type and member, e.g. `State.ftitle`.
  - **Derive it only** from the `[XmlAttribute]` / `[XmlElement]` / `[XmlArray]` / `[XmlArrayItem]` bindings in
    `Process.cs`, `State.cs`, `AbstractStateEvent.cs`, `Transition.cs` and `TimeoutStateEvent.cs`, and in every
    class they reference, diffed against `process.xsd`. **Never** add a row because a sample uses it
    (ADR 0006/0014 §1).
  - Expected at minimum: `State/@fdesc`, `State/@ftitle`, `State/OnTimeout` (with `@interval`, `@state`),
    `Process/@hideDesc`, `StoredProcedureActivity` in the state event content models, and `State/@type` as
    `enum-relaxed` (`State.Type` is a plain `string`).
  - Verify the result reproduces E15's 2 failing samples as divergences only. Load the vendored XSD, apply the rows by
    hand in a scratch copy, and run `xmllint` on the 23 samples. **If any sample still fails, STOP and report.** Do
    not widen the list to make it pass.
  - **§2** states DD10's resolution rules as facts (E9–E13), with the four `GetWorkPath` forms.
  - **§3** covers the reserved `End`.
  - Write the ledger.

  Files: `knowledge/process-model.md`, `provenance/knowledge/process-model.md`. Logging: n/a (prose).

<!-- Commit checkpoint: tasks 5-8. check_knowledge_stamps.py → 0; doctor → 0; check-dual-schema-docs.sh → 0. -->

### Phase 3: Runtime foundation

- [x] **Task 9: Pin the dependencies and write the stdlib foundation modules.** (depends on 6, 7, 8)
  - **Dependencies.**
    - Create `tools/requirements.in`, generate `scripts/requirements.txt` with DD13's `uv` command, and commit both.
    - Verify in a fresh `.venv` built on `/usr/bin/python3` (3.9.6) that
      `pip install --require-hashes -r scripts/requirements.txt` succeeds and both packages import.
    - If the resolver picks a version that drops 3.9, pin the newest that supports it and say so in the file header.
    - Add `.venv/` and `__pycache__/` to `../../.gitignore`.
    - **Keep the venv out of the docs check.** `owned_markdown()` in `tools/check-dual-schema-docs.sh:93-98` prunes
      only `.claude`, `.git`, `node_modules` and `plans`. A plugin-root `.venv/` would pull every site-packages `.md`
      into sections 1 and 4. Add `.venv` and `__pycache__` to its `-name … -prune` list.
  - **Import mechanics** (one scheme everywhere):
    - Modules in `scripts/lib/` import each other with relative imports (`from . import report`).
    - **`knowledge.py` imports nothing from the package.** The doctor loads it by file path with
      `spec_from_file_location`, where relative imports fail. It defines its own `KnowledgeTableError`.
    - The CLIs in `scripts/` rely on Python putting `scripts/` at `sys.path[0]`, and import `lib.<module>`.
    - `tests/helpers.py` and every tool insert `<plugin>/scripts` into `sys.path` once, then import `lib.<module>`.
      Nothing imports `scripts.lib…`.
  - **`scripts/lib/report.py`.**
    - `Finding(code, severity, file, line, message)`, `Report(family, checks_run, not_run, findings)`,
      `exit_code(reports)`, `render(reports, stream)` (DD3), and the `debug(module_fn, msg, **kv)` helper.
    - `debug` writes only when `--verbose` or `DEBUG=1`. Define the ANSI constants once, and disable colour when
      stdout is not a TTY.
    - Include one `fail(code, message)`.
  - **`scripts/lib/deps.py`.** `require()` imports `lxml.etree` and `jsonschema`. On `ImportError` it fails with
    `DEPENDENCY_MISSING` (exit `3`) and the DD13 install command. Every validator calls it first, and nothing in
    `scripts/lib` imports lxml or jsonschema at module import time before `require()`.
    - The printed command includes `--user` **only** outside a virtual environment (`sys.prefix == sys.base_prefix`),
      because `pip install --user` fails inside one.
  - **`scripts/lib/knowledge.py`.** The DD2 loader, stdlib only, with `load(table_id)` returning a list of dicts. It
    declares the expected headers for all six table ids.
  - **Tests** (stdlib only, so they run without the dependencies):
    - `tests/helpers.py` with `make_root(tmp, files: dict)` and `run_cli(script, *args) -> (code, stdout, stderr)`.
    - `tests/test_report.py`: exit aggregation, where `3` beats `1` beats `2` beats `0`.
    - `tests/test_knowledge.py`: every real table loads; a mutated temp copy fails on a missing marker, a wrong
      header, and a duplicate key.
    - `tests/test_deps.py`: simulate `ImportError` by patching `builtins.__import__` → exit `3`, with the command
      in the message; `--user` present outside a venv and absent inside one (patch `sys.prefix`).
  - **Logging:** `debug` on each knowledge table loaded (`table=<id> rows=<n>`) and on the `deps` result.
    Missing-dependency and malformed-table messages go to stderr through `fail`.

  Files: `tools/requirements.in`, `scripts/requirements.txt`, `scripts/lib/{__init__,report,deps,knowledge}.py`,
  `tests/{__init__,helpers,test_report,test_knowledge,test_deps}.py`, `../../.gitignore`,
  `tools/check-dual-schema-docs.sh` (prune list only).

- [x] **Task 10: Give `doctor.py` its validator-runtime section.** (depends on 9)
  - **Add the section** "Validator runtime" after "Line endings" and before "Build progress", renumbering as needed.
    The doctor stays stdlib-only (ADR 0015).
    1. **Dependency probe.** `importlib.util.find_spec` for `lxml` and `jsonschema`. If either is missing →
       warning `VALIDATOR_DEPS_MISSING`, with the install command. It never installs anything.
    2. **Pins.** If `scripts/requirements.txt` exists, every non-comment requirement line must be `name==version`
       with at least one `--hash=sha256:`, else the error `REQUIREMENTS_UNPINNED`. If `scripts/` exists but the
       file does not, that is also `REQUIREMENTS_UNPINNED`.
    3. **Knowledge tables.** Load `scripts/lib/knowledge.py` with `importlib.util.spec_from_file_location` (the
       `vendor_schemas.py` pattern) and call `load()` for every table id. Failure → error `KNOWLEDGE_TABLE`.
  - **Skip bytecode in `shipped_files()`** (`doctor.py:147-155`). Running a validator writes
    `scripts/lib/__pycache__/*.pyc`, on a contributor's tree and on a developer's installed copy alike. The CRLF
    check (`doctor.py:354-363`) reads raw bytes, and marshalled bytecode can contain `\r\n`. Skip any path with a
    `__pycache__` component and any `*.pyc`. They are never shipped (gitignored, Task 9). Trace the skip count under
    `DEBUG=1`.
  - **Update** the module docstring's check list and `skills/dgf-doctor/SKILL.md` wherever it enumerates sections or
    codes.
  - **Tests** in `tests/test_doctor.py` run the doctor against temp copies of the plugin. The copy is
    `shutil.copytree(..., ignore=shutil.ignore_patterns('.venv', '__pycache__', '.claude'))`.
    - the real tree → `0` or `2` (the deps warning only);
    - a requirement line without a hash → `1`;
    - a broken table marker → `1`;
    - a shipped file containing a DGF path → `1` (this guards the doctor's existing check against new scripts);
    - a planted `scripts/lib/__pycache__/x.pyc` containing `\r\n` → no `CRLF` finding.
  - **Logging:** each probe result is reported as `INFO`/`WARN` in the section, with `trace` under `DEBUG=1` as the
    doctor already does.

  Files: `skills/dgf-doctor/scripts/doctor.py`, `skills/dgf-doctor/SKILL.md`, `tests/test_doctor.py`.

<!-- Commit checkpoint: tasks 9-10 -->

### Phase 4: JSON family and the config validator

- [x] **Task 11: Write the pre-pass and its fixtures first** (ADR 0015; ADR 0007 §4's "tested first").
  - **Fixtures first:** `tests/fixtures/unit/prepass/`, holding a minimal synthetic schema. It is a three-level
    NJsonSchema-shaped `allOf` chain with `x-abstract` bases and `additionalProperties: false` on every branch.
    Instances:
    - `inherited-pass.json` sets a property from each level → no findings;
    - `unknown-property-fail.json` adds one unknown property → exactly one `UNKNOWN_PROPERTY`;
    - `required-from-base-fail.json` omits a base `required` → `SCHEMA_INVALID`.
  - **Write `tests/test_prepass.py` and see it fail** before writing `scripts/lib/prepass.py`.
  - **`prepass.merge(schema)`.** Walk the schema recursively, `definitions` included. For every `allOf` that contains
    a local `$ref`, produce one object: the union of `properties` (derived overrides base), the union of
    `required`, and `additionalProperties: false` when any branch set it. Resolve `$ref` chains transitively,
    guard cycles with a visited set, and leave non-inheritance `allOf` untouched. Never mutate the input; deep-copy.
  - **`scripts/lib/json_reader.py`** implements DD5's parse step. Test the comment scanner with `//` and `/* */`
    inside strings (they must survive), a BOM, and a trailing comma (a failure).
    - **Comment stripping preserves positions.** Replace every comment character with a space and keep every
      newline, so the line and column that `json` reports, and that findings cite, are the file's own. Test that an
      error after a multi-line `/* … */` block reports its true line.
  - Then run the pre-pass over **all 69** vendored `json/` schemas in a test and assert it terminates. Assert that
    every merged root with an `allOf`+`$ref` source now has a single `properties` map. The source pattern appears 97
    times in 64 files (ADR 0007 errata).
  - **Logging:** `debug("prepass.merge", …, schema=<title> merged_allof=<n> props=<n>)` per schema, and a debug line
    per cycle skipped.

  Files: `scripts/lib/{prepass,json_reader}.py`, `tests/test_prepass.py`, `tests/test_json_reader.py`,
  `tests/fixtures/unit/prepass/*`.

- [x] **Task 12: Write the runtime-faithful JSON validator and schema resolution.** (depends on 11)
  - **`scripts/lib/json_validate.py`.** Use `jsonschema.validators.extend` on `Draft4Validator` or
    `Draft7Validator`, chosen by the schema's own `$schema`; an unknown dialect → exit `3`. Override
    `properties`, `required`, `additionalProperties` (→ `UNKNOWN_PROPERTY`, a warning), `enum` (DD5), `type` (only
    where Task 6 §1 says a converter widens a type) and `$ref`.
    - `$ref` dispatches `IComponentConfiguration` and `IDataSource` (DD5). Every other `$ref` defers to
      `validator._validate_reference(ref=…, instance=…)`.
    - Cache merged, dispatched schemas per class.
    - Map `jsonschema` errors to `SCHEMA_INVALID` findings, with a line number where the reader can supply one; a
      JSON path otherwise.
    - Do **not** pass a `format_checker` (DD3).
  - **`scripts/lib/json_resolve.py`.**
    - `index()` mirrors `SchemaIndexService` exactly (`*Configuration.schema.json` plus the one allow-listed file).
    - `class_for(type_value)` reads `component-classes`, and `datasource_for(value)` reads
      `datasource-discriminators`.
    - `select(path, document, override)` applies DD6 using `component-folders`.
    - Quote every path; one filename has a backtick.
  - **Tests** (`tests/test_json_validate.py`, synthetic fixtures under `tests/fixtures/unit/json/`):
    - case-folded keys pass;
    - two keys differing only in case fail;
    - an integer enum written as a name passes;
    - nested `section` → `Row` → `text` dispatch finds an error two levels down;
    - an unknown nested `type` → `UNKNOWN_COMPONENT`;
    - a DataSource `type: "tabel"` → `UNKNOWN_DISCRIMINATOR`;
    - a comment-bearing file parses;
    - `Template/`, `Endpoints/`, root sitemap and `Forms/` select per DD6.
  - **Logging:** `debug` for the class selected per file and per dispatched child (`path=<json-path>
    type=<value> class=<name>`), and for each reader rule applied (enum-by-name, case-fold).

  Files: `scripts/lib/{json_validate,json_resolve}.py`, `tests/test_json_validate.py`, `tests/test_json_resolve.py`,
  `tests/fixtures/unit/json/*`.

- [x] **Task 13: Write family detection, the XSD layer, the parity gate and `scripts/validate_config.py`.**
  (depends on 12)
  - **`scripts/lib/family.py`** implements DD8: bytes in, BOM sniffed on the raw bytes, and lxml handed the
    original bytes. It never decodes XML first (E21).
  - **`scripts/lib/xsd.py`.**
    - Compile each vendored XSD once with lxml, except `profile.xsd` → `XSD_NOT_COMPILABLE`, not run.
    - `grammar_for(root_tag, path, view_kind)` implements DD9.
    - `validate(doc, grammar)` returns `XSD_LAGS_RUNTIME` warnings for the non-process grammars.
    - `validate_process_structure(doc)` does DD9's two passes, building the extended XSD from `process-divergence`
      by editing a parsed copy of `process.xsd` (never the vendored file).
  - **`scripts/lib/parity.py`** implements DD7 over `parity`.
  - **`scripts/validate_config.py`.**
    - Usage: `<path>... [--component-type T] [--view-kind table|lookup|grid] [--verbose]`. A directory argument
      recurses over the E16 artifact names and `*.json`.
    - Calls `deps.require()`, then per file: family → schema/grammar → validate → parity.
    - Prints DD3's output and exits per DD3. No arguments or an unknown flag → exit `3`.
  - **Tests** (`tests/test_validate_config.py`):
    - every DD4 code this CLI can emit, each with the exact exit code;
    - a JSON `Workflow` config → exit `2` `PARITY_NOT_RUNTIME`;
    - a JSON `Form` → `PARITY_PARTIAL`;
    - a process with `ftitle` → exit `2` `XSD_RUNTIME_DIVERGENCE`;
    - a process with an unknown element → exit `1` `XSD_INVALID`;
    - a workflow using `StateProcess` → exit `2` `XSD_LAGS_RUNTIME`;
    - plain text → exit `3`;
    - a `Tree` root → `XSD_NOT_COMPILABLE`;
    - a UTF-16 LE `_form.xml` with a BOM and an `encoding="utf-16"` declaration parses and validates (E21); a
      UTF-8 file with a BOM and an encoding declaration parses; a filename containing a space is handled.
  - **Logging:** `debug` per file for `family=`, `grammar=`/`schema=`, `pass1_errors=`, `pass2_errors=`, and
    `parity_row=`. Findings go to stdout only.

  Files: `scripts/lib/{family,xsd,parity}.py`, `scripts/validate_config.py`, `tests/test_validate_config.py`,
  `tests/test_xsd.py`, `tests/fixtures/unit/xml/*`.

<!-- Commit checkpoint: tasks 11-13 -->

### Phase 5: Components and route

- [ ] **Task 14: Write `scripts/resolve_components.py` — component-type legality in both families.** (depends on 13)
  - **JSON.** Walk every object that has a `type` key, reached through a property the pre-pass-merged schema types as
    `IComponentConfiguration` (not every `type` key; DataSource and endpoint `type`s are different enums). Check its
    value case-insensitively against the `ComponentType` enum read from the vendored schemas' `definitions` (67
    members plus `None`).
    - An unknown value is `UNKNOWN_COMPONENT`.
    - A member not among the 34 dispatchable services is `NO_SERVICE`, INFO. Parse the 34 from
      `component-catalogue.md` §3; add a `<!-- machine-read: dispatchable -->` marker and header to that table in
      this task, and add the id to `knowledge.py` and the doctor.
    - A member with no configuration class is `NO_CONFIG_CLASS`.
  - **XML.** For `_form.xml`, check every `component/@type` against `form.xsd`'s `componentTypeValue` enumeration.
    That makes an unknown type **blocking**, even though form XSD failures only warn (D3).
  - **Component file references.** Read how DGF resolves `ComponentConfigurationBase.Path` and `.Ref`
    (`ComponentFileLoadService` callers).
    - If the evidence shows a `_COMPONENTS/<Type>/<name>.json` lookup, add `COMPONENT_FILE_UNRESOLVED` (exit `1`),
      using `workspace.py`'s exact-case lookup and `BASE:` → `webasm`, and record the rule in `json-reader.md` §2
      with its ledger.
    - Otherwise print `NOT RUN: component-file-references (resolution semantics not verified)` and add a follow-up
      line to this plan.
  - The CLI takes the same arguments and output as `validate_config.py`.
  - **Tests:** a known type in camelCase passes; `dataTabel` → `1`; a legal no-service type → `0` with INFO; an XML
    form with an unknown component type → `1`; both families in one invocation.
  - **Logging:** `debug` per checked type occurrence (`path=`, `value=`, `member=`), and a summary count per code.

  Files: `scripts/resolve_components.py`, `knowledge/component-catalogue.md` (marker only),
  `provenance/knowledge/component-catalogue.md` (`read_date` untouched unless a fact changes),
  `scripts/lib/knowledge.py`, `tests/test_resolve_components.py`.

- [ ] **Task 15: Write `scripts/route_means.py` — ADR 0010 §1 as a script.** (depends on 13)
  - **Input:** `<name>`, a `ComponentType` member (case-insensitive) or a legacy artifact name from
    `legacy-artifacts` (`form`, `workflow`, `process`, `settings`, `view`, grid).
  - **Rule, in order:**
    1. A legacy artifact type → `xml`, naming its filename and folder. `Form` → `xml` too, per ADR 0010 §1 bullet 3
       (ADR 0005 rule 1).
    2. The row is ✗ → `xml`.
    3. The row is ✓ → `json`, `<workspace>/FM/_COMPONENTS/<Type>/<name>.json`.
    4. The row is ◐ → `json` **and** exit `2`, naming the row's XML-only part.
    5. No row → `ROUTE_NO_ROW` (exit `3`).
  - **Output:** a single `ROUTE: json|xml <where> — <reason>` line plus the DD3 verdict. It never prints `code`: means
    3 is a planner's judgement (`kind: code`), not a table lookup. Say so in the docstring.
  - **Tests:** one per rule, with `Form`, `Workflow`, `ProcessFlow`, `DataTable`, `Uploader` and `Search`.
  - **Logging:** `debug("route_means.main", name=…, row=…, legacy=…)`.

  Files: `scripts/route_means.py`, `tests/test_route_means.py`.

<!-- Commit checkpoint: tasks 14-15 -->

### Phase 6: Process checks

- [ ] **Task 16: Write `scripts/lib/workspace.py` — the workspaces-root model and resolvers** (DD10). (depends on 9)
  - **Functions:** `owning_workspace(path)`, `workspaces_root(path, override)`, `applications(root)`,
    `exact_child(dir, name) -> ('ok'|'case-only'|'missing', actual)`, `resolve_workflow_ref(value, process_ref,
    W, root)`, `resolve_validation_flow(value, W, root)`, `resolve_process(name, W, root)`.
  - **Resolver results** are one of:
    - `Resolved(path)`;
    - `Unresolved(path)`;
    - `CaseOnly(path, actual)`;
    - `AppDependent(resolved_in=[…], missing_in=[…])`.
  - No I/O beyond `os.scandir` and `is_file`.
  - **Tests** use temp roots built with `helpers.make_root`, one per DD10 table cell:
    - both `BASE:` spellings;
    - `/X` from an application and from `webasm`: all apps, some apps, no apps;
    - bare `X` process-local, from an application and from `webasm`;
    - `validationFlow` bare vs `BASE:`;
    - `CHANGE_STATE` process `BASE:Q`, `Q` from an app, and `Q` from a `webasm` workflow;
    - a case-only directory match.
  - **Logging:** `debug("workspace.resolve_workflow_ref", value=…, form=…, candidates=[…], result=…)`.

  Files: `scripts/lib/workspace.py`, `tests/test_workspace.py`.

- [ ] **Task 17: Write `scripts/lib/process_checks.py` and `scripts/validate_process.py`.** (depends on 13, 16)
  - **`scripts/validate_process.py`.** Usage: `[--workspaces-root R] (--all | <process.xml|_workflow.xml>...)
    [--verbose]`.
    - For each `process.xml`: structure (`xsd.validate_process_structure`), then, only when structure is not
      `XSD_INVALID`, dead-transition, unreachable-state, workflow-reference (including `MultiTaskGroup` actions)
      and validation-flow checks.
    - For each `_workflow.xml`: change-state target resolution.
    - `--all` covers every process and every workflow under the root (DD11). The `CHANGE_STATE` entry set for
      unreachable-state is always collected from **every** workflow under the root, even when only one process is
      named.
  - **`checks_run` ids:** `xsd-structure`, `dead-transition`, `unreachable-state`, `workflow-reference`,
    `validation-flow`, `change-state-target`. They are printed exactly, so milestone 10 can reuse them.
  - **Tests** (`tests/test_validate_process.py`) use synthetic roots:
    - a transition to `End` passes;
    - an `OnTimeout` edge makes a state reachable, and a `CHANGE_STATE` target makes one reachable;
    - an `applyforstates` token with a leading space → `CHANGE_STATE_STATE_UNDECLARED`;
    - `mode="change_state"` is **not** a `CHANGE_STATE` step;
    - structure-invalid skips the semantic checks and lists them under `NOT RUN`;
    - a `webasm` process with `/X` present in one of two apps → exit `2` `WORKFLOW_APP_DEPENDENT`.
  - **Logging:** `debug` per process (`states=`, `entry=`, `reachable=`) and per reference resolved (see Task 16).

  Files: `scripts/lib/process_checks.py`, `scripts/validate_process.py`, `tests/test_validate_process.py`.

<!-- Commit checkpoint: tasks 16-17 -->

### Phase 7: Corpora and maintainer tools

- [ ] **Task 18: Build the known-bad corpus** (ADR 0014 follow-ups: "a validator with no failing fixture has not been
  tested"). (depends on 13, 14, 17)
  - **Layout.** `tests/fixtures/known-bad/<case>/` holds a minimal synthetic `workspaces/` root (an app and `webasm`)
    and an `expected.json`: `{"cli": "<script>", "args": [...], "exit": N, "codes": ["CODE", ...]}`, in which
    `codes` must appear and no other error code may.
  - **One case per blocking row and exit-3 path:**
    - `json-schema-invalid`, `json-required-missing`, `json-duplicate-case-keys`, `json-unknown-discriminator`,
      `json-unknown-component` (resolve_components);
    - `json-trailing-comma` → `3`, `family-unresolved` → `3`, `schema-unselectable` → `3`;
    - `xml-malformed` → `1`, `xml-unknown-root` → `3`, `form-unknown-component-type` → `1`;
    - `process-xsd-invalid`, `process-dead-transition`, `process-dead-timeout`;
    - `process-workflow-unresolved-slash`, `process-workflow-unresolved-local`, `process-workflow-unresolved-base`;
    - `process-validation-flow-unresolved`, `multitask-action-unresolved`;
    - `change-state-process-unresolved`, `change-state-state-undeclared`, `change-state-applyforstates-undeclared`.
  - **`tests/test_known_bad.py`** discovers the cases, runs each CLI with `helpers.run_cli`, and asserts the exact
    exit and codes.
  - **Guards:** fixtures are synthetic, never copied from DGF, and never contain a DGF path. They live outside
    `SHIPPED_DIRS`, so the doctor ignores them either way. Also assert in the test that `tests/` is not in
    `doctor.SHIPPED_DIRS`.
  - **Logging:** each case failure prints the CLI's full stdout/stderr in the assertion message.

  Files: `tests/fixtures/known-bad/**`, `tests/test_known_bad.py`.

- [ ] **Task 19: Write `tools/run_known_good.py`, run it, and settle every error.** (depends on 18)
  - **Build the tool** per DD12. Usage: `<dgf-root> [--verbose]`. It validates the root as `vendor_schemas.py` does
    (the `src/Directory.Build.props` presence check).
  - **Seed `tools/known-good-exceptions.txt`** with:
    - the 8 `EXPECTED_EXTERNAL` names from ADR 0006/0014;
    - the true positives from E14 as `EXCEPTION` lines: `CHANGE_STATE_STATE_UNDECLARED` for `Expert.MoveTaskTo` →
      `RecordState13`, and `WORKFLOW_UNRESOLVED` ×2 for `InspectionBorderOrOutSide`.
  - **Run it** in `.venv` against `~/workspaces/dotgov/_DotGovFramework/DotGovFramework` at `aa1d5c4c2`. For
    **every** other error, do one of two things:
    - **(a)** Fix the validator when it contradicts the runtime evidence in `json-reader.md` / `process-model.md`.
      Add a unit test for the fix.
    - **(b)** Add an `EXCEPTION` line when the sample is genuinely defective, i.e. the runtime would reject or
      misread it. The reason cites the runtime code path.

    **Never** add an exception to make a validator gap pass. If an error class is neither provably a validator bug
    nor provably a sample defect, STOP and report it with counts and three examples.
  - **Record** the final warning counts per code at the top of the exceptions file as a dated comment. E6 predicts
    `UNKNOWN_PROPERTY` for `showHeaders`, and E14 predicts 15 `UNREACHABLE_STATE` and ≥29 `WORKFLOW_APP_DEPENDENT`.
    Record the counts as lxml measures them, with its `LIBXML_VERSION`, never from an `xmllint` run. The two engines
    are different libxml2 versions and agree today only by measurement (E18).
  - **Add section 8, "Validator tests",** to `tools/check-dual-schema-docs.sh`.
    - It runs `python3 -m unittest discover -s tests -t .` when `lxml` and `jsonschema` import, and warns otherwise.
      Map exit codes as section 7 does. Update the header comment.
    - The known-good run is **not** wired in, because it needs a DGF checkout; say so in the comment.
  - **Logging:** `debug` per validated file (`file=`, `codes=`). A summary table per CLI and per code goes to stdout.

  Files: `tools/run_known_good.py`, `tools/known-good-exceptions.txt`, `tools/check-dual-schema-docs.sh`, and
  validator fixes with their tests as found.

- [ ] **Task 20: Write `tools/check_drift.py` — the ledgers against a DGF checkout** (ADR 0013 §4–5). (depends on 9)
  - **Usage:** `<dgf-root> [--verbose]`. Stdlib only. Load `tools/check_knowledge_stamps.py` with `importlib` and
    reuse `frontmatter_lines`, `parse_frontmatter`, `sha256_of` and `knowledge_files`. Never re-implement the
    parser.
  - **Checks:**
    - every ledger under `provenance/knowledge/`, every `sources` entry: the upstream file's `sha256` in the checkout
      differs → `DRIFT` warning; missing upstream → `DRIFT_MISSING` warning;
    - the schema ledger's `dgf_commit` vs `git -C <dgf-root> rev-parse HEAD` → an INFO line;
    - the checkout's `Directory.Build.props` `<Version>` vs the stamps' `dgf_version` → a warning if they differ;
    - uncommitted changes in the checkout → a warning that digests may reflect local edits.
  - **Output:** each drift names the ledger, the source path and the knowledge file it feeds. It modifies nothing.
    The exit is `0`, `2` or `3`: shipped-digest errors belong to `check_knowledge_stamps.py`, so this tool never
    exits `1`.
  - **Tests** (`tests/test_check_drift.py`) use a temp fake DGF root, a `git init` with one commit, and a copied
    ledger set rewritten to point at it: clean → `0`; one byte changed → `2` `DRIFT`; a file removed → `2`
    `DRIFT_MISSING`; not a DGF root → `3`.
  - **Run it** against the real checkout and paste the result summary into this plan's Follow-ups.
  - **Logging:** `debug` per source (`ledger=`, `path=`, `expected=`, `actual=`).

  Files: `tools/check_drift.py`, `tests/test_check_drift.py`.

<!-- Commit checkpoint: tasks 18-20 -->

### Phase 8: Documentation and propagation

- [ ] **Task 21: Documentation checkpoint (`/aif-docs`) and owner-routed propagation.** (depends on all)
  - **Through `/aif-docs`:**
    - `docs/getting-started.md`: the install command (ADR 0015 §6), the `.venv` workflow, running the validators,
      the unit tests, `tools/run_known_good.py` and `tools/check_drift.py`. Remove "not here yet" line L77, correct
      build-order §2's path wording, and update the `.claude/skills` count (29, not 30). Note that regenerating
      `scripts/requirements.txt` needs `uv` (DD13).
    - **Placeholders in every command example:** write `<dgf-root>` and `<plugin>`, never a home path. Section 4 of
      `tools/check-dual-schema-docs.sh` flags `/Users/` and `/home/` in fenced code in every owned Markdown file.
    - `docs/dgf-schemas.md`: §7 is now implemented by `scripts/validate_config.py`; §8's DataSource mapping now
      lives in `knowledge/json-reader.md`; the runtime reader semantics; the XSD-lag policy (ADR 0016); links to
      0014, 0015 and 0016.
    - `docs/architecture.md` and `docs/skill-authoring.md` wherever they describe `scripts/`.
    - `AGENTS.md`: the structure tree (`scripts/`, `tests/`, new `tools/` entries, the two new knowledge files), Key
      Entry Points, and Agent Rules. Cite ADR 0011 from "Both schema families", and 0014/0015 in place of
      0006/0007.
    - `README.md` status.
  - **Owner-routed**, each run through its owning command; never hand-edit these:
    - **`/aif`:** `.ai-factory/DESCRIPTION.md` Current State (`scripts/` built, `tests/`, the new tools), a
      verified-facts row per E2/E9/E15, and the 0006 → 0014 and 0007 → 0015 relinks. Also
      `.ai-factory/rules/base.md` §"DGF Schema Handling": cite ADR 0011; point the parity gate at
      `knowledge/schema-families.md` §6; add the reader-semantics and XSD-lag rules.
    - **`/aif-architecture`:** the `.ai-factory/ARCHITECTURE.md` tree (`scripts/lib/` as built, `tests/` not shipped,
      the two new knowledge files); the code example's comment on the parity gate.
    - **`/aif-roadmap`:** milestone 8's links 0006/0007 → 0014/0015, adding 0016; milestone 10's link 0006 → 0014.
      Record any owner run that cannot happen in this session under Follow-ups, as the previous plan did.

  Files: as reported by `/aif-docs` and the owner commands. Logging: n/a (prose).

<!-- Commit checkpoint: task 21 -->

## Risks

- **The JSON reader rules are the part most likely to be wrong** (ADR 0007's warning, now measured: 183/344 before
  the enum and converter rules). Task 19's "(a) fix or (b) evidenced exception, never a blind exception" rule is the
  guard. A validator that disagrees with the runtime in either direction is a defect.
- **The converter prefix match is order-dependent** (E3). If Task 6 cannot establish which class the runtime picks
  for an ambiguous type, record both in `component-classes` prose and validate against the constructor-bound class.
  It is an upstream report, not a guess.
- **`WORKFLOW_APP_DEPENDENT` and `UNKNOWN_PROPERTY` warnings will be common.** Common warnings get ignored
  (ADR 0010's own consequence). The known-good summary makes the counts visible, so a jump is noticed.
- **Two superseding ADRs in two days.** ADRs 0006 and 0007 were accepted on 2026-09-23. Their successors must restate
  them in full, or `tools/check-dual-schema-docs.sh` §5b and the full-supersession contract fail.
- **The doctor's `DGF_PATH` check scans every shipped file** (E19). A docstring that says "mirrors
  `src/Tools/dgf-mcp/…`" blocks the doctor. Name types and knowledge files.
- **Python 3.9 is end-of-life.** If `uv` resolves a version without 3.9 wheels, pin down and say so. Do not raise the
  floor without an ADR.

## Follow-ups

- **Report upstream to DGF** (maintainer act, not a plan task):
  - `Expert.MoveTaskTo` targets the undeclared `RecordState13`, and `ZIMS4_InspectionBorder` names the absent
    `/InspectionBorderOrOutSide` (E14).
  - `HeaderConfiguration` binds `ComponentType.Footer` (E3).
  - The schemas' `Type` description says lowercase fails, and the runtime accepts it (E5).
  - The MCP serves the NJsonSchema export rather than the System.Text.Json one, and never indexes the DataSource
    schemas (E4, E5).
  - `workflow.xsd` lacks `StateProcess`, `ForeachRecord` and more (E15).
  - `format-coverage.md` labels `_process.xml` and `view.xml` (E16).
  - `zims/FM/_COMPONENTS/Forms/` is read by no loader (E7).
  - Carried forward: `process.xsd` lag and `xs:keyref`; `profile.xsd` L20-21.
- **Per-grammar divergence lists** (ADR 0016), workflow first.
- **Deferred reference checks:** `Process/@table`, `OpenHandler`, `SubProcess` (ADR 0014); component file references
  if Task 14 could not verify them.
- **The developer-facing version gate** (ADR 0013 §4 first table): how it learns a developer's DGF version is still
  undecided.
