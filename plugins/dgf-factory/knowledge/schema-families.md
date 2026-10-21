---
dgf_version: "1.1.11"
read_date: 2026-09-24
review_date: 2026-09-24
---

# Schema families — how a validator resolves, selects and trusts a DGF schema

DGF configuration comes in **two families**: modern JSON component config, validated by
generated JSON Schemas, and legacy XML, validated by XSDs. A validator that handles one
silently passes everything in the other. This file holds the facts a validator needs to
resolve the family, find the right schema, pick its dialect, and — the part most often
skipped — know whether the runtime actually reads that format for that component.

§1–§5 are **structural** facts: stamp only. §6 is a **policy** fact carrying `review_date`,
because its source is hand-maintained prose that no code regenerates.

## 1. The two families

| Family | Schema form | Where the schemas live | Vendored at |
|---|---|---|---|
| Modern JSON component config | JSON Schema, one per `IComponentConfiguration` class | DGF's generated JSON schema set, served by the MCP (`list_available_json_schemas`, `get_json_schema_details`) — 69 files, 58 of them indexed (§3) | `schemas/json/` |
| Legacy XML | XSD 1.0, one per artifact grammar | DGF's XSD set, served by the MCP (`list_available_xsd_schemas`, `get_xsd_schema_details`) — 9 files, plus the XML grammar reference `form.reference.json` | `schemas/xsd/` |

Neither family is an encoding of the other. Some concepts exist in only one (§5).

## 2. Family detection — resolve before parsing

| Signal in the input | Family |
|---|---|
| XML declaration, or a root element from the table in §5 | XSD |
| Parses as a JSON object | JSON |
| Neither, or both plausible | **Unresolved** — exit `3` |

**Never fall back to JSON.** Defaulting to JSON makes every legacy XML configuration look
like malformed JSON instead of a different format, which is the failure this rule prevents.

## 3. Resolving a JSON schema the way DGF does

The MCP's `SchemaIndexService` does **not** glob `*.schema.json`. A resolver reproduces its selection exactly:

1. **Glob `*Configuration.schema.json`** — matches 57 of the 69 files. The index key is the
   filename with `Configuration.schema.json` removed, lowercased.
2. **Add the allow-list by exact name** — `StandaloneJsonSchemas = ["componentValidator.schema.json"]`.
   That is the entire list. It is the one hand-authored, cross-cutting contract that is not
   a per-component config.
3. **Everything else is unindexed** — 11 files, present in the set but never surfaced as a
   component type:

   | Kind | Files | Why unindexed |
   |---|---|---|
   | `$ref`-only fragments | `RowConfig`, `SectionConfig`, `IDataSource`, `InputGroupConfig` | Not component types; surfacing them would invent bogus components |
   | DataSource kinds | `ApiDataSource`, `CodeDataSource`, `DocumentDataSource`, `RawSqlDataSource`, `StaticOptionsDataSource`, `TableDataSource` | Reached through a discriminator on the authored config, not by schema name |
   | Stale export | ``NumberConfiguration`1`` | Generic-arity marker leaked from the exporter; unserved. Its filename contains a backtick — quote it |

   All 11 are vendored regardless: a validator resolving `$ref` needs the fragments.

The XSD side needs no rules: `Directory.GetFiles(XSD, "*.xsd")`, non-recursive, registers
all 9.

## 4. Dialect — per file, from its own `$schema`

| Where | Dialect |
|---|---|
| The 68 generated schemas in `schemas/json/` | `http://json-schema.org/draft-04/schema#` |
| `componentValidator.schema.json` | `draft-07` — hand-authored, synced into the generated set |
| The 3 contracts in `schemas/standalone/` | `draft-07` |

Select the validator dialect from each file's `$schema`. Never assume one for the set.
`schemas/MANIFEST.md` records the dialect per file.

## 5. Correspondence map — XSD to JSON

Verified root elements, read from the first top-level `xs:element` in each XSD:

