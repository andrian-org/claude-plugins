---
name: tenant-tests
description: Scaffold and write the test project for a ZamConnect tenant — `src/Tests/<Tenant>.Tests/` with a `WebApplicationFactory`, a mock HTTP handler standing in for the upstream, and endpoint tests that drive the tenant's real Carter modules or controllers over HTTP. Optionally adds an `[Explicit]` staging fixture that calls the live upstream. Use when the user says "add tests for <Tenant>", "test this integration", "write module tests", "cover <Tenant> endpoints", or types /tenant-tests.
argument-hint: "<TenantName> [--module <Name> ...] [--coverage full|errors|smoke] [--live] [--no-scaffold] [--auto] [--dry-run]"
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(tail *) Bash(wc *) Bash(mkdir *) Bash(dotnet *) AskUserQuestion
disable-model-invocation: false
---

# ZamConnect Tenant Tests

Tenant test projects share one shape: a `WebApplicationFactory<Program>` that swaps the upstream `HttpClient` for a recording mock, and fixtures that exercise the tenant's own routes end to end over HTTP. This skill reproduces that shape and writes the tests.

Never trust a count — re-derive it:

```bash
ls src/Tenants/*/*.csproj | wc -l                      # tenants
ls src/Tests/*/*.Tests.csproj | wc -l                  # test projects (AdminAPI.Tests is not a tenant)
grep -l 'Include="NUnit"' src/Tests/*/*.Tests.csproj   # NUnit; the rest are xUnit
```

Folders under `src/Tests/` without a `*.Tests.csproj` (snapshot projects, untracked leftovers) are not tenant test projects.

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`).

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Shared code/config facts live in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md` (cited as C1–C8).

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Tenant under `src/Tenants/<TenantName>/`. Test project goes to `src/Tests/<TenantName>.Tests/` |
| `--module <Name>` | Cover only these modules/controllers; repeatable. Default: every one the tenant exposes |
| `--live` | Also generate the staging fixture that calls the real upstream (`[Explicit]`, `[Category("Staging")]`) |
| `--coverage full\|errors\|smoke` | Which cases each route gets — see step 6. Default `full` |
| `--no-scaffold` | Project already exists — add fixtures only. Detected: when `src/Tests/<TenantName>.Tests/` exists, this is implied and never asked |
| `--gate <n>/<N>` | Gate mode, set by `tenant-pipeline` |
| `--auto` | No questions: every default |
| `--dry-run` | Stop at the review and write nothing |

## Gate

