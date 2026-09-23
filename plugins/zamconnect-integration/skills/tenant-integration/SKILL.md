---
name: tenant-integration
description: Build the integration surface of an existing ZamConnect tenant — upstream REST or SOAP client(s) under Endpoints/, request/response models, mappers, and the Carter modules or controllers the tenant exposes. Takes a tenant name plus integration sources (Postman collection, Swagger/OpenAPI spec, REST base URL, SOAP WSDL, or prose API documentation) and an optional list of endpoints to expose; the source artefact decides whether the client derives from RestEndpoint or SoapEndpoint. Use when the user says "integrate <Tenant> with <System>", "add <API> to <Tenant>", "consume this WSDL", "expose these endpoints on <Tenant>", or types /tenant-integration.
argument-hint: "<TenantName> [--source <url|path>...] [--expose <METHOD /route>...] [--protocol rest|soap] [--auth Basic|JWT|Custom|RA|ClientCertificate|None] [--auth-header <name>] [--system <Name>] [--role provide|consume] [--dto public|passthrough] [--modules system|domain] [--timeout <seconds>] [--no-spec-ready] [--spec-only] [--auto] [--dry-run]"
disable-model-invocation: false
---

# ZamConnect Tenant Integration

Implement the business surface of a tenant that already exists (scaffold it first with `tenant-init`). This skill covers the two halves of an integration:

- **Consume** — the upstream API the tenant talks to, wrapped in a `RestEndpoint` or `SoapEndpoint` client
- **Expose** — the routes the tenant publishes to its own consumers

The tenant always exposes REST. What it consumes is whatever the upstream speaks, and that is decided by the integration sources, not by preference — see step 1a.

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`, R12 above all: **every option is a complete answer**. This skill never offers a source *type* as an option, never asks for anything the source already says (protocol, SOAP version, operations, auth block), and never writes "pick Other and…" in an option.

## Arguments

| Flag | Meaning | When absent |
|---|---|---|
| `<TenantName>` | Existing tenant under `src/Tenants/` | Required. If the folder is missing, run `tenant-init` first |
| `--source <url\|path>` | Integration source; repeatable | Asked (step 1, source question) |
| `--expose <METHOD /route>` | A route the tenant should expose; repeatable | Every upstream operation, confirmed in the review |
| `--protocol rest\|soap` | Overrides the classification in step 1a | Detected from the source |
| `--auth <scheme>` / `--auth-header <name>` | Upstream auth. `--auth-header` goes with `Custom` | Detected from the source. Asked only when it can't be |
| `--system <Name>` | Upstream system name: the client class, `Models/<Name>/`, the config token `<SYSTEM>` | Derived from the source title. Asked only under `Customize…` or when there's nothing to derive it from |
| `--role provide\|consume` | Whether the exposed routes serve this tenant's own institution (`provide`) or data reached back through the gateway (`consume`). `tenant-deliverables` uses it to split the Consume/Provide documents | `provide` |
| `--dto public\|passthrough` | Public DTOs plus a mapper, or return the upstream shape as-is | `public` |
| `--modules system\|domain` | One Carter module per upstream system, or per business domain | `system` |
| `--timeout <seconds>` | Upstream `Timeout` (REST only) | The `RestEndpoint` default |
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
- WSDL → read `wsdl:portType`/`wsdl:operation` for the operation list, `wsdl:binding` for the SOAP version and `soapAction` values, `wsdl:service`/`soap:address` for the endpoint URL, and the inline or imported `xsd:schema` for the message types

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

### Proposal questions

**With `Proceed`, or no gate:** ask only what detection left open, in one call of at most 4 questions. When everything was detected, skip straight to the review.

**With `Customize…`:** ask all four questions of the proposal call, then the customize call, whether detected or not. The detected value is always the first option, marked `(Recommended)`.

Proposal call:

| Header | Question | Options (each a complete answer) |
|---|---|---|
| `Auth` | How does `<T>` authenticate to `<System>`? | The detected scheme first, naming where it came from: `Basic (collection auth)`, `Custom header X-Api-Key (securitySchemes)`. Then the other supported schemes, to 4 in total. REST: `Basic`, `JWT bearer`, `Client certificate`, `Custom header`; the question text says "`RA` or `None`: type it in Other". SOAP: `Basic`, `Client certificate`, `None` |
| `System` | Upstream system name for the client class and config | The derived name `(Recommended)`, e.g. `Pqps — from wsdl:service PqpsService`; the tenant code; the source's short title, if different |
| `Role` | Where does the data behind these routes come from? | `Provide — <T>'s own institution (Recommended)` · `Consume — another system reached through the gateway` |
| `Name` | Only when `fullName` is `pending`: full descriptive name of `<T>` for the spec title | Titles found in the sources, the most specific first · `Use <T> for now` |

