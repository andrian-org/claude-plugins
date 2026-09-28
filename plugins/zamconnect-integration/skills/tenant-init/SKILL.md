---
name: tenant-init
description: Scaffold a new ZamConnect integration tenant project from the standard tenant boilerplate (Carter + Serilog + OpenTelemetry + Prometheus + health checks, net10.0), wire it into ZamConnect.sln, and verify it builds. Use when the user says "create a new tenant", "add tenant <NAME>", "scaffold integration for <AGENCY>", or types /tenant-init.
argument-hint: "<TenantName> [--controllers] [--full-name \"<name>\"] [--integrates rest,soap,shared,unknown] [--port <https>] [--no-pipeline] [--auto] [--dry-run] [--help]"
allowed-tools: Read Write Edit Glob Grep Bash(mkdir *) Bash(cat *) Bash(dotnet *) Bash(find *) Bash(grep *) Bash(ls *) Bash(sort *) Bash(uniq *) Bash(docker *) AskUserQuestion Skill
disable-model-invocation: false
---

# Create ZamConnect Tenant

Scaffold a new tenant under `src/Tenants/<TenantName>/`. Produce the boilerplate only — **no Modules, Models, Controllers, Endpoints, or Mappers** unless the user asks for them in the same request. The boilerplate is spec-ready from the start (step 3), so the integration never has to retrofit it.

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Read it first.