Only with `--gate <n>/<N>`. One `AskUserQuestion` call. Nothing here is required, so the gate is asked alone:

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/tenant-tests <T>` — scaffold `src/Tests/<T>.Tests` if missing and write endpoint tests for <k> routes. Run it? | `Proceed (Recommended)` — full coverage matrix, every module, no live fixture · `Customize…` — choose coverage, modules, live staging fixture · `Skip` · `Stop` |

`<k>` is the route count from step 1. When the project already exists, the question says "add fixtures to the existing `src/Tests/<T>.Tests`" instead.

`Customize…` asks one call, leaving out any question whose flag was passed:

| Header | Question | Options | → flag |
|---|---|---|---|
| `Coverage` | What should each route be tested for? | `Full matrix (Recommended)` — happy path, upstream 404, upstream 500, forwarded body, route contract, swagger smoke · `Happy path + errors` — no forwarded-body, route-contract or swagger cases · `Smoke only` — happy path per route | `--coverage` |
| `Modules` | Which modules or controllers? (`multiSelect`) | The tenant's modules from step 1, with their route counts, up to 3 · `All <n> modules (Recommended)`. With more than 4, spread them over up to 3 more questions in this call (R9) | `--module` |
| `Live` | Add a staging fixture that calls the real upstream? | `No (Recommended)` · `Yes — [Explicit], [Category("Staging")], reads appsettings.local.json` | `--live` |

`Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`.

Before writing, one R6 review: the files to create (project, handler, factory, one fixture per module, the `Program` edit if step 2 needs it), the test count per module, the error path per route (step 1), and the equivalent command. Options `Apply (Recommended)` · `Adjust` · `Cancel`. With `--dry-run`, print it and stop.

## 1. Read the tenant

```bash
find src/Tenants/<TenantName> -type f -name "*.cs" -not -path "*/bin/*" -not -path "*/obj/*"
cat src/Tenants/<TenantName>/appsettings.json
cat src/Tenants/<TenantName>/Program.cs
grep -E "ImplicitUsings|Nullable" src/Tests/<TenantName>.Tests/*.csproj   # --no-scaffold only
```

**Upstream clients.** Find them anywhere in the tenant, not just `Endpoints/` (APIS keeps `ZimsApi` in `Zims/`):

```bash
grep -rnE "\b(I?RestEndpoint|I?SoapEndpoint|Gateway)\b" src/Tenants/<TenantName> --include=*.cs | grep -vE "/(bin|obj)/|using |Options"
```

Also read multi-line class declarations and follow intermediate base classes; skip `abstract` ones. For each concrete client note: class name, **real namespace** (goes into the factory `using`), constructor signature, and its config section — `Endpoints:<ClassName>` (REST) or `SoapEndpoints:<ClassName>` (SOAP). REST clients are built with `ActivatorUtilities` (extra DI arguments such as `IOptions<TOptions>` allowed); SOAP clients take `HttpClient` only.

**Error path, per route.** The 404/500 assertions depend on it (step 6):

| Path | How to spot it | Upstream 404/500 surfaces as |
|---|---|---|
| **A — Result** | Handler returns `CustomResults.Problem(result)` on a `Result` from a non-throwing call (`GetAsync`, `PostAsync`, …, `PostSoap11Result`) | `application/problem+json`, status from the `Error` type (C2) |
| **B — throw** | Handler or client calls a throwing method: `Get`/`Post`/`Put`/`Patch`/`Delete` (no `Async`, they call `EnsureSuccess`), `Get<T>`/`GetFromJsonAsync`, `TryValidateSoap11Response` | `RestExceptionHandlingMiddleware`: `application/json` `{ "message", "traceId" }`, status = the upstream status (else 500). After `EnsureSuccess`, `message` **is the upstream body**. A SOAP `Fault` thrown on HTTP 200 comes back as **200** |
| **C — unhandled** | Throwing call and no `app.UseRestExceptionHandler()` in `Program.cs` (`grep -L UseRestExceptionHandler src/Tenants/*/Program.cs`) | Development exception page, 500 |

Decide per route; one module can mix paths.

**JSON casing.** Minimal-API (Carter) responses use ASP.NET Core's web defaults — camelCase — unless `ConfigureHttpJsonOptions` changes them. Controller tenants that call `AddControllers().AddJsonOptions(o => o.JsonSerializerOptions.PropertyNamingPolicy = null)` emit PascalCase (`grep -l "PropertyNamingPolicy *= *null" src/Tenants/*/Program.cs`). `Configure<JsonSerializerOptions>` is the instance clients use to read upstream JSON, not the response serializer.

**In-process auth.** `grep -lE "AddAuthentication" src/Tenants/*/Program.cs` — those tenants authenticate the caller themselves; step 5 adds a test scheme.

Reference projects, in order of usefulness:

- `src/Tests/APIS.Tests` — factory, the recording `TestHelpers/MockHttpMessageHandler.cs`, `Modules/PaxlstModuleTests.cs` driving real routes
- `src/Tests/ZPS.Tests` — mocked **and** live factories side by side, `Shared.Endpoints.Gateway` mock, `[Category("Staging")]` fixture with an `Assume` guard
- `src/Tests/PQPS.Tests` — SOAP: `TestHelpers/MockSoapHttpMessageHandler.cs`, primary-handler swap in `PqpsWebApplicationFactory` (xUnit)
- `src/Tests/MMMD.Tests` — controllers variant
- `src/Tests/NDR.Tests` — the minimal shape

## 2. Make `Program` reachable — only if needed

On net10.0 the top-level `Program` is public, so `WebApplicationFactory<Program>` compiles without an edit (PQPS and ZamData tests do). Only if the test project fails to compile on `Program` (inaccessible/not found), append to the tenant's `Program.cs`:

```csharp
public partial class Program;
```

Both `;` and `{ }` forms exist in the repo (`grep -l "partial class Program" src/Tenants/*/Program.cs`). It is the one edit this skill makes inside `src/Tenants/`.

## 3. Create the project

`src/Tests/<TenantName>.Tests/<TenantName>.Tests.csproj`. NUnit is the house stack for new projects — do not introduce xUnit. Under `--no-scaffold`, write fixtures in whatever framework the existing project uses (PQPS, ZamData and AdminAPI are xUnit).

```xml
<Project Sdk="Microsoft.NET.Sdk">

  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <IsPackable>false</IsPackable>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="FluentAssertions" Version="8.3.0" />
    <PackageReference Include="Microsoft.AspNetCore.Mvc.Testing" Version="10.0.0" />
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.14.1" />
    <PackageReference Include="NUnit" Version="4.3.2" />
    <PackageReference Include="NUnit3TestAdapter" Version="5.0.0" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\..\Tenants\<TenantName>\<TenantName>.csproj" />
  </ItemGroup>

</Project>
```

This is `APIS.Tests.csproj` verbatim. Most existing test projects have `ImplicitUsings` off (`grep -L "<ImplicitUsings>enable" src/Tests/*/*.Tests.csproj`), and the same templates go into them under `--no-scaffold` — so every `.cs` template below carries its full `using` block and a file-scoped namespace regardless (C1). If the test csproj enables `<Nullable>`, use `Dictionary<string, string?>` and `string?`.

There is no `Directory.Packages.props` in this repo — versions are pinned per project, so copy them exactly rather than floating. FluentAssertions 8.x is under the Xceed commercial licence; keep the repo-wide version and flag it in the report, don't change it.

Write `.cs` files UTF-8, CRLF; BOM optional (C6).

## 4. The mock handler

`TestHelpers/MockHttpMessageHandler.cs`. Copy the **recording** variant from `src/Tests/APIS.Tests/TestHelpers/MockHttpMessageHandler.cs` — most other projects have a minimal non-recording shape that can't assert what was forwarded. It stubs the response and records what was sent:

```csharp
using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;

