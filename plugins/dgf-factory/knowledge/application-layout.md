---
dgf_version: "1.1.11"
read_date: 2026-09-30
---

# Application layout — what a new DGF application is made of

Structural facts: stamp only. What a new application workspace needs, how the runtime finds its
workspace and its database row, what the framework database holds and how it is seeded, which sign-in
providers a host reads from settings, what a host project is, and what the local Docker stack runs.
The files read are in the maintainer provenance ledger for this file.

Every fact is read from the framework's code, its samples or its compose files, never from what an
estate's applications happen to contain. Where the framework pins nothing — a package id, an image
tag, a feed, a location for the database baseline — this file says **not pinned**, and a generator
must leave the value to a placeholder. Where a fact could not be found, it says **not found**.

## 1. The workspace minimum

A new application workspace is a directory beside `webasm` under the workspaces root. The reference
layout is the `dgf` sample workspace. The rows below are the files a generated workspace carries and
that this plugin's post-generation check reads; `Root` and `Required` are what the reference layout's
file has, and an XML file's are checked with `xml.etree`. The runtime's serializers bind by name and
fail on none of the `Required` names, so `Required` is a property of the layout, not a runtime error.
For a JSON file `Root` is `—` and `Required` names top-level keys.

<!-- machine-read: workspace-minimum -->
| File | Root | Required | Rule | Fact |
|---|---|---|---|---|
| `FM/_COMPONENTS/sitemap.json` | — | routes | landing-first login-route page-per-route | The portal shell and route table. `routes` is a `router` component whose own `routes` list is flat; the landing route is listed first, has a real path and is never `"/"` |
| `FM/_COMPONENTS/Page/SiteMap/<page>.json` | — | type name content | login-component | A page a route points at. The login page holds a `login` component whose `authenticationMethods` lists the providers |
| `_application.sitemap` | map | @name @type @visible basedOn dbprefix title tabs links | profile-tab | The legacy application map, read from the application workspace root only. The base does not supply one |
| `_application-<instance>.sitemap` | map | @name @type @visible basedOn dbprefix title tabs links | profile-tab | The same file for one instance of a shared workspace, bind-mounted over `_application.sitemap` |
| `FM/_PROFILE/<profile>/<group>/_tree.xml` | Tree | @title @name Folders | members-group | A profile tree; one per `router` component, in the `Members` group unless a role narrows it |
| `FM/_PROFILE/<profile>/<group>/<node>.xml` | mapNode | @type set | node-per-folder | The node file a tree folder names |

The `Rule` tokens are the checks the post-generation check makes of a file:

| Token | Meaning |
|---|---|
| `landing-first` | the first route of the router's `routes` list is the landing route, and its path is not `"/"` |
| `login-route` | a route whose path is `/login` exists, and its content is a page |
| `page-per-route` | every route's `page` content names a page file that exists, by exact case |
| `login-component` | the page holds a `login` component with a non-empty `authenticationMethods` |
| `profile-tab` | the map has a `tabs` node of `type="PROFILE"` for each profile folder under `FM/_PROFILE/` |
| `members-group` | each profile folder has a `Members` group with a `_tree.xml` |
| `node-per-folder` | every tree folder that has a `control` has a node file of its `name` beside the tree |

Facts behind the rows:

- **The landing route is never `"/"`.** The shell's route builder drops a route whose path is `"/"`
  without an error, and the application root then redirects to `routes[0].path`, which no longer
  exists. So the landing route is listed first with a real path. The `dgf` sample's is `/home`, with
  `requireAuthorization: false` and a `page` content named `SiteMap/home`.
- **`sitemap.json`'s shape.** Top-level keys are `theme`, `title`, `version`, `logo`, `favicon`,
  `localization` (`languages`, `default`), `routes`, `header` and `footer`. A route has `path`, `name`,
  `requireAuthorization`, `fluid`, `hideHeader`, `hideFooter` and `content`; a router is referenced from
  a route's `content` by `{"type": "router", "name": …}`, not nested in `routes`.
- **`/login` is hard-coded in the shell and the host.** The auth guard, the route guard and the error
  interceptor navigate to `/login`, and the host's cookie `LoginPath` is `/login`. A workspace therefore
  declares a route whose `path` is `/login`, with `hideHeader` and `hideFooter`, and content a local page.
  Nothing else in the shell requires the route to exist, but the redirect would land on nothing.
