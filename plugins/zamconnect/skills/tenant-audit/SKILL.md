---
name: tenant-audit
description: Read-only drift audit for ZamConnect tenants. Checks that a tenant is registered everywhere it must be (solution, Azure pipeline, docker-compose), that its slug is spelled identically across compose, Helm and the gateway route, that every `RestEndpoint` client has a matching `Endpoints:<Name>` configuration section in both appsettings files, that no real credential escaped a `__Token__` placeholder, and that its docs, Postman collection and test project exist. Use when the user says "audit <Tenant>", "is <Tenant> wired up correctly", "check tenant drift", "what's missing for <Tenant>", "why is my endpoint not configured", or types /tenant-audit.
argument-hint: "[<TenantName>|--all] [--only registration|slugs|config|secrets|spec|tests|docs] [--fix]"
allowed-tools: Read Glob Grep Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(git *) Edit Write
disable-model-invocation: false
---

# ZamConnect Tenant Audit

A tenant can build cleanly and still be broken: unregistered in the pipeline, deployed under a name the gateway route does not resolve, or running with an upstream client that silently has no `HttpClient`. None of that fails a build. This skill finds it.

Read-only by default. `--fix` permits edits, and only for the checks marked fixable below.

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`).

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Audit one tenant |
| `--all` | Audit every tenant under `src/Tenants/`. Default when no tenant is given |
| `--only <check>` | Run only these checks; repeatable |
| `--fix` | Apply the fixable repairs instead of only reporting them |

Folders with no `.csproj` (`Certificates`, `DotGovDocs`, `MOHAIS`, `PO`, `PluginTest`, `TestConsoleTenant`, `TestPluginTenant`) are not tenants. Skip them silently — they are placeholders, not drift.

## Check 1 — Registration

A tenant must appear in three places. Missing any one is real drift, not a style issue.

```bash
grep -c "Tenants.<TenantName>.<TenantName>\.csproj" src/ZamConnect.sln
ls .azure/tenant.azure-pipelines.*.yaml
grep -n "Tenants/<TenantName>/Dockerfile" src/.dockercompose/docker-compose.yml
```

| Missing | Consequence |
|---|---|
| Solution entry | Not built by a solution-wide `dotnet build`; invisible in the IDE |
| `.azure/tenant.azure-pipelines.<slug>.yaml` | **Never deployed.** No CI, no image, no release |
| docker-compose service | Cannot be run locally alongside the gateway |

The pipeline slug is lowercase but hyphenation is inconsistent (`cloud-admin`, `zam-data`, `zam-mobile` hyphenate; `mobileid`, `mockdata` do not), so match by content rather than filename:

```bash
grep -l "tenant: <TenantName>$" .azure/tenant.azure-pipelines.*.yaml
```

Known at time of writing: `CloudAdmin`, `ZamData` and `ZamMobile` have compose services but **no pipeline file**. Re-derive rather than trusting that list.

Fixable with `--fix`: all three. Generate the pipeline and compose entries exactly as `tenant-init` §4 and §5 specify.

## Check 2 — Slug consistency

One string has to be spelled identically in four places, or the gateway routes to nothing:

| Place | Form |
|---|---|
| docker-compose service key | `core-<slug>` |
| docker-compose `container_name` | `core-<slug>.zamconnect` |
| Helm release / k8s service | `core-$(helmReleaseName)` — `helmReleaseName` lives in the `GSB.<TENANT>.<ENV>` variable group, outside the repo |
| Gateway YARP cluster address | `http://core-<slug>` (see the tenant's `GATEWAY-CONFIG.md`) |

`<slug>` is the tenant name lowercased with no separators. Report the compose value and state that `helmReleaseName` must equal it — the audit cannot read the variable group, so this is a flag for the user, not a verdict.

The compose `dockerfile:` path must keep the tenant folder's exact casing. `Tenants/egp/Dockerfile` is in the file today and works only because the build host is case-insensitive; it breaks on Linux.

## Check 3 — Endpoint configuration

`RegisterEndpoints` (`src/Core/Internal/Extensions/Extensions/Rest/RestExtensions.cs`) scans the assembly for public classes implementing `IRestEndpoint` and binds `Endpoints:<TypeName>` for each. **A class with no matching section logs `Endpoint {Name} is not configured` and gets no `HttpClient`** — a warning at startup and a null-reference or unconfigured call at runtime. Nothing fails the build.

```bash
grep -rhoE "class\s+[A-Za-z0-9_]+\s*(\([^)]*\))?\s*:\s*(RestEndpoint|IRestEndpoint)\b" \
  src/Tenants/<TenantName> --include=*.cs | sed -E 's/class\s+([A-Za-z0-9_]+).*/\1/' | sort -u
```

For each class name, require a section in **both** `appsettings.json` and `appsettings.Development.json`.

Two things to get right, or the check produces noise:

- The lookup is `config.GetSection($"Endpoints:{type.Name}")`, and `IConfiguration` keys are **case-insensitive** — `MFL.Endpoints.Mfl` against a section named `"MFL"` is fine. Compare case-insensitively.
- `: RestEndpointOptions` is a different base type. Anchor the match on `RestEndpoint\b` or every `*ServiceOptions` class reports as a false positive.

