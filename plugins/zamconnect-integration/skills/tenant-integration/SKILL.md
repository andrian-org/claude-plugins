---
name: tenant-integration
description: Build the integration surface of an existing ZamConnect tenant — upstream REST, SOAP, GraphQL or SQL Server database client(s), request/response models, mappers, and the Carter modules or controllers the tenant exposes. Takes a tenant name plus integration sources (Postman collection, Swagger/OpenAPI spec, REST base URL, SOAP WSDL, GraphQL schema or endpoint, SQL file, or prose API documentation) and an optional list of endpoints to expose; the source artefact decides the client kind. Also covers token-login upstreams (log in, cache and refresh the token) with shared or per-caller credentials, a catch-all proxy for unmapped routes, and combined routes that fan out to several upstream operations with a cache. Also promotes a virtual tenant that needs an integration its gateway routes and scope can't carry: it re-implements every operation the virtual routes forwarded, with the same paths, request and response models, status codes and auth, before building the new integration. Use when the user says "integrate <Tenant> with <System>", "extend virtual tenant <CODE> with <System>", "promote <CODE> to a real tenant", "add <API> to <Tenant>", "consume this WSDL", "read <Tenant>'s database", "call this GraphQL API", "the upstream needs a login token", "proxy the rest of <System>", "combine these calls into one route", "expose these endpoints on <Tenant>", or types /tenant-integration.
argument-hint: "<TenantName> [--source <url|path> | db[=<path>] | graphql[=<url|path>]...] [--expose <METHOD /route>...] [--protocol rest|soap|graphql|db (comma list)] [--auth Basic|JWT|Custom|RA|Login|None (REST, GraphQL) · Basic|ClientCertificate|None (SOAP)] [--auth-header <name>] [--login-path <path>] [--credentials shared|per-caller] [--callers <user>,...] [--system <Name>] [--role provide|consume] [--dto public|passthrough] [--modules system|domain] [--timeout <seconds>] [--proxy] [--aggregate \"<GET /path>=<Client.Method>+<Client.Method>\"...] [--aggregate-shape fields|list] [--cache <seconds>] [--db-access dapper|efcore] [--db-writes] [--no-spec-ready] [--spec-only] [--promote] [--auto] [--dry-run] [--help]"
disable-model-invocation: false
---

# ZamConnect Tenant Integration

Implement the business surface of a tenant that already exists (scaffold it first with `tenant-init`). This skill covers the two halves of an integration:

- **Consume** — the upstream API the tenant talks to, wrapped in a `RestEndpoint` or `SoapEndpoint` client
- **Expose** — the routes the tenant publishes to its own consumers

The tenant always exposes REST. What it consumes is whatever the upstream speaks, and that is decided by the integration sources, not by preference — see step 1a.

A tenant that was a virtual tenant (C11) first takes over the contract its gateway routes forwarded to the host, unchanged, and only then gets the new integration — see step 1b.

Six patterns go beyond a plain REST or SOAP client: token login (`--auth Login`), per-caller credentials (`--credentials per-caller`), the catch-all proxy (`--proxy`), aggregate routes (`--aggregate`), database upstreams (`--source db`) and GraphQL upstreams (`--source graphql`). Their templates and rules are in `${CLAUDE_PLUGIN_ROOT}/skills/tenant-integration/references/upstream-patterns.md` (§1–§6). Read only the section a pass uses, when it uses it.

Every question follows `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`, R12 above all: **every option is a complete answer**. This skill never offers a source *type* as an option, never asks for anything the source already says (protocol, SOAP version, operations, auth block), and never writes "pick Other and…" in an option.

Shared repo facts — usings/namespace (C1), `Error` → status (C2), `Username` casing (C3), token naming (C4), Carter DI lifetime (C5), file hygiene (C6), committed-secrets baseline (C7), live routes doc (C8), cross-cluster routes (C11), upstream scopes of the tenant's gateway user (C12) — live in `${CLAUDE_PLUGIN_ROOT}/references/zamconnect-conventions.md`. Read it before generating; this skill cites section ids instead of repeating them.

## Arguments

| Flag | Meaning | When absent |
|---|---|---|
| `<TenantName>` | Existing tenant under `src/Tenants/` | Required. Asked first, from the contract's Missing arguments menu (R13); `--auto` stops with `missing <TenantName>`. If the folder is missing, run `tenant-init` first |
| `--source <url\|path>` | Integration source; repeatable. `db[=<path>]` and `graphql[=<url\|path>]` name the kind explicitly: a database upstream (patterns §5) with an optional `.sql` file or document, or a GraphQL upstream (§6) with an optional endpoint URL or schema file | Asked (step 1, source question) |
| `--expose <METHOD /route>` | A route the tenant should expose; repeatable | Every upstream operation, confirmed in the review |
| `--protocol <list>` | Comma list of `rest`, `soap`, `graphql`, `db`. Runs one typed pass per upstream, per protocol listed, in the order REST, GraphQL, SOAP, database (step 1, Protocol passes). The pass's protocol settles a classification step 1a leaves open | Untyped passes, protocol detected from the source |
| `--auth <scheme>` / `--auth-header <name>` | Upstream auth. REST and GraphQL: `Basic`, `JWT`, `Custom`, `RA`, `Login`, `None`. SOAP: `Basic`, `ClientCertificate`, `None`. `--auth-header` goes with `Custom`. `Login` is a token-login upstream (patterns §1) | Detected from the source. Asked only when it can't be |
| `--login-path <path>` | Login path of a `Login` upstream, relative to `BaseUrl` | Detected from the source; asked when there are several candidates or none |
| `--credentials shared\|per-caller` | `Login` only. One login for the tenant, or credentials per gateway caller (patterns §2) | `shared` |
| `--callers <user>,…` | `per-caller` only. Gateway usernames that get an upstream credential entry | Asked; `Add them later` writes an empty map |
| `--proxy` | Forward every route the tenant doesn't map to this pass's upstream unchanged (patterns §3) | No proxy. Asked under `Customize…` |
| `--aggregate "<GET /path>=<Client.Method>+<Client.Method>"` | A combined route over existing read operations (patterns §4); repeatable | None. Offered in step 9 |
| `--aggregate-shape fields\|list` | One field per source, or one merged list | `fields` |
| `--cache <seconds>` | Cache lifetime of the aggregate route's response. `0` = no cache | `1800` |
| `--db-access dapper\|efcore` | Database passes: one SQL statement per operation, or an EF Core `DbContext` | `dapper` |
| `--db-writes` | Database passes: the tenant also writes | Read-only |
| `--system <Name>` | Upstream system name: the client class, `Models/<Name>/`, the config section and tokens | Derived from the source title. Asked only under `Customize…` or when there's nothing to derive it from |
| `--role provide\|consume` | Whether the exposed routes serve this tenant's own institution (`provide`) or data reached back through the gateway (`consume`). `tenant-deliverables` uses it to split the Consume/Provide documents | `provide` |
| `--dto public\|passthrough` | Public DTOs plus a mapper, or return the upstream shape as-is | `public` |
| `--modules system\|domain` | One Carter module per upstream system, or per business domain | `system` |
| `--timeout <seconds>` | Upstream `Timeout` (REST only), written to config as `hh:mm:ss` | 60 s, the `RestEndpointOptions` default (key omitted) |
| `--no-spec-ready` | Skip step 8 | Step 8 runs |
| `--spec-only` | Run only step 8 on the tenant's existing surface, then the step 7 build. No source is needed and no questions are asked. `tenant-deliverables` uses it to fix the code findings it reports | Full integration |
| `--promote` | The tenant was a virtual tenant: run the promotion pass of step 1b before the first protocol pass | Detected (step 1b, When it runs) |
| `--gate <n>/<N>`, `--recommend` | Gate mode, set by `tenant-pipeline` | No gate |
| `--auto` | Every `(Recommended)` default, no questions. Stops with `missing --source <url\|path>` if there's none | Interactive |
| `--dry-run` | Stop at the review (step 1, review) and write nothing | Writes |
| `--help` | Print the arguments and examples, then stop. Asks and writes nothing (R14) | — |

## Gate