<!-- machine-read: correspondence -->
| XSD | Root | JSON counterpart | Relationship |
|---|---|---|---|
| `form.xsd` | `form` | `FormConfiguration.schema.json` | True pair; both have dedicated validators |
| `workflow.xsd` | `Workflow` | `WorkflowConfiguration.schema.json` | Pair — but see §6: runtime reads XML only |
| `process.xsd` | `Process` | `ProcessFlowConfiguration.schema.json` | Pair — but see §6: runtime reads XML only |
| `table-view.xsd`, `lookup-view.xsd`, `grid-form.xsd` | `view` | — | Three subtypes sharing one root; no single JSON counterpart |
| `settings.xsd` | `entity` | — | None. Entity field declarations |
| `options.xsd` | `options` | — | None. Legacy option lists |
| `profile.xsd` | `Tree` | — | None. Profile tree definitions |

**Do not infer a counterpart from a filename.** `options.xsd` is not
`StaticOptionsDataSource.schema.json` — it is the legacy `<options>` list grammar, an
unrelated concept. When this table says none, there is none.

## 6. Runtime parity — a schema existing is not the runtime reading it

*Policy fact. Source: DGF's format-coverage page,
`get_doc_page('AI-Authoring/format-coverage.md')`, a hand-maintained living document stamped
`last_updated: 2026-09-09`. Nothing regenerates it. Re-read it on every
re-vendor and update `review_date`.*

Legend, verbatim from the source: **`✓ supported · ◐ partial · ✗ not supported today`**.

The table holds **every** row of the page's modern-JSON table, in the page's own order and
numbering. `Row` is the page's own name for it. `ComponentType` is the enum member the row
describes, read from `ComponentConverter`'s class selection (`json-reader.md` §2); it is `—` for
the site map, the six DataSource kinds and the struck `Accordion`, which are not dispatched as
components. `Schema` is the vendored file. `Runtime` is the page's symbol. `XML-only part` is the
row's own words for every `◐` and `✗` row.

