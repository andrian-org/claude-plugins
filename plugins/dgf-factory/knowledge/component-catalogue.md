---
dgf_version: "1.1.11"
read_date: 2026-09-22
---

# Component catalogue — which components exist, and which count answers which question

Structural facts: stamp only.

## 1. Five counts, five different things

DGF has no single "list of components". It has five, each slicing a different axis, and
they disagree because they measure different things. **Never quote one without saying
which.** In particular, never write "~40" — it matches none of them.

| Count | What it enumerates | Source | Answers |
|---|---|---|---|
| **34** | `IComponentService<TSource>` registrations — components the runtime dispatches to a service | the 34 `RegisterComponentService(` calls across 31 `ConfigureServices.cs` files | *"Which component names does the runtime route a request to?"* — the validator's question |
| **67** | `ComponentType` enum members (excluding `None`) — every type name the runtime recognises, including layout-only types with no service | the `ComponentType` enum | *"Is this a legal `type` value at all?"* |
| **56** | lifecycle-matrix entries | the MCP's lifecycle matrix, `get_component_lifecycle` (`totalCount`) | *"What is this component's lifecycle classification?"* — hand-authored with code citations |
| **59** | showcase examples | the MCP's showcase examples, `get_component_examples` (`componentCount`) | *"Is there a demo of this component?"* — built from the sample app, not from services |
| **66** | components with a generated JSON schema | DGF's format-coverage page, `get_doc_page('AI-Authoring/format-coverage.md')` (67 rows, one struck through) | *"Can its config be schema-validated?"* — see `schema-families.md` |

None of these is published as a derived artifact; the 34 and the 67 are derived by static
read of DGF source, and must be re-derived on re-vendor. The files read, with their digests,
are in the maintainer provenance ledger for this file.

## 2. How registration actually works — two stages, not one

The reflection scan is a **filter**, not the naming source. Both stages live in DGF's
`DGF.Services.Extensions` project:

1. **Explicit registration is the source of truth.** Each component module's
   `ConfigureServices.cs` calls
   `ComponentServiceProvider.RegisterComponentService(nameof(ComponentType.X), typeof(XComponentService))`
   at DI-setup time. This populates the static `Dictionary<string, Type> ComponentServices`
   in `ComponentServiceProvider.cs`, keyed by the `ComponentType` member name.
2. **Reflection only wires what stage 1 already named.** `RegisterComponentServices()` in
   `ConfigureServices.cs` scans `AppDomain.CurrentDomain.GetAssemblies()` for every
   non-abstract class implementing `IComponentService<>`, then:

   ```csharp
   if (ComponentServiceProvider.ComponentServices.ContainsValue(componentServiceType))
       services.AddTransient(componentServiceType);
   else
       Log.Warning("Component service of type {type} has not been registered. Possible it is disabled in configuration", ...);
   ```

   An implementation that exists but was never explicitly registered is **skipped with a
   warning**, not registered. So the 34 explicit calls, not the interface implementers,
   define the dispatchable set. Every current implementer is registered — the two sets match
   1:1 at this `dgf_version`.

## 3. The 34 dispatchable components

Name → service type → registering module, derived from the call sites. Several services are
`partial class` split across two files; each counts once.

