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
the `GSB.<TENANT>.<ENV>` group **and** in the `projects-variables` repo, or the deploy fails.

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

## C8 — Live route reference

`docs/zamconnect-test-routes.md` lists every live gateway route, cluster and scope. Conventions it shows:
route `t_<slug>`, `clusterId` = uppercase tenant, `authorizationPolicy: "Basic"`, `metadata.Scope` = slug.
Routes often differ from the tenant name — look them up rather than guessing.