Repo facts shared with the other skills — usings, config casing, token naming, file hygiene, committed secrets, the live route reference — are in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md` and cited below by section id (C1–C8). Never trust a count in either file; re-derive it.

## Inputs

| Input | Flag | Default |
|---|---|---|
| `<TenantName>` | positional, required | — PascalCase; matches folder, csproj, assembly, namespace root |
| Style | `--controllers` | `carter` (minimal API modules) |
| Full descriptive name | `--full-name "<name>"` | Asked in step 1a. Goes into `OpenApiInfo.Title` as `"<full name> (<TenantName>)"` |
| What it integrates with | `--integrates rest,soap,shared,unknown` | Asked in step 1a. Decides the defaults of the later pipeline steps |
| Dev ports | `--port <https>` | Next free pair from the scan in step 2 |
| Pipeline | `--no-pipeline` / `--auto` | Guided. `--no-pipeline` stops after the scaffold; `--auto` runs the whole chain without gates |
| Dry run | `--dry-run` | Off. Stops at the review in step 2a and writes nothing |
| Help | `--help` | Print the arguments and examples, then stop (R14) |

If `<TenantName>` is missing, ask for it in plain text before anything else, as the contract's Missing arguments section says for a new tenant (R13): PascalCase, and no existing `src/Tenants/<TenantName>/` folder. Under `--auto`, stop with `missing <TenantName>`. Everything else goes through step 1a.

## Reference tenants

Read these before generating; they are the canonical shapes.

- `src/Tenants/CEEC` — Carter style, gateway client under `Endpoints/`, references `Shared`
- `src/Tenants/MOH` — Carter style plus `RegisterGatewayEndpoint` and `EServicesShared`
- `src/Tenants/MOA` — Controllers style, no `Shared` reference

## Steps

### 1. Confirm the tenant does not exist

```bash
ls src/Tenants | grep -i "TenantName"
grep -n "TenantName" src/ZamConnect.sln
grep -n -i "t_<slug>\|/t/<slug>/\| <TENANT> |" docs/zamconnect-test-routes.md
```

`<slug>` is the tenant name lowercased with no separators (step 5), `<TENANT>` the tenant name uppercased (step 6). Stop and ask if any hits. A hit in the routes doc (C8) means the gateway already has that route, cluster or scope — importing step 6 would overwrite it.

### 1a. Intake

One `AskUserQuestion` call. Leave out any question whose flag was passed. With `--auto`, take every `(Recommended)` option and ask nothing.

| Header | Question | Options | → flag |
|---|---|---|---|
| `Style` | Project style for `<TenantName>`? | `Carter modules (Recommended)` — minimal API, like CEEC and MOH · `MVC controllers` — like MOA | `--controllers` |
| `Integrates` | What will `<TenantName>` integrate with? (`multiSelect`) | `Agency REST API` · `Agency SOAP service` · `Shared e-Services` — NIR, PACRA, ZRA, ZDI and the rest via `EServicesShared` · `Not known yet` | `--integrates` |
| `Name` | Full descriptive name of `<TenantName>`, for the API specification title. Type it in Other, or: | `Take it from the integration source (Recommended)` — step 2 proposes it from the spec or WSDL title · `Use <TenantName> for now` — the title stays the bare code and the deliverables report it | `--full-name` |
| `Pipeline` | After the scaffold? | `Guided — gate each step (Recommended)` · `Auto — run every step with defaults` · `Scaffold only` | `--auto` / `--no-pipeline` |

Leave out the `Pipeline` question when run with `--no-pipeline`, which is how `tenant-pipeline` calls this skill.

Record the answers as flags for the equivalent command, for example `/tenant-init PQPS --integrates soap --full-name "Plant Quarantine and Phytosanitary Service"`. `Take it from the integration source` records `fullName: "pending"` in state; step 2 picks it up from there.

### 2. Pick free dev ports

```bash
grep -h applicationUrl src/Tenants/*/Properties/launchSettings.json | grep -o "[0-9][0-9][0-9][0-9][0-9]" | sort -n | uniq
```

Choose an unused consecutive pair (https, http). Repo convention is a high 5-digit pair next to the existing ones; the scan is the only source — never reuse a port from an example.

### 2a. Review before writing

Work out the pipeline slug (step 4) and `core-<slug>` (step 5) now, so the review can show them. Then make one R6 review call. The question text is the plan:

```
Scaffold PQPS (Carter, spec-ready):
  src/Tenants/PQPS/            csproj, Program.cs, appsettings x2, Dockerfile, launchSettings, Swagger/, GATEWAY-CONFIG.md
  .azure/tenant.azure-pipelines.pqps.yaml
  src/.dockercompose/docker-compose.yml   + core-pqps
  src/ZamConnect.sln                      + Tenants/PQPS
Dev ports 53398 / 53399 · gateway route t_pqps → /t/pqps (cluster PQPS, scope pqps) · title "Plant Quarantine and Phytosanitary Service (PQPS)"
Command: /tenant-init PQPS --full-name "Plant Quarantine and Phytosanitary Service" --integrates soap --port 53398
```

Options: `Apply (Recommended)` · `Adjust` · `Cancel`. `Adjust` asks one `multiSelect` — `Dev ports`, `Pipeline slug`, `Style`, `Full name` — and re-asks only the ones picked. Ports and slug are the values most often overridden: offer the next two free pairs and the hyphenated / unhyphenated slug as options, never "type it in Other".

With `--dry-run`, print the plan and stop here. With `--auto`, skip the call and apply. `Cancel` ends the skill; with `--no-pipeline` its last line is `GATE-RESULT: stopped`.

### 3. Create the files

`src/Tenants/<TenantName>/` with exactly:

```
<TenantName>.csproj
Program.cs
appsettings.json
appsettings.Development.json
Dockerfile
Properties/launchSettings.json
Swagger/OpenApiDocumentation.cs
GATEWAY-CONFIG.md
```

File hygiene per C6: `.editorconfig` asks for CRLF + UTF-8 BOM on `.cs`; `core.autocrlf` fixes line endings on commit and BOM is optional (APIS has none).

#### `<TenantName>.csproj`

`GenerateDocumentationFile` feeds `IncludeXmlComments`, so `///` comments on DTOs reach the generated specification. `CS1591` is silenced because not every public type needs one.

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">

  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <DockerDefaultTargetOS>Linux</DockerDefaultTargetOS>
    <DockerfileContext>..\..</DockerfileContext>
    <GenerateDocumentationFile>true</GenerateDocumentationFile>
    <NoWarn>$(NoWarn);CS1591</NoWarn>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Carter" Version="10.0.0" />
    <PackageReference Include="prometheus-net.AspNetCore.HealthChecks" Version="8.2.1" />
  </ItemGroup>

  <ItemGroup>
    <ProjectReference Include="..\..\Core\Internal\Internal.csproj" />
    <ProjectReference Include="..\..\Core\Shared\Shared.csproj" />
  </ItemGroup>

</Project>
```

For `--controllers`: drop the `Carter` package and the `Shared` project reference, and add `<CodeAnalysisRuleSet>..\..\.sonarlint\zamconnectcsharp.ruleset</CodeAnalysisRuleSet>` (MOA shape).

The csproj sets neither `ImplicitUsings` nor `Nullable`, like most tenants (C1). So every `.cs` template below carries its full `using` block — a missing one is a build error — and every file except the top-level-statement `Program.cs` has a file-scoped `namespace <TenantName>.<Folder>;`. Don't add either property. If the developer adds them, or a later skill works on an existing tenant, check the csproj with the C1 greps: `<Nullable>enable</Nullable>` makes `string?` / `T?` the rule for optional members.

#### `Program.cs` (Carter style)

```csharp
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using Carter;
using Internal.Extensions.Extensions.Logging;
using Internal.Extensions.Extensions.Rest;
using Internal.Extensions.Extensions.Telemetry;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.OpenApi.Models;
using Prometheus;

Activity.DefaultIdFormat = ActivityIdFormat.W3C;
Activity.ForceDefaultIdFormat = true;

var builder = WebApplication.CreateBuilder(args);
builder.Host.UseConfiguredSerilog();

builder.Services.Configure<JsonSerializerOptions>(options =>
{
    options.ReferenceHandler = ReferenceHandler.IgnoreCycles;
    options.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    options.PropertyNameCaseInsensitive = true;
});
builder.Services.AddCarter()
    .ConfigureHttpJsonOptions(options =>
    {
        options.SerializerOptions.ReferenceHandler = ReferenceHandler.IgnoreCycles;
        options.SerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    });
builder.Services.AddEndpointsApiExplorer();
if (builder.Environment.IsDevelopment())
{
    builder.Services.AddSwaggerGen(options =>
    {
        options.SwaggerDoc("v1", new OpenApiInfo
        {
            Title = "<Full name> (<TenantName>)",
            Version = "v1",
            Description = OpenApiDocumentation.Description
        });

        options.AddSecurityDefinition("basic", new OpenApiSecurityScheme
        {
            Type = SecuritySchemeType.Http,
            Scheme = "basic",
            Description = "HTTP Basic authentication. Credentials are issued per consumer and "
                          + "are checked by the ZamConnect gateway before the request reaches "
                          + "this service; an unauthenticated call is rejected with 401."
        });

        options.AddSecurityRequirement(new OpenApiSecurityRequirement
        {
            [new OpenApiSecurityScheme
            {
                Reference = new OpenApiReference { Type = ReferenceType.SecurityScheme, Id = "basic" }
            }] = []
        });

        var xmlPath = Path.Combine(AppContext.BaseDirectory, "<TenantName>.xml");
        if (File.Exists(xmlPath))
        {
            options.IncludeXmlComments(xmlPath);
        }
    });
}

builder.Services.RegisterEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration);
builder.Services.AddHealthChecks().ForwardToPrometheus();
builder.ConfigureOpenTelemetry();

var app = builder.Build();
app.UseHttpMetrics();
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseBaseLogger();

app.UseRestExceptionHandler();
app.MapHealthChecks("/health/live", new HealthCheckOptions { AllowCachingResponses = false });
app.MapMetrics();

app.MapCarter();
app.UseOpenTelemetryPrometheusScrapingEndpoint("/metrics/otel");

app.Run();

public partial class Program;
```

Insert `using <TenantName>.Swagger;` at its alphabetical position after the `System*` block (`base.md` rule: `System*` first, then alphabetical, no groups) — between `Microsoft.OpenApi.Models` and `Prometheus` for `PQPS`, after `Prometheus` for `TT`.

`Title` is `"<Full name> (<TenantName>)"` when the full name is known. When it's `pending` or the code was chosen, write `"<TenantName>"`; step 2 or the developer replaces it later. `public partial class Program;` is harmless and kept for older `WebApplicationFactory<Program>` test patterns; it is not required — .NET 10 generates a public `Program`, and existing test projects (PQPS, ZamData) compile without it.

For `--controllers`, follow `src/Tenants/MOA/Program.cs`: swap `AddCarter`/`MapCarter` for `AddControllers`/`MapControllers`, and add `AddHttpClient()`, `AddHttpContextAccessor()`, `UseRouting()`, and `options.EnableAnnotations()` inside the same `AddSwaggerGen` block. The Swagger block and the observability lines are the same either way.

#### `Swagger/OpenApiDocumentation.cs`

The Executive Summary of the generated specification comes from `Description`, and only from there (see `src/Tenants/APIS/Swagger/OpenApiDocumentation.cs`). Scaffold one short paragraph that states only what is known. `tenant-integration` extends it with the datasets the tenant exposes.

```csharp
namespace <TenantName>.Swagger;

internal static class OpenApiDocumentation
{
    public const string Description = """
        This API specification describes the interface through which <Full name> (<TenantName>)
        exchanges data over the ZamConnect Government Service Bus.
        """;
}
```

With no full name yet, write `<TenantName>` alone in that sentence.

Do not add `RegisterGatewayEndpoint` or `EServicesShared` (MOH extras). `integrate-shared` adds them, with the `Gateway` section, when the tenant needs the shared e-services surface.

#### Observability

A new tenant gets this four-part baseline, all of it already present in the `Program.cs` above. It is the target for new tenants, not a description of existing ones — most tenants (CEEC, MOH, MOA, APIS among them) don't call `ConfigureOpenTelemetry`, and AdminAPI doesn't call `MapMetrics()`. Don't copy observability lines from a neighbour; re-derive with `grep -L "ConfigureOpenTelemetry" src/Tenants/*/Program.cs`.

| Part | Line | What it gives |
|---|---|---|
| Structured logs | `builder.Host.UseConfiguredSerilog()` + `app.UseBaseLogger()` | Serilog with the repo's enrichers; request logging with the W3C trace id set by the `Activity.ForceDefaultIdFormat` lines |
| Traces + metrics | `builder.ConfigureOpenTelemetry()` | ASP.NET Core and `HttpClient` instrumentation, runtime meters, resource attributes, OTLP export |
| Scrape endpoints | `app.UseHttpMetrics()`, `app.MapMetrics()`, `app.UseOpenTelemetryPrometheusScrapingEndpoint("/metrics/otel")` | prometheus-net HTTP and health-check series on `/metrics`; OTel meters on `/metrics/otel` |
| Liveness | `AddHealthChecks().ForwardToPrometheus()` + `MapHealthChecks("/health/live")` | Served, and exported as a gauge — but the universal chart has probes disabled (`values.tenant.yaml`: `healthCheckEnabled: false`), so nothing in Kubernetes calls it |

**Give the OTel scraper its own path.** On its default path, `UseOpenTelemetryPrometheusScrapingEndpoint()` answers `/metrics` itself before the routed `MapMetrics()` endpoint runs, so `/metrics` shows only OTel output and every prometheus-net series (`UseHttpMetrics`, `ForwardToPrometheus`) becomes unreachable. Keep `"/metrics/otel"`, or drop the line if nothing scrapes OTel meters.

No packages to add: `ConfigureOpenTelemetry` lives in `Internal.Extensions.Extensions.Telemetry` (`src/Core/Internal/Extensions/Extensions/Telemetry/OpenTelemetryExtensions.cs`) and every OpenTelemetry package arrives transitively through the `Internal.csproj` reference the tenant already has.

**Configuration is environment-driven — do not add OTEL keys to `appsettings.json`.** `ConfigureOpenTelemetry` reads three keys through `builder.Configuration[...]`; in practice they arrive as environment variables. The OTLP exporter also honours the standard `OTEL_EXPORTER_OTLP_*` variables (protocol, headers) once the endpoint is set.

| Variable | Unset behaviour |
|---|---|
| `OTEL_SERVICE_NAME` | Falls back to the assembly name, then `zc-tenant`. Set it to `core-<slug>` in the variable group so traces line up with the Kubernetes service name |
| `OTEL_SERVICE_VERSION` | Defaults to `1.0.0` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | **The OTLP exporter is not registered at all.** Logs, traces and metrics stay local and only the Prometheus scrape survives. No error, no warning — a tenant that "has no traces" almost always has this unset |

Nothing in this repo sets those three; they come from the cluster, so name them in the report as a deployment prerequisite alongside the `__Token__` variables.

Logs probably don't reach OTLP even with the endpoint set: `UseConfiguredSerilog` calls `UseSerilog` without `writeToProviders`, which defaults to `false`, so Serilog most likely bypasses the OpenTelemetry logging provider. Traces and metrics are unaffected. Confirm on a running tenant before stating it either way.

#### `appsettings.json`

4-space indent. `RegisterEndpoints` matches `Endpoints:<ClientClassName>` sections against `IRestEndpoint` class names in the assembly; a section with no matching class is inert, yet every `__Token__` in it still becomes a required deploy variable (C4). So scaffold no placeholder client:

- Always `"Endpoints": {}`, whatever `--integrates` says.
- The `Gateway` section (the tenant calling back into the ZamConnect gateway) is written by `integrate-shared` §5, together with the `RegisterGatewayEndpoint` call that binds it, or by `tenant-integration` for an upstream reached through the gateway. Scaffolding it here without that call leaves dead config whose tokens still become required deploy variables.
- An agency client is added by `tenant-integration`, which names the section after the real client class.

```json
{
    "AllowedHosts": "*",
    "Endpoints": {},
    "Serilog": {
        "MinimumLevel": {
            "Default": "Information",
            "Override": {
                "Microsoft": "Warning",
                "System": "Warning",
                "Yarp": "Information"
            }
        },
        "Properties": {
            "ApplicationName": "<tenantname-lowercase>"
        }
    }
}
```

- No `WriteTo` block: `UseConfiguredSerilog` already hard-codes a JSON console sink (`LogConfigurationExtensions.cs`) on top of `ReadFrom.Configuration`, so a `Console` entry in `WriteTo` adds a second console sink and every line is written twice. Existing tenants (CEEC) still carry it — don't copy it.

`appsettings.Development.json` mirrors `appsettings.json`. The later steps add each client section to both files; there, only `BaseUrl` may be real and credentials stay `__Token__` placeholders. Many tenants' Development files commit literal credentials (C7). Never use another tenant's Development file as the template for credential values.

#### `Dockerfile`

Build context is `src/`, so every path is relative to it. Copy the three core csproj files (Internal, Database, Shared) first for restore-layer caching, even when the tenant does not reference `Database`.

```dockerfile
FROM mcr.microsoft.com/dotnet/aspnet:10.0-alpine AS base
WORKDIR /app
ENV ASPNETCORE_HTTP_PORTS=80
EXPOSE 80 9090

