---
name: tenant-audit
description: Read-only drift audit for ZamConnect tenants. Checks that a tenant is registered everywhere it must be (solution, Azure pipeline, docker-compose), that its slug is spelled identically across compose, Helm and the gateway route, that every REST, SOAP and Gateway client has its `Endpoints:<Name>` / `SoapEndpoints:<Name>` / `Endpoints:Gateway` section in both appsettings files, that `appsettings.json` holds no literal credential (and reports the committed Development-credential baseline), that its API-spec metadata, docs, Postman collection and test project exist, that no migration regression (.NET version, Newtonsoft, AutoMapper, Dockerfile) crept back in, and that the image builds and the tenant answers through the local Docker gateway once its `GATEWAY-CONFIG.md` and a local test user (`test<Tenant>` / `test`) are written to the local Docker Mongo (health plus one endpoint per module). Use when the user says "audit <Tenant>", "is <Tenant> wired up correctly", "check tenant drift", "what's missing for <Tenant>", "why is my endpoint not configured", or types /tenant-audit.
argument-hint: "<TenantName>|--all [--only registration|slugs|config|secrets|spec|tests|docs|guards|runtime] [--no-runtime] [--fix [registration]] [--report-only] [--auto] [--dry-run] [--help]"
allowed-tools: Read Glob Grep Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(git *) Bash(awk *) Bash(sort *) Bash(wc *) Bash(head *) Bash(tail *) Bash(dotnet *) Bash(docker *) Bash(curl *) Edit Write AskUserQuestion
disable-model-invocation: false
---

# ZamConnect Tenant Audit

A tenant can build cleanly and still be broken: unregistered in the pipeline, deployed under a name the gateway route does not resolve, or running with an upstream client that was never registered. None of that fails a build. This skill finds it.

Read-only on the repository by default. No repo file is edited unless the developer picks it in the fix question (see Fixing) or passes `--fix` / `--auto`, and even then only the checks marked fixable below. Checks 8 and 9 touch only the local Docker environment: they build local images, build and start the local stack (`mongo`, `admin-api`, `gateway`) and the tenant container, and apply the tenant's `GATEWAY-CONFIG.md` to the local gateway database. They run under `--report-only` too. Questions follow `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Repo facts (secrets baseline, token naming, key casing, live routes) are in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`, cited below by section id (C1–C8).

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`). Run every command in **Bash** (Git Bash on Windows), not the Grep tool: the patterns below are written to survive CRLF files, which ripgrep/WSL `$` anchors do not.

Never state a count or a "known finding" from memory or from this file. Re-derive everything on each run.

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Audit one tenant. Required unless `--all` is given. With neither, asked first from the contract's Missing arguments menu (R13), with `All tenants` as the fourth option; `--auto` stops with `missing <TenantName> or --all` |
| `--all` | Audit every tenant under `src/Tenants/` |
| `--only <check>` | Run only these checks; repeatable |
| `--fix [<check>...]` | Apply the fixable repairs without asking: all of them, or only the named checks |
| `--report-only` | Report, and don't ask the fix question. `tenant-pipeline` always passes it (guided and `--auto`), so pipeline step 5 never writes |
| `--auto` | Same as `--fix` — every fixable repair, no questions. Standalone use only |
| `--no-runtime` | Skip Check 9 (the local gateway round-trip) |
| `--dry-run` | Checks 1–7 and the static part of Check 8 only: `--report-only`, no image build, no Check 9. Nothing is written, not even to Docker. `tenant-pipeline --dry-run` passes it |
| `--help` | Print the arguments and examples, then stop. Asks and writes nothing (R14) |

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
- A route for the tenant in `GATEWAY-CONFIG.md` or `docs/zamconnect-test-routes.md` (Check 2) — the deliverables need a real gateway path, and read it in that order

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

Image build: the greps above are static. Confirm the image actually builds locally through its compose service — this is what catches a closure gap the grep missed, a casing mismatch, or a stale base image:

```bash
docker info >/dev/null 2>&1 && docker compose -f src/.dockercompose/docker-compose.yml build core-<slug>
```

| Result | Severity |
|---|---|
| Exit 0 | `ok` |
| Non-zero exit — report the failing Dockerfile step and the first error line | `fail` |
| No compose service (Check 1) | Not run; Check 1 already reports it |
| `docker info` fails — Docker not installed or the engine is not running | `skipped`, never `ok`. Print the command for the user to run |

Runs for a single-tenant audit and for `--only guards`. Under a plain `--all` it is `skipped` (each build takes minutes); say so in the report. The build writes only a local image, never a repo file, so it runs under `--report-only` too. If the Dockerfile declares `ARG PAT` (private feed), pass `--build-arg PAT=<token>` from the user's environment and never echo it.

Not fixable automatically — each is a code change for `/tenant-integration` or a hand edit.

## Check 9 — Runtime through the local gateway

Checks 1–8 only read files. This check proves the tenant answers through YARP: it writes `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` and a test gateway user straight into the **local** compose `mongo`, then calls the tenant through the local gateway. It runs for a single-tenant audit and for `--only runtime`. It never runs under a plain `--all`, and `--no-runtime` skips it. It needs no token or password from the user.

**Local only.** Writes go only to the `mongo` compose container (`docker exec mongo`), and calls go only to `http://localhost:8081` (AdminAPI health) and `http://localhost:10080` (gateway), the ports published in `src/.dockercompose/docker-compose.yml`. Both apps read that same `mongo` service (their `appsettings.Development.json` connection strings point at host `mongo`). Never point this check at a test, staging or production database, AdminAPI or gateway, even when the user supplies one. Those registrations belong to `GATEWAY-CONFIG.md`'s manual import through the AdminAPI.