- **The login page** is a `page` whose content is one `login` component with `title` and
  `authenticationMethods`, a list of `{name, title, hidden}`. The shell's accepted names are `azure`,
  `dgpass` and `basic`. A method with `hidden: true` is listed under other options.
- **The sign-in menu item calls DGPass directly when the login route lists 0 or 1 method** and only
  navigates to `/login` when it lists more than one. A profile-menu item with the id `signIn` therefore
  starts a DGPass login whatever the single method is; a header for an application that lists only
  `basic` must not use that id.
- **`_application.sitemap`** is read by `ApplicationMapService` from the application workspace root
  alone: `ApplicationMap` binds the root `map` and `ApplicationInfo` its attributes `name`, `page`,
  `type`, `visible` and elements `theme`, `dgf-theme`, `createdInfo`, `basedOn`, `dbprefix`, `title`,
  `description`, `logo`, `tabs` and `links` (each a list of `mapNode`). A `mapNode` has `content`,
  `deny`, `ico`, `name`, `package`, `restitle`, `roles`, `title`, `type`, `visible` and `set` children.
  The `dgf` sample's `map` is `name="default" type="1" visible="true"`, `basedOn` is `default`, and its
  one `tabs` node is `type="PROFILE"` with `content` naming the profile. A router's profile is found
  by looking its name up in these tabs and links before falling back to the name as the profile folder.
- **A profile tree** is `Tree` (`title`, `name`, `image`, `navigator`), holding `Folders` of `Folder`
  (`title`, `name`, `image`, `control`), nestable. A folder's `control` says what it opens — `FORM`,
  `GRID`, `SERVERCONTROL` — or is empty for a group heading. Its node file is `<name>.xml` beside the
  tree: `mapNode type="FORM"` with `set name="FormName" value="…"`; with no `TableName` set, the JSON
  form `FM/_COMPONENTS/Form/<FormName>.json` is loaded.
- **`Members` is the profile group every role falls back to.** `TreeManager` normalises a null or
  blank group to `Members`, and when the group's `_tree.xml` does not exist it loads the `Members` one.
  When neither exists it does not throw: it returns an empty tree. A node file is looked up in the
  group, then in `Members`, and a missing one throws `File not found`. A plain profile name is looked
  up in the application workspace only; `BASE:` reaches `webasm`.
- **The reference layout's one `BASE:` route is `/user-profile`** (page `BASE:UserProfilePage`). It is
  optional: a workspace that omits it loses only that page.
- **Scratch directories** `_STORAGE/`, `Temp/_Upload` and `Temp/Attachments` live under the
  application root. The host creates a missing `Temp/_Upload` or `Temp/Attachments` when it maps them
  as static paths.

## 2. Which workspace runs, and the application row

- **Settings.** The workspaces root is the environment variable `DGF_WORKSPACES_ROOT_PATH`, else the
  setting `WorkspacesRootPath`; with neither, the host throws — there is no default. The workspace is
  the setting `WorkspaceName`, defaulting to `default`. The base workspace is the compile-time constant
  `webasm` (`BaseWorkspaceName`), so the base directory must be called that. The application
  workspace's root is `<root>/<WorkspaceName>`; its `FM/` is `FmPath`, and `webasm`'s is `FmBasePath`.
- **The host serves** the application workspace at `/application/` and the base at `/webasm/`.
- **The application row.** At start `WorkspaceProvider.InitAsync` runs
  `SELECT ApplicationId, LoweredApplicationName FROM aspnet_Applications WHERE LoweredApplicationName = '<WorkspaceName lower-cased>'`.
  `Current` throws `AppException` — "Cannot load workspace … Please check aspnet_Applications table" —
  when no row matches, so **the host does not start without a row for the workspace**. The row's
  `ApplicationId` is the id the framework partitions its own rows by. The base workspace is resolved
  from the filesystem only and never looked up.
- **A second mode exists.** When the setting `WorkspaceProvider_ApplicationUrlColumn` names a column,
  `InitAsync` selects every row whose column is not null, and `Current` matches the row whose
  `SiteName` equals the request's host: one process serving several applications. This is not what
  the local stack's several-instance sample does (§4), and this plugin's scaffold does not use it.