FROM mcr.microsoft.com/dotnet/sdk:10.0-alpine AS build
WORKDIR /src
COPY ["Tenants/<TenantName>/<TenantName>.csproj", "Tenants/<TenantName>/"]
COPY ["Core/Internal/Internal.csproj", "Core/Internal/"]
COPY ["Core/Database/Database.csproj", "Core/Database/"]
COPY ["Core/Shared/Shared.csproj", "Core/Shared/"]
RUN dotnet restore "Tenants/<TenantName>/<TenantName>.csproj"

COPY ["Tenants/<TenantName>", "Tenants/<TenantName>/"]
COPY ["Core/Internal/", "Core/Internal/"]
COPY ["Core/Database/", "Core/Database/"]
COPY ["Core/Shared/", "Core/Shared/"]
WORKDIR "/src/Tenants/<TenantName>"
RUN dotnet build "<TenantName>.csproj" -c Release --no-restore

FROM build AS publish
RUN dotnet publish "<TenantName>.csproj" -c Release -o /app/publish --no-build

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "<TenantName>.dll"]
```

Port 80 serves the app and `/metrics`. Nothing binds 9090; `EXPOSE 80 9090` is kept for parity with every tenant Dockerfile.

#### `Properties/launchSettings.json`

```json
{
  "profiles": {
    "<TenantName>": {
      "commandName": "Project",
      "launchBrowser": true,
      "environmentVariables": {
        "ASPNETCORE_ENVIRONMENT": "Development"
      },
      "applicationUrl": "https://localhost:<https>;http://localhost:<http>"
    }
  }
}
```

### 4. Add the Azure pipeline

Create `.azure/tenant.azure-pipelines.<slug>.yaml`. `<slug>` is the lowercase tenant name, and hyphenation of multi-word names is **not consistent** in this repo — `CloudAdmin` -> `cloud-admin`, `ZamData` -> `zam-data` and `ZamMobile` -> `zam-mobile` hyphenate, but `MobileID` -> `mobileid` and `MockData` -> `mockdata` do not. The slug is cosmetic (nothing resolves it), so list the directory first, match the closest neighbour, and hyphenate when in doubt:

```bash
ls .azure/tenant.azure-pipelines.*.yaml
```

Tenant files share one shape:

```yaml
trigger:
  branches:
    include:
      - develop
      - release/*
      - master
  paths:
    include:
      - "/src/Tenants/<TenantName>/*"
      - "/.azure/tenant.azure-pipelines.<slug>.yaml"

extends:
  template: /.azure/tenant.pipeline.yaml
  parameters:
    tenant: <TenantName>
```

`tenant:` is the exact PascalCase folder name — `tenant.pipeline.yaml` uses it for `src/Tenants/${{ parameters.tenant }}/Dockerfile`, the published `appsettings.json` path, and the `GSB.<tenant>.DEV|STG|PROD` variable groups.

Add `buildArguments: "--build-arg PAT=$(DOTGOV_ENGINEERING_NUGET_PAT)"` only if the Dockerfile restores from a private feed (see `tenant.azure-pipelines.zam-mobile.yaml`). Otherwise omit it — it defaults to empty.

The pipeline file alone does not create the build: the `GSB.<TENANT>.<ENV>` variable groups and the ADO pipeline definition pointing at this YAML are set up outside the repo. Say so in the report, and name where each variable the deploy reads comes from:

| Source | Variables |
|---|---|
| Inline in `tenant.pipeline.yaml` | `helmChart`, `helmChartVersion`, `helmVersion`, `dockerId` (per branch) |
| `GSB.COMMON.<ENV>` (exists) | `REPLICAS`, `containerRegistry`, `POOL`, `environment`, `helmRepo`, `helmUsername`, `helmPassword`, `kubeReleaseName` |
| `GSB.<TENANT>.<ENV>` (new, per tenant) | `helmReleaseName`, `helmNamespace`, and one variable per `__Token__` in `appsettings.json` (C4) |

`variables.common.yaml@PipelineTemplates` is used by the gateway pipelines only; tenant pipelines don't load it.

Two consequences worth stating up front:

- **`helmReleaseName` names the Kubernetes service.** The chart deploys `core-$(helmReleaseName)` and sets `apps[0].serviceName` / `containerName` to it. `helmReleaseName` must be the compose slug (step 5, never hyphenated), so the service equals the compose service key from step 5 and the cluster address in step 6, or the gateway route points at nothing.
- **Deployment substitutes tokens with `actionOnMissing: fail`.** Every `__Placeholder__` left in `appsettings.json` must have a matching variable in the group for that environment or the deploy fails outright. Only `appsettings.json` is published as the settings artifact — `appsettings.Development.json` never leaves the repo, so its values are local-only.

### 5. Add the docker-compose service

Append a service to the `## Tenants` block in `src/.dockercompose/docker-compose.yml`, at the end of the tenant list — immediately before the `#region Core` marker that starts `admin-ui`. Service key and image are `core-<slug>`, where `<slug>` is the tenant name lowercased with no separators (`CloudAdmin` -> `core-cloudadmin`, `ZamMobile` -> `core-zammobile`) — note this differs from the pipeline slug of step 4, which may hyphenate.

This slug is the one that matters. `core-<slug>` must match the deployed Kubernetes service `core-$(helmReleaseName)` and the cluster address in step 6; all three are the same string.

Two existing services break the pattern — don't take either as the "closest neighbour": `core-ecounncil` (typo for `ecouncil`) and `test-tenant` (no `core-` prefix, hyphenated).

```yaml
  core-<slug>:
    container_name: core-<slug>.zamconnect
    image: ${DOCKER_REGISTRY-}core-<slug>
    build:
      context: ../
      dockerfile: Tenants/<TenantName>/Dockerfile
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
```

Two-space indent, blank line between services. No `ports:` — tenants are not published to the host; only the gateway, admin apps and infra are. Keep `dockerfile:` at the exact PascalCase folder name.

### 6. Write the gateway config handoff

Create `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` — the scope, cluster and route the gateway needs, as one package the AdminAPI can import. This skill does **not** apply it; the file is the handoff artefact.

Naming follows the live routes (C8):

| Field | Value | Example `TestPluginTenant` |
|---|---|---|
| Route `name` / `routeId` | `t_<slug>` | `t_testplugintenant` |
| Path | `/t/<slug>/{**url}` | `/t/testplugintenant/{**url}` |
| Cluster `name` / `clusterId` | `<TENANT>` — tenant name uppercased | `TESTPLUGINTENANT` |
| Cluster address | `http://core-<slug>` — the compose key (step 5) and `core-$(helmReleaseName)` | `http://core-testplugintenant` |
| `authorizationPolicy` | `Basic` | |
| `metadata.Scope` | `<slug>` | `testplugintenant` |

No `order`. Without `authorizationPolicy` the gateway doesn't authenticate the route; without `metadata.Scope` any authenticated user passes the scope check (`RouteScopeValidationExtension.cs`). Both are required.

~~~~markdown
# <TenantName> Gateway Config

Import with `POST /Import/routes` on the AdminAPI (Admin policy). The body is the JSON below as-is
(`RouteConfigurationPackageDto`). The import creates the `<slug>` scope from `metadata.Scope`, then the
cluster, then the route; an existing route or cluster with the same id is overwritten.

Locally, don't import by hand: `/tenant-audit <TenantName> --only runtime` applies this package to the
local Docker `mongo` only, together with a `test<TenantName>` gateway user.

```json
{
    "clusters": [
        {
            "name": "<TENANT>",
            "configJson": {
                "clusterId": "<TENANT>",
                "destinations": {
                    "Route1": {
                        "address": "http://core-<slug>"
                    }
                }
            }
        }
    ],
    "routes": [
        {
            "name": "t_<slug>",
            "configJson": {
                "routeId": "t_<slug>",
                "match": {
                    "methods": [
                        "GET"
                    ],
                    "path": "/t/<slug>/{**url}"
                },
                "clusterId": "<TENANT>",
                "authorizationPolicy": "Basic",
                "metadata": {
                    "Scope": "<slug>"
                },
                "transforms": [
                    {
                        "PathPattern": "/{**url}"
                    }
                ]
            }
        }
    ]
}
```

Every consumer's gateway user needs the `<slug>` scope, or the gateway answers 403.

Registering by hand through `POST /Routes` instead: create the scope first with `POST /Scopes {"name": "<slug>"}` —
the route validator rejects a scope that doesn't exist.
~~~~

`methods` lists only the verbs the tenant actually exposes. With no modules yet, default to `GET`. `tenant-integration` §6 and `integrate-shared` §6 widen it to every verb the tenant's routes map.

### 7. Add to the solution

```bash
dotnet sln src/ZamConnect.sln add src/Tenants/<TenantName>/<TenantName>.csproj --solution-folder Tenants
```

### 8. Verify

```bash
dotnet build src/Tenants/<TenantName>/<TenantName>.csproj -v q --nologo
```

Must report `0 Error(s)`. Pre-existing `NU1903` and `CARTER1` warnings come from `Core` and are not caused by the new tenant.

Then build the image through the compose service from step 5. `dotnet build` passing says nothing about the Dockerfile: a missing `COPY` for a referenced project, a path-casing mismatch, or a wrong `dockerfile:` path only fails here, on the Linux image build the pipeline also runs.

```bash
docker info >/dev/null 2>&1 && docker compose -f src/.dockercompose/docker-compose.yml build core-<slug>
```

Must exit 0. On failure, fix the Dockerfile or compose entry and re-run; don't report the scaffold as done. If `docker info` fails (Docker not installed or the engine is not running), stop and tell the user, then report the image build and the start check below as `skipped — Docker not available`, never as passed, with the commands to run later. If the Dockerfile declares `ARG PAT` (private feed), pass `--build-arg PAT=<token>` from the user's environment and never echo it.

Then prove the image starts. A clean build can still crash at startup: a missing config section, a DI registration that can't resolve, `MapCarter()` failing on an unconfigured endpoint.

```bash
C="docker compose -f src/.dockercompose/docker-compose.yml"
$C up -d --no-deps core-<slug>
for i in $(seq 1 12); do
  $C exec -T core-<slug> wget -qO- http://localhost/health/live 2>/dev/null && break
  sleep 5
done
$C ps core-<slug> --format '{{.State}} {{.Status}}'
$C logs --no-color --tail 50 core-<slug>
```

The tenant publishes no host port (step 5), so the probe runs inside the container with the busybox `wget` in the Alpine image. It must print `Healthy` within the 60 s loop, and `ps` must still show `running`, not `exited` or `restarting`. If it fails, read the logs for the first exception. Fix the cause, rebuild and re-run. Don't report the scaffold as done while it fails. Only the log lines about the exception go into the report, never config values.

Then remove the container: `$C rm -sf core-<slug>`. The image stays, and `/tenant-audit` Check 9 starts the container again with the gateway.

Then confirm the three registrations, since a tenant that builds but is unregistered fails silently later:

```bash
grep -n "<TenantName>" src/ZamConnect.sln
ls .azure/tenant.azure-pipelines.*.yaml | grep -i "<slug>"
grep -n "Tenants/<TenantName>/Dockerfile" src/.dockercompose/docker-compose.yml
```

And that the observability baseline is intact:

```bash
grep -n "UseConfiguredSerilog\|ConfigureOpenTelemetry\|ForwardToPrometheus\|MapMetrics\|metrics/otel\|health/live" src/Tenants/<TenantName>/Program.cs
```

Six hits, one per line of the template. `metrics/otel` missing means the OTel scraper sits on `/metrics` and hides the prometheus-net series. `ConfigureOpenTelemetry` missing is the one that fails silently — the tenant still builds, serves and reports healthy, it just never appears in the traces.

And that `core-<slug>` is spelled identically in the compose service key, the compose `container_name`, and the `GATEWAY-CONFIG.md` cluster address — and that the package is importable:

```bash
grep -n '"authorizationPolicy": "Basic"\|"Scope": "<slug>"\|"routeId": "t_<slug>"\|"clusterId": "<TENANT>"' src/Tenants/<TenantName>/GATEWAY-CONFIG.md
```

Five hits (`clusterId` appears in the cluster and the route); no `"order"`.

And that the spec-ready baseline is there:

```bash
grep -n "GenerateDocumentationFile" src/Tenants/<TenantName>/<TenantName>.csproj
grep -n "OpenApiInfo\|AddSecurityDefinition\|IncludeXmlComments\|partial class Program" src/Tenants/<TenantName>/Program.cs
```

## State

Write `.claude/zamconnect/<TenantName>.pipeline.json` as the interaction contract describes, creating `.claude/zamconnect/.gitignore` (`*`) with it. Record step 1 as `ran`, its equivalent command, and the intake answers (`style`, `integrates`, `fullName`). Later steps read them from there. Do this even with `--no-pipeline`, so a later `/tenant-pipeline <TenantName>` picks up where this left off. Skip it with `--dry-run`.

## Report

One line per file created, then the solution entry, the build result, the image build result and the container start result (`ok` / `fail` / `skipped`), then the equivalent command (R7). Close by naming what was deliberately left out so the user can ask for it:

- ADO pipeline definition + `GSB.<TENANT>.<ENV>` variable groups — `helmReleaseName` (must be the compose `<slug>`), `helmNamespace`, `OTEL_SERVICE_NAME` (set it to `core-<slug>`), `OTEL_EXPORTER_OTLP_ENDPOINT`, and a variable for every `__Token__` in `appsettings.json`, mirrored in `projects-variables` (C4) — all created outside the repo. `REPLICAS` and the registry/pool/helm-repo variables come from the existing `GSB.COMMON.<ENV>`; `helmChart`, `helmChartVersion`, `helmVersion`, `dockerId` are inline in `tenant.pipeline.yaml`. `values.tenant.yaml` is generic and needs no per-tenant edit; the release is parameterised through `--set` in `tenant.deployment-jobs.yaml`
- Gateway import: `POST /Import/routes` with the package in `GATEWAY-CONFIG.md`, then the `<slug>` scope on every consumer's gateway user
- Business surface: `Modules/`, `Endpoints/`, `Models/`, `Mapper/`
- Test project `src/Tests/<TenantName>.Tests` — required by `AGENTS.md` and `.ai-factory/rules/base.md`; `/tenant-tests <TenantName>` creates it

With `--no-pipeline` (how `tenant-pipeline` runs step 1), the report's last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when the build, the image build or the start check fails.

## Hand-off to the pipeline

The scaffold is step 1 of six. The rest of the chain belongs to `tenant-pipeline`; this skill does not gate it.

| Intake / flag | What happens after the report |
|---|---|
| `Guided` (default) | Invoke `tenant-pipeline` with the `Skill` tool: `<TenantName> --from integration` |
| `Auto` / `--auto` | Invoke `tenant-pipeline`: `<TenantName> --from integration --auto` |
| `Scaffold only` / `--no-pipeline` | Stop after the report, and print `/tenant-pipeline <TenantName>` as the command to continue |

Do not end the turn between the report and the hand-off.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
- Never use another tenant's `appsettings.Development.json` as the template for credential values — many commit literal credentials (C7). A generated Development file keeps `__Token__` placeholders for credentials; only a test `BaseUrl` may be real.