Only with `--gate <n>/<N>`. **One** `AskUserQuestion` call holds the gate and, unless `--source` was passed, the source question (R4). The source is required and has no default.

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/tenant-integration <T>` — build the upstream client, models, mappers and exposed routes. Run it? | `Proceed (Recommended)` — protocol and auth detected from the source, every operation exposed, public DTOs + mapper, spec-ready · `Customize…` — also choose system name, auth, data role, DTO strategy, module grouping, timeout, catch-all proxy · `Skip` · `Stop` |
| `Source` | The source question from step 1 below | discovered sources |

With `--protocol rest,soap` the question says the order — "build the REST API clients first, then the SOAP service clients, one upstream at a time" — and `Source` is the first REST pass's source question.

With `--promote` the question starts with the promotion: "first re-implement the <n> operations the virtual routes forwarded to <host>, with their contract unchanged (step 1b), then build the new integration". `Skip` skips both, and the cross-cluster routes `tenant-init` moved into `GATEWAY-CONFIG.md` keep serving the forwarded operations.

`Skip` → end with `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`. Either way, ignore the source answer.

## 1. Collect inputs

Don't write code until every input is settled. Ask through `AskUserQuestion` only, never in plain text.

### Protocol passes

The skill works one upstream at a time: a **pass** is steps 1 to 7 for one upstream system (its sources may be several files, such as a WSDL and its guide), then step 9. `--protocol` decides whether the passes are typed:

| `--protocol` | Passes |
|---|---|
| absent | Untyped. The source question lists every candidate; step 1a detects the protocol per pass; step 9 offers `Add another integration source` |
| one protocol (`rest`, `soap`, `graphql` or `db`) | Typed, that protocol only. It settles a classification step 1a leaves open |
| several, e.g. `rest,soap` or `rest,db` | Typed, as a queue in the fixed order REST, GraphQL, SOAP, database — whatever order they were listed in. `tenant-pipeline` passes the members of the intake answer `integrates` |

In a typed pass:

- The source question asks only for the pass's protocol (below).
- Step 9 keeps offering another upstream of the **same** protocol until the developer says that protocol is done, then starts the next protocol in the queue. The skill doesn't end while a listed protocol hasn't been either integrated or explicitly skipped with its own `Skip <protocol> for now` option.
- `--source` values are classified up front (step 1a), and each goes to a pass of its own protocol. A pass with no `--source` asks.
- A `Customize…` gate answer holds for every pass. The proposal questions, endpoint selection and review (R6) are asked per pass, for that upstream.

Under `--auto`, each listed protocol needs a `--source` of its own; one without stops with `missing --source <url|path> for <protocol>` (R10). A database pass needs a path too: bare `--source db` stops with `missing --source db=<path>`. `--auth Login` with no detectable login path stops with `missing --login-path <path>`.

### Discover sources

Before asking anything, look for sources on disk. Files whose name contains the tenant code come first:

```bash
find "src/Tenants/<T>/Deliverables/Integration Requests" "postman collections" . -maxdepth 2 -type f \( -iname "*.wsdl" -o -iname "*.postman_collection.json" -o -iname "*swagger*.json" -o -iname "*swagger*.yaml" -o -iname "*openapi*.json" -o -iname "*openapi*.yaml" -o -iname "*.graphql" -o -iname "*.gql" -o -iname "*.sql" -o -iname "*.docx" -o -iname "*.pdf" \) 2>/dev/null
```

Skip anything under `bin/`, `obj/` or `node_modules/`, and skip other tenants' `Deliverables/`. For each candidate, peek at it (the first request of a collection, `openapi`/`swagger` and `info.title` of a spec, the `wsdl:service` name) so the option can say what it is.

### Source question

Header `Source`, `multiSelect: true`. Leave it out when `--source` was passed.

**When candidates were found**, each option *is* a source: label is the path relative to the repo, description is what the peek found.

```
Integration source for TT — select one or more, or paste a URL or path in Other.
  [ ] postman collections/TT.postman_collection.json    Postman · 12 requests · JSON bodies (REST)
  [ ] Integration Requests/tt-service.wsdl              WSDL · SOAP 1.1 · 5 operations
  [ ] Integration Requests/TT API Guide.docx            API document · converted to Markdown first
```

With more than 3 candidates, show the best 3 plus `Show all <N> found`. That option re-asks with the rest, spread over up to 4 questions (R9).

**In a typed pass**, list only candidates of the pass's protocol, from the peek: REST — OpenAPI / Swagger, Postman with JSON bodies; SOAP — `.wsdl`, Postman whose requests carry a `<soap:Envelope>`; GraphQL — `.graphql` / `.gql`, introspection JSON, Postman with `graphql` bodies; database — `.sql`. A `.docx` / `.pdf` whose protocol the peek can't tell is listed in every pass. A database pass with no candidate asks the `Tables` question of patterns §5 instead. Leave out candidates an earlier pass already integrated. The question text names the protocol and where the queue stands:

```
REST API source for TT — upstream 2 of REST, SOAP follows. Select one or more, or paste a URL or path in Other.
  [ ] postman collections/TT-Registry.postman_collection.json    Postman · 8 requests · JSON bodies (REST)
  [ ] Integration Requests/TT Registry API.docx                  API document · converted to Markdown first
```

**When nothing was found**, single-select:

```
No integration source for TT in the repo. Paste a URL or path in Other, or:
  ( ) Search Downloads and Desktop     .wsdl / Postman / OpenAPI / .docx / .pdf changed in the last 30 days
  ( ) Wait while I add files           creates Integration Requests/, then rescans
  ( ) Skip the integration for now
```

- `Search Downloads and Desktop` — run the same `find` over `"$HOME/Downloads" "$HOME/Desktop"` with `-mtime -30`, then ask the found-candidates form. If that finds nothing too, fall back to this question without that option.
- `Wait while I add files` — `mkdir -p "src/Tenants/<T>/Deliverables/Integration Requests"`, say where it is, then ask `Files added?` with `Rescan (Recommended)` / `Skip the integration for now`.
- `Skip the integration for now` — end. In gate mode: `GATE-RESULT: skipped`.

In a typed pass the question says `No REST API source for TT in the repo`, and the last option is `Skip REST for now` (`Skip SOAP for now`): it ends that protocol's passes and starts the next one in the queue. After the last protocol, the skill ends — in gate mode `GATE-RESULT: ran` when any pass was built, `GATE-RESULT: skipped` when none was.

Other may hold several sources, one per line. A local file from outside the repo belongs in `Integration Requests/` — offer to copy it there as part of the review, not as a separate question.

### Resolve the sources

- Local file → read it directly
- `.docx` / `.pdf` / `.xlsx` → `convert-documents-to-markdown` skill first
- URL → fetch it; for a Swagger UI URL fetch the underlying `/swagger/v1/swagger.json`, for a SOAP service URL try `?wsdl` / `?singleWsdl`
- Postman collection → parse `item[]` recursively; each leaf `request` gives method, URL, headers, and an example body. A collection can describe a SOAP service too — see step 1a
- WSDL → read `wsdl:portType`/`wsdl:operation` for the operation list, `wsdl:binding` for the SOAP version and `soapAction` values, `wsdl:service`/`soap:address` for the endpoint URL, and the inline or imported `xsd:schema` for the message types (including `minOccurs` and `nillable` — step 4b needs them)
- GraphQL schema, introspection JSON or endpoint → patterns §6, Detection
- `.sql` → the tables, views and procedures it creates, with their columns and parameters (patterns §5)

Record, for every upstream operation you intend to call: its name, the request and response message shapes, and the failure signals that carry meaning — non-200 codes for REST, `Fault` codes and reasons for SOAP.

Then classify (step 1a) and **echo what was read** (R11) before asking anything else:

```
Read as: Postman collection · 12 requests in 3 folders · REST (JSON bodies) · Basic auth at collection level
```

### Detect the rest

Take these from the source, not from the developer:

| Input | Where it's detected |
|---|---|
| Protocol, SOAP version | Step 1a; `wsdl:binding` |
| Auth | OpenAPI `components.securitySchemes`; Postman `auth` at collection, folder or request level; `Authorization` / `X-Api-Key`-style headers on requests; WS-Security policy in the WSDL. A login call whose token later requests send as `Bearer` is `Login` (patterns §1, Detection), with its `LoginPath`, `RefreshTokenPath`, body encoding and token response shape |
| System name | OpenAPI `info.title`, the Postman `info.name`, `wsdl:service/@name`, the document title. Reduced to a PascalCase class name (`PqpsService` → `Pqps`) |
| Operations and groups | OpenAPI tags; Postman folders; `wsdl:portType` operations |
| Per-operation URLs (SOAP) | More than one `soap:address`, or operations documented at different paths |
| Full descriptive name | Only when the state file has `fullName: "pending"`: the same titles as for the system name |

A token-login upstream (log in, receive a token, send it on later calls — ZRA, NAPSA, WCF, NHIMA, ZESCO) is `Login`: the client logs in itself, caches and refreshes the token, and retries once on 401 (patterns §1). When the source shows credentials issued per consuming institution, or the developer says so, ask header `Credentials`: `One login for <T> (Recommended)` · `Per gateway caller` → `--credentials per-caller` (patterns §2).

### Proposal questions

**With `Proceed`, or no gate:** ask only what detection left open, in one call of at most 4 questions. When everything was detected, skip straight to the review.

**With `Customize…`:** ask all four questions of the proposal call, then the customize call, whether detected or not. The detected value is always the first option, marked `(Recommended)`.

Proposal call:

| Header | Question | Options (each a complete answer) |
|---|---|---|
| `Auth` | How does `<T>` authenticate to `<System>`? | The detected scheme first, naming where it came from: `Basic (collection auth)`, `Custom header X-Api-Key (securitySchemes)`, `Token login at auth/login (Postman "Login" request)`. Then the other supported schemes, to 4 in total. REST and GraphQL: `Basic`, `JWT bearer`, `Custom header`, `Token login`, `None`; the question text says "`RA` (DotGov internal services only): type it in Other". SOAP: `Basic`, `Client certificate`, `None`. `Token login` with no detected path asks the `Login` question of patterns §1 |
| `System` | Upstream system name for the client class and config | The derived name `(Recommended)`, e.g. `Pqps — from wsdl:service PqpsService`; the tenant code; the source's short title, if different |
| `Role` | Where does the data behind these routes come from? | `Provide — <T>'s own institution (Recommended)` · `Consume — another system reached through the gateway` |
| `Name` | Only when `fullName` is `pending`: full descriptive name of `<T>` for the spec title | Titles found in the sources, the most specific first · `Use <T> for now` |

When `Custom header` is picked and no header name was detected, follow up with `Header name?`, offering the header names found on the source's requests.

A database pass has no `Auth` question and no `Role` question (its data role is `provide`): it asks `Access` and `Writes` from patterns §5 in their place.

Customize call (`Customize…` only):

| Header | Question | Options |
|---|---|---|
| `DTOs` | Response shaping | `Public DTOs + mapper (Recommended)` · `Pass-through — shared model already exists` |
| `Modules` | Module grouping | `One module per upstream system (Recommended)` · `One module per business domain` |
| `Timeout` | Upstream timeout (REST only) | `Default — 60 s (Recommended)` · `30 s` · `120 s` · `300 s` |
| `Spec` | Make the surface spec-ready now (step 8)? | `Now (Recommended)` · `Later` — adds `--no-spec-ready` |

