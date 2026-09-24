---
name: integrate-shared
description: Expose ZamConnect shared e-Services (NIR, NBR/PACRA, DOC, SRS, ZDI, NLR, ZDA, NAIR, ZRA, MOH) on a tenant by wiring `EServicesShared` through the API gateway. Scans `src/Core/Shared/Services/EServicesShared.cs` for the available operations and drives an interactive menu to pick sources and endpoints, then generates the Carter module, registration, and gateway `appsettings` section. Use when the user says "add NIR lookup to <Tenant>", "expose shared e-services on <Tenant>", "give <Tenant> access to PACRA/ZRA/ZDI", "which shared endpoints are available", or types /integrate-shared.
argument-hint: "[<TenantName>] [--source NIR|NBR|DOC|SRS|ZDI|NLR|ZDA|NAIR|ZRA|MOH ...] [--endpoint <key> ...] [--base-path <path>] [--tag EServices] [--mode inherit|common|routes] [--dto shared|tenant] [--all] [--new] [--list] [--auto] [--dry-run]"
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(mkdir *) Bash(dotnet *) AskUserQuestion Skill
disable-model-invocation: false
---

# Integrate Shared e-Services into a Tenant

`EServicesShared` (`src/Core/Shared/Services/EServicesShared.cs`) is the single client for every e-Service reachable through the ZamConnect API gateway. A tenant does not re-implement those calls — it injects `EServicesShared` and republishes the subset of operations it is entitled to.

This skill selects that subset interactively and generates the wiring.

All paths below are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`). Resolve it once and never write an absolute path into generated code, config, or the report.

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Every option is a complete answer (R12). The catalogue holds more than 4 sources, so the menus group first and drill down after (R9).

Shared facts — usings/namespace (C1), `Error` → status (C2), `Username` casing (C3), token naming (C4), Carter DI lifetime (C5), file hygiene (C6), committed-secrets baseline (C7), live routes doc (C8) — live in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`. Read it before generating; this skill cites section ids instead of repeating them.

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Target tenant folder `src/Tenants/<TenantName>/`. Prompted from a menu if omitted |
| `--source <SYS>` | Pre-select one or more upstream systems; repeatable. Skips the source menu |
| `--endpoint <key>` | Pre-select individual operations by catalogue key; repeatable. Skips the endpoint menu |
| `--base-path <path>` | Route group prefix. **Default: none** — routes sit at the tenant root. Pass one only when the tenant already groups its own surface under a prefix, or its gateway route transforms onto one (step 6) |
| `--tag <Tag>` | Swagger tag for the group. Default `EServices` |
| `--mode <mode>` | `inherit` \| `common` \| `routes`. Default chosen per step 4. `inherit` is refused unless the selection is exactly the `EServicesSharedModule` route set |
| `--dto shared\|tenant` | Return the shared response models, or tenant DTOs plus a mapper. Default `shared` |
| `--all` | Every operation from the step 1 rescan, in `routes` mode. Not `inherit` — `EServicesSharedModule` maps only a subset |
| `--new` | Tenant does not exist yet; scaffold it with `tenant-init` first |
| `--list` | Print the catalogue (step 1) and stop. No files written |
| `--gate <n>/<N>`, `--recommend proceed\|skip` | Gate mode, set by `tenant-pipeline` |
| `--auto` | No questions. Uses `--source` / `--endpoint` / `--all` as given; with none of them, stops with `missing --source <SYS> or --all` |
| `--dry-run` | Stop at the confirmation in step 3 and write nothing |

`--source` and `--endpoint` combine: sources expand to all their operations, then `--endpoint` adds individual ones.

## Gate

