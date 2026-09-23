---
name: tenant-tests
description: Scaffold and write the test project for a ZamConnect tenant — `src/Tests/<Tenant>.Tests/` with a `WebApplicationFactory`, a mock HTTP handler standing in for the upstream, and endpoint tests that drive the tenant's real Carter modules or controllers over HTTP. Optionally adds an `[Explicit]` staging fixture that calls the live upstream. Use when the user says "add tests for <Tenant>", "test this integration", "write module tests", "cover <Tenant> endpoints", or types /tenant-tests.
argument-hint: "<TenantName> [--module <Name> ...] [--coverage full|errors|smoke] [--live] [--no-scaffold] [--auto] [--dry-run]"
allowed-tools: Read Write Edit Glob Grep Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(mkdir *) Bash(dotnet *) AskUserQuestion
disable-model-invocation: false
---

# ZamConnect Tenant Tests

20 of 58 tenants have a test project and they all share one shape: a `WebApplicationFactory<Program>` that swaps the upstream `HttpClient` for a recording mock, and fixtures that exercise the tenant's own routes end to end over HTTP. This skill reproduces that shape and writes the tests.

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`).

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`.

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
| `Coverage` | What should each route be tested for? | `Full matrix (Recommended)` — happy path, upstream 404, upstream 500, forwarded body, route contract · `Happy path + errors` — no forwarded-body or route-contract cases · `Smoke only` — happy path per route | `--coverage` |
| `Modules` | Which modules or controllers? (`multiSelect`) | The tenant's modules from step 1, with their route counts, up to 3 · `All <n> modules (Recommended)`. With more than 4, spread them over up to 3 more questions in this call (R9) | `--module` |
| `Live` | Add a staging fixture that calls the real upstream? | `No (Recommended)` · `Yes — [Explicit], [Category("Staging")], reads appsettings.local.json` | `--live` |

`Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`.

Before writing, one R6 review: the files to create (project, handler, factory, one fixture per module, the `Program` edit if needed), the test count per module, and the equivalent command. Options `Apply (Recommended)` · `Adjust` · `Cancel`. With `--dry-run`, print it and stop.

## 1. Read the tenant

```bash
find src/Tenants/<TenantName> -type f -name "*.cs" -not -path "*/bin/*" -not -path "*/obj/*"
cat src/Tenants/<TenantName>/appsettings.json
tail -5 src/Tenants/<TenantName>/Program.cs
```

Note, for each upstream client (`Endpoints/*.cs` deriving from `RestEndpoint`): its class name, its constructor signature, and its `Endpoints:<ClassName>` configuration keys. The factory has to reconstruct that client by hand, so a client taking `IOptions<TOptions>` as well as `HttpClient` needs that option resolved from the test host's services.

Reference projects, in order of usefulness:

- `src/Tests/APIS.Tests` — the fullest example: factory, `TestHelpers/MockHttpMessageHandler.cs`, `Modules/PaxlstModuleTests.cs` driving real routes
- `src/Tests/ZPS.Tests` — mocked **and** live factories side by side, plus a `[Category("Staging")]` fixture
- `src/Tests/MMMD.Tests` — controllers variant
- `src/Tests/NDR.Tests` — the minimal shape

## 2. Make `Program` reachable

`WebApplicationFactory<Program>` cannot bind to a top-level-statements entry point. The tenant's `Program.cs` must end with:

```csharp
public partial class Program;
```

10 tenants already have it (`APIS`, `MLNR`, `MMMD`, `MobileID`, `NDR`, `NDW`, `NLR`, `RTSA`, `USSD`, `WARMA`). Add it if missing — it is the one edit this skill makes inside `src/Tenants/`.

## 3. Create the project

`src/Tests/<TenantName>.Tests/<TenantName>.Tests.csproj`. NUnit is the house stack (14 of 20 projects); do not introduce xUnit into a new project even though three older ones use it.

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

There is no `Directory.Packages.props` in this repo — versions are pinned per project, so copy them exactly rather than floating.

## 4. The mock handler

`TestHelpers/MockHttpMessageHandler.cs`, verbatim across every existing project. It both stubs the response and records what was sent, which is what lets a test assert the tenant forwarded the right body upstream.

```csharp
using System.Net;

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

`<TenantName>WebApplicationFactory.cs`. Two jobs, both required:

1. **Supply configuration.** `appsettings.json` ships `__Endpoints.*__` deployment placeholders, and `new Uri("__Endpoints.X.BaseUrl__")` throws inside `RegisterEndpoints`. `AddInMemoryCollection` overrides them with a syntactically valid fake host.
2. **Replace the client.** `ConfigureTestServices` re-registers each upstream client over the mock handler, exposed as a public property so tests can program the response.

```csharp
using <TenantName>.Endpoints;
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
                ["Endpoints:<ClientClassName>:Password"] = "test"
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

