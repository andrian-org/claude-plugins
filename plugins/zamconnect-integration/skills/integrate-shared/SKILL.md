---
name: integrate-shared
description: Expose ZamConnect shared e-Services (NIR, NBR/PACRA, DOC, SRS, ZDI, NLR, ZDA, NAIR, ZRA, MOH) on a tenant by wiring `EServicesShared` through the API gateway. Scans `src/Core/Shared/Services/EServicesShared.cs` for the available operations and drives an interactive menu to pick sources and endpoints, then generates the Carter module, registration, and gateway `appsettings` section. For an agency with no system of its own, it instead sets up a virtual tenant: gateway routes onto the GOVZM `/eservices` surface, with no project and no code (`--mode virtual`). Use when the user says "add NIR lookup to <Tenant>", "expose shared e-services on <Tenant>", "give <Tenant> access to PACRA/ZRA/ZDI", "<agency> only needs NIR/PACRA", "create a virtual tenant", "route <agency> to GOVZM eservices", "which shared endpoints are available", or types /integrate-shared.
argument-hint: "<TenantName|AgencyCode> [--source NIR|NBR|DOC|SRS|ZDI|NLR|ZDA|NAIR|ZRA|MOH ...] [--endpoint <key> ...] [--base-path <path>] [--tag EServices] [--mode inherit|common|routes|virtual] [--shape catch-all|paths] [--scope <scope>] [--dto shared|tenant] [--all] [--new] [--list] [--auto] [--dry-run] [--help]"
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(mkdir *) Bash(dotnet *) Bash(docker *) AskUserQuestion Skill
disable-model-invocation: false
---

# Integrate Shared e-Services into a Tenant

`EServicesShared` (`src/Core/Shared/Services/EServicesShared.cs`) is the single client for every e-Service reachable through the ZamConnect API gateway. A tenant does not re-implement those calls — it injects `EServicesShared` and republishes the subset of operations it is entitled to.

This skill selects that subset interactively and generates the wiring.

An agency that needs only shared e-Services may need no tenant at all. GOVZM already republishes part of the catalogue under `/eservices`, and a **virtual tenant** is a gateway route under the agency's slug that points at the GOVZM cluster (`t_ccpc_eservices`: `/t/ccpc/{**url}` → `GOVZM` `/eservices/{**url}`). Virtual mode (§4a) writes only that gateway package. The same rule exists for hosts other than GOVZM; see conventions C11.

All paths below are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`). Resolve it once and never write an absolute path into generated code, config, or the report.

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Every option is a complete answer (R12). The catalogue holds more than 4 sources, so the menus group first and drill down after (R9).

Shared facts — usings/namespace (C1), `Error` → status (C2), `Username` casing (C3), token naming (C4), Carter DI lifetime (C5), file hygiene (C6), committed-secrets baseline (C7), live routes doc (C8), virtual tenants and cross-cluster routes (C11), upstream scopes of the tenant's gateway user (C12) — live in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`. Read it before generating; this skill cites section ids instead of repeating them.

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Target tenant folder `src/Tenants/<TenantName>/`, or, with `--mode virtual`, the agency code of a virtual tenant (`CCPC`) that has no folder there. Required. When omitted, asked first from the contract's Missing arguments menu (R13); `--auto` stops with `missing <TenantName>` |
| `--source <SYS>` | Pre-select one or more upstream systems; repeatable. Skips the source menu |
| `--endpoint <key>` | Pre-select individual operations by catalogue key; repeatable. Skips the endpoint menu |
| `--base-path <path>` | Route group prefix. **Default: none** — routes sit at the tenant root. Pass one only when the tenant already groups its own surface under a prefix, or its gateway route transforms onto one (step 6) |
| `--tag <Tag>` | Swagger tag for the group. Default `EServices` |
| `--mode <mode>` | `inherit` \| `common` \| `routes` \| `virtual`. Default chosen per step 4. `inherit` is refused unless the selection is exactly the `EServicesSharedModule` route set. `virtual` writes gateway routes onto GOVZM and no code (§4a); it is refused for an operation GOVZM doesn't serve |
| `--shape catch-all\|paths` | Virtual mode only: one `/t/<slug>/{**url}` route, or one route per path (§4a). Default per §4a |
| `--scope <scope>` | Virtual mode only: the gateway scope of the routes. Default `<slug>`, or the tenant's own scope for an existing tenant (§4a) |
| `--dto shared\|tenant` | Return the shared response models, or tenant DTOs plus a mapper. Default `shared` |
| `--all` | Every operation from the step 1 rescan, in `routes` mode. Not `inherit` — `EServicesSharedModule` maps only a subset. With `--mode virtual`: every operation GOVZM serves (§4a) |
| `--new` | Tenant does not exist yet; scaffold it with `tenant-init` first. The opposite of `--mode virtual` for a missing tenant |
| `--list` | Print the catalogue (step 1) and stop. No files written |
| `--gate <n>/<N>`, `--recommend proceed\|skip` | Gate mode, set by `tenant-pipeline` |
| `--auto` | No questions. Uses `--source` / `--endpoint` / `--all` as given; with none of them, stops with `missing --source <SYS> or --all`. A tenant missing from `src/Tenants/` without `--mode virtual` or `--new` stops with `missing --mode virtual or --new` |
| `--dry-run` | Stop at the confirmation in step 3 and write nothing |
| `--help` | Print the arguments and examples, then stop. Asks and writes nothing (R14) |

`--source` and `--endpoint` combine: sources expand to all their operations, then `--endpoint` adds individual ones.

