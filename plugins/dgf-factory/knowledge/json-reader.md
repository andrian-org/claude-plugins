---
dgf_version: "1.1.11"
read_date: 2026-09-24
---

# JSON reader — how the runtime reads a component JSON file

Structural facts: stamp only. How DGF's runtime turns a JSON file under `FM/_COMPONENTS/` into a
configuration object: which JSON it accepts, how it picks a class for a polymorphic child, and
which folder is read by which loader. The files read are in the maintainer provenance ledger for
this file. Everything here is read from DGF's serializer setup, its converters and its loaders,
never from how the schemas describe the same data.

The generated JSON schemas (`schemas/json/`) and this reader disagree in several places — property
name case, enum form, polymorphic children. Where they disagree, **this file describes what the
runtime does.**

## 1. Reader options

Component JSON is read with System.Text.Json and one options object, set up in DGF's API host
(`ConfigureJsonOptions`) and used both for the registered `JsonSerializerOptions` and for MVC's
`JsonOptions`, which `JsonSerializationService` reads. What it changes about what is **accepted**:

| Setting | Effect on reading |
|---|---|
| `PropertyNameCaseInsensitive = true` | A JSON property binds a member whatever its case: `placeholder`, `Placeholder` and `PLACEHOLDER` are one property. Two keys that differ only in case bind the same member, and one value replaces the other |
| `ReadCommentHandling = Skip` | `//` and `/* */` comments are skipped |
| `IncludeFields = true` | Public fields bind like properties |
| `JsonStringEnumConverter(CamelCase)` | Every enum accepts a member name in any case, or an integer, whatever its schema's `type` says |
| `AllowTrailingCommas` — not set | A trailing comma is a parse error |
| `NumberHandling` — not set | A number written as a string (`"5"`) is not read as a number; only the converters below widen a type |
| `UnmappedMemberHandling` — not set | An unknown property is skipped silently |

A member marked `[JsonIgnore]`, or one without a setter, is never read: a JSON property of that
name is skipped like an unknown one. One leading UTF-8 byte-order mark is ignored.

Registered converters, and the JSON each accepts on reading:

| Converter | Target type | Accepts | Anything else |
|---|---|---|---|
| `BooleanConverter` | `bool`, and `bool?` through the serializer's nullable wrapper | `true` / `false`; a string that `bool.TryParse` accepts — `true` or `false` in any case, surrounding whitespace allowed; any number, non-zero being `true`. `bool?` also accepts `null` | throws, including `null` for a non-nullable `bool` |
| `DateOnlyConverter`, `NullableDateOnlyConverter` | `DateOnly`, `DateOnly?` | `null`; a string `DateTime.TryParse` accepts under the server's current culture | throws |
| `TimeOnlyConverter`, `NullableTimeOnlyConverter` | `TimeOnly`, `TimeOnly?` | `null`; a string `DateTime.TryParse` accepts under the server's current culture | throws |
| `DictionaryJsonConverter` | `Dictionary<string, object>` — among others, every component's `metaData` | `null`, or an object with non-blank keys. Under the key `dataSources` (any case) the value is an object whose every value is a DataSource, read by §3. Under `dataSourceReferences` (any case) it is an array of strings. Any other key takes any value | throws, for a non-object or a blank key |
| `ComponentConverter` | `IComponentConfiguration` | §2 | §2 |
| `DataSourceConverter` | `IDataSource` | §3 | §3 |
| `ObjectParametersConverter` | `List<KeyValuePair<string, object>>` | `null`, or an array of objects with non-blank keys | throws. No component configuration member has this type; it reads request payloads |
| `ComponentModelConverter` | `IComponentModel` | the presentation model, dispatched on `type` like §2 | not used for configuration files |
| `AbstractStepJsonConverter` | `AbstractStep` | a JSON workflow step, dispatched on an exact `type` key against `WorkflowStepType`, like §2 | an unknown step type is dropped |

## 2. Component dispatch

A top-level component file is read as `IComponentConfiguration`, and so is every child whose
member is typed `IComponentConfiguration`. `ComponentConverter` reads it:

1. **The key is exactly `type`.** It is looked up case-sensitively, unlike every other property.
   A component with `Type` and no `type`, or with a blank `type`, throws
   `Component - 'Type' property should be set.` A non-string `type` throws too.
2. **The value is parsed as a `ComponentType`** with `Enum.TryParse(..., ignoreCase: true)`: a
   member name in any case, surrounding whitespace ignored. An integer written as a string selects
   the member with that value. **A value that parses as no member returns `null`: the component
   silently vanishes**, with no error.
3. **The class** is chosen from every loaded type assignable to `IComponentConfiguration` (and not
   to `IComponentModel`), ordered by name within each assembly: the first whose name equals
   `<Type>` or `<Type>Configuration`, ignoring case — **bound by name** — and failing that, the
   first whose name starts with `<Type>` — **bound by prefix**. If none matches, it logs an error
   and returns `null`.
4. The object is then deserialized as that class, with the options in §1. A generic class is
   closed over `double`.

