---
name: tenant-audit
description: Read-only drift audit for ZamConnect tenants. Checks that a tenant is registered everywhere it must be (solution, Azure pipeline, docker-compose), that its slug is spelled identically across compose, Helm and the gateway route, that every REST, SOAP and Gateway client has its `Endpoints:<Name>` / `SoapEndpoints:<Name>` / `Endpoints:Gateway` section in both appsettings files, that `appsettings.json` holds no literal credential (and reports the committed Development-credential baseline), that its API-spec metadata, docs, Postman collection and test project exist, and that no migration regression (.NET version, Newtonsoft, AutoMapper, Dockerfile) crept back in. Use when the user says "audit <Tenant>", "is <Tenant> wired up correctly", "check tenant drift", "what's missing for <Tenant>", "why is my endpoint not configured", or types /tenant-audit.
argument-hint: "[<TenantName>|--all] [--only registration|slugs|config|secrets|spec|tests|docs|guards] [--fix [registration]] [--report-only] [--auto]"
allowed-tools: Read Glob Grep Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(git *) Bash(awk *) Bash(sort *) Bash(wc *) Bash(head *) Bash(tail *) Bash(dotnet *) Edit Write AskUserQuestion
disable-model-invocation: false
---

# ZamConnect Tenant Audit

A tenant can build cleanly and still be broken: unregistered in the pipeline, deployed under a name the gateway route does not resolve, or running with an upstream client that was never registered. None of that fails a build. This skill finds it.

Read-only by default. Nothing is edited unless the developer picks it in the fix question (see Fixing) or passes `--fix` / `--auto`, and even then only the checks marked fixable below. Questions follow `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Repo facts (secrets baseline, token naming, key casing, live routes) are in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`, cited below by section id (C1–C8).

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`). Run every command in **Bash** (Git Bash on Windows), not the Grep tool: the patterns below are written to survive CRLF files, which ripgrep/WSL `$` anchors do not.

Never state a count or a "known finding" from memory or from this file. Re-derive everything on each run.

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Audit one tenant |
| `--all` | Audit every tenant under `src/Tenants/`. Default when no tenant is given |
| `--only <check>` | Run only these checks; repeatable |
| `--fix [<check>...]` | Apply the fixable repairs without asking: all of them, or only the named checks |
| `--report-only` | Report, and don't ask the fix question. `tenant-pipeline` always passes it (guided and `--auto`), so pipeline step 5 never writes |
| `--auto` | Same as `--fix` — every fixable repair, no questions. Standalone use only |

A folder under `src/Tenants/` with no `*.csproj` is not a tenant. Skip it silently — it is a placeholder, not drift:

```bash
for d in src/Tenants/*/; do ls "$d"*.csproj >/dev/null 2>&1 || echo "skip $(basename "$d")"; done
```

## Check 1 — Registration

A tenant must appear in three places. Missing any one is real drift, not a style issue.

```bash
grep -c "Tenants.<TenantName>.<TenantName>\.csproj" src/ZamConnect.sln
grep -lE "tenant:[[:space:]]*<TenantName>[[:space:]]*$" .azure/tenant.azure-pipelines.*.yaml
grep -niE "dockerfile:[[:space:]]*Tenants/<TenantName>/Dockerfile[[:space:]]*$" src/.dockercompose/docker-compose.yml
```

Match the pipeline by content, not filename — the pipeline slug's hyphenation is inconsistent (tenant-init §4). `[[:space:]]*$` absorbs a trailing `\r`; a bare `<TenantName>$` misses CRLF files.

| Missing | Consequence |
|---|---|
| Solution entry | Not built by a solution-wide `dotnet build`; invisible in the IDE |
| `.azure/tenant.azure-pipelines.<slug>.yaml` | **Never deployed.** No CI, no image, no release |
| docker-compose service | Cannot be run locally alongside the gateway |

Two casing findings, reported separately from "missing":

- **Compose path casing.** The compose grep is `-i`. A hit whose path casing differs from the folder name works only on a case-insensitive build host and breaks on Linux Docker. Report it as its own `warn`.
- **Pipeline `tenant:` casing.** `tenant:` must equal the folder name exactly — `tenant.pipeline.yaml` builds `src/Tenants/${{ parameters.tenant }}/Dockerfile` on a Linux agent. Re-run the pipeline grep with `-i`; a hit that only matches case-insensitively is a `fail`.

Fixable (through the fix question, `--fix` or `--auto`): all three "missing" rows. Generate the pipeline, compose and solution entries exactly as tenant-init §4, §5 and §7 specify.

## Check 2 — Slug consistency

One string has to be spelled identically in four places, or the gateway routes to nothing:

| Place | Form |
|---|---|
| docker-compose service key | `core-<slug>` |
| docker-compose `container_name` | `core-<slug>.zamconnect` |
| Helm release / k8s service | `core-$(helmReleaseName)` — `helmReleaseName` lives in the `GSB.<TENANT>.<ENV>` variable group, outside the repo |
| Gateway YARP cluster | `docs/zamconnect-test-routes.md` (C8) |

`<slug>` is the tenant name lowercased with no separators. List every compose service whose key isn't `core-<lowercase folder>`:

```bash
awk '/^  [a-z0-9.-]+:[[:space:]]*$/ { k = $1; sub(/:$/, "", k) }
     /dockerfile:[[:space:]]*Tenants\// { t = $2; sub(/^Tenants\//, "", t); sub(/\/Dockerfile.*/, "", t)
       if (k != "core-" tolower(t)) print k, t }' src/.dockercompose/docker-compose.yml