## Gate

Only with `--gate <n>/<N>`. Run the step 3 prerequisites first, but only to shape the gate: no prerequisite ends the step before the developer has seen it. **One** `AskUserQuestion` call holds the gate and, unless `--source`, `--endpoint` or `--all` was passed, the group question from 3b (R4). Which e-Services to expose has no default.

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/integrate-shared <T>` — republish shared e-Services (NIR, PACRA, ZRA…) on this tenant through `EServicesShared`. Run it? | `Proceed` — every operation of the groups picked below, `routes` mode, tag `EServices`, no base path, shared response models · `Customize…` — also choose operations, Swagger tag, module mode, response models · `Skip` · `Stop` |
| `e-Services` | The 3b group question | the four groups |

`(Recommended)` goes on `Proceed` with `--recommend proceed`, and on `Skip` with `--recommend skip`. The option order doesn't change. `Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`.

**No Carter** (a controllers tenant, from `tenant-init --controllers`). The gate question adds: "<T> serves controllers and has no Carter. `Proceed` and `Customize…` also add Carter alongside the controllers (step 5), so the e-Services module is mapped. Skip unless this tenant needs shared e-Services." `(Recommended)` goes on `Skip`, whatever `--recommend` says. Picking `Proceed` or `Customize…` is the consent to add Carter: the prerequisites question isn't asked again. A note on `Proceed` that refuses Carter ends the step with `GATE-RESULT: failed no Carter in <T>`, because a module that is never mapped exposes nothing.

With `Proceed`, skip 3c and 3d: every operation of the picked groups is exposed in `routes` mode (whole groups never equal the `inherit` route set), and step 3's confirmation shows them. With `Customize…`, ask 3c and 3d as well.

With `--mode virtual` (how `tenant-pipeline` runs a virtual tenant), the gate question reads: "`/integrate-shared <T> --mode virtual` — gateway routes for <T> onto the GOVZM `/eservices` surface; no project, no code. Run it?" `Proceed` — every operation of the groups picked below, shape and scope per §4a. `Customize…` — also choose operations (3c), shape and scope. The `e-Services` question uses the virtual groups of 3b.

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

Failure statuses each operation can produce through `CustomResults.Problem` (C2) — declare exactly these with `.ProducesProblem(...)`:

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

Offer the tenants that already inject `EServicesShared` first (extending an existing integration), then the rest. Also list the virtual tenants (`ls src/VirtualTenants`).

**Tenant not in `src/Tenants`.** Whether `<TenantName>` came as an argument or from 3a: unless `--new` or `--mode virtual` was passed, and when `src/VirtualTenants/<T>/` doesn't exist either, ask once, header `No tenant`:

| Option | Meaning |
|---|---|
| `Virtual tenant on GOVZM (Recommended)` | The agency has no system of its own and needs only shared e-Services that GOVZM serves. Gateway routes only (§4a). Sets `--mode virtual` |
| `Scaffold <T> as a real tenant` | The agency has its own system to integrate, needs operations GOVZM doesn't serve (ZDI, NLR, ZDA, NAIR, MOH, DOC, SRS, `zra.taxpayer`), or needs its own contract. Sets `--new` — run `tenant-init <T> --no-virtual` before continuing |

The question text names the GOVZM operations from the step 1 `EServicesSharedModule` grep, so the choice is made against the real list. An existing `src/VirtualTenants/<T>/` means `--mode virtual` without asking: the run extends that virtual tenant.

**Prerequisites.** Skipped in virtual mode: no tenant code changes. Otherwise, once the tenant is known — before 3b, before the gate question, and under `--auto` too:

```bash
grep -nE 'AddCarter|MapCarter|Configure<JsonSerializerOptions>|PropertyNameCaseInsensitive|RegisterGatewayEndpoint|AddTransient<EServicesShared>' src/Tenants/<TenantName>/Program.cs
grep -n 'Shared.csproj' src/Tenants/<TenantName>/<TenantName>.csproj
grep -n 'COPY \["Core/' src/Tenants/<TenantName>/Dockerfile
grep -nE '<ImplicitUsings>|<Nullable>' src/Tenants/<TenantName>/<TenantName>.csproj
grep -rlnE 'class Gateway\b' src/Tenants/<TenantName> --include=*.cs
ls src/Tenants/<TenantName>/Controllers src/Tenants/<TenantName>/Modules src/Tenants/<TenantName>/Mapper
```

| Finding | Action |
|---|---|
| No `AddCarter()` / `MapCarter()` — a controllers tenant | The generated module never gets mapped. Ask `Add Carter alongside the controllers (Recommended)` · `Stop`. Adding means step 5's Carter lines; `Carter` arrives transitively through `Shared.csproj`. `--auto` stops with `no Carter in <TenantName>`. Gate mode doesn't ask: the gate holds the choice (see Gate) |
| No `Configure<JsonSerializerOptions>` with `PropertyNameCaseInsensitive = true` | `EServicesShared` deserializes with that `IOptions<JsonSerializerOptions>` instance; without it the upstream camelCase JSON binds to nulls. Add it in step 5 |
| No `Shared.csproj` reference | Add it in step 5 |
| Dockerfile has no `Core/Shared` pair (`Core/Shared/Shared.csproj` and `Core/Shared/`), or is missing `Core/Internal` or `Core/Database` | Add the missing lines in step 5. `dotnet build` passes without them; only the Linux image build fails, at restore (`Shared.csproj` not found). The tenants without a `Shared` reference today (PQPS, IFMIS, NHIMA, ZRA, MOA…) have only the Internal and Database pairs |
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

In virtual mode, offer only what GOVZM serves (the `inherit` route set, §4a), counts from the rescan:

| Option | Covers |
|---|---|
| `Identity — NIR (6 operations)` | NIR |
| `Business registry — NBR/PACRA entity (1)` | `nbr.entity` |
| `Tax — ZRA tax clearance (1)` | `zra.tcc` |
| `Everything GOVZM serves (8) — one catch-all route` | All of the above. Picks the catch-all shape (§4a) when the slug allows it |

**3c — Operations.** Asked under `Customize…`, or without a gate when no `--endpoint` was passed. `multiSelect: true` over the operations of the chosen groups, each option labelled `METHOD /route — purpose` (`GET /nir/persons/nrc/{nrc} — person by NRC`). One question per group, at most 4 questions per call (R9). A group with more than 4 operations shows 3 plus `All <n> <group> operations`, which selects the rest. The question text says that only the ticked operations are exposed.

**3d — Placement.** `Customize…` only, one call. Not asked in virtual mode, where §4a asks `Shape` and `Scope` and holds the review:

| Header | Options |
|---|---|
| `Tag` | `EServices (Recommended)` · the tag the tenant's existing modules already use, if there is one |
| `Mode` | The step 4 default `(Recommended)` · the other modes that step 4 allows for this selection, each with its one-line "use when". `virtual` is offered on an existing tenant only when every selected operation is on GOVZM |
| `Models` | `Shared response models (Recommended)` · `Tenant DTOs + mapper` |
| `Base path` | Only when the tenant's existing modules already group under a prefix: `None (Recommended)` · that prefix |

Then one R6 confirmation. The question text is the table — key, method, route, response model, required gateway scope — plus the files to write and the equivalent command. Options `Apply (Recommended)` · `Adjust` · `Cancel`. `Adjust` re-asks whichever of 3b, 3c or 3d is picked. With `--dry-run`, print it and stop.

## 4. Choose the module mode

| Mode | Shape | Use when |
|---|---|---|
| `inherit` | `public class EServicesModule(EServicesShared services) : EServicesSharedModule("EServices", services);` | The selection is **exactly** the routes `EServicesSharedModule.AddRoutes` maps (step 1 grep — currently the six NIR operations, `nbr.entity` and `zra.tcc`). Canonical one-liner: `src/Tenants/ZPS/Modules/EServicesModule.cs`. The two-argument constructor has no base path; `src/Tenants/GOVZM/Modules/EServicesModule.cs` passes `"/eservices"` to the three-argument one, which is the exception |
| `common` | Abstract `CommonModule` in the tenant holding the selected routes plus a `protected virtual void AddAdditionalRoutes(RouteGroupBuilder group)` hook, with one thin concrete module per consumer | The tenant publishes the same subset under several base paths or tags. The hook pattern is `src/Tenants/MCTI/Modules/CommonModule.cs` (concrete `ZabsModule`, `ZmaModule`). `src/Tenants/DOC/Modules/CommonModule.cs` has no hook and one concrete module — cite it for route shapes only |
| `routes` | One plain `ICarterModule` with only the selected routes | Any other selection, including `--all`. The default |
| `virtual` | Gateway routes onto GOVZM `/eservices` in a `GATEWAY-CONFIG.md`; no code in any tenant (§4a) | The agency has no system of its own (no `src/Tenants/<T>/`), or an existing tenant needs the GOVZM operations unchanged. Every selected operation must be in the `inherit` route set, which is what GOVZM serves |

Default to `virtual` when the tenant has no folder in `src/Tenants/` and the 3a answer (or a `src/VirtualTenants/<T>/` folder) chose it, `inherit` only when the selection equals the `inherit` route set, `common` when the tenant already has a `CommonModule`, otherwise `routes`. On an existing tenant `virtual` is never the default: the tenant's own module gives it a documented and tested contract.

`EServicesSharedModule` is all-or-nothing — it maps its full route set and nothing else. Never subclass it to expose a subset, and never pick `inherit` for a selection containing an operation it doesn't map; generate the routes instead.

In `inherit` mode the module body stays empty. `EServicesSharedModule.AddRoutes` already does `app.MapGroup(basePath).WithTags(tags)` and maps its routes onto it, so the tenant module must not declare `var group = app.MapGroup("").WithTags("EServices");` or map anything itself — the base path and tag are the constructor arguments. Only `routes` and `common` mode create the group.

## 4a. Virtual mode — GOVZM routes, no code

Route shapes, fields, file locations and the import rules are in conventions C11. This step applies them to the GOVZM host. In virtual mode, skip steps 5–7 and go from here to the Report.

**Host check.** Re-derive what GOVZM serves before writing:

```bash
grep -n 'EServicesSharedModule(' src/Tenants/GOVZM/Modules/*.cs
grep -nE '\| GOVZM \|' docs/zamconnect-test-routes.md | grep -v '/t/govzm/'
```

The first argument of the three-argument base constructor is the prefix: `"/eservices"` today. The two-argument form has none. With no hit or another prefix, stop with `GOVZM no longer serves EServicesSharedModule under /eservices`. The second grep lists the live virtual routes on GOVZM: the precedents, and the slugs already taken.

**What GOVZM serves.** Exactly the `inherit` route set from the step 1 grep: today the six NIR operations, `nbr.entity` and `zra.tcc`. `--all` means that set here. When `--source` or `--endpoint` selected anything else, ask header `Not on GOVZM`: `Drop them — virtual tenant with <n> operations (Recommended)` · `Scaffold <T> as a real tenant instead`. The second sets `--new`, runs `tenant-init <T> --integrates shared --no-virtual --no-pipeline` and continues in `routes` mode. `--auto` stops with `not on GOVZM: <keys>`. Never add routes to GOVZM to make a virtual tenant possible. A change to the shared host is a separate change for the GOVZM owners.

**Paths.** Rebuild this table from the step 1 grep. A consumer calls `/t/<slug>` + route, and GOVZM serves `/eservices` + route.

| Key | Verb | GOVZM route | Deeper path, when its resource route is split |
|---|---|---|---|
| `nir.person.document` | `GET` | `/nir/persons/identity-document` | `nir/persons/identity-document` |
| `nir.person.nrc` | `GET` | `/nir/persons/nrc/{nrc}` | `nir/persons/nrc` |
| `nir.person.zampass` | `GET` | `/nir/persons/zampass/{zamPassId}` | `nir/persons/zampass` |
| `nir.person.create` | `POST` | `/nir/persons` | `nir/persons` |
| `nir.person.update` | `PATCH` | `/nir/persons/{id}` | `nir/persons` |
| `nir.person.update-zampass` | `PATCH` | `/nir/persons/zampass/{zamPassId}` | `nir/persons/zampass` |
| `nbr.entity` | `GET` | `/nbr/entities/{entityNumber}` | `nbr/entities` |
| `zra.tcc` | `GET` | `/zra/taxpayers/tcc` | `zra/taxpayers/tcc` |

**Shape.** From `--shape`, else the default below. Under `Customize…`, ask header `Shape` with the default `(Recommended)` and the other shape when it is allowed.

| Shape | Default when | Routes |
|---|---|---|
| `catch-all` | The selection is every operation GOVZM serves, and no route in the routes doc or in any `GATEWAY-CONFIG.md` uses `/t/<slug>/{**url}` yet. Allowed only then | One route: `t_<slug>_eservices`, `/t/<slug>/{**url}` → `/eservices/{**url}`, `order: 1`, every verb of the set (`GET`, `POST`, `PATCH` today) |
| `paths` | Any subset, and always on an existing tenant: its own `t_<slug>` owns `/t/<slug>/{**url}` | One route per resource, the first two segments of the route (`nir/persons`, `nbr/entities`, `zra/taxpayers`): `t_<slug>_eservices_nir_persons` and so on, the `t_pqps_eservices_*` shape. Each lists the verbs of the selected operations under it. When a resource route would reach an unselected operation with one of its verbs, use the deeper paths of the selected operations from the table instead (`nir/persons/nrc`, `nir/persons/zampass`), the `zigsapi_*` shape |

Example: `nir.person.nrc` and `nir.person.zampass` alone. `nir/persons` with `GET` would also reach `nir.person.document`, so the routes are `t_<slug>_eservices_nir_persons_nrc` and `t_<slug>_eservices_nir_persons_zampass`, `GET` only.

**Scope.** From `--scope`, else `<slug>` for a virtual tenant, or the tenant's own `metadata.Scope` for an existing tenant (from its `GATEWAY-CONFIG.md`, else the routes doc). Under `Customize…`, ask header `Scope` with that default `(Recommended)`. The question text says that an agency already holding a scope on another slug (`zilas` for `deeds`, `lands`, `survey`) types it in Other.

**Collisions.** Before the review:

```bash
grep -n '/t/<slug>/' docs/zamconnect-test-routes.md
grep -ln '"/t/<slug>/' src/Tenants/*/GATEWAY-CONFIG.md src/VirtualTenants/*/GATEWAY-CONFIG.md 2>/dev/null
```

| Finding | Action |
|---|---|
| A route on another cluster with the same `match.path` as a route to write | Stop with `<path> is already routed to <cluster> by <route>`. Two routes on one path make the gateway answer 500 |
| A live route with the same id, on `GOVZM`, with the same path | This run updates it. The review says so |
| Existing tenant: its own module or controller already maps a route under a per-path route's path (`grep -rnE '"/(nir/persons\|nbr/entities\|zra/taxpayers)' src/Tenants/<T>/Modules src/Tenants/<T>/Controllers`), or a module derives from `EServicesSharedModule` | The per-path route would shadow it. Stop: the tenant already serves these operations itself |

**Review.** One R6 call, options `Apply (Recommended)` · `Adjust` · `Cancel`. The question text is the plan:

```
Virtual tenant CCPC → GOVZM /eservices (no project, no code):
  src/VirtualTenants/CCPC/GATEWAY-CONFIG.md   scope ccpc · 1 route · clusters []
Routes:
  t_ccpc_eservices   GET, POST, PATCH   /t/ccpc/{**url} → /eservices/{**url}   order 1
Reaches:
  GET   /t/ccpc/nir/persons/nrc/{nrc}     nir.person.nrc
  POST  /t/ccpc/nir/persons               nir.person.create
  …
Command: /integrate-shared CCPC --mode virtual --all --shape catch-all
```

Under `Reaches`, list every GOVZM operation each route reaches. An unselected operation that a route can't keep out is marked `(not selected — same path and verb)`. `Adjust` re-asks 3b, 3c, `Shape` or `Scope`. With `--dry-run`, print it and stop.

**Write.**

- Virtual tenant: create `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md` from the template below, or replace its routes when it exists. `<CODE>` is `<T>` in upper case, `<slug>` in lower case.
- Existing tenant: add the routes to `routes[]` of `src/Tenants/<T>/GATEWAY-CONFIG.md`. Keep `clusters` and the tenant's own route as they are, and add the operations table of the template below the import paragraph. A tenant with no `GATEWAY-CONFIG.md` gets the route objects in the report instead.
- Git: the file is local only (C10, "Not committed"). Append to the repository root `.gitignore` any line of the C10 handoff block that `grep -xF -e 'src/Tenants/*/ENVIRONMENT-VARIABLES.json' -e 'src/Tenants/*/GATEWAY-CONFIG.md' -e 'src/VirtualTenants/*/GATEWAY-CONFIG.md' .gitignore` does not print. Never rewrite the rest of the file.
- Nothing else: no `Program.cs`, `appsettings`, `ENVIRONMENT-VARIABLES.json`, module or test change.