### Endpoint selection

Asked with `Customize…`, or when `--expose` is absent and there are more than 3 operation groups. `multiSelect`. Options are the groups found (`Pesticides — 3 operations`), or single operations (`GET /pesticides/{id} — pesticide by id`) when there are 3 or fewer, plus `All operations (Recommended)`. More than 3 groups go over up to 3 questions (R9). With `Proceed` and 3 or fewer groups, everything is exposed and the review shows it.

Under `Customize…`, and for REST and GraphQL passes only, the same call also asks the `Proxy` question of patterns §3 when `--proxy` wasn't passed and the tenant has no catch-all yet (`grep -n '{\*\*catch-all}' src/Tenants/<T>/Program.cs`). One catch-all per tenant: a second pass never offers it.

### Review before writing

One R6 call. The question text is the plan, the options `Apply (Recommended)` · `Adjust` · `Cancel`:

```
Integrate TT with Pqps (SOAP 1.1, Basic):
  Endpoints/Pqps.cs                     SoapEndpoint, 5 operations
  appsettings.json + .Development.json  SoapEndpoints:Pqps (+ 5 per-operation URLs)
  Models/Pqps/                          5 request/response pairs, PqpsSoapEndpointOptions
  Mapper/TtMappingExtensions.cs
  Modules/PqpsModule.cs                 MapGroup("/pqps"), tag PQPS
  Program.cs                            + RegisterSoapEndpoints, Configure<PqpsSoapEndpointOptions>
New deploy tokens: __SoapEndpoints.Pqps.BaseUrl__, .Username__, .Password__, 5 × .<Op>Url__
Routes:
  GET  /t/tt/pqps/pesticides            list pesticides
  POST /t/tt/pqps/validate/ephyto       validate an ePhyto certificate
Command: /tenant-integration TT --source "src/Tenants/TT/Deliverables/Integration Requests/tt-service.wsdl" --auth Basic --system Pqps --role provide
```

The review also names, when they apply: the login path and token cache (`Login`), the gateway users given credentials (`per-caller`), the operations reachable only through the catch-all proxy, the aggregate route with its sources and cache lifetime, the connection-string token and packages (database), and the queries (GraphQL).

`Adjust` asks one `multiSelect` — `Source`, `Endpoints`, `Auth`, `System`, `Role`, `DTOs / modules / timeout` — and re-asks only what was picked. `Cancel` ends; in gate mode, `GATE-RESULT: stopped`. With `--dry-run`, print the plan and end here. With `--auto`, apply without asking.

## 1a. Decide the client base class

Read the sources first, then classify. The artefact tells you what the upstream speaks:

| Source artefact | Protocol | Base class |
|---|---|---|
| Swagger / OpenAPI spec | REST | `RestEndpoint` |
| REST base URL + prose docs | REST | `RestEndpoint` |
| Postman collection, JSON bodies, varied verbs, resource paths | REST | `RestEndpoint` |
| **WSDL** (`.wsdl`, `?wsdl`, `?singleWsdl`) | SOAP | `SoapEndpoint` |
| Postman collection where every request is `POST` to one URL with an XML `<soap:Envelope>` body and a `SOAPAction` header | SOAP | `SoapEndpoint` |
| Prose docs quoting XML envelopes, `xmlns:soap`, `wsdl:operation` or `SOAPAction` | SOAP | `SoapEndpoint` |
| `.graphql` / `.gql`, introspection JSON, Postman `graphql` bodies, a `/graphql` URL, `--source graphql` | GraphQL | `RestEndpoint` posting `{query, variables}` (patterns §6) |
| `.sql`, a document listing tables or procedures, `--source db` | Database | Repository over Dapper or EF Core, no endpoint class (patterns §5) |

GraphQL is REST underneath: everything in the REST column below applies, plus patterns §6. A database pass has no client class, no `Endpoints` section and no registrar: patterns §5 replaces steps 3 and 4, and steps 5–9 apply as written.

A Postman collection is the ambiguous case, and the body decides it, not the file type — a collection of `POST`s carrying `<soap:Envelope>` is a SOAP integration dressed as a REST artefact. Check an actual request body before choosing.

Everything downstream follows from this one choice:

| | REST | SOAP |
|---|---|---|
| Base class | `Internal.Clients.RestEndpoint` | `Internal.Clients.SoapEndpoint` |
| Marker type scanned | `IRestEndpoint` (interface) | `ISoapEndpoint` (a class, despite the name) |
| Instantiation | `ActivatorUtilities.CreateInstance(sp, type, client)` — extra DI constructor args allowed (`IOptions<JsonSerializerOptions>`, APIS `IOptions<ApisOptions>`) | `Activator.CreateInstance(type, client)` — `HttpClient` only |
| Config section | `Endpoints:<ClassName>` | `SoapEndpoints:<ClassName>` |
| Registration in `Program.cs` | `RegisterEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration)` | `RegisterSoapEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration)` |
| Auth schemes supported | `Basic`, `JWT`, `Custom`, `RA` — **case-sensitive** exact match; anything else (`basic`, `None`, missing) sends no auth | `Basic`, `ClientCertificate` — case-insensitive; `AuthenticationScheme` key **required** (missing → `NullReferenceException` at startup); anything else = no auth |
| Payloads | `System.Text.Json` | `XmlExtensions.Serialize` / `Deserialize` |
| Client section | Step 4 | Step 4b |

**Upstream reached through the ZamConnect gateway.** When the source's base URL is a ZamConnect gateway (`api.*.gsb.gov.zm`, the compose `http://gateway/`, `localhost:10080`, or a local mock of one) or its paths start with `/t/<route>/`, the upstream is another tenant behind the gateway. Don't create a `<System>` client with its own section. Put the operations on the tenant's `Endpoints/Gateway.cs` (`public class Gateway(HttpClient client, IOptions<JsonSerializerOptions> jsonOptions) : RestEndpoint(client)`, the `src/Tenants/IOM/Endpoints/Gateway.cs` shape), creating it if missing, and call relative paths `t/<route>/…`. `RegisterEndpoints` binds it to `Endpoints:Gateway`, the same section `Shared.Endpoints.Gateway` and `EServicesShared` read (`integrate-shared` §5), so every gateway call of the tenant uses one base URL and one set of gateway credentials. Write that section with the `integrate-shared` §5 shape when it's missing, and keep it when it's there. The data role is `consume`. The review names the client `Gateway`, and the scope each `t/<route>/…` path needs.

The tenant calls those paths as its own gateway user, `Credentials.<Folder>Tenant`, so that user needs the scope of each route they land on (C12): the longest matching route in the routes doc (C8), or the target tenant's `GATEWAY-CONFIG.md` when the route isn't live in test yet. GOVZM's shared e-Services over the gateway (`t/govzm/eservices/…`) need `govzm`. A path no route matches is a `none — no route` row, and the report says an administrator must add the route before the call can work. Rewrite the `## Upstream scopes` section of `GATEWAY-CONFIG.md` in the C12 shape after step 6: one row per scope, `Calls through` naming `Gateway`, with every `t/<route>/…` path of `Endpoints/Gateway.cs` (`grep -oE '"/?t/[^"?{]+' src/Tenants/<T>/Endpoints/Gateway.cs | sort -u`), and keep the `EServicesShared` rows `integrate-shared` wrote.

**Or no code at all.** When the tenant would republish the other tenant's routes unchanged — the same paths below a prefix, the same bodies and errors, no mapping (`--dto passthrough`) — a cross-cluster route forwards them without a client (C11). Find the other tenant's cluster for `/t/<route>/` in the routes doc (C8), then ask header `Pass-through`: `Build the Gateway client and routes (Recommended)` — the tenant owns the contract, its tests and its documents · `Cross-cluster routes, no code` — per-path routes onto `<cluster>` added to `routes[]` of this tenant's `GATEWAY-CONFIG.md`, in the C11 shape. The second writes no client, model, module or config, and ends the pass with that file. The review lists every route with its host path. The tenant's own export doesn't contain these operations: the report names `tenant-deliverables` step 4, which adds them from the host's export. For shared e-Services on GOVZM, `integrate-shared --mode virtual` does this.

A tenant may do both — `RegisterEndpoints` and `RegisterSoapEndpoints` are independent and can be called side by side, each scanning the same assembly for its own marker type. IFMIS is the reference for a tenant that consumes SOAP while exposing REST.

If the sources are genuinely silent on protocol, ask with header `Protocol`: `REST — JSON over HTTP` / `SOAP — XML envelopes` / `GraphQL — one endpoint, {query, variables}` / `Database — direct SQL Server access`, with the reason detection failed in the question text. Do not assume REST. Reaching a SOAP service with a `RestEndpoint` fails at the first call with an unparseable response, not at build time. `--protocol` and the `db` / `graphql` forms of `--source` override the classification when the user already knows.

In a typed pass, the pass's protocol settles a classification the source leaves open. A source that clearly reads as the other protocol — a WSDL or `<soap:Envelope>` bodies in a REST pass, an OpenAPI spec in a SOAP pass — isn't integrated in that pass. Echo it (R11) — `Read as: WSDL · SOAP 1.1 — this is a REST pass` — and ask with header `Protocol`. In a `rest,soap` queue: `Queue it for the SOAP passes (Recommended)` — then ask the REST source question again · `Choose another REST source`. With a single `--protocol`: `Integrate it as SOAP` · `Choose another REST source`.

## 1b. Promote a virtual tenant