<!-- machine-read: parity -->
| # | Row | ComponentType | Schema | Runtime | XML-only part |
|---|---|---|---|---|---|
| 1 | Badge | `Badge` | `BadgeConfiguration.schema.json` | ✓ | |
| 2 | Booking | `Booking` | `BookingConfiguration.schema.json` | ◐ | Partial — booking workflow still triggers XML workflow steps. |
| 3 | Breadcrumb | `Breadcrumb` | `BreadcrumbConfiguration.schema.json` | ✓ | |
| 4 | Button | `Button` | `ButtonConfiguration.schema.json` | ✓ | |
| 5 | Calendar | `Calendar` | `CalendarConfiguration.schema.json` | ✓ | |
| 6 | Card | `Card` | `CardConfiguration.schema.json` | ✓ | |
| 7 | Carousel | `Carousel` | `CarouselConfiguration.schema.json` | ✓ | |
| 8 | Checkbox | `Checkbox` | `CheckboxConfiguration.schema.json` | ✓ | |
| 9 | CodeViewer | `CodeViewer` | `CodeViewerConfiguration.schema.json` | ✓ | |
| 10 | ComboBox | `ComboBox` | `ComboBoxConfiguration.schema.json` | ✓ | |
| 11 | Container | `Container` | `ContainerConfiguration.schema.json` | ✓ | |
| 12 | CorporateAccount | `CorporateAccount` | `CorporateAccountConfiguration.schema.json` | ◐ | Reads JSON; some validation paths still XML-only. |
| 13 | DataFetcher | `DataFetcher` | `DataFetcherConfiguration.schema.json` | ✓ | |
| 14 | DataTable | `DataTable` | `DataTableConfiguration.schema.json` | ✓ | |
| 15 | DatePicker | `Date` | `DatePickerConfiguration.schema.json` | ✓ | |
| 16 | DateTimePicker | `DateTime` | `DateTimePickerConfiguration.schema.json` | ✓ | |
| 17 | EligibilityCriteria | `EligibilityCriteria` | `EligibilityCriteriaConfiguration.schema.json` | ◐ | Reads JSON; underlying file-upload workflow still XML. |
| 18 | Footer | `Footer` | `FooterConfiguration.schema.json` | ✓ | |
| 19 | Form | `Form` | `FormConfiguration.schema.json` | ◐ | **Read** — runtime parses JSON Form config, but most consumer apps still author `_form.xml` because the JSON-form path lacks parity for: custom cells (`control_xxx`), `<slavegrid>` (EditableGrid), some `<binding>` patterns. Wave-1 §4 ships `build_form_xml` to produce XML deterministically while JSON parity matures. |
| 20 | Header | `Header` | `HeaderConfiguration.schema.json` | ✓ | |
| 21 | Icon | `Icon` | `IconConfiguration.schema.json` | ✓ | |
| 22 | Iframe | `Iframe` | `IframeConfiguration.schema.json` | ✓ | |
| 23 | Image | `Image` | `ImageConfiguration.schema.json` | ✓ | |
| 24 | InputGroup | `InputGroup` | `InputGroupConfig.schema.json` | ✓ | |
| 25 | Link | `Link` | `LinkConfiguration.schema.json` | ✓ | |
| 26 | ListBox | `ListBox` | `ListBoxConfiguration.schema.json` | ✓ | |
| 27 | Login | `Login` | `LoginConfiguration.schema.json` | ✓ | |
| 28 | Number | `Number` | `NumberConfiguration.schema.json` | ✓ | |
| 29 | Page | `Page` | `PageConfiguration.schema.json` | ✓ | |
| 30 | PayComponent | `Pay` | `PayComponentConfiguration.schema.json` | ◐ | JSON config consumed; payment-gateway workflow still XML. |
| 31 | PdfViewer | `PdfViewer` | `PdfViewerConfiguration.schema.json` | ✓ | |
| 32 | PhoneNumber | `PhoneNumber` | `PhoneNumberConfiguration.schema.json` | ✓ | |
| 33 | PowerBi | `PowerBi` | `PowerBiConfiguration.schema.json` | ✓ | |
| 34 | ProcessFlow | `ProcessFlow` | `ProcessFlowConfiguration.schema.json` | ✗ | Schema exists but runtime parses legacy `_process.xml`. JSON path planned for Wave 2/3. |
| 35 | ProcessMonitor | `ProcessMonitor` | `ProcessMonitorComponentConfiguration.schema.json` | ✓ | |
| 36 | ProfileMenu | `ProfileMenu` | `ProfileMenuConfiguration.schema.json` | ✓ | |
| 37 | Query | `Query` | `QueryConfiguration.schema.json` | ◐ | Reads JSON for filter panel; SP execution still uses legacy XML datasource configs in some cases. |
| 38 | RadioGroup | `RadioGroup` | `RadioGroupConfiguration.schema.json` | ✓ | |
| 39 | Range | `Range` | `RangeConfiguration.schema.json` | ✓ | |
| 40 | ReferenceComponent | `ReferenceComponent` | `ReferenceComponentConfiguration.schema.json` | ✓ | |
| 41 | RoleSwitcher | `RoleSwitcher` | `RoleSwitcherConfiguration.schema.json` | ✓ | |
| 42 | Route | `Route` | `RouteConfiguration.schema.json` | ✓ | |
| 43 | Router | `Router` | `RouterConfiguration.schema.json` | ✓ | |
| 44 | Row | `Row` | `RowConfig.schema.json` | ✓ | |
| 45 | Section | `Section` | `SectionConfig.schema.json` | ✓ | |
| 46 | SelectButton | `SelectButton` | `SelectButtonConfiguration.schema.json` | ✓ | |
| 47 | Separator | `Separator` | `SeparatorConfiguration.schema.json` | ✓ | |
| 48 | SignaturePadSig100 | `SignaturePadSig100` | `SignaturePadSig100Configuration.schema.json` | ✓ | |
| 49 | SiteMap | — | `SiteMapConfiguration.schema.json` | ✓ | |
| 50 | Tab | `Tab` | `TabConfiguration.schema.json` | ✓ | |
| 51 | TeamSwitcher | `TeamSwitcher` | `TeamSwitcherConfiguration.schema.json` | ✓ | |
| 52 | Text | `Text` | `TextConfiguration.schema.json` | ✓ | |
| 53 | TextArea | `Textarea` | `TextAreaConfiguration.schema.json` | ✓ | |
| 54 | TextBox | `TextBox` | `TextBoxConfiguration.schema.json` | ✓ | |
| 55 | TimePicker | `Time` | `TimePickerConfiguration.schema.json` | ✓ | |
| 56 | Toggle | `Toggle` | `ToggleConfiguration.schema.json` | ✓ | |
| 57 | TreeTable | `TreeTable` | `TreeTableConfiguration.schema.json` | ✓ | |
| 58 | TreeView | `TreeView` | `TreeViewConfiguration.schema.json` | ✓ | |
| 59 | Uploader | `Uploader` | `UploaderConfiguration.schema.json` | ◐ | Reads JSON; large-file workflow + virus scan still XML. |
| 60 | Workflow | `Workflow` | `WorkflowConfiguration.schema.json` | ✗ | Schema exists but runtime parses `_workflow.xml` exclusively. JSON workflow path is the largest remaining migration. |
| 61 | ~~Accordion~~ | — | — | — | |
| 62 | ApiDataSource | — | `ApiDataSource.schema.json` | ✓ | |
| 63 | CodeDataSource | — | `CodeDataSource.schema.json` | ✓ | |
| 64 | DocumentDataSource | — | `DocumentDataSource.schema.json` | ✓ | |
| 65 | RawSqlDataSource | — | `RawSqlDataSource.schema.json` | ✓ | |
| 66 | StaticOptionsDataSource | — | `StaticOptionsDataSource.schema.json` | ✓ | |
| 67 | TableDataSource | — | `TableDataSource.schema.json` | ✓ | |

