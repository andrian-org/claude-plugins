# Upstream patterns beyond plain REST and SOAP

Read the section a pass needs, only when it needs it. Each section adds to the `SKILL.md` steps; anything
not mentioned here (usings and namespace C1, `Error` → status C2, `Username` casing C3, token naming C4,
Carter lifetime C5, `ENVIRONMENT-VARIABLES.json` C9, spec readiness step 8) applies unchanged.

| § | Pattern | Flag | Repo precedents |
|---|---|---|---|
| 1 | Token-login upstream: log in, cache the token, refresh it, retry once on 401 | `--auth Login` | ZRA, NAPSA, WCF, NHIMA, ZESCO |
| 2 | Per-caller upstream credentials, picked by the authenticated gateway user | `--credentials per-caller` | ZRA, NHIMA |
| 3 | Catch-all proxy: every route the tenant doesn't map goes to the upstream unchanged | `--proxy` | SRS, DOC, MMMD, ZIMS, NLR, RTSA |
| 4 | Aggregate route: one tenant route fans out to several upstream operations, with a typed cache | `--aggregate`, `--cache` | ZamMobile, GOVZM |
| 5 | Database upstream (SQL Server) | `--source db[=<path>]` | ZamData (Dapper), NDP and NDW (EF Core) |
| 6 | GraphQL upstream | `--source graphql[=<url\|path>]` | `EServicesShared`, ZamMobile `Nir`, NDW |

Every existing copy of these patterns has defects (shared `DefaultRequestHeaders` raced across callers,
`.Result` inside `lock`, credentials and tokens logged, 401 handling that never runs, partial failures that
crash the request). The templates below are the corrected shapes. Never copy a precedent's code forward;
read it only for the upstream's request and response shapes.

## 1. Token-login upstream — `--auth Login`

The upstream issues a token from a login call, and every other call sends it as `Bearer`. `Login` is
not a `RestEndpoint` scheme: the client logs in itself, and its config section says
`"AuthenticationScheme": "None"` so `RegisterEndpoints` adds no header of its own.

### Detection

| Signal in the source | Read as |
|---|---|
| A request or path named `login`, `token`, `auth`, `access_token`, `api-login` that returns `accessToken` / `access_token` / `token`, and later requests carry `Authorization: Bearer {{…}}` | `Login`, `LoginPath` = that path |
| A request named `refresh` taking `refreshToken` / `refresh_token` | `RefreshTokenPath` = that path |
| OpenAPI `securitySchemes` of type `http` / `bearer` plus a login operation in `paths` | `Login` |
| OpenAPI `oauth2` with `flows.password` or `flows.clientCredentials` | `Login`, `LoginPath` = `tokenUrl`, form-encoded body |
| Prose: "obtain a token", "authenticate first", "token expires in" | `Login`; echo it (R11) and confirm in the proposal `Auth` question |

From the login request take: the body fields and their encoding (JSON or `application/x-www-form-urlencoded`),
any extra login headers (NAPSA sends `grantType`, `scope`, `clientId`). From the login response take: the
envelope (`data` wrapper or root), the token field names, and how expiry is given (`expiresIn` /
`expires_in` seconds, `duration` minutes, `expires_at` timestamp, or nothing — then the JWT `exp` claim).

Asked only when detection leaves it open: header `Login`, "Login path for `<System>`? Type it in Other", with
the candidate paths found in the source as options. Flag `--login-path <path>`.

### Config

Both appsettings files. `LoginPath` and `RefreshTokenPath` are literal relative paths (no leading `/` when
`BaseUrl` carries a path, step 3), not tokens: they are the same in every environment.

```json
"Endpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "None",
        "BaseUrl": "__Endpoints.<ClientClassName>.BaseUrl__",
        "LoginPath": "auth/login",
        "RefreshTokenPath": "auth/refresh",
        "Username": "__Endpoints.<ClientClassName>.Username__",
        "Password": "__Endpoints.<ClientClassName>.Password__"
    }
},
"JwtOptions": {
    "AccessTokenExpirationMinutes": 1,
    "RefreshTokenExpirationMinutes": 1
}
```

- Leave `RefreshTokenPath` out when the upstream has no refresh call. NAPSA's refresh path equals its login
  path, which is a login, not a refresh.