A virtual tenant (C11) is gateway routes only. A route and a scope can forward a request to a path prefix a host already serves, and nothing more. Everything else needs a project: the agency's own upstream (REST, SOAP, GraphQL, database), an operation no host serves, token login or per-caller credentials, a combined route, validation, or a contract that differs from the host's. The agency is then **promoted**: `tenant-init <T> --no-virtual` scaffolds the project, and this skill re-implements in the tenant's code every operation the virtual routes forwarded, with the host's contract unchanged. Only then does it build the new integration.

Why code, and not the routes `tenant-init` step 6 moved into the tenant's `GATEWAY-CONFIG.md` as cross-cluster per-path routes: a per-path route wins over the tenant's own `t_<slug>` on its path, so the tenant can never add, test or document anything under it. A virtual catch-all left in a live gateway (`order: 1`) shadows the whole tenant, the new integration included. After promotion the tenant owns one contract: its modules, tests and documents cover every route a consumer calls.

**When it runs.** With `--promote`, or when detected: `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md` exists while `src/Tenants/<T>/` holds a project, or the tenant's `GATEWAY-CONFIG.md` holds a route whose `clusterId` isn't `<TENANT>`. Detected without `--promote`, ask header `Promote`: `Re-implement the <n> forwarded operations in <T> (Recommended)` · `Keep them as cross-cluster routes` — then the new integration must stay off their paths, and the review says so. `--auto` takes the first. With no project under `src/Tenants/<T>/`, stop with `run /tenant-init <T> --no-virtual first`. The promotion is a pass of its own: it runs before the first protocol pass and isn't part of the `--protocol` queue.

**Inventory.** List every route a consumer of the slug calls today:

```bash
cat src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md 2>/dev/null
grep -n '"routeId"\|"path"\|"clusterId"\|"PathPattern"\|"Scope"\|"order"' src/Tenants/<T>/GATEWAY-CONFIG.md
grep -n '/t/<slug>/' docs/zamconnect-test-routes.md
```

For each route: the host cluster, the `PathPattern` prefix, the verbs, the scope, and every host operation it reaches — the `Reaches` list of `integrate-shared` §4a. A live route found only in the routes doc (C8) counts too. Then find each operation's handler in the host: for `GOVZM` `/eservices` it's `src/Core/Shared/Modules/EServicesSharedModule.cs`; for another host, grep its `Modules/` and `Controllers/` for the path below the prefix, and walk the base class of every module (`tenant-deliverables` step 1).

**Baseline.** The contract consumers have today: `src/VirtualTenants/<CODE>/Deliverables/Tenant/<CODE> (t) API Swagger.json` when it exists, else the host's own export filtered to the reached operations (`tenant-deliverables` step 4, virtual tenant). Copy it to the scratchpad; step 7 compares against it. Echo it (R11):

```
Baseline: TTV (t) API Swagger.json · 7 operations · host GOVZM /eservices · scope ttv
```

**Contract freeze.** A consumer of the virtual tenant must see no difference on any of these. Copy each from the host; never regenerate it from this skill's templates or `integrate-shared` §6.

| Aspect | Rule |
|---|---|
| Path and verb | Same consumer path. The tenant's own route `t_<slug>` forwards `/{**url}` unchanged, so map the host route **without** the host prefix: `/eservices/nir/persons/nrc/{nrc}` becomes `/nir/persons/nrc/{nrc}`, in a `MapGroup("")`. Same route constraints (`{zamPassId:Guid}`, `{id:guid}`) |
| Request | Same parameter names and casing, same source (path, query, body), same types, same required-ness, same body type. GOVZM's `POST /nir/persons` binds `NirPersonAddRequest`, not the `PersonAddRequest` of the `integrate-shared` §6 template. Same decoding: GOVZM's `WebUtility.UrlDecode(nrc)` stays |
| Response | Same success status (`200`, `201` with `PersonCreatedResponse`, `202` with no body) and the same type: the host's model from `Shared.Models.*`, or copied property for property into `Models/<Host>/`. No new public DTO and no mapper — `--dto` doesn't apply to promoted operations |
| Serialization | The host's HTTP JSON options, copied exactly onto `AddCarter().ConfigureHttpJsonOptions` (a controller host: `AddControllers().AddJsonOptions`). GOVZM's Carter options add `JsonStringEnumConverter` to `WhenWritingNull` and `IgnoreCycles`; the `tenant-init` scaffold has no enum converter, so without it every enum on the wire turns from a string into a number |
| Errors | The same failure statuses, from the same `Error`s through `CustomResults.Problem`, with `UseRestExceptionHandler()` for the rest (C2). No status the host doesn't produce — no new 400 validation where the host answers 500 |
| Consumer auth | Gateway `Basic` with the scope the virtual routes used. That scope may belong to another slug (`zilas`): `t_<slug>` takes it, so no consumer's gateway user needs a new grant. The host's routes carry no in-app authorization, so the promoted routes call no `RequireAuthorization()`. `--credentials per-caller` applies to the new integration's groups only |
| Upstream | The same upstream, through the same client and path: `EServicesShared` for GOVZM, otherwise the `Gateway` client (step 1a) on the host's own `t/<route>/…` path. Copy the host's non-secret `Endpoints:Gateway` keys (`AuthenticationScheme`, `Timeout`, `RetryCount`), never a value. The tenant's gateway user (`Credentials.<T>Tenant`) needs every scope the host's user used for these operations — `ndw`, `ndw-nbr`, `zra`, `zra-portal` for GOVZM, per the `integrate-shared` §2 catalogue |
| Docs metadata | The host's tag (`EServices`), summaries and descriptions. Step 8 adds metadata only; it never changes the wire |

**Build, per host.**