| `ComponentType` | Service | Component extension module |
|---|---|---|
| `Booking` | `BookingComponentService` | `DGF.DateTimeComponents` |
| `Calendar` | `CalendarComponentService` | `DGF.Calendar` |
| `Carousel` | `CarouselComponentService` | `DGF.Carousel` |
| `ComboBox` | `ComboBoxComponentService` | `DGF.ComboBox` |
| `CorporateAccount` | `CorporateAccountComponentService` | `DGF.Corporate` |
| `DataFetcher` | `DataFetcherComponentService` | `DGF.DataFetcher` |
| `DataTable` | `DataTableComponentService` | `DGF.DataTable` |
| `EligibilityCriteria` | `EligibilityCriteriaComponentService` | `DGF.Eligibility` |
| `Form` | `FormComponentService` | `DGF.Form` |
| `Iframe` | `IframeComponentService` | `DGF.IFrame` |
| `Image` | `ImageComponentService` | `DGF.ImageComponent` |
| `InputGroup` | `InputGroupComponentService` | `DGF.LayoutComponents` |
| `ListBox` | `ListBoxComponentService` | `DGF.ListBox` |
| `Login` | `LoginComponentService` | `DGF.LoginComponent` |
| `Page` | `PageComponentService` | `DGF.Page` |
| `Pay` | `PayComponentService` | `DGF.PayComponent` |
| `PdfViewer` | `PdfViewerComponentService` | `DGF.PdfViewer` |
| `PowerBi` | `PowerBiComponentService` | `DGF.Reports.PowerBI` |
| `ProcessFlow` | `ProcessFlowComponentService` | `DGF.FlowComponents` (`ProcessFlow`) |
| `ProcessMonitor` | `ProcessMonitorComponentService` | `DGF.FlowComponents` (`ProcessMonitor`) |
| `Query` | `QueryComponentService` | `DGF.Query` |
| `RadioGroup` | `RadioGroupComponentService` | `DGF.FormComponents` |
| `Range` | `RangeComponentService` | `DGF.DateTimeComponents` |
| `ReferenceComponent` | `ReferenceComponentService` | `DGF.ReferenceComponent` |
| `RoleSwitcher` | `RoleSwitcherComponentService` | `DGF.RoleSwitcher` |
| `Router` | `RouterComponentService` | `DGF.Router` |
| `SignaturePadSig100` | `SignaturePadSig100ComponentService` | `DGF.SignaturePadSIG100` |
| `TeamSwitcher` | `TeamSwitcherComponentService` | `DGF.TeamSwitcher` |
| `Text` | `TextComponentService` | `DGF.TextComponents` |
| `TreeTable` | `TreeTableComponentService` | `DGF.DataTable` |
| `TreeView` | `TreeViewComponentService` | `DGF.TreeView` |
| `Uploader` | `UploaderComponentService` | `DGF.Uploader` |
| `Workflow` | `WorkflowComponentService` | `DGF.FlowComponents` (`WorkFlow`) |
| `WorkflowNew` | `WorkflowComponentServiceNew` | `DGF.FlowComponents` (`WorkFlow`) |

Three modules register two components each (`DGF.DataTable`, `DGF.DateTimeComponents`,
`DGF.FlowComponents` (`WorkFlow`)) — hence 34 calls in 31 files.

## 4. The 33 enum members with no service

Legal `type` values the runtime recognises but does **not** dispatch to an
`IComponentService`. They are layout, structural or purely client-side types. A validator
must accept them as types and must not expect a service behind them:

`Accordion` `Badge` `Breadcrumb` `Button` `Card` `Checkbox` `CodeViewer` `Container` `Date`
`DateTime` `DropdownTree` `Footer` `Header` `Icon` `Internal` `Link` `Number` `Option`
`PhoneNumber` `ProfileMenu` `RadioButton` `Route` `Row` `Search` `Section` `SelectButton`
`Separator` `Tab` `Template` `Textarea` `TextBox` `Time` `Toggle`

67 − 34 = 33. `Text`, `Textarea` and `TextBox` are three distinct enum members; only `Text`
has a service.

## 5. Cross-checks a validator should perform

- A `type` not in the 67 → **unknown component**, blocked
- A `type` in the 67 but not in the 34 → **legal, no service**; do not expect dispatch
- A `type` in the 34 → dispatchable; consult `schema-families.md` §6 before claiming its
  JSON config is runtime-read — `Workflow` and `ProcessFlow` are both in the 34 and both `✗`

## See Also

- [`README.md`](README.md) — the stamping convention this file follows
- [`schema-families.md`](schema-families.md) — which of these have schemas, and runtime parity