namespace <TenantName>.Tests.TestHelpers;

public class MockHttpMessageHandler : HttpMessageHandler
{
    public Func<HttpRequestMessage, HttpResponseMessage> Handler { get; set; } =
        _ => new HttpResponseMessage(HttpStatusCode.OK);

    public List<HttpRequestMessage> Requests { get; } = [];
    public List<string> RequestBodies { get; } = [];

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        Requests.Add(request);
        RequestBodies.Add(request.Content is null ? null : await request.Content.ReadAsStringAsync(cancellationToken));
        return Handler(request);
    }
}
```

## 5. The factory

`<TenantName>WebApplicationFactory.cs`. The factory runs in `Development` (the `WebApplicationFactory` default), so `appsettings.Development.json` loads over `appsettings.json` — including any credentials it commits (C7). The in-memory collection is added last and wins. Two jobs, both required:

1. **Supply configuration.** `RegisterEndpoints` binds each `Endpoints:<Client>` section eagerly: a `__Token__` placeholder in a typed field (`Timeout` is a `TimeSpan`, `DangerousAcceptAnyServerCertificate` a `bool`, `RetryCount` an `int`) throws at startup. `new Uri(BaseUrl)` is lazy (runs when the named client is created) but still needs a valid value for the step 5 alternative. Override **every key the section has** in either appsettings file with a fake value, so no placeholder breaks binding and no committed credential is live. Keys are `Username`, never `UserName` (C3).
2. **Replace the client.** `ConfigureTestServices` re-registers each upstream client over the mock handler, exposed as a public property so tests can program the response.

```csharp
using System;
using System.Collections.Generic;
using System.Net.Http;
using <ClientNamespace>;
using <TenantName>.Tests.TestHelpers;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace <TenantName>.Tests;