- **Partitioning by `ApplicationId`.** The framework writes the current workspace's id to its own
  rows: the audit trail (`atApplicationId`), process instances, user events, notifications and the
  identity tables. In the baseline the column is `UNIQUEIDENTIFIER` and, in the tables read, `NOT NULL`
  with no default and no foreign key on most, `NULL` on the role, event and notification tables. The
  framework database has 57 table scripts that mention `ApplicationId`.

### 2.1 The `aspnet_Applications` row

The table has 28 columns, of which `ApplicationId` (`UNIQUEIDENTIFIER`), `ApplicationName`
(`VARCHAR(256)`), `SignType` (`VARCHAR(20)`, default `PinCode`) and `IntranetSignType`
(`VARCHAR(20)`, default `ZamGov`) are `NOT NULL`; every other column is nullable. `LoweredApplicationName`
is `VARCHAR(50)` and carries the clustered index. The others include `ShortName`, `Description`,
`IsAvailable`, `SortOrder`, `ApplicationUrl`, `StartProcess`, `Namespace` and `ParentID`. The
framework's own seed inserts `ApplicationId`, `ApplicationName`, `LoweredApplicationName`, `ShortName`,
`Description`, `IsAvailable`, `SortOrder`, `SignType` and `IntranetSignType`, under
`IF NOT EXISTS (SELECT 1 FROM [dbo].[aspnet_Applications] WHERE [LoweredApplicationName] = '<name>')`,
and prints a line either way. It sets the two sign types to their own defaults.

## 3. The database

- **The baseline** is an SDK-style `Microsoft.Build.Sql/2.2.0` project of 145 derived objects (87
  tables, 45 procedures, 8 functions, 5 views). Its properties are `DSP`
  `Microsoft.Data.Tools.Schema.Sql.Sql160DatabaseSchemaProvider`, `ModelCollation` `1033, CI`,
  `SqlServerVerification` false and `TreatTSqlWarningsAsErrors` true; it has no `TargetFramework`. It
  removes `Scripts/**/*.sql` and `ContinuousDeployment/**/*.sql` from `Build` — the SDK globs every
  `.sql` as schema — declares `PostDeploy` `Scripts/Script.PostDeployment.sql`, and lists the
  `ContinuousDeployment` scripts as `None`. Two procedures carry `SuppressTSqlWarnings="71502"`.
  `dotnet build` writes a standard `.dacpac`.
- **Post-deployment** is the SQLCMD include idiom: `Scripts/Script.PostDeployment.sql` holds
  `:r ../ContinuousDeployment/<n>.PostDeployment.<Name>.sql` lines, and **every included script must
  be idempotent**, since a publish runs against an empty database and an existing one. The idiom is
  `IF NOT EXISTS (…) BEGIN INSERT … PRINT … END ELSE PRINT …`, then `GO`.
- **The publish profile** used locally sets `CreateNewDatabase` false, `BlockOnPossibleDataLoss`
  false and `DropObjectsNotInSource` false: the framework shares its database with consumer-owned
  objects and never drops what it does not ship. The local stack builds the dacpac in a one-shot
  `db-init` container and publishes it with `sqlpackage`, retrying up to 30 times at 5-second
  intervals and re-publishing with `CreateNewDatabase=True` when the database does not exist.
- **What a consumer database project builds against is not found.** No `ArtifactReference`,
  `PackageReference` or `SqlCmdVariable` exists in any database project; nothing documents how a
  consumer project extends the baseline; the only stated relation is that a consumer can
  schema-compare against the dacpac. **No image, package or dacpac location for the baseline is
  pinned**: it is built from the framework's source. A generated database project therefore has no
  reference to the baseline, and its post-deployment scripts run against the tables the baseline has
  already created.

### 3.1 Roles

