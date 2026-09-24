---
name: tenant-integration
description: Build the integration surface of an existing ZamConnect tenant — upstream REST or SOAP client(s) under Endpoints/, request/response models, mappers, and the Carter modules or controllers the tenant exposes. Takes a tenant name plus integration sources (Postman collection, Swagger/OpenAPI spec, REST base URL, SOAP WSDL, or prose API documentation) and an optional list of endpoints to expose; the source artefact decides whether the client derives from RestEndpoint or SoapEndpoint. Use when the user says "integrate <Tenant> with <System>", "add <API> to <Tenant>", "consume this WSDL", "expose these endpoints on <Tenant>", or types /tenant-integration.
argument-hint: "<TenantName> [--source <url|path>...] [--expose <METHOD /route>...] [--protocol rest|soap] [--auth Basic|JWT|Custom|RA|None (REST) · Basic|ClientCertificate|None (SOAP)] [--auth-header <name>] [--system <Name>] [--role provide|consume] [--dto public|passthrough] [--modules system|domain] [--timeout <seconds>] [--no-spec-ready] [--spec-only] [--auto] [--dry-run]"
disable-model-invocation: false
---

# ZamConnect Tenant Integration

Implement the business surface of a tenant that already exists (scaffold it first with `tenant-init`). This skill covers the two halves of an integration:

- **Consume** — the upstream API the tenant talks to, wrapped in a `RestEndpoint` or `SoapEndpoint` client
- **Expose** — the routes the tenant publishes to its own consumers

The tenant always exposes REST. What it consumes is whatever the upstream speaks, and that is decided by the integration sources, not by preference — see step 1a.

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`, R12 above all: **every option is a complete answer**. This skill never offers a source *type* as an option, never asks for anything the source already says (protocol, SOAP version, operations, auth block), and never writes "pick Other and…" in an option.

Shared repo facts — usings/namespace (C1), `Error` → status (C2), `Username` casing (C3), token naming (C4), Carter DI lifetime (C5), file hygiene (C6), committed-secrets baseline (C7), live routes doc (C8) — live in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`. Read it before generating; this skill cites section ids instead of repeating them.

## Arguments

| Flag | Meaning | When absent |
|---|---|---|
| `<TenantName>` | Existing tenant under `src/Tenants/` | Required. If the folder is missing, run `tenant-init` first |
| `--source <url\|path>` | Integration source; repeatable | Asked (step 1, source question) |
| `--expose <METHOD /route>` | A route the tenant should expose; repeatable | Every upstream operation, confirmed in the review |
| `--protocol rest\|soap` | Overrides the classification in step 1a | Detected from the source |
| `--auth <scheme>` / `--auth-header <name>` | Upstream auth. REST: `Basic`, `JWT`, `Custom`, `RA`, `None`. SOAP: `Basic`, `ClientCertificate`, `None`. `--auth-header` goes with `Custom` | Detected from the source. Asked only when it can't be |
| `--system <Name>` | Upstream system name: the client class, `Models/<Name>/`, the config section and tokens | Derived from the source title. Asked only under `Customize…` or when there's nothing to derive it from |
| `--role provide\|consume` | Whether the exposed routes serve this tenant's own institution (`provide`) or data reached back through the gateway (`consume`). `tenant-deliverables` uses it to split the Consume/Provide documents | `provide` |
| `--dto public\|passthrough` | Public DTOs plus a mapper, or return the upstream shape as-is | `public` |
| `--modules system\|domain` | One Carter module per upstream system, or per business domain | `system` |
| `--timeout <seconds>` | Upstream `Timeout` (REST only), written to config as `hh:mm:ss` | 60 s, the `RestEndpointOptions` default (key omitted) |
| `--no-spec-ready` | Skip step 8 | Step 8 runs |
| `--spec-only` | Run only step 8 on the tenant's existing surface, then the step 7 build. No source is needed and no questions are asked. `tenant-deliverables` uses it to fix the code findings it reports | Full integration |
| `--gate <n>/<N>`, `--recommend` | Gate mode, set by `tenant-pipeline` | No gate |
| `--auto` | Every `(Recommended)` default, no questions. Stops with `missing --source <url\|path>` if there's none | Interactive |
| `--dry-run` | Stop at the review (step 1, review) and write nothing | Writes |

## Gate

Only with `--gate <n>/<N>`. **One** `AskUserQuestion` call holds the gate and, unless `--source` was passed, the source question (R4). The source is required and has no default.

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/tenant-integration <T>` — build the upstream client, models, mappers and exposed routes. Run it? | `Proceed (Recommended)` — protocol and auth detected from the source, every operation exposed, public DTOs + mapper, spec-ready · `Customize…` — also choose system name, auth, data role, DTO strategy, module grouping, timeout · `Skip` · `Stop` |
| `Source` | The source question from step 1 below | discovered sources |

`Skip` → end with `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`. Either way, ignore the source answer.

## 1. Collect inputs

Don't write code until every input is settled. Ask through `AskUserQuestion` only, never in plain text.

### Discover sources

Before asking anything, look for sources on disk. Files whose name contains the tenant code come first:

```bash
find "src/Tenants/<T>/Deliverables/Integration Requests" "postman collections" . -maxdepth 2 -type f \( -iname "*.wsdl" -o -iname "*.postman_collection.json" -o -iname "*swagger*.json" -o -iname "*swagger*.yaml" -o -iname "*openapi*.json" -o -iname "*openapi*.yaml" -o -iname "*.docx" -o -iname "*.pdf" \) 2>/dev/null
```

Skip anything under `bin/`, `obj/` or `node_modules/`, and skip other tenants' `Deliverables/`. For each candidate, peek at it (the first request of a collection, `openapi`/`swagger` and `info.title` of a spec, the `wsdl:service` name) so the option can say what it is.

### Source question

Header `Source`, `multiSelect: true`. Leave it out when `--source` was passed.

**When candidates were found**, each option *is* a source: label is the path relative to the repo, description is what the peek found.

```
Integration source for TT — select one or more, or paste a URL or path in Other.
  [ ] postman collections/TT.postman_collection.json    Postman · 12 requests · JSON bodies (REST)
  [ ] Integration Requests/tt-service.wsdl              WSDL · SOAP 1.1 · 5 operations
  [ ] Integration Requests/TT API Guide.docx            API document · converted to Markdown first