### 9a. Bring up the local stack

A stopped stack is the normal starting state, not a finding: the local gateway environment exists only once this check has built and started it. Build it from the current source and start it on the developer's Docker engine, without asking — every container is local, and nothing outside this machine is touched.

```bash
C="docker compose -f src/.dockercompose/docker-compose.yml"
docker info >/dev/null 2>&1 || echo "docker: not running"
$C up -d --build mongo admin-api gateway
```

`--build` rebuilds `admin-api` and `gateway` from the working tree, so the round-trip runs against the same Core code the tenant was built with, not a stale image.

The compose `mongo` service has no named volume, so a recreated container starts with an empty database. Seed it from the local dump when the `Certificates` collection is missing. Don't test for the `zamconnect` database itself: AdminAPI creates it on startup with only `Secrets`, so it exists even when the dump was never restored.

```bash
M='mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin zamconnect'
$C exec -T mongo sh -c "$M --eval 'db.getCollectionNames().includes(\"Certificates\")'"
# false -> seed it; mongo-restore exits when done
$C up mongo-restore
```

`$M` is single-quoted so the root credentials expand **inside** the `mongo` container, from the variables its compose service sets. Never write the credential values into a command, a file or the report, never use them outside the local container, and never print any other value from the database.

Then wait for both apps, up to 120 s, before 9b:

```bash
for i in $(seq 1 24); do
  a=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/health/live)
  g=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:10080/health/live)
  [ "$a" = 200 ] && [ "$g" = 200 ] && break
  sleep 5
done
```

| Result | Action |
|---|---|
| Docker not installed or the engine not running | Stop Check 9, report it `skipped — Docker not available`, and tell the user in the report's first line |
| `up --build` fails for `admin-api` or `gateway` | `fail` — report the service, the failing Dockerfile step and the first error line. A broken platform image is its own finding, not the tenant's |
| A health endpoint is not `200` after 120 s | `fail` — quote the exception type and message from `$C logs --no-color --tail 60 <service>`, never config values |
| No `GATEWAY-CONFIG.md` | `skipped — no GATEWAY-CONFIG.md`. It is optional for tenants older than the `tenant-init` scaffold (Check 7). Report the file to create, in the `tenant-init` §6 shape, with the tenant's route from the routes doc |
| No compose service (Check 1) | `skipped` — Check 1 already reports it |

Leave the stack running after the check; the report names the containers it started.

### 9b. Apply the gateway config and create the test user

Check 9 uses a fixed, local-only test user per tenant. Nothing is read from the user's environment and nothing is asked:

| Value | Setting |
|---|---|
| Username | `test<TenantName>`, e.g. `testTT`. One per tenant, so it never collides with a real or another tenant's user |
| Password | `test` |

