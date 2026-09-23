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

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Target tenant folder `src/Tenants/<TenantName>/`. Prompted from a menu if omitted |
| `--source <SYS>` | Pre-select one or more upstream systems; repeatable. Skips the source menu |
| `--endpoint <key>` | Pre-select individual operations by catalogue key; repeatable. Skips the endpoint menu |
| `--base-path <path>` | Route group prefix. **Default: none** — routes sit at the tenant root. Pass one only when the tenant already groups its own surface under a prefix |
| `--tag <Tag>` | Swagger tag for the group. Default `EServices` |
| `--mode <mode>` | `inherit` \| `common` \| `routes`. Default chosen per step 4 |
| `--dto shared\|tenant` | Return the shared response models, or tenant DTOs plus a mapper. Default `shared` |
| `--all` | Every operation in the catalogue — equivalent to `--mode inherit` |
| `--new` | Tenant does not exist yet; scaffold it with `tenant-init` first |
| `--list` | Print the catalogue (step 1) and stop. No files written |
| `--gate <n>/<N>`, `--recommend proceed\|skip` | Gate mode, set by `tenant-pipeline` |
| `--auto` | No questions. Uses `--source` / `--endpoint` / `--all` as given; with none of them, stops with `missing --source <SYS> or --all` |
| `--dry-run` | Stop at the confirmation in step 3 and write nothing |

`--source` and `--endpoint` combine: sources expand to all their operations, then `--endpoint` adds individual ones.

## Gate

Only with `--gate <n>/<N>`. **One** `AskUserQuestion` call holds the gate and, unless `--source`, `--endpoint` or `--all` was passed, the group question from 3b (R4). Which e-Services to expose has no default.

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/integrate-shared <T>` — republish shared e-Services (NIR, PACRA, ZRA…) on this tenant through `EServicesShared`. Run it? | `Proceed` — every operation of the groups picked below, `routes` mode (`inherit` if everything is picked), tag `EServices`, no base path, shared response models · `Customize…` — also choose operations, Swagger tag, module mode, response models · `Skip` · `Stop` |
| `e-Services` | The 3b group question | the four groups |

`(Recommended)` goes on `Proceed` with `--recommend proceed`, and on `Skip` with `--recommend skip`. The option order doesn't change. `Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`.

With `Proceed`, skip 3c and 3d: every operation of the picked groups is exposed, and step 3's confirmation shows them. With `Customize…`, ask 3c and 3d as well.

## 1. Rescan the catalogue

Never answer from the table in step 2 alone — `EServicesShared` changes. Rebuild the list first:

```bash
grep -nE '^\s*#region|^\s*#endregion|public async Task<Result' src/Core/Shared/Services/EServicesShared.cs
grep -n 'gateway\.\(Get\|Post\|Patch\|Put\|Delete\)' src/Core/Shared/Services/EServicesShared.cs
grep -n 'public static' src/Core/Shared/Mapper/EServicesSharedMappingExtensions.cs
ls src/Core/Shared/Models/
```

The `#region` names are the upstream systems. Each `public async Task<Result<...>>` inside a region is one operation; the `gateway.*` call below it gives the real upstream path. Reconcile the result with step 2 and report any operation present in the file but missing from the table — then include it in the menu anyway.

## 2. Catalogue

`map` is the `Func<TSource, TResponse>` argument; every mapper listed lives in `Shared.Mapper.EServicesSharedMappingExtensions` and every model in `Shared.Models.<SYS>`. Generic operations (`<TResponse, TSource>`) let the tenant substitute its own response DTO — default to the shared one unless the tenant already declares its own under `src/Tenants/<TenantName>/Models/`.

### NIR — National Identity Register (`/t/ndw/graphql`, `/t/ndw/nir/*`)

| Key | Method | Suggested route | Result |
|---|---|---|---|
| `nir.person.document` | `GetPersonByIdentityDocument(documentNumber, documentType = 1, documentCountry = "ZMB")` | `GET /nir/persons/identity-document` | `PersonResponse` |
| `nir.person.nrc` | `GetPersonByNrc(nrc)` | `GET /nir/persons/nrc/{nrc}` | `PersonResponse` |
| `nir.person.zampass` | `GetPersonByZamPassId(Guid zamPassId)` | `GET /nir/persons/zampass/{zamPassId:guid}` | `PersonResponse` |
| `nir.person.create` | `CreatePerson(NirPersonAddRequest)` | `POST /nir/persons` | `NirPerson` → `PersonCreatedResponse` |
| `nir.person.update` | `UpdatePerson(Guid id, NirPersonUpdateRequest)` | `PATCH /nir/persons/{id:guid}` | `202 Accepted` |
| `nir.person.update-zampass` | `UpdatePersonByZamPassId(Guid zamPassId, NirPersonUpdateRequest)` | `PATCH /nir/persons/zampass/{zamPassId:guid}` | `202 Accepted` |

