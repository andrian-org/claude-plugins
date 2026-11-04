---
dgf_version: "1.1.16"
read_date: 2026-11-04
review_date: 2026-11-04
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
| Modern JSON component config | JSON Schema, one per `IComponentConfiguration` class | DGF's generated JSON schema set, served by the MCP (`list_available_json_schemas`, `get_json_schema_details`) — 71 files, 66 of them indexed (§3) | `schemas/json/` |
| Legacy XML | XSD 1.0, one per artifact grammar | DGF's XSD set, served by the MCP (`list_available_xsd_schemas`, `get_xsd_schema_details`) — 10 files, plus the XML grammar reference `form.reference.json` | `schemas/xsd/` |

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

1. **Glob `*Configuration.schema.json`** — matches 59 of the 71 files. The index key is the
   filename with `Configuration.schema.json` removed, lowercased.
2. **Add the allow-list by exact name** — `StandaloneJsonSchemas = ["componentValidator.schema.json"]`.
   That is the entire list. It is the one hand-authored, cross-cutting contract that is not
   a per-component config.
3. **Add the DataSource kinds by discriminator** — `DataSourceSchemas`, a hand-kept table that
   mirrors the engine's `DataSourceConverter` switch: nine discriminators onto the six
   `<Kind>DataSource.schema.json` files. Each discriminator is its own index key, lowercased, so
   one file can sit under several keys:

   | Discriminators | Schema |
   |---|---|
   | `table`, `lookupTable`, `editableGrid` | `TableDataSource.schema.json` |
   | `api` | `ApiDataSource.schema.json` |
   | `code` | `CodeDataSource.schema.json` |
   | `static` | `StaticOptionsDataSource.schema.json` |
   | `document` | `DocumentDataSource.schema.json` |
   | `rawSql`, `storedProcedure` | `RawSqlDataSource.schema.json` |

   A DataSource entry carries the file stem as a second keyword, so a search for `datasource`
   finds all nine. `DataSourceType.None` has no class and no entry. The full JSON index is therefore
   69 keys over 66 files.
4. **Everything else is unindexed** — 5 files, present in the set but never surfaced as a
   component type:

   | Kind | Files | Why unindexed |
   |---|---|---|
   | `$ref`-only fragments | `RowConfig`, `SectionConfig`, `IDataSource`, `InputGroupConfig` | Not component types; surfacing them would invent bogus components |
   | Stale export | ``NumberConfiguration`1`` | Generic-arity marker leaked from the exporter; unserved. Its filename contains a backtick — quote it |

   All 5 are vendored regardless: a validator resolving `$ref` needs the fragments.

The XSD side needs no rules: `Directory.GetFiles(XSD, "*.xsd")`, non-recursive, registers
all 10.

## 4. Dialect — per file, from its own `$schema`

| Where | Dialect |
|---|---|
| The 70 generated schemas in `schemas/json/` | `http://json-schema.org/draft-04/schema#` |
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
| `application-sitemap.xsd` | `map` | — | None. The legacy application map, `_application.sitemap` (and the per-instance `_application-<instance>.sitemap`) |

**Do not infer a counterpart from a filename.** `options.xsd` is not
`StaticOptionsDataSource.schema.json` — it is the legacy `<options>` list grammar, an
unrelated concept. Nor is `application-sitemap.xsd` the grammar of
`SiteMapConfiguration.schema.json`: that schema is the JSON site map `sitemap.json` under
`_COMPONENTS/`, a different file with a different shape (`routes`, `header`, `footer`), while the
XSD's `<map>` holds the profile tabs and links of `_application.sitemap`. When this table says
none, there is none.

## 6. Runtime parity — a schema existing is not the runtime reading it

