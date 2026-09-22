---
name: zc-tenant-integration
description: Build the integration surface of an existing ZamConnect tenant — upstream REST or SOAP client(s) under Endpoints/, request/response models, mappers, and the Carter modules or controllers the tenant exposes. Takes a tenant name plus integration sources (Postman collection, Swagger/OpenAPI spec, REST base URL, SOAP WSDL, or prose API documentation) and an optional list of endpoints to expose; the source artefact decides whether the client derives from RestEndpoint or SoapEndpoint. Use when the user says "integrate <Tenant> with <System>", "add <API> to <Tenant>", "consume this WSDL", "expose these endpoints on <Tenant>", or types /zc-tenant-integration.
argument-hint: "<TenantName> [--source <url|path|wsdl>...] [--expose <METHOD /route>...] [--protocol rest|soap]"
disable-model-invocation: false
---

# ZamConnect Tenant Integration

Implement the business surface of a tenant that already exists (scaffold it first with `zc-create-tenant`). This skill covers the two halves of an integration:

- **Consume** — the upstream API the tenant talks to, wrapped in a `RestEndpoint` or `SoapEndpoint` client
- **Expose** — the routes the tenant publishes to its own consumers

The tenant always exposes REST. What it consumes is whatever the upstream speaks, and that is decided by the integration sources, not by preference — see step 1a.

## 1. Collect inputs

Do not start writing code until these are settled. Ask for anything missing, in one batch.

| Input | What it decides |
|---|---|
| **Tenant name** | Target folder `src/Tenants/<TenantName>/`. Must already exist — if not, run `zc-create-tenant` first |
| **Integration sources** | One or more of: Postman collection (`.json`), Swagger/OpenAPI spec (JSON or YAML, URL or file), a bare REST base URL, a SOAP WSDL (`?wsdl` URL or `.wsdl` file), or integration/API documentation (`.docx`, `.pdf`, `.md`, Confluence/SharePoint page) |
| **Upstream protocol** | REST or SOAP — **derived from the sources, not asked**. Decides the client base class, the configuration section, and the registration call. See step 1a |
| **Upstream auth** | REST: `Basic`, `JWT`, `Custom` (header name + value), `RA`, or `ClientCertificate`. SOAP: `Basic` or `ClientCertificate` only |
| **Endpoints to expose** | Method + route + purpose for each route the tenant publishes. If the user does not list them, derive a proposal from the sources and confirm before generating |

Resolve sources in this order:

- Local file → read it directly
- `.docx` / `.pdf` / `.xlsx` → `convert-documents-to-markdown` skill first
- URL → fetch it; for a Swagger UI URL fetch the underlying `/swagger/v1/swagger.json`, for a SOAP service URL try `?wsdl` / `?singleWsdl`
- Postman collection → parse `item[]` recursively; each leaf `request` gives method, URL, headers, and an example body. A collection can describe a SOAP service too — see step 1a
- WSDL → read `wsdl:portType`/`wsdl:operation` for the operation list, `wsdl:binding` for the SOAP version and `soapAction` values, `wsdl:service`/`soap:address` for the endpoint URL, and the inline or imported `xsd:schema` for the message types

Record, for every upstream operation you intend to call: its name, the request and response message shapes, and the failure signals that carry meaning — non-200 codes for REST, `Fault` codes and reasons for SOAP.

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

If the sources are genuinely silent on protocol, ask — do not assume REST. Reaching a SOAP service with a `RestEndpoint` fails at the first call with an unparseable response, not at build time. `--protocol rest|soap` overrides the classification when the user already knows.

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

Scheme-specific fields: `JWT` and `Custom` use `AuthHeaderValue` (and `AuthHeaderName` for `Custom`); `RA` uses the registration-authority handler. `Timeout` and `DangerousAcceptAnyServerCertificate` are available when the upstream needs them — the latter only for a test environment with a self-signed certificate, never for production.

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

`/zc-tenant-audit <TenantName>` runs the configuration and secrets checks for you.

## 8. Make the surface spec-ready

Every integration ends here. `/api-spec-sync <TenantName>` generates the OpenAPI JSON, the DOCX API Specification, and the Postman collection from the tenant's own Swashbuckle document — but it is only one command, and it is only as good as the metadata already in the code. Retrofitting a tenant to meet its prerequisites is the real work, and it is far cheaper to do now, while the routes and DTOs are being written, than as a separate pass later. Do it as part of the integration, not after it.

Only `src/Tenants/APIS` currently satisfies all of this — read it as the reference for each item below.

**Project** — `src/Tenants/<TenantName>/<TenantName>.csproj`:

```xml
<GenerateDocumentationFile>true</GenerateDocumentationFile>
<NoWarn>$(NoWarn);CS1591</NoWarn>
```

**Swagger folder** — put the narrative content and any custom `IOperationFilter` / `ISchemaFilter` in `src/Tenants/<TenantName>/Swagger/`, namespace `<TenantName>.Swagger`. Not loose at the project root: these are OpenAPI-generation concerns, not application logic. See `src/Tenants/APIS/Swagger/OpenApiDocumentation.cs` and `ProblemResponseOperationFilter.cs`, and `src/Core/Shared/Swagger/PaginatedResultSchemaFilter.cs`.

**`Program.cs`** — `AddSwaggerGen` with a populated `OpenApiInfo` and `IncludeXmlComments`:

- `Title` must be `"{full descriptive name} ({TENANT})"` — e.g. `"Advance Passenger Information System (APIS)"`. The DOCX cover page renders the tenant code and role separately, so `Title` carries the full name only. Older `"{TENANT} - {name}"` and `"{TENANT} ({role})"` forms still render, but risk the role appearing twice — use this convention for anything new.
- `Description` is the **only** source of narrative prose in the generated DOCX — submission model, message-format primers, worked examples. There is no markdown file to maintain; it lives in the C#.

**Routes** — on every route generated in step 6:

- `.WithTags("...")` — required. The Postman step folders requests by tag; untagged operations collapse into one undifferentiated list
- `.WithSummary(...)` and `.WithDescription(...)` — these become the endpoint table entries
- `.Produces<T>(...)` / `.ProducesProblem(...)` — already required by step 6, and they populate the response tables

**DTOs** — `///` XML doc comments on every public property of every request and response type the tenant declares. They become the schema tables verbatim.

**Never use `<see cref="..."/>` in those comments.** Swashbuckle does not resolve cref targets; it emits the raw fully-qualified type name as literal text ("See APIS.Paxlst.MessageKind."). Write plain prose.

Then run `/api-spec-sync <TenantName>`. If the tenant cannot be brought up to this bar within the current request, say exactly which items are missing in the report rather than offering the sync as if it were ready.

## Report

State the upstream system and its base URL, one line per file added or changed, and a table of the exposed routes (method, path, purpose). Name the generated deliverables from step 8, or the prerequisites still unmet. Then list what remains outside this skill: the `GSB.<TENANT>.<ENV>` variable-group values behind each `__Credentials.*__` token, the gateway scope/cluster/route registration, and the ADO pipeline definition.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