What each symbol means for a JSON configuration of that component:

| Parity | Meaning |
|---|---|
| `✗` | The schema exists and the runtime does **not** read JSON for this component; it reads the legacy XML. A JSON config that validates is still not read. Schema-valid is not runtime-supported |
| `◐` | The runtime reads the JSON, but the part named in `XML-only part` still runs from XML. Valid and read, not fully migrated |
| `✓` | The runtime reads the JSON in full |

**Rows the page has that no component carries.** Row 49 (`SiteMap`) is the site map file under
`_COMPONENTS/`, rows 62–67 are the DataSource kinds (`json-reader.md` §3), and row 61
(`Accordion`) is struck through on the page: *"Deprecated — no `IComponentConfiguration` schema
exists; removed from SchemaExporter output. Row kept for history."*

**Members the page has no row for.** Eight `ComponentType` members have no parity statement at
all: `Search`, `RadioButton`, `WorkflowNew`, `DropdownTree`, `Option`, `Internal`, `Template` and
`Accordion`. Seven of them have no configuration class (`json-reader.md` §2), and `Accordion`'s row
is struck. Nothing states which format the runtime reads for them.

**The hosted MCP may serve an older copy of the page.** On 2026-09-24 the MCP's copy had 65 rows,
without `Carousel` and `SignaturePadSig100`, and numbered them differently. The rows and numbers
above are the page as read from DGF's repository the same day.

Five legacy artifact types have **no JSON path at all**, separate from the `✗` rows above:
`_form.xml`, `_workflow.xml`, `process.xml`, `settings.xml`, and the three view subtypes
(`_view.xml` under `_views/` and `_lookupviews/`, `_grid.xml` under `_gridforms/`). These are the
filenames the runtime loaders open (`naming-conventions.md` §2). Their current generation policy
is recorded in `composition-specs.md`.

**Never state that a component is JSON-capable without this table behind it.** The parity
column in `format-coverage.md` is the only authority; a schema in `schemas/json/` is not.

## Not in this file

How the runtime reads a JSON file — case-insensitive names, enum names, dispatch by `type`, and
the DataSource discriminators — is in `json-reader.md`, not here.

## See Also

- [`README.md`](README.md) — the stamping convention this file follows
- [`schemas/MANIFEST.md`](schemas/MANIFEST.md) — per-file dialect and membership for the vendored set
- [`composition-specs.md`](composition-specs.md) — the five legacy artifacts and the XML-always policy
- [`json-reader.md`](json-reader.md) — how the runtime reads a JSON file, and which class each `ComponentType` binds