- **`AspNetRoles`** has `Id` (`UNIQUEIDENTIFIER`), `ApplicationId` (`UNIQUEIDENTIFIER NULL`, a foreign
  key to `aspnet_Applications`), `Name` and `NormalizedName` (`NVARCHAR(256) NULL`), `ConcurrencyStamp`
  (`NVARCHAR(MAX)`), `Description` (`NVARCHAR(256)`), `TypeId` (default
  `4dbd37af-33bf-41e0-9834-f1de42a511d8`) and `IsAvailable` (`BIT`). The primary key is `Id`.
  **Its one unique index, `RoleNameIndex`, is on `NormalizedName` alone** (filtered to not null), so a
  role name exists once across all applications; the entity-framework migration declares `ApplicationId`
  `NOT NULL`, which the database project does not.
- **How `NormalizedName` is formed is not in the framework's code.** It registers no
  `ILookupNormalizer`, so ASP.NET Identity's default applies; the framework's own migration script for
  legacy membership copies the legacy lower-cased role name into it, and it sets a user's normalised
  name and email lower-case itself. The baseline's `ModelCollation` is case-insensitive, so the unique
  index and `x.NormalizedName == newRole` see two casings of one name as one.
- **Built-in roles** are `Administrators`, `Members`, `Anonymous`, `Registered Users` and `PortalUser`
  (the constants also name `Applicant` and `New`, which no seed creates).
- **The code seed** (`ApplicationDbContextSeed`, run after start) does nothing unless
  `AdminSeedOptions:Enabled` is true and `Accounts` is non-empty. It creates roles **only when
  `AspNetRoles` has no row at all** — for any application — through `RoleManager`, as
  `ApplicationRole(name, current ApplicationId)`, for the five built-ins and each account's `RoleName`;
  `RoleExistsAsync` is by normalised name alone. It then registers each account whose `UserName`
  matches no user, for any application. So a role row written by a deployment script before the first
  start switches the code's role seeding off, and a role name written under one application is seen as
  existing for every other.
- **An account** is `Username`, `Password`, `FirstName`, `LastName`, `Email`, `RoleName`
  (`AdminSeedOptions:Accounts:<n>:*`); one missing `Username`, `Password` or `RoleName` is skipped with a
  warning. The local stack passes them as environment variables, so no password is committed.
- **Role lookups by application** exist beside the global name index: the account service finds a role
  by `ApplicationId` and `Name`.

## 4. Several instances

An instance is a `WorkspaceName` with its own `aspnet_Applications` row. The local stack's several-
instance sample runs one API container per instance from **one workspace directory** mounted under each
instance's name, and bind-mounts a per-instance sitemap file over `_application.sitemap`:

```text
<repo>/workspaces/zma:/workspaces/lm
<repo>/workspaces/zma/_application-lm.sitemap:/workspaces/lm/_application.sitemap
<repo>/workspaces/zma:/workspaces/sim
<repo>/workspaces/zma/_application-sim.sitemap:/workspaces/sim/_application.sitemap
```

Per instance the sample also varies the API's settings file, the cache's `RedisInstanceName`, the
container name, the traefik host and the paired UI's settings file. The sample sets no `WorkspaceName`
in its compose file; the active name comes from each mounted settings file, which is not in the
framework's repository. Both instances share the base mount `webasm`.

<!-- machine-read: instance-models -->
| Model | Mounts | Sitemap | Applications row | Fact |
|---|---|---|---|---|
| `shared-workspace` | shared | override | per-instance | One directory mounted under each instance's name; a per-instance `_application-<instance>.sitemap` is bind-mounted over `_application.sitemap` |
| `own-workspace` | own | own | per-instance | One workspace directory per instance, each with its own `_application.sitemap`; the same `WorkspaceName` rule and the same row per instance |

## 5. Sign-in

**Cookie authentication is always on**, with the default scheme and challenge scheme the cookie; its
`LoginPath` is `/login`, and a redirect to login answers 401 instead of redirecting. A provider is added
**only when its section exists**:

- DGPass OIDC when `Authentication:DGPassOIDC` exists;
- Azure AD OIDC when `Authentication:AzureOIDC` exists;
- the local `basic` sign-in is a controller branch, enabled by `Authentication:Basic:Enabled`; with it
  false the controller answers `Basic authentication is disabled`.

No other inbound scheme is read from settings: there is no JWT bearer, API key, Kerberos or Google
scheme. The scheme names are constants (`DGPassOIDC`, `AzureOIDC`); the shell's login-method names are
`dgpass`, `azure` and `basic`, and the host's login endpoint challenges the scheme a method names.