When `Custom header` is picked and no header name was detected, follow up with `Header name?`, offering the header names found on the source's requests.

Customize call (`Customize…` only):

| Header | Question | Options |
|---|---|---|
| `DTOs` | Response shaping | `Public DTOs + mapper (Recommended)` · `Pass-through — shared model already exists` |
| `Modules` | Module grouping | `One module per upstream system (Recommended)` · `One module per business domain` |
| `Timeout` | Upstream timeout (REST only) | `Default (Recommended)` · `60 seconds` · `120 seconds` |
| `Spec` | Make the surface spec-ready now (step 8)? | `Now (Recommended)` · `Later` — adds `--no-spec-ready` |

### Endpoint selection

Asked with `Customize…`, or when `--expose` is absent and there are more than 3 operation groups. `multiSelect`. Options are the groups found (`Pesticides — 3 operations`), or single operations (`GET /pesticides/{id} — pesticide by id`) when there are 3 or fewer, plus `All operations (Recommended)`. More than 3 groups go over up to 4 questions (R9). With `Proceed` and 3 or fewer groups, everything is exposed and the review shows it.

### Review before writing

One R6 call. The question text is the plan, the options `Apply (Recommended)` · `Adjust` · `Cancel`:

```
Integrate TT with Pqps (SOAP 1.1, Basic):
  Endpoints/Pqps.cs                     SoapEndpoint, 5 operations
  appsettings.json + .Development.json  SoapEndpoints:Pqps
  Models/Pqps/                          5 request/response pairs
  Mapper/TTMappingExtensions.cs
  Modules/PqpsModule.cs                 MapGroup("/pqps"), tag PQPS
  Program.cs                            + RegisterSoapEndpoints
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
| Marker interface scanned | `IRestEndpoint` | `ISoapEndpoint` |
| Config section | `Endpoints:<ClassName>` | `SoapEndpoints:<ClassName>` |
| Registration in `Program.cs` | `RegisterEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration)` | `RegisterSoapEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration)` |
| Auth schemes supported | `Basic`, `JWT`, `Custom`, `RA`, `ClientCertificate` | `Basic`, `ClientCertificate` (anything else falls through to no auth) |
| Payloads | `System.Text.Json` | `XmlExtensions.Serialize` / `Deserialize` |
| Client section | Step 4 | Step 4b |

A tenant may do both — `RegisterEndpoints` and `RegisterSoapEndpoints` are independent and can be called side by side, each scanning the same assembly for its own marker interface. IFMIS is the reference for a tenant that consumes SOAP while exposing REST.

If the sources are genuinely silent on protocol, ask with header `Protocol`: `REST — JSON over HTTP` / `SOAP — XML envelopes`, with the reason detection failed in the question text. Do not assume REST. Reaching a SOAP service with a `RestEndpoint` fails at the first call with an unparseable response, not at build time. `--protocol rest|soap` overrides the classification when the user already knows.

## 2. Read the tenant and its neighbours

```bash
find src/Tenants/<TenantName> -type f -not -path "*/bin/*" -not -path "*/obj/*"
```

Reference implementations:

- `src/Tenants/CEEC` — REST, client `Endpoints/ZamConnect.cs`, one Carter module per resource
- `src/Tenants/MOH` — `EServicesShared` for shared NIR/NBR calls, `Mapper/` for upstream→public DTO shaping
- `src/Tenants/MOA` — controllers variant
- `src/Tenants/IFMIS` — SOAP, per-operation URLs through a `SoapEndpointOptions` subclass
- `src/Tenants/PSPF` — SOAP, one generic `Send<TIn, TOut>` with a per-call `SOAPAction` header
- `src/Tenants/DNRPC` — SOAP, the minimal shape (`Endpoints/Imago.cs`)

Before defining a new model, check `src/Core/Shared/Models/` — NIR, NBR, DOC, SRS shapes already exist and should be reused rather than redeclared.

## 3. Configure the upstream endpoint

Both registrars work the same way: scan the assembly for the marker interface, then bind the configuration section named after the class. **The section key must equal the class name**; a client with no matching section logs `Endpoint {Name} is not configured` (`SOAP Endpoint {Name} is not configured` for SOAP) and gets no `HttpClient` — a startup warning, never a build failure. The lookup is `IConfiguration`, so the key match is case-insensitive.

### REST

Add to both `appsettings.json` and `appsettings.Development.json`:

```json
"Endpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "Basic",
        "BaseUrl": "__Endpoints.<SYSTEM>.BaseUrl__",
        "Username": "__Credentials.<TenantName>Tenant.Username__",
        "Password": "__Credentials.<TenantName>Tenant.Password__"
    }
}
```

Scheme-specific fields: `JWT` and `Custom` use `AuthHeaderValue` (and `AuthHeaderName` for `Custom`); `RA` uses the registration-authority handler. `--auth-header` / the detected header name goes in `AuthHeaderName` as a literal. `AuthHeaderValue` is always a `__Credentials.<TenantName>Tenant.<SYSTEM>ApiKey__`-style token, never a value found in the source. A `--timeout` answer from the customize call goes in `Timeout`. `Timeout` and `DangerousAcceptAnyServerCertificate` are available when the upstream needs them — the latter only for a test environment with a self-signed certificate, never for production.

### SOAP

A different top-level section — `SoapEndpoints`, not `Endpoints`:

```json
"SoapEndpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "Basic",
        "BaseUrl": "__SoapEndpoints.<SYSTEM>.BaseUrl__",
        "Username": "__SoapEndpoints.<SYSTEM>.Username__",
        "Password": "__SoapEndpoints.<SYSTEM>.Password__"
    }
}
```

`SoapEndpointOptions` carries only `BaseUrl`, `AuthenticationScheme`, `UserName`, `Password`, `PublicKey` and `PrivateKey`. `ClientCertificate` uses `PublicKey` + `PrivateKey` as base64 DER; `Basic` uses `Username`/`Password`. Any other scheme value is not rejected — it silently configures the client with no authentication at all.

Two consequences of that narrow options type:

- **There is no `Timeout` and no `DangerousAcceptAnyServerCertificate` for SOAP.** `src/Tenants/PSPF/appsettings.json` sets the latter and it does nothing; do not copy it forward
- **Per-operation URLs need a subclass.** When the service exposes each operation at its own path, declare `<TenantName>SoapEndpointOptions : SoapEndpointOptions` under `Models/`, add the URL properties there, and bind it in the module — see step 4b

Secrets are always `__...__` placeholders replaced at deploy time. Never commit a real credential. In `appsettings.Development.json` the `BaseUrl` may be the real test URL.

## 4. Write the REST client — `Endpoints/<ClientClassName>.cs`

Skip to step 4b for a SOAP upstream.

Derive from `Internal.Clients.RestEndpoint`; take `HttpClient` and, when deserializing manually, `IOptions<JsonSerializerOptions>`. Return `Result<T>` / `Result` from `Internal.Domain.Shared.Result` — never throw across the client boundary.

```csharp
public class <ClientClassName>(HttpClient client, IOptions<JsonSerializerOptions> jsonOptions)
    : RestEndpoint(client)
{
    public async Task<Result<TModel>> GetThing(string id, CancellationToken cancellationToken = default)
    {
        try
        {
            var response = await Get($"/path/{WebUtility.UrlEncode(id)}", cancellationToken);

            switch (response.StatusCode)
            {
                case HttpStatusCode.OK:
                    var stream = await response.Content.ReadAsStreamAsync(cancellationToken);
                    var model = (await JsonDocument.ParseAsync(stream, cancellationToken: cancellationToken))
                        .Deserialize<TModel>(jsonOptions.Value);
                    return model is null
                        ? Result.Failure<TModel>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"))
                        : Result.Success(model);

                case HttpStatusCode.NotFound:
                    return Result.Failure<TModel>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"));

                default:
                    Log.Error("Unexpected response from <SYSTEM> API: {StatusCode}, {Content}",
                        response.StatusCode, await response.Content.ReadAsStringAsync(cancellationToken));
                    return Result.Failure<TModel>(Error.Internal());
            }
        }
        catch (Exception e)
        {
            Log.Error(e, e.Message);
            return Result.Failure<TModel>(Error.Internal());
        }
    }
}
```

Rules:

- URL-encode every interpolated path and query value (`WebUtility.UrlEncode`)
- Error codes are snake_case and stable — consumers match on them
- `Error.NotFound` for a missing resource, `Error.Problem` for a business-rule violation, `Error.Internal()` for anything unexpected; never leak the upstream body to the caller, log it instead
- One method per upstream operation. Do not build a generic passthrough

## 4b. Write the SOAP client — `Endpoints/<ClientClassName>.cs`

Derive from `Internal.Clients.SoapEndpoint`. **The constructor must take `HttpClient` and nothing else** — `RegisterSoapEndpoints` instantiates the class with `Activator.CreateInstance(type, client)`, so any extra constructor parameter is a runtime failure, not a compile error. That is why per-operation URLs arrive through a setter rather than the constructor.

Pick the base method by what the caller should get back and which SOAP version the binding declares:

| Method | SOAP | Returns | Use when |
|---|---|---|---|
| `PostSoap11Result<T>` | 1.1 | `Result<T>` | Default. Maps 404 → `not_found`, 504 → `gateway_timeout`, anything else → `Error.Internal()` |
| `SendSoap11<T>` | 1.1 | `Result<T>` | Same, but posts to the client's `BaseAddress` with no per-call URL |
| `PostSoap11<T>` / `PostSoap12<T>` | 1.1 / 1.2 | `T`, **throws** `HttpRequestException` | Only where the caller handles the exception. Prefer the `Result` variants |

Take the version from `wsdl:binding` — `http://schemas.xmlsoap.org/soap/envelope/` is 1.1, `http://www.w3.org/2003/05/soap-envelope` is 1.2 — and wrap with the matching `WrapInSoap11Envelope()` / `WrapInSoap12Envelope()`. Mixing them produces a fault the upstream will not explain.