`Bound by` below records which rule selects the class; `none` means no class matches, so the
runtime drops a component of that type. The schema is the vendored file for the selected class.

<!-- machine-read: component-classes -->
| ComponentType | Configuration schema | Bound by |
|---|---|---|
| `Login` | `LoginConfiguration.schema.json` | name |
| `Search` | — | none |
| `Toggle` | `ToggleConfiguration.schema.json` | name |
| `ComboBox` | `ComboBoxConfiguration.schema.json` | name |
| `RadioButton` | — | none |
| `RadioGroup` | `RadioGroupConfiguration.schema.json` | name |
| `Checkbox` | `CheckboxConfiguration.schema.json` | name |
| `Text` | `TextConfiguration.schema.json` | name |
| `Button` | `ButtonConfiguration.schema.json` | name |
| `Image` | `ImageConfiguration.schema.json` | name |
| `Date` | `DatePickerConfiguration.schema.json` | prefix |
| `Time` | `TimePickerConfiguration.schema.json` | prefix |
| `DateTime` | `DateTimePickerConfiguration.schema.json` | prefix |
| `Uploader` | `UploaderConfiguration.schema.json` | name |
| `Page` | `PageConfiguration.schema.json` | name |
| `ListBox` | `ListBoxConfiguration.schema.json` | name |
| `Form` | `FormConfiguration.schema.json` | name |
| `Breadcrumb` | `BreadcrumbConfiguration.schema.json` | name |
| `PdfViewer` | `PdfViewerConfiguration.schema.json` | name |
| `TreeView` | `TreeViewConfiguration.schema.json` | name |
| `Tab` | `TabConfiguration.schema.json` | name |
| `Row` | `RowConfig.schema.json` | prefix |
| `Section` | `SectionConfig.schema.json` | prefix |
| `DataTable` | `DataTableConfiguration.schema.json` | name |
| `Link` | `LinkConfiguration.schema.json` | name |
| `Number` | `NumberConfiguration.schema.json` | prefix |
| `TextBox` | `TextBoxConfiguration.schema.json` | name |
| `Container` | `ContainerConfiguration.schema.json` | name |
| `ProcessFlow` | `ProcessFlowConfiguration.schema.json` | name |
| `Workflow` | `WorkflowConfiguration.schema.json` | name |
| `WorkflowNew` | — | none |
| `Router` | `RouterConfiguration.schema.json` | name |
| `Route` | `RouteConfiguration.schema.json` | name |
| `Icon` | `IconConfiguration.schema.json` | name |
| `Query` | `QueryConfiguration.schema.json` | name |
| `Pay` | `PayComponentConfiguration.schema.json` | prefix |
| `Separator` | `SeparatorConfiguration.schema.json` | name |
| `ReferenceComponent` | `ReferenceComponentConfiguration.schema.json` | name |
| `DropdownTree` | — | none |
| `Option` | — | none |
| `Internal` | — | none |
| `Textarea` | `TextAreaConfiguration.schema.json` | name |
| `Booking` | `BookingConfiguration.schema.json` | name |
| `Range` | `RangeConfiguration.schema.json` | name |
| `EligibilityCriteria` | `EligibilityCriteriaConfiguration.schema.json` | name |
| `CorporateAccount` | `CorporateAccountConfiguration.schema.json` | name |
| `RoleSwitcher` | `RoleSwitcherConfiguration.schema.json` | name |
| `TeamSwitcher` | `TeamSwitcherConfiguration.schema.json` | name |
| `Iframe` | `IframeConfiguration.schema.json` | name |
| `CodeViewer` | `CodeViewerConfiguration.schema.json` | name |
| `SelectButton` | `SelectButtonConfiguration.schema.json` | name |
| `Template` | — | none |
| `PowerBi` | `PowerBiConfiguration.schema.json` | name |
| `Calendar` | `CalendarConfiguration.schema.json` | name |
| `ProcessMonitor` | `ProcessMonitorComponentConfiguration.schema.json` | prefix |
| `Header` | `HeaderConfiguration.schema.json` | name |
| `Footer` | `FooterConfiguration.schema.json` | name |
| `ProfileMenu` | `ProfileMenuConfiguration.schema.json` | name |
| `InputGroup` | `InputGroupConfig.schema.json` | prefix |
| `PhoneNumber` | `PhoneNumberConfiguration.schema.json` | name |
| `TreeTable` | `TreeTableConfiguration.schema.json` | name |
| `Badge` | `BadgeConfiguration.schema.json` | name |
| `Card` | `CardConfiguration.schema.json` | name |
| `Accordion` | — | name |
| `DataFetcher` | `DataFetcherConfiguration.schema.json` | name |
| `SignaturePadSig100` | `SignaturePadSig100Configuration.schema.json` | name |
| `Carousel` | `CarouselConfiguration.schema.json` | name |

Notes on the table:

- **The prefix match can be ambiguous.** `Date` is a prefix of both `DatePickerConfiguration`
  and `DateTimePickerConfiguration`. Both live in the same assembly, which the cache orders by name,
  so `DatePickerConfiguration` comes first; it is also the class whose constructor passes
  `ComponentType.Date` to its base. No other member has more than one prefix candidate.