<!-- machine-read: auth-schemes -->
| Provider | Section | Keys | Fact |
|---|---|---|---|
| `basic` | Authentication:Basic | Enabled | Local username and password. The `dgf` sample and the local stack use it alone. An account is seeded from `AdminSeedOptions`, never from this section |
| `dgpass` | Authentication:DGPassOIDC | Authority ClientId ClientSecret CallbackPath PostLogoutRedirectUri BackChannelLogoutUri Scopes ClockSkew ClientCredentialStyle MetadataUrl | OpenID Connect, code flow with PKCE. `Authority`, `ClientId` and `ClientSecret` have no default and no validation; the others default to `/signin-oidc`, `/signout-callback-oidc`, none, `openid profile`, 60 seconds, `PostBody` and a metadata address derived from the authority |
| `azure` | Authentication:AzureOIDC | TenantId Authority ClientId ClientSecret CallbackPath PostLogoutRedirectUri Scopes | OpenID Connect against `<Authority>/<TenantId>/v2.0`. Sets no metadata address, no `offline` scope, no clock skew and no token refresh |

Facts behind the rows:

- **DGPass hard-codes** `RequireHttpsMetadata` false, `ResponseType` code, PKCE, `UseTokenLifetime`,
  `SaveTokens`, `MapInboundClaims` false, `GetClaimsFromUserInfoEndpoint`, name claim `sub` and role
  claim `role`, and always adds the scope `offline`. Azure hard-codes the same except `MapInboundClaims`
  true.
- **Keys shared by every provider** live under `Authentication`: `DefaultRole` (the role given a new
  external user; `Members` when unset), `AutoApprove` (a user is approved only when it is `true`) and
  `SessionOptions`, whose keys are `CookieDomain` (none), `CookieNamePrefix` (`webapp`), `IdleTimeout`
  (30 minutes), `SlidingExpiration` (true), `SameSite` (`None`) and `UseDistributedCacheSessionStorage`
  (false). The cookie names are `<prefix>_session` and `<prefix>_oidc_auth`.
- **Two host settings rewrite redirects**: `WebAppHost` is the UI's base URL, used for the failure
  redirect to `/login`; `ReverseProxyHost` is the API's public URL, prefixed to the callback path. Both
  are read from the top level of the settings.
- **The login endpoint** accepts `azure`, `dgpass` and `basic`. The login component hides a method the
  host cannot serve: `dgpass` is listed only when its section exists, `basic` only when enabled.

## 6. The host

- **A host project** is `Microsoft.NET.Sdk.Web`, `net10.0`, referencing the API library. The sample host
  is a thin project: `Program.cs` is `WebApplication.CreateBuilder(args)` and
  `await builder.BuildEServicesApi(postConfigureServices, postAppConfigure)`, where both arguments are
  optional actions. `BuildEServicesApi` reads `appsettings.json` (required), `appsettings.<Environment>.json`
  (optional) and the environment, in that order, and ends by mapping controllers and running.
- **The API library is a project reference in the framework's repository, and no package id is pinned.**
  It sets no `PackageId`, no description and no version of its own; the only version is the props file's
  `1.1.11`. A generic scaffold's `PackageReference` id, version and feed are therefore not pinned by the
  framework: the id is by default the assembly name, `DGF.API`, which is not confirmed by any pack
  configuration.
- **Startup requires** `ConnectionStrings:LocalSqlServer` (the host throws when it is absent), the
  workspaces root and `webasm` (§2), the application row (§2.1) and `ConnectionStrings:Redis` for the
  Redis health check and cache. Caching is `DistributedCachingOptions`: SQL Server cache, else Redis
  (which needs `RedisInstanceName` and the Redis connection string), else in memory.
- **The `Integrations` sections must exist even when nothing calls them.** The sign and notify services
  are registered only if `Integrations:DgSign`, `Integrations:DgNotify` (and `DgNotifyOtp`) exist, but
  two services that take them as plain constructor dependencies are registered unconditionally, so a
  host without the sections fails `ValidateOnBuild` and exits before serving. `DgPay`, `DgSign`,
  `DgNotify` and `DgNotifyOtp` are RA-authenticated endpoints, so `Integrations:RegistrationAuthority`
  (`BaseUrl`, `AuthenticationScheme`, `TokenGeneration` with `CallingServiceFqn`, `CertificateThumbprint`
  and `PrivateKey`) is required for any call. `PinCodeSign` is a plain endpoint.
