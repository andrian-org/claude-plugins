# zamconnect-integration

Tenant tooling for the [ZamConnect](https://dev.azure.com/zambiazigs/zambiazigs/_git/ZamConnect)
gateway: scaffolding, integration, drift auditing, tests, and the contractual delivery documents.

Run every skill from the ZamConnect repository root — the directory holding `src/ZamConnect.sln`.

## Install

Run these in a **normal interactive terminal**, not inside a Claude Code session — Git Credential
Manager may need to prompt for Azure DevOps sign-in:

```bash
claude plugin marketplace add https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins
claude plugin install zamconnect-integration@dotgov
```

Restart Claude Code, then confirm with `claude plugin list`.

If the `add` fails with `unable to get password from user`, you are running non-interactively. Do
`git clone <url>` once by hand so GCM caches the credential, then retry. Access is controlled by
the `dotgov` project's repo permissions — no extra PAT is needed if you already clone ZamConnect.

### Provision it for the whole team

Declare the marketplace in the ZamConnect repo itself so teammates get the plugin with no setup:

```bash
claude plugin marketplace add https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins --scope project
```

Then add `zamconnect-integration@dotgov` to `enabledPlugins` in the generated `.claude/settings.json` and
commit it:

```json
{
  "extraKnownMarketplaces": {
    "dotgov": {
      "source": {
        "source": "git",
        "url": "https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins"
      }
    }
  },
  "enabledPlugins": ["zamconnect-integration@dotgov"]
}
```

### Updating

`claude plugin update zamconnect-integration` (restart required). Inside a session: `/plugin marketplace update dotgov`, then `/reload-plugins`.

## Skills

| Skill | What it does |
|---|---|
| `/tenant-init <Tenant>` | Scaffolds `src/Tenants/<Tenant>/` from the standard boilerplate (Carter + Serilog + OpenTelemetry + Prometheus + health checks), spec-ready from the start (`OpenApiInfo`, Basic security scheme, XML comments). Adds the Azure pipeline file, the `core-<slug>` docker-compose service, the `GATEWAY-CONFIG.md` import package (scope, cluster, route), the `ENVIRONMENT-VARIABLES.json` variable list and the `ZamConnect.sln` entry. Verifies that `dotnet build` passes, that the Docker image builds, and that the container answers `/health/live`. Boilerplate only — no modules, models or mappers. Then hands over to `/tenant-pipeline` |
| `/tenant-pipeline <Tenant>` | Runs the whole chain below as one guided flow — a gate per step, a saved state, resume, and stale-marking when an earlier step is re-run |
| `/tenant-integration <Tenant>` | Builds the integration surface of an existing tenant: the upstream `RestEndpoint`/`SoapEndpoint` client, models, mappers, and the routes the tenant exposes. Takes a Postman collection, OpenAPI spec, REST base URL, WSDL or prose API docs as the source — offered from the files it finds in the repo, with protocol and auth detected from them |
| `/integrate-shared <Tenant>` | Exposes shared e-Services (NIR, NBR/PACRA, DOC, SRS, ZDI, NLR, ZDA, NAIR, ZRA, MOH) on a tenant by wiring `EServicesShared` through the gateway, driven by an interactive endpoint menu |
| `/tenant-audit <Tenant>\|--all` | Drift audit, read-only on the repo. It checks: registration in solution/pipeline/compose; slug consistency across compose/Helm/gateway routes; `Endpoints:<Name>` / `SoapEndpoints:<Name>` / `Endpoints:Gateway` config for every client; literal credentials in `appsettings.json` plus the committed Development-credential baseline; `ENVIRONMENT-VARIABLES.json` matching the tokens; spec readiness; regression guards (.NET 10, no Newtonsoft/AutoMapper, Dockerfile closure, a local image build); and presence of docs, Postman collection and tests. For a single tenant it also runs the tenant through the local Docker gateway (see [Local gateway round-trip](#local-gateway-round-trip)). `--fix` repairs the fixable ones |
| `/tenant-tests <Tenant>` | Scaffolds `src/Tests/<Tenant>.Tests/` with a `WebApplicationFactory`, a recording mock upstream handler, and endpoint tests over HTTP. `--live` adds an `[Explicit]` staging fixture |
| `/tenant-deliverables <Tenant>` | Generates the delivery package — OpenAPI JSON, the (c)/(p)/(t) Word API Specifications and the Postman collection — into `src/Tenants/<Tenant>/Deliverables/`. Documents only; never modifies tenant code |

## Local only

Every skill works on the local repository and the local Docker stack. Nothing is created in DEV, STG or PROD. The skills leave three handoff files; an administrator applies them by hand:

| File | What the administrator does with it |
|---|---|
| `.azure/tenant.azure-pipelines.<slug>.yaml` | Registers the Azure DevOps pipeline that points at it |
| `src/Tenants/<Tenant>/ENVIRONMENT-VARIABLES.json` | Adds every listed variable to each environment. Names only; secret values are always empty |
| `src/Tenants/<Tenant>/GATEWAY-CONFIG.md` | Imports the scope, cluster and route into each gateway, and grants the scope to each consumer's gateway user |

ZamPass / RA clients are registered by hand by an administrator. The skills write only the `__Token__` placeholders for them, and never record a container registry, Helm, cluster, MongoDB, RA or ZamPass address.

## Arguments and flags

Every question a skill asks has a flag, and passing the flag skips the question. Every skill that writes files takes `--auto` (defaults, no questions) and `--dry-run` (plan only, nothing written), and prints the fully-flagged command that reproduces what it did.

Every skill takes `--help` (or `-h`): it prints its arguments, their defaults and a few example commands, then stops without asking or writing anything. Typing `/<skill> ` in the prompt box also shows the argument hint inline. A required argument left out, such as the tenant name, is asked for before anything else.

### `/tenant-init`

`<TenantName> [--controllers] [--full-name "<name>"] [--integrates rest,soap,shared,unknown] [--port <https>] [--no-pipeline] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant project name (required) |
| `--controllers` | Scaffold MVC controllers instead of Carter modules (the default) |
| `--full-name "<name>"` | Full descriptive name, written into `OpenApiInfo.Title` as `"<name> (<Tenant>)"` |
| `--integrates` | What the tenant will integrate with. Decides the later defaults — `shared` makes the shared e-Services step recommended |
| `--port <https>` | HTTPS port for the tenant |
| `--no-pipeline` | Stop after the scaffold; do not drive the rest of the chain |
| `--auto` | Run the whole chain without gates |

### `/tenant-pipeline`

`<TenantName> [--from init|integration|shared|tests|audit|deliverables] [--resume] [--status] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to onboard or continue |
| `--from <step>` | Start at this step |
| `--resume` | Continue from the first stale, pending or failed step. The default when a state file exists |
| `--status` | Print what ran, what's left and the commands to resume; ask and write nothing |
| `--auto` | No gates — every step with its recommended defaults |

### `/tenant-integration`

`<TenantName> [--source <url|path>...] [--expose <METHOD /route>...] [--protocol rest|soap|rest,soap] [--auth <scheme>] [--auth-header <name>] [--system <Name>] [--role provide|consume] [--dto public|passthrough] [--modules system|domain] [--timeout <s>] [--no-spec-ready] [--spec-only] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Existing tenant (required) |
| `--source <url\|path>` | Integration source: Postman collection, OpenAPI spec, REST base URL, WSDL or prose docs; repeatable. Without it, the skill offers the sources it finds in the repo |
| `--expose <METHOD /route>` | Endpoints the tenant should expose; repeatable. Default: every upstream operation |
| `--protocol rest\|soap\|rest,soap` | Integrate one upstream at a time for each protocol listed, REST first, asking for another of the same protocol until you mark it done. Also settles a REST/SOAP classification the source leaves open |
| `--auth` / `--auth-header` | Upstream auth — REST: `Basic`, `JWT`, `Custom`, `RA`, `None`; SOAP: `Basic`, `ClientCertificate`, `None` — and, for `Custom`, the header name. Default: detected from the source |
| `--system <Name>` | Upstream system name — client class, models folder, config token. Default: derived from the source title |
| `--role provide\|consume` | Where the routes' data comes from; feeds the Consume/Provide split of the deliverables. Default `provide` |
| `--dto`, `--modules`, `--timeout` | DTO strategy, module grouping, REST timeout |
| `--no-spec-ready` / `--spec-only` | Skip the spec-readiness step / run only it |

### `/integrate-shared`

`<TenantName> [--source <SYS> ...] [--endpoint <key> ...] [--base-path <path>] [--tag <Tag>] [--mode inherit|common|routes] [--dto shared|tenant] [--all] [--new] [--list] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Target tenant (required; asked for if omitted) |
| `--source <SYS>` | `NIR\|NBR\|DOC\|SRS\|ZDI\|NLR\|ZDA\|NAIR\|ZRA\|MOH`; repeatable. Skips the group menu |
| `--endpoint <key>` | Individual operations by catalogue key; repeatable. Skips the operation menu |
| `--base-path <path>` | Route group prefix. Default: none (tenant root) |
| `--tag <Tag>` | Swagger tag for the group. Default `EServices` |
| `--mode inherit\|common\|routes` | Wiring mode. Default chosen by the skill |
| `--dto shared\|tenant` | Shared response models (default) or tenant DTOs plus a mapper |
| `--all` | Every operation in the catalogue, in `routes` mode. `inherit` maps only the subset `EServicesSharedModule` exposes |
| `--new` | Tenant does not exist yet; scaffold it with `tenant-init` first |
| `--list` | Print the catalogue and stop. No files written |

`--source` and `--endpoint` combine: sources expand to all their operations, then `--endpoint` adds individual ones.

### `/tenant-tests`

`<TenantName> [--module <Name> ...] [--coverage full|errors|smoke] [--live] [--no-scaffold] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to test (required) |
| `--module <Name>` | Cover only these modules/controllers; repeatable. Default: all |
| `--coverage` | `full` (default): happy path, upstream 404 and 500, forwarded body, route contract, plus one swagger smoke test. `errors`: the first three. `smoke`: happy path only |
| `--live` | Also generate the `[Explicit]`, `[Category("Staging")]` fixture that calls the real upstream |
| `--no-scaffold` | Test project already exists — add fixtures only. Detected automatically |

### `/tenant-audit`

`<TenantName>|--all [--only <check>] [--no-runtime] [--fix [registration]] [--report-only] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to audit |
| `--all` | Audit every tenant under `src/Tenants/`. With neither a tenant nor `--all`, the tenant is asked for. Skips the image build and the runtime check, which take minutes per tenant |
| `--only <check>` | `registration\|slugs\|config\|secrets\|spec\|tests\|docs\|guards\|runtime`; repeatable. `--only runtime` re-runs just the local gateway round-trip |
| `--no-runtime` | Skip the local gateway round-trip (Check 9) |
| `--fix` | Apply the fixable repairs without asking. Without it, the audit offers the fixable ones as a pick-list after the report |
| `--report-only` | Report without offering fixes. The Docker checks still run |
| `--auto` | Same as `--fix`: every fixable repair, no questions |
| `--dry-run` | File checks only: no image build, no Check 9, nothing written to Docker. `/tenant-pipeline --dry-run` passes it |

#### Local gateway round-trip

For a single tenant (or `--only runtime`), Check 9 proves the tenant answers through YARP on your machine. It needs Docker running, but no token and no password:

1. Builds and starts `mongo`, `admin-api` and `gateway` from the working tree, and seeds `mongo` from the local dump when it's empty.
2. Writes the tenant's `GATEWAY-CONFIG.md` into the local `mongo` in order: scope, cluster, route. It then creates the test gateway user and bumps the tokens the gateway polls, so the change loads within 30 s.
3. Starts `core-<slug>` and calls `/t/<slug>/health/live` and at least one endpoint per module through `http://localhost:10080`. A tenant that calls back into the gateway reaches the local compose `http://gateway/` (its Development `BaseUrl`), signed in as the same test user.

| Test user | Value |
|---|---|
| Username | `test<Tenant>`, e.g. `testTT` |
| Password | `test` |

These are local-only throwaway values. The password is shorter than the AdminAPI's password rule, which is why the user is written to Mongo directly and not through `POST /Users`. The containers, config and user stay in place afterwards, so you can keep testing:

```bash
curl -u testTT:test http://localhost:10080/t/tt/health/live
```

It never touches a test, staging or production gateway. Those still take the manual `POST /Import/routes` described in `GATEWAY-CONFIG.md`.

### `/tenant-deliverables`

`<TenantName> [--route <gateway-route>] [--roles tenant,consumer,provider] [--out <dir>] [--version <X.Y>] [--author <name>] [--provide-paths <path>...] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to document (required) |
| `--route <r>` | Gateway route, without `/t/`. Default: from `GATEWAY-CONFIG.md` (`/tenant-pipeline` also falls back to `docs/zamconnect-test-routes.md`), else the tenant code lowercased (e.g. `mcti/zabs`, `govzm/ZamPass` when it differs) |
| `--roles` | Documents to render. Default: `tenant` always, `consumer`/`provider` when the tenant consumes/provides |
| `--out <dir>` | Output directory holding the five role folders. Default: `src/Tenants/<Tenant>/Deliverables/` |
| `--version <X.Y>` | Document version. Default `1.0` for a new package, the current version for an existing one. Bump only when the contract changed |
| `--author <name>` | Document History author. Default `dotGov Solutions LLC` |
| `--provide-paths` | OpenAPI paths that are Provide; the rest are Consume. Without it, unresolved endpoints are asked |

## Agents

| Agent | Use |
|---|---|
| `tenant-deliverables-builder` | Runs the full `tenant-deliverables` package build for a named tenant in its own context, with every gate passing. Write-restricted to `Deliverables/` |

## Prerequisites

- **.NET 10 SDK** — all skills (`dotnet build`, `dotnet tool run swagger`)
- **Docker Desktop** (engine running) — the image build and start check in `/tenant-init`, and Checks 8–9 of `/tenant-audit`. Without it those checks report `skipped`, never `ok`
- **Git Bash** on Windows — the audit's commands are POSIX shell
- **Python 3.9+** with `python-docx` — the document renderers under `skills/tenant-deliverables/scripts/`
- **Node.js** — `npx openapi-to-postmanv2`, invoked by `openapi_to_postman.ps1`
- **Windows PowerShell** — the Postman conversion step

```
pip install python-docx
```

## Order of execution for a new tenant

`/tenant-init <Tenant>` runs the whole chain for you through `/tenant-pipeline`. Run the skills by hand in this order only when you want a single step:

| # | Skill | Why it sits here |
|---|---|---|
| 1 | `/tenant-init <Tenant>` | Nothing else can run until `src/Tenants/<Tenant>/` exists and builds |
| 2 | `/tenant-integration <Tenant>` | Needs the scaffold; produces the upstream client and the exposed routes. Repeat per upstream system |
| 3 | `/integrate-shared <Tenant>` | **Optional** — only when the tenant also republishes shared e-Services (NIR, PACRA, ZRA, …) |
| 4 | `/tenant-tests <Tenant>` | Fixtures are generated from the routes that exist after steps 2–3 |
| 5 | `/tenant-audit <Tenant>` | Catches what a green build hides: pipeline/compose registration, slug mismatches, missing `Endpoints:<Name>` config, leaked credentials, and a tenant that doesn't answer through the local gateway |
| 6 | `/tenant-deliverables <Tenant>` | **Last.** The deliverables are generated from the final API surface; running it earlier ships a stale specification |

```
/tenant-init PQPS --integrates soap
/tenant-integration PQPS --source "src/Tenants/PQPS/Deliverables/Integration Requests/pqps.wsdl"
/integrate-shared PQPS            # only if shared e-Services are needed
/tenant-tests PQPS
/tenant-audit PQPS
/tenant-deliverables PQPS --route pqps --version 1.0
```

### Guided mode

After the scaffold, `/tenant-pipeline` asks one gate per step. Every gate has the same four options:

| Option | What it does |
|---|---|
| `Proceed` | Runs the step with the defaults listed in the option itself |
| `Customize…` | Asks that step's optional questions first, then runs |
| `Skip` | Leaves the step undone and moves on |
| `Stop` | Ends the chain. The state is kept for `--resume` |

What `Proceed` does, and what `Customize…` adds, per step:

| Step | `Proceed` | `Customize…` also asks |
|---|---|---|
| 2 `tenant-integration` | Uses the source you pick in the same gate. Protocol, SOAP version and auth are detected from it, every operation is exposed, public DTOs + mapper, spec-ready | System name, auth, data role, endpoints, DTO strategy, module grouping, timeout |
| 3 `integrate-shared` | Every operation of the e-Service groups you pick in the same gate, `routes` mode, tag `EServices`, shared models | Operations, tag, module mode, response models, base path |
| 4 `tenant-tests` | Full coverage matrix, every module, no live fixture | Coverage level, modules, live staging fixture |
| 6 `tenant-deliverables` | Route from `GATEWAY-CONFIG.md`, version `1.0` (or the current one), derived roles, author `dotGov Solutions LLC` | Version, roles, author, output folder |

Step 5, the audit, has no gate: the pipeline runs it with `--report-only`, even under `--auto`, and lists the fixable findings as a `/tenant-audit <Tenant> --fix` command in the closing summary. Every option in every question is a complete answer: sources are offered as the files found in the repo, never as source types. Type a URL or path in **Other** when the one you need isn't listed.

Each step shows a review — the files it will write, the routes, and the equivalent command — before it writes anything.

### State and resume

The run is saved to `.claude/zamconnect/<Tenant>.pipeline.json` in the ZamConnect repo. The directory carries its own `.gitignore`, so nothing is committed. It holds answers and commands only, never credentials.

- `/tenant-pipeline PQPS --status` — what ran, what's left, and the commands to resume
- `/tenant-pipeline PQPS --resume` — pick up where it stopped, with no question asked twice
- Re-running step 2 or 3 marks tests, audit and deliverables `stale`; `--resume` offers them first

## Contributing

The plugin lives in the [`dotgov-claude-plugins`](https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins)
marketplace repository, under `plugins/zamconnect-integration/`.

Bump `version` in `.claude-plugin/plugin.json` with every change (SemVer), then validate **both**
manifests before opening a PR:

```bash
claude plugin validate .
claude plugin validate plugins/zamconnect-integration
```

Test locally as a directory marketplace before pushing:

```bash
claude plugin marketplace add /path/to/dotgov-claude-plugins
claude plugin install zamconnect-integration@dotgov
claude plugin details zamconnect-integration@dotgov      # check always-on token cost
```

Tag the release with `claude plugin tag plugins/zamconnect-integration`.

Two rules that matter more than the rest:

- **The `description` in `SKILL.md` frontmatter is the only thing Claude sees when deciding whether
  to load a skill.** Write it as trigger phrases people actually type. Review descriptions in PRs
  more carefully than implementations — a good skill with a vague description never fires.
- **Never commit tokens, `.pfx`/`.jks`/`.pem` files, tenant credentials or client document
  content.** Skills acquire credentials at runtime and cache them outside the repo.

Keep `SKILL.md` lean and push detail into `references/` files that load only when needed — every
session pays the always-on cost. If you also keep a copy of a skill in `~/.claude/skills/`, delete
it; two registrations of the same name collide.