public class <TenantName>WebApplicationFactory : WebApplicationFactory<Program>
{
    public MockHttpMessageHandler UpstreamHandler { get; } = new();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration(config =>
        {
            config.AddInMemoryCollection(new Dictionary<string, string>
            {
                ["Endpoints:<ClientClassName>:BaseUrl"] = "http://<system>-test",
                ["Endpoints:<ClientClassName>:AuthenticationScheme"] = "Basic",
                ["Endpoints:<ClientClassName>:Username"] = "test",
                ["Endpoints:<ClientClassName>:Password"] = "test",
                // Only keys the tenant's section actually has:
                ["Endpoints:<ClientClassName>:Timeout"] = "00:01:00",
                ["Endpoints:<ClientClassName>:DangerousAcceptAnyServerCertificate"] = "false",
                ["Endpoints:<ClientClassName>:RetryCount"] = "0"
            });
        });

        builder.ConfigureTestServices(services =>
        {
            services.AddTransient<<ClientClassName>>(sp => new <ClientClassName>(
                new HttpClient(UpstreamHandler) { BaseAddress = new Uri("http://<system>-test") }));
        });
    }
}
```

`<ClientNamespace>` is the client's real namespace from step 1 (`APIS.Zims`, `PQPS.Endpoints`); re-sort the block after substitution. One handler property per upstream system, named for it (`ZimsHandler`, `GatewayHandler`) when the tenant talks to more than one. Pass any extra constructor argument through `sp.GetRequiredService<...>()` — see `ApisWebApplicationFactory`, which resolves `IOptions<ApisOptions>` that way.

**Singleton capture (C5).** Carter builds modules once at `MapCarter()`, so a constructor-injected client — and the mock handler inside it — lives for the whole factory. Tests set `UpstreamHandler.Handler`; never create or assign a different handler object after the host starts.

**Alternative — keep the tenant's own client pipeline** (auth header, `HttpClientLoggingHandler`, base address), e.g. to assert the `Authorization` header. The typed-client name equals the type name, which is the named client `RegisterEndpoints` / `RegisterSoapEndpoints` configured, so only the primary handler changes. Shape from `PqpsWebApplicationFactory.cs`; add `using System.Linq;`:

```csharp
builder.ConfigureTestServices(services =>
{
    foreach (var d in services.Where(s => s.ServiceType == typeof(<ClientClassName>)).ToList())
        services.Remove(d);

    services.AddHttpClient<<ClientClassName>>()
        .ConfigurePrimaryHttpMessageHandler(() => UpstreamHandler);
});
```

Here the real `BaseUrl` / auth lambdas run, so the overrides must be complete and valid.

### SOAP upstream

Reference `src/Tests/PQPS.Tests/TestHelpers/MockSoapHttpMessageHandler.cs`.

- Override `SoapEndpoints:<ClientClassName>:BaseUrl` (empty → the client is never registered → DI failure) and every other key of the section, including one `<Op>Url` per operation URL.
- `AuthenticationScheme` must be non-null — a missing key is a `NullReferenceException` inside `RegisterSoapEndpoints`. Set `"None"` in tests: `ClientCertificate` decodes `PublicKey`/`PrivateKey` eagerly at startup, and a placeholder fails base64. Override `PublicKey`/`PrivateKey`/`Username`/`Password` to `""`.
- Re-register as `new <ClientClassName>(new HttpClient(UpstreamHandler) { BaseAddress = … })` — SOAP clients take `HttpClient` only.
- Stub responses as `soap:Envelope` with `Content-Type: text/xml`. Cover a `soap:Fault` on HTTP 200 **and** on HTTP 500 — Core handles them differently. Use the recording handler to assert the `SOAPAction` header and envelope in `RequestBodies`.

### Gateway / `EServicesShared` upstream

A tenant calling back into the gateway (directly or through `EServicesShared`) mocks `Shared.Endpoints.Gateway` — see `src/Tests/ZPS.Tests/ZpsWebApplicationFactory.cs`. Fully qualify it: some tenants define their own `<T>.Endpoints.Gateway` (`grep -rlE "class Gateway\b" src/Tenants --include=*.cs`).

```csharp
services.AddTransient<Shared.Endpoints.Gateway>(_ => new Shared.Endpoints.Gateway(
    new HttpClient(GatewayHandler) { BaseAddress = new Uri("http://gateway-test") }));