Non-generic — the response type is fixed. `nrc` arrives URL-encoded; `WebUtility.UrlDecode` it before the call (see `src/Core/Shared/Modules/EServicesSharedModule.cs`).

### NBR / PACRA — companies, cooperatives, societies

| Key | Method | Suggested route | `TSource` → `TResponse` / `map` |
|---|---|---|---|
| `nbr.entity` | `GetEntityByRegistrationNumber<TResponse, TSource>(registrationNumber, map, ct, usePacraService = true)` | `GET /nbr/entities/{registrationNumber}` | `BusinessEntity` → `BusinessEntityResponse` / `ToBusinessEntityResponse()` |
| `doc.cooperative` | `GetCooperativeByRegistrationNumber<TResponse, TSource>(registrationNumber, map)` | `GET /doc/entities/{registrationNumber}` | `Cooperative` → `CooperativeResponse` / `ToCooperativeResponse()` |
| `srs.society` | `GetSocietyByRegistrationNumber<TResponse, TSource>(registrationNumber, map)` | `GET /srs/entities/{registrationNumber}` | `Society` → `SocietyResponse` / `ToSocietyResponse()` |

### ZDI — Department of Immigration

| Key | Method | Suggested route | `TSource` → `TResponse` / `map` |
|---|---|---|---|
| `zdi.permit` | `GetZdiPermitByPermitNumber<TResponse, TSource>(permitNumber, map)` | `GET /zdi/permits/{permitNumber}` | `Permit` → `PermitResponse` / `ToPermitResponse()` |
| `zdi.permits.passport` | `GetZdiPermitsByApplicantPassportNumber<TResponse, TSource>(applicantPassportNumber, map, returnOnlyActivePermits = false, page = 0, pageSize = 10)` | `GET /zdi/permits` | paginated `Permit` |
| `zdi.immigrant.passport` | `GetZdiImmigrantByPassportNumber<TResponse, TSource>(passportNumber, map)` | `GET /zdi/immigrants` | `Immigrant` → `ImmigrantResponse` / `ToImmigrantResponse()` |
| `zdi.immigrant.permit` | `GetZdiImmigrantByPermitNumber<TResponse, TSource>(permitNumber, map)` | `GET /zdi/immigrants` | `Immigrant` → `ImmigrantResponse` |
| `zdi.passport` | `GetZdiPassportDetails<TResponse, TSource>(passportNumber, passportCountryCode, map)` | `GET /zdi/passports/{passportNumber}` | `Permit` |

`zdi.immigrant.passport` and `zdi.immigrant.permit` share one route in `src/Tenants/DOC/Modules/CommonModule.cs` — it branches on which query value is present. Generate that single `GET /zdi/immigrants` when both are selected.

### Other sources

| Key | Method | Suggested route | `TSource` → `TResponse` / `map` |
|---|---|---|---|
| `nlr.lot` | `GetLotByPropertyNumber<TResponse, TSource>(propertyNumber, map)` | `GET /nlr/lots/{propertyNumber}` | `Lot` → `LotResponse` / `ToLotResponse()` |
| `zda.permits` | `GetZdaPermitsByEntityNumber<TResponse, TSource>(entityNumber, map, page = 0, pageSize = 10)` | `GET /zda/permits/{entityNumber}` | `Permit` → `PermitResponse` / `ToPermitResponse(sectorTypes)` |
| `nair.student` | `GetStudentByLegalId<TResponse, TSource>(legalId, countryCode, map)` | `GET /nair/students/{legalId}` | `NairStudent` → `Student` / `ToStudent()` |
| `zra.tcc` | `GetTaxpayerTcc(tpin, nrc, brn)` | `GET /zra/taxpayers/tcc` | `TaxClearanceCertificateResponse` |
| `zra.taxpayer` | `GetTaxpayer(tpin = "", taxpayerName = "", nrc = "", brn = "")` | `GET /zra/taxpayers` | `List<TaxpayerResponse>` |
| `moh.facilities` | `GetMohFacilitiesByName<TResponse, TSource>(name, map, page = 0, pageSize = 10)` | `GET /moh/facilities` | `Facility` → `FacilityResponse` / `ToFacilityResponse()` |

`zda.permits` takes `Func<TSource, List<SectorsType>, TResponse>` — two arguments, not one; the service fetches `/t/ndw/zda/sector-types` itself and passes the list in. `zra.tcc` and `zra.taxpayer` are non-generic. Both ZRA operations resolve a TPIN from NRC or BRN when `tpin` is empty, so expose all three as optional query parameters.

## 3. Interactive menu

Skip any step whose answer arrived as an argument. Use `AskUserQuestion`, one question at a time so each answer narrows the next.

