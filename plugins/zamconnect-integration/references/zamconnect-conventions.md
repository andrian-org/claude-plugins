# ZamConnect conventions

Facts every zamconnect-integration skill that generates code or config relies on. Each skill links here
instead of restating them. Paths are relative to the ZamConnect repository root.

Never trust a count in this file or in a skill — re-derive it with the command shown.

## C1 — C# templates: usings, namespace, nullability

`ImplicitUsings` is off in most tenants and in the `tenant-init` scaffold. Check before generating:

```bash
grep -l "<ImplicitUsings>enable" src/Tenants/*/*.csproj
grep -l "<Nullable>enable" src/Tenants/*/*.csproj
```

- Every generated `.cs` file carries its full `using` block, sorted alphabetically with `System*` first, and a
  file-scoped namespace: `namespace <T>.Endpoints;`, `<T>.Modules;`, `<T>.Mapper;`, `<T>.Models.<SYSTEM>;`.
- Where the csproj has `<Nullable>enable</Nullable>`, use `string?` / `T?` for optional members; elsewhere don't.
- A missing `using` is a build error, not a warning. Build after writing.

## C2 — `Error` → HTTP status

`src/Core/Internal/Domain/Shared/Result/Error.cs`, mapped by `CustomResults.Problem` on `ErrorType`
(`CustomResults.cs`, `GetStatusCode`):

| Factory | `ErrorType` | Status | Use for |
|---|---|---|---|
| `Error.BadRequest(code, desc)` | `Validation` | 400 | Rejected input, business-rule violation the caller can fix |
| `Error.NotFound(code, desc)` | `NotFound` | 404 | Missing resource |
| `Error.Conflict(code, desc)` | `Conflict` | 409 | Duplicate / state conflict |
| `Error.NotImplemented()` | `NotImplemented` | 501 | Stub |
| `Error.Problem(code, desc)` | `Problem` | **500** | Upstream failure whose code the caller should see |
| `Error.Failure(...)`, `Error.Internal()`, `Error.NullValue` | `Failure` | 500 | Anything unexpected |

`Error.Problem` is **not** a 4xx. `CustomResults.Problem(result)` is the only path that yields
`application/problem+json`.

## C3 — Config key casing

JSON keys and tokens are always `Username`; the C# options property is `UserName`; binding is
case-insensitive. Never write `UserName` into JSON or a token.

## C4 — Token naming

`replacetokens` runs with `actionOnMissing: fail`: every `__Token__` in `appsettings.json` needs a variable in
the tenant's environment variables, or the deploy fails. Skills never create those variables; they list every
one in `src/Tenants/<Folder>/ENVIRONMENT-VARIABLES.json` (C9) and an administrator adds them by hand.