~~~~markdown
# <CODE> Gateway Config — virtual tenant

<CODE> has no project of its own. Its routes point at the `GOVZM` cluster, which serves the shared
e-Services under `/eservices`. A consumer calls `/t/<slug>/<path>`; the gateway forwards it to GOVZM
`/eservices/<path>`.

| Method | Consumer path | GOVZM path | Operation |
|---|---|---|---|
| GET | `/t/<slug>/nir/persons/nrc/{nrc}` | `/eservices/nir/persons/nrc/{nrc}` | Person by NRC |

Import with `POST /Import/routes` on the AdminAPI (Admin policy). The body is the JSON below as-is
(`RouteConfigurationPackageDto`). `clusters` is empty on purpose: importing `GOVZM` from here would
overwrite the live cluster. The import creates the `<scope>` scope from `metadata.Scope`, then the
routes; an existing route with the same id is overwritten. A gateway without a `GOVZM` cluster rejects
the routes.

Locally, don't import by hand: `/tenant-audit <CODE> --only runtime` applies this package to the
local Docker `mongo` only, together with a `test<CODE>` gateway user.

```json
{
    "clusters": [],
    "routes": [
        {
            "name": "t_<slug>_eservices",
            "configJson": {
                "routeId": "t_<slug>_eservices",
                "match": {
                    "methods": [
                        "GET",
                        "POST",
                        "PATCH"
                    ],
                    "path": "/t/<slug>/{**url}"
                },
                "order": 1,
                "clusterId": "GOVZM",
                "authorizationPolicy": "Basic",
                "metadata": {
                    "Scope": "<scope>"
                },
                "transforms": [
                    {
                        "PathPattern": "/eservices/{**url}"
                    }
                ]
            }
        }
    ]
}
```