- **Other settings the host reads:** `ApplicationConfig:ApplicationName` (the data-protection application
  name, default `DGF`; keys are persisted to the database), `ApplicationConfig:CustomAssembliesPath`,
  `CorsOrigins` (a list, with credentials allowed), `Serilog`, `Languages`, `DbResourceConfiguration`,
  `Documents`, `ProcessConfigurations`, `TemplateRendering`, `Defaults` (uploader and image limits),
  `workflow`, `Plugins` and `AdminSeedOptions`.
- **Ports and health.** The sample image listens on `4000` (`ASPNETCORE_URLS=http://+:4000`,
  `ASPNETCORE_HTTP_PORTS=4000`); the health endpoint is `/health/live`; the image has no `curl` or `wget`.
- **The sample host's Dockerfile** builds from the framework's own source tree, so it is not a pattern
  a package-consuming project can copy. What it pins: `mcr.microsoft.com/dotnet/aspnet:10.0` as the
  runtime and `mcr.microsoft.com/dotnet/sdk:10.0` as the build image; libraries for PDF and imaging
  (`libfontconfig`, `libgdiplus`, `libc6-dev`, `libuuid1`, `fontconfig`, `fonts-liberation`); a user and
  group with id `4000`; `ENTRYPOINT ["dotnet", "<Host>.dll"]`.
- **The sample `appsettings.json` of the host holds live-looking secrets** in eight places — the
  connection string, two endpoint passwords, two integration passwords, an RSA private key, a PowerBI
  secret and a Syncfusion licence — and environment URLs. None of it is a pattern: the credential-free
  settings the local stack mounts are.

## 7. The local stack

The local stack is a set of compose files; `docker-compose.yml` includes the infrastructure, the shared
services and the stubs.

- **Services and what DGF pins.** `traefik:v3.6` (ports 80, 443, 8080; providers docker and file; TLS
  from a mounted certificate directory); `mcr.microsoft.com/mssql/server:2022-latest` (`MSSQL_PID`
  `Developer`, `ACCEPT_EULA` `Y`, healthcheck `sqlcmd -Q 'SELECT 1'`, data volume); `redis:7-alpine`
  (`--save 60 1`); `datalust/seq:2024.3` (`SEQ_FIRSTRUN_NOAUTHENTICATION` `True`); `wiremock/wiremock:3.13.1`
  for the Registration Authority, Pay, Sign and Notify stubs; `gotenberg/gotenberg:8`. The database and
  Redis services are in the `infra` profile; `COMPOSE_PROFILES=` opts out.
- **`db-init`** is built from the database project's folder and exits after publishing; the API waits on
  `service_completed_successfully`, and on `service_healthy` for SQL Server and Redis.
- **The API and UI images are built from source and no tag is pinned** (`image: dgf-api`, `image: dgf-ui`,
  each with a `build:` block); no consumer image tag is pinned anywhere. The only DGF-registry images
  are the legacy engine's (`…/dotgovengineweb:1.2.27`).
- **The API service's environment** sets `ASPNETCORE_ENVIRONMENT`, `ASPNETCORE_URLS`,
  `DGF_WORKSPACES_ROOT_PATH`, `WorkspaceName`, `ConnectionStrings__LocalSqlServer` (from
  `${MSSQL_SA_PASSWORD}` and `${MSSQL_DB}`), `ConnectionStrings__Redis`,
  `DistributedCachingOptions__RedisConnectionString`, `AdminSeedOptions__Enabled`,
  `AdminSeedOptions__Accounts__0__*` and `Integrations__RegistrationAuthority__TokenGeneration__PrivateKey`.
  Its mounts are the workspace directory, `webasm`, and a settings file over `/app/appsettings.json`
  (read-only). A double underscore in an environment variable overrides the JSON key it names.