*Policy fact. Source: DGF's format-coverage page,
`get_doc_page('AI-Authoring/format-coverage.md')`, a hand-maintained living document stamped
`last_updated: 2026-09-30`. Nothing regenerates it. Re-read it on every
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
| 1 | AutoComplete | `AutoComplete` | `AutoCompleteConfiguration.schema.json` | ✓ | |
| 2 | Badge | `Badge` | `BadgeConfiguration.schema.json` | ✓ | |
| 3 | Booking | `Booking` | `BookingConfiguration.schema.json` | ◐ | Partial — booking workflow still triggers XML workflow steps. |
| 4 | Breadcrumb | `Breadcrumb` | `BreadcrumbConfiguration.schema.json` | ✓ | |
| 5 | Button | `Button` | `ButtonConfiguration.schema.json` | ✓ | |
| 6 | Calendar | `Calendar` | `CalendarConfiguration.schema.json` | ✓ | |
| 7 | Card | `Card` | `CardConfiguration.schema.json` | ✓ | |
| 8 | Carousel | `Carousel` | `CarouselConfiguration.schema.json` | ✓ | |
| 9 | Chart | `Chart` | `ChartConfiguration.schema.json` | ✓ | |
| 10 | Checkbox | `Checkbox` | `CheckboxConfiguration.schema.json` | ✓ | |
| 11 | CodeViewer | `CodeViewer` | `CodeViewerConfiguration.schema.json` | ✓ | |
| 12 | ComboBox | `ComboBox` | `ComboBoxConfiguration.schema.json` | ✓ | |
| 13 | Container | `Container` | `ContainerConfiguration.schema.json` | ✓ | |
| 14 | CorporateAccount | `CorporateAccount` | `CorporateAccountConfiguration.schema.json` | ◐ | Reads JSON; some validation paths still XML-only. |
| 15 | DataFetcher | `DataFetcher` | `DataFetcherConfiguration.schema.json` | ✓ | |
| 16 | DataTable | `DataTable` | `DataTableConfiguration.schema.json` | ✓ | |
| 17 | DatePicker | `Date` | `DatePickerConfiguration.schema.json` | ✓ | |
| 18 | DateTimePicker | `DateTime` | `DateTimePickerConfiguration.schema.json` | ✓ | |
| 19 | EligibilityCriteria | `EligibilityCriteria` | `EligibilityCriteriaConfiguration.schema.json` | ◐ | Reads JSON; underlying file-upload workflow still XML. |
| 20 | Footer | `Footer` | `FooterConfiguration.schema.json` | ✓ | |
| 21 | Form | `Form` | `FormConfiguration.schema.json` | ◐ | **Read** — runtime parses JSON Form config, but most consumer apps still author `_form.xml` because the JSON-form path lacks parity for: custom cells (`control_xxx`), `<slavegrid>` (EditableGrid), some `<binding>` patterns. Wave-1 §4 ships `build_form_xml` to produce XML deterministically while JSON parity matures. |
| 22 | Header | `Header` | `HeaderConfiguration.schema.json` | ✓ | |
| 23 | Icon | `Icon` | `IconConfiguration.schema.json` | ✓ | |
| 24 | Iframe | `Iframe` | `IframeConfiguration.schema.json` | ✓ | |
| 25 | Image | `Image` | `ImageConfiguration.schema.json` | ✓ | |
| 26 | InputGroup | `InputGroup` | `InputGroupConfig.schema.json` | ✓ | |
| 27 | Link | `Link` | `LinkConfiguration.schema.json` | ✓ | |
| 28 | ListBox | `ListBox` | `ListBoxConfiguration.schema.json` | ✓ | |
| 29 | Login | `Login` | `LoginConfiguration.schema.json` | ✓ | |
| 30 | Number | `Number` | `NumberConfiguration.schema.json` | ✓ | |
| 31 | Page | `Page` | `PageConfiguration.schema.json` | ✓ | |
| 32 | PayComponent | `Pay` | `PayComponentConfiguration.schema.json` | ◐ | JSON config consumed; payment-gateway workflow still XML. |
| 33 | PdfViewer | `PdfViewer` | `PdfViewerConfiguration.schema.json` | ✓ | |
| 34 | PhoneNumber | `PhoneNumber` | `PhoneNumberConfiguration.schema.json` | ✓ | |
| 35 | PowerBi | `PowerBi` | `PowerBiConfiguration.schema.json` | ✓ | |
| 36 | ProcessFlow | `ProcessFlow` | `ProcessFlowConfiguration.schema.json` | ✗ | Schema exists but runtime parses legacy `_process.xml`. JSON path planned for Wave 2/3. |
| 37 | ProcessMonitor | `ProcessMonitor` | `ProcessMonitorComponentConfiguration.schema.json` | ✓ | |
| 38 | ProfileMenu | `ProfileMenu` | `ProfileMenuConfiguration.schema.json` | ✓ | |
| 39 | Query | `Query` | `QueryConfiguration.schema.json` | ◐ | Reads JSON for filter panel; SP execution still uses legacy XML datasource configs in some cases. |
| 40 | RadioGroup | `RadioGroup` | `RadioGroupConfiguration.schema.json` | ✓ | |
| 41 | Range | `Range` | `RangeConfiguration.schema.json` | ✓ | |
| 42 | ReferenceComponent | `ReferenceComponent` | `ReferenceComponentConfiguration.schema.json` | ✓ | |
| 43 | RoleSwitcher | `RoleSwitcher` | `RoleSwitcherConfiguration.schema.json` | ✓ | |
| 44 | Route | `Route` | `RouteConfiguration.schema.json` | ✓ | |
| 45 | Router | `Router` | `RouterConfiguration.schema.json` | ✓ | |
| 46 | Row | `Row` | `RowConfig.schema.json` | ✓ | |
| 47 | Section | `Section` | `SectionConfig.schema.json` | ✓ | |
| 48 | SelectButton | `SelectButton` | `SelectButtonConfiguration.schema.json` | ✓ | |
| 49 | Separator | `Separator` | `SeparatorConfiguration.schema.json` | ✓ | |
| 50 | SignaturePadSig100 | `SignaturePadSig100` | `SignaturePadSig100Configuration.schema.json` | ✓ | |
| 51 | SiteMap | — | `SiteMapConfiguration.schema.json` | ✓ | |
| 52 | Tab | `Tab` | `TabConfiguration.schema.json` | ✓ | |
| 53 | TeamSwitcher | `TeamSwitcher` | `TeamSwitcherConfiguration.schema.json` | ✓ | |
| 54 | Text | `Text` | `TextConfiguration.schema.json` | ✓ | |
| 55 | TextArea | `Textarea` | `TextAreaConfiguration.schema.json` | ✓ | |
| 56 | TextBox | `TextBox` | `TextBoxConfiguration.schema.json` | ✓ | |
| 57 | TimePicker | `Time` | `TimePickerConfiguration.schema.json` | ✓ | |
| 58 | Toggle | `Toggle` | `ToggleConfiguration.schema.json` | ✓ | |
| 59 | TreeTable | `TreeTable` | `TreeTableConfiguration.schema.json` | ✓ | |
| 60 | TreeView | `TreeView` | `TreeViewConfiguration.schema.json` | ✓ | |
| 61 | Uploader | `Uploader` | `UploaderConfiguration.schema.json` | ◐ | Reads JSON; large-file workflow + virus scan still XML. |
| 62 | Workflow | `Workflow` | `WorkflowConfiguration.schema.json` | ✗ | Schema exists but runtime parses `_workflow.xml` exclusively. JSON workflow path is the largest remaining migration. |
| 63 | ~~Accordion~~ | — | — | — | |
| 64 | ApiDataSource | — | `ApiDataSource.schema.json` | ✓ | |
| 65 | CodeDataSource | — | `CodeDataSource.schema.json` | ✓ | |
| 66 | DocumentDataSource | — | `DocumentDataSource.schema.json` | ✓ | |
| 67 | RawSqlDataSource | — | `RawSqlDataSource.schema.json` | ✓ | |
| 68 | StaticOptionsDataSource | — | `StaticOptionsDataSource.schema.json` | ✓ | |
| 69 | TableDataSource | — | `TableDataSource.schema.json` | ✓ | |