Known real findings: `GOVZM.NdrElastic`, `GOVZM.ZamPointEndpoint`, `USSD.GsbEndpoint` have no section in their tenant's `appsettings.json`.

Also flag the reverse — an `Endpoints:<Name>` section with no class of that name is dead configuration, usually a rename that left the old key behind.

Not fixable automatically: the section needs a `BaseUrl` and credentials only the user knows. Report the exact section to add.

## Check 4 — Secrets

Deployment substitutes tokens with `actionOnMissing: fail`, so a placeholder that never got a variable breaks the release, and a literal credential that got committed is a disclosure.

In `appsettings.json` (the file published as the settings artifact):

- Every `Username`, `Password`, `ApiKey`, `AuthHeaderValue`, `PrivateKey`, `CertificateThumbprint` and `ClientSecret` must be a `__Token__` placeholder, never a literal
- `BaseUrl` is a placeholder too, except where a value is genuinely environment-independent

In `appsettings.Development.json` a real test `BaseUrl` is expected and fine; credentials still must not be literals.

```bash
grep -nE '"(Username|Password|ApiKey|AuthHeaderValue|PrivateKey|ClientSecret|CertificateThumbprint)"[[:space:]]*:[[:space:]]*"[^_]' \
  src/Tenants/<TenantName>/appsettings*.json
```

`[^_]` rather than a negative lookahead — this repo's `grep` is not PCRE by default. It also matches a value that merely starts with one underscore, which a real token never does.

No tenant matches today, so any hit is new. Treat it as a finding regardless of whether the value looks real. If one is found, check whether it is already in git history — `git log -p --all -- <file>` — and say so, because removing it from the working tree does not remove it from the repository.

## Check 5 — API spec readiness

`/api-spec-sync <Tenant>` needs metadata that has to already be in the code. Only `src/Tenants/APIS` currently satisfies all of it.

- `<GenerateDocumentationFile>true</GenerateDocumentationFile>` and `<NoWarn>$(NoWarn);CS1591</NoWarn>` in the csproj
- `AddSwaggerGen` with a populated `OpenApiInfo` and `IncludeXmlComments` in `Program.cs`
- `OpenApiInfo.Title` in the form `"{full descriptive name} ({TENANT})"`
- A `Swagger/` folder holding the narrative content and any `IOperationFilter` / `ISchemaFilter`
- `.WithTags(...)` on every route — untagged operations collapse into one Postman folder
- `.WithSummary(...)`, `.WithDescription(...)`, `.Produces<T>(...)` on every route
- `///` comments on every public DTO property, with no `<see cref="..."/>` (Swashbuckle emits the raw type name as literal text)

Report as a readiness percentage per tenant, not pass/fail — most tenants meet none of it and that is the current baseline, not a regression.

## Check 6 — Tests

```bash
ls src/Tests/<TenantName>.Tests 2>/dev/null
tail -5 src/Tenants/<TenantName>/Program.cs | grep -c "partial class Program"
```

20 of 58 tenants have a test project. Report presence, and when one exists, that the tenant ends with `public partial class Program;` — without it the factory does not compile. Offer `/tenant-tests <TenantName>` when it is missing.

## Check 7 — Docs and collateral

| Artefact | Path |
|---|---|
| Postman collection | `postman collections/<TenantName>.postman_collection.json` |
| Gateway handoff | `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` |
| Agency register row | `docs/zamconnect-agency-tenants.md` |

The agency register is hand-generated (its header carries the date it was derived) and goes stale as tenants are added. Flag a tenant that is absent from it, and flag the document itself when its stated generation date is older than the newest commit under `src/Tenants/`:

```bash
head -5 docs/zamconnect-agency-tenants.md
git log -1 --format=%ad --date=short -- src/Tenants
```

Internal platform tenants (`CloudAdmin`, `GOVZM`, `MobileID`, `ZamMobile`, `ZamData`, `NIR`, `NLR`, `NDR`, `NDW`, `NDP`) are excluded from that table by design — do not report them as missing rows.

## Report

Lead with the findings, not the checks that passed.

For one tenant: a table of check, status (`ok` / `warn` / `fail`), and the specific finding. Then, for each `fail`, the exact file and the exact line or JSON block that fixes it.

For `--all`: one row per tenant with a column per check, then the failures grouped by check — the same root cause usually spans several tenants and is worth fixing in one pass. Do not print per-tenant detail for tenants that pass everything.

Severity, highest first:

1. Committed literal credential (check 4)
2. No pipeline file — never deployed (check 1)
3. Unconfigured `IRestEndpoint` class — silently broken at runtime (check 3)
4. Slug mismatch — gateway routes to nothing (check 2)
5. Everything else

Close by naming what the audit cannot see: the `GSB.<TENANT>.<ENV>` variable-group contents, the ADO pipeline definitions, and the live YARP scope/cluster/route registrations in the gateway admin.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.