- `JwtOptions` (`Internal.Domain.JwtRemoteClientAuthentification`) is one top-level section per tenant. The
  values are safety margins in minutes, subtracted from the upstream's lifetimes. Literal integers, never
  tokens: a placeholder fails binding at the first login. Keep the margin below the upstream's token lifetime,
  or every call logs in again.
- Other login fields (`InstitutionCode`, `ClientId`, `ClientSecret`, `GrantType`, `Scope`) go in the same
  section as `__Endpoints.<ClientClassName>.<Key>__` tokens, read with `configuration["Endpoints:<ClientClassName>:<Key>"]`.
  Any key matching C7's suffix list is `secret: true` in `ENVIRONMENT-VARIABLES.json`.

`Program.cs`, beside `RegisterEndpoints`:

```csharp
builder.Services.AddMemoryCache();
builder.Services.Configure<JwtOptions>(builder.Configuration.GetSection(nameof(JwtOptions)));
```

with `using Internal.Domain.JwtRemoteClientAuthentification;`.

### Client — `Endpoints/<ClientClassName>.cs`

`RegisterEndpoints` builds REST clients with `ActivatorUtilities`, so the extra constructor arguments resolve
from DI. **`GetAsync`, `PostAsync`, `PutAsync`, `PatchAsync` and `DeleteAsync` call `Client.SendAsync`
directly and bypass any override** — every operation of a login client goes through `SendAuthorizedAsync`
below, with a factory that builds a fresh `HttpRequestMessage` (a sent message can't be re-sent on retry).

```csharp
using System;
using System.Net;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Internal.Clients;
using Internal.Domain.Exceptions;
using Internal.Domain.JwtRemoteClientAuthentification;
using Internal.Domain.Shared.Result;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Options;
using Serilog;
using <T>.Models.<SYSTEM>;

namespace <T>.Endpoints;

public class <ClientClassName>(
    HttpClient client,
    IOptions<JsonSerializerOptions> jsonOptions,
    IOptions<JwtOptions> jwtOptions,
    IMemoryCache cache,
    IConfiguration configuration) : RestEndpoint(client)
{
    private const string CacheKey = "<ClientClassName>_token";
    private static readonly SemaphoreSlim TokenGate = new(1, 1);

    private readonly RestEndpointOptions _options =
        configuration.GetSection("Endpoints:<ClientClassName>").Get<RestEndpointOptions>();

    public async Task<Result<ThingDto>> GetThing(string id, CancellationToken cancellationToken)
    {
        try
        {
            using var response = await SendAuthorizedAsync(
                () => new HttpRequestMessage(HttpMethod.Get, $"things/{WebUtility.UrlEncode(id)}"),
                cancellationToken);

            switch (response.StatusCode)
            {
                case HttpStatusCode.OK:
                    var model = await response.Content.ReadFromJsonAsync<ThingDto>(jsonOptions.Value, cancellationToken);
                    return model is null
                        ? Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"))
                        : Result.Success(model);

                case HttpStatusCode.NotFound:
                    return Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"));

                default:
                    Log.Error("Unexpected response from <SYSTEM> API: {StatusCode}", response.StatusCode);
                    return Result.Failure<ThingDto>(Error.Internal());
            }
        }
        catch (ClientException e)
        {
            Log.Error(e, "<SYSTEM> login failed");
            return Result.Failure<ThingDto>(Error.Problem("<system>_login_failed", "<SYSTEM> rejected the tenant's credentials"));
        }
        catch (Exception e)
        {
            Log.Error(e, "<SYSTEM> GetThing failed");
            return Result.Failure<ThingDto>(Error.Internal());
        }
    }

    private async Task<HttpResponseMessage> SendAuthorizedAsync(Func<HttpRequestMessage> build,
        CancellationToken cancellationToken)
    {
        var response = await SendWithTokenAsync(build(), await GetTokenAsync(cancellationToken), cancellationToken);
        if (response.StatusCode != HttpStatusCode.Unauthorized)
        {
            return response;
        }

        response.Dispose();
        cache.Remove(CacheKey);
        return await SendWithTokenAsync(build(), await GetTokenAsync(cancellationToken), cancellationToken);
    }

    private Task<HttpResponseMessage> SendWithTokenAsync(HttpRequestMessage request, string token,
        CancellationToken cancellationToken)
    {
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
        return SendAsync(request, cancellationToken);
    }

    private async Task<string> GetTokenAsync(CancellationToken cancellationToken)
    {
        if (cache.TryGetValue(CacheKey, out JwtAuthenticationResponse token) && token.IsAccessTokenValid())
        {
            return token.AccessToken;
        }

        await TokenGate.WaitAsync(cancellationToken);
        try
        {
            if (cache.TryGetValue(CacheKey, out token) && token.IsAccessTokenValid())
            {
                return token.AccessToken;
            }

            var renewed = token is not null && token.IsRefreshTokenValid() && !string.IsNullOrEmpty(_options.RefreshTokenPath)
                ? await RequestTokenAsync(_options.RefreshTokenPath,
                    new JwtRefreshTokenModel { RefreshToken = token.RefreshToken }, cancellationToken)
                : null;
            renewed ??= await RequestTokenAsync(_options.LoginPath,
                new JwtAuthenticationModel(_options.UserName, _options.Password), cancellationToken);
            if (renewed is null)
            {
                throw new ClientException("<SYSTEM> login failed");
            }

            renewed.SetTokensExpirationDt(jwtOptions.Value);
            var keepUntil = renewed.RefreshTokenExpirationDt > renewed.AccessTokenExpirationDt
                ? renewed.RefreshTokenExpirationDt
                : renewed.AccessTokenExpirationDt;
            if (keepUntil > DateTime.Now)
            {
                cache.Set(CacheKey, renewed, keepUntil - DateTime.Now);
            }

            return renewed.AccessToken;
        }
        finally
        {
            TokenGate.Release();
        }
    }

    private async Task<JwtAuthenticationResponse> RequestTokenAsync<TBody>(string path, TBody body,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, path)
        {
            Content = JsonContent.Create(body)
        };
        using var response = await SendAsync(request, cancellationToken);
        if (!response.IsSuccessStatusCode)
        {
            Log.Error("<SYSTEM> token request to {Path} failed: {StatusCode}", path, response.StatusCode);
            return null;
        }

        var payload = await response.Content.ReadFromJsonAsync<<ClientClassName>TokenResponse>(jsonOptions.Value,
            cancellationToken);
        return payload?.ToJwtAuthenticationResponse();
    }
}
```

Adapt only what the source dictates:

- **Login body.** `JwtAuthenticationModel` sends `{"username","password"}` and `JwtRefreshTokenModel`
  `{"refreshToken"}` (both Core). Other field names: a `<ClientClassName>LoginRequest` model under
  `Models/<SYSTEM>/` with `[JsonPropertyName]` per field. Form encoding:
  `new FormUrlEncodedContent(new Dictionary<string, string> { ["user_name"] = _options.UserName, … })`
  (`using System.Collections.Generic;`).
- **Extra login headers** go on that login `request`, never on `Client.DefaultRequestHeaders`.
- **Token response.** `Models/<SYSTEM>/<ClientClassName>TokenResponse.cs` mirrors the source's response
  exactly (envelope, field names via `[JsonPropertyName]` when not camelCase) and maps it in one method:

  ```csharp
  using Internal.Domain.JwtRemoteClientAuthentification;

  namespace <T>.Models.<SYSTEM>;

  public class <ClientClassName>TokenResponse
  {
      public TokenData Data { get; set; }

      public JwtAuthenticationResponse ToJwtAuthenticationResponse() => Data is null
          ? null
          : new JwtAuthenticationResponse
          {
              AccessToken = Data.AccessToken,
              ExpiresIn = Data.ExpiresIn,
              RefreshToken = Data.RefreshToken,
              RefreshExpiresIn = Data.RefreshExpiresIn
          };

      public class TokenData
      {
          public string AccessToken { get; set; }
          public long ExpiresIn { get; set; }
          public string RefreshToken { get; set; }
          public long RefreshExpiresIn { get; set; }
      }
  }
  ```

  `ExpiresIn` is seconds. Convert minutes (`duration * 60`) and timestamps (`(expiresAt - DateTime.Now).TotalSeconds`).
  With no lifetime in the response, read the JWT `exp` claim:
  `(long)((AccessToken.GetExpirationDateFromToken() ?? DateTime.UtcNow) - DateTime.UtcNow).TotalSeconds`
  (`using Internal.Helpers;`) — `exp` is UTC, so compare with `DateTime.UtcNow`, never `DateTime.Now`.
- **An API key on every call** (ZRA's `X-Api-Key`): a `__Endpoints.<ClientClassName>.ApiKey__` token under the
  section's `AuthHeaderValue`, `AuthHeaderName` as a literal, added in `SendWithTokenAsync` on the request.
  `RegisterEndpoints` ignores both keys because the scheme is `None`.

Rules:

- The token goes on each `HttpRequestMessage`, never on `Client.DefaultRequestHeaders`. The module holds
  the client for the process lifetime (C5), so a shared header races between concurrent calls.
- One login at a time: the `static SemaphoreSlim` plus the second cache check. Never `lock` around an
  `await`, never `.Result`.
- A 401 evicts the cached token and retries **once** with a fresh one. A second 401 goes back to the caller
  as the operation's own error mapping.
- The cache entry lives until the refresh token expires, so the refresh path is reachable. Never pass a
  zero or negative lifetime to `cache.Set` — it throws.
- Never log a password, API key, access token, refresh token or `JwtAuthenticationResponse.ToString()`
  (it prints both tokens). Log the path and the status only.
- Login failure is `Error.Problem("<system>_login_failed", …)` (500, C2): the caller sees why, never the
  upstream body.

## 2. Per-caller credentials — `--credentials per-caller`

Only with `--auth Login`, and only when the upstream issues credentials per consuming institution (ZRA's
`Users` map, NHIMA). Default `shared`: one login for the tenant.

**Who the caller is.** The tenant authenticates the gateway caller itself, with Core's
`BasicAuthenticationHandler` against the gateway's user store, and keys credentials on
`HttpContext.User.Identity.Name`. **Never key on the `IdentityName` header.** The gateway's
`IdentityMiddleware` adds it with `Headers.TryAdd`, which keeps a value the caller already sent — any
gateway user can claim another institution's identity and its upstream credentials.

Config, both files. One entry per gateway username; keys under `Users` are those usernames, as literals:

```json
"MongoDb": {
    "ConnectionString": "__MongoDB.ConnectionString__",
    "DatabaseName": "__MongoDB.DatabaseName__"
},
"Endpoints": {
    "<ClientClassName>": {
        "AuthenticationScheme": "None",
        "BaseUrl": "__Endpoints.<ClientClassName>.BaseUrl__",
        "LoginPath": "auth/login",
        "Users": {
            "<gatewayUser>": {
                "Username": "__Endpoints.<ClientClassName>.Users.<gatewayUser>.Username__",
                "Password": "__Endpoints.<ClientClassName>.Users.<gatewayUser>.Password__"
            }
        }
    }
}
```

The gateway users come from `--callers <user>,<user>`, or a question with header `Callers`: "Which gateway
users call `<T>`? Type their usernames in Other, comma separated", options `Add them later (Recommended)` —
writes `"Users": {}` and the report names the gap · the users found in `GATEWAY-CONFIG.md` /
`docs/zamconnect-test-routes.md` holding the tenant's scope, up to 3.

`Program.cs` — the NHIMA pipeline, from Core:

```csharp
builder.AddUsersCache();
builder.Services.AddMongoDb(builder.Configuration);
builder.Services.AddUserRepository();
builder.Services.AddAuthentication(BasicAuthenticationHandler.AuthenticationScheme)
    .AddScheme<AuthenticationSchemeOptions, BasicAuthenticationHandler>(BasicAuthenticationHandler.AuthenticationScheme, null);
builder.Services.AddAuthorization();
builder.Services.AddHttpContextAccessor();
// after Build(), before the route maps:
app.UseAuthentication();
app.UseAuthorization();
```

with `using Database;`, `using Internal.Extensions;`, `using Internal.Infrastructure.Authentication.Basic;`,
`using Microsoft.AspNetCore.Authentication;`. Every module group calls `.RequireAuthorization()`.

Client changes against §1:

- Constructor adds `IHttpContextAccessor httpContextAccessor` (`using Microsoft.AspNetCore.Http;`).
- `var caller = httpContextAccessor.HttpContext?.User.Identity?.Name;` read the caller's section
  `configuration.GetSection($"Endpoints:<ClientClassName>:Users:{caller}")`. No caller or no section →
  `Result.Failure<T>(Error.Problem("<system>_caller_not_configured", "No <SYSTEM> credentials are configured for this caller"))`.
  Never fall back to another caller's credentials.
- The cache key is `$"<ClientClassName>_token_{caller}"`; `GetTokenAsync` takes the caller's username and
  password as arguments. One `TokenGate` for all callers is fine — it only serialises logins.

The report adds to the administrator list: every listed gateway user must exist with the tenant's scope,
and the tenant needs the two `MongoDB.*` variables.

## 3. Catch-all proxy — `--proxy`

Every request the tenant doesn't map (no Carter route, controller, `/health/live`, `/metrics`) is forwarded
to one upstream client unchanged: method, path, query, body. Explicit routes always win — endpoint routing
ranks the catch-all last. Use it when the tenant republishes most of an upstream as-is and maps only the
operations that need its own contract (SRS, DOC), or nothing at all.

Asked only under `Customize…`, in the endpoint selection call, header `Proxy`: "Forward every route `<T>`
doesn't map to `<System>` unchanged?" — `No (Recommended)` · `Yes — catch-all proxy to <System>`. With
`--proxy`, the operations not selected for exposure are reachable through it; the review lists them.

Not for: binary or multipart bodies (the forward is text), a second upstream (one catch-all per tenant),
or anything that needs mapping, validation or a different error contract.

The client gets one method. A plain client:

```csharp
public Task<HttpResponseMessage> Proxy(Func<HttpRequestMessage> build, CancellationToken cancellationToken) =>
    SendAsync(build(), cancellationToken);
```

A `Login` client (§1) reuses its retry: `=> SendAuthorizedAsync(build, cancellationToken);`.

`Program.cs`, after `app.UseRestExceptionHandler();` and before `app.MapCarter();` (the SRS shape, with the
body read once so the factory can rebuild the message):

```csharp
app.Map("/{**catch-all}", async context =>
{
    var upstream = context.RequestServices.GetRequiredService<<ClientClassName>>();
    var body = await new StreamReader(context.Request.Body).ReadToEndAsync(context.RequestAborted);
    var target = string.Concat(context.Request.Path.Value?.TrimStart('/'), context.Request.QueryString.Value);

    using var response = await upstream.Proxy(() => new HttpRequestMessage(new HttpMethod(context.Request.Method), target)
    {
        Content = body.Length == 0 ? null : new StringContent(body, Encoding.UTF8, MediaTypeNames.Application.Json)
    }, context.RequestAborted);
    await response.WriteTo(context.Response);
});
```

with `using System.IO;`, `using System.Net.Http;`, `using System.Net.Mime;`, `using System.Text;`,
`using Internal.Extensions.Extensions.Http;` (`WriteTo`), `using Microsoft.Extensions.DependencyInjection;`.

Rules:

- `TrimStart('/')` keeps a `BaseUrl` path (step 3). Never rewrite the path with `Replace` — DOC's
  `Replace("/new", "")` also cuts `/newsletter`.
- The caller's headers are not forwarded, the gateway's `Authorization` included. Upstream auth comes from
  the client's own section only.
- Upstream statuses and bodies pass through as they are. That is the contract the proxy promises, and the
  report says so.
- `RequestDelegate` form (`async context => …`), so the catch-all stays out of Swagger.
- `match.methods` in `GATEWAY-CONFIG.md` lists every verb the upstream source uses, not only the mapped ones.
- Proxied operations are not in the tenant's Swagger, so `tenant-deliverables` documents only the mapped
  routes. The report names the proxied ones.
- `UseRestExceptionHandler()` must be registered before the `Map`: a timeout or connection failure then
  answers `{message, traceId}` instead of the developer exception page.

## 4. Aggregate route — `--aggregate`

One `GET` route on the tenant calls several upstream operations — of one client or several — in parallel,
and returns one response. Only for reads: a write never fans out.

Offered in step 9 when the tenant has at least two read operations across its clients: option
`Add a combined route over existing operations`. Then one call:

| Header | Question | Options | → flag |
|---|---|---|---|
| `Sources` | Which operations does the combined route call? (`multiSelect`) | The tenant's `GET` client methods, `<Client>.<Method> — <purpose>`, spread over up to 2 questions (R9) | `--aggregate "<GET /path>=<Client.Method>+<Client.Method>"` |
| `Shape` | How are the results combined? | `One field per source (Recommended)` — `{ "nir": {…}, "nbr": {…}, "unavailable": [] }` · `One merged list` — only when every source returns a list of the same item type | `--aggregate-shape fields\|list` |
| `Cache` | Cache the combined response? | `30 minutes (Recommended)` · `5 minutes` · `No cache` | `--cache <seconds>` (`0` = none) |

The route path is proposed from the shared route parameter (`GET /persons/{nrc}/summary`); `Other` replaces it.

Module — the domain module the route belongs to (`--modules domain`), each source injected:

```csharp
group.MapGet("/persons/{nrc}/summary", async (string nrc, CancellationToken cancellationToken) =>
    {
        var key = $"PersonSummary_{nrc}";
        if (cache.TryGet(key, out PersonSummaryResponse cached) && cached is not null)
        {
            return Results.Ok(cached);
        }

        var nirTask = nir.GetPerson(nrc, cancellationToken);
        var nbrTask = nbr.GetEntitiesByOwner(nrc, cancellationToken);
        await Task.WhenAll(nirTask, nbrTask);

        if (nirTask.Result.IsFailure && nbrTask.Result.IsFailure)
        {
            return CustomResults.Problem(nirTask.Result);
        }

        var response = new PersonSummaryResponse
        {
            Person = nirTask.Result.IsSuccess ? nirTask.Result.Value.ToPersonResponse() : null,
            Entities = nbrTask.Result.IsSuccess ? nbrTask.Result.Value.ToEntityResponses() : null,
            Unavailable = SourceNames(("nir", nirTask.Result), ("nbr", nbrTask.Result))
        };

        if (response.Unavailable.Count == 0)
        {
            cache.AddOrUpdate(key, response);
        }

        return Results.Ok(response);
    })
    .Produces<PersonSummaryResponse>(StatusCodes.Status200OK)
    .ProducesProblem(StatusCodes.Status404NotFound)
    .ProducesProblem(StatusCodes.Status500InternalServerError)
    .WithSummary("…")
    .WithDescription("…");
```

The module constructor takes the clients and `IMemoryCacheService<PersonSummaryResponse> cache`
(`using Internal.Services.Interfaces;`), and holds the helper — `Result<T>` derives from `Result`, so one
signature takes every source (`using System.Collections.Generic;`, `using System.Linq;`):

```csharp
private static List<string> SourceNames(params (string Name, Result Result)[] sources) =>
    sources.Where(s => s.Result.IsFailure).Select(s => s.Name).ToList();
```

`Program.cs` and config, both files, when `--cache` isn't `0`:

```csharp
builder.AddCache<PersonSummaryResponse>("PersonSummary");
```

```json
"CacheOptions": {
    "PersonSummary": { "ExpirationInSeconds": 1800 }
}
```

with `using Internal.Extensions;`. A literal, never a token — and never `0`: `AddOrUpdate` throws on a zero
lifetime. `appsettings.Development.json` may set a shorter value.

Rules:

- Every source call returns `Result` and catches its own exceptions (the step 4 templates do), so
  `Task.WhenAll` never faults. ZamMobile's sources throw, so one timeout fails the whole route — don't copy it.
- Some sources failed → 200 with their names in `unavailable`; all failed → the first failure through
  `CustomResults.Problem`. Partial responses are never cached.
- The cache key holds every route parameter. `TryGet` returns `true` with `null` when the cached type differs,
  hence the `cached is not null` check.
- The response DTO is public, with a field per source, mapped through the existing mappers. `unavailable` is
  documented (`///`) so consumers know a missing field is an outage, not "no data".
- Data role: `consume` when any source is the `Gateway` client, otherwise `provide`.

## 5. Database upstream — `--source db[=<path>]`

The agency's data sits in a SQL Server database the tenant reads directly. Every precedent is SQL Server;
another engine has no precedent here — say so in the review and stop the pass.

### Source

`--source db=<path>` points to a `.sql` file (DDL, views, stored procedures) or a document listing the
tables and the queries. Discovery offers `*.sql` in `Integration Requests/` (step 1). Bare `--source db`,
or a DB pass with nothing found, asks header `Tables`: "Which tables or procedures does `<T>` read? Type
them in Other, one per line", options the `.sql` files found in the repo · `Describe them in a document
first` — creates `Integration Requests/` and rescans, as in the source question.

Then, in the proposal call:

| Header | Question | Options | → flag |
|---|---|---|---|
| `Access` | How does `<T>` query `<System>`? | `Dapper — one SQL statement per operation (Recommended)` · `EF Core — DbContext from the schema` (offered when the source has DDL for 3 or more related tables) | `--db-access dapper\|efcore` |
| `Writes` | Does `<T>` write to `<System>`? | `Read-only (Recommended)` · `Reads and writes` | `--db-writes` |

### Config

Top-level `ConnectionStrings`, never under `Endpoints` (Check 3 fails that), both files:

```json
"ConnectionStrings": {
    "<System>": "__ConnectionStrings.<System>__"
}
```

`ENVIRONMENT-VARIABLES.json`: `ConnectionStrings.<System>`, `secret: true`. Development keeps the placeholder
too; a connection string is a credential (C7). The connection is opened per call, so a placeholder fails
the first query, not startup.

### Files

| Access | Files | Packages (pinned, from the precedents) | Registration |
|---|---|---|---|
| Dapper | `Database/I<System>Repository.cs`, `Database/<System>Repository.cs` | `Dapper` 2.1.66, `Microsoft.Data.SqlClient` 6.1.4 | `builder.Services.AddTransient<I<System>Repository, <System>Repository>();` |
| EF Core | `Database/<System>Context.cs` (entities under `Database/Entities/`), the same repository pair | `Microsoft.EntityFrameworkCore.SqlServer` 10.0.0 | `builder.Services.AddDbContext<<System>Context>(o => o.UseSqlServer(builder.Configuration.GetConnectionString("<System>")));` + `AddScoped<I<System>Repository, <System>Repository>()` |

Namespace `<T>.Database`. No migrations and no `EnsureCreated` — the database belongs to the agency.

Dapper repository method:

```csharp
public async Task<Result<ThingDto>> GetThing(int id, CancellationToken cancellationToken)
{
    const string sql = "SELECT [Id], [Name] FROM [dbo].[Things] WHERE [Id] = @Id";
    try
    {
        await using var connection = new SqlConnection(configuration.GetConnectionString("<System>"));
        var thing = await connection.QuerySingleOrDefaultAsync<ThingDto>(
            new CommandDefinition(sql, new { Id = id }, cancellationToken: cancellationToken));
        return thing is null
            ? Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"))
            : Result.Success(thing);
    }
    catch (Exception e)
    {
        Log.Error(e, "<SYSTEM> GetThing query failed");
        return Result.Failure<ThingDto>(Error.Internal());
    }
}
```

with `using Dapper;`, `using Microsoft.Data.SqlClient;`, `using Microsoft.Extensions.Configuration;` and the
repository taking `IConfiguration configuration` in its primary constructor. A stored procedure:
`new CommandDefinition("[dbo].[GetThing]", new { Id = id }, commandType: CommandType.StoredProcedure, cancellationToken: cancellationToken)`
(`using System.Data;`).

Rules:

- Parameters only (`@Id`). Never interpolate or concatenate a value into SQL text.
- Name every column and alias it to the DTO property (`[THING_NAME] AS [Name]`); never `SELECT *`.
- The repository is injected as a **handler parameter**, never through the module constructor: a scoped
  `DbContext` captured at `MapCarter()` (C5) outlives its scope, and Development's scope validation refuses
  to resolve it.
- Never log the connection string or a `SqlException` message with it.
- The route's data role is `provide`.
- The Dockerfile needs nothing new: the packages restore from the csproj. `tenant-audit` Check 8 still checks
  the `COPY` closure.

The report adds to the administrator list: the connection-string variable for each environment, and a
network path from the cluster to the database server.

## 6. GraphQL upstream — `--source graphql[=<url|path>]`

The upstream answers `POST {query, variables}` at one URL. There is no GraphQL library in the repo and none
is added: the client is a `RestEndpoint` posting JSON, exactly like `EServicesShared`. All REST auth
schemes apply, `Login` included.

### Detection

| Source | Read as |
|---|---|
| `.graphql` / `.gql` file with `type Query` | Schema (SDL): operations = the `Query` / `Mutation` fields |
| JSON with `__schema` | Introspection result: same |
| Postman requests with `body.mode: "graphql"`, or JSON bodies `{"query": …}` all posted to one path | GraphQL; each request is one operation, with its query and variables |
| URL ending `/graphql` | GraphQL; try the introspection query `{"query":"{__schema{queryType{name}}}"}` and fall back to asking for the schema file when it's disabled |
| `--source graphql` with no value | Ask for the URL or schema file, as the source question |

Discovery (step 1) adds `*.graphql` and `*.gql`.

### Config and client

`BaseUrl` is the GraphQL endpoint itself, ending `/` (`https://host/graphql/`). The client posts to `""`.

```csharp
public class <ClientClassName>(HttpClient client, IOptions<JsonSerializerOptions> jsonOptions)
    : RestEndpoint(client)
{
    private const string ThingQuery = """
        query Thing($id: String!) {
          thing(id: $id) { id name }
        }
        """;

    public async Task<Result<ThingDto>> GetThing(string id, CancellationToken cancellationToken)
    {
        try
        {
            using var response = await PostAsync("",
                JsonContent.Create(new { query = ThingQuery, variables = new { id } }), cancellationToken);
            if (!response.IsSuccessStatusCode)
            {
                Log.Error("Unexpected response from <SYSTEM> GraphQL API: {StatusCode}", response.StatusCode);
                return Result.Failure<ThingDto>(Error.Internal());
            }

            var payload = await response.Content.ReadFromJsonAsync<GraphQLResponse<ThingData>>(jsonOptions.Value,
                cancellationToken);
            if (payload?.Errors is { Count: > 0 })
            {
                Log.Error("<SYSTEM> GraphQL errors: {Errors}", payload.Errors.Select(e => e.Message));
                return Result.Failure<ThingDto>(Error.Internal());
            }

            return payload?.Data?.Thing is { } thing
                ? Result.Success(thing)
                : Result.Failure<ThingDto>(Error.NotFound("thing_not_found", $"Thing \"{id}\" not found"));
        }
        catch (Exception e)
        {
            Log.Error(e, "<SYSTEM> GetThing failed");
            return Result.Failure<ThingDto>(Error.Internal());
        }
    }
}
```

`using System.Linq;` added to the step 4 using block. `Models/<SYSTEM>/GraphQLResponse.cs`:

```csharp
using System.Collections.Generic;

namespace <T>.Models.<SYSTEM>;

public class GraphQLResponse<TData>
{
    public TData Data { get; set; }
    public List<GraphQLError> Errors { get; set; }
}

public class GraphQLError
{
    public string Message { get; set; }
}
```

and one `<Operation>Data` class per query, mirroring its selection (`ThingData { public ThingDto Thing { get; set; } }`).

Rules:

- One `const string` query per operation, selecting only the fields the public DTO maps. Values go in
  `variables`, never into the query text.
- Check `errors` before `data`: a GraphQL server answers 200 with `errors` and a partial `data`. None of the
  precedents checks it on a `Result` path — that is the defect this template fixes.
- An `errors[].extensions.code` the source documents (`NOT_FOUND`, `BAD_USER_INPUT`) may map to
  `Error.NotFound` / `Error.BadRequest`; anything else is `Error.Internal()`. Never return the upstream
  message to the caller.
- The tenant exposes REST routes, one per operation, like any other pass. Forwarding the raw GraphQL
  endpoint (NDW's `/graphql`) is `--proxy`, not this section.
- A GraphQL upstream reached through the ZamConnect gateway (`/t/ndw/graphql`) goes on the tenant's
  `Gateway` client (step 1a), with these same query and response rules.