- **`Number`** binds by prefix because its class is generic, `NumberConfiguration<T>`, whose runtime
  name is ``NumberConfiguration`1``. It is deserialized as `NumberConfiguration<double>`.
- **`Accordion`** has a class, `AccordionConfiguration`, loaded by the API host, but **no generated
  schema**: DGF removed it from the exporter's output and marks the component deprecated.
- **`Header`**: `HeaderConfiguration`'s constructor passes `ComponentType.Footer` to its base. It is
  still selected by name for `Header`. This is an upstream defect.
- 67 members are listed; `None` is omitted. `Template` has no class: a template file is a
  fragment typed by its own `type` (§4).

## 3. DataSource dispatch

A `_COMPONENTS/DataSource/<name>.json` file is read straight to `IDataSource` (`DataSourceLoader`),
and so is every child whose member is typed `IDataSource`, and every value under
`metaData.dataSources`. `DataSourceConverter` reads it:

- **The key is exactly `type`**, case-sensitive. A missing `type` throws; a non-string `type`
  throws.
- The value is parsed as a `DataSourceType` in any case. **An unknown value throws**
  `Invalid or unknown DataSourceType`, and so does `None`, which parses but has no class.

Nine discriminators select six classes:

<!-- machine-read: datasource-discriminators -->
| Discriminator | Schema |
|---|---|
| `Table` | `TableDataSource.schema.json` |
| `LookupTable` | `TableDataSource.schema.json` |
| `EditableGrid` | `TableDataSource.schema.json` |
| `Api` | `ApiDataSource.schema.json` |
| `Static` | `StaticOptionsDataSource.schema.json` |
| `Document` | `DocumentDataSource.schema.json` |
| `RawSql` | `RawSqlDataSource.schema.json` |
| `StoredProcedure` | `RawSqlDataSource.schema.json` |
| `Code` | `CodeDataSource.schema.json` |

DGF's MCP does not index these six schemas (`schema-families.md` §3), so
`validate_component_config` cannot validate a DataSource.

## 4. Component folders

Which loader reads a file under `<workspace>/FM/_COMPONENTS/`, and how the class for the file is
chosen. `Selection` is `by-type` (the file's own `type`, through §2), `by-discriminator` (§3),
`fragment-by-type` (§2, with no folder-to-type relationship) or `none` (no configuration class
reads it).

<!-- machine-read: component-folders -->
| Folder | Loader | Selection |
|---|---|---|
| `DataSource` | `DataSourceLoader` | by-discriminator |
| `Template` | `ComponentFileLoadService.LoadTemplateFromFileAsync` | fragment-by-type |
| `Endpoints` | `EndpointFactory` | none |
| `(root)` | `SiteMapManager` | none |
| `(any other ComponentType name)` | `ComponentFileLoadService.LoadFromFileAsync` | by-type |
| `(unreferenced)` | — | none |

- **A `<Type>/` folder is the requested type.** `ComponentServiceProvider.LoadComponentAsync`
  asks for a component of a given `ComponentType`, and the loader builds
  `_COMPONENTS/<ComponentType>/<path>.json` from the member's own spelling, so the folder name must
  match the member exactly on Linux. The file's `type` then selects the class and the service, so
  a file whose `type` names another member is served as that other type. A `BASE:` prefix on the
  path reads the same folder in `webasm`.
- **`Template/`** holds fragments, each typed by its own `type`, loaded by path from
  `_COMPONENTS/Template/`.
- **`Endpoints/`** is read by `EndpointFactory` into `EndpointSchema`, which has no generated
  schema. A `BASE:` prefix on the endpoint name is removed, and the file falls back to `webasm`'s
  `Endpoints/` when the application has none.
- **`(root)`** — a file directly under `_COMPONENTS/` is a site map, named by the `Sitemap`
  configuration section's `FileName` (`SiteMapOptions`, default `sitemap.json`). `SiteMapManager` parses it with `JsonNode.Parse`,
  so **a comment in a site map is a parse error**, unlike every other component file. It resolves
  reference components before deserializing to `SiteMapConfiguration`, which has no `type`. The
  file falls back to `webasm` when the application has none.
- **`(unreferenced)`** — a folder that is neither a `ComponentType` member's exact name nor one of
  the rows above is read by no loader. The observed case is a `Forms/` folder (plural).
- **`Workflow/`** is a `ComponentType` folder read by the flow-components workflow engine
  (`WorkflowLoaderService`). DGF's format-coverage page nevertheless marks `Workflow` as not read
  from JSON; `schema-families.md` §6 records that row, and the page is the parity authority.

## See Also

- [`README.md`](README.md) — the stamping convention and the machine-read table contract (§7)
- [`schema-families.md`](schema-families.md) — schema resolution and the runtime-parity table
- [`component-catalogue.md`](component-catalogue.md) — the 67 `ComponentType` members and the 34 services
- [`naming-conventions.md`](naming-conventions.md) — the directory names above
