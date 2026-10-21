# zamconnect-integration reference

Every flag, check and output of the plugin's skills. Start with the [README](README.md): it explains the concepts and the steps to create an integration. Come here when you need the detail of one skill.

Each skill also prints its own arguments with `/<skill> --help`.

## Arguments and flags

Every question a skill asks has a flag, and passing the flag skips the question. Every skill that writes files takes `--auto` (defaults, no questions) and `--dry-run` (plan only, nothing written), and prints the fully-flagged command that reproduces what it did. Before writing, every skill shows one review — the files it will write, the routes and the equivalent command — with `Apply`, `Adjust` and `Cancel`.

Every skill takes `--help` (or `-h`): it prints its arguments, their defaults and a few example commands, then stops without asking or writing anything. Typing `/<skill> ` in the prompt box also shows the argument hint inline. A required argument left out, such as the tenant name, is asked for before anything else.

Under `--auto`, a skill never guesses a required input that has no default. It stops and names the flag instead, for example `missing --source <url|path>` or `missing <TenantName>`.

`--gate <n>/<N>` and `--recommend proceed|skip` are internal: `/tenant-pipeline` passes them so each step opens with its own gate and ends with a `GATE-RESULT:` line. You don't pass them yourself.

### `/tenant-init`

`<TenantName> [--controllers] [--full-name "<name>"] [--integrates rest,soap,graphql,db,shared,unknown] [--source <url|path>...] [--shared-source <SYS>...] [--all] [--virtual | --no-virtual] [--port <https>] [--no-pipeline] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant project name (required). PascalCase, with no existing `src/Tenants/<TenantName>/` folder; asked in plain text when omitted |
| `--controllers` | Scaffold MVC controllers instead of Carter modules (the default) |
| `--full-name "<name>"` | Full descriptive name, written into `OpenApiInfo.Title` as `"<name> (<Tenant>)"`. When asked, `Take it from the integration source` leaves it pending, and `/tenant-integration` proposes it from the spec or WSDL title |
| `--integrates` | What the tenant will integrate with. Decides the later defaults — `rest`, `soap`, `graphql` and `db` set the protocol queue of `/tenant-integration`, `shared` makes the shared e-Services step recommended. Asked as `Agency system` / `Shared e-Services` / `Not known yet`, and `Agency system` then asks what the agency system speaks. Derived from the source flags when only they are passed |
| `--source <url\|path>` | Integration source for the integration step, as `/tenant-integration --source` takes it; repeatable. The scaffold doesn't use it: it goes into the pipeline state |
| `--shared-source <SYS>` / `--all` | Shared e-Services systems for the shared e-Services step (`NIR`, `NBR`, `ZRA`, …; repeatable), or every operation. Passed on as `/integrate-shared --source <SYS>` / `--all` |
| `--virtual` / `--no-virtual` | With `--integrates shared` alone: make it a virtual tenant (nothing scaffolded), or scaffold the project anyway. Asked when neither is passed |
| `--port <https>` | HTTPS dev port. Default: the next free pair after the ports in every tenant's `launchSettings.json` |
| `--no-pipeline` | Stop after the scaffold; do not drive the rest of the chain. Use it when you run the other skills by hand. It always wins over `--auto` |
| `--auto` | Run the chain without gates. Pass the sources with `--source`, `--shared-source` or `--all`; when you pick `Auto` in the intake instead, it asks for them once. A missing source stops the chain right after the scaffold, before the next step runs, with the flag named. With `--no-pipeline` too, `--auto` only skips the questions, and nothing runs after the scaffold. With `--integrates shared` alone, `--auto` picks a virtual tenant without asking |
| `--dry-run` | Stop at the review and write nothing, the pipeline state included |

Before writing anything, the skill checks that the name isn't already a folder, a solution entry, or a route, cluster or scope in `docs/zamconnect-test-routes.md`. When the slug is already routed to another tenant's cluster — the agency is a virtual tenant today — it offers to keep those routes as per-path routes in the new `GATEWAY-CONFIG.md`, choose another slug, or stop. The routes of an existing `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md` move into the new package the same way.

After writing, it confirms the solution, pipeline and compose registrations, the observability baseline (`/metrics`, `/metrics/otel`, `/health/live`), the gateway package fields and the `.gitignore` lines. A failed build, image build or start check is reported as a failure, never as done. Without Docker, the image and start checks are reported `skipped`.

### `/tenant-pipeline`

`<TenantName> [--from init|integration|shared|tests|audit|deliverables] [--resume] [--promote] [--status] [--source <url|path>...] [--shared-source <SYS>...] [--all] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to onboard or continue. When omitted, tenants with a state file are offered first, plus `New tenant` |
| `--from <step>` | Start at this step. Earlier steps stay as they are in the state |
| `--resume` | Continue from the first stale step, then the first pending or failed one. The default when a state file exists |
| `--promote` | Turn a virtual tenant into a real one because it needs an integration its gateway routes can't carry: scaffold, re-implement every forwarded operation with the same contract, then integrate, test, audit and document. Stops if the re-implemented operations differ from the virtual tenant's contract |
| `--status` | Print what ran, what's left and the commands to resume; ask and write nothing |
| `--source <url\|path>` / `--shared-source <SYS>` / `--all` | Sources for the integration step and the shared e-Services step, as in `/tenant-init`. Saved to the state, so a resumed run doesn't need them again |
| `--auto` | No gates — every step with its recommended defaults. The audit still runs `--report-only`. Before any step runs, it checks that every protocol has a source and that shared e-Services have a system or `--all`, in the state or the flags. A missing one stops the run with the flag named, and nothing is written. The integration step is skipped when there is neither a protocol nor a source |
| `--dry-run` | Passed to every step: plans are printed and nothing is written, the state file included |