Only with `--gate <n>/<N>`. Run the step 3 prerequisites first; if one stops the skill, print the reason and emit `GATE-RESULT: failed <reason>` without asking. Otherwise **one** `AskUserQuestion` call holds the gate and, unless `--source`, `--endpoint` or `--all` was passed, the group question from 3b (R4). Which e-Services to expose has no default.

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/integrate-shared <T>` — republish shared e-Services (NIR, PACRA, ZRA…) on this tenant through `EServicesShared`. Run it? | `Proceed` — every operation of the groups picked below, `routes` mode, tag `EServices`, no base path, shared response models · `Customize…` — also choose operations, Swagger tag, module mode, response models · `Skip` · `Stop` |
| `e-Services` | The 3b group question | the four groups |

`(Recommended)` goes on `Proceed` with `--recommend proceed`, and on `Skip` with `--recommend skip`. The option order doesn't change. `Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`.

With `Proceed`, skip 3c and 3d: every operation of the picked groups is exposed in `routes` mode (whole groups never equal the `inherit` route set), and step 3's confirmation shows them. With `Customize…`, ask 3c and 3d as well.

## 1. Rescan the catalogue

Never answer from the table in step 2 alone — `EServicesShared` changes. Rebuild the list first:

```bash
grep -nE '^    #(end)?region|public async Task<Result' src/Core/Shared/Services/EServicesShared.cs
grep -nE 'gateway\.(Get|Post|Patch|Put|Delete)' src/Core/Shared/Services/EServicesShared.cs
grep -nE 'group\.Map(Get|Post|Patch|Put|Delete)' src/Core/Shared/Modules/EServicesSharedModule.cs
grep -n 'public static' src/Core/Shared/Mapper/EServicesSharedMappingExtensions.cs
ls src/Core/Shared/Models/
```

- Top-level `#region`s sit at exactly 4 spaces; the pattern skips helper regions nested inside methods (ZRA has several). One region can hold several systems — `PACRA` holds NBR, DOC and SRS — so split by the upstream path segment (`/t/ndw/<sys>/…`), not by region name.
- Each `public async Task<Result<...>>` is one operation; the `gateway.*` call below it gives the real upstream path.
- The `EServicesSharedModule` grep is the `inherit` route set (step 4) — re-derive it, never assume it.
- In `Models/`, ignore `NDR/` and `NDW/`: `EServicesShared` returns neither, and `NDR/DOC/DocAddress` duplicates a shared name.

Reconcile with step 2 and report any operation present in the file but missing from the table — then include it in the menu anyway.

## 2. Catalogue

Rebuilt from `EServicesShared(Gateway gateway, IOptions<JsonSerializerOptions> jsonOptions)`. Rescan first (step 1); this table is a snapshot. Mappers live in `Shared.Mapper.EServicesSharedMappingExtensions`, models in `Shared.Models.<SYS>`. Generic operations (`<TResponse, TSource>`) let the tenant substitute its own response DTO — default to the shared one unless the tenant already declares its own under `src/Tenants/<TenantName>/Models/`.