These are throwaway values for the local compose database, not secrets. They can be printed in the report. Never create them in any other environment. The password is shorter than `CreateUserValidator` allows (8+ characters with a letter, a digit and one of `@$!%*?&`). That is why this user is written directly to local Mongo and not through `POST /Users`, and why the AdminAPI and AdminUI refuse to re-save it with the same password.

You can't mint a DGPass admin token locally (every AdminAPI controller is `[Authorize(Policy = "Admin")]` against the DGPass authority), so 9b writes to the local `mongo` container directly with `${CLAUDE_PLUGIN_ROOT}/skills/tenant-audit/scripts/apply-local-gateway.js`. The script applies the package in this order, matching the `Core/Database/Entities` shapes the AdminAPI would write:

1. **Scope**: `scopes` `{Name}` for each route's `metadata.Scope`, inserted only when missing.
2. **Cluster**: `clusters`, upserted on `ConfigJson.ClusterId`.
3. **Route**: `routes`, upserted on `ConfigJson.RouteId`. The route validator needs the scope and cluster to exist first.
4. **User**: `users`, upserted on `Username`. It gets a `PasswordKey` and `PasswordSalt` from `HashHelper`'s PBKDF2 settings (SHA1, 1000 iterations, 20 bytes), `IsDisabled: false`, and the route scopes added with `$addToSet`. Scopes the user already has are kept. The password is reset to `test` on every run.

Keys under `configJson` are PascalCased on write (`clusterId` → `ClusterId`), because the gateway deserialises `ConfigJson` with `BsonSerializer`, which is case-sensitive. The script then replaces `YarpModificationToken` and `UsersModificationToken` in `Secrets`. `YarpStatusWorker` reloads routes, clusters and users only when those tokens change, so a direct write without the bump is never picked up.

Extract the single ```` ```json ```` block from `GATEWAY-CONFIG.md` to a scratch file (never into the repo), copy it and the script into the container, and run it:

On Git Bash, `export MSYS_NO_PATHCONV=1` first, or the `/tmp/...` container paths are rewritten to Windows paths.

```bash
awk '/^```json/{f=1;next} /^```/{f=0} f' src/Tenants/<TenantName>/GATEWAY-CONFIG.md > <scratch>/gateway-package.json
docker cp <scratch>/gateway-package.json mongo:/tmp/gateway-package.json
docker cp "${CLAUDE_PLUGIN_ROOT}/skills/tenant-audit/scripts/apply-local-gateway.js" mongo:/tmp/apply-local-gateway.js
$C exec -T -e ZC_PACKAGE=/tmp/gateway-package.json -e ZC_TEST_USER=test<TenantName> -e ZC_TEST_PASSWORD=test \
  mongo sh -c "$M /tmp/apply-local-gateway.js"
$C exec -T mongo rm -f /tmp/gateway-package.json /tmp/apply-local-gateway.js
```

It prints the scope, cluster and route ids with `created` / `exists` / `updated`, plus the user and its scopes. A mongosh error is a `fail`: quote the error message and stop 9b. The script prints no cluster addresses or other config values, and the report shouldn't either.

The gateway picks up the change on its next `YarpStatusWorker` poll, every 30 s. Wait 35 s before 9c.

### 9c. Start the tenant and call it through the gateway

In the gateway paths below, `/t/<slug>/` stands for the prefix of the route just applied: `match.path` in `GATEWAY-CONFIG.md` minus `{**url}`. That is `/t/<slug>/` for every `tenant-init` scaffold; a hand-written file may use another route (C8), and the calls follow the file.

When the tenant has an `Endpoints:Gateway` section (Check 3), its outbound gateway calls go to `http://gateway/`, the local compose gateway (the Development `BaseUrl`). Give the container the local test user as its gateway credentials through a scratch compose override, never through a repo file:

```bash
cat > <scratch>/gateway-user.override.yml <<EOF
services:
  core-<slug>:
    environment:
      - Endpoints__Gateway__BaseUrl=http://gateway/
      - Endpoints__Gateway__Username=test<TenantName>
      - Endpoints__Gateway__Password=test
EOF
C="$C -f <scratch>/gateway-user.override.yml"
```