See [Guided mode](#guided-mode) and [State and resume](#state-and-resume).

### `/tenant-integration`

`<TenantName> [--source <url|path> | db[=<path>] | graphql[=<url|path>]...] [--expose <METHOD /route>...] [--protocol rest|soap|graphql|db (comma list)] [--auth <scheme>] [--auth-header <name>] [--login-path <path>] [--credentials shared|per-caller] [--callers <user>,...] [--system <Name>] [--role provide|consume] [--dto public|passthrough] [--modules system|domain] [--timeout <s>] [--proxy] [--aggregate "<GET /path>=<Client.Method>+<Client.Method>"...] [--aggregate-shape fields|list] [--cache <s>] [--db-access dapper|efcore] [--db-writes] [--no-spec-ready] [--spec-only] [--promote] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Existing tenant (required). A missing folder points you to `/tenant-init` |
| `--source <url\|path>` | Integration source: Postman collection, OpenAPI spec, REST base URL, WSDL, GraphQL schema or endpoint, `.sql` file or prose docs; repeatable. `db[=<path>]` and `graphql[=<url\|path>]` name the kind explicitly. Without it, the skill offers the sources it finds in `Deliverables/Integration Requests/`, `postman collections/` and the repo root, tenant-named files first |
| `--expose <METHOD /route>` | Endpoints the tenant should expose; repeatable. Default: every upstream operation, confirmed in the review |
| `--protocol <list>` | Comma list of `rest`, `soap`, `graphql`, `db`. Integrate one upstream at a time for each protocol listed, in the order REST, GraphQL, SOAP, database, asking for another of the same protocol until you mark it done or skip it. Also settles a classification the source leaves open. Without it, the protocol is detected per source |
| `--auth` / `--auth-header` | Upstream auth — REST and GraphQL: `Basic`, `JWT`, `Custom`, `RA`, `Login`, `None`; SOAP: `Basic`, `ClientCertificate`, `None` — and, for `Custom`, the header name. `Login` is a token-login upstream: the client logs in, caches and refreshes the token, and retries once on 401. Default: detected from the source |
| `--login-path <path>` | `Login` only: the login path, relative to the base URL. Default: detected from the source |
| `--credentials shared\|per-caller` / `--callers <user>,…` | `Login` only: one login for the tenant (default), or credentials per gateway caller. `per-caller` makes the tenant authenticate callers itself against the gateway user store; `--callers` lists the gateway usernames that get an entry |
| `--proxy` | Forward every route the tenant doesn't map to this upstream unchanged (method, path, query, JSON body). Proxied operations aren't in Swagger or the documents |
| `--aggregate "<GET /path>=<Client.Method>+…"` | A combined read route that calls several existing operations in parallel and returns one response; repeatable. Some sources failing gives a partial response that names them; all failing gives the first error |
| `--aggregate-shape fields\|list` / `--cache <s>` | One field per source (default) or one merged list; cache lifetime of the combined response, default 1800, `0` for none. Partial responses are never cached |
| `--db-access dapper\|efcore` / `--db-writes` | Database upstreams (SQL Server only): one parameterized SQL statement per operation (default) or an EF Core context; read-only unless `--db-writes` |
| `--system <Name>` | Upstream system name — client class, `Models/<Name>/`, config section and tokens. Default: derived from the source title |
| `--role provide\|consume` | Whether the routes serve this tenant's own institution (`provide`) or data reached back through the gateway (`consume`). Feeds the Consume/Provide split of the deliverables. Default `provide` |
| `--dto public\|passthrough` | Public DTOs plus a mapper (default), or return the upstream shape as-is |
| `--modules system\|domain` | One module per upstream system (default), or per business domain |
| `--timeout <s>` | REST upstream timeout. Default 60 s (the key is omitted) |
| `--no-spec-ready` | Skip the spec-readiness step; the report lists what is still unmet |
| `--spec-only` | Run only the spec-readiness step on the existing surface, then build. Needs no source and asks nothing. `/tenant-deliverables` uses it to fix the code findings it reports |
| `--promote` | The tenant was a virtual tenant. Before the new integration, re-implement every operation its gateway routes forwarded, with the same paths, request and response models, status codes, JSON format and consumer scope; remove the old cross-cluster routes from `GATEWAY-CONFIG.md` and add a cutover section. A contract difference fails the run. Default: detected when `src/VirtualTenants/<CODE>/` still exists |

Under `--auto`, every listed protocol needs a `--source` of its own, or the skill stops with `missing --source <url|path> for <protocol>`. Each pass gets its own client, config section, models and module; the report covers all passes and prints one command per pass.

### `/integrate-shared`

`<TenantName> [--source <SYS> ...] [--endpoint <key> ...] [--base-path <path>] [--tag <Tag>] [--mode inherit|common|routes|virtual] [--shape catch-all|paths] [--scope <scope>] [--dto shared|tenant] [--all] [--new] [--list] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Target tenant, or a virtual tenant's agency code (required; asked for if omitted) |
| `--source <SYS>` | `NIR\|NBR\|DOC\|SRS\|ZDI\|NLR\|ZDA\|NAIR\|ZRA\|MOH`; repeatable. Skips the group menu |
| `--endpoint <key>` | Individual operations by catalogue key (`nir.person.nrc`, `nbr.entity`, …); repeatable. Skips the operation menu |
| `--base-path <path>` | Route group prefix. Default: none (tenant root) |
| `--tag <Tag>` | Swagger tag for the group. Default `EServices` |
| `--mode` | `inherit` — a one-line subclass of `EServicesSharedModule`, only when the selection is exactly its route set. `common` — an abstract `CommonModule` shared by several concrete modules. `routes` — one plain module with only the selected routes. `virtual` — gateway routes onto GOVZM and no code. Default: `virtual` for a name with no tenant folder (when you choose it), `inherit` when the selection is exactly the `EServicesSharedModule` route set, `common` when the tenant already has a `CommonModule`, otherwise `routes` |
| `--shape catch-all\|paths` | Virtual mode: one `/t/<slug>/{**url}` route, or one route per path. Catch-all is allowed only when everything GOVZM serves is selected and no route uses `/t/<slug>/{**url}` yet; it is then the default. Otherwise per path, and always per path on an existing tenant |
| `--scope <scope>` | Virtual mode: the routes' gateway scope. Default `<slug>` for a virtual tenant, or the tenant's own `metadata.Scope` for an existing tenant |
| `--dto shared\|tenant` | Shared response models (default) or tenant DTOs plus a mapper |
| `--all` | Every operation in the catalogue, in `routes` mode. With `--mode virtual`: every operation GOVZM serves |
| `--new` | Tenant does not exist yet; scaffold it with `tenant-init` first |
| `--list` | Print the catalogue and stop. No files written |

`--source` and `--endpoint` combine: sources expand to all their operations, then `--endpoint` adds individual ones. The catalogue is rescanned from `src/Core/Shared/Services/EServicesShared.cs` on every run, so a new shared operation shows up without a plugin change.

For a name with no folder under `src/Tenants/`, the skill asks whether to make it a virtual tenant on GOVZM or scaffold a real tenant first, unless `--mode virtual` or `--new` was passed. Under `--auto` it stops with `missing --source <SYS> or --all`, or, for a missing tenant, `missing --mode virtual or --new`.

The report lists the gateway scopes the tenant's gateway user needs for the operations it exposes (`ndw`, `ndw-nbr`, `zra`, `zra-portal`, …), and the skill writes them into the `## Upstream scopes` section of the tenant's `GATEWAY-CONFIG.md`. A virtual tenant's file gets a `## Host scopes` section instead: the scopes GOVZM's own gateway user must keep.

#### Virtual tenants

A virtual tenant is an agency with no project and no cluster of its own. Its gateway routes point at another tenant's cluster, the host, and a path transform maps them onto a surface the host already serves. The live `GOVZM` routes show both shapes:

| Shape | Example route | Path | Transform |
|---|---|---|---|
| Catch-all — everything the host serves | `t_ccpc_eservices` | `/t/ccpc/{**url}` → `GOVZM` | `/eservices/{**url}`, `order: 1` |
| Per path — a subset | `zigsapi_eservices_person_by_nrc` | `/t/zigs/nir/persons/nrc/{**url}` → `GOVZM` | `/eservices/nir/persons/nrc/{**url}` |

Use one when the agency has no system of its own and needs only operations GOVZM serves (today the six NIR operations, the NBR entity lookup and the ZRA tax clearance). It needs its own tenant when it needs anything else, or its own contract.

A per-path package gets one route per resource (`nir/persons`, `nbr/entities`, `zra/taxpayers`), each listing only the verbs of the operations picked under it. When a resource route would also reach an operation you didn't pick with the same verb, the skill uses deeper paths instead (`nir/persons/nrc`, `nir/persons/zampass`). The review lists every host operation each route reaches. An agency that already holds a scope on another slug (`zilas` for `deeds`, `lands`, `survey`) reuses it through `--scope`.

`<CODE>` below is a new agency code. CCPC and ZIGS are already live, so running these commands for them is refused or collides with their routes:

```
/tenant-init <CODE> --integrates shared --virtual --no-pipeline
/integrate-shared <CODE> --mode virtual --all --shape catch-all
/integrate-shared <CODE> --mode virtual --endpoint nir.person.nrc --endpoint nir.person.zampass
/tenant-audit <CODE>
/tenant-deliverables <CODE>
```

The skill writes `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md`, with `"clusters": []` so the import never overwrites the host cluster, and adds the handoff lines to `.gitignore` when they are missing. It writes no project, pipeline, variables or tests. Run on an existing tenant, `--mode virtual` adds the routes to that tenant's own `GATEWAY-CONFIG.md` instead. It stops when another cluster already owns one of the paths. `/tenant-audit` runs Check V on it: it validates the package against the host, then calls each route through the local gateway as `test<CODE>` / `test`. A real tenant can carry the same cross-cluster routes under its own slug (`t_pqps_eservices_nir_persons`). The rule is generic, not limited to GOVZM: `references/zamconnect-conventions.md` C11 has it.

A virtual tenant that later needs its own project becomes a real tenant with `/tenant-init <CODE> --no-virtual`, which moves its routes into the new `GATEWAY-CONFIG.md`.

### `/tenant-tests`

`<TenantName> [--module <Name> ...] [--coverage full|errors|smoke] [--live] [--no-scaffold] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to test (required) |
| `--module <Name>` | Cover only these modules/controllers; repeatable. Default: all |
| `--coverage` | `full` (default): happy path, upstream 404 and 500, forwarded body, route contract, plus one swagger smoke test. `errors`: the first three. `smoke`: happy path only |
| `--live` | Also generate the `[Explicit]`, `[Category("Staging")]` fixture that calls the real upstream. It reads credentials from `appsettings.local.json`, which git already ignores |
| `--no-scaffold` | Test project already exists — add fixtures only. Detected automatically |

The project is added to `ZamConnect.sln` and the tests are run before the skill reports. Tests assert the route's real error path, as decided by the tenant and Core, and an assertion is never weakened to make it pass. When tests fail, the skill asks whether to fix the tenant, fix the test, or stop with the failures reported.

### `/tenant-audit`

`<TenantName>|--all [--only <check>] [--no-runtime] [--fix [<check>...]] [--report-only] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to audit. A name with no project but a `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md` is audited as a virtual tenant |
| `--all` | Audit every tenant under `src/Tenants/`, and the static part of Check V for every `src/VirtualTenants/*/`. With neither a tenant nor `--all`, the tenant is asked for. Skips the image build and the runtime check, which take minutes per tenant, and reports the Development-credential baseline once, as a count |
| `--only <check>` | One of the check names below; repeatable. `--only runtime` re-runs just the local gateway round-trip |
| `--no-runtime` | Skip the local gateway round-trip (Check 9, or V2 for a virtual tenant) |
| `--fix [<check>...]` | Apply the fixable repairs without asking — all of them, or only those of the named checks. Without it, the audit offers the fixable ones as a pick-list after the report |
| `--report-only` | Report without offering fixes. The Docker checks still run. `/tenant-pipeline` always passes it |
| `--auto` | Same as `--fix`: every fixable repair, no questions |
| `--dry-run` | File checks only: no image build, no Check 9, nothing written to Docker. `/tenant-pipeline --dry-run` passes it |

| # | `--only` name | What it checks | Fixable |
|---|---|---|---|
| 1 | `registration` | Solution entry, `.azure/tenant.azure-pipelines.<slug>.yaml` (and its `tenant:` casing), compose service (and its path casing) | The three missing entries |
| 2 | `slugs` | The slug spelled identically in the compose key `core-<slug>`, `container_name` `core-<slug>.zamconnect`, the `helmReleaseName` value `<slug>` and the `GATEWAY-CONFIG.md` cluster address; the tenant's routes in `docs/zamconnect-test-routes.md` | No |
| 3 | `config` | One `Endpoints:<Name>` / `SoapEndpoints:<Name>` section per client class (base classes resolved transitively), `Endpoints:Gateway` when `RegisterGatewayEndpoint` is called, SOAP `AuthenticationScheme`, dead sections, blocks misnested under `Endpoints` | No — the report gives the block to add |
| 4 | `secrets` | Literal credentials in `appsettings.json`, the committed Development-credential baseline, committed key material, `ENVIRONMENT-VARIABLES.json` against the tokens, handoff files tracked by git or not ignored | The variable list and the `.gitignore` lines |
| 5 | `spec` | Spec readiness for the deliverables, as a percentage | No |
| 6 | `tests` | `src/Tests/<Tenant>.Tests/<Tenant>.Tests.csproj` | No — run `/tenant-tests` |
| 7 | `docs` | Postman collection, gateway route, agency register row and the register's age | No |
| 8 | `guards` | .NET 10, no Newtonsoft/AutoMapper, `ICarterModule`, `Username` key casing, Dockerfile image tags and `COPY` closure, and a local image build | No |
| 9 | `runtime` | The tenant through the local Docker gateway (below) | No |
| V | — | Virtual tenant: V1 checks the package against the host (empty `clusters`, known host cluster, prefix the host maps, verbs, `order`, path collisions, git); V2 calls each route through the local gateway | The `.gitignore` lines |

For a virtual tenant, `--only runtime` runs V2 only, and `--no-runtime`, `--dry-run` and `--all` run V1 only. Secrets commands print key names, line numbers and counts — never a value. A tracked handoff file is reported with the `git rm --cached <path>` command for you to run.

#### Local gateway round-trip

For a single tenant (or `--only runtime`), Check 9 proves the tenant answers through YARP on your machine. It needs Docker running, but no token and no password:

1. Builds and starts `mongo`, `admin-api` and `gateway` from the working tree, and seeds `mongo` from the local dump when it's empty.
2. Writes the tenant's `GATEWAY-CONFIG.md` into the local `mongo` in order: scope, cluster, route. It then creates the test gateway user and bumps the tokens the gateway polls, so the change loads within 30 s.
3. Starts `core-<slug>` and calls `/t/<slug>/health/live` and at least one endpoint per module through `http://localhost:10080`. Every client that calls a gateway (an `__Endpoints.APIGATEWAY.BaseUrl__` token, or a gateway host in its Development `BaseUrl`) is pointed at the local compose `http://gateway/` by a scratch override, signed in as the same test user. Most Development `BaseUrl`s point at the public test gateway, so the tenant is not started when one can't be moved.

| Test user | Value |
|---|---|
| Username | `test<Tenant>`, e.g. `testTT` |
| Password | `test` |

These are local-only throwaway values. The password is shorter than the AdminAPI's password rule, which is why the user is written to Mongo directly and not through `POST /Users`. The script that writes them, `skills/tenant-audit/scripts/apply-local-gateway.js`, refuses to run unless `mongosh` is connected to localhost. The containers, config and user stay in place afterwards, so you can keep testing:

```bash
curl -u testTT:test http://localhost:10080/t/tt/health/live
```

Each response is classified by who answered — the gateway (`401`, `403 Request not allowed`, an empty `404`) or the tenant (its own JSON or problem details). A `5xx` from the tenant whose log shows an unreachable upstream is a `warn`, not a `fail`: a local container usually can't reach the agency system.

For a virtual tenant (V2), the same steps apply to its routes. The host cluster is added to the local `mongo` only when it's missing, and never changed. The host service (`core-govzm`) is started with the test user as its own gateway credentials, and each route is called as `test<CODE>` / `test`. A `5xx` whose host log shows the host's own upstream call failing (`/t/ndw/…` isn't routed locally) is a `warn`: the virtual route itself worked.

It never touches a test, staging or production gateway. Those still take the manual `POST /Import/routes` described in `GATEWAY-CONFIG.md`.

### `/tenant-deliverables`

`<TenantName> [--route <gateway-route>] [--roles tenant,consumer,provider] [--out <dir>] [--version <X.Y>] [--author <name>] [--provide-paths <path>...] [--history-description <text>] [--swagger-doc <name>] [--update-working-collection] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TenantName>` | Tenant to document (required) |
| `--route <r>` | Gateway route, without `/t/`. Default: from the tenant's `GATEWAY-CONFIG.md` (`src/VirtualTenants/<CODE>/` for a virtual tenant; `/tenant-pipeline` also falls back to `docs/zamconnect-test-routes.md`), else the tenant code lowercased. Pass it when the real route differs (`mcti/zabs`, `govzm/ZamPass`) |
| `--roles` | Documents to render. Default: `tenant` always, `consumer`/`provider` when the tenant consumes/provides |
| `--out <dir>` | Output directory holding the five role folders. Default: `src/Tenants/<Tenant>/Deliverables/`, or `src/VirtualTenants/<CODE>/Deliverables/` for a virtual tenant |
| `--version <X.Y>` | Document version. Default `1.0` for a new package, the current version for an existing one. Bump only when the contract changed |
| `--author <name>` | Document History author. Default `dotGov Solutions LLC` |
| `--provide-paths` | OpenAPI paths that are Provide; the rest are Consume. Matched without regard to case and resolved to the exported casing (`/t/pqps/hub/pesticides` → `/t/pqps/Hub/pesticides`). Without it, unresolved endpoints are asked |
| `--history-description <text>` | Description of the new Document History row. Required when `--version` is higher than the current `(t)` document's last row; without it, asked, with a recommendation derived from the operations added or removed |
| `--swagger-doc <name>` | Swagger document to export. Required when `Program.cs` declares several (GOVZM: 12) |
| `--update-working-collection` | Also replace the tracked `postman collections/<Tenant>.postman_collection.json`. Off by default |
| `--auto` | Every default. Stops with `unresolved endpoint <path>: pass --provide-paths` when the split is unclear |
| `--dry-run` | Inspect the tenant and print the review; nothing is built or written |

#### Delivery package

```
<Deliverables>/
  Consumer/              <CODE> (c) API Specification.docx
  Provider/              <CODE> (p) API Specification.docx
  Tenant/                <CODE> (t) API Specification.docx, <CODE> (t) API Swagger.json, <CODE>.postman_collection.json
  Integration Requests/  upstream specs and mapping sheets — carried over, never generated
  Archive/               superseded versions, in Archive/<YYYY-MM-DD HHMM>/
```

| Document | Endpoints |
|---|---|
| `(c)` Consumer | What this tenant calls — data from other systems, reached through the gateway (`Gateway`, `EServicesShared`, a `*SharedModule`) |
| `(p)` Provider | What this tenant serves from its own institution's system (its own `Endpoints:<System>` / `SoapEndpoints:<System>` client) |
| `(t)` Tenant | Every endpoint, Consume first. The OpenAPI JSON and the Postman collection cover this same full surface |

The split is read from the client each module injects, never from the path. An endpoint the inspection can't settle is asked, one question per endpoint. A role with no endpoints gets no document.

What a run does:

- Exports the tenant's own Swagger document (`dotnet build`, then `dotnet tool run swagger tofile` in Development), and prefixes every path with `/t/<route>` exactly once. With several `SwaggerDoc(…)` in `Program.cs` it stops and lists them until `--swagger-doc` picks one.
- Renders each Word document from `templates/api-specification-template.docx` in a fixed six-chapter layout: Executive Summary (from `OpenApiInfo.Description`), Glossary, Endpoints, Schemas, API Environments, Contacts and Signature (left blank for signing). Author names, SharePoint metadata and the ~1 MB `webSettings.xml` junk are stripped.
- Repaginates through Microsoft Word so the table of contents and page numbers are exact.
- Writes the Postman collection with collection-level Basic auth (`{{username}}` / `{{password}}`), requests at `{{zc_base_url}}`, folders by tag and synthetic example values only.
- Describes every schema and property before rendering, so no Schemas table has a blank Description column. Each description comes from the code's `///` comment, else the tenant's catalogue `src/Tenants/<T>/Swagger/schema-descriptions.json`, else another tenant's catalogue entry for the same model. Anything still missing stops the build with exit code 3 and a `missing-descriptions.json`; Claude writes the sentences into the catalogue and re-runs. The catalogue is the file to correct after reading the Word document.
- Carries the Document History forward from the current `(t)` document: a higher version adds one row, the same version keeps the rows, a lower version is refused.
- Moves the superseded version to `Archive/` before anything new lands (seconds are added to the folder name when that minute's folder exists). A delivered file is never overwritten in place.
- Runs the quality gates in `verify_package.py`: path prefix, title, `servers` and DOCX Base URLs against `environments.py`, environment headings, security scheme, tags, parameter docs, DOCX parameter names (casing and order) and response codes against the OpenAPI document, reason phrases, `ProblemDetails`, placeholders in body, header and footer, empty description columns (more than 2 per document), filenames, role words on the cover and in the header, version, history, chapter set, signature block, headings, TOC and pagination, table styles, metadata and package parts (`customXml`, `ContentTypeId`, `HLinks`, `lastPrinted`), `(t)` completeness against the OpenAPI operations, role documents as projections of `(t)`, Postman auth, shape, routes, query keys and example data, and the folder layout (at most one folder level below `Deliverables/`). The Consume/Provide split itself is not a gate. The full table is in the skill's step 8.
- Writes the collection to `Tenant/` only. The repo's tracked working copy, `postman collections/<Tenant>.postman_collection.json`, is replaced only with `--update-working-collection`, and the report then names it.

When the source can't fill a compartment — no `///` comments, no `.WithTags`, undeclared response codes — the document reflects the code as it is and the report lists each gap by file and member. The skill then asks: `Fix them now, then re-render` runs `/tenant-integration <Tenant> --spec-only` and re-renders (the pipeline marks tests and audit `stale`), `Hand over the list` keeps the documents, or `Stop`. A gap whose fix is in `src/Core` is reported only, because no skill edits Core.

Never open a delivered DOCX in Word and save it: the footer's `DATE` fields are live and would rewrite "Last modified". Inspect by unzipping.

For a virtual tenant, the OpenAPI document is assembled from the host's export, trimmed to the operations its routes reach at the consumer's paths, and passed to `build_package.py --from-swagger`. See [Known limitations](#known-limitations) for GOVZM.

The scripts can be run on their own from the ZamConnect root. They are under `<plugins-repo>/plugins/zamconnect-integration/skills/tenant-deliverables/scripts/`, so call them by that full path, or pass `--repo-root <ZamConnect root>` to `inspect_tenant.py` and `build_package.py`:

| Script | Use |
|---|---|
| `inspect_tenant.py <CODE>` | Fact sheet: shape (Carter, controllers, virtual), route, every endpoint with its Consume/Provide section, config, Swagger readiness, roles |
| `build_package.py <CODE> --route <r> --version <X.Y> --roles <roles>` | The whole build. Also takes `--provide-paths`, `--author`, `--out`, `--history-description`, `--swagger-doc <name>`, `--skip-build` (reuse the existing `swagger.json`), `--from-swagger <file>` and `--update-working-collection`. Exits non-zero when a gate fails. Run alone, it does not read `GATEWAY-CONFIG.md`: `--route` defaults to the code lowercased, `--version` to `1.0` and `--roles` to `tenant,consumer`, so pass all three |
| `verify_package.py <Deliverables dir> --route <r> --version <X.Y>` | The gates alone. Without `--route` and `--version`, the comparisons with them are skipped (the documents' versions are still compared with each other) |
| `openapi_to_docx.py`, `openapi_to_postman.ps1`, `apply_gateway_route.py` | The individual render, conversion and prefix steps |

### `/payment-callback`

`<DestinationCode> [--system <Name>] [--kind rest|zampoint|alias] [--alias-of <Client>] [--path </payment/callback>] [--auth Basic|JWT|Custom|None] [--auth-header <name>] [--test-url <url>] [--no-tests] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<DestinationCode>` | The `destinationCode` header ZamPay sends, upper case, `^[A-Z][A-Z0-9]{1,15}$` (required) |
| `--system <Name>` | PascalCase system name for the client class. Default: the code with only its first letter upper case, e.g. `NPDD` → `Npdd` → client `NpddApi` |
| `--kind` | `rest` (default): new `<System>Api : RestEndpoint`. `zampoint`: new `ZamPoint<System> : ZamPointEndpoint`, for an agency on the ZamPoint platform. `alias`: map the code onto an existing callback client — its `case`, or a new `case` when it has none; nothing else is written |
| `--alias-of <Client>` | The existing client for `--kind alias`. Implies `--kind alias` |
| `--path` | Callback path on the agency system. Default `/payment/callback`. `rest` only — `ZamPointEndpoint` fixes the path |
| `--auth` / `--auth-header` | Callback auth. Default `Basic`; `None` only when chosen. `--auth-header` goes with `Custom` |
| `--test-url` | Development `BaseUrl`. Default `https://<code>api.test.gsb.gov.zm` (`rest`) or `https://zampoint<code>.test.gsb.gov.zm` (`zampoint`) |
| `--no-tests` | Skip the `TransactionCallbackEndpointTests` row |

Under `--auto` it stops only on a missing `<DestinationCode>`, or on `--kind alias` without `--alias-of`.

The tokens it writes need `GSB.GOVZM.{DEV,STG,PROD}` variables, or the GOVZM deploy fails on `replacetokens`. When `src/Tenants/GOVZM/ENVIRONMENT-VARIABLES.json` exists, the skill appends one entry per token. Otherwise it lists the names in the report, because a file holding only the new tokens would fail the audit. The forwarding test runs on its own: GOVZM's other fixtures call live systems.

```
/payment-callback NPDD
/payment-callback PAMS --system MihudPams --path /api/zampay/callback
/payment-callback ZTA --alias-of ZamPointMota
```

### `/data-exchange`

`<TargetCode> [--system <Name>] [--kind zampoint|rest|alias] [--alias-of <Client>] [--path </DataExchange/SetData>] [--auth Basic|JWT|Custom|None] [--auth-header <name>] [--test-url <url>] [--no-tests] [--auto] [--dry-run] [--help]`

| Argument / flag | Meaning |
|---|---|
| `<TargetCode>` | The `Target` value in the `SendData` body, upper case, `^[A-Z][A-Z0-9]{1,15}$` (required) |
| `--system <Name>` | PascalCase system name for the client class. Default: the code with only its first letter upper case, e.g. `ZICTA` → `Zicta` → client `ZamPointZicta` |
| `--kind` | `zampoint` (default): new `ZamPoint<System> : ZamPointEndpoint`, posting to `/DataExchange/SetData`. `rest`: new `<System>Api : RestEndpoint, IDataExchangeEndpoint` with its own path. `alias`: reuse an existing client — add a `case` for it, a label on its existing `case`, or `IDataExchangeEndpoint` on a REST client that lacks it |
| `--alias-of <Client>` | The existing client for `--kind alias`. Implies `--kind alias` |
| `--path` | Data-exchange path on the agency system. Default `/DataExchange/SetData`. Not used by `zampoint` — `ZamPointEndpoint` fixes the path |
| `--auth` / `--auth-header` | Auth for a new client. Default `Basic`; `None` only when chosen. `--auth-header` goes with `Custom` |
| `--test-url` | Development `BaseUrl` for a new client. Default `https://zampoint<code>.test.gsb.gov.zm` (`zampoint`) or `https://<code>api.test.gsb.gov.zm` (`rest`) |
| `--no-tests` | Skip the `DataExchangeControllerTests` row |

When `<CODE>` already has a `PayController` case whose client implements `IDataExchangeEndpoint`, that client is the recommended answer, and only the `SendData` case is written. Under `--auto` it takes that client, else a new `zampoint` client, and stops only on a missing `<TargetCode>`.

The test drives `DataExchangeController.SendData` itself with a mocked client, so a row proves the `case`, the client and the path together. Token handling is the same as `/payment-callback`. The gateway route `data_exchange` already exists, so nothing changes there.

```
/data-exchange ERS --alias-of ZamPointErs
/data-exchange ZICTA
/data-exchange NPDD --alias-of NpddApi --path /api/DataExchange/SetData
```

## Guided mode

`/tenant-pipeline` runs these steps. Step 1 has no gate of its own: you answer `tenant-init`'s questions and its review instead.

| # | Step | Offered when |
|---|---|---|
| 1 | `tenant-init` | `src/Tenants/<Tenant>/` doesn't exist |
| 2 | `tenant-integration` | Always. Gets `--protocol` with the `rest`, `graphql`, `soap` and `db` members of the intake answer |
| 3 | `integrate-shared` | Always. Recommended when the intake picked shared e-Services, otherwise `Skip` is recommended |
| 4 | `tenant-tests` | The tenant exposes at least one route, or a catch-all proxy, checked on disk |
| 5 | `tenant-audit` | Always, with `--report-only` and no gate |
| 6 | `tenant-deliverables` | The tenant exposes at least one route; a catch-all proxy alone doesn't count. The route comes from `GATEWAY-CONFIG.md`, then the routes doc |

A step whose condition fails is recorded `skipped` with the reason. A virtual tenant runs steps 3, 5 and 6 only: steps 2 and 4 are recorded `skipped — virtual tenant`, step 3 runs `integrate-shared --mode virtual`, and step 6 is offered once `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md` exists.

Every gate has the same four options:

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
| 3 `integrate-shared` | Every operation of the e-Service groups you pick in the same gate, `routes` mode, tag `EServices`, shared models. Virtual: every operation of the picked groups, default shape and scope | Operations, tag, module mode, response models, base path. Virtual: operations, shape, scope |
| 4 `tenant-tests` | Full coverage matrix, every module, no live fixture | Coverage level, modules, live staging fixture |
| 6 `tenant-deliverables` | Route from `GATEWAY-CONFIG.md`, version `1.0` (or the current one), derived roles, author `dotGov Solutions LLC` | Version, roles, author, output folder |

Step 5, the audit, has no gate: the pipeline runs it with `--report-only`, even under `--auto`, and lists the fixable findings as a `/tenant-audit <Tenant> --fix` command in the closing summary. Every option in every question is a complete answer: sources are offered as the files found in the repo, never as source types. Type a URL or path in **Other** when the one you need isn't listed.

Each step shows a review — the files it will write, the routes, and the equivalent command — before it writes anything. A failed step stops the chain; it never carries on silently.

The closing summary shows one line per step with its status and the command it ran, the commands to resume anything left over, and the administrator's manual list (pipeline registration, variables, gateway import and scopes, ZamPass / RA clients). A virtual tenant's list is shorter: import its `GATEWAY-CONFIG.md` and create the agency's gateway user.

## State and resume

The run is saved to `.claude/zamconnect/<Tenant>.pipeline.json` in the ZamConnect repo after every step. The directory carries its own `.gitignore`, so nothing is committed. It holds answers and commands only, never credentials or host names. Earlier answers become the recommended defaults of the next run.

- `/tenant-pipeline PQPS --status` — what ran, what's left, and the commands to resume
- `/tenant-pipeline PQPS --resume` — pick up where it stopped, with no question asked twice
- Re-running step 2 or 3 marks tests, audit and deliverables `stale`; `--resume` offers them first
- When step 6's findings fix runs `tenant-integration --spec-only`, tests and audit become `stale`
- A tenant that exists but has no state file starts at step 2, with step 1 recorded as run. An existing `src/VirtualTenants/<CODE>/` starts the virtual chain at step 3
- `/tenant-init --no-pipeline` writes the state too, so `/tenant-pipeline <Tenant>` continues from there
- With `--dry-run` nothing is written, the state file included

## Local only: handoff files and what leaves your machine

Every skill works on the local repository and the local Docker stack. Nothing is created in DEV, STG or PROD. The skills leave these handoff files; an administrator applies them by hand:

| File | What the administrator does with it |
|---|---|
| `.azure/tenant.azure-pipelines.<slug>.yaml` | Registers the Azure DevOps pipeline that points at it |
| `src/Tenants/<Tenant>/ENVIRONMENT-VARIABLES.json` | Adds every listed variable to each environment and fills the empty values. Only `helmReleaseName` and `OTEL_SERVICE_NAME` come filled in; `helmNamespace`, `OTEL_EXPORTER_OTLP_ENDPOINT` and every token are empty, and secret values are always empty |
| `src/Tenants/<Tenant>/GATEWAY-CONFIG.md` | Imports the scope, cluster and route into each gateway, and grants the scope to each consumer's gateway user. Its `## Upstream scopes` section lists the scopes the tenant's own gateway user needs for the routes it calls back into (NDW, ZRA, GOVZM `/eservices`, other tenants) |
| `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md` | A virtual tenant's routes, with no cluster. Imports them into each gateway and creates the agency's gateway user with the route scope |

`ENVIRONMENT-VARIABLES.json` and both `GATEWAY-CONFIG.md` files are local only and never committed: send them to the administrator directly. The skill that writes one adds these lines to the repository root `.gitignore` when they are missing:

```gitignore
# zamconnect-integration handoff files: local only
src/Tenants/*/ENVIRONMENT-VARIABLES.json
src/Tenants/*/GATEWAY-CONFIG.md
src/VirtualTenants/*/GATEWAY-CONFIG.md
```

A file that git already tracks stays tracked until someone runs `git rm --cached <path>`; `/tenant-audit` reports it, and no skill runs `git add`, `git rm` or `git commit`. The pipeline file stays in git, because the Azure DevOps pipeline reads it from the repository. `references/zamconnect-conventions.md` C10 lists which other configuration files are committed, and why.

Outside the repository, the skills write only to the local Docker engine: the images `/tenant-init` and `/tenant-audit` build, the compose containers they start, and the scopes, clusters, routes and test users `/tenant-audit` writes into the local `mongo` container. The pipeline state goes to `.claude/zamconnect/` in the ZamConnect repo, which carries its own `.gitignore`.

ZamPass / RA clients are registered by hand by an administrator. The skills write only the `__Token__` placeholders for them, and never record a container registry, Helm, cluster, MongoDB, RA or ZamPass address.

## Known limitations

- **GOVZM's Swagger documents leave out the shared `/eservices` routes.** GOVZM's `DocInclusionPredicate` keeps only routes whose group name matches a document, and `EServicesSharedModule` sets none. The host export that `/tenant-deliverables` would start from is therefore empty for a GOVZM virtual tenant. The workaround is in `tenant-deliverables` step 4: export ZPS document `v1`, keep its `EServices`-tagged operations, trim them to the operations the routes reach, and pass the result with `--from-swagger`.
- **Shared e-Services documents have empty descriptions.** `EServicesSharedModule` declares no `.WithSummary`, `.WithDescription` or `.ProducesProblem`, and the `Shared.Models` types have no `///` comments, so those description columns stay empty and the gates report them. `POST /nir/persons` also declares `200` while it returns `201`. The fixes belong in `src/Core`, which no skill edits.
- **The local round-trip can't reach other gateway upstreams.** A tenant or host that calls `/t/<other>/…` through the gateway gets a local `404`/`403`, because only the audited package is imported locally. The audit reports those calls as `warn`.
- **Exact pagination needs Word on Windows.** See [Prerequisites](README.md#before-you-start).

## Reference files

| File | What it holds |
|---|---|
| `references/interaction-contract.md` | How every skill asks: rules R1–R14 (a flag for every question, structured questions only, review before write, `--auto`, missing arguments, `--help`), the gate and gate mode, and the pipeline state file format |
| `skills/tenant-integration/references/upstream-patterns.md` | Templates and rules for token-login upstreams, per-caller credentials, the catch-all proxy, aggregate routes, database and GraphQL upstreams. Loaded only by a pass that uses one; `tenant-tests` reads it for the matching mocks |
| `references/zamconnect-conventions.md` | ZamConnect facts the skills share: C1 usings and nullability, C2 `Error` → HTTP status, C3 `Username` casing, C4 token naming, C5 Carter DI lifetime, C6 file hygiene, C7 committed-secrets baseline, C8 live routes doc, C9 `ENVIRONMENT-VARIABLES.json`, C10 local-only scope and what's committed, C11 virtual tenants and cross-cluster routes |
| `skills/tenant-deliverables/UPSTREAM-FIXES.md` | Defects in the ZamConnect repo's own `/api-spec-sync` that this plugin's renderers fix but the repo still ships, including personal names in document metadata |