```

Each line is a finding (a typo, or a service without the `core-` prefix). Re-derive — don't carry a list forward.

Gateway side: find the tenant's cluster in the routes doc. Cluster IDs are roughly the uppercase tenant name; route names and paths often differ from it:

```bash
awk -F' *[|] *' -v t=<TenantName> 'toupper($6) == toupper(t) { print $3, $5, $8 }' docs/zamconnect-test-routes.md
```

Prints route name, test URL and scope for every route on that cluster. No row = no test-environment route (`warn`; a new tenant won't have one until its gateway package is imported).

The routes doc does not show cluster addresses. `http://core-<slug>` is the expected address; report it and state that `helmReleaseName` and the live cluster destination must equal it. That is a flag for the user, not a verdict — the audit can read neither the variable group nor the gateway admin.

## Check 3 — Endpoint configuration

Clients are registered by assembly scan: `RegisterEndpoints` (`src/Core/Internal/Extensions/Extensions/Rest/RestExtensions.cs`) binds `Endpoints:<TypeName>` for every public class assignable to `IRestEndpoint`; `RegisterSoapEndpoints` (`…/Soap/SoapExtension.cs`) binds `SoapEndpoints:<TypeName>` for every public class assignable to `ISoapEndpoint`. **A class with no section logs `Endpoint {Name} is not configured` and is never registered** — any module or service that injects it fails to resolve at startup (`MapCarter()` for Carter modules). An uninjected one is dead code, not an outage. Nothing fails the build.

A one-line `class X : RestEndpoint` grep is wrong: it misses subclasses of a tenant's own base (e.g. `: ZamPointEndpoint`), misses multi-line declarations (the form `tenant-integration` generates), and reports abstract bases. Resolve bases transitively instead:

```bash
find src/Tenants/<TenantName> -name '*.cs' -not -path '*/bin/*' -not -path '*/obj/*' -exec cat {} + | awk '
  { sub(/\r$/, ""); sub(/\/\/.*/, "") }
  !open && /(^|[^A-Za-z0-9_])class([ \t]+[A-Za-z_]|[ \t]*$)/ { open = 1; d = "" }
  open { d = d " " $0; if (d ~ /[{;]/) { decl(d); open = 0 } }
  function decl(s,   name, n, p, i, b) {
    sub(/[{;].*/, "", s)
    if (s !~ /(^|[^A-Za-z0-9_])public[ \t]/) return
    name = s; sub(/.*(^|[^A-Za-z0-9_])class[ \t]+/, "", name); sub(/[^A-Za-z0-9_].*/, "", name)
    while (s ~ /<[^<>]*>/)   gsub(/<[^<>]*>/, "", s)     # generic args
    while (s ~ /\([^()]*\)/) gsub(/\([^()]*\)/, "", s)   # primary ctor + base ctor args
    sub(/[ \t]where[ \t].*/, "", s)
    if (name == "" || !index(s, ":")) return
    abstract[name] = (s ~ /(^|[^A-Za-z0-9_])abstract[ \t]/)
    n = split(substr(s, index(s, ":") + 1), p, ",")
    for (i = 1; i <= n; i++) { b = p[i]; gsub(/[ \t]/, "", b); sub(/.*\./, "", b); bases[name] = bases[name] " " b " " }
  }
  END {
    kind["RestEndpoint"] = kind["IRestEndpoint"] = "Endpoints"
    kind["SoapEndpoint"] = kind["ISoapEndpoint"] = "SoapEndpoints"
    do { grew = 0
      for (c in bases) if (!(c in kind)) for (k in kind) if (index(bases[c], " " k " ")) { kind[c] = kind[k]; grew = 1; break }
    } while (grew)
    for (c in bases) if ((c in kind) && !abstract[c]) print kind[c] ":" c
  }' | sort -u
```