```csharp
public class <ClientClassName>(HttpClient client) : SoapEndpoint(client)
{
    public async Task<Result<ThingResponse>> GetThing(ThingRequest request,
        CancellationToken cancellationToken)
    {
        var envelope = XmlExtensions.Serialize(request).Root.WrapInSoap11Envelope();
        return await PostSoap11Result<ThingResponse>(envelope.ToString(), cancellationToken);
    }
}
```

Rules:

- Message types are plain classes with `System.Xml.Serialization` attributes, generated from the WSDL's schema and placed under `Models/<SYSTEM>/`. Keep the element and namespace names exactly as the schema declares them — `XmlExtensions.Deserialize<T>` matches on them
- A `soapAction` on the binding must be sent. `SoapEndpoint` does not set it; do it per call, as PSPF does: `Client.SetHeader("SOAPAction", "<action>")`
- `PostSoap11Result` already turns a `<Fault>` into a failed `Result`, logging the fault code and reason. Do not re-parse the envelope in the client
- One method per WSDL operation, named for the operation
- Per-operation URLs: declare `<TenantName>SoapEndpointOptions : SoapEndpointOptions` with one property per URL, expose `public void SetOptions(...)` on the client, and bind it where the module is constructed:

  ```csharp
  _client.SetOptions(configuration
      .GetSection($"SoapEndpoints:{nameof(Endpoints.<ClientClassName>)}")
      .Get<<TenantName>SoapEndpointOptions>());
  ```

  Follow `src/Tenants/IFMIS/Modules/Ifmis.cs` and `src/Tenants/IFMIS/Models/Ifmis/IfmisSoapEndpointOptions.cs`.