| Key | Suggested tenant route | Upstream (via gateway) | Returns · `TSource` → `TResponse` / `map` | Gateway scope |
|---|---|---|---|---|
| `nir.person.document` | `GET /nir/persons/identity-document?documentNumber=&documentTypeId=&documentCountry=` | POST `/t/ndw/graphql` | `Result<PersonResponse>` | `ndw` |
| `nir.person.nrc` | `GET /nir/persons/nrc/{nrc}` | POST `/t/ndw/graphql` | `Result<PersonResponse>` | `ndw` |
| `nir.person.zampass` | `GET /nir/persons/zampass/{zamPassId:guid}` | POST `/t/ndw/graphql` | `Result<PersonResponse>` | `ndw` |
| `nir.person.create` | `POST /nir/persons` | POST `/t/ndw/nir/persons` | `Result<NirPerson>` → `201` + `PersonCreatedResponse { Id }` | `ndw` |
| `nir.person.update` | `PATCH /nir/persons/{id:guid}` | PATCH `/t/ndw/nir/persons/{id}` | `Result<string>` → `202` | `ndw` |
| `nir.person.update-zampass` | `PATCH /nir/persons/zampass/{zamPassId:guid}` | PATCH `/t/ndw/nir/persons/zampass/{zamPassId}` | `Result<string>` → `202` | `ndw` |
| `nbr.entity` | `GET /nbr/entities/{registrationNumber}` | GET `/t/ndw/nbr/entities/query?entityNumber=&usePacraService=` | `BusinessEntity` → `BusinessEntityResponse` / `ToBusinessEntityResponse()` | `ndw-nbr` |
| `doc.cooperative` | `GET /doc/entities/{registrationNumber}` | GET `/t/ndw/doc/entities?registrationNumber=` | `Cooperative` → `CooperativeResponse` / `ToCooperativeResponse()` | `ndw-doc` |
| `srs.society` | `GET /srs/entities/{registrationNumber}` | GET `/t/ndw/srs/entities?entityNumber=` | `Society` → `SocietyResponse` / `ToSocietyResponse()` | `ndw-srs` |
| `zdi.permit` | `GET /zdi/permits/{permitNumber}` | GET `/t/ndw/zdi/permits?permitNumber=` | `Permit` → `PermitResponse` / `ToPermitResponse()` | `ndw-zdi` |
| `zdi.permits.passport` | `GET /zdi/permits?passportNumber=&returnOnlyActivePermits=&page=&pageSize=` | GET `/t/ndw/zdi/permits?passportNumber=&returnOnlyActivePermits=&page=&pageSize=` | paginated: `PaginatedResult<Permit>` → `PaginatedResult<PermitResponse>` / `src => src.MapItems(p => p.ToPermitResponse())` | `ndw-zdi` |
| `zdi.passport` | `GET /zdi/passports?passportNumber=&passportCountryCode=` | GET `/t/ndw/zdi/permits?passportNumber=&passportCountryCode=` | `Permit` → no shared passport model; `PermitResponse` / `ToPermitResponse()` or a tenant DTO | `ndw-zdi` |
| `zdi.immigrant.passport` | `GET /zdi/immigrants?passportNumber=` | GET `/t/ndw/zdi/people?passportNumber=` | `Immigrant` → `ImmigrantResponse` / `ToImmigrantResponse()` | `ndw-zdi` |
| `zdi.immigrant.permit` | `GET /zdi/immigrants?permitNumber=` | GET `/t/ndw/zdi/people?permitNumber=` | `Immigrant` → `ImmigrantResponse` / `ToImmigrantResponse()` | `ndw-zdi` |
| `nlr.lot` | `GET /nlr/lots/{propertyNumber}` | GET `/t/ndw/nlr/lots/query?propertyNumber=` | `Lot` → `LotResponse` / `ToLotResponse()` | `ndw-nlr` |
| `zda.permits` | `GET /zda/permits?entityNumber=&page=&pageSize=` | GET `/t/ndw/zda/permits?entityNumber=&page=&pageSize=` + `/t/ndw/zda/sector-types` | paginated: `PaginatedResult<Permit>` → `PaginatedResult<PermitResponse>` / `(permits, sectors) => permits.MapItems(p => p.ToPermitResponse(sectors))` | `ndw-zda` |
| `nair.student` | `GET /nair/students/{legalId}?countryCode=` | POST `/t/ndw/nair/students/search` | `NairStudent` → `Student` / `ToStudent()` | `ndw-nair` |
| `zra.tcc` | `GET /zra/taxpayers/tcc?tpin=&nrc=&brn=` | GET `/t/zra/Tcc/get-taxpayer-tcc?Tpin=` (+ `GetTaxpayer` when `tpin` is empty) | `Result<TaxClearanceCertificateResponse>` | `zra` + `zra-portal` |
| `zra.taxpayer` | `GET /zra/taxpayers?tpin=&taxpayerName=&nrc=&brn=` | POST `/t/zra/portal/retrieveTaxpayersSearch` | `Result<List<TaxpayerResponse>>` | `zra-portal` |
| `moh.facilities` | `GET /moh/facilities?name=&page=&pageSize=` | GET `/t/ndw/moh/facilities?name=&page=&pageSize=` | paginated: `PaginatedResult<Facility>` → `PaginatedResult<FacilityResponse>` / `f => f.MapItems(x => x.ToFacilityResponse())` | `ndw-moh` |

Scopes come from `docs/zamconnect-test-routes.md` (C8): the gateway route that matches each upstream path. Re-check them there when the rescan finds a new path.

Signatures — parameter order matters; `cancellationToken` is not always last-but-one:

```csharp
GetPersonByIdentityDocument(string documentNumber, int documentType = 1, string documentCountry = "ZMB", CancellationToken cancellationToken = default)
GetPersonByNrc(string nrc, CancellationToken cancellationToken = default)
GetPersonByZamPassId(Guid zamPassId, CancellationToken cancellationToken = default)
CreatePerson(NirPersonAddRequest model, CancellationToken cancellationToken)
UpdatePerson(Guid id, NirPersonUpdateRequest model, CancellationToken cancellationToken)
UpdatePersonByZamPassId(Guid zamPassId, NirPersonUpdateRequest model, CancellationToken cancellationToken)
GetEntityByRegistrationNumber<TResponse, TSource>(string registrationNumber, Func<TSource, TResponse> map, CancellationToken cancellationToken = default, bool usePacraService = true)
GetCooperativeByRegistrationNumber<TResponse, TSource>(string registrationNumber, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetSocietyByRegistrationNumber<TResponse, TSource>(string registrationNumber, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetZdiPermitByPermitNumber<TResponse, TSource>(string permitNumber, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetZdiPermitsByApplicantPassportNumber<TResponse, TSource>(string applicantPassportNumber, Func<TSource, TResponse> map, bool returnOnlyActivePermits = false, int page = 0, int pageSize = 10, CancellationToken cancellationToken = default)
GetZdiImmigrantByPassportNumber<TResponse, TSource>(string passportNumber, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetZdiImmigrantByPermitNumber<TResponse, TSource>(string permitNumber, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetZdiPassportDetails<TResponse, TSource>(string passportNumber, string passportCountryCode, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetLotByPropertyNumber<TResponse, TSource>(string propertyNumber, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetZdaPermitsByEntityNumber<TResponse, TSource>(string entityNumber, Func<TSource, List<SectorsType>, TResponse> map, int page = 0, int pageSize = 10, CancellationToken cancellationToken = default)
GetStudentByLegalId<TResponse, TSource>(string legalId, string countryCode, Func<TSource, TResponse> map, CancellationToken cancellationToken = default)
GetTaxpayerTcc(string tpin, string nrc, string brn, CancellationToken cancellationToken = default)
GetTaxpayer(string tpin = "", string taxpayerName = "", string nrc = "", string brn = "", CancellationToken cancellationToken = default)
GetMohFacilitiesByName<TResponse, TSource>(string name, Func<TSource, TResponse> map, int page = 0, int pageSize = 10, CancellationToken cancellationToken = default)
```