**3a — Tenant.** Only if `<TenantName>` is absent:

```bash
ls src/Tenants
grep -rln "EServicesShared" src/Tenants --include=Program.cs
```

Offer the tenants that already inject `EServicesShared` first (extending an existing integration), then the rest. A tenant not in `src/Tenants` means `--new` — run `tenant-init` before continuing.

**3b — Groups.** Header `e-Services`, `multiSelect: true`. The ten regions don't fit in 4 options, so group them. Take the counts from the step 1 rescan, not from this example:

| Option | Covers |
|---|---|
| `Identity — NIR (6 operations)` | NIR |
| `Business registries — NBR, DOC, SRS (3)` | NBR / PACRA, cooperatives, societies |
| `Immigration — ZDI (5)` | permits, immigrants, passports |
| `Land, tax, health, education — NLR, ZDA, ZRA, MOH, NAIR (6)` | the rest |

A region the rescan finds that isn't in this table joins the last group, with its name added to the label. The question text says "Pick every group you need; each one is expanded to its operations next". There is no `All sources` option: picking all four groups means the same thing, and sets `--all`.

**3c — Operations.** Asked under `Customize…`, or without a gate when no `--endpoint` was passed. `multiSelect: true` over the operations of the chosen groups, each option labelled `METHOD /route — purpose` (`GET /nir/persons/nrc/{nrc} — person by NRC`). One question per group, at most 4 questions per call (R9). A group with more than 4 operations shows 3 plus `All <n> <group> operations`, which selects the rest. The question text says that only the ticked operations are exposed.

**3d — Placement.** `Customize…` only, one call:

| Header | Options |
|---|---|
| `Tag` | `EServices (Recommended)` · the tag the tenant's existing modules already use, if there is one |
| `Mode` | The step 4 default `(Recommended)` · the other two modes, each with its one-line "use when" from step 4 |
| `Models` | `Shared response models (Recommended)` · `Tenant DTOs + mapper` |
| `Base path` | Only when the tenant's existing modules already group under a prefix: `None (Recommended)` · that prefix |

Then one R6 confirmation. The question text is the table — key, method, route, response model — plus the files to write and the equivalent command. Options `Apply (Recommended)` · `Adjust` · `Cancel`. `Adjust` re-asks whichever of 3b, 3c or 3d is picked. With `--dry-run`, print it and stop.

## 4. Choose the module mode

| Mode | Shape | Use when |
|---|---|---|
| `inherit` | `public class EServicesModule(EServicesShared services) : EServicesSharedModule("EServices", services);` | The tenant takes the full shared surface. The canonical one-liner — `src/Tenants/ZPS/Modules/EServicesModule.cs`. The two-argument overload takes no base path; `src/Tenants/GOVZM/Modules/EServicesModule.cs` passes `"/eservices"` to the three-argument one, which is the exception |
| `common` | Abstract `CommonModule` in the tenant holding the selected routes plus a `virtual AddAdditionalRoutes(RouteGroupBuilder)` hook, with one thin concrete module per consumer | The tenant publishes the same subset under several base paths or tags — `src/Tenants/MCTI/Modules/CommonModule.cs`, `src/Tenants/DOC/Modules/CommonModule.cs` |
| `routes` | One plain `ICarterModule` with only the selected routes | A subset exposed once. The default |

Default to `inherit` when the selection is every operation, `common` when the tenant already has a `CommonModule`, otherwise `routes`.

`EServicesSharedModule` is all-or-nothing — it maps its full route set. Never subclass it to expose a subset; generate the routes instead.

In `inherit` mode the module body stays empty. `EServicesSharedModule.AddRoutes` already does `app.MapGroup(basePath).WithTags(tags)` and maps every route onto it, so the tenant module must not declare `var group = app.MapGroup("").WithTags("EServices");` or map anything itself — the base path and tag are the constructor arguments. Only `routes` and `common` mode create the group.

## 5. Wire the tenant

**`src/Tenants/<TenantName>/<TenantName>.csproj`** — must reference `Shared`:

```xml
<ProjectReference Include="..\..\Core\Shared\Shared.csproj" />
```

**`src/Tenants/<TenantName>/Program.cs`** — add, next to the existing `RegisterEndpoints` call:

```csharp
builder.Services.RegisterGatewayEndpoint(builder.Configuration);
builder.Services.AddTransient<EServicesShared>();
```

with `using Shared.Extensions;` and `using Shared.Services;`. `RegisterGatewayEndpoint` registers the `Gateway` client from the `Shared` assembly; the tenant's own `RegisterEndpoints(Assembly.GetExecutingAssembly(), ...)` does not see it. Both calls are needed when the tenant also has its own `Endpoints/`.