Output is the required section list, one `Endpoints:<Name>` / `SoapEndpoints:<Name>` per concrete public client. Base names match exactly, so `RestEndpointOptions` never counts. Add `Endpoints:Gateway` when the tenant calls `RegisterGatewayEndpoint(` (it registers `Shared.Endpoints.Gateway` from Core):

```bash
grep -rlE "RegisterGatewayEndpoint\(" src/Tenants/<TenantName> --include=*.cs
```

Actual sections, keys only (never values), for each of `appsettings.json` and `appsettings.Development.json`:

```bash
awk '
  { buf = buf $0 "\n" }
  END {
    n = length(buf)
    for (i = 1; i <= n; i++) {
      c = substr(buf, i, 1)
      if (c == "\"") { s = ""; for (i++; i <= n && substr(buf, i, 1) != "\""; i++) { if (substr(buf, i, 1) == "\\") i++; s = s substr(buf, i, 1) }; last = s }
      else if (c == "/" && substr(buf, i + 1, 1) == "/") { while (i <= n && substr(buf, i, 1) != "\n") i++ }
      else if (c == ":") key = last
      else if (c == "{") { path[++depth] = key; if (depth == 3 && path[2] ~ /^(Endpoints|SoapEndpoints)$/) print path[2] ":" key; key = "" }
      else if (c == "}") depth--
      else if (c == "," || c == "[") key = ""
    }
  }' src/Tenants/<TenantName>/appsettings.json
```

Compare the two lists **case-insensitively** (`IConfiguration` keys are; `MFL.Endpoints.Mfl` against `"MFL"` is fine).

| Finding | Severity |
|---|---|
| Required section missing from `appsettings.json` | `fail` |
| Required section missing only from `appsettings.Development.json` | `warn` |
| `SoapEndpoints:<Name>` without an `AuthenticationScheme` key (null → startup exception; `"None"` for no auth) | `fail` |
| A section with no matching class — dead config, usually a rename that left the old key behind | `warn` |
| A non-endpoint block nested under `Endpoints` (`Serilog`, `Logging`, `ConnectionStrings`, …) — the real top-level section is missing, so that config is never applied | `fail` in `appsettings.json` |

Before calling a section dead, exclude sections read by hand — they have no scanned class by design:

```bash
grep -rnoE 'Endpoints:(\{nameof\()?[A-Za-z0-9_]+' src/Tenants/<TenantName> --include=*.cs
```

Not fixable automatically: a section needs a `BaseUrl` and credentials only the user knows. Report the exact block to add, with `__Token__` placeholders named per C4 and `Username` casing per C3.

## Check 4 — Secrets

Deployment substitutes tokens with `actionOnMissing: fail` (C4), so a placeholder that never got a variable breaks the release, and a literal credential that got committed is a disclosure. **Never print a value** — every command below prints file names, line numbers, key names or counts.

Key suffixes treated as credentials (case-insensitive): `user_?name`, `password`, `secret`, `token`, `thumbprint`, `connection_?string`, `key` (covers `ApiKey`, `api_key`, `PrivateKey`, `PublicKey`), `authheadervalue`. A value is literal when it is non-empty and doesn't start with `_`.

```bash
P='"[^"]*(user_?name|password|secret|token|thumbprint|connection_?string|key|authheadervalue)"[[:space:]]*:[[:space:]]*"[^_"]'
grep -noiE "$P" src/Tenants/<TenantName>/appsettings.json | sed -E 's/^([0-9]+):"([^"]*)".*/\1:\2/'
grep -noiE "$P" src/Tenants/<TenantName>/appsettings.Development.json | sed -E 's/^([0-9]+):"([^"]*)".*/\1:\2/'
git ls-files src/Tenants | grep -iE '\.(p12|pfx|pem|key|jks)$'
```

Each JSON output line is `<line>:<KeyName>`; the last command lists committed key-material paths.

| Where | Rule | Severity |
|---|---|---|
| `appsettings.json` (the published settings artifact) | Every credential is a `__Token__`. `BaseUrl` is a token too unless genuinely environment-independent. Clean repo-wide at the last check, so any hit is new | `fail` |
| `appsettings.Development.json` | Committed credentials are a known repo-wide baseline (C7). Report per tenant as a count, not per line | `warn` |
| Key material outside JSON | Report each path | `fail` |

