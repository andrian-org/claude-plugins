# zamconnect-plugin

Tenant tooling for the [ZamConnect](https://dev.azure.com/zambiazigs/zambiazigs/_git/ZamConnect)
gateway: scaffolding, integration, drift auditing, tests, and the contractual delivery documents.

Run every skill from the ZamConnect repository root — the directory holding `src/ZamConnect.sln`.

## Install

```
/plugin marketplace add https://dev.azure.com/zambiazigs/zambiazigs/_git/claude-marketplace
/plugin install zamconnect-plugin@dotgov
```

Authentication reuses your existing Azure DevOps git credential; no extra PAT is needed if you
already clone ZamConnect.

## Skills

| Skill | What it does |
|---|---|
| `/zc-create-tenant <Tenant>` | Scaffolds `src/Tenants/<Tenant>/` from the standard boilerplate (Carter + Serilog + OpenTelemetry + Prometheus + health checks), wires it into `ZamConnect.sln`, and verifies it builds. Boilerplate only — no modules, models or mappers. Then drives the rest of the chain below interactively, gating each step |
| `/zc-tenant-integration <Tenant>` | Builds the integration surface of an existing tenant: the upstream `RestEndpoint`/`SoapEndpoint` client, models, mappers, and the routes the tenant exposes. Takes a Postman collection, OpenAPI spec, REST base URL, WSDL or prose API docs as the source |
| `/zc-integrate-shared [<Tenant>]` | Exposes shared e-Services (NIR, NBR/PACRA, DOC, SRS, ZDI, NLR, ZDA, NAIR, ZRA, MOH) on a tenant by wiring `EServicesShared` through the gateway, driven by an interactive endpoint menu |
| `/zc-tenant-audit [<Tenant>\|--all]` | Read-only drift audit: registration in solution/pipeline/compose, slug consistency across compose/Helm/gateway, `Endpoints:<Name>` config for every client, leaked credentials, and presence of docs, Postman collection and tests. `--fix` repairs the fixable ones |
| `/zc-tenant-tests <Tenant>` | Scaffolds `src/Tests/<Tenant>.Tests/` with a `WebApplicationFactory`, a recording mock upstream handler, and endpoint tests over HTTP. `--live` adds an `[Explicit]` staging fixture |
| `/zc-tenant-docs <Tenant>` | Generates the delivery package — OpenAPI JSON, the (c)/(p)/(t) Word API Specifications and the Postman collection — into `src/Tenants/<Tenant>/Deliverables/`. Documents only; never modifies tenant code |

## Agents

| Agent | Use |
|---|---|
| `zc-tenant-docs-builder` | Runs the full `zc-tenant-docs` package build for a named tenant in its own context, with every gate passing. Write-restricted to `Deliverables/` |

## Prerequisites

Only `/zc-tenant-docs` and `zc-tenant-docs-builder` need more than the .NET SDK:

- **.NET 10 SDK** — all skills (`dotnet build`, `dotnet tool run swagger`)
- **Python 3.9+** with `python-docx` — the document renderers under `skills/zc-tenant-docs/scripts/`
- **Node.js** — `npx openapi-to-postmanv2`, invoked by `openapi_to_postman.ps1`
- **Windows PowerShell** — the Postman conversion step

```
pip install python-docx
```

## Order of execution for a new tenant

Run the skills in this order. Each step assumes the previous one has completed.

| # | Skill | Why it sits here |
|---|---|---|
| 1 | `/zc-create-tenant <Tenant>` | Nothing else can run until `src/Tenants/<Tenant>/` exists and builds |
| 2 | `/zc-tenant-integration <Tenant>` | Needs the scaffold; produces the upstream client and the exposed routes |
| 3 | `/zc-integrate-shared <Tenant>` | **Optional** — only when the tenant also republishes shared e-Services (NIR, PACRA, ZRA, …) |
| 4 | `/zc-tenant-tests <Tenant>` | Fixtures are generated from the routes that exist after steps 2–3 |
| 5 | `/zc-tenant-audit <Tenant>` | Catches what a green build hides: pipeline/compose registration, slug mismatches, missing `Endpoints:<Name>` config, leaked credentials |
| 6 | `/zc-tenant-docs <Tenant>` | **Last.** The deliverables are generated from the final API surface; running it earlier ships a stale specification |

```
/zc-create-tenant PQPS
/zc-tenant-integration PQPS --source <wsdl-or-openapi-url>
/zc-integrate-shared PQPS            # only if shared e-Services are needed
/zc-tenant-tests PQPS
/zc-tenant-audit PQPS
/zc-tenant-docs PQPS --route /t/pqps --version 1.0
```

### Interactive mode

`/zc-create-tenant` drives this chain itself. After the scaffold it asks before each remaining
step — **Proceed** (run the skill now), **Skip** (leave it, continue) or **Stop** (end the chain) —
and closes with a summary of what ran plus the commands to resume anything left. Answering a gate
with free text instead of an option passes it to that step (a `--source` URL, a route override).

Step 3 defaults to Skip. Steps 4 and 6 are offered only when step 2 or 3 actually ran — there is
nothing to test or document on a bare scaffold.

- `--no-pipeline` — stop after the scaffold, as before
- `--auto` — run steps 2, 4, 5 and 6 with no gates

Notes:

- Steps 2 and 3 are independent of each other — run either or both, in any order, as long as both precede step 4.
- Re-running an earlier step (a new endpoint, a changed DTO) invalidates steps 4–6; re-run tests, audit and docs after it.

## Contributing

The plugin lives in the `claude-marketplace` repository. Bump `version` in
`.claude-plugin/plugin.json` with every change (SemVer), open a PR against `main`, and let the
validation pipeline run. Consumers pick the change up with `/plugin marketplace update dotgov`.
