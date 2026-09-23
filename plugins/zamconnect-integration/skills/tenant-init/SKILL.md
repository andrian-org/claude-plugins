---
name: tenant-init
description: Scaffold a new ZamConnect integration tenant project from the standard tenant boilerplate (Carter + Serilog + OpenTelemetry + Prometheus + health checks, net10.0), wire it into ZamConnect.sln, and verify it builds. Use when the user says "create a new tenant", "add tenant <NAME>", "scaffold integration for <AGENCY>", or types /tenant-init.
argument-hint: "<TenantName> [--controllers] [--full-name \"<name>\"] [--integrates rest,soap,shared,unknown] [--port <https>] [--no-pipeline] [--auto] [--dry-run]"
allowed-tools: Read Write Glob Grep Bash(mkdir *) Bash(cat *) Bash(dotnet *) Bash(find *) Bash(grep *) Bash(ls *) AskUserQuestion Skill
disable-model-invocation: false
---

# Create ZamConnect Tenant

Scaffold a new tenant under `src/Tenants/<TenantName>/`. Produce the boilerplate only — **no Modules, Models, Controllers, Endpoints, or Mappers** unless the user asks for them in the same request. The boilerplate is spec-ready from the start (step 3), so the integration never has to retrofit it.

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Read it first.

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

If `<TenantName>` is missing, ask for it in plain text; there's nothing to offer as options. Everything else goes through step 1a.

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
```

Stop and ask if either hits.

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

Choose an unused consecutive pair (https, http). Repo convention is a high 5-digit pair, e.g. `53390;53391`.

### 2a. Review before writing

Work out the pipeline slug (step 4) and `core-<slug>` (step 5) now, so the review can show them. Then make one R6 review call. The question text is the plan:

```
Scaffold PQPS (Carter, spec-ready):
  src/Tenants/PQPS/            csproj, Program.cs, appsettings x2, Dockerfile, launchSettings, Swagger/, GATEWAY-CONFIG.md
  .azure/tenant.azure-pipelines.pqps.yaml
  src/.dockercompose/docker-compose.yml   + core-pqps
  src/ZamConnect.sln                      + Tenants/PQPS
Dev ports 53390 / 53391 · gateway route /t/pqps · title "Plant Quarantine and Phytosanitary Service (PQPS)"
Command: /tenant-init PQPS --full-name "Plant Quarantine and Phytosanitary Service" --integrates soap --port 53390
```

Options: `Apply (Recommended)` · `Adjust` · `Cancel`. `Adjust` asks one `multiSelect` — `Dev ports`, `Pipeline slug`, `Style`, `Full name` — and re-asks only the ones picked. Ports and slug are the values most often overridden: offer the next two free pairs and the hyphenated / unhyphenated slug as options, never "type it in Other".

With `--dry-run`, print the plan and stop here. With `--auto`, skip the call and apply.

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

#### `Program.cs` (Carter style)

```csharp
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using <TenantName>.Swagger;
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
app.UseOpenTelemetryPrometheusScrapingEndpoint();

app.Run();