```

With more than 3 candidates, show the best 3 plus `Show all <N> found`. That option re-asks with the rest, spread over up to 4 questions (R9).

**When nothing was found**, single-select:

```
No integration source for TT in the repo. Paste a URL or path in Other, or:
  ( ) Search Downloads and Desktop     .wsdl / Postman / OpenAPI / .docx / .pdf changed in the last 30 days
  ( ) Wait while I add files           creates Integration Requests/, then rescans
  ( ) Skip the integration for now
```

- `Search Downloads and Desktop` — run the same `find` over `"$HOME/Downloads" "$HOME/Desktop"` with `-mtime -30`, then ask the found-candidates form. If that finds nothing too, fall back to this question without that option.
- `Wait while I add files` — `mkdir -p "src/Tenants/<T>/Deliverables/Integration Requests"`, say where it is, then ask `Files added?` with `Rescan (Recommended)` / `Skip the integration for now`.
- `Skip the integration for now` — end. In gate mode: `GATE-RESULT: skipped`.

Other may hold several sources, one per line. A local file from outside the repo belongs in `Integration Requests/` — offer to copy it there as part of the review, not as a separate question.

### Resolve the sources

- Local file → read it directly
- `.docx` / `.pdf` / `.xlsx` → `convert-documents-to-markdown` skill first
- URL → fetch it; for a Swagger UI URL fetch the underlying `/swagger/v1/swagger.json`, for a SOAP service URL try `?wsdl` / `?singleWsdl`
- Postman collection → parse `item[]` recursively; each leaf `request` gives method, URL, headers, and an example body. A collection can describe a SOAP service too — see step 1a
- WSDL → read `wsdl:portType`/`wsdl:operation` for the operation list, `wsdl:binding` for the SOAP version and `soapAction` values, `wsdl:service`/`soap:address` for the endpoint URL, and the inline or imported `xsd:schema` for the message types (including `minOccurs` and `nillable` — step 4b needs them)

Record, for every upstream operation you intend to call: its name, the request and response message shapes, and the failure signals that carry meaning — non-200 codes for REST, `Fault` codes and reasons for SOAP.

Then classify (step 1a) and **echo what was read** (R11) before asking anything else:

```
Read as: Postman collection · 12 requests in 3 folders · REST (JSON bodies) · Basic auth at collection level
```

### Detect the rest

Take these from the source, not from the developer:

| Input | Where it's detected |
|---|---|
| Protocol, SOAP version | Step 1a; `wsdl:binding` |
| Auth | OpenAPI `components.securitySchemes`; Postman `auth` at collection, folder or request level; `Authorization` / `X-Api-Key`-style headers on requests; WS-Security policy in the WSDL |
| System name | OpenAPI `info.title`, the Postman `info.name`, `wsdl:service/@name`, the document title. Reduced to a PascalCase class name (`PqpsService` → `Pqps`) |
| Operations and groups | OpenAPI tags; Postman folders; `wsdl:portType` operations |
| Per-operation URLs (SOAP) | More than one `soap:address`, or operations documented at different paths |
| Full descriptive name | Only when the state file has `fullName: "pending"`: the same titles as for the system name |

A token-login upstream (log in, receive a token, send it on later calls — ZRA, NAPSA, WCF, NHIMA, ZESCO) has no scheme value: it needs a hand-written service around the client. Say so in the review.

### Proposal questions

**With `Proceed`, or no gate:** ask only what detection left open, in one call of at most 4 questions. When everything was detected, skip straight to the review.

**With `Customize…`:** ask all four questions of the proposal call, then the customize call, whether detected or not. The detected value is always the first option, marked `(Recommended)`.

Proposal call:

| Header | Question | Options (each a complete answer) |
|---|---|---|
| `Auth` | How does `<T>` authenticate to `<System>`? | The detected scheme first, naming where it came from: `Basic (collection auth)`, `Custom header X-Api-Key (securitySchemes)`. Then the other supported schemes, to 4 in total. REST: `Basic`, `JWT bearer`, `Custom header`, `None`; the question text says "`RA` (DotGov internal services only): type it in Other". SOAP: `Basic`, `Client certificate`, `None` |
| `System` | Upstream system name for the client class and config | The derived name `(Recommended)`, e.g. `Pqps — from wsdl:service PqpsService`; the tenant code; the source's short title, if different |
| `Role` | Where does the data behind these routes come from? | `Provide — <T>'s own institution (Recommended)` · `Consume — another system reached through the gateway` |
| `Name` | Only when `fullName` is `pending`: full descriptive name of `<T>` for the spec title | Titles found in the sources, the most specific first · `Use <T> for now` |

When `Custom header` is picked and no header name was detected, follow up with `Header name?`, offering the header names found on the source's requests.

Customize call (`Customize…` only):

| Header | Question | Options |
|---|---|---|
| `DTOs` | Response shaping | `Public DTOs + mapper (Recommended)` · `Pass-through — shared model already exists` |
| `Modules` | Module grouping | `One module per upstream system (Recommended)` · `One module per business domain` |
| `Timeout` | Upstream timeout (REST only) | `Default — 60 s (Recommended)` · `30 s` · `120 s` · `300 s` |
| `Spec` | Make the surface spec-ready now (step 8)? | `Now (Recommended)` · `Later` — adds `--no-spec-ready` |

### Endpoint selection

Asked with `Customize…`, or when `--expose` is absent and there are more than 3 operation groups. `multiSelect`. Options are the groups found (`Pesticides — 3 operations`), or single operations (`GET /pesticides/{id} — pesticide by id`) when there are 3 or fewer, plus `All operations (Recommended)`. More than 3 groups go over up to 4 questions (R9). With `Proceed` and 3 or fewer groups, everything is exposed and the review shows it.