What each symbol means for a JSON configuration of that component:

| Parity | Meaning |
|---|---|
| `✗` | The schema exists and the runtime does **not** read JSON for this component; it reads the legacy XML. A JSON config that validates is still not read. Schema-valid is not runtime-supported |
| `◐` | The runtime reads the JSON, but the part named in `XML-only part` still runs from XML. Valid and read, not fully migrated |
| `✓` | The runtime reads the JSON in full |

**Rows the page has that no component carries.** Row 51 (`SiteMap`) is the site map file under
`_COMPONENTS/`, rows 64–69 are the DataSource kinds (`json-reader.md` §3), and row 63
(`Accordion`) is struck through on the page: *"Deprecated — no `IComponentConfiguration` schema
exists; removed from SchemaExporter output. Row kept for history."*

**A `✓` row with a limit.** Row 9 (`Chart`) is `✓`, and its note on the page adds *"JSON forms
only."* The runtime reads its JSON in full; the limit is where the component may be placed, not
which format is read, so it is not an `XML-only part`.

**Members the page has no row for.** Eight `ComponentType` members have no parity statement at
all: `Search`, `RadioButton`, `WorkflowNew`, `DropdownTree`, `Option`, `Internal`, `Template` and
`Accordion`. Seven of them have no configuration class (`json-reader.md` §2), and `Accordion`'s row
is struck. Nothing states which format the runtime reads for them.

**The hosted MCP may serve a different copy of the page than the stamped release.** On 2026-09-24
the MCP's copy had 65 rows, without `Carousel` and `SignaturePadSig100`, and numbered them
differently. On 2026-11-04 its copy matched the 69 rows above. The rows and numbers above are the
page as read from DGF's repository at the stamped release.

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