```

Override every `Endpoints:Gateway:*` key too — ZPS doesn't, so its mocked factory still loads the committed Development credentials. `EServicesShared` resolves the mocked `Gateway` itself; assert upstream paths (`/t/ndw/...`) on `GatewayHandler.Requests`.

### In-process auth tenants

For tenants found in step 1, add `TestHelpers/TestAuthHandler.cs` and register it as the default scheme in `ConfigureTestServices`. It authenticates only when the request carries the test header, so the same factory tests both 401 and the authorised path:

```csharp
using System.Security.Claims;
using System.Text.Encodings.Web;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace <TenantName>.Tests.TestHelpers;

public class TestAuthHandler(IOptionsMonitor<AuthenticationSchemeOptions> options, ILoggerFactory logger, UrlEncoder encoder)
    : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    public const string SchemeName = "Test";
    public const string UserHeader = "X-Test-User";

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Headers.TryGetValue(UserHeader, out var user))
            return Task.FromResult(AuthenticateResult.NoResult());

        var identity = new ClaimsIdentity([new Claim(ClaimTypes.Name, user.ToString())], SchemeName);
        return Task.FromResult(AuthenticateResult.Success(
            new AuthenticationTicket(new ClaimsPrincipal(identity), SchemeName)));
    }
}
```

```csharp
services.AddAuthentication(TestAuthHandler.SchemeName)
    .AddScheme<AuthenticationSchemeOptions, TestAuthHandler>(TestAuthHandler.SchemeName, _ => { });
```

Add the claims the tenant's policies read (e.g. GOVZM `PaymentProcessor`). A policy that pins a scheme with `AddAuthenticationSchemes(...)` ignores the default — note such routes and cover them only with the real scheme or leave them untested with the reason.

## 6. Endpoint fixtures

One fixture per module or controller: `<Name>ModuleTests.cs` / `<Name>ControllerTests.cs`. Mirror the tenant's folder layout (`Modules/`, `Controllers/`); a tenant with one module can keep its fixture at the project root. Namespace follows the folder (`<TenantName>.Tests.Modules`).

```csharp
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json.Nodes;
using System.Threading.Tasks;
using FluentAssertions;
using NUnit.Framework;

namespace <TenantName>.Tests.Modules;

/// <summary>
/// <What the tenant does on these routes>. <Upstream> is replaced by the recording mock handler
/// via <see cref="<TenantName>WebApplicationFactory"/>.
/// </summary>
[TestFixture]
public class <Name>ModuleTests
{
    private const string UpstreamSentinel = "UPSTREAM-SENTINEL-BODY";

    private <TenantName>WebApplicationFactory _factory;
    private HttpClient _client;

    [SetUp]
    public void SetUp()
    {
        _factory = new <TenantName>WebApplicationFactory();
        _client = _factory.CreateClient();
    }

    [TearDown]
    public void TearDown()
    {
        _client.Dispose();
        _factory.Dispose();
    }

    [Test]
    public async Task GetThing_ReturnsOk_WhenUpstreamFindsIt()
    {
        _factory.UpstreamHandler.Handler = _ => new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent("""{"id":"1","name":"Alpha"}""", Encoding.UTF8, "application/json")
        };

        var response = await _client.GetAsync("/things/1");