**`appsettings.json` and `appsettings.Development.json`** — the gateway section. The key must be exactly `Gateway`, matching the class name `Shared.Endpoints.Gateway`; a mismatch logs `Endpoint Gateway is not configured` and the client silently gets no `HttpClient`.

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

Credentials stay as `__Credentials.*__` placeholders, replaced at deploy time. Never commit a real one. In `appsettings.Development.json` the `BaseUrl` may be the real test gateway.

If the tenant already has other `Endpoints` entries, add `Gateway` as a sibling — do not replace the object.

## 6. Generate the module

`src/Tenants/<TenantName>/Modules/EServicesModule.cs` for `routes` and `inherit`; `CommonModule.cs` plus concrete modules for `common`.

The `MapGroup` below belongs to `routes` and `common` mode only. An `inherit` module has no `AddRoutes` override at all — mapping the group there would duplicate the shared route set.

**No base path.** The group exists to carry the Swagger tag, not to add a segment. Routes sit directly under the tenant's gateway route, so `nir.person.nrc` is called at `/t/<route>/nir/persons/nrc/{nrc}` — never `/t/<route>/eservices/nir/...`. That is what the published API specifications document (`GET /t/dam/nir/persons/nrc/:nrc`) and what `EServicesSharedModule`'s two-argument constructor produces. Adding `/eservices` puts a segment in the contract that no consumer expects and that the tenant's own specification does not describe.

```csharp
public class EServicesModule(EServicesShared services) : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("").WithTags("EServices");

        group.MapGet("/nir/persons/nrc/{nrc}",
                async (string nrc, CancellationToken cancellationToken) =>
                {
                    var result = await services.GetPersonByNrc(WebUtility.UrlDecode(nrc), cancellationToken);
                    return result.IsSuccess ? Results.Ok(result.Value) : CustomResults.Problem(result);
                })
            .Produces(StatusCodes.Status200OK, typeof(PersonResponse))
            .Produces(StatusCodes.Status404NotFound, typeof(ProblemDetails))
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
            .Produces(StatusCodes.Status500InternalServerError, typeof(ProblemDetails));
    }
}
```

Rules:

- `CustomResults.Problem(result)` (`Internal.Domain.Shared.Result`) is the only failure path — it turns `Error` into RFC 7807 `ProblemDetails`
- Every handler takes `CancellationToken` and passes it through
- `.Produces(...)` for the success type and for every `ProblemDetails` status the operation can return — this feeds Swagger and the generated API specification
- `POST` that creates returns `Results.Created`; `PATCH` returns `Results.Accepted()`
- Route segments are lowercase and grouped by source: `/<source>/<resource>/{key}` — the source name is the only grouping in the path
- `ImplicitUsings` is off in the tenant projects, so the module needs `using System.Threading;` for `CancellationToken`. Missing it is a build error, not a warning
- Reuse the shared response models from `Shared.Models.<SYS>`. Only introduce a tenant DTO under `src/Tenants/<TenantName>/Models/<SYS>/` when the tenant's contract genuinely differs, and then add the mapper to `src/Tenants/<TenantName>/Mapper/<TenantName>MappingExtensions.cs` — follow `src/Tenants/DOC/Mapper/`
- Do not redeclare a model that already exists under `src/Core/Shared/Models/`

Generic calls need both type arguments named explicitly (`<BusinessEntityResponse, BusinessEntity>`) — inference does not reach `TSource` through the `Func`.

## 7. Verify

```bash
dotnet build src/Tenants/<TenantName>/<TenantName>.csproj -v q --nologo
```

Must report `0 Error(s)`. Then, without running the app:

- `Endpoints:Gateway` exists in **both** appsettings files, with placeholder credentials
- `RegisterGatewayEndpoint` and `AddTransient<EServicesShared>()` are both in `Program.cs`
- Every selected operation has exactly one route, and no route was generated for an operation the user deselected
- No route collides with one the tenant already exposes — `grep -rn "MapGroup\|MapGet\|MapPost" src/Tenants/<TenantName>/Modules/`
- Every generic call passes both type arguments and a `map` delegate

The new routes change the tenant's contract. Outside `tenant-pipeline`, which runs it for you, name `/tenant-deliverables <TenantName>` as the next step: it regenerates the OpenAPI JSON, DOCX specification and Postman collection.

## Report

One line per file added or changed, then a table of the exposed routes (method, path, shared operation, upstream gateway path). Close with what stays outside this skill: the gateway credentials themselves, the tenant's entitlement to each e-Service on the gateway side, the Helm `values.tenant.yaml` entry, and the `azure-pipelines.yaml` stage.

End with the equivalent command (R7), e.g. `/integrate-shared PQPS --source NIR --endpoint nbr.entity --mode routes`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when the build in step 7 fails.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