### Review before writing

One R6 call. The question text is the plan, the options `Apply (Recommended)` · `Adjust` · `Cancel`:

```
Integrate TT with Pqps (SOAP 1.1, Basic):
  Endpoints/Pqps.cs                     SoapEndpoint, 5 operations
  appsettings.json + .Development.json  SoapEndpoints:Pqps (+ 5 per-operation URLs)
  Models/Pqps/                          5 request/response pairs, PqpsSoapEndpointOptions
  Mapper/TtMappingExtensions.cs
  Modules/PqpsModule.cs                 MapGroup("/pqps"), tag PQPS
  Program.cs                            + RegisterSoapEndpoints, Configure<PqpsSoapEndpointOptions>
New deploy tokens: __SoapEndpoints.Pqps.BaseUrl__, .Username__, .Password__, 5 × .<Op>Url__
Routes:
  GET  /t/tt/pqps/pesticides            list pesticides
  POST /t/tt/pqps/validate/ephyto       validate an ePhyto certificate
Command: /tenant-integration TT --source "src/Tenants/TT/Deliverables/Integration Requests/tt-service.wsdl" --auth Basic --system Pqps --role provide
```

`Adjust` asks one `multiSelect` — `Source`, `Endpoints`, `Auth`, `System`, `Role`, `DTOs / modules / timeout` — and re-asks only what was picked. `Cancel` ends; in gate mode, `GATE-RESULT: stopped`. With `--dry-run`, print the plan and end here. With `--auto`, apply without asking.

## 1a. Decide the client base class

Read the sources first, then classify. The artefact tells you what the upstream speaks:

| Source artefact | Protocol | Base class |
|---|---|---|
| Swagger / OpenAPI spec | REST | `RestEndpoint` |
| REST base URL + prose docs | REST | `RestEndpoint` |
| Postman collection, JSON bodies, varied verbs, resource paths | REST | `RestEndpoint` |
| **WSDL** (`.wsdl`, `?wsdl`, `?singleWsdl`) | SOAP | `SoapEndpoint` |
| Postman collection where every request is `POST` to one URL with an XML `<soap:Envelope>` body and a `SOAPAction` header | SOAP | `SoapEndpoint` |
| Prose docs quoting XML envelopes, `xmlns:soap`, `wsdl:operation` or `SOAPAction` | SOAP | `SoapEndpoint` |

A Postman collection is the ambiguous case, and the body decides it, not the file type — a collection of `POST`s carrying `<soap:Envelope>` is a SOAP integration dressed as a REST artefact. Check an actual request body before choosing.

Everything downstream follows from this one choice:

| | REST | SOAP |
|---|---|---|
| Base class | `Internal.Clients.RestEndpoint` | `Internal.Clients.SoapEndpoint` |
| Marker type scanned | `IRestEndpoint` (interface) | `ISoapEndpoint` (a class, despite the name) |
| Instantiation | `ActivatorUtilities.CreateInstance(sp, type, client)` — extra DI constructor args allowed (`IOptions<JsonSerializerOptions>`, APIS `IOptions<ApisOptions>`) | `Activator.CreateInstance(type, client)` — `HttpClient` only |
| Config section | `Endpoints:<ClassName>` | `SoapEndpoints:<ClassName>` |
| Registration in `Program.cs` | `RegisterEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration)` | `RegisterSoapEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration)` |
| Auth schemes supported | `Basic`, `JWT`, `Custom`, `RA` — **case-sensitive** exact match; anything else (`basic`, `None`, missing) sends no auth | `Basic`, `ClientCertificate` — case-insensitive; `AuthenticationScheme` key **required** (missing → `NullReferenceException` at startup); anything else = no auth |
| Payloads | `System.Text.Json` | `XmlExtensions.Serialize` / `Deserialize` |
| Client section | Step 4 | Step 4b |

A tenant may do both — `RegisterEndpoints` and `RegisterSoapEndpoints` are independent and can be called side by side, each scanning the same assembly for its own marker type. IFMIS is the reference for a tenant that consumes SOAP while exposing REST.

If the sources are genuinely silent on protocol, ask with header `Protocol`: `REST — JSON over HTTP` / `SOAP — XML envelopes`, with the reason detection failed in the question text. Do not assume REST. Reaching a SOAP service with a `RestEndpoint` fails at the first call with an unparseable response, not at build time. `--protocol rest|soap` overrides the classification when the user already knows.

## 2. Read the tenant and its neighbours

```bash
find src/Tenants/<TenantName> -type f -not -path "*/bin/*" -not -path "*/obj/*"
grep -rlE ":\s*(RestEndpoint|SoapEndpoint)\b" src/Tenants/<TenantName> --include=*.cs
grep -E "<ImplicitUsings>|<Nullable>" src/Tenants/<TenantName>/<TenantName>.csproj
```

Existing clients may live outside `Endpoints/` (APIS `Zims/ZimsApi.cs`) — the grep finds them. The csproj decides the using block and nullability (C1).

Reference implementations — each for one thing only:

- `src/Tenants/APIS` — REST client on a `*Async` method (`Zims/ZimsApi.cs`), options injected into the client, and the Swagger metadata for step 8. **Not** a folder-layout reference: new code keeps `Endpoints/`, `Models/<SYSTEM>/`, `Mapper/`, `Modules/`
- `src/Tenants/CEEC` — one Carter module per resource. Its client `Endpoints/ZamConnect.cs` switches on the status of the throwing `Get` — don't copy that call (step 4)
- `src/Tenants/MOH` — `Mapper/MohMappingExtensions.cs`, and `EServicesShared` for shared NIR/NBR calls: `builder.Services.RegisterGatewayEndpoint(builder.Configuration);` + `builder.Services.AddTransient<EServicesShared>();` (`using Shared.Extensions;`, `using Shared.Services;`)
- `src/Tenants/MOA` — controllers variant
- `src/Tenants/PQPS/Endpoints/GensHub.cs` — the minimal SOAP client (it uses the throwing `PostSoap11`; new code uses the `Result` variants)
- `src/Tenants/IFMIS` — per-operation SOAP URLs only (`Models/Ifmis/IfmisSoapEndpointOptions.cs`, `appsettings.json`). Its module returns raw SOAP DTOs and mutates the client with `SetOptions` — copy neither
- `src/Tenants/PSPF` — SOAP action *format* only (`urn:…:<actionName>`); its `Client.SetHeader("SOAPAction", …)` races (step 4b)