Failure statuses each operation can produce through `CustomResults.Problem` (C2) — declare exactly these with `.Produces(...)`:

| Operations | Statuses |
|---|---|
| NIR lookups, `nbr.entity`, `doc.cooperative`, `srs.society`, `zdi.permit`, `zdi.passport`, `zdi.immigrant.*`, `nlr.lot` | 404, 500 (multiple matches is `Error.Problem` → 500) |
| `nir.person.create` | 400 (upstream validation), 404, 409, 500 |
| `nir.person.update`, `nir.person.update-zampass` | 404, 409, 500 |
| `nair.student` | 404, 409, 500 (an upstream 400 arrives as `ProblemDetails`, mapped to 500) |
| `zra.tcc`, `zra.taxpayer` | 400 (search-criteria validation), 404, 500 |
| `zdi.permits.passport`, `zda.permits`, `moh.facilities` | 500 only in practice — an empty result is 200 with empty `Items`; an upstream 404 becomes 500 |

Notes:

- **NIR create/update.** The public route takes the shared request `PersonAddRequest` / `PersonUpdateRequest` (`Shared.Models.NIR.Common.Requests.Person`) and converts with `.ToNirPersonAddRequest()` / `.ToNirPersonUpdateRequest()` before calling the service — the MCTI, DOC and ZIMS pattern. `cancellationToken` has no default on these three. Shared `CreatePerson` does not forward an explicit person `Id` (only GOVZM's own PKI path does); say so in the report when `nir.person.create` is selected.
- **NRC.** `GetPersonByNrc` URL-decodes `nrc` itself. Pass the route value as received; don't decode again.
- **ZDI vs ZDA name clash.** Both namespaces declare `Permit` and `PermitResponse`. When both are selected, alias them the way `EServicesSharedMappingExtensions.cs` does (`using ZdiPermit = Shared.Models.ZDI.Permit;`, `ZdiPermitResponse`, `ZdaPermit`, `ZdaPermitResponse`) — an unqualified name with both namespaces imported is `CS0104`.
- **`zdi.passport`** has no shared response model (`PassportResponse` exists only in MSMS). Under `--dto shared` return `PermitResponse`; a passport-shaped contract needs a tenant DTO — follow `src/Tenants/MSMS/Models/ZDI/PassportResponse.cs`.
- **`zdi.immigrant.passport` + `zdi.immigrant.permit`** share one route in `src/Tenants/MCTI/Modules/CommonModule.cs` and `src/Tenants/DOC/Modules/CommonModule.cs`, branching on which query value is present. Generate that single `GET /zdi/immigrants` when both are selected.
- **`zda.permits`** takes `Func<TSource, List<SectorsType>, TResponse>`; the service fetches the sector types itself and passes them in.
- **ZRA.** `zra.tcc` and `zra.taxpayer` are non-generic. Both resolve a TPIN from NRC or BRN when `tpin` is empty, so expose all identifiers as optional query parameters. `GetTaxpayer` rejects zero or more than one identifier with 400.
- **Known upstream bug — note, don't fix.** `GetCooperativeByRegistrationNumber` deserializes the whole response document instead of `items[0]` when the upstream returns an `items` array, so `doc.cooperative` can map an empty object. Mention it in the report when `doc.cooperative` is selected.

## 3. Interactive menu

Skip any step whose answer arrived as an argument. Use `AskUserQuestion`, one question at a time so each answer narrows the next.

**3a — Tenant.** Only if `<TenantName>` is absent:

```bash
ls src/Tenants
grep -rln "EServicesShared" src/Tenants --include=Program.cs
```

Offer the tenants that already inject `EServicesShared` first (extending an existing integration), then the rest. A tenant not in `src/Tenants` means `--new` — run `tenant-init` before continuing.

**Prerequisites.** Once the tenant is known — before 3b, before the gate question, and under `--auto` too:

```bash
grep -nE 'AddCarter|MapCarter|Configure<JsonSerializerOptions>|PropertyNameCaseInsensitive|RegisterGatewayEndpoint|AddTransient<EServicesShared>' src/Tenants/<TenantName>/Program.cs
grep -n 'Shared.csproj' src/Tenants/<TenantName>/<TenantName>.csproj
grep -nE '<ImplicitUsings>|<Nullable>' src/Tenants/<TenantName>/<TenantName>.csproj
grep -rlnE 'class Gateway\b' src/Tenants/<TenantName> --include=*.cs
ls src/Tenants/<TenantName>/Controllers src/Tenants/<TenantName>/Modules src/Tenants/<TenantName>/Mapper
```

| Finding | Action |
|---|---|
| No `AddCarter()` / `MapCarter()` — a controllers tenant | The generated module never gets mapped. Ask `Add Carter alongside the controllers (Recommended)` · `Stop`. Adding means step 5's Carter lines; `Carter` arrives transitively through `Shared.csproj`. `--auto` and gate mode stop with `no Carter in <TenantName>` |
| No `Configure<JsonSerializerOptions>` with `PropertyNameCaseInsensitive = true` | `EServicesShared` deserializes with that `IOptions<JsonSerializerOptions>` instance; without it the upstream camelCase JSON binds to nulls. Add it in step 5 |
| No `Shared.csproj` reference | Add it in step 5 |
| Tenant declares its own `Gateway` class | It reads the same `Endpoints:Gateway` section as `Shared.Endpoints.Gateway` (registration keys on the class name). Confirm both target the ZamConnect gateway with the tenant's credentials, and fully qualify `Shared.Endpoints.Gateway` in any code that names it |
| `ImplicitUsings` / `Nullable` | Drives the generated `using` block and `string?` usage (C1) |

**3b — Groups.** Header `e-Services`, `multiSelect: true`. The regions don't fit in 4 options, so group them. Take the counts from the step 1 rescan, not from this example:

| Option | Covers |
|---|---|
| `Identity — NIR (6 operations)` | NIR |
| `Business registries — NBR, DOC, SRS (3)` | NBR / PACRA, cooperatives, societies |
| `Immigration — ZDI (5)` | permits, immigrants, passports |
| `Land, tax, health, education — NLR, ZDA, ZRA, MOH, NAIR (6)` | the rest |

A system the rescan finds that isn't in this table joins the last group, with its name added to the label. The question text says "Pick every group you need; each one is expanded to its operations next". There is no `All sources` option: picking all four groups means the same thing, and sets `--all`.

**3c — Operations.** Asked under `Customize…`, or without a gate when no `--endpoint` was passed. `multiSelect: true` over the operations of the chosen groups, each option labelled `METHOD /route — purpose` (`GET /nir/persons/nrc/{nrc} — person by NRC`). One question per group, at most 4 questions per call (R9). A group with more than 4 operations shows 3 plus `All <n> <group> operations`, which selects the rest. The question text says that only the ticked operations are exposed.

**3d — Placement.** `Customize…` only, one call:

| Header | Options |
|---|---|
| `Tag` | `EServices (Recommended)` · the tag the tenant's existing modules already use, if there is one |
| `Mode` | The step 4 default `(Recommended)` · the other modes that step 4 allows for this selection, each with its one-line "use when" |
| `Models` | `Shared response models (Recommended)` · `Tenant DTOs + mapper` |
| `Base path` | Only when the tenant's existing modules already group under a prefix: `None (Recommended)` · that prefix |

Then one R6 confirmation. The question text is the table — key, method, route, response model, required gateway scope — plus the files to write and the equivalent command. Options `Apply (Recommended)` · `Adjust` · `Cancel`. `Adjust` re-asks whichever of 3b, 3c or 3d is picked. With `--dry-run`, print it and stop.

## 4. Choose the module mode

| Mode | Shape | Use when |
|---|---|---|
| `inherit` | `public class EServicesModule(EServicesShared services) : EServicesSharedModule("EServices", services);` | The selection is **exactly** the routes `EServicesSharedModule.AddRoutes` maps (step 1 grep — currently the six NIR operations, `nbr.entity` and `zra.tcc`). Canonical one-liner: `src/Tenants/ZPS/Modules/EServicesModule.cs`. The two-argument constructor has no base path; `src/Tenants/GOVZM/Modules/EServicesModule.cs` passes `"/eservices"` to the three-argument one, which is the exception |
| `common` | Abstract `CommonModule` in the tenant holding the selected routes plus a `protected virtual void AddAdditionalRoutes(RouteGroupBuilder group)` hook, with one thin concrete module per consumer | The tenant publishes the same subset under several base paths or tags. The hook pattern is `src/Tenants/MCTI/Modules/CommonModule.cs` (concrete `ZabsModule`, `ZmaModule`). `src/Tenants/DOC/Modules/CommonModule.cs` has no hook and one concrete module — cite it for route shapes only |
| `routes` | One plain `ICarterModule` with only the selected routes | Any other selection, including `--all`. The default |

Default to `inherit` only when the selection equals the `inherit` route set, `common` when the tenant already has a `CommonModule`, otherwise `routes`.

`EServicesSharedModule` is all-or-nothing — it maps its full route set and nothing else. Never subclass it to expose a subset, and never pick `inherit` for a selection containing an operation it doesn't map; generate the routes instead.

In `inherit` mode the module body stays empty. `EServicesSharedModule.AddRoutes` already does `app.MapGroup(basePath).WithTags(tags)` and maps its routes onto it, so the tenant module must not declare `var group = app.MapGroup("").WithTags("EServices");` or map anything itself — the base path and tag are the constructor arguments. Only `routes` and `common` mode create the group.

## 5. Wire the tenant

**`src/Tenants/<TenantName>/<TenantName>.csproj`** — must reference `Shared`:

```xml
<ProjectReference Include="..\..\Core\Shared\Shared.csproj" />
```

**`src/Tenants/<TenantName>/Program.cs`** — add what the prerequisites found missing:

```csharp
builder.Services.Configure<JsonSerializerOptions>(options => options.PropertyNameCaseInsensitive = true);
builder.Services.AddCarter();
// next to the existing RegisterEndpoints call:
builder.Services.RegisterGatewayEndpoint(builder.Configuration);
builder.Services.AddTransient<EServicesShared>();
// after app is built:
app.MapCarter();
```

with `using Carter;`, `using Shared.Extensions;`, `using Shared.Services;` and `using System.Text.Json;` where missing. If `Configure<JsonSerializerOptions>` already exists, add `PropertyNameCaseInsensitive = true` inside it rather than a second call. `RegisterGatewayEndpoint` registers the `Gateway` client from the `Shared` assembly; the tenant's own `RegisterEndpoints(Assembly.GetExecutingAssembly(), ...)` does not see it. Both calls are needed when the tenant also has its own `Endpoints/`.

**`appsettings.json` and `appsettings.Development.json`** — the gateway section. The key must be exactly `Gateway`, matching the class name `Shared.Endpoints.Gateway`. A missing or misnamed section logs `Endpoint Gateway is not configured`, `Gateway` is never registered, and the app fails at `MapCarter()` with `Unable to resolve service for type 'Shared.Endpoints.Gateway'` while activating `EServicesShared` — a startup crash, not a silent no-op.

```json
"Endpoints": {
    "Gateway": {
        "AuthenticationScheme": "Basic",
        "BaseUrl": "__Endpoints.APIGATEWAY.BaseUrl__",
        "Username": "__Credentials.<TenantName>Tenant.Username__",
        "Password": "__Credentials.<TenantName>Tenant.Password__"
    }
}
```

- JSON key and token are `Username`, never `UserName` (C3).
- Token names follow C4 (tenant calling back into the gateway); `<TenantName>` is the exact folder name. Each new token needs a variable in `GSB.<TENANT>.<ENV>` and in the `projects-variables` repo, or the deploy fails.
- In `appsettings.Development.json` the `BaseUrl` may be the real test gateway; credentials stay `__Token__` placeholders. Never copy a value from another tenant's Development file (C7).
- If the tenant already has other `Endpoints` entries, add `Gateway` as a sibling — do not replace the object.

## 6. Generate the module

`src/Tenants/<TenantName>/Modules/EServicesModule.cs` for `routes` and `inherit`; `CommonModule.cs` plus concrete modules for `common`. New `.cs` files follow C6.

The `MapGroup` below belongs to `routes` and `common` mode only. An `inherit` module has no `AddRoutes` override at all — mapping the group there would duplicate the shared route set.

**No base path by default.** The group exists to carry the Swagger tag, not to add a segment. A tenant's own gateway route (`t_<slug>` → `/t/<slug>/{**url}`, transform `/{**url}`) forwards the remainder unchanged, so `nir.person.nrc` is served at `/t/<slug>/nir/persons/nrc/{nrc}`. A prefix is right only when a gateway route maps onto it: GOVZM serves under `/eservices` because agency routes such as `t_dam_eservices` (`/t/dam/{**url}`) point at the GOVZM cluster and the gateway transform adds the prefix. Look up the tenant's route in `docs/zamconnect-test-routes.md` (C8) before choosing.

`routes` mode, ImplicitUsings off (C1) — full `using` block and file-scoped namespace. Keep only the usings the selected routes need; add `using System;` when a route binds `Guid`:

```csharp
using System.Threading;
using Carter;
using Internal.Domain.Shared.Result;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Routing;
using Shared.Mapper;
using Shared.Models.NBR;
using Shared.Models.NIR;
using Shared.Models.NIR.Common.Requests.Person;
using Shared.Models.ZDA;
using Shared.Services;
using Shared.Types;

namespace <TenantName>.Modules;

public class EServicesModule(EServicesShared services) : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("").WithTags("EServices");

        group.MapGet("/nir/persons/nrc/{nrc}",
                async (string nrc, CancellationToken cancellationToken) =>
                {
                    var result = await services.GetPersonByNrc(nrc, cancellationToken);
                    return result.IsSuccess ? Results.Ok(result.Value) : CustomResults.Problem(result);
                })
            .Produces(StatusCodes.Status200OK, typeof(PersonResponse))
            .Produces(StatusCodes.Status404NotFound, typeof(ProblemDetails))
            .Produces(StatusCodes.Status500InternalServerError, typeof(ProblemDetails));

        group.MapPost("/nir/persons",
                async (PersonAddRequest model, CancellationToken cancellationToken) =>
                {
                    var result = await services.CreatePerson(model.ToNirPersonAddRequest(), cancellationToken);
                    return result.IsSuccess
                        ? Results.Created(string.Empty, new PersonCreatedResponse { Id = result.Value.Id })
                        : CustomResults.Problem(result);
                })
            .Produces(StatusCodes.Status201Created, typeof(PersonCreatedResponse))
            .Produces(StatusCodes.Status400BadRequest, typeof(ProblemDetails))
            .Produces(StatusCodes.Status404NotFound, typeof(ProblemDetails))
            .Produces(StatusCodes.Status409Conflict, typeof(ProblemDetails))
            .Produces(StatusCodes.Status500InternalServerError, typeof(ProblemDetails));

        group.MapGet("/nbr/entities/{registrationNumber}",
                async (string registrationNumber, CancellationToken cancellationToken) =>
                {
                    var result = await services
                        .GetEntityByRegistrationNumber<BusinessEntityResponse, BusinessEntity>(
                            registrationNumber, e => e.ToBusinessEntityResponse(), cancellationToken);
                    return result.IsSuccess ? Results.Ok(result.Value) : CustomResults.Problem(result);
                })
            .Produces(StatusCodes.Status200OK, typeof(BusinessEntityResponse))
            .Produces(StatusCodes.Status404NotFound, typeof(ProblemDetails))
            .Produces(StatusCodes.Status500InternalServerError, typeof(ProblemDetails));

        group.MapGet("/zda/permits",
                async (string entityNumber, CancellationToken cancellationToken, int page = 0, int pageSize = 10) =>
                {
                    var result = await services
                        .GetZdaPermitsByEntityNumber<PaginatedResult<PermitResponse>, PaginatedResult<Permit>>(
                            entityNumber,
                            (permits, sectors) => permits.MapItems(p => p.ToPermitResponse(sectors)),
                            page, pageSize, cancellationToken);
                    return result.IsSuccess ? Results.Ok(result.Value) : CustomResults.Problem(result);
                })
            .Produces(StatusCodes.Status200OK, typeof(PaginatedResult<PermitResponse>))
            .Produces(StatusCodes.Status500InternalServerError, typeof(ProblemDetails));
    }
}
```

Using list by selection (precedent `src/Tenants/ZIMS/Modules/NirModule.cs`): always `System.Threading`, `Carter`, `Internal.Domain.Shared.Result`, `Microsoft.AspNetCore.Builder`, `Microsoft.AspNetCore.Http`, `Microsoft.AspNetCore.Mvc`, `Microsoft.AspNetCore.Routing`, `Shared.Mapper`, `Shared.Services`; plus `System` for `Guid` routes, `Shared.Models.<SYS>` per selected system, `Shared.Models.NIR.Common.Requests.Person` for NIR create/update, `Shared.Types` for paginated operations. `ImplicitUsings` is off in most tenants — check the csproj (C1); a missing `using` is a build error.

Rules:

- `CustomResults.Problem(result)` (`Internal.Domain.Shared.Result`) is the only failure path — it turns `Error` into RFC 7807 `ProblemDetails` with the status from C2
- Every handler takes `CancellationToken` and passes it through
- `.Produces(...)` for the real success status and type, and for every failure status step 2 lists for that operation — this feeds Swagger and the generated API specification. Don't copy `EServicesSharedModule`'s POST `.Produces(StatusCodes.Status200OK, ...)` (the route returns 201) or EGP's `/zra/taxpayers` `.Produces` type (declares `TaxClearanceCertificateResponse` for a `List<TaxpayerResponse>` result)
- `POST` that creates returns `Results.Created`; `PATCH` returns `Results.Accepted()`
- Route segments are lowercase and grouped by source: `/<source>/<resource>/{key}` — the source name is the only grouping in the path
- Where the csproj enables `<Nullable>`, optional query parameters are `string?` (C1); otherwise plain `string` already binds as optional
- Reuse the shared response models from `Shared.Models.<SYS>`. Only introduce a tenant DTO under `src/Tenants/<TenantName>/Models/<SYS>/` when the tenant's contract genuinely differs, and then add the mapper to the tenant's existing `Mapper/*MappingExtensions.cs`, or create `Mapper/<PascalTenant>MappingExtensions.cs` (`DOC` → `DocMappingExtensions`, `GOVZM` → `GovZmMappingExtensions`) following `src/Core/Shared/Mapper/MappingConventions.md`. Assign every settable target property explicitly
- Do not redeclare a model that already exists under `src/Core/Shared/Models/`

Generic calls need both type arguments named explicitly (`<BusinessEntityResponse, BusinessEntity>`) — inference does not reach `TSource` through the `Func`.

**Injection (C5).** `EServicesShared` holds no per-call state, so constructor injection — the repo convention, and required by `inherit` / `common` whose base constructors take it — is safe; it is still captured for the process lifetime and raises `CARTER1`. For a new `routes` module you may inject it as a handler parameter instead (`async (string nrc, EServicesShared services, CancellationToken cancellationToken) => …`) and drop the primary constructor. Offer it only under `Customize…`; default to the constructor.

## 7. Verify

```bash
dotnet build src/Tenants/<TenantName>/<TenantName>.csproj -v q --nologo
```

Must report `0 Error(s)`. Then, without running the app:

- `Endpoints:Gateway` exists in **both** appsettings files, with placeholder credentials
- `Program.cs` has `Configure<JsonSerializerOptions>` with `PropertyNameCaseInsensitive = true`, `AddCarter()`, `MapCarter()`, `RegisterGatewayEndpoint` and `AddTransient<EServicesShared>()`
- Every selected operation has exactly one route, and no route was generated for an operation the user deselected
- `inherit` mode only when the selection equals the `EServicesSharedModule` route set
- No route collides with one the tenant already exposes — `grep -rn "MapGroup\|MapGet\|MapPost\|MapPatch" src/Tenants/<TenantName>/Modules/`
- Every generic call passes both type arguments and a `map` delegate; paginated ones map with `MapItems`

The new routes change the tenant's contract. Outside `tenant-pipeline`, which runs it for you, name `/tenant-deliverables <TenantName>` as the next step: it regenerates the OpenAPI JSON, DOCX specification and Postman collection.

## Report

One line per file added or changed, then a table of the exposed routes (method, path, shared operation, upstream gateway path, gateway scope). Then:

- **Required gateway scopes** — the distinct scopes from that table (e.g. `ndw`, `ndw-nbr`, `zra`, `zra-portal`). The tenant's gateway user must hold every one; `ScopeAuthorizationMiddleware` answers `403 Request not allowed` otherwise.
- Any note step 2 calls for: explicit person `Id` not forwarded (`nir.person.create`), the `GetCooperativeByRegistrationNumber` upstream bug (`doc.cooperative`).

Close with what stays outside this skill:

- `GSB.<TENANT>.<ENV>` variables (and `projects-variables` entries) for every new token — `Endpoints.APIGATEWAY.BaseUrl`, `Credentials.<TenantName>Tenant.Username`, `Credentials.<TenantName>Tenant.Password` (C4)
- Granting the scopes above to the tenant's gateway user
- A gateway route for the new paths when the tenant's existing routes don't already forward them — check `docs/zamconnect-test-routes.md` (C8); some tenants are routed per path (`t_<slug>_eservices_nir_persons`, `…_nbr_entities`) rather than with one catch-all

End with the equivalent command (R7), e.g. `/integrate-shared ZAQA --source NIR --endpoint nbr.entity --mode routes`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when a prerequisite stops the skill or the build in step 7 fails.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
- Many tracked `appsettings.Development.json` files — including this tenant's, possibly — already commit literal credentials, and `src/Tenants/Certificates/*.p12` is committed (C7). Never use any tenant's Development file as the template for credential values, never carry an existing literal forward when editing, and write placeholders even where the file around them holds literals. Report the tenant's own literals as a finding without printing them; rotation is a separate ticket.