        response.StatusCode.Should().Be(HttpStatusCode.OK);
        var body = JsonNode.Parse(await response.Content.ReadAsStringAsync());
        body["name"].GetValue<string>().Should().Be("Alpha");
    }

    // Path A — route returns CustomResults.Problem(result)
    [Test]
    public async Task GetThing_Returns404ProblemDetails_WhenUpstreamHasNothing()
    {
        _factory.UpstreamHandler.Handler = _ => new HttpResponseMessage(HttpStatusCode.NotFound);

        var response = await _client.GetAsync("/things/missing");

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/problem+json");
    }

    // Path B — throwing call caught by RestExceptionHandlingMiddleware
    [Test]
    public async Task GetThing_MirrorsUpstream404_WhenUpstreamHasNothing()
    {
        _factory.UpstreamHandler.Handler = _ => new HttpResponseMessage(HttpStatusCode.NotFound)
        {
            Content = new StringContent(UpstreamSentinel)
        };

        var response = await _client.GetAsync("/things/missing");

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/json");
        var body = JsonNode.Parse(await response.Content.ReadAsStringAsync());
        body["traceId"].Should().NotBeNull();
    }
}
```

Write only the error-test variant that matches each route's path from step 1.

What to cover, per route. `--coverage full` takes all five plus the swagger smoke test, `errors` the first three, `smoke` the first only:

- **Happy path** — upstream 200 maps to the tenant's public response shape. Assert on field **names and values**, not just the status, since the DTO boundary is the whole point of the mapper
- **Upstream 404** — path A: 404 `application/problem+json` (status per C2). Path B: mirrors the upstream 404 as `application/json` `{message, traceId}`. A route that deliberately maps 404 to something else (empty list, paginated result) — assert that
- **Upstream 500 or garbage body** — stub the upstream body with `UpstreamSentinel`. Path A: 500 `problem+json` and the body does not contain the sentinel. Path B: status mirrors upstream, `application/json`, `traceId` present — don't assert on the sentinel either way; list the route as an upstream-body leak in the report (Core design, not fixed here)
- **What was forwarded** — for every `POST`/`PATCH`, assert against `UpstreamHandler.RequestBodies` and `Requests` that the path, query and body the tenant sent upstream are correct. This catches mapper regressions that a response-only assertion cannot
- **Route contract** — path and query parameters bind, and a missing required one gives 400
- **Auth** (in-process auth tenants) — no `X-Test-User` → 401; with it → the handler runs
- **Swagger smoke** (once per project, `full` only) — `SwaggerTests.cs`: `GET /swagger/<doc>/swagger.json` → 200 and parses with a `paths` node. `<doc>` is the `SwaggerDoc("<name>", …)` name in `Program.cs` (`v1` usually, `hub` in PQPS); served because the factory runs as Development. `tenant-deliverables` and `api-spec-sync` depend on this document

Match the tenant's JSON casing from step 1 before writing assertions.

Use `System.Text.Json` (`JsonNode`, `JsonDocument`). The repo has migrated off Newtonsoft; `src/Tests/StjMigrationSnapshots` exists to pin that behaviour.

Write an XML doc comment on each fixture stating what the tenant does and what is mocked — it is the only place the integration's intent is recorded.

## 7. Staging fixture — `--live` only

A second factory that mocks nothing and reads real credentials from a gitignored local file (`<TenantName>LiveWebApplicationFactory.cs`):

```csharp
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;

namespace <TenantName>.Tests;

public class <TenantName>LiveWebApplicationFactory : WebApplicationFactory<Program>
{
    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.ConfigureAppConfiguration(config =>
        {
            config.AddJsonFile("appsettings.local.json", optional: true);
        });
    }
}
```

Tenant pipelines only build and push the Docker image — no pipeline runs tests. The two attributes keep the fixture out of IDE "Run All" and `dotnet test src/ZamConnect.sln`:

```csharp
[TestFixture]
[Explicit("Requires appsettings.local.json with staging credentials in src/Tenants/<TenantName>/")]
[Category("Staging")]
public class <Name>StagingTests
```

`SetUp` guards every value it reads, so a missing or placeholder value skips instead of failing (`src/Tests/ZPS.Tests/DocumentsStagingTests.cs`):

```csharp
var config = _factory.Services.GetRequiredService<IConfiguration>();
_value = config["TestData:<Key>"];
Assume.That(!string.IsNullOrEmpty(_value) && !_value.StartsWith("__"),
    "appsettings.local.json must define TestData:<Key>");
