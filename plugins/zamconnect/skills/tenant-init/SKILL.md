---
name: tenant-init
description: Scaffold a new ZamConnect integration tenant project from the standard tenant boilerplate (Carter + Serilog + OpenTelemetry + Prometheus + health checks, net10.0), wire it into ZamConnect.sln, and verify it builds. Use when the user says "create a new tenant", "add tenant <NAME>", "scaffold integration for <AGENCY>", or types /tenant-init.
argument-hint: "<TenantName> [--controllers] [--port <https>] [--no-pipeline] [--auto]"
allowed-tools: Read Write Glob Grep Bash(mkdir *) Bash(cat *) Bash(dotnet *) Bash(find *) Bash(grep *) Bash(ls *) AskUserQuestion Skill
disable-model-invocation: false
---

# Create ZamConnect Tenant

Scaffold a new tenant under `src/Tenants/<TenantName>/`. Produce the boilerplate only — **no Modules, Models, Controllers, Endpoints, or Mappers** unless the user asks for them in the same request.

## Inputs

| Input | Required | Default |
|---|---|---|
| `<TenantName>` | yes | — PascalCase; matches folder, csproj, assembly, namespace root |
| Style | no | `carter` (minimal API modules). `--controllers` selects the MVC variant |
| Dev ports | no | Next free pair from the scan in step 2 |
| Pipeline | no | On. `--no-pipeline` stops after the scaffold; `--auto` runs the whole chain without gates |

Ask only if `<TenantName>` is missing. Everything else takes the default.

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

### 2. Pick free dev ports

```bash
grep -h applicationUrl src/Tenants/*/Properties/launchSettings.json | grep -o "[0-9][0-9][0-9][0-9][0-9]" | sort -n | uniq
```

Choose an unused consecutive pair (https, http). Repo convention is a high 5-digit pair, e.g. `53390;53391`.

### 3. Create the files

`src/Tenants/<TenantName>/` with exactly:

```
<TenantName>.csproj
Program.cs
appsettings.json
appsettings.Development.json
Dockerfile
Properties/launchSettings.json
GATEWAY-CONFIG.md
```

#### `<TenantName>.csproj`

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">

  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <DockerDefaultTargetOS>Linux</DockerDefaultTargetOS>
    <DockerfileContext>..\..</DockerfileContext>
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
using System.Diagnostics;
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
if (builder.Environment.IsDevelopment()) builder.Services.AddSwaggerGen();

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
```

For `--controllers`, follow `src/Tenants/MOA/Program.cs`: swap `AddCarter`/`MapCarter` for `AddControllers`/`MapControllers`, and add `AddHttpClient()`, `AddHttpContextAccessor()`, `UseRouting()`, `AddSwaggerGen(o => o.EnableAnnotations())`. The observability lines below are the same either way.

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

## Report

One line per file created, then the solution entry and the build result. Close by naming what was deliberately left out so the user can ask for it:

- ADO pipeline definition + `GSB.<TENANT>.<ENV>` variable groups, including `helmReleaseName` (must be `<slug>`), `OTEL_SERVICE_NAME` (set it to `core-<slug>`) and `OTEL_EXPORTER_OTLP_ENDPOINT`, and a variable for every `__Token__` in `appsettings.json` — all created outside the repo. `values.tenant.yaml` is generic and needs no per-tenant edit; the release is parameterised entirely through `--set` in `tenant.deployment-jobs.yaml`
- Gateway scope/cluster/route registration in the gateway admin (values generated in `GATEWAY-CONFIG.md`)
- Business surface: `Modules/`, `Endpoints/`, `Models/`, `Mapper/`

## Pipeline

The scaffold is step 1 of six. Unless `--no-pipeline` was passed, do **not** end the turn after the report — walk the rest of the chain, asking the developer at every boundary.

| # | Skill | Arguments | Gate condition |
|---|---|---|---|
| 2 | `tenant-integration` | `<TenantName> [--source ...] [--expose ...]` | always offered |
| 3 | `integrate-shared` | `<TenantName>` | always offered, **defaults to Skip** — only tenants republishing shared e-Services need it |
| 4 | `tenant-tests` | `<TenantName>` | offered only if step 2 or step 3 ran; otherwise skip silently — there are no routes to test |
| 5 | `tenant-audit` | `<TenantName>` | always offered |
| 6 | `tenant-deliverables` | `<TenantName> --route /t/<slug>` | offered only if step 2 or step 3 ran; a docs package for a scaffold with no routes is an empty deliverable |

### The gate

Before each step, one `AskUserQuestion` call — never a plain-text question, and never two steps in one call. Header `Step <n>`, and the question names what the step will do to the repo:

```
Step 2 of 6 — /tenant-integration PQPS. Build the upstream client, models, mappers
and exposed routes. Proceed?
```

Exactly three options, in this order:

| Option | Meaning | What you do |
|---|---|---|
| `Proceed` | run it now | invoke the skill via the `Skill` tool with the arguments from the table, let it finish, then gate the next step |
| `Skip` | leave this step undone, continue the chain | record it as skipped and gate the next step |
| `Stop` | end the pipeline here | stop immediately; do not gate any further step |

Keep this order in every gate — `Proceed` first, `Skip` second, `Stop` third — regardless of which one is recommended. Put `(Recommended)` on `Proceed` for steps 2, 4, 5 and 6, and on `Skip` for step 3; the label moves, the order does not.

The developer can answer with their own text instead of picking an option. Treat it as instructions for that step — a source URL, a route override, "run it but only for the REST endpoints" — apply it, then run the step. Do not re-gate what they already answered.

### Running a step

- Invoke the skill with the `Skill` tool. Do not reimplement it inline, and do not paste its instructions into the conversation.
- Step 2 with no `--source`: ask for the source in the same `AskUserQuestion` gate (a free-text answer carries it) rather than starting the skill and having it ask again.
- Step 6's `--route` is the gateway route already written into `GATEWAY-CONFIG.md` — `/t/<slug>`. Pass it; do not make the developer retype it.
- If a step fails, stop the pipeline and report the failure. Do not silently continue to the next gate.

### Closing

End with the chain as it actually ran — one line per step, `ran` / `skipped` / `not reached` — and, when anything is left, the exact commands to resume:

```
1 /tenant-init PQPS        ran
2 /tenant-integration PQPS   ran
3 /integrate-shared PQPS     skipped
4 /tenant-tests PQPS         ran
5 /tenant-audit PQPS         stopped here

Resume with:
  /tenant-audit PQPS
  /tenant-deliverables PQPS --route /t/pqps
```

With `--auto`, run steps 2, 4, 5 and 6 without gating (3 stays skipped unless the request named shared e-Services), and still print the chain summary.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