| Upstream | Section | Tokens |
|---|---|---|
| The ZamConnect gateway (tenant calling back in) | `Endpoints:Gateway` (or the tenant's gateway client) | `__Endpoints.APIGATEWAY.BaseUrl__`, `__Credentials.<Folder>Tenant.Username__`, `__Credentials.<Folder>Tenant.Password__` |
| External REST | `Endpoints:<ClientClassName>` | `__Endpoints.<ClientClassName>.BaseUrl__`, `.Username__`, `.Password__`, `.ApiKey__` |
| SOAP | `SoapEndpoints:<ClientClassName>` | `__SoapEndpoints.<ClientClassName>.BaseUrl__`, `.Username__`, `.Password__`, one `.<Op>Url__` per operation URL |

`<Folder>` is the exact tenant folder name. Reference: `src/Tenants/APIS/appsettings.json`
(`ZimsApi`, `MihudPamsApi`, `NpddApi`, `PoApi`).

## C5 — Carter DI and client lifetime

`ICarterModule` instances are built once, at `MapCarter()`. A client injected through the module
constructor is captured for the process lifetime even when registered transient (build warning `CARTER1`).

- Stateless clients: constructor injection is the repo convention — keep it.
- A client whose per-call state is mutated (`SetHeader`, `SetOptions`, `DefaultRequestHeaders`) must be
  injected as a **handler parameter** (`async (string id, <Client> client, CancellationToken ct) => …`), or
  the mutation must move to a per-request `HttpRequestMessage`.
- Tests: mutate the mock handler's `Handler` delegate, never replace the handler object.

## C6 — File hygiene

`.editorconfig` asks for CRLF and UTF-8 BOM on `.cs`. `core.autocrlf` fixes line endings on commit; BOM is
optional (APIS has none). Don't rewrite existing files just to change either.

## C7 — Committed secrets baseline

Many tracked `appsettings.Development.json` files commit literal credentials, and
`src/Tenants/Certificates/*.p12` is committed. Re-derive the count:

```bash
grep -liE '"[^"]*(user_?name|password|api_?key|secret|token|thumbprint|private_?key|connection_?string)"[[:space:]]*:[[:space:]]*"[^_"][^"]*"' src/Tenants/*/appsettings.Development.json | wc -l
```

- Never copy a value from one of those files, and never use a tenant's Development file as the template for
  credential values. Generated Development files keep `__Token__` placeholders for credentials; only a test
  `BaseUrl` may be real.
- `tenant-audit` reports them as a baseline count (warn), never printing a value. Rotation is a separate
  ticket, not skill work.
- Credential suffixes: `user_?name`, `password`, `secret`, `token`, `thumbprint`, `connection_?string`, `key`
  (`ApiKey`, `PrivateKey`, `PublicKey`), `authheadervalue`.

## C8 — Live route reference

`docs/zamconnect-test-routes.md` lists every live gateway route, cluster and scope. Conventions it shows:
route `t_<slug>`, `clusterId` = uppercase tenant, `authorizationPolicy: "Basic"`, `metadata.Scope` = slug.
Routes often differ from the tenant name — look them up rather than guessing. A route whose cluster is not
the slug's own tenant is a cross-cluster route (C11). The doc shows no transforms.

## C9 — `ENVIRONMENT-VARIABLES.json`

One file per tenant, `src/Tenants/<Folder>/ENVIRONMENT-VARIABLES.json`. It is **local only**: git ignores it,
and it is never committed (C10, "Not committed"). It lists the **names** of every variable a deployment of the
tenant reads. The engineer sends the file to an administrator, who adds the variables by hand to each
environment. It never holds a secret value or a host address.

```json
{
    "tenant": "<Folder>",
    "environments": ["DEV", "STG", "PROD"],
    "variables": [
        { "name": "helmReleaseName", "secret": false, "value": "<slug>", "description": "Kubernetes service core-<slug>. Must equal the compose slug and the GATEWAY-CONFIG.md cluster address" },
        { "name": "helmNamespace", "secret": false, "value": "", "description": "Kubernetes namespace. Set by the administrator" },
        { "name": "OTEL_SERVICE_NAME", "secret": false, "value": "core-<slug>", "description": "Trace service name" },
        { "name": "OTEL_EXPORTER_OTLP_ENDPOINT", "secret": false, "value": "", "description": "OTLP collector. Unset means no traces are exported" },
        { "name": "Endpoints.<ClientClassName>.BaseUrl", "secret": false, "value": "", "description": "<System> base URL for the environment" },
        { "name": "Endpoints.<ClientClassName>.Password", "secret": true, "value": "", "description": "<System> password" }
    ]
}
```

- `name` is the `__Token__` without the surrounding `__`. 4-space indent. Entries are sorted: the four
  deployment variables first, in the order above, then the tokens in the order they appear in `appsettings.json`.
- `value` is filled only when it is identical in every environment and is not a secret or a host:
  `helmReleaseName` and `OTEL_SERVICE_NAME`. Everything else is `""`.
- `secret: true` for every credential key (C7's suffix list: username, password, API key, secret, token,
  thumbprint, private/public key, connection string, `AuthHeaderValue`).
- `tenant-init` creates it. `tenant-integration` and `integrate-shared` add an entry for every token they write
  and remove the entry of a token they delete. `tenant-audit` Check 4 checks that the file and the tokens in
  `appsettings.json` match exactly.
- A fresh clone has no copy, because git does not carry it. `tenant-audit` Check 4 regenerates it from the
  tokens in `appsettings.json`.

## C10 — Local-only scope

Every skill works on the local repository and the local Docker compose stack only.

- **Pipelines.** A skill writes the `.azure/tenant.azure-pipelines.<slug>.yaml` file. It never creates an Azure
  DevOps pipeline definition, never queues a run, never touches an ADO environment or service connection.
- **Variables.** A skill writes `ENVIRONMENT-VARIABLES.json` (C9). It never creates or edits a variable group,
  never calls `az pipelines variable-group`, never writes to a `projects-variables` repository.
- **Gateway.** A skill writes `GATEWAY-CONFIG.md` in the tenant folder, or in `src/VirtualTenants/<CODE>/` for a
  virtual tenant (C11). It is applied only to the local Docker
  `mongo` (`tenant-audit` Check 9). A skill never calls the AdminAPI, and never writes to a database, of a DEV,
  test, staging or production gateway. The administrator imports the file there by hand.
- **ZamPass / RA clients.** Registered by hand by an administrator. A skill writes only the `__Token__`
  placeholders the client's values go into, and lists them in C9.
- **No addresses.** Never write into any file, state or report the address or credential of a container
  registry (Harbor), a Helm repository, a Kubernetes cluster, a MongoDB instance, the Registration Authority,
  ZamPass or Hydra. The only addresses skills write are the local compose ones (`http://gateway/`,
  `http://core-<slug>`, `localhost`) and the public gateway base URLs the deliverables document.

### Not committed

The handoff files describe environment setup that an administrator applies by hand. They stay on the
engineer's machine and go to the administrator directly, never through git:

| File | Written by |
|---|---|
| `src/Tenants/<Folder>/ENVIRONMENT-VARIABLES.json` (C9) | `tenant-init`; entries added by `tenant-integration`, `integrate-shared`, `payment-callback` |
| `src/Tenants/<Folder>/GATEWAY-CONFIG.md` | `tenant-init`; routes and methods added by `integrate-shared` |
| `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md` (C11) | `integrate-shared --mode virtual` |

A skill that creates one of these files makes sure the repository root `.gitignore` holds this block. It
appends only the missing lines and never rewrites or reorders the rest of the file:

```gitignore
# zamconnect-integration handoff files: local only
src/Tenants/*/ENVIRONMENT-VARIABLES.json
src/Tenants/*/GATEWAY-CONFIG.md
src/VirtualTenants/*/GATEWAY-CONFIG.md
```

A `.gitignore` line does not untrack a file that git already tracks. A skill never runs `git add`, `git rm` or
`git commit`. `tenant-audit` Check 4 reports a tracked handoff file with the `git rm --cached <path>` command
for the engineer to run.

Other configuration, checked against the same rule:

| File | In git | Why |
|---|---|---|
| `appsettings.json` | Yes | The build reads it, and the deploy publishes it as the settings artifact. Tokens only, no values (C4) |
| `appsettings.Development.json` | Yes | Local runs and the test factories load it. Credentials stay `__Token__` placeholders (C7) |
| `.azure/tenant.azure-pipelines.<slug>.yaml` | Yes | The Azure DevOps pipeline definition reads it from the repository |
| `Properties/launchSettings.json`, compose service, `ZamConnect.sln` entry | Yes | Build and local run inputs, with no environment values |
| `appsettings.local.json` | No | Real credentials for `tenant-tests --live`. Already ignored |
| `.claude/zamconnect/` | No | Pipeline state. The directory carries its own `.gitignore` (`*`) |

## C11 — Virtual tenants and cross-cluster routes

A **cross-cluster route** is a gateway route under one slug (`/t/<slug>/…`) whose `clusterId` is the cluster
of another tenant, the **host**. A `PathPattern` transform maps the request onto a path prefix the host
already serves. A **virtual tenant** is an agency made only of such routes. It has a scope and routes, and no
project and no cluster of its own. The host serves every request.

Live precedents (re-derive with `grep -nE '\| GOVZM \|' docs/zamconnect-test-routes.md | grep -v '/t/govzm/'`):

| Route | Path | Cluster | Transform | Scope | Case |
|---|---|---|---|---|---|
| `t_ccpc_eservices` (also `t_dam_…`, `t_miwd_…`, `t_zema_…`) | `/t/ccpc/{**url}` | `GOVZM` | `/eservices/{**url}` | `ccpc` | Virtual tenant, catch-all |
| `zigsapi_eservices_person_by_nrc` | `/t/zigs/nir/persons/nrc/{**url}` | `GOVZM` | `/eservices/nir/persons/nrc/{**url}` | `zigsapi` | Virtual tenant, per path |
| `t_pqps_eservices_nir_persons` (also `t_rtsa_…`, `t_pacra_…`) | `/t/pqps/nir/persons/{**url}` | `GOVZM` | — | `pqps` | Sub-route of a real tenant: `t_pqps` → `PQPS` owns `/t/pqps/{**url}` |
| `t_ccpc_ndr` | `/t/ccpc/document/{**url}` | `NDR` | — | `ndr` | Same pattern, another host |

The routes doc shows no transforms. The `t_ccpc_eservices` and `zigsapi_*` transforms come from the exported
route config.

### When to use it

| Situation | Answer |
|---|---|
| The agency has no system of its own to integrate, and a host already serves everything it needs | Virtual tenant. For shared e-Services the host is `GOVZM` (`integrate-shared` §4a) |
| A real tenant also needs a host's surface, unchanged | Cross-cluster sub-routes in the tenant's own `GATEWAY-CONFIG.md` |
| The agency needs its own contract: own DTOs, validation, combined calls, other paths, or operations the host doesn't serve | A real tenant (`tenant-init`, then `tenant-integration` / `integrate-shared` in code) |

A cross-cluster route forwards the host's contract as it is: the same paths below the prefix, the same
bodies, the same errors. Nothing in the repo is generated for it except the gateway package.

### Route shapes

| Shape | Route `name` / `routeId` | `match.path` | `PathPattern` | `order` | Use when |
|---|---|---|---|---|---|
| Catch-all | `t_<slug>_<surface>` | `/t/<slug>/{**url}` | `<prefix>/{**url}` | `1` | The agency takes every route the host serves under `<prefix>`, and no other tenant owns `/t/<slug>/{**url}` |
| Per path | `t_<slug>_<surface>_<path segments joined by _>` | `/t/<slug>/<path>/{**url}` | `<prefix>/<path>/{**url}` | none | A subset, or a real tenant already owns `/t/<slug>/{**url}` |

- `<surface>` names the host's surface: `eservices` for `GOVZM` `/eservices`. For another host, use the last
  segment of its prefix, or else the host cluster id lowercased (`ndr`).
- `order: 1` on the catch-all: YARP prefers the lower `order`, so a sibling route of the same slug with the
  default order (`t_ccpc_ndr` on `/t/ccpc/document/{**url}`) still wins. Per-path routes need no `order`: a
  longer literal path wins over `/t/<slug>/{**url}` by route precedence.
- Two routes with the same `match.path`, a shared verb and the same `order` make the gateway answer 500
  (ambiguous match).
  Before writing, list every route of the slug: `grep -n '/t/<slug>/' docs/zamconnect-test-routes.md`, plus
  `src/Tenants/*/GATEWAY-CONFIG.md` and `src/VirtualTenants/*/GATEWAY-CONFIG.md`.
- A per-path route also shadows a route the slug's own tenant serves under the same path. Check the tenant's
  modules for that path before you add the route.

### Fields

| Field | Value |
|---|---|
| `clusterId` | The host's cluster id, exactly as the routes doc shows it (`GOVZM`). Never `<SLUG>` |
| `authorizationPolicy` | `Basic` |
| `metadata.Scope` | `<slug>` by default. An agency that already uses a scope on another slug keeps it, and gets no second scope (live: `deeds`, `lands`, `survey` → `zilas`; `vcs`, `vrs` → `miwd`). A sub-route of a real tenant uses that tenant's scope |
| `match.methods` | Only the verbs the host maps under the forwarded path. For a per-path route, only the verbs of the operations picked under that path |
| `transforms` | `[{ "PathPattern": "<prefix>/<path>/{**url}" }]`. `<prefix>` must be a route group the host maps: check the host's modules for `MapGroup("<prefix>")` or the base-path argument of its shared module |

The consumer's gateway user gets the virtual tenant's scope only. It does not need the host's own scope
(`govzm`). The host reaches its own upstreams with its own `Endpoints:Gateway` user and scopes.

**Exposure.** A route forwards every host route below its path for the verbs it lists, not only the operations
that were picked. List in the review every host operation each route reaches. When a broader route would reach
an unpicked operation with the same verb, split it into deeper paths (the `zigsapi_*` routes). When no literal
segment separates two operations (`PATCH /nir/persons/{id}` and `PATCH /nir/persons/zampass/{zamPassId}`), say
in the review that both are reachable.

### Handoff file

| Case | File | `clusters` |
|---|---|---|
| Virtual tenant | `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md`. `<CODE>` is the agency code in upper case (`CCPC`), `<slug>` the same in lower case | `[]` |
| Sub-route of a real tenant | Add the routes to `routes[]` of `src/Tenants/<T>/GATEWAY-CONFIG.md` | The tenant's own cluster only |

- Never list the host cluster in a package. `POST /Import/routes` overwrites a cluster with the same id, so
  the import would replace the live host cluster. Without it, the import checks that the host cluster exists
  and rejects the route otherwise: `Route '<id>' references cluster '<host>' which does not exist.`
- Never write a virtual tenant's file under `src/Tenants/`. The skills read a folder there as a tenant
  (`tenant-init` refuses the name), and the host's folder already holds the host's own `GATEWAY-CONFIG.md`.
- A virtual tenant gets no project, solution entry, compose service, Azure pipeline file,
  `ENVIRONMENT-VARIABLES.json` or test project. Nothing is deployed for it.
- Its folder holds `GATEWAY-CONFIG.md`, which is local only (C10, "Not committed"), and, once
  `tenant-deliverables` has run, `Deliverables/`. The document is the host's contract for the operations the
  routes reach, at the consumer's paths (`tenant-deliverables` step 4).
- Locally, `tenant-audit <CODE>` applies the package to the local Docker `mongo` and calls each route through
  the local gateway (its Check V).