public partial class Program;
```

`Title` is `"<Full name> (<TenantName>)"` when the full name is known. When it's `pending` or the code was chosen, write `"<TenantName>"`; step 2 or the developer replaces it later. `public partial class Program;` is there so `tenant-tests` can bind `WebApplicationFactory<Program>` without editing the tenant later.

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

Do not add `RegisterGatewayEndpoint` or `EServicesShared` (MOH extras) unless the integration needs the shared e-services surface.

#### Observability

Every tenant gets the same four-part baseline, all of it already present in the `Program.cs` above. `src/Tenants/ZamData/Program.cs` and `src/Admin/AdminAPI/Program.cs` are the canonical shapes — read them if anything below is unclear.

| Part | Line | What it gives |
|---|---|---|
| Structured logs | `builder.Host.UseConfiguredSerilog()` + `app.UseBaseLogger()` | Serilog with the repo's enrichers; request logging with the W3C trace id set by the `Activity.ForceDefaultIdFormat` lines |
| Traces + metrics | `builder.ConfigureOpenTelemetry()` | ASP.NET Core and `HttpClient` instrumentation, runtime meters, resource attributes, OTLP export |
| Scrape endpoints | `app.UseHttpMetrics()`, `app.MapMetrics()`, `app.UseOpenTelemetryPrometheusScrapingEndpoint()` | prometheus-net HTTP metrics on `/metrics` plus the OTEL Prometheus exporter |
| Liveness | `AddHealthChecks().ForwardToPrometheus()` + `MapHealthChecks("/health/live")` | The probe the Helm chart calls, with its result exported as a gauge |

No packages to add: `ConfigureOpenTelemetry` lives in `Internal.Extensions.Extensions.Telemetry` (`src/Core/Internal/Extensions/Extensions/Telemetry/OpenTelemetryExtensions.cs`) and every OpenTelemetry package arrives transitively through the `Internal.csproj` reference the tenant already has.

**Configuration is environment-driven — do not add OTEL keys to `appsettings.json`.** `ConfigureOpenTelemetry` reads three variables and nothing else:

| Variable | Unset behaviour |
|---|---|
| `OTEL_SERVICE_NAME` | Falls back to the assembly name, then `zc-tenant`. Set it to `core-<slug>` in the variable group so traces line up with the Kubernetes service name |
| `OTEL_SERVICE_VERSION` | Defaults to `1.0.0` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | **The OTLP exporter is not registered at all.** Logs, traces and metrics stay local and only the Prometheus scrape survives. No error, no warning — a tenant that "has no traces" almost always has this unset |

Nothing in this repo sets those three; they come from the cluster, so name them in the report as a deployment prerequisite alongside the `__Token__` variables.

One caveat: `MapMetrics()` claims `/metrics` as a routed endpoint, so the OTEL scraping middleware on its default path is shadowed by it. That matches ZamData and AdminAPI and is what the existing dashboards scrape — keep it. Only if you want the OTEL-native metric set exposed separately, give it its own path: `app.UseOpenTelemetryPrometheusScrapingEndpoint("/metrics/otel")`.

#### `appsettings.json`

4-space indent. `RegisterEndpoints` matches `Endpoints:<ClientClassName>` sections against `IRestEndpoint` class names in the assembly; keep the section even with no client class yet so the integration has a named slot. Secrets stay as `__Placeholder__` tokens replaced at deploy time.

```json
{
    "AllowedHosts": "*",
    "Endpoints": {
        "ZamConnect": {
            "AuthenticationScheme": "Basic",
            "BaseUrl": "__Endpoints.APIGATEWAY.BaseUrl__",
            "Username": "__Credentials.<TenantName>Tenant.Username__",
            "Password": "__Credentials.<TenantName>Tenant.Password__"
        }
    },
    "Serilog": {
        "MinimumLevel": {
            "Default": "Information",
            "Override": {
                "Microsoft": "Warning",
                "System": "Warning",
                "Yarp": "Information"
            }
        },
        "WriteTo": [
            {
                "Name": "Console"
            }
        ],
        "Properties": {
            "ApplicationName": "<tenantname-lowercase>"
        }
    }
}
```

`appsettings.Development.json` is the same file with `BaseUrl` set to `https://api.test.gsb.gov.zm/`.

Never commit a real username or password — leave the `__Credentials.*__` tokens in both files.

#### `Dockerfile`

Build context is `src/`, so every path is relative to it. Copy the four core csproj files first for restore-layer caching, even when the tenant does not reference `Database`.

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

Port 80 serves the app, 9090 is the Prometheus scrape port.

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

Every tenant file is the same 15 lines:

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

The pipeline file alone does not create the build: the `GSB.<TENANT>.<ENV>` variable groups and the ADO pipeline definition pointing at this YAML are set up outside the repo. Say so in the report, and name what those groups must supply — `tenant.deployment-jobs.yaml` reads `helmReleaseName`, `helmNamespace`, `helmChart`, `helmChartVersion`, `REPLICAS`, `dockerId`, plus one variable per `__Token__` in `appsettings.json`.

Two consequences worth stating up front:

- **`helmReleaseName` names the Kubernetes service.** The chart deploys `core-$(helmReleaseName)` and sets `apps[0].serviceName` / `containerName` to it. That value must equal the compose service key from step 5 and the cluster address in step 6, or the gateway route points at nothing.
- **Deployment substitutes tokens with `actionOnMissing: fail`.** Every `__Placeholder__` left in `appsettings.json` must have a matching variable in the group for that environment or the deploy fails outright. Only `appsettings.json` is published as the settings artifact — `appsettings.Development.json` never leaves the repo, so its values are local-only.

### 5. Add the docker-compose service

Append a service to the `## Tenants` block in `src/.dockercompose/docker-compose.yml`, at the end of the tenant list — immediately before the `#region Core` marker that starts `admin-ui`. Service key and image are `core-<slug>`, where `<slug>` is the tenant name lowercased with no separators (`CloudAdmin` -> `core-cloudadmin`, `ZamMobile` -> `core-zammobile`) — note this differs from the pipeline slug of step 4, which may hyphenate.