Register in `Program.cs`, alongside `RegisterEndpoints` if the tenant also consumes REST:

```csharp
builder.Services.RegisterSoapEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration);
```

with `using Internal.Extensions.Extensions.Soap;`.

## 5. Models and mappers

`Models/<SYSTEM>/` holds upstream shapes and the tenant's public response DTOs. Keep them separate: an upstream field rename must not become a breaking change on the tenant's own API.

`Mapper/<TenantName>MappingExtensions.cs` holds `static` extension methods (`ToXxxResponse()`) that translate upstream → public. Follow `src/Tenants/MOH/Mapper/`.

Skip both when the response passes through unchanged and the shape already lives in `Core/Shared/Models`.

## 6. Expose the tenant's own endpoints

One `ICarterModule` per upstream system or business domain in `Modules/<Name>Module.cs`, where `<Name>` is that system or domain — `NirModule`, `NbrModule`, `DophmsModule` — not the individual resource it serves (`NirPersonsModule` is wrong; persons are one resource inside NIR). Inject the client through the constructor; group routes with `MapGroup` + `WithTags`; declare every response shape with `.Produces(...)` so Swagger and the generated API spec are accurate.

```csharp
public class <Name>Module(<ClientClassName> client) : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/<name>").WithTags("<TAG>");

        group.MapGet("/things/{id}", async (string id, CancellationToken cancellationToken) =>
            {
                var result = await client.GetThing(id, cancellationToken);
                return result.IsSuccess ? Results.Ok(result.Value) : CustomResults.Problem(result);
            })
            .Produces(StatusCodes.Status200OK, typeof(TResponse))
            .Produces(StatusCodes.Status404NotFound, typeof(ProblemDetails))
            .Produces(StatusCodes.Status500InternalServerError, typeof(ProblemDetails));
    }
}
```