Every consumer's gateway user needs the `<scope>` scope, or the gateway answers 403. It doesn't need `govzm`.

Registering by hand through `POST /Routes` instead: create the scope first with `POST /Scopes {"name": "<scope>"}` —
the route validator rejects a scope that doesn't exist.

## Host scopes

GOVZM calls the upstream for these routes with its own gateway user, not with the consumer's. That user must
keep the scopes below in each gateway, or GOVZM answers 500 to <CODE>'s consumers. <CODE>'s gateway user needs
none of them.

| Upstream paths | Scope |
|---|---|
| `/t/ndw/graphql`, `/t/ndw/nir/persons/…` | `ndw` |
~~~~

A per-path route has the same object without `"order"`, with `"path": "/t/<slug>/<path>/{**url}"` and `"PathPattern": "/eservices/<path>/{**url}"`, and one operations-table row per operation it reaches.

**Host scopes.** One row per distinct scope of the operations the routes reach — every operation listed under `Reaches`, selected or not — with the upstream paths from the §2 catalogue. A catch-all reaches every operation GOVZM serves, so it lists every scope of the `EServicesSharedModule` set. An existing tenant's cross-cluster sub-routes add the same table, headed `## Host scopes — <route ids>`, below the operations table: the scopes are GOVZM's, never the tenant's own Upstream scopes section (C12).