This slug is the one that matters. `core-<slug>` must match the deployed Kubernetes service `core-$(helmReleaseName)` and the cluster address in step 6; all three are the same string.

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

Create `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` — the YARP scope, cluster and route the gateway admin must register. These are **not** applied by this skill; the file is the handoff artefact.

Naming:

- **Scope** — tenant name lowercased, no separators (`TestPluginTenant` -> `testplugintenant`). Same as the compose `<slug>`.
- **Cluster address** — `http://core-<slug>`, matching both the docker-compose service key from step 5 and the deployed service `core-$(helmReleaseName)`.
- **`clusterId` / `routeId`** — the scope value.

~~~~markdown
# <TenantName> Gateway Config

## Scope

```
<scope>
```

## Cluster

```json
{
    "clusterId": "<scope>",
    "destinations": {
        "Route1": {
            "address": "http://core-<slug>"
        }
    }
}
```

## Route

```json
{
    "routeId": "<scope>",
    "match": {
        "methods": [
            "GET"
        ],
        "path": "/t/<scope>/{**url}"
    },
    "order": 1,
    "clusterId": "<scope>",
    "transforms": [
        {
            "PathPattern": "/{**url}"
        }
    ]
}
```
~~~~

`methods` lists only the verbs the tenant actually exposes; with no modules yet default to `GET` and tell the user to widen it when the business surface lands.

### 7. Add to the solution

```bash
dotnet sln src/ZamConnect.sln add src/Tenants/<TenantName>/<TenantName>.csproj --solution-folder Tenants
```

### 8. Verify

```bash
dotnet build src/Tenants/<TenantName>/<TenantName>.csproj -v q --nologo
```

Must report `0 Error(s)`. Pre-existing `NU1903` and `CARTER1` warnings come from `Core` and are not caused by the new tenant.

Then confirm the three registrations, since a tenant that builds but is unregistered fails silently later:

```bash
grep -n "<TenantName>" src/ZamConnect.sln
ls .azure/tenant.azure-pipelines.*.yaml | grep -i "<slug>"
grep -n "Tenants/<TenantName>/Dockerfile" src/.dockercompose/docker-compose.yml
```

And that the observability baseline is intact:

```bash
grep -n "UseConfiguredSerilog\|ConfigureOpenTelemetry\|ForwardToPrometheus\|MapMetrics\|health/live" src/Tenants/<TenantName>/Program.cs
```

Five hits. `ConfigureOpenTelemetry` missing is the one that fails silently — the tenant still builds, serves and reports healthy, it just never appears in the traces.

And that `core-<slug>` is spelled identically in the compose service key, the compose `container_name`, and the `GATEWAY-CONFIG.md` cluster address.

And that the spec-ready baseline is there:

```bash
grep -n "GenerateDocumentationFile" src/Tenants/<TenantName>/<TenantName>.csproj
grep -n "OpenApiInfo\|AddSecurityDefinition\|IncludeXmlComments\|partial class Program" src/Tenants/<TenantName>/Program.cs
```

## State

Write `.claude/zamconnect/<TenantName>.pipeline.json` as the interaction contract describes, creating `.claude/zamconnect/.gitignore` (`*`) with it. Record step 1 as `ran`, its equivalent command, and the intake answers (`style`, `integrates`, `fullName`). Later steps read them from there. Do this even with `--no-pipeline`, so a later `/tenant-pipeline <TenantName>` picks up where this left off. Skip it with `--dry-run`.

## Report

One line per file created, then the solution entry and the build result, then the equivalent command (R7). Close by naming what was deliberately left out so the user can ask for it:

- ADO pipeline definition + `GSB.<TENANT>.<ENV>` variable groups, including `helmReleaseName` (must be `<slug>`), `OTEL_SERVICE_NAME` (set it to `core-<slug>`) and `OTEL_EXPORTER_OTLP_ENDPOINT`, and a variable for every `__Token__` in `appsettings.json` — all created outside the repo. `values.tenant.yaml` is generic and needs no per-tenant edit; the release is parameterised entirely through `--set` in `tenant.deployment-jobs.yaml`
- Gateway scope/cluster/route registration in the gateway admin (values generated in `GATEWAY-CONFIG.md`)
- Business surface: `Modules/`, `Endpoints/`, `Models/`, `Mapper/`

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