Rules:

- `CustomResults.Problem(result)` is the only failure path — it turns `Error` into RFC 7807 `ProblemDetails`
- `POST` that creates returns `Results.Created` with the created id
- Every handler takes `CancellationToken` and passes it down
- The `MapGroup` prefix is lowercase, leading-slash, and matches the module name: `NirModule` -> `MapGroup("/nir")`, so every route in the module reads `/nir/persons/{nrc}`. Resource segments go after the prefix, never in it
- XML doc comments on public request/response types feed the generated API specification — write them

For a controllers-style tenant, put the equivalent in `Controllers/<Resource>Controller.cs` following `src/Tenants/MOA/Controllers/`.

The exposed surface is REST and JSON regardless of what the tenant consumes. A SOAP upstream stops at the client: never return an XML message type from a route, and never surface a SOAP `Fault` verbatim — `CustomResults.Problem` has already turned it into `ProblemDetails`.

## 7. Verify

```bash
dotnet build src/Tenants/<TenantName>/<TenantName>.csproj -v q --nologo
```

Must report `0 Error(s)`. Then check, without running the app:

- Every `RestEndpoint` class has a matching `Endpoints:<Name>` section, and every `SoapEndpoint` class a `SoapEndpoints:<Name>` section, in **both** appsettings files
- `Program.cs` calls the registrar for each kind of client the tenant actually has — `RegisterEndpoints`, `RegisterSoapEndpoints`, or both
- Every SOAP client's constructor takes `HttpClient` alone
- Each SOAP call wraps and validates the same version the WSDL binding declares (11 with 11, 12 with 12)
- No real credential appears in either file
- Every exposed route declares its success type and `ProblemDetails` failures
- No upstream DTO — JSON or XML — is returned directly where a public DTO was defined

`/tenant-audit <TenantName>` runs the configuration and secrets checks for you.

## 8. Make the surface spec-ready

Skipped with `--no-spec-ready`, and then the report names every item below that is still unmet.