Before defining a new model, check `src/Core/Shared/Models/` — NIR, NBR, DOC, SRS shapes already exist and should be reused rather than redeclared.

## 3. Configure the upstream endpoint

Both registrars work the same way: scan the assembly for the marker type, then bind the configuration section named after the class. **The section key must equal the class name** (the lookup is `IConfiguration`, so case-insensitive). A client with no matching section logs `Endpoint {Name} is not configured` (`SOAP Endpoint {Name} is not configured` for SOAP; SOAP also skips a blank `BaseUrl`) and is **never registered in DI** — any module that injects it then fails at `MapCarter()`, so the tenant crashes on startup. It still builds.

`BaseUrl` is turned into `new Uri(...)` when the client is first created — at `MapCarter()` for a constructor-injected client. It must be a valid absolute URL in **both** files; a placeholder left in `appsettings.Development.json` crashes local runs and the Swagger export that `api-spec-sync` and `tenant-deliverables` run. When `BaseUrl` carries a path (`https://host/api/v2/`), end it with `/` and call relative paths with no leading `/` (`things/{id}`) — a leading `/` drops the base path.

Config keys follow C3: JSON key and token are always `Username`, the C# property is `UserName`. Tokens follow C4; every new `__Token__` needs a variable in `GSB.<TENANT>.<ENV>` and in `projects-variables`, or the deploy fails (`actionOnMissing: fail`).

### REST

Add to both `appsettings.json` and `appsettings.Development.json`:

```json
"Endpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "Basic",
        "BaseUrl": "__Endpoints.<ClientClassName>.BaseUrl__",
        "Username": "__Endpoints.<ClientClassName>.Username__",
        "Password": "__Endpoints.<ClientClassName>.Password__"
    }
}
```

That is the external-upstream shape (APIS `ZimsApi`, `NpddApi`). Only a client that calls back into the ZamConnect gateway uses `__Endpoints.APIGATEWAY.BaseUrl__` + `__Credentials.<Folder>Tenant.Username|Password__` (C4).

Scheme values are matched **exactly** — `"basic"` configures no auth:

| `AuthenticationScheme` | Fields |
|---|---|
| `Basic` | `Username`, `Password` |
| `JWT` | `AuthHeaderValue` = `__Endpoints.<ClientClassName>.ApiKey__` (sent as bearer) |
| `Custom` | `AuthHeaderName` — the detected / `--auth-header` name, as a literal; `AuthHeaderValue` = `__Endpoints.<ClientClassName>.ApiKey__` |
| `RA` | DotGov Registration Authority service-to-service token — **internal DotGov services only** (GOVZM, NDR); never for an external system. Per endpoint `ApplicationScopes { Services[], Scopes[] }`; plus `builder.Services.RegisterRa();` (`using Internal.Extensions;`) and a top-level `RegistrationAuthority { BaseUrl, TokenGeneration { CallingServiceFqn, CertificateThumbprint, PrivateKey } }` section, every value a `__Token__`. Copy the shape from GOVZM/NDR `appsettings.json`, never a value |
| `None` | Nothing else. Write it explicitly |

`AuthHeaderValue` is always a token, never a value found in the source. Optional fields:

- `Timeout` is a `TimeSpan`: write `"00:02:00"`. A bare `"60"` is 60 **days**. Omit for the 60 s default
- `RetryCount` (int) — above 0 adds a retry policy. Only for idempotent upstream calls
- `DangerousAcceptAnyServerCertificate` — only for a test environment with a self-signed certificate, never production

REST has no client-certificate option: `RestEndpointOptions` carries no key fields.

### SOAP

A different top-level section — `SoapEndpoints`, not `Endpoints`:

```json
"SoapEndpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "Basic",
        "BaseUrl": "__SoapEndpoints.<ClientClassName>.BaseUrl__",
        "Username": "__SoapEndpoints.<ClientClassName>.Username__",
        "Password": "__SoapEndpoints.<ClientClassName>.Password__",
        "<Op>Url": "__SoapEndpoints.<ClientClassName>.<Op>Url__"
    }
}
```

`SoapEndpointOptions` carries only `BaseUrl`, `AuthenticationScheme`, `UserName`, `Password`, `PublicKey` and `PrivateKey`. `ClientCertificate` uses `PublicKey` + `PrivateKey` as base64 DER; `Basic` uses `Username`/`Password`.

- **`AuthenticationScheme` is always written.** A missing key throws `NullReferenceException` at startup. Use `"None"` for no auth
- **There is no `Timeout` and no `DangerousAcceptAnyServerCertificate` for SOAP.** `src/Tenants/PSPF/appsettings.json` sets the latter and it does nothing; do not copy it forward
- **Per-operation URLs: one property and one token per operation**, in both files, never hard-coded. A missing or empty value silently posts to `BaseAddress`. The properties live on `<ClientClassName>SoapEndpointOptions : SoapEndpointOptions` — see step 4b

### Development file