**Verify.** Read the file back and check each route: `clusterId` is `GOVZM`, `authorizationPolicy` is `Basic`, `metadata.Scope` is the chosen scope, the `PathPattern` starts with the GOVZM prefix, `methods` holds only verbs GOVZM maps under that path, `order` is `1` on a catch-all and absent on a per-path route. The `## Host scopes` table holds every scope of the operations under `Reaches`, and no other. For a virtual tenant `clusters` is `[]`. For an existing tenant, `clusters` and the tenant's own route are unchanged. No other file changed. Don't run the audit from here: `/tenant-audit <CODE>` is the next step, and its Check V calls every route through the local gateway.

## 5. Wire the tenant

**`src/Tenants/<TenantName>/<TenantName>.csproj`** — must reference `Shared`:

```xml
<ProjectReference Include="..\..\Core\Shared\Shared.csproj" />
```

**`src/Tenants/<TenantName>/Dockerfile`** — must copy `Shared` and what it references. `Shared.csproj` references `Internal`, which references `Database`, so the restore needs all three projects in the image. The build context is `src/`. Use the tenant-init §3 form, and add only the lines the prerequisites grep didn't find:

| Line | Place it after |
|---|---|
| `COPY ["Core/Shared/Shared.csproj", "Core/Shared/"]` | The last `COPY ["Core/<Dir>/<Dir>.csproj", "Core/<Dir>/"]` line, before `RUN dotnet restore` |
| `COPY ["Core/Shared/", "Core/Shared/"]` | The last `COPY ["Core/<Dir>/", "Core/<Dir>/"]` line, before `WORKDIR "/src/Tenants/<TenantName>"` |