The delivery documents (`/tenant-deliverables <TenantName>`) are generated from the tenant's own Swashbuckle document, so they are only as good as the metadata already in the code. It is far cheaper to add that metadata now, while the routes and DTOs are being written, than as a separate pass later.

A tenant scaffolded by `tenant-init` 0.3+ already has the project-level half: `GenerateDocumentationFile`, `Swagger/OpenApiDocumentation.cs`, and `AddSwaggerGen` with `OpenApiInfo`, the Basic security scheme and `IncludeXmlComments`. Check it is there, and add whatever is missing on an older tenant. `src/Tenants/APIS` is the reference for each item below.

**Project** — `src/Tenants/<TenantName>/<TenantName>.csproj`:

```xml
<GenerateDocumentationFile>true</GenerateDocumentationFile>
<NoWarn>$(NoWarn);CS1591</NoWarn>
```

**Swagger folder** — put the narrative content and any custom `IOperationFilter` / `ISchemaFilter` in `src/Tenants/<TenantName>/Swagger/`, namespace `<TenantName>.Swagger`. Not loose at the project root: these are OpenAPI-generation concerns, not application logic. See `src/Tenants/APIS/Swagger/OpenApiDocumentation.cs` and `ProblemResponseOperationFilter.cs`, and `src/Core/Shared/Swagger/PaginatedResultSchemaFilter.cs`.

**`Program.cs`** — `AddSwaggerGen` with a populated `OpenApiInfo` and `IncludeXmlComments`:

- `Title` must be `"{full descriptive name} ({TENANT})"` — e.g. `"Advance Passenger Information System (APIS)"`. The DOCX cover page renders the tenant code and role separately, so `Title` carries the full name only. When the scaffold left the bare code because the name was `pending`, write the name chosen in the proposal call now.
- `Description` is the **only** source of narrative prose in the generated DOCX. Extend the scaffolded sentence with what this integration adds: the system it reaches and the datasets its routes expose ("Pesticide registrations and ePhyto validation from the PQPS Plant Health system"). State only what a route actually provides.

**Routes** — on every route generated in step 6:

- `.WithTags("...")` — required. The Postman step folders requests by tag; untagged operations collapse into one undifferentiated list
- `.WithSummary(...)` and `.WithDescription(...)` — these become the endpoint table entries
- `.Produces<T>(...)` / `.ProducesProblem(...)` — already required by step 6, and they populate the response tables

**DTOs** — `///` XML doc comments on every public property of every request and response type the tenant declares. They become the schema tables verbatim.

**Never use `<see cref="..."/>` in those comments.** Swashbuckle does not resolve cref targets; it emits the raw fully-qualified type name as literal text ("See APIS.Paxlst.MessageKind."). Write plain prose.

**Gateway route** — widen `match.methods` in `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` to exactly the verbs the tenant now exposes. `tenant-init` left it at `GET`.

The documents themselves are step 6 of `tenant-pipeline` (`/tenant-deliverables <TenantName>`). Don't generate them here. The ZamConnect repository also has a repo-local `/api-spec-sync` for a quick developer-side regeneration; it reads the same metadata.

## 9. Another integration?

Tenants often reach more than one upstream (`MCTI` → ZABS + ZMA, `MLSS` → four systems). Unless `--auto` is set, ask with header `Next`:

- `Done — continue (Recommended)`
- `Add another integration source` — back to step 1 for the next upstream. Keep what's been built, and skip anything already answered for this tenant, such as the full name

Each pass gets its own client, config section, models and module, and the report covers all passes.

## Report

State the upstream system(s) and their base URL, one line per file added or changed, and a table of the exposed routes (method, `/t/<route>/…` path, purpose). Name the spec-readiness items from step 8 that are still unmet, if any. Then list what remains outside this skill: the `GSB.<TENANT>.<ENV>` variable-group values behind each `__Credentials.*__` token, the gateway scope/cluster/route registration, and the ADO pipeline definition.

Close with the equivalent command for each pass (R7), and these answers for the pipeline state: `sources`, `system`, `auth`, `role`, and `fullName` if it was settled here. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when the build in step 7 fails.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