`appsettings.Development.json` gets the same keys. Only `BaseUrl` may be real (the upstream's test URL, or any valid absolute stand-in); credentials, keys and tokens stay `__Token__` placeholders. Many tenants' Development files commit literal credentials (C7) — never use one as the template for values, and never copy a value forward.

## 4. Write the REST client — `Endpoints/<ClientClassName>.cs`

Skip to step 4b for a SOAP upstream.

Every template in steps 4–6 is a complete file: full `using` block, sorted with `System*` first, and a file-scoped namespace (C1). They compile with `ImplicitUsings` off. Use `string?` / `T?` only where the csproj enables `<Nullable>`. Line endings and BOM: C6.

Derive from `Internal.Clients.RestEndpoint`; take `HttpClient` and `IOptions<JsonSerializerOptions>` (the instance `Program.cs` configures with `PropertyNameCaseInsensitive = true`; the `tenant-init` scaffold has it). Return `Result<T>` / `Result` from `Internal.Domain.Shared.Result` — never throw across the client boundary.

**Base-method rule:** the non-`Async` methods (`Get`, `Post`, `Put`, `Patch`, `Get<T>`, `Post<TReq,TRes>`) call `EnsureSuccess()` and **throw** on any non-2xx, so a status `switch` after them is dead code and every upstream 404 becomes a 500. The `*Async` methods (`GetAsync`, `PostAsync`, `PutAsync`, `PatchAsync`, `DeleteAsync`, `SendAsync`) return the response untouched. Always use the `*Async` ones.

```csharp
using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;
using Internal.Domain.Shared.Result;
using Microsoft.Extensions.Options;
using Serilog;
using <T>.Models.<SYSTEM>;

namespace <T>.Endpoints;

public class <ClientClassName>(HttpClient client, IOptions<JsonSerializerOptions> jsonOptions)
    : RestEndpoint(client)
{
    public async Task<Result<ThingDto>> GetThing(string id, CancellationToken cancellationToken)
    {
        try
        {
            using var response = await GetAsync($"things/{WebUtility.UrlEncode(id)}", cancellationToken);

            switch (response.StatusCode)
            {
                case HttpStatusCode.OK:
                    var model = await response.Content.ReadFromJsonAsync<ThingDto>(jsonOptions.Value, cancellationToken);
                    return model is null
                        ? Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"))
                        : Result.Success(model);

                case HttpStatusCode.NotFound:
                    return Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"));

                case HttpStatusCode.BadRequest:
                    Log.Warning("<SYSTEM> rejected GetThing: {Content}",
                        await response.Content.ReadAsStringAsync(cancellationToken));
                    return Result.Failure<ThingDto>(Error.BadRequest("thing_invalid_id", $"\"{id}\" is not a valid thing id"));

                default:
                    Log.Error("Unexpected response from <SYSTEM> API: {StatusCode}, {Content}",
                        response.StatusCode, await response.Content.ReadAsStringAsync(cancellationToken));
                    return Result.Failure<ThingDto>(Error.Internal());
            }
        }
        catch (Exception e)
        {
            Log.Error(e, "<SYSTEM> GetThing failed");
            return Result.Failure<ThingDto>(Error.Internal());
        }
    }
}
```

A request body goes through the same options: `PostAsync("things", JsonContent.Create(request, options: jsonOptions.Value), cancellationToken)`.

Rules:

- URL-encode every interpolated path and query value (`WebUtility.UrlEncode`); relative paths, no leading `/` (step 3)
- Error codes are snake_case and stable — consumers match on them
- Pick the `Error` by what the caller should see (C2): `BadRequest` (400) for rejected input or a business rule the caller can fix, `NotFound` (404), `Conflict` (409), `Problem` (**500**, not a 4xx) only for an upstream failure whose code the caller should see, `Internal()` for anything else. Never leak the upstream body to the caller; log it instead
- One method per upstream operation. Do not build a generic passthrough

STJ traps (the Newtonsoft → STJ migration hit each of these):

- `Get<T>` and `Post<TReq,TRes>` also ignore the tenant's options — they use web defaults (USSD regression). Never use them for upstream DTOs
- `Internal.Helpers.StjDefaults.Options` is the repo-wide Newtonsoft-compatible set: case-insensitive reads, PascalCase writes, `WhenWritingNull`. `response.GetPayloadAs<T>()` (`Internal.Extensions.Extensions.Http`) uses it — and returns `default` on a non-JSON content type or parse error, without failing
- An upstream that sends numbers where the model has `string`: `[JsonConverter(typeof(StringOrNumberConverter))]` (`Internal.Helpers`) on the property
- `[JsonIgnore]` blocks inbound binding as well as output. When a field must be read from the caller but not sent upstream (or the reverse), declare a separate outbound DTO
- `DefaultIgnoreCondition = WhenWritingNull` changes the wire format — omitted keys, not `null`. Decide per upstream whether it accepts absent keys

## 4b. Write the SOAP client — `Endpoints/<ClientClassName>.cs`

Derive from `Internal.Clients.SoapEndpoint`. **The constructor must take `HttpClient` and nothing else** — `RegisterSoapEndpoints` instantiates the class with `Activator.CreateInstance(type, client)`, so any extra constructor parameter is a runtime failure, not a compile error. Per-operation URLs therefore arrive as a method argument, supplied by the module.

Base methods (all `protected`; `payload`, then `cancellationToken`, then `url`):

| Method | SOAP | Returns | Behaviour |
|---|---|---|---|
| `PostSoap11Result<T>(payload, ct, url)` | 1.1 | `Result<T>` | Default. 200 → deserialized, or a `<Fault>` in the 200 → logged + `Internal()`. 404 → `NotFound("not_found")`. 504 → `Problem("gateway_timeout")` (500). Any other status — including a standard HTTP-500 SOAP fault — → `Internal()` with **nothing logged**. 200 without an envelope → `NullValue` / `Internal()` (500) |
| `SendSoap11<T>(payload, ct)` | 1.1 | `Result<T>` | Posts to `BaseAddress` only. A `<Fault>` or unparseable 200 → `NotFound("invalid_response")` (404). 504 → `NotFound("gateway_timeout")` (404). Other statuses log the body → `Internal()` |
| `PostSoap11<T>` / `PostSoap12<T>(payload, ct, url)` | 1.1 / 1.2 | `T`, **throws** `HttpRequestException` | Only where the caller handles the exception. There is no `Result` variant for 1.2 — wrap `PostSoap12` in `try`/`catch`, or use the per-request template with `TryValidateSoap12Response<T>()` |

Take the version from `wsdl:binding` — `http://schemas.xmlsoap.org/soap/envelope/` is 1.1, `http://www.w3.org/2003/05/soap-envelope` is 1.2 — and wrap with the matching `WrapInSoap11Envelope()` / `WrapInSoap12Envelope()`. Mixing them produces a fault the upstream will not explain.

**No `soapAction` on the binding** — call the base method, URL as the argument:

```csharp
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;
using Internal.Domain.Shared.Result;
using Internal.Helpers.SoapHelpers;
using <T>.Models.<SYSTEM>;

namespace <T>.Endpoints;

public class <ClientClassName>(HttpClient client) : SoapEndpoint(client)
{
    public Task<Result<ThingResponse>> GetThing(ThingRequest request, string url,
        CancellationToken cancellationToken)
    {
        var envelope = XmlExtensions.Serialize(request).Root.WrapInSoap11Envelope();
        return PostSoap11Result<ThingResponse>(envelope.ToString(), cancellationToken, url);
    }
}
```

**A `soapAction` on the binding** must be sent, and the base methods can't carry it. Put it on a per-request `HttpRequestMessage` — never `Client.SetHeader(...)`: that mutates `DefaultRequestHeaders` on a client the module captures for the process lifetime (C5), so concurrent calls race. `TryValidateSoap11Response<T>()` (`Internal.Extensions.Extensions.Soap`) throws `HttpRequestException` on a `<Fault>` after logging its code and reason — on any status, so HTTP-500 faults get logged too:

```csharp
using System;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;
using Internal.Domain.Shared.Result;
using Internal.Extensions.Extensions.Soap;
using Internal.Helpers.SoapHelpers;
using Serilog;
using <T>.Models.<SYSTEM>;

namespace <T>.Endpoints;

public class <ClientClassName>(HttpClient client) : SoapEndpoint(client)
{
    public async Task<Result<ThingResponse>> GetThing(ThingRequest request, string url,
        CancellationToken cancellationToken)
    {
        var envelope = XmlExtensions.Serialize(request).Root.WrapInSoap11Envelope();
        using var message = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(envelope.ToString(), Encoding.UTF8, SoapConstants.Soap11MediaType)
        };
        message.Headers.TryAddWithoutValidation(SoapConstants.ActionHeader, "\"<soapAction>\"");

        try
        {
            using var response = await Client.SendAsync(message, cancellationToken);
            if (response.StatusCode == HttpStatusCode.NotFound)
            {
                return Result.Failure<ThingResponse>(Error.NotFound("thing_not_found", "Thing not found"));
            }

            var payload = await response.TryValidateSoap11Response<ThingResponse>();
            if (!response.IsSuccessStatusCode || payload is null)
            {
                Log.Error("Unexpected response from <SYSTEM>: {StatusCode}", response.StatusCode);
                return Result.Failure<ThingResponse>(Error.Internal());
            }

            return Result.Success(payload);
        }
        catch (Exception e)
        {
            Log.Error(e, "<SYSTEM> GetThing failed");
            return Result.Failure<ThingResponse>(Error.Internal());
        }
    }
}
```

SOAP 1.2 has no `SOAPAction` header: use `WrapInSoap12Envelope()`, `SoapConstants.Soap12MediaType`, add the action to the content type — `message.Content.Headers.ContentType.Parameters.Add(new NameValueHeaderValue("action", "\"<soapAction>\""));` (`using System.Net.Http.Headers;`) — and validate with `TryValidateSoap12Response<T>()`. PSPF shows the action format (`urn:microsoft-dynamics-schemas/codeunit/PartnerAPI:<actionName>`), not the mechanism.

**Per-operation URLs** — `Models/<SYSTEM>/<ClientClassName>SoapEndpointOptions.cs`, one property per operation, each with its token (step 3):

```csharp
using Internal.Clients;

namespace <T>.Models.<SYSTEM>;

public class <ClientClassName>SoapEndpointOptions : SoapEndpointOptions
{
    public string GetThingUrl { get; set; }
}
```

Bind it in `Program.cs` and inject `IOptions<<ClientClassName>SoapEndpointOptions>` into the module, which passes `options.Value.GetThingUrl` to the client (step 6):

```csharp
builder.Services.Configure<<ClientClassName>SoapEndpointOptions>(
    builder.Configuration.GetSection("SoapEndpoints:<ClientClassName>"));
```

Don't copy IFMIS's `SetOptions`. An existing client that already has it keeps it, bound in the module constructor `(<ClientClassName> client, IConfiguration configuration)` — safe only because the captured instance is set once, at `MapCarter()`.

Rules:

- Message types are plain classes with `System.Xml.Serialization` attributes, generated from the WSDL's schema and placed under `Models/<SYSTEM>/`, namespace `<T>.Models.<SYSTEM>`. Keep the element and namespace names exactly as the schema declares them — `XmlExtensions.Deserialize<T>` matches on them
- `XmlSerializer` drops null elements. Emit every `minOccurs="1"` element: coerce null strings to `string.Empty` in the mapper, or `[XmlElement(IsNullable = true)]` when the XSD allows `xsi:nil`. Compare one serialized envelope against a sample from the source before calling it done
- Don't re-parse the envelope by hand — the base methods and `TryValidateSoap11Response<T>()` already detect `<Fault>`
- One method per WSDL operation, named for the operation

Register in `Program.cs`, alongside `RegisterEndpoints` if the tenant also consumes REST:

```csharp
builder.Services.RegisterSoapEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration);
```

with `using Internal.Extensions.Extensions.Soap;` (and `using <T>.Models.<SYSTEM>;` for the options binding).

## 5. Models and mappers

`Models/<SYSTEM>/` holds upstream shapes and the tenant's public response DTOs. Keep them separate: an upstream field rename must not become a breaking change on the tenant's own API.

`Mapper/<PascalTenant>MappingExtensions.cs` — PascalCase tenant, not the folder casing: `TT` → `TtMappingExtensions`, like `MohMappingExtensions` and `GovZmMappingExtensions`. It holds `static` extension methods (`ToXxxResponse()`) that translate upstream → public, following `src/Core/Shared/Mapper/MappingConventions.md` (naming, null safety) and `src/Tenants/MOH/Mapper/`:

```csharp
using <T>.Models.<SYSTEM>;

namespace <T>.Mapper;

public static class <PascalTenant>MappingExtensions
{
    public static ThingResponse ToThingResponse(this ThingDto src)
    {
        if (src is null) return null;

        return new ThingResponse
        {
            Id = src.Id,
            Name = src.Name,
        };
    }
}
```

Assign **every** settable target property explicitly — the AutoMapper removal silently dropped one that was left out. Before finishing, diff the target type's property list against each initializer.

Upstream DTOs follow the STJ traps in step 4. Skip both folders when the response passes through unchanged and the shape already lives in `Core/Shared/Models`.

## 6. Expose the tenant's own endpoints

One `ICarterModule` per upstream system or business domain in `Modules/<Name>Module.cs`, where `<Name>` is that system or domain — `NirModule`, `NbrModule`, `DophmsModule` — not the individual resource it serves (`NirPersonsModule` is wrong; persons are one resource inside NIR). Group routes with `MapGroup` + `WithTags`; declare every response shape so Swagger and the generated API spec are accurate.

```csharp
using System.Threading;
using Carter;
using Internal.Domain.Shared.Result;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using <T>.Endpoints;
using <T>.Mapper;
using <T>.Models.<SYSTEM>;

namespace <T>.Modules;

public class <Name>Module(<ClientClassName> client) : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/<name>").WithTags("<TAG>");

        group.MapGet("/things/{id}", async (string id, CancellationToken cancellationToken) =>
            {
                var result = await client.GetThing(id, cancellationToken);
                return result.IsSuccess
                    ? Results.Ok(result.Value.ToThingResponse())
                    : CustomResults.Problem(result);
            })
            .Produces<ThingResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status404NotFound)
            .ProducesProblem(StatusCodes.Status500InternalServerError)
            .WithSummary("Get a thing by id")
            .WithDescription("Returns the thing registered under the given id in <SYSTEM>.");
    }
}
```

A SOAP module with per-operation URLs adds `IOptions<<ClientClassName>SoapEndpointOptions> options` to the constructor (`using Microsoft.Extensions.Options;`) and passes `options.Value.<Op>Url` to each client call.

Client injection (C5): the module is built once at `MapCarter()`, so a constructor-injected client lives for the process (build warning `CARTER1` — expected). Constructor injection is the convention for stateless clients, which every template above is. A client whose per-call state is mutated (`SetHeader`, `SetOptions`, `DefaultRequestHeaders`) is injected as a handler parameter instead: `async (string id, <ClientClassName> client, CancellationToken cancellationToken) => …`.

Rules:

- `CustomResults.Problem(result)` is the only failure path — it turns `Error` into RFC 7807 `ProblemDetails` with the status from C2
- Declare responses in the APIS style: `.Produces<T>(StatusCodes.Status200OK)` (or `201`/`202`), one `.ProducesProblem(...)` per status the route's `Error`s can produce (C2), `.WithSummary`, `.WithDescription`
- `POST` that creates returns `Results.Created` with the created id
- Every handler takes `CancellationToken` and passes it down
- The `MapGroup` prefix is lowercase, leading-slash, and matches the module name: `NirModule` -> `MapGroup("/nir")`, so every route in the module reads `/nir/persons/{nrc}`. Resource segments go after the prefix, never in it
- When the module name equals the tenant's own gateway route (the IFMIS module in the `ifmis` tenant), use `MapGroup("")` — the gateway already adds `/t/<route>`, so `MapGroup("/ifmis")` doubles it to `/t/ifmis/ifmis/...`
- XML doc comments on public request/response types feed the generated API specification — write them

For a controllers-style tenant, put the equivalent in `Controllers/<Resource>Controller.cs` following `src/Tenants/MOA/Controllers/`.

The exposed surface is REST and JSON regardless of what the tenant consumes. A SOAP upstream stops at the client: never return an XML message type from a route, and never surface a SOAP `Fault` verbatim — `CustomResults.Problem` has already turned it into `ProblemDetails`.

## 7. Verify

```bash
dotnet build src/Tenants/<TenantName>/<TenantName>.csproj -v q --nologo
```

Must report `0 Error(s)` (`CARTER1` and `NU1903` warnings come from Core and existing modules). Then check, without running the app:

- Every `RestEndpoint` class has a matching `Endpoints:<Name>` section, and every `SoapEndpoint` class a `SoapEndpoints:<Name>` section, in **both** appsettings files — a missing one is a startup crash at `MapCarter()`
- Every `BaseUrl` is a valid absolute URL in `appsettings.Development.json`, and one that carries a path ends with `/`
- REST `AuthenticationScheme` is exactly `Basic`, `JWT`, `Custom`, `RA` or `None`; every SOAP section has `AuthenticationScheme` (`None` when there's no auth)
- `Timeout`, when set, is `hh:mm:ss`
- Every SOAP per-operation URL has an options property and a `__SoapEndpoints.<ClientClassName>.<Op>Url__` token in both files; no URL is hard-coded in a client or module
- Every token follows C4 and `Username` casing follows C3; every new token is listed in the report
- REST clients call only `*Async` base methods, and deserialize with the tenant's `jsonOptions.Value`
- No SOAP client calls `Client.SetHeader`; `SOAPAction` is on a per-request message. Any client with mutable state is injected as a handler parameter
- `Program.cs` calls the registrar for each kind of client the tenant actually has — `RegisterEndpoints`, `RegisterSoapEndpoints`, or both — and binds each `<ClientClassName>SoapEndpointOptions`
- Every SOAP client's constructor takes `HttpClient` alone
- Each SOAP call wraps and validates the same version the WSDL binding declares (11 with 11, 12 with 12)
- Every mapper initializer assigns every settable target property
- No real credential appears in either file (C7)
- Every exposed route declares its success type and one `ProducesProblem` per reachable failure status
- No upstream DTO — JSON or XML — is returned directly where a public DTO was defined

`/tenant-audit <TenantName>` runs the configuration and secrets checks for you.

## 8. Make the surface spec-ready

Skipped with `--no-spec-ready`, and then the report names every item below that is still unmet.

The delivery documents (`/tenant-deliverables <TenantName>`) are generated from the tenant's own Swashbuckle document, so they are only as good as the metadata already in the code. It is far cheaper to add that metadata now, while the routes and DTOs are being written, than as a separate pass later.

A tenant scaffolded by `tenant-init` 0.4+ already has the project-level half: `GenerateDocumentationFile`, `Swagger/OpenApiDocumentation.cs`, and `AddSwaggerGen` with `OpenApiInfo`, the Basic security scheme and `IncludeXmlComments`. Check it is there, and add whatever is missing on an older tenant. `src/Tenants/APIS` is the reference for each item below — its Swagger metadata, not its folder layout.

**Project** — `src/Tenants/<TenantName>/<TenantName>.csproj`:

```xml
<GenerateDocumentationFile>true</GenerateDocumentationFile>
<NoWarn>$(NoWarn);CS1591</NoWarn>
```

**Swagger folder** — put the narrative content and any custom `IOperationFilter` / `ISchemaFilter` in `src/Tenants/<TenantName>/Swagger/`, namespace `<TenantName>.Swagger`. Not loose at the project root: these are OpenAPI-generation concerns, not application logic. See `src/Tenants/APIS/Swagger/OpenApiDocumentation.cs` and `ProblemResponseOperationFilter.cs`, and `src/Core/Shared/Swagger/PaginatedResultSchemaFilter.cs`.

**`Program.cs`** — `AddSwaggerGen` with a populated `OpenApiInfo` and `IncludeXmlComments`:

- `Title` must be `"{full descriptive name} ({TENANT})"` — e.g. `"Advance Passenger Information System (APIS)"`. The DOCX cover page renders the tenant code and role separately, so `Title` carries the full name only. When the scaffold left the bare code because the name was `pending`, write the name chosen in the proposal call now.
- `Description` is the **only** source of narrative prose in the generated DOCX. Shape it as the repo's `api-spec-sync` expects: one intro paragraph (the Executive Summary) plus a `## Glossary` table — nothing else. Extend the scaffolded sentence with what this integration adds: the system it reaches and the datasets its routes expose ("Pesticide registrations and ePhyto validation from the PQPS Plant Health system"). State only what a route actually provides. Extra `##` sections are only for protocol-level complexity, as APIS does for PAXLST.

**Routes** — on every route generated in step 6, the APIS set:

- `.WithTags("...")` — required. The Postman step folders requests by tag; untagged operations collapse into one undifferentiated list
- `.WithSummary(...)` and `.WithDescription(...)` — these become the endpoint table entries
- `.Produces<T>(StatusCodes.Status200OK)` and `.ProducesProblem(StatusCodes.Status4xx/500…)` — already required by step 6; they populate the response tables
- Optional: `.WithMetadata(new ProblemResponseDescriptions("…400 prose…", "…500 prose…"))` to replace the bare reason phrases. Copy `ProblemResponseOperationFilter.cs` (record + filter) from APIS into `<TenantName>.Swagger`, register `options.OperationFilter<ProblemResponseOperationFilter>();` in `AddSwaggerGen`, and add a record member for any other status (404) the tenant describes — APIS's record covers 400 and 500 only

**DTOs** — `///` XML doc comments on every public property of every request and response type the tenant declares. They become the schema tables verbatim.

**Never use `<see cref="..."/>` in those comments.** Swashbuckle does not resolve cref targets; it emits the raw fully-qualified type name as literal text ("See APIS.Paxlst.MessageKind."). Write plain prose.

**Gateway route** — widen `match.methods` in `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` to exactly the verbs the tenant now exposes. `tenant-init` left it at `GET`.

The documents themselves are step 6 of `tenant-pipeline` (`/tenant-deliverables <TenantName>`). Don't generate them here. The ZamConnect repository also has a repo-local `/api-spec-sync` for a quick developer-side regeneration; it reads the same metadata. Its `api-docs-auditor` agent watches only `Modules/`, so a controllers-style tenant's changes aren't flagged — say so in the report.

## 9. Another integration?

Tenants often reach more than one upstream (`MCTI` → ZABS + ZMA, `MLSS` → four systems). Unless `--auto` is set, ask with header `Next`:

- `Done — continue (Recommended)`
- `Add another integration source` — back to step 1 for the next upstream. Keep what's been built, and skip anything already answered for this tenant, such as the full name

Each pass gets its own client, config section, models and module, and the report covers all passes.

## Report

State the upstream system(s) and their base URL, one line per file added or changed, and a table of the exposed routes (method, `/t/<route>/…` path, purpose). Name the spec-readiness items from step 8 that are still unmet, if any. Then list what remains outside this skill: every new `__Token__` (by name, never a value), which needs a variable in `GSB.<TENANT>.<ENV>` and in `projects-variables` (C4); the gateway scope/cluster/route registration (C8); and the ADO pipeline definition.

Close with the equivalent command for each pass (R7), and these answers for the pipeline state: `sources`, `system`, `auth`, `role`, and `fullName` if it was settled here. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when the build in step 7 fails.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder — in `appsettings.Development.json` too. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Many tracked `appsettings.Development.json` files and `src/Tenants/Certificates/*.p12` do (C7): never carry them forward, never use another tenant's Development file as the template for credential values, and report what you noticed as a finding, not a value to reuse. Rotation is a separate ticket.