Under `--all`, lead the section with the baseline count (the C7 command) and the key-material paths, then list tenants whose `appsettings.json` hits. Recommend one rotation ticket for the baseline; don't propose per-tenant edits.

Token names that don't follow C4 (e.g. an external upstream on `__Credentials.<T>Tenant.*__`) are `warn` — they deploy, but won't match the `projects-variables` convention.

For an `appsettings.json` hit, check whether it is already in history — `git log --oneline -- <file>` — and say so: removing it from the working tree does not remove it from the repository.

## Check 5 — API spec readiness

`/tenant-deliverables <Tenant>` (and the repo-local `/api-spec-sync`) need metadata that must already be in the code. `tenant-init` scaffolds the project-level half; `/tenant-integration <Tenant> --spec-only` adds the rest.

Signals, each scored present / absent:

- `<GenerateDocumentationFile>true</GenerateDocumentationFile>` and `<NoWarn>$(NoWarn);CS1591</NoWarn>` in the csproj
- `IncludeXmlComments` and a populated `OpenApiInfo` in `Program.cs`, with `Title` in the form `"{full descriptive name} ({TENANT})"`. `AddSwaggerGen` alone is not a signal — every tenant has it
- A `Swagger/` folder holding the narrative content and any `IOperationFilter` / `ISchemaFilter`
- `.WithTags(...)` on every route — untagged operations collapse into one Postman folder
- `.WithSummary(...)`, `.WithDescription(...)`, `.Produces<T>(...)` and `.ProducesProblem(...)` on every route (`grep -rcE "\.ProducesProblem\(" src/Tenants/<TenantName> --include=*.cs`)
- `///` comments on every public **DTO** property, with no `<see cref="..."/>` in DTOs (Swashbuckle emits the raw type name as literal text). The `cref` rule doesn't apply to endpoints, services or modules
- `.config/dotnet-tools.json` pins `swashbuckle.aspnetcore.cli` (repo-wide; the swagger export can't run without it) at the same version as the tenant's resolved `Swashbuckle.AspNetCore`
- A route for the tenant in `docs/zamconnect-test-routes.md` (Check 2) — the deliverables need a real gateway path

Report as a readiness percentage per tenant, not pass/fail — most tenants meet little of it and that is the baseline, not a regression.

## Check 6 — Tests

```bash
ls src/Tests/<TenantName>.Tests/<TenantName>.Tests.csproj 2>/dev/null
```

Test for the csproj, not the folder — `src/Tests/` holds snapshot folders and untracked leftovers with no project. Report presence; offer `/tenant-tests <TenantName>` when it's missing (`AGENTS.md` requires one per tenant). Whether `Program.cs` ends with `public partial class Program` is informational only — .NET 10 generates a public `Program`, so it's not required.

## Check 7 — Docs and collateral

| Artefact | Rule | Missing = |
|---|---|---|
| Postman collection | A file in `postman collections/` matching `<TenantName>.postman_collection.json` case-insensitively, or whose `info.name` is the tenant | `warn` — many collections are named after the agency or system, not the code |
| Gateway route | The tenant's cluster in `docs/zamconnect-test-routes.md` (Check 2). `src/Tenants/<T>/GATEWAY-CONFIG.md` is optional — only new scaffolds have one | `warn` |
| Agency register row | A table row for the tenant in `docs/zamconnect-agency-tenants.md` | `warn` |

```bash
ls "postman collections" | grep -i "^<TenantName>\.postman_collection\.json$"
grep -m1 -o '"name"[[:space:]]*:[[:space:]]*"[^"]*"' "postman collections"/*.postman_collection.json
grep -ciE "\|[[:space:]]*\`?<TenantName>\`?[[:space:]]*\|" docs/zamconnect-agency-tenants.md
```

(Don't combine `grep -i -x -F` — it crashes Git Bash grep.)

The agency register is hand-generated and goes stale. Flag the document itself when its stated generation date is older than the newest commit under `src/Tenants/`:

```bash
head -5 docs/zamconnect-agency-tenants.md
git log -1 --format=%ad --date=short -- src/Tenants
```

Excluded from the register by design — never report them as missing rows: internal platform tenants (`CloudAdmin`, `GOVZM`, `MobileID`, `ZamMobile`, `ZamData`, `NIR`, `NLR`, `NDR`, `NDW`, `NDP`) and test/mock tenants (`MockData`, `TestTenant`, `TT`). Any other tenant without a row is a real gap.

## Check 8 — Regression guards

Each guard protects a completed migration. All should be clean; any hit is a regression (`fail`).

```bash
T=<TenantName>
# Target framework is net10.0 (prints the csproj if not)
grep -LE "<TargetFramework>net10\.0</TargetFramework>" src/Tenants/$T/$T.csproj
# No Newtonsoft / AutoMapper — AGENTS.md: System.Text.Json only. Comments mentioning them are fine
grep -rnE '^[[:space:]]*using[[:space:]]+(Newtonsoft|AutoMapper)|Include="[^"]*(Newtonsoft|AutoMapper)' src/Tenants/$T --include=*.cs --include=*.csproj
# Modules implement ICarterModule, not the CarterModule base class
grep -rnE ':[[:space:]]*CarterModule\b' src/Tenants/$T --include=*.cs
# Config keys and tokens use Username (C3)
grep -nE '"UserName"[[:space:]]*:|__[A-Za-z.]*UserName__' src/Tenants/$T/appsettings*.json
# Dockerfile images match the pipeline SDK (version: in .azure/tenant.pipeline.yaml) — every tag starts 10.0
grep -nE 'mcr.microsoft.com/dotnet/(sdk|aspnet):' src/Tenants/$T/Dockerfile
grep -nE 'version:' .azure/tenant.pipeline.yaml
```

Also diff the Check 3 section lists of the two appsettings files: every `Endpoints` / `SoapEndpoints` key should exist in both.

Dockerfile closure: list the tenant's `ProjectReference`s, follow each referenced csproj the same way, and require a `COPY ["<dir>/..."` line for every project directory reached. A missing one fails the Linux image build even though `dotnet build` passes.

```bash
grep -oE 'ProjectReference Include="[^"]+"' src/Tenants/<TenantName>/<TenantName>.csproj
grep -oE 'ProjectReference Include="[^"]+"' src/Core/*/*.csproj src/Gateway/Gateway.csproj
grep -E '^COPY \[' src/Tenants/<TenantName>/Dockerfile
```

Not fixable automatically — each is a code change for `/tenant-integration` or a hand edit.

## Fixing

After the report, when at least one finding is fixable and none of `--fix`, `--auto`, `--report-only` was passed, ask once. Header `Fix`, `multiSelect: true`. Each option is one concrete repair, labelled with what it writes:

```
Apply fixes for PQPS? Only the ticked repairs are written. The rest of the report stays as-is.
  [ ] Fix all 3 fixable findings (Recommended)
  [ ] Add .azure/tenant.azure-pipelines.pqps.yaml       check 1 — never deployed without it
  [ ] Add core-pqps to docker-compose.yml               check 1
  [ ] Add PQPS to ZamConnect.sln (Tenants folder)       check 1
```

With more than 3 fixable findings, show the 3 most severe plus `Fix all <n> fixable findings`. Under `--all`, one option per root cause across tenants, naming the tenants the run actually found: `Add pipeline files for <T1>, <T2>`.

Findings that aren't fixable — a missing endpoint section, a committed credential, a casing or slug mismatch, a regression guard — are **never** options. They stay in the report with the exact block to add.

Apply the picked repairs exactly as tenant-init §4 (pipeline), §5 (compose) and §7 (`dotnet sln add … --solution-folder Tenants`) specify, re-run the checks they belong to, and report the new status.

## Report

Lead with the findings, not the checks that passed.

For one tenant: a table of check, status (`ok` / `warn` / `fail`), and the specific finding. Then, for each `fail`, the exact file and the exact line or JSON block that fixes it.

For `--all`: one row per tenant with a column per check, then the failures grouped by check — the same root cause usually spans several tenants and is worth fixing in one pass. Report the Development-credential baseline once, as a count (Check 4). Do not print per-tenant detail for tenants that pass everything.

Severity, highest first:

1. Literal credential in `appsettings.json`, or committed key material (check 4)
2. No pipeline file — never deployed; `tenant:` casing mismatch (check 1)
3. Missing endpoint section in `appsettings.json` for a REST, SOAP or Gateway client; SOAP section without `AuthenticationScheme`; block misnested under `Endpoints` (check 3)
4. Slug mismatch — gateway routes to nothing (check 2)
5. Regression guard hit (check 8)
6. Everything else, including the Development-credential baseline (`warn`)

Close by naming what the audit cannot see: the `GSB.<TENANT>.<ENV>` variable-group contents, the `projects-variables` repo, the ADO pipeline definitions, and the live YARP scope/cluster/route registrations and destination addresses in the gateway admin.

When anything was repaired, end with the equivalent command, e.g. `/tenant-audit PQPS --fix registration`.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it (C7). Finding one in the repo is a finding to report, not a value to reuse. Secrets commands print key names, line numbers and counts only.