Then start the tenant:

```bash
$C up -d --build --no-deps core-<slug>
```

Calls go to `http://localhost:10080/t/<slug>/<path>` with `-u "test<TenantName>:test"`, `-s -o <scratch>/body -w '%{http_code}'`. First the health endpoint:

```bash
curl -s -u "test<TenantName>:test" -w '\n%{http_code}\n' http://localhost:10080/t/<slug>/health/live
```

It must return `200 Healthy`. This single call proves the whole chain: route match, Basic auth, scope, cluster address `http://core-<slug>` resolving on the compose network, and the tenant being up.

Then call **at least one endpoint per module**. List the routes from the tenant's code: `Map(Get|Post|Put|Delete|Patch)(` in each `Modules/*.cs` for Carter tenants, or `[Http*]` plus `[Route]` in `Controllers/*.cs`. Include any group prefix from `MapGroup(`. For each module, prefer a `GET`. Fill route parameters and bodies with obviously fake sample values that pass validation (a 12-digit NRC-shaped string, `"test"`), never real personal data. Use `POST` only when a module has nothing else, with the smallest valid body from the request DTO.

Classify every response by **who answered**. The gateway answers `401`, `403 Request not allowed` and `404` with an empty body for unmatched routes. The tenant answers with its own JSON or problem details.

| Response | Verdict |
|---|---|
| `2xx` | `ok` |
| `400` / `422` problem details from the tenant | `ok` — the call reached the handler and validation ran |
| `401` | `fail` — the test user wasn't picked up: the `UsersModificationToken` bump didn't happen or the users cache hasn't refreshed yet (retry once after 35 s) |
| `403 Request not allowed` | `fail` — the user lacks the `<slug>` scope, or the route's `metadata.Scope` differs from it |
| `404` / `405` from the gateway | `fail` — the path is outside `/t/<slug>/{**url}`, or the verb is missing from the route's `match.methods`. The fix goes in `GATEWAY-CONFIG.md`, and the next run re-applies it |
| `404` from the tenant | `fail` — the route isn't mapped, or its path is wrong |
| `502` / `503` / `504` from the gateway | `fail` — the tenant container isn't reachable at `http://core-<slug>`. Check `$C ps core-<slug>` and its logs |
| `5xx` from the tenant | `warn` if the logs show an upstream connection or timeout error (the agency API isn't reachable from a local container, which is expected), otherwise `fail` |
| `404` / `5xx` from the tenant on a route that calls back through the gateway | `warn` when the gateway log shows the call to `/t/<other route>/…` answered `404`: that other tenant's route isn't in the local gateway. The call itself reached the local gateway with the test user, which is what this check proves |

For every non-`ok` row, read `$C logs --no-color --tail 80 core-<slug>` and `$C logs --no-color --tail 40 gateway`. Quote only the exception type and message, never headers, tokens, request bodies or config values.

Report one row per call: module, method, gateway path, status, verdict. Leave the containers, the applied config and the test user in place so the user can keep testing with `-u test<TenantName>:test`. The report names what was written to the local database, in order: the scope, cluster and route ids, and the test user with its scopes.

Fixable through the fix question: none. Every failure here is a code, config or `GATEWAY-CONFIG.md` change. Applying the package and creating the test user are part of running the check, not repairs.

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
4. Slug mismatch — gateway routes to nothing (check 2); health or a module endpoint failing through the local gateway (check 9)
5. Regression guard hit, image build failure (check 8)
6. Everything else, including the Development-credential baseline (`warn`)

When Check 9 was skipped, the report's first line says why: Docker not running, or no `GATEWAY-CONFIG.md`. A stopped stack is never a reason — 9a starts it.

Close by naming what the audit cannot see: the `GSB.<TENANT>.<ENV>` variable-group contents, the `projects-variables` repo, the ADO pipeline definitions, and the YARP scope/cluster/route registrations in the test, staging and production gateways. Check 9 covers only the local Docker gateway.

When anything was repaired, end with the equivalent command, e.g. `/tenant-audit PQPS --fix registration`.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it (C7). Finding one in the repo is a finding to report, not a value to reuse. Secrets commands print key names, line numbers and counts only.