- **The `.env` keys** are `MSSQL_SA_PASSWORD`, `MSSQL_DB`, `MSSQL_PORT`, `DGF_ADMIN_USERNAME`,
  `DGF_ADMIN_PASSWORD`, `DGF_ADMIN_EMAIL`, `TIME_ZONE` and `COMPOSE_PROFILES`; the Registration
  Authority's private key is generated per machine into `.env` and never committed.
- **The UI container** is `nginx:alpine`. The shell fetches `assets/appsettings.json` at run time, and
  the stack mounts a settings file over it. Its keys are `apiUrl` (the API's public URL), `dateFormat`,
  `timeFormat`, `dateTimeFormat`, `inactivityTimeout` (seconds), `minimumLevel` and optionally `version`,
  the cache-busting key. The shell also loads three customisation files, `assets/js/formhelper.js`,
  `assets/js/formshared.js` and `assets/styles/custom.css`
  ([`composition-specs.md`](composition-specs.md) §5); the default stack mounts none of them, and the
  consumer samples bind-mount each from the consumer's repository.
- **Routing** is by traefik labels: a router rule on the host name, entrypoint `websecure`, TLS, and the
  service port (`4000` for the API, `80` for the UI).

<!-- machine-read: solution-parts -->
| Part | Verified values | Placeholders | Fact |
|---|---|---|---|
| `solution` | slnx | ApplicationName | The framework's own solution file is an `.slnx` |
| `host-project` | Microsoft.NET.Sdk.Web net10.0 BuildEServicesApi | DgfApiVersion NuGetFeed | The package id is not pinned; the API library is a project reference in the framework's repository |
| `host-settings` | ConnectionStrings:LocalSqlServer ConnectionStrings:Redis WorkspacesRootPath WorkspaceName DistributedCachingOptions CorsOrigins ApplicationConfig AdminSeedOptions | ConnectionString RedisConnection WebAppHost ReverseProxyHost | The workspace name and root are settings; the application row must exist for the name |
| `host-integrations` | Integrations:RegistrationAuthority Integrations:DgSign Integrations:DgNotify Integrations:DgNotifyOtp | IntegrationBaseUrl CallingServiceFqn CertificateThumbprint PrivateKey | The sections must exist or the host fails validation at start; no value is pinned |
| `host-dockerfile` | mcr.microsoft.com/dotnet/aspnet:10.0 mcr.microsoft.com/dotnet/sdk:10.0 ASPNETCORE_URLS=http://+:4000 uid=4000 | NuGetFeed | The sample host builds from the framework's source tree, so a package-consuming project's build stage is its own |
| `database-project` | Microsoft.Build.Sql/2.2.0 Sql160DatabaseSchemaProvider ModelCollation=1033,CI TreatTSqlWarningsAsErrors=true | — | Scripts and ContinuousDeployment are removed from Build and included by :r; every included script is idempotent |
| `application-row` | aspnet_Applications LoweredApplicationName IF-NOT-EXISTS | InstanceName InstanceTitle | The API does not start without a row for the workspace name |
| `roles-seed` | AspNetRoles RoleNameIndex Administrators Members Anonymous Registered-Users PortalUser | RoleNames | One unique index on NormalizedName, so a name exists once across applications |
| `compose-stack` | traefik:v3.6 mssql/server:2022-latest redis:7-alpine datalust/seq:2024.3 | SaPassword DatabaseName DbInitImage ApiImage UiImage | DGF pins no image for its own API, UI or database baseline |
| `ui-settings` | assets/appsettings.json apiUrl | ApiPublicUrl | Mounted over the shell's default; the shell also loads three customisation files |
| `auth-sections` | Authentication:DefaultRole Authentication:AutoApprove Authentication:SessionOptions | ClientId ClientSecret Authority TenantId CookieDomain | Every provider's secret is a placeholder |

## 8. What was not established

- The package id, feed and version scheme of the API library as consumed from NuGet (§6).
- How a consumer database project references the baseline (§3), and where a baseline image or dacpac
  is published, if anywhere.
- The role normalizer the identity library applies (§3.1); it is outside the framework's code.
- How the several-instance sample sets each instance's `WorkspaceName` (§4).
- Whether a later framework version changes these facts. The maintainer's drift check compares the
  files this file was read from with a framework checkout.