A missing `Internal` or `Database` pair is added the same way, keeping the order `Internal`, `Database`, `Shared` in both groups. With no `Core/` line at all in a group, the line goes after the tenant's own `COPY` in that group (`Tenants/<TenantName>/<TenantName>.csproj`, then `Tenants/<TenantName>`). Change nothing else in the file. For PQPS the result is:

```dockerfile
COPY ["Tenants/PQPS/PQPS.csproj", "Tenants/PQPS/"]
COPY ["Core/Internal/Internal.csproj", "Core/Internal/"]
COPY ["Core/Database/Database.csproj", "Core/Database/"]
COPY ["Core/Shared/Shared.csproj", "Core/Shared/"]
RUN dotnet restore "Tenants/PQPS/PQPS.csproj"

COPY ["Tenants/PQPS", "Tenants/PQPS/"]
COPY ["Core/Internal/", "Core/Internal/"]
COPY ["Core/Database/", "Core/Database/"]
COPY ["Core/Shared/", "Core/Shared/"]
WORKDIR "/src/Tenants/PQPS"
```

Every tenant that already references `Shared` (ZPS, GOVZM, MCTI…) has this layout. Re-run the prerequisites grep afterwards: it must print the three pairs, each once.

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
- Token names follow C4 (tenant calling back into the gateway); `<TenantName>` is the exact folder name. Each new token needs a variable in each environment, or the deploy fails. Add the three to `src/Tenants/<TenantName>/ENVIRONMENT-VARIABLES.json` (C9) — `Endpoints.APIGATEWAY.BaseUrl` with `secret: false`, the two credentials with `secret: true`, every `value` `""` — unless they are already listed. Never create the variables anywhere else (C10).
- In `appsettings.Development.json` the `BaseUrl` is `http://gateway/`, the `gateway` service of `src/.dockercompose/docker-compose.yml`, so a tenant container running locally calls the local Docker gateway, never the test one. Credentials stay `__Token__` placeholders; `/tenant-audit` Check 9 supplies the local test user when it starts the container. Never copy a value from another tenant's Development file (C7).
- If the tenant already has other `Endpoints` entries, add `Gateway` as a sibling — do not replace the object. If a `Gateway` section is already there (`tenant-integration` writes it for an upstream reached through the gateway), keep it: both clients share that one section and one set of credentials.

## 6. Generate the module

`src/Tenants/<TenantName>/Modules/EServicesModule.cs` for `routes` and `inherit`; `CommonModule.cs` plus concrete modules for `common`. New `.cs` files follow C6.

**Gateway methods.** Once the module is written, set `match.methods` of the tenant's route in `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` to every verb the tenant now maps, not just the new ones, so no route of the tenant answers 405 at the gateway:

```bash
grep -rhoE "Map(Get|Post|Put|Patch|Delete)\(|\[Http(Get|Post|Put|Patch|Delete)" src/Tenants/<TenantName>/Modules src/Tenants/<TenantName>/Controllers 2>/dev/null \
  | sed -E 's/.*(Get|Post|Put|Patch|Delete).*/\1/' | tr a-z A-Z | sort -u
```