One handler property per upstream system, named for it (`ZimsHandler`, `GatewayHandler`) when the tenant talks to more than one. Pass any extra constructor argument through `sp.GetRequiredService<...>()` — see `ApisWebApplicationFactory`, which resolves `IOptions<ApisOptions>` that way.

A tenant whose only upstream is `EServicesShared` mocks `Gateway` instead: override `Endpoints:Gateway:*` and re-register `Shared.Endpoints.Gateway`.

## 6. Endpoint fixtures

One fixture per module or controller: `<Name>ModuleTests.cs` / `<Name>ControllerTests.cs`. Put them in `Modules/` when the tenant has several (APIS), at the project root when it has one or two (NDR, ZPS).

```csharp
[TestFixture]
public class <Name>ModuleTests
{
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

    [Test]
    public async Task GetThing_Returns404_AsProblemDetails_WhenUpstreamHasNothing()
    {
        _factory.UpstreamHandler.Handler = _ => new HttpResponseMessage(HttpStatusCode.NotFound);

        var response = await _client.GetAsync("/things/missing");

        response.StatusCode.Should().Be(HttpStatusCode.NotFound);
        response.Content.Headers.ContentType!.MediaType.Should().Be("application/problem+json");
    }
}
```

What to cover, per route. `--coverage full` takes all five, `errors` the first three, `smoke` the first only:

- **Happy path** — upstream 200 maps to the tenant's public response shape. Assert on field **names and values**, not just the status, since the DTO boundary is the whole point of the mapper
- **Upstream 404** — surfaces as `ProblemDetails` with the tenant's own status, via `CustomResults.Problem`
- **Upstream 500 or garbage body** — surfaces as 500 `ProblemDetails` and never leaks the upstream body
- **What was forwarded** — for every `POST`/`PATCH`, assert against `UpstreamHandler.RequestBodies` and `Requests` that the path, query and body the tenant sent upstream are correct. This catches mapper regressions that a response-only assertion cannot
- **Route contract** — path and query parameters bind, and a missing required one gives 400

Match the tenant's JSON casing. Carter with this repo's default options emits camelCase, and a tenant that overrides `PropertyNamingPolicy` will not — check `Program.cs` before writing assertions.

Use `System.Text.Json` (`JsonNode`, `JsonDocument`). The repo has migrated off Newtonsoft; `src/Tests/StjMigrationSnapshots` exists to pin that behaviour.

Write an XML doc comment on each fixture stating what the tenant does and what is mocked — every existing fixture does, and it is the only place the integration's intent is recorded.

## 7. Staging fixture — `--live` only

A second factory that mocks nothing and reads real credentials from a gitignored local file:

```csharp
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

Its fixture carries both attributes, or CI will try to reach the upstream and fail:

```csharp
[TestFixture]
[Explicit("Requires appsettings.local.json with staging credentials in src/Tenants/<TenantName>/")]
[Category("Staging")]
public class <Name>StagingTests
```

Document the required `appsettings.local.json` shape in the factory's XML doc comment, including any `TestData` keys the fixture reads — copy the pattern from `src/Tests/ZPS.Tests/ZpsLiveWebApplicationFactory.cs`. Never commit that file or the real credentials, and never put a real credential in the fixture.

## 8. Register and run

```bash
dotnet sln src/ZamConnect.sln add src/Tests/<TenantName>.Tests/<TenantName>.Tests.csproj --solution-folder Tests
dotnet test src/Tests/<TenantName>.Tests/<TenantName>.Tests.csproj -v q --nologo
```

All non-`[Explicit]` tests must pass. If a test fails because the tenant is wrong rather than the test, say so and fix the tenant — do not weaken the assertion to make it green.

When tests fail, and not with `--auto`, ask once with header `Failures`. The question text lists each failing test and the one-line cause:

- `Fix the tenant and re-run (Recommended)` — the failure shows a tenant defect: fix it, re-run, ask again if it still fails
- `Fix the test and re-run` — only when the test itself is wrong, e.g. it asserts the wrong casing for this tenant's JSON options. Never to weaken an assertion
- `Stop with the failures reported` — in gate mode, `GATE-RESULT: failed <n> tests failing`

Common failures:

- `Invalid URI: The format of the URI could not be determined` — a `__Endpoints.*__` placeholder the in-memory configuration did not override
- DI resolution error on `CreateClient()` — the client's real constructor takes an argument the factory's re-registration did not supply
- `WebApplicationFactory<Program>` will not compile — step 2 was skipped

## Report

One line per file created, the solution entry, and the `dotnet test` result as counts (passed / failed / skipped). Then a table of routes covered against routes exposed, and name any route left untested and why.

End with the equivalent command (R7), e.g. `/tenant-tests PQPS --coverage full --live`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>`.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