- **GOVZM, every operation of `EServicesSharedModule` reached** (a catch-all virtual tenant, or per-path routes covering the whole set): run `integrate-shared <T> --mode inherit --endpoint <key>… --tag EServices --auto` with the `Skill` tool. It writes `public class EServicesModule(EServicesShared services) : EServicesSharedModule("EServices", services);` — GOVZM's own class with no base path, so every handler is identical by construction — and the wiring of its §5 (`Shared.csproj`, `RegisterGatewayEndpoint`, `AddTransient<EServicesShared>`, `Endpoints:Gateway`, its three `ENVIRONMENT-VARIABLES.json` entries). Then add the enum converter (Serialization row) yourself: `integrate-shared` doesn't
- **GOVZM, a subset**: write `Modules/EServicesModule.cs` yourself, `MapGroup("").WithTags("EServices")`, holding only the reached routes. Copy each handler from `EServicesSharedModule.AddRoutes` — binding, body, result calls — then add the step 8 metadata. Wire per `integrate-shared` §5. Never `inherit` here: it would also expose the operations the per-path routes kept out
- **Another host** (`NDR`, another tenant's cluster): put the operations on `Endpoints/Gateway.cs` (step 1a, Upstream reached through the ZamConnect gateway), calling the host's own gateway route for the path, from the routes doc (C8). With no such route, stop with `no gateway route onto <host> for <path>`: the host is reachable only by cross-cluster routes, and an administrator must first add one, with a scope the tenant's gateway user gets. Copy the response models from the host's types property for property, with `[JsonPropertyName]` wherever the host's serializer renamed one, and map each status the host operation declares to the same status (404 → `NotFound`, 409 → `Conflict`, 400 → `BadRequest`, 500 → `Internal()`)

No module of the tenant, and no route of the new integration, may map a promoted path again. Check with the `integrate-shared` §7 collision grep before the review.

**Gateway package.** Edit `src/Tenants/<T>/GATEWAY-CONFIG.md`:

- Remove every cross-cluster route of the slug (`clusterId` not `<TENANT>`). Each one would shadow the code that now serves its path.
- Set `metadata.Scope` of `t_<slug>` to the scope the virtual routes used, and its `methods` to every verb the tenant maps (step 6, Gateway methods).
- Write the `## Upstream scopes` section (C12): the promoted operations now call the upstream as `Credentials.<T>Tenant`, so it needs every scope the host's user used for them — the `## Host scopes` table of the virtual package when it has one, else the `integrate-shared` §2 catalogue per operation reached. The cutover's step 2 points at this section.
- Add the cutover section below, listing every old route id — from the virtual package, the routes doc and the routes just removed.

Keep `src/VirtualTenants/<CODE>/` as it is. It is the rollback until every gateway has been cut over.

~~~~markdown
## Cutover from the virtual tenant

<CODE> was a virtual tenant on <host>. Importing this package does not delete the old routes, and while
they exist they keep winning over `t_<slug>`: the catch-all has `order: 1`, and a per-path route is the
longer path. In each gateway, in this order:

1. Deploy `core-<slug>` and check that it answers `/health/live`.
2. Grant the tenant's gateway user (`Credentials.<T>Tenant`) the scopes of the Upstream scopes section above: <scopes>.
3. Import this package with `POST /Import/routes`. Traffic still goes to <host>.
4. Delete each old route: <route ids>. `DELETE /Routes/{id}` takes the route's store id, not its
   `routeId`: look it up in the AdminAPI route list first. From here on, `t_<slug>` serves every path.
5. Call one operation per old route through the gateway with a consumer's credentials.

Consumers change nothing: same paths, same scope, same responses.

Rollback: re-import `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md`. Its routes win over `t_<slug>` again.
~~~~

**Review.** The promotion is its own R6 review, before the first protocol pass's source question:

```
Promote TTV from virtual tenant (GOVZM /eservices) — contract frozen:
  Modules/EServicesModule.cs            7 routes copied from EServicesSharedModule, no base path (zra.tcc not reached)
  Program.cs                            + RegisterGatewayEndpoint, EServicesShared, JsonStringEnumConverter
  appsettings.json + .Development.json  Endpoints:Gateway
  GATEWAY-CONFIG.md                     − 2 cross-cluster routes · t_ttv scope ttv · GET, POST, PATCH · upstream scopes · cutover
Baseline: TTV (t) API Swagger.json · 7 operations · no change allowed
Gateway user Credentials.TTVTenant needs: ndw, ndw-nbr
Old routes to delete at cutover: t_ttv_eservices_nir_persons, t_ttv_eservices_nbr_entities
Command: /tenant-integration TTV --promote
```

`Adjust` asks which operations to drop: dropping one is a breaking change for its consumers, and the review says so in the question text. With `--dry-run`, print the plan and end here.

## 2. Read the tenant and its neighbours

```bash
find src/Tenants/<TenantName> -type f -not -path "*/bin/*" -not -path "*/obj/*"
grep -rlE ":\s*(RestEndpoint|SoapEndpoint)\b" src/Tenants/<TenantName> --include=*.cs
grep -E "<ImplicitUsings>|<Nullable>" src/Tenants/<TenantName>/<TenantName>.csproj
```

Existing clients may live outside `Endpoints/` (APIS `Zims/ZimsApi.cs`) — the grep finds them. The csproj decides the using block and nullability (C1).

Reference implementations — each for one thing only:

- `src/Tenants/APIS` — REST client on a `*Async` method (`Zims/ZimsApi.cs`), options injected into the client, and the Swagger metadata for step 8. **Not** a folder-layout reference: new code keeps `Endpoints/`, `Models/<SYSTEM>/`, `Mapper/`, `Modules/`
- `src/Tenants/CEEC` — one Carter module per resource. Its client `Endpoints/ZamConnect.cs` switches on the status of the throwing `Get` — don't copy that call (step 4)
- `src/Tenants/MOH` — `Mapper/MohMappingExtensions.cs`, and `EServicesShared` for shared NIR/NBR calls: `builder.Services.RegisterGatewayEndpoint(builder.Configuration);` + `builder.Services.AddTransient<EServicesShared>();` (`using Shared.Extensions;`, `using Shared.Services;`)
- `src/Tenants/MOA` — controllers variant
- `src/Tenants/PQPS/Endpoints/GensHub.cs` — the minimal SOAP client (it uses the throwing `PostSoap11`; new code uses the `Result` variants)
- `src/Tenants/IFMIS` — per-operation SOAP URLs only (`Models/Ifmis/IfmisSoapEndpointOptions.cs`, `appsettings.json`). Its module returns raw SOAP DTOs and mutates the client with `SetOptions` — copy neither
- `src/Tenants/PSPF` — SOAP action *format* only (`urn:…:<actionName>`); its `Client.SetHeader("SOAPAction", …)` races (step 4b)

Before defining a new model, check `src/Core/Shared/Models/` — NIR, NBR, DOC, SRS shapes already exist and should be reused rather than redeclared.

## 3. Configure the upstream endpoint

Both registrars work the same way: scan the assembly for the marker type, then bind the configuration section named after the class. **The section key must equal the class name** (the lookup is `IConfiguration`, so case-insensitive). A client with no matching section logs `Endpoint {Name} is not configured` (`SOAP Endpoint {Name} is not configured` for SOAP; SOAP also skips a blank `BaseUrl`) and is **never registered in DI** — any module that injects it then fails at `MapCarter()`, so the tenant crashes on startup. It still builds.

`BaseUrl` is turned into `new Uri(...)` when the client is first created — at `MapCarter()` for a constructor-injected client. It must be a valid absolute URL in **both** files; a placeholder left in `appsettings.Development.json` crashes local runs and the Swagger export that `api-spec-sync` and `tenant-deliverables` run. When `BaseUrl` carries a path (`https://host/api/v2/`), end it with `/` and call relative paths with no leading `/` (`things/{id}`) — a leading `/` drops the base path.

Config keys follow C3: JSON key and token are always `Username`, the C# property is `UserName`. Tokens follow C4; every new `__Token__` needs a variable in each environment, or the deploy fails (`actionOnMissing: fail`). Add one entry per new token to `src/Tenants/<TenantName>/ENVIRONMENT-VARIABLES.json` (C9) — `secret: true` for credential keys, `value: ""` always — and remove the entry of any token this run deletes. Create the file with the four deployment variables first when an older tenant has none. The file is local only: when this run creates it, also append the missing lines of the C10 handoff block to the repository root `.gitignore` (C10, "Not committed"). Never create the variables anywhere else (C10).

### REST

Add to both `appsettings.json` and `appsettings.Development.json`:

```json
"Endpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "Basic",
        "BaseUrl": "__Endpoints.<ClientClassName>.BaseUrl__",
        "Username": "__Endpoints.<ClientClassName>.Username__",
        "Password": "__Endpoints.<ClientClassName>.Password__"
    }
}
```

That is the external-upstream shape (APIS `ZimsApi`, `NpddApi`). Only the `Gateway` client, for an upstream reached through the ZamConnect gateway (step 1a), uses `__Endpoints.APIGATEWAY.BaseUrl__` + `__Credentials.<Folder>Tenant.Username|Password__` (C4), with `http://gateway/` as its Development `BaseUrl`.

Scheme values are matched **exactly** — `"basic"` configures no auth:

| `AuthenticationScheme` | Fields |
|---|---|
| `Basic` | `Username`, `Password` |
| `JWT` | `AuthHeaderValue` = `__Endpoints.<ClientClassName>.ApiKey__` (sent as bearer) |
| `Custom` | `AuthHeaderName` — the detected / `--auth-header` name, as a literal; `AuthHeaderValue` = `__Endpoints.<ClientClassName>.ApiKey__` |
| `RA` | DotGov Registration Authority service-to-service token — **internal DotGov services only** (GOVZM, NDR); never for an external system. Per endpoint `ApplicationScopes { Services[], Scopes[] }`; plus `builder.Services.RegisterRa();` (`using Internal.Extensions;`) and a top-level `RegistrationAuthority { BaseUrl, TokenGeneration { CallingServiceFqn, CertificateThumbprint, PrivateKey } }` section, every value a `__Token__`. Copy the shape from GOVZM/NDR `appsettings.json`, never a value. The RA client is registered by hand by an administrator; write only the tokens, never an RA address (C10) |
| `None` | Nothing else. Write it explicitly |
| `Login` (not a Core scheme) | Write `"AuthenticationScheme": "None"` plus `LoginPath`, `RefreshTokenPath`, `Username`, `Password`, and a top-level `JwtOptions` section — patterns §1. Per-caller credentials add a `Users` map, `MongoDb` and `CacheOptions:Users` — patterns §2 |

`AuthHeaderValue` is always a token, never a value found in the source. Optional fields:

- `Timeout` is a `TimeSpan`: write `"00:02:00"`. A bare `"60"` is 60 **days**. Omit for the 60 s default
- `RetryCount` (int) — above 0 adds a retry policy. Only for idempotent upstream calls
- `DangerousAcceptAnyServerCertificate` — only for a test environment with a self-signed certificate, never production

REST has no client-certificate option: `RestEndpointOptions` carries no key fields.

### SOAP

A different top-level section — `SoapEndpoints`, not `Endpoints`:

```json
"SoapEndpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "Basic",
        "BaseUrl": "__SoapEndpoints.<ClientClassName>.BaseUrl__",
        "Username": "__SoapEndpoints.<ClientClassName>.Username__",
        "Password": "__SoapEndpoints.<ClientClassName>.Password__",
        "<Op>Url": "__SoapEndpoints.<ClientClassName>.<Op>Url__"
    }
}
```

`SoapEndpointOptions` carries only `BaseUrl`, `AuthenticationScheme`, `UserName`, `Password`, `PublicKey` and `PrivateKey`. `ClientCertificate` uses `PublicKey` + `PrivateKey` as base64 DER; `Basic` uses `Username`/`Password`.

- **`AuthenticationScheme` is always written.** A missing key throws `NullReferenceException` at startup. Use `"None"` for no auth
- **There is no `Timeout` and no `DangerousAcceptAnyServerCertificate` for SOAP.** `src/Tenants/PSPF/appsettings.json` sets the latter and it does nothing; do not copy it forward
- **Per-operation URLs: one property and one token per operation**, in both files, never hard-coded. A missing or empty value silently posts to `BaseAddress`. The properties live on `<ClientClassName>SoapEndpointOptions : SoapEndpointOptions` — see step 4b

### Development file

`appsettings.Development.json` gets the same keys. Only `BaseUrl` may be real (the upstream's test URL, or any valid absolute stand-in); credentials, keys and tokens stay `__Token__` placeholders. Many tenants' Development files commit literal credentials (C7) — never use one as the template for values, and never copy a value forward.

## 4. Write the REST client — `Endpoints/<ClientClassName>.cs`

Skip to step 4b for a SOAP upstream, and to patterns §5 for a database. A `Login` client starts from the patterns §1 template and a GraphQL client from §6; the rules of this step still apply to both.

Every template in steps 4–6 is a complete file: full `using` block, sorted with `System*` first, and a file-scoped namespace (C1). They compile with `ImplicitUsings` off. Use `string?` / `T?` only where the csproj enables `<Nullable>`. Line endings and BOM: C6.

Derive from `Internal.Clients.RestEndpoint`; take `HttpClient` and `IOptions<JsonSerializerOptions>` (the instance `Program.cs` configures with `PropertyNameCaseInsensitive = true`; the `tenant-init` scaffold has it). Return `Result<T>` / `Result` from `Internal.Domain.Shared.Result` — never throw across the client boundary.

**Base-method rule:** the non-`Async` methods (`Get`, `Post`, `Put`, `Patch`, `Get<T>`, `Post<TReq,TRes>`) call `EnsureSuccess()` and **throw** on any non-2xx, so a status `switch` after them is dead code and every upstream 404 becomes a 500. The `*Async` methods (`GetAsync`, `PostAsync`, `PutAsync`, `PatchAsync`, `DeleteAsync`, `SendAsync`) return the response untouched. Always use the `*Async` ones.

```csharp
using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;
using Internal.Domain.Shared.Result;
using Microsoft.Extensions.Options;
using Serilog;
using <T>.Models.<SYSTEM>;

namespace <T>.Endpoints;

public class <ClientClassName>(HttpClient client, IOptions<JsonSerializerOptions> jsonOptions)
    : RestEndpoint(client)
{
    public async Task<Result<ThingDto>> GetThing(string id, CancellationToken cancellationToken)
    {
        try
        {
            using var response = await GetAsync($"things/{WebUtility.UrlEncode(id)}", cancellationToken);

            switch (response.StatusCode)
            {
                case HttpStatusCode.OK:
                    var model = await response.Content.ReadFromJsonAsync<ThingDto>(jsonOptions.Value, cancellationToken);
                    return model is null
                        ? Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"))
                        : Result.Success(model);

                case HttpStatusCode.NotFound:
                    return Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"));

                case HttpStatusCode.BadRequest:
                    Log.Warning("<SYSTEM> rejected GetThing: {Content}",
                        await response.Content.ReadAsStringAsync(cancellationToken));
                    return Result.Failure<ThingDto>(Error.BadRequest("thing_invalid_id", $"\"{id}\" is not a valid thing id"));

                default:
                    Log.Error("Unexpected response from <SYSTEM> API: {StatusCode}, {Content}",
                        response.StatusCode, await response.Content.ReadAsStringAsync(cancellationToken));
                    return Result.Failure<ThingDto>(Error.Internal());
            }
        }
        catch (Exception e)
        {
            Log.Error(e, "<SYSTEM> GetThing failed");
            return Result.Failure<ThingDto>(Error.Internal());
        }
    }
}
```

A request body goes through the same options: `PostAsync("things", JsonContent.Create(request, options: jsonOptions.Value), cancellationToken)`.

Rules:

- URL-encode every interpolated path and query value (`WebUtility.UrlEncode`); relative paths, no leading `/` (step 3)
- Error codes are snake_case and stable — consumers match on them
- Pick the `Error` by what the caller should see (C2): `BadRequest` (400) for rejected input or a business rule the caller can fix, `NotFound` (404), `Conflict` (409), `Problem` (**500**, not a 4xx) only for an upstream failure whose code the caller should see, `Internal()` for anything else. Never leak the upstream body to the caller; log it instead
- One method per upstream operation. Do not build a generic passthrough

STJ traps (the Newtonsoft → STJ migration hit each of these):

- `Get<T>` and `Post<TReq,TRes>` also ignore the tenant's options — they use web defaults (USSD regression). Never use them for upstream DTOs
- `Internal.Helpers.StjDefaults.Options` is the repo-wide Newtonsoft-compatible set: case-insensitive reads, PascalCase writes, `WhenWritingNull`. `response.GetPayloadAs<T>()` (`Internal.Extensions.Extensions.Http`) uses it — and returns `default` on a non-JSON content type or parse error, without failing
- An upstream that sends numbers where the model has `string`: `[JsonConverter(typeof(StringOrNumberConverter))]` (`Internal.Helpers`) on the property
- `[JsonIgnore]` blocks inbound binding as well as output. When a field must be read from the caller but not sent upstream (or the reverse), declare a separate outbound DTO
- `DefaultIgnoreCondition = WhenWritingNull` changes the wire format — omitted keys, not `null`. Decide per upstream whether it accepts absent keys

## 4b. Write the SOAP client — `Endpoints/<ClientClassName>.cs`

Derive from `Internal.Clients.SoapEndpoint`. **The constructor must take `HttpClient` and nothing else** — `RegisterSoapEndpoints` instantiates the class with `Activator.CreateInstance(type, client)`, so any extra constructor parameter is a runtime failure, not a compile error. Per-operation URLs therefore arrive as a method argument, supplied by the module.

Base methods (all `protected`; `payload`, then `cancellationToken`, then `url`):

| Method | SOAP | Returns | Behaviour |
|---|---|---|---|
| `PostSoap11Result<T>(payload, ct, url)` | 1.1 | `Result<T>` | Default. 200 → deserialized, or a `<Fault>` in the 200 → logged + `Internal()`. 404 → `NotFound("not_found")`. 504 → `Problem("gateway_timeout")` (500). Any other status — including a standard HTTP-500 SOAP fault — → `Internal()` with **nothing logged**. 200 without an envelope → `NullValue` / `Internal()` (500) |
| `SendSoap11<T>(payload, ct)` | 1.1 | `Result<T>` | Posts to `BaseAddress` only. A `<Fault>` or unparseable 200 → `NotFound("invalid_response")` (404). 504 → `NotFound("gateway_timeout")` (404). Other statuses log the body → `Internal()` |
| `PostSoap11<T>` / `PostSoap12<T>(payload, ct, url)` | 1.1 / 1.2 | `T`, **throws** `HttpRequestException` | Only where the caller handles the exception. There is no `Result` variant for 1.2 — wrap `PostSoap12` in `try`/`catch`, or use the per-request template with `TryValidateSoap12Response<T>()` |

Take the version from `wsdl:binding` — `http://schemas.xmlsoap.org/soap/envelope/` is 1.1, `http://www.w3.org/2003/05/soap-envelope` is 1.2 — and wrap with the matching `WrapInSoap11Envelope()` / `WrapInSoap12Envelope()`. Mixing them produces a fault the upstream will not explain.

**No `soapAction` on the binding** — call the base method, URL as the argument:

```csharp
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;
using Internal.Domain.Shared.Result;
using Internal.Helpers.SoapHelpers;
using <T>.Models.<SYSTEM>;

namespace <T>.Endpoints;

public class <ClientClassName>(HttpClient client) : SoapEndpoint(client)
{
    public Task<Result<ThingResponse>> GetThing(ThingRequest request, string url,
        CancellationToken cancellationToken)
    {
        var envelope = XmlExtensions.Serialize(request).Root.WrapInSoap11Envelope();
        return PostSoap11Result<ThingResponse>(envelope.ToString(), cancellationToken, url);
    }
}
```

**A `soapAction` on the binding** must be sent, and the base methods can't carry it. Put it on a per-request `HttpRequestMessage` — never `Client.SetHeader(...)`: that mutates `DefaultRequestHeaders` on a client the module captures for the process lifetime (C5), so concurrent calls race. `TryValidateSoap11Response<T>()` (`Internal.Extensions.Extensions.Soap`) throws `HttpRequestException` on a `<Fault>` after logging its code and reason — on any status, so HTTP-500 faults get logged too:

```csharp
using System;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;
using Internal.Domain.Shared.Result;
using Internal.Extensions.Extensions.Soap;
using Internal.Helpers.SoapHelpers;
using Serilog;
using <T>.Models.<SYSTEM>;

namespace <T>.Endpoints;

public class <ClientClassName>(HttpClient client) : SoapEndpoint(client)
{
    public async Task<Result<ThingResponse>> GetThing(ThingRequest request, string url,
        CancellationToken cancellationToken)
    {
        var envelope = XmlExtensions.Serialize(request).Root.WrapInSoap11Envelope();
        using var message = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(envelope.ToString(), Encoding.UTF8, SoapConstants.Soap11MediaType)
        };
        message.Headers.TryAddWithoutValidation(SoapConstants.ActionHeader, "\"<soapAction>\"");

        try
        {
            using var response = await Client.SendAsync(message, cancellationToken);
            if (response.StatusCode == HttpStatusCode.NotFound)
            {
                return Result.Failure<ThingResponse>(Error.NotFound("thing_not_found", "Thing not found"));
            }

            var payload = await response.TryValidateSoap11Response<ThingResponse>();
            if (!response.IsSuccessStatusCode || payload is null)
            {
                Log.Error("Unexpected response from <SYSTEM>: {StatusCode}", response.StatusCode);
                return Result.Failure<ThingResponse>(Error.Internal());
            }

            return Result.Success(payload);
        }
        catch (Exception e)
        {
            Log.Error(e, "<SYSTEM> GetThing failed");
            return Result.Failure<ThingResponse>(Error.Internal());
        }
    }
}
```

SOAP 1.2 has no `SOAPAction` header: use `WrapInSoap12Envelope()`, `SoapConstants.Soap12MediaType`, add the action to the content type — `message.Content.Headers.ContentType.Parameters.Add(new NameValueHeaderValue("action", "\"<soapAction>\""));` (`using System.Net.Http.Headers;`) — and validate with `TryValidateSoap12Response<T>()`. PSPF shows the action format (`urn:microsoft-dynamics-schemas/codeunit/PartnerAPI:<actionName>`), not the mechanism.

**Per-operation URLs** — `Models/<SYSTEM>/<ClientClassName>SoapEndpointOptions.cs`, one property per operation, each with its token (step 3):

```csharp
using Internal.Clients;

namespace <T>.Models.<SYSTEM>;

public class <ClientClassName>SoapEndpointOptions : SoapEndpointOptions
{
    public string GetThingUrl { get; set; }
}
```

Bind it in `Program.cs` and inject `IOptions<<ClientClassName>SoapEndpointOptions>` into the module, which passes `options.Value.GetThingUrl` to the client (step 6):

```csharp
builder.Services.Configure<<ClientClassName>SoapEndpointOptions>(
    builder.Configuration.GetSection("SoapEndpoints:<ClientClassName>"));
```

Don't copy IFMIS's `SetOptions`. An existing client that already has it keeps it, bound in the module constructor `(<ClientClassName> client, IConfiguration configuration)` — safe only because the captured instance is set once, at `MapCarter()`.

Rules:

- Message types are plain classes with `System.Xml.Serialization` attributes, generated from the WSDL's schema and placed under `Models/<SYSTEM>/`, namespace `<T>.Models.<SYSTEM>`. Keep the element and namespace names exactly as the schema declares them — `XmlExtensions.Deserialize<T>` matches on them
- `XmlSerializer` drops null elements. Emit every `minOccurs="1"` element: coerce null strings to `string.Empty` in the mapper, or `[XmlElement(IsNullable = true)]` when the XSD allows `xsi:nil`. Compare one serialized envelope against a sample from the source before calling it done
- Don't re-parse the envelope by hand — the base methods and `TryValidateSoap11Response<T>()` already detect `<Fault>`
- One method per WSDL operation, named for the operation

Register in `Program.cs`, alongside `RegisterEndpoints` if the tenant also consumes REST:

```csharp
builder.Services.RegisterSoapEndpoints(Assembly.GetExecutingAssembly(), builder.Configuration);
```

with `using Internal.Extensions.Extensions.Soap;` (and `using <T>.Models.<SYSTEM>;` for the options binding).

## 5. Models and mappers

`Models/<SYSTEM>/` holds upstream shapes and the tenant's public response DTOs. Keep them separate: an upstream field rename must not become a breaking change on the tenant's own API.

`Mapper/<PascalTenant>MappingExtensions.cs` — PascalCase tenant, not the folder casing: `TT` → `TtMappingExtensions`, like `MohMappingExtensions` and `GovZmMappingExtensions`. It holds `static` extension methods (`ToXxxResponse()`) that translate upstream → public, following `src/Core/Shared/Mapper/MappingConventions.md` (naming, null safety) and `src/Tenants/MOH/Mapper/`:

```csharp
using <T>.Models.<SYSTEM>;

namespace <T>.Mapper;

public static class <PascalTenant>MappingExtensions
{
    public static ThingResponse ToThingResponse(this ThingDto src)
    {
        if (src is null) return null;

        return new ThingResponse
        {
            Id = src.Id,
            Name = src.Name,
        };
    }
}
```

Assign **every** settable target property explicitly — the AutoMapper removal silently dropped one that was left out. Before finishing, diff the target type's property list against each initializer.

Upstream DTOs follow the STJ traps in step 4. Skip both folders when the response passes through unchanged and the shape already lives in `Core/Shared/Models`.

## 6. Expose the tenant's own endpoints

One `ICarterModule` per upstream system or business domain in `Modules/<Name>Module.cs`, where `<Name>` is that system or domain — `NirModule`, `NbrModule`, `DophmsModule` — not the individual resource it serves (`NirPersonsModule` is wrong; persons are one resource inside NIR). Group routes with `MapGroup` + `WithTags`; declare every response shape so Swagger and the generated API spec are accurate.

```csharp
using System.Threading;
using Carter;
using Internal.Domain.Shared.Result;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Routing;
using <T>.Endpoints;
using <T>.Mapper;
using <T>.Models.<SYSTEM>;

namespace <T>.Modules;

public class <Name>Module(<ClientClassName> client) : ICarterModule
{
    public void AddRoutes(IEndpointRouteBuilder app)
    {
        var group = app.MapGroup("/<name>").WithTags("<TAG>");

        group.MapGet("/things/{id}", async (string id, CancellationToken cancellationToken) =>
            {
                var result = await client.GetThing(id, cancellationToken);
                return result.IsSuccess
                    ? Results.Ok(result.Value.ToThingResponse())
                    : CustomResults.Problem(result);
            })
            .Produces<ThingResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status404NotFound)
            .ProducesProblem(StatusCodes.Status500InternalServerError)
            .WithSummary("Get a thing by id")
            .WithDescription("Returns the thing registered under the given id in <SYSTEM>.");
    }
}
```

A SOAP module with per-operation URLs adds `IOptions<<ClientClassName>SoapEndpointOptions> options` to the constructor (`using Microsoft.Extensions.Options;`) and passes `options.Value.<Op>Url` to each client call.

Client injection (C5): the module is built once at `MapCarter()`, so a constructor-injected client lives for the process (build warning `CARTER1` — expected). Constructor injection is the convention for stateless clients, which every template above is. A client whose per-call state is mutated (`SetHeader`, `SetOptions`, `DefaultRequestHeaders`) is injected as a handler parameter instead: `async (string id, <ClientClassName> client, CancellationToken cancellationToken) => …`. So is a database repository (patterns §5).

Per pattern, on top of the module above:

- `per-caller` credentials — every group calls `.RequireAuthorization()` (patterns §2)
- `--proxy` — the catch-all goes in `Program.cs`, not in a module (patterns §3)
- `--aggregate` — the combined route goes in the module of its business domain (patterns §4)

Rules:

- `CustomResults.Problem(result)` is the only failure path — it turns `Error` into RFC 7807 `ProblemDetails` with the status from C2
- Declare responses in the APIS style: `.Produces<T>(StatusCodes.Status200OK)` (or `201`/`202`), one `.ProducesProblem(...)` per status the route's `Error`s can produce (C2), `.WithSummary`, `.WithDescription`
- `POST` that creates returns `Results.Created` with the created id
- Every handler takes `CancellationToken` and passes it down
- The `MapGroup` prefix is lowercase, leading-slash, and matches the module name: `NirModule` -> `MapGroup("/nir")`, so every route in the module reads `/nir/persons/{nrc}`. Resource segments go after the prefix, never in it
- When the module name equals the tenant's own gateway route (the IFMIS module in the `ifmis` tenant), use `MapGroup("")` — the gateway already adds `/t/<route>`, so `MapGroup("/ifmis")` doubles it to `/t/ifmis/ifmis/...`
- XML doc comments on public request/response types feed the generated API specification — write them

For a controllers-style tenant, put the equivalent in `Controllers/<Resource>Controller.cs` following `src/Tenants/MOA/Controllers/`.

**Gateway methods.** Set `match.methods` of the tenant's route in `src/Tenants/<TenantName>/GATEWAY-CONFIG.md` to every verb the tenant now maps, not just the new ones, with the verb grep in `integrate-shared` §6 — including the verbs a `*SharedModule` base contributes, which that grep can't see in the tenant's files. `tenant-init` left it at `GET`; a verb missing there answers 405 at the gateway. This runs with `--no-spec-ready` too.

The exposed surface is REST and JSON regardless of what the tenant consumes. A SOAP upstream stops at the client: never return an XML message type from a route, and never surface a SOAP `Fault` verbatim — `CustomResults.Problem` has already turned it into `ProblemDetails`.

## 7. Verify

```bash
dotnet build src/Tenants/<TenantName>/<TenantName>.csproj -v q --nologo
```

Must report `0 Error(s)` (`CARTER1` and `NU1903` warnings come from Core and existing modules). Then check, without running the app:

- Every `RestEndpoint` class has a matching `Endpoints:<Name>` section, and every `SoapEndpoint` class a `SoapEndpoints:<Name>` section, in **both** appsettings files — a missing one is a startup crash at `MapCarter()`
- Every `BaseUrl` is a valid absolute URL in `appsettings.Development.json`, and one that carries a path ends with `/`
- REST `AuthenticationScheme` is exactly `Basic`, `JWT`, `Custom`, `RA` or `None`; every SOAP section has `AuthenticationScheme` (`None` when there's no auth)
- `Timeout`, when set, is `hh:mm:ss`
- Every SOAP per-operation URL has an options property and a `__SoapEndpoints.<ClientClassName>.<Op>Url__` token in both files; no URL is hard-coded in a client or module
- Every token follows C4 and `Username` casing follows C3; every new token is listed in the report
- REST clients call only `*Async` base methods, and deserialize with the tenant's `jsonOptions.Value`
- No SOAP client calls `Client.SetHeader`; `SOAPAction` is on a per-request message. Any client with mutable state is injected as a handler parameter
- `Program.cs` calls the registrar for each kind of client the tenant actually has — `RegisterEndpoints`, `RegisterSoapEndpoints`, or both — and binds each `<ClientClassName>SoapEndpointOptions`
- Every SOAP client's constructor takes `HttpClient` alone
- Each SOAP call wraps and validates the same version the WSDL binding declares (11 with 11, 12 with 12)
- Every mapper initializer assigns every settable target property
- No real credential appears in either file (C7)
- Every exposed route declares its success type and one `ProducesProblem` per reachable failure status
- `match.methods` in `GATEWAY-CONFIG.md` lists every verb the tenant maps
- An upstream reached through the gateway goes through `Endpoints/Gateway.cs` and `Endpoints:Gateway`, never a second client and section with its own gateway credentials
- The `## Upstream scopes` section of `GATEWAY-CONFIG.md` has a row for every `t/<route>/…` path the tenant calls, through `Endpoints/Gateway.cs` or `EServicesShared`, and no row for a path it no longer calls (C12)
- No upstream DTO — JSON or XML — is returned directly where a public DTO was defined

After a promotion (step 1b) — the **parity gate**. Export the tenant's Swagger the way `tenant-deliverables` step 4 does, strip `/t/<slug>` from the baseline's paths, and compare every baseline operation: path, verb, each parameter (`name`, `in`, `required`, schema), request body schema, success status and schema, enum representation, failure statuses. Every baseline operation must be there, unchanged. Two differences are allowed: the new integration's operations, and failure statuses that step 8 now documents where the host returned them without declaring them (report each one). Anything else is a failure: fix the code, never the baseline. In gate mode the last line is then `GATE-RESULT: failed parity <METHOD> <path>`. Also check:

- No promoted route calls `RequireAuthorization()`, and none is under a base path
- The HTTP JSON options equal the host's, enum converter included
- `GATEWAY-CONFIG.md` holds no route with a `clusterId` other than `<TENANT>`, `t_<slug>` has the virtual scope, and the cutover section names every old route id
- `src/VirtualTenants/<CODE>/` is still there

When the pass used a pattern from `references/upstream-patterns.md`:

- `Login` — every operation goes through `SendAuthorizedAsync`, none through `GetAsync`/`PostAsync`; the token is set per request, never on `DefaultRequestHeaders`; `JwtOptions` holds literal integers in both files; no log line carries a credential or a token
- `per-caller` — credentials keyed on `User.Identity.Name`, never on the `IdentityName` header; `UseAuthentication`/`UseAuthorization` present and every group requires authorization; `CacheOptions:Users:ExpirationInSeconds` is a positive literal in both files
- `--proxy` — `UseRestExceptionHandler()` is registered before the catch-all `Map`; no path rewriting
- `--aggregate` — every source returns `Result` without throwing; `CacheOptions:<Name>:ExpirationInSeconds` is a positive literal in both files
- Database — `ConnectionStrings:<System>` is top-level in both files with a `__ConnectionStrings.<System>__` placeholder; every query is parameterized; the repository is a handler parameter
- GraphQL — every query is a `const` with variables; `errors` is checked before `data`

`/tenant-audit <TenantName>` runs the configuration and secrets checks for you.

## 8. Make the surface spec-ready

Skipped with `--no-spec-ready`, and then the report names every item below that is still unmet.

The delivery documents (`/tenant-deliverables <TenantName>`) are generated from the tenant's own Swashbuckle document, so they are only as good as the metadata already in the code. It is far cheaper to add that metadata now, while the routes and DTOs are being written, than as a separate pass later.

A tenant scaffolded by `tenant-init` already has the project-level half: `GenerateDocumentationFile`, `Swagger/OpenApiDocumentation.cs`, and `AddSwaggerGen` with `OpenApiInfo`, the Basic security scheme and `IncludeXmlComments`. Check it is there, and add whatever is missing on an older tenant. `src/Tenants/APIS` is the reference for each item below — its Swagger metadata, not its folder layout.

**Project** — `src/Tenants/<TenantName>/<TenantName>.csproj`:

```xml
<GenerateDocumentationFile>true</GenerateDocumentationFile>
<NoWarn>$(NoWarn);CS1591</NoWarn>
```

**Swagger folder** — put the narrative content and any custom `IOperationFilter` / `ISchemaFilter` in `src/Tenants/<TenantName>/Swagger/`, namespace `<TenantName>.Swagger`. Not loose at the project root: these are OpenAPI-generation concerns, not application logic. See `src/Tenants/APIS/Swagger/OpenApiDocumentation.cs` and `ProblemResponseOperationFilter.cs`, and `src/Core/Shared/Swagger/PaginatedResultSchemaFilter.cs`.

**`Program.cs`** — `AddSwaggerGen` with a populated `OpenApiInfo` and `IncludeXmlComments`:

- `Title` must be `"{full descriptive name} ({TENANT})"` — e.g. `"Advance Passenger Information System (APIS)"`. The DOCX cover renders the role separately, so `Title` carries no role word. When the scaffold left the bare code because the name was `pending`, write the name chosen in the proposal call now.
- `Description` is the **only** source of narrative prose in the generated DOCX. Shape it as the repo's `api-spec-sync` expects: one intro paragraph (the Executive Summary) plus a `## Glossary` table — nothing else. Extend the scaffolded sentence with what this integration adds: the system it reaches and the datasets its routes expose ("Pesticide registrations and ePhyto validation from the PQPS Plant Health system"). State only what a route actually provides. Extra `##` sections are only for protocol-level complexity, as APIS does for PAXLST.

**Routes** — on every route generated in step 6, the APIS set:

- `.WithTags("...")` — required. The Postman step folders requests by tag; untagged operations collapse into one undifferentiated list
- `.WithSummary(...)` and `.WithDescription(...)` — these become the endpoint table entries
- `.Produces<T>(StatusCodes.Status200OK)` and `.ProducesProblem(StatusCodes.Status4xx/500…)` — already required by step 6; they populate the response tables
- Optional: `.WithMetadata(new ProblemResponseDescriptions("…400 prose…", "…500 prose…"))` to replace the bare reason phrases. Copy `ProblemResponseOperationFilter.cs` (record + filter) from APIS into `<TenantName>.Swagger`, register `options.OperationFilter<ProblemResponseOperationFilter>();` in `AddSwaggerGen`, and add a record member for any other status (404) the tenant describes — APIS's record covers 400 and 500 only

**DTOs** — `///` XML doc comments on every public property of every request and response type the tenant declares. They become the schema tables verbatim.

**Never use `<see cref="..."/>` in those comments.** Swashbuckle does not resolve cref targets; it emits the raw fully-qualified type name as literal text ("See APIS.Paxlst.MessageKind."). Write plain prose.

The documents themselves are step 6 of `tenant-pipeline` (`/tenant-deliverables <TenantName>`). Don't generate them here. The ZamConnect repository also has a repo-local `/api-spec-sync` for a quick developer-side regeneration; it reads the same metadata. Its `api-docs-auditor` agent watches only `Modules/`, so a controllers-style tenant's changes aren't flagged — say so in the report.

## 9. Another integration?

Tenants often reach more than one upstream (`MCTI` → ZABS + ZMA, `MLSS` → four systems). Unless `--auto` is set, ask with header `Next`.

Untyped passes:

- `Done — continue (Recommended)`
- `Add another integration source` — back to step 1 for the next upstream. Keep what's been built, and skip anything already answered for this tenant, such as the full name
- `Add a combined route over existing operations` — only when the tenant now has at least two read operations across its clients and repositories. Asks the patterns §4 call, then its own R6 review, and comes back to this question

Typed passes stay on the current protocol until the developer ends it. The question text lists what that protocol has so far and what comes next:

```
TT — REST so far: Zims. SOAP is next.
  ( ) Add another REST API           back to step 1, REST source question
  ( ) Done with REST — go to SOAP    starts the first SOAP pass (Recommended)
```

On the last protocol in the queue (or the only one), the second option is `Done with SOAP — continue (Recommended)`, which ends the skill. The combined-route option is offered there too, once, after the last protocol. `Add another …` keeps what's been built and skips anything already answered for this tenant, such as the full name. Under `--auto`, every `--source` of a protocol gets its own pass and nothing is asked.

Each pass gets its own client, config section, models and module, and the report covers all passes, grouped by protocol.

## Report

State the upstream system(s) and their base URL, one line per file added or changed, and a table of the exposed routes (method, `/t/<route>/…` path, purpose). Name the spec-readiness items from step 8 that are still unmet, if any. Then list the entries added to or removed from `ENVIRONMENT-VARIABLES.json` (names only, never a value), and what an administrator does by hand (C10): add those variables to each environment, import `GATEWAY-CONFIG.md` into each gateway (locally that is `/tenant-audit <TenantName> --only runtime`), grant `Credentials.<TenantName>Tenant` the scopes of its `## Upstream scopes` section (C12) when the tenant calls back into the gateway, and register any RA / ZamPass client. `ENVIRONMENT-VARIABLES.json` and `GATEWAY-CONFIG.md` are not in git (C10): the engineer sends them to the administrator directly.

After a promotion, the report opens with it: the host, the baseline, the parity result per operation, and the cutover from `GATEWAY-CONFIG.md` — the upstream scopes to grant the tenant's gateway user and the old route ids to delete in each gateway, in that order, after the deploy and the import. Consumers change nothing. Locally, the Docker `mongo` may still hold the old routes from an earlier `tenant-audit` Check V: they shadow `t_<slug>` there too, so name them for deletion before `/tenant-audit <T> --only runtime`. Name `/tenant-tests <T>` next: its tests for the promoted routes assert the baseline's statuses and JSON property names.

The administrator list grows with the patterns used: the gateway users of a `per-caller` map and the `MongoDB.*` variables (§2), and for a database the connection-string variable per environment and a network path from the cluster to the database server (§5). Name the operations reachable only through the catch-all proxy: they are not in Swagger, so the delivery documents leave them out (§3).

Close with the equivalent command for each pass (R7) — with `--protocol` set to that pass's protocol — and these answers for the pipeline state, one entry per pass: `protocol` (`rest`, `soap`, `graphql` or `db`), `sources`, `system`, `auth`, `role`, plus `fullName` if it was settled here, and whichever apply: `loginPath`, `credentials`, `callers`, `proxy`, `dbAccess`, `dbWrites`. Each combined route is one more entry: `{ "aggregate": "<GET /path>=<Client.Method>+…", "shape", "cache" }`. A promotion is one more entry too: `{ "promotion": "<host> <prefix>", "baseline": "<path>", "operations": [<METHOD /path>…], "scope", "oldRoutes": [<route id>…], "parity": "passed" }`. A protocol skipped with `Skip <protocol> for now` is reported as skipped. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <reason>` when the build in step 7 fails.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder — in `appsettings.Development.json` too. List its name in `ENVIRONMENT-VARIABLES.json` (C9) with an empty value, and leave the value out. Never write a registry, Helm, cluster, MongoDB, RA or ZamPass address (C10).
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Many tracked `appsettings.Development.json` files and `src/Tenants/Certificates/*.p12` do (C7): never carry them forward, never use another tenant's Development file as the template for credential values, and report what you noticed as a finding, not a value to reuse. Rotation is a separate ticket.