```

(needs `using Microsoft.Extensions.Configuration;` and `using Microsoft.Extensions.DependencyInjection;`).

Document the required `appsettings.local.json` shape in the factory's XML doc comment, including any `TestData` keys the fixture reads — copy the pattern from `src/Tests/ZPS.Tests/ZpsLiveWebApplicationFactory.cs`. Never commit that file or the real credentials, and never put a real credential in the fixture.

Committed Development credentials cut both ways: where a tenant's `appsettings.Development.json` holds real values (ZPS does), a *mocked* test whose factory misses an override calls the real test environment. Step 5's "override every key" rule is what prevents that.

## 8. Register and run

```bash
dotnet sln src/ZamConnect.sln add src/Tests/<TenantName>.Tests/<TenantName>.Tests.csproj --solution-folder Tests
dotnet test src/Tests/<TenantName>.Tests/<TenantName>.Tests.csproj -v q --nologo
```

All non-`[Explicit]` tests must pass. Never weaken an assertion to make it green. What counts as a tenant defect:

- **Fix in the tenant** — its own code is wrong: mapper drops or misnames a field, route/query doesn't bind, wrong upstream path or body forwarded.
- **Not a defect here — assert the actual behaviour and report it** — anything decided by the route's error path (step 1) or by Core: path B mirroring upstream status, the `{message, traceId}` shape, the upstream body in `message`, a SOAP fault returned as 200. Asserting the real contract is not weakening. Changing the error path (throwing → `*Async` + `CustomResults.Problem`) is `tenant-integration` work, and `src/Core/` is never edited by this skill.

When tests fail, and not with `--auto`, ask once with header `Failures`. The question text lists each failing test and the one-line cause:

- `Fix the tenant and re-run (Recommended)` — the failure shows a tenant defect as defined above: fix it, re-run, ask again if it still fails
- `Fix the test and re-run` — the test itself is wrong: wrong casing for this tenant's JSON options, or it assumed the wrong error path. Never to weaken an assertion
- `Stop with the failures reported` — in gate mode, `GATE-RESULT: failed <n> tests failing`

Common failures:

- `Failed to convert configuration value '__…__'` (to `TimeSpan`/`Boolean`/`Int32`) — a typed field in an `Endpoints:*` section the in-memory configuration did not override
- `Invalid URI: The format of the URI could not be determined` — a `BaseUrl` placeholder reached `new Uri(...)`: a client not re-registered, or the primary-handler alternative without a full override
- `NullReferenceException` in `RegisterSoapEndpoints` — `SoapEndpoints:<Type>:AuthenticationScheme` missing; `FormatException` (base64) — `ClientCertificate` keys loaded; set `"None"`
- DI resolution error on `CreateClient()` — the client wasn't registered (section missing → skipped with a warning), or its constructor takes an argument the factory's re-registration did not supply
- `Program` inaccessible / not found — apply step 2
- 401 on every route — in-process auth tenant without the test scheme or `X-Test-User` header

## Report

One line per file created, the solution entry, and the `dotnet test` result as counts (passed / failed / skipped). Then a table of routes covered against routes exposed, with each route's error path (A/B/C); name any route left untested and why.

Findings, never fixed by this skill:

- Upstream-body leak — every path-B route whose throwing call uses `EnsureSuccess`
- No `UseRestExceptionHandler` (path C)
- This tenant's `appsettings.Development.json` commits credential values (count of keys only, C7)
- FluentAssertions 8.x licence (Xceed commercial) — repo-wide

End with the equivalent command (R7), e.g. `/tenant-tests PQPS --coverage full --live`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>`.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
- Baseline (C7): many tracked `appsettings.Development.json` files, and `src/Tenants/Certificates/*.p12`, commit real secrets. Never use a tenant's Development file as the template for factory overrides or the `appsettings.local.json` shape — fake values in the factory, key names only in the doc comment.
