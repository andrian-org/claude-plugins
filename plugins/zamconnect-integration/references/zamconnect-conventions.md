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
Routes often differ from the tenant name — look them up rather than guessing.

## C9 — `ENVIRONMENT-VARIABLES.json`

One file per tenant, `src/Tenants/<Folder>/ENVIRONMENT-VARIABLES.json`, committed. It lists the **names** of
every variable a deployment of the tenant reads. An administrator adds them by hand to each environment. It
never holds a secret value or a host address.

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

## C10 — Local-only scope

Every skill works on the local repository and the local Docker compose stack only.

- **Pipelines.** A skill writes the `.azure/tenant.azure-pipelines.<slug>.yaml` file. It never creates an Azure
  DevOps pipeline definition, never queues a run, never touches an ADO environment or service connection.
- **Variables.** A skill writes `ENVIRONMENT-VARIABLES.json` (C9). It never creates or edits a variable group,
  never calls `az pipelines variable-group`, never writes to a `projects-variables` repository.
- **Gateway.** A skill writes `GATEWAY-CONFIG.md` in the tenant folder. It is applied only to the local Docker
  `mongo` (`tenant-audit` Check 9). A skill never calls the AdminAPI, and never writes to a database, of a DEV,
  test, staging or production gateway. The administrator imports the file there by hand.
- **ZamPass / RA clients.** Registered by hand by an administrator. A skill writes only the `__Token__`
  placeholders the client's values go into, and lists them in C9.
- **No addresses.** Never write into any file, state or report the address or credential of a container
  registry (Harbor), a Helm repository, a Kubernetes cluster, a MongoDB instance, the Registration Authority,
  ZamPass or Hydra. The only addresses skills write are the local compose ones (`http://gateway/`,
  `http://core-<slug>`, `localhost`) and the public gateway base URLs the deliverables document.