When any module of the tenant derives from `EServicesSharedModule` (this run's `inherit` mode or an earlier one), add the verbs of the step 1 `EServicesSharedModule` grep: its routes live in Core, so the tenant grep never sees them. Keep the order `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. A tenant with no `GATEWAY-CONFIG.md` (created before `tenant-init` wrote one) gets the verbs in the report instead.

**Upstream scopes.** The tenant now calls NDW or ZRA through the gateway as `Credentials.<TenantName>Tenant`, and that user needs the scope of every operation it calls (C12). Rewrite the `## Upstream scopes` section of `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` in the C12 shape, from every shared operation the tenant calls after this run, not only the new ones:

```bash
grep -oE 'public async Task<Result<.*>> [A-Za-z]+[<(]' src/Core/Shared/Services/EServicesShared.cs \
  | sed -E 's/.*>> ([A-Za-z]+)[<(]$/\1/' | sort -u > <scratch>/shared-ops.txt
grep -rhoFwf <scratch>/shared-ops.txt src/Tenants/<TenantName>/Modules | sort -u
```

It matches the method name wherever the call wraps (`await services\n    .GetZdiPermitsByApplicantPassportNumber<…>`). Each method maps to its §2 key, and the key gives the upstream path and the scope. An `inherit` module calls every operation of `EServicesSharedModule`, which the grep can't see: add their scopes from the step 1 grep. Calls the tenant makes through its own `Endpoints/Gateway.cs` keep their rows (`tenant-integration` writes them). Group the rows by scope; the `Calls through` cell names the system, `EServicesShared (NIR)`. Re-check each scope in the routes doc (C8) when the step 1 rescan found a path the §2 table doesn't hold. A tenant with no `GATEWAY-CONFIG.md` gets the table in the report instead.

The `MapGroup` below belongs to `routes` and `common` mode only. An `inherit` module has no `AddRoutes` override at all — mapping the group there would duplicate the shared route set.

**No base path by default.** The group exists to carry the Swagger tag, not to add a segment. A tenant's own gateway route (`t_<slug>` → `/t/<slug>/{**url}`, transform `/{**url}`) forwards the remainder unchanged, so `nir.person.nrc` is served at `/t/<slug>/nir/persons/nrc/{nrc}`. A prefix is right only when a gateway route maps onto it: GOVZM serves under `/eservices` because agency routes such as `t_dam_eservices` (`/t/dam/{**url}`) point at the GOVZM cluster and the gateway transform adds the prefix. Look up the tenant's route in `docs/zamconnect-test-routes.md` (C8) before choosing.

`routes` mode, ImplicitUsings off (C1) — full `using` block and file-scoped namespace. Keep only the usings the selected routes need; add `using System;` when a route binds `Guid`:

```csharp
using System.Threading;
using Carter;
using Internal.Domain.Shared.Result;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
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
            .Produces<PersonResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status404NotFound)
            .ProducesProblem(StatusCodes.Status500InternalServerError)
            .WithSummary("Get a person by NRC")
            .WithDescription("Returns the person registered under the given NRC in the National Identity Register (NIR).");

        group.MapPost("/nir/persons",
                async (PersonAddRequest model, CancellationToken cancellationToken) =>
                {
                    var result = await services.CreatePerson(model.ToNirPersonAddRequest(), cancellationToken);
                    return result.IsSuccess
                        ? Results.Created(string.Empty, new PersonCreatedResponse { Id = result.Value.Id })
                        : CustomResults.Problem(result);
                })
            .Produces<PersonCreatedResponse>(StatusCodes.Status201Created)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status404NotFound)
            .ProducesProblem(StatusCodes.Status409Conflict)
            .ProducesProblem(StatusCodes.Status500InternalServerError)
            .WithSummary("Register a person")
            .WithDescription("Creates a person record in the National Identity Register (NIR) and returns its id.");

        group.MapGet("/nbr/entities/{registrationNumber}",
                async (string registrationNumber, CancellationToken cancellationToken) =>
                {
                    var result = await services
                        .GetEntityByRegistrationNumber<BusinessEntityResponse, BusinessEntity>(
                            registrationNumber, e => e.ToBusinessEntityResponse(), cancellationToken);
                    return result.IsSuccess ? Results.Ok(result.Value) : CustomResults.Problem(result);
                })
            .Produces<BusinessEntityResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status404NotFound)
            .ProducesProblem(StatusCodes.Status500InternalServerError)
            .WithSummary("Get a business entity by registration number")
            .WithDescription("Returns the business entity registered under the given number in the National Business Register (NBR/PACRA).");

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
            .Produces<PaginatedResult<PermitResponse>>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status500InternalServerError)
            .WithSummary("List ZDA permits of an entity")
            .WithDescription("Returns the Zambia Development Agency (ZDA) permits held by the given entity, one page at a time.");
    }
}
```

Using list by selection (precedent `src/Tenants/ZIMS/Modules/NirModule.cs`): always `System.Threading`, `Carter`, `Internal.Domain.Shared.Result`, `Microsoft.AspNetCore.Builder`, `Microsoft.AspNetCore.Http`, `Microsoft.AspNetCore.Routing`, `Shared.Mapper`, `Shared.Services`; plus `System` for `Guid` routes, `Shared.Models.<SYS>` per selected system, `Shared.Models.NIR.Common.Requests.Person` for NIR create/update, `Shared.Types` for paginated operations. `ImplicitUsings` is off in most tenants — check the csproj (C1); a missing `using` is a build error.

Rules:

- `CustomResults.Problem(result)` (`Internal.Domain.Shared.Result`) is the only failure path — it turns `Error` into RFC 7807 `ProblemDetails` with the status from C2
- Every handler takes `CancellationToken` and passes it through
- `.Produces<T>(...)` for the real success status and type, one `.ProducesProblem(...)` for every failure status step 2 lists for that operation, plus `.WithSummary(...)` and `.WithDescription(...)` — the APIS set `tenant-integration` step 8, `tenant-audit` Check 5 and `tenant-deliverables` all read. The description names the upstream system; state only what the route returns. Don't copy `EServicesSharedModule`'s POST `.Produces(StatusCodes.Status200OK, ...)` (the route returns 201) or EGP's `/zra/taxpayers` `.Produces` type (declares `TaxClearanceCertificateResponse` for a `List<TaxpayerResponse>` result)
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

Must report `0 Error(s)`. `dotnet build` says nothing about the Dockerfile, so then build the image through the tenant's compose service. Resolve the service key from the compose file first, never from the tenant name:

```bash
grep -nE '^  [A-Za-z0-9_.-]+:[[:space:]]*$|dockerfile: Tenants/<TenantName>/Dockerfile' src/.dockercompose/docker-compose.yml | grep -B1 'dockerfile:'
```

The first line printed is the key of the service that builds `Tenants/<TenantName>/Dockerfile`. It is normally `core-<slug>`, the tenant name lowercased with no separators (tenant-init step 5). When it differs — ECOUNCIL's `core-ecounncil`, TestTenant's `test-tenant` — build with the key the file holds and report the mismatch; don't rename the service here. With no service at all, report `no compose service for <TenantName>`, count the image build as not run, and name `/tenant-audit <TenantName>` (Check 1).

```bash
docker info >/dev/null 2>&1 && docker compose -f src/.dockercompose/docker-compose.yml build <service>
```

Must exit 0. On failure, read the first error: a restore error naming a `Core/*.csproj` is a missing `COPY` from step 5. Fix it and re-run; don't report the run as done while it fails. If `docker info` fails (Docker not installed or the engine is not running), report the image build as `skipped — Docker not available`, never as passed, with the command to run later. If the Dockerfile declares `ARG PAT` (private feed, ZamMobile), pass `--build-arg PAT=<token>` from the user's environment and never echo it.

Then, without running the app:

- The Dockerfile has the `Core/Internal`, `Core/Database` and `Core/Shared` pairs, each once, in the step 5 places
- `Endpoints:Gateway` exists in **both** appsettings files, with placeholder credentials
- `Program.cs` has `Configure<JsonSerializerOptions>` with `PropertyNameCaseInsensitive = true`, `AddCarter()`, `MapCarter()`, `RegisterGatewayEndpoint` and `AddTransient<EServicesShared>()`
- Every selected operation has exactly one route, and no route was generated for an operation the user deselected
- `inherit` mode only when the selection equals the `EServicesSharedModule` route set
- No route collides with one the tenant already exposes — `grep -rn "MapGroup\|MapGet\|MapPost\|MapPatch" src/Tenants/<TenantName>/Modules/`
- `match.methods` in `GATEWAY-CONFIG.md` lists every verb from the step 6 grep
- The `## Upstream scopes` section of `GATEWAY-CONFIG.md` holds one row per distinct scope of the operations the tenant now calls, and no row for an operation it doesn't (C12)
- `Endpoints:Gateway:BaseUrl` in `appsettings.Development.json` is `http://gateway/`
- Every generic call passes both type arguments and a `map` delegate; paginated ones map with `MapItems`
- Every generated route has `.Produces<T>`, one `.ProducesProblem` per status from step 2, `.WithSummary` and `.WithDescription`

The new routes change the tenant's contract. Outside `tenant-pipeline`, which runs it for you, name `/tenant-deliverables <TenantName>` as the next step: it regenerates the OpenAPI JSON, DOCX specification and Postman collection.

## Report

One line per file added or changed, then a table of the exposed routes (method, path, shared operation, upstream gateway path, gateway scope). Then the step 7 results: `dotnet build`, and the image build of `<service>` as passed, failed or `skipped — Docker not available`, with any service-key mismatch. Then:

- **Required gateway scopes** — the distinct scopes from that table (e.g. `ndw`, `ndw-nbr`, `zra`, `zra-portal`). The tenant's gateway user must hold every one; `ScopeAuthorizationMiddleware` answers `403 Request not allowed` otherwise. Say they are written in the `## Upstream scopes` section of `GATEWAY-CONFIG.md` (C12).
- Any note step 2 calls for: explicit person `Id` not forwarded (`nir.person.create`), the `GetCooperativeByRegistrationNumber` upstream bug (`doc.cooperative`).

Close with what an administrator does by hand (C10):

- Add the `ENVIRONMENT-VARIABLES.json` entries this run added to each environment — `Endpoints.APIGATEWAY.BaseUrl`, `Credentials.<TenantName>Tenant.Username`, `Credentials.<TenantName>Tenant.Password` (C4, C9)
- Grant the scopes above to the tenant's gateway user (`Credentials.<TenantName>Tenant`) in each gateway, as the `## Upstream scopes` section of `GATEWAY-CONFIG.md` lists them
- A gateway route for the new paths when the tenant's existing routes don't already forward them — check `docs/zamconnect-test-routes.md` (C8); some tenants are routed per path (`t_<slug>_eservices_nir_persons`, `…_nbr_entities`) rather than with one catch-all
- `ENVIRONMENT-VARIABLES.json` and `GATEWAY-CONFIG.md` are not in git (C10): the engineer sends them to the administrator directly

End with the equivalent command (R7), e.g. `/integrate-shared ZAQA --source NIR --endpoint nbr.entity --mode routes`, and these answers for the pipeline state: `sources`, `endpoints`, `mode`, plus `dto`, `tag` and `basePath` when they differ from the defaults. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when the developer refuses Carter (see Gate), the build in step 7 fails, or the image build in step 7 fails (`GATE-RESULT: failed image build <service>`). An image build `skipped — Docker not available` is not a failure: the line stays `GATE-RESULT: ran`, and the report says it was skipped.

**Virtual mode.** One line for the `GATEWAY-CONFIG.md` written or changed, then the route table: route id, methods, consumer path, GOVZM path, operations reached. Then what an administrator does by hand (C10, C11):

- Import the `GATEWAY-CONFIG.md` package into each gateway. The import rejects the routes in a gateway without a `GOVZM` cluster. The file is not in git (C10): the engineer sends it to the administrator directly
- Create the agency's gateway user in each gateway, with the `<scope>` scope only
- Nothing to deploy: no pipeline, no variables, no image. GOVZM serves the routes with its own gateway user, which must keep the scopes of the operations reached, as the `## Host scopes` section of the file lists them (`ndw`, `ndw-nbr`, `zra`, `zra-portal`)

Name `/tenant-audit <CODE>` as the next step, then `/tenant-deliverables <CODE>`: it documents the GOVZM operations the routes reach, at the consumer's paths, into `src/VirtualTenants/<CODE>/Deliverables/`. End with the equivalent command, e.g. `/integrate-shared CCPC --mode virtual --all --shape catch-all`, and the state answers `mode: virtual`, `shape`, `scope`, `endpoints`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when the host check or a collision stops the skill.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. List its name in `ENVIRONMENT-VARIABLES.json` (C9) with an empty value, and leave the value out. Never write a registry, Helm, cluster, MongoDB, RA or ZamPass address (C10).
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
- Many tracked `appsettings.Development.json` files — including this tenant's, possibly — already commit literal credentials, and `src/Tenants/Certificates/*.p12` is committed (C7). Never use any tenant's Development file as the template for credential values, never carry an existing literal forward when editing, and write placeholders even where the file around them holds literals. Report the tenant's own literals as a finding without printing them; rotation is a separate ticket.
