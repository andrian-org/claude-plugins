---
name: tenant-deliverables
description: Generate the full delivery document set for a ZamConnect tenant — the OpenAPI JSON, the Word API Specification and the Postman collection, laid out in the Consumer/Provider/Tenant folders under the tenant's Deliverables directory, with every section of the document filled from the tenant's own source rather than left as boilerplate. Documentation only — never modifies tenant code or any ZamConnect library. Routes are always written with the gateway prefix (`/t/pqps/hub/pesticides`, never the bare controller route). Use when the user says "generate the documents for <Tenant>", "produce the API specification for <Tenant>", "build the deliverable package", "make the tenant docs", or types /tenant-deliverables.
argument-hint: "<Tenant> [--route <gateway-route>] [--roles tenant,consumer,provider] [--out <dir>] [--version <X.Y>] [--author <name>] [--provide-paths <path>...] [--auto] [--dry-run]"
allowed-tools: Read Glob Grep Write Bash(cat *) Bash(sed *) Bash(grep *) Bash(find *) Bash(ls *) Bash(mkdir *) Bash(cp *) Bash(dotnet build *) Bash(dotnet tool run *) Bash(python *) Bash(powershell *) Bash(git status *) Bash(git log *) Bash(git diff *) AskUserQuestion
disable-model-invocation: false
---

# ZamConnect Tenant Delivery Documents

Produces the package a third party actually receives for a tenant. Not a README, not internal notes — the contractual deliverable, in the layout and with the section structure the existing published specs use.

All repo paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`).

## Hard constraint: this skill writes documents, never code

The tenant's source is **read-only input**. Nothing here edits, adds or deletes a file under `src/Tenants/<Tenant>/`, `src/Core/`, `src/Gateway/`, any `.csproj`, `.sln`, `appsettings*.json`, pipeline or compose file. No refactor, no "small fix while I'm here", no adding a missing `///` comment or `.WithTags(…)`, even where doing so would visibly improve the generated document.

The only paths this skill may write to:

- `src/Tenants/<Tenant>/Deliverables/…` (or `--out`) — the package itself
- the scratchpad — `sections.json`, intermediate JSON, logs
- `src/Tenants/<Tenant>/bin/…` — build output produced by `dotnet build` and the Swashbuckle export, never hand-edited source

`dotnet build` is allowed because it only produces build output; it is the mechanism for exporting the swagger document. Do not run it with any flag that rewrites source, and never run a formatter, a code fix or `git commit`/`git add` from this skill.

**A code defect is a finding, not a task.** When the source cannot fill a compartment — no XML doc comments, tags defaulting to class names, a response type the code does not declare — generate the document with what the source actually says, and list the defect in the final report with the exact file, type and member to change. The user decides whether to change the code and re-run. Overriding a value straight into the generated artifact is equally forbidden: the document must reflect the tenant as it is, otherwise the spec and the running service disagree.

## The short path

Three scripts in `scripts/` do the mechanical work. Prefer them over doing any of it by hand — each replaces a fistful of file reads or a block of inline Python, and they cannot drift from each other the way a hand-run sequence does.

```bash
python scripts/inspect_tenant.py <TENANT>          # steps 1-3 as one fact sheet
python scripts/build_package.py <TENANT> \         # steps 4-9 in one call
    --route <r> --version <X.Y> --roles tenant,consumer
python scripts/verify_package.py src/Tenants/<TENANT>/Deliverables --route <r> --version <X.Y>   # step 8 alone
```

`build_package.py` takes `--provide-paths <path> ...` for a tenant that both consumes and provides; every path not named is Consume. It builds, exports, applies the gateway prefix, lays out the five folders, moves superseded files to `Archive/<timestamp>/`, renders one DOCX per role, writes the Postman collection and runs every gate, exiting non-zero if one fails.

The rest of this document is why each of those steps is what it is, and what the scripts deliberately leave to you: an endpoint the split cannot settle mechanically, and every piece of prose that has to come from source. Read on before overriding anything.

`${CLAUDE_PLUGIN_ROOT}/agents/tenant-deliverables-builder.md` runs the whole thing as a subagent, which keeps the exploration and the render logs out of the calling conversation.

## What gets produced

The package is written to `src/Tenants/<Tenant>/Deliverables/` — that folder *is* the package, and the five role folders sit directly inside it. There is no level between `Deliverables/` and `Consumer/`. A virtual tenant has no project folder — create `src/Tenants/<Tenant>/Deliverables/` anyway; the deliverables live with the tenant they describe.

```
src/Tenants/<Tenant>/Deliverables/
  Consumer/            <CODE> (c) API Specification.docx
  Provider/            <CODE> (p) API Specification.docx
  Tenant/              <CODE> (t) API Specification.docx  + <CODE> (t) API Swagger.json  + <CODE>.postman_collection.json
  Integration Requests/  upstream specs, mapping spreadsheets, a readme.md of source links — never generated, only carried over
  Archive/             superseded versions
```

**The OpenAPI document and the Postman collection are Tenant-level artifacts and live only in `Tenant/`.** One OpenAPI document covers the tenant's whole surface. The role folders hold only their DOCX — splitting the machine-readable artifacts per role would hand a consumer two files that each describe half a route space.

Folder names are unnumbered — `Consumer`, `Provider`, `Tenant`, `Integration Requests`, `Archive`. Some published packages carry a numeric prefix (`1. Consumer`, `2. Provider`, …); that is legacy, do not copy it forward, and rename it when you touch such a package so one tenant never has both forms.

**No contract code anywhere in the layout.** `C2.1.7`, `C2.1.52` and the rest are contract deliverable numbers that exist only in the contract; nothing in the repository maps a tenant to one. Older packages carry one as an extra folder level (`Deliverables/C2.1.7 Agricultural Permits (DAM)/Consumer/`) — do not reproduce it, do not ask for it, and do not derive a substitute. The tenant code in each filename identifies the package. When you touch a package that still has that level, lift its five folders up into `Deliverables/` so one tenant never has both shapes.

### The three roles are three different documents

A tenant is routinely **both a Consumer and a Provider at the same time**, and then all three documents differ:

| Document | Contains |
|---|---|
| `(c)` Consumer | Only the **Consume** endpoints — what this tenant calls, served by other systems and tenants |
| `(p)` Provider | Only the **Provide** endpoints — what this tenant serves, backed by its own institution's system |
| `(t)` Tenant | **Both kinds. Every endpoint of this tenant, without exception** |

All three share one chapter structure; the role decides which endpoints sit under the single **Endpoints** chapter, never which chapters exist (step 5).

The Tenant document is the complete one and the one to build first; the other two are projections of it. WCF's package is the worked example: four Consume endpoints in `(c)`, one Provide endpoint in `(p)`, all five in `(t)`.

Only where a tenant plays a single role do two of the documents coincide — a consume-only tenant's `(c)` and `(t)` are the same content, which is why the older DAM and PQPS packages have just the one document filed twice. Do not generalise from those to a tenant that also provides.

Whatever the role, the role word lives in three places, and the last is a separate part of the package that a body-text comparison will not show: the `(c)`/`(p)`/`(t)` marker in the filename, the role word on the cover, and the role word in the running header. All three must agree, and the filename marker must match the folder. A published package has `1. Consumer/PQPS (t) API Specifications.docx`, whose header reads "PQPS Tenant API Specifications" — the Tenant document filed and named as the Consumer one.

## Arguments

| Argument | Meaning |
|---|---|
| `<Tenant>` | Tenant code, e.g. `PQPS`, `APIS`, `DAM`. Required |
| `--route <r>` | Gateway route, without `/t/`. Defaults to the tenant code lowercased. Pass it when the real route differs (`mcti/zabs`, `govzm/ZamPass`) |
| `--roles` | Which documents to render. Default: whichever the tenant actually has — `tenant` always, `consumer` when it consumes, `provider` when it provides |
| `--out <dir>` | Where the package is written — this directory holds the five role folders directly. Default: `src/Tenants/<Tenant>/Deliverables/`. Override only when the user asks for a location outside the repository |
| `--version <X.Y>` | Document version. Bump only when the contract changed; keep it for a docs-only re-render |
| `--author <name>` | Author on the Document History row. Default `dotGov Solutions LLC` |
| `--provide-paths <path> ...` | OpenAPI paths that are Provide; every other path is Consume. Passed straight to `build_package.py`. When absent, settled in the classification question below |
| `--gate <n>/<N>` | Gate mode, set by `tenant-pipeline` |
| `--auto` | No questions. Every default; stops with `unresolved endpoint <path>: pass --provide-paths` when an endpoint is `UNKNOWN` or `Provide?` |
| `--dry-run` | Run `inspect_tenant.py` and the review, then stop. Nothing is built or written |

## Questions

Questions follow `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`. Run `inspect_tenant.py` first: every default below comes from it or from the package on disk (R5), never from the developer's memory.

**Gate** — only with `--gate <n>/<N>`. One call:

| Header | Question | Options |
|---|---|---|
| `Step <n>/<N>` | `/tenant-deliverables <T>` — build the OpenAPI JSON, the Word specifications and the Postman collection into `Deliverables/`. Run it? | `Proceed (Recommended)` — route `<route>`, version `<v>`, roles `<roles>`, author `dotGov Solutions LLC`, superseded files to `Archive/` · `Customize…` — choose version, roles, author, output folder · `Skip` · `Stop` |

The defaults written into `Proceed` are the real values: the route from `GATEWAY-CONFIG.md`, the roles `inspect_tenant.py` derived, and the version. That's `1.0` for a new package; for an existing one, the version in the running header of `Deliverables/Tenant/<CODE> (t) API Specification.docx`, read by unzipping `word/header*.xml`, never by opening it in Word. `Skip` → `GATE-RESULT: skipped`. `Stop` → `GATE-RESULT: stopped`.

**Customize** — `Customize…` only, or without a gate when the flag is absent and there's a real choice:

| Header | Question | Options | → flag |
|---|---|---|---|
| `Version` | Document version? | New package: `1.0 (Recommended)` · `0.9 — draft for review`. Existing `<v>`: `Keep <v> — docs-only re-render (Recommended)` · `<v+0.1> — the contract changed` · `<major+1>.0 — breaking change` | `--version` |
| `Roles` | Which documents? | The derived set `(Recommended)`, e.g. `Tenant + Consumer — derived from the injected clients` · `All three` · `Tenant only` | `--roles` |
| `Author` | Author on the Document History row | `dotGov Solutions LLC (Recommended)` · the `git config user.name` value | `--author` |
| `Output` | Where to write the package? | `src/Tenants/<T>/Deliverables/ (Recommended)` · the `--out` of the last run, if state has one | `--out` |

**Classification** — always asked when `inspect_tenant.py` reports any endpoint as `UNKNOWN` or `Provide?`, because a wrong split is a wrong contract (step 3). One question per endpoint, 4 per call, header `Split`:

```
GET /t/pqps/hub/pesticides — HubModule injects PqpsService (Endpoints:Pqps). Consume or Provide?
  ( ) Provide — served from PQPS's own system (Recommended)
  ( ) Consume — reached through the ZamConnect gateway
```

The description names the injected client and the config section that decided the recommendation. When the pipeline state records `role: provide` for the integration that added a route, that is the recommended answer. The answers become `--provide-paths`.

**Review** — one R6 call before `build_package.py` writes anything. Options `Apply (Recommended)` · `Adjust` · `Cancel`. The question text lists the documents per role folder, what moves to `Archive/`, and the equivalent command. With `--dry-run`, print it and stop.

**Code findings** — after the build, when the report lists code findings (missing `///`, `.WithTags`, `.WithSummary`, undeclared response codes), and not with `--auto`, ask with header `Findings`:

- `Fix them now, then re-render (Recommended)` — invoke `tenant-integration <T> --spec-only`. It makes the code changes, which this skill never does. Then re-run `build_package.py` with the same flags
- `Hand over the list` — keep the documents as rendered, and report the findings by file and member
- `Stop`

This skill still writes no code. The fix is `tenant-integration`'s, run as a separate step that the developer picked.

## 1. Establish the tenant's shape

`python scripts/inspect_tenant.py <TENANT>` answers this section and the two after it in one pass — shape, route, every endpoint with its Consume/Provide section and the client that decided it, the `Endpoints:*` configuration, committed credentials, Swagger readiness, and the roles to render. Read its output instead of opening the files below one at a time. What follows is what it is reading, and how to settle what it reports as `UNKNOWN`.

Three shapes exist, and the route inventory is gathered differently for each. Decide this first — getting it wrong is how a spec ends up with an empty Endpoints section.

| Shape | How to recognise it | Where the routes are |
|---|---|---|
| **Carter / minimal API** | `src/Tenants/<Tenant>/Modules/*.cs` with `ICarterModule` and `MapGet`/`MapPost` | The module files themselves |
| **MVC controllers** | `src/Tenants/<Tenant>/Controllers/*Controller.cs` with `[ApiController]` | The `[Route]` on the class plus `[HttpGet("…")]` on each action |
| **Virtual tenant** | **No `src/Tenants/<Tenant>` folder at all**, and no `core-<slug>` service in `src/.dockercompose/docker-compose.yml` | A gateway route that fronts the shared modules — `src/Core/Shared/Modules/*SharedModule.cs` |

The virtual shape is real and easy to miss. `DAM` has no project, no container and no pipeline; its surface is `EServicesSharedModule` reached through a `/t/dam` route that lives in the gateway's Mongo configuration, not in the repository. Confirm with:

```bash
ls src/Tenants/<Tenant> 2>/dev/null; grep -n "core-<slug>" src/.dockercompose/docker-compose.yml
```

Both empty means virtual. Then find which shared module supplies the surface:

```bash
grep -rn "EServicesSharedModule\|SharedModule" src/Core/Shared/Modules/
```

A tenant with its own project can *also* inherit from a shared module — a base class contributes routes that a grep of `src/Tenants/<Tenant>/` will never show. Always walk the base class of every module you find.

## 2. Derive the route exactly as a consumer will call it

This is the rule the published specs follow and the one most often got wrong:

> **Every path in every artifact is `/t/<route>` + the tenant-internal path.**

Nothing describes the endpoint by its internal path alone. YARP strips `/t/<route>` before forwarding, so the tenant's own code and its Swashbuckle output both see the short form; the consumer never does.

For MVC controllers the internal path is built from the attributes, with the tokens expanded:

| In code | Expands to | Document shows |
|---|---|---|
| `[Route("[controller]")]` on `HubController` | `/hub` | — |
| `[HttpGet("pesticides")]` | `/hub/pesticides` | `GET /t/pqps/hub/pesticides` |
| `[HttpPost("validate/ePhyto")]` | `/hub/validate/ePhyto` | `POST /t/pqps/hub/validate/ePhyto` |

The `[controller]` token expands to the class name minus its `Controller` suffix, written **lowercase** in the document — `HubController` → `hub`, giving `/t/pqps/hub/pesticides`. Action-segment casing is preserved as written (`validate/ePhyto`, `importEnvelopeHeaders`), because those are literal strings in the attribute rather than a token.

Two notations, deliberately different, and each artifact uses one consistently:

| Artifact | Path parameter |
|---|---|
| DOCX | `:registrationNumber` — colon |
| OpenAPI JSON, Postman | `{registrationNumber}` — braces |

The parameter **name** must be identical in all three, and so must its casing. A published package writes `IdentityNumber` in the DOCX and `identityNumber` in the OpenAPI for the same query parameter; ASP.NET binds either, so nothing fails at runtime and the inconsistency ships. Another names a path parameter `{registrationNumber}` in the OpenAPI and `:entityNumber` in the Postman collection for the same operation.

## 3. Split the endpoints into Consume and Provide

`inspect_tenant.py` reports this per endpoint with the client that decided it. Two of its answers need you: `UNKNOWN` means it could not name the client, and `Provide?` means it inferred one from a matching `Endpoints:<Name>` section rather than reading it. Open that module and settle it — an endpoint in the wrong section is a wrong contract, and `build_package.py` will not classify one for you.

Each endpoint is exactly one of Consume or Provide, and the assignment is mechanical — read it from the client the module takes, never guess it from the path.

| Section | The endpoint's data comes from | Recognised by |
|---|---|---|
| **Consume** | Another system or tenant, reached back out through the gateway | The module injects the `ZamConnect` client (`Endpoints:ZamConnect`, a `RestEndpoint` pointed at the API gateway) |
| **Provide** | This tenant's own institution | The module injects the tenant's own client (`Endpoints:<Tenant>`, e.g. `Endpoints:Wcf`) |

```bash
grep -rn "class .*Module(" src/Tenants/<Tenant>/Modules/
```

WCF reads straight off that one command: `BusinessEntitiesModule(ZamConnect …)`, `NapsaEmployersModule(ZamConnect …)`, `NapsaMembersModule(ZamConnect …)` and `PersonsModule(ZamConnect …)` are Consume; `EmployersModule(WcfService …)` is Provide.

**Both sections live in the tenant's own route space.** Every endpoint is `/t/<route>/…` whichever section it falls in — `/t/wcf/napsa/members` is a Consume endpoint and `/t/wcf/employers` a Provide one. The split is by where the data originates, not by the shape of the path, so it cannot be inferred from the URL. A tenant whose Consume endpoints carry another system's name in the path (`/pacra/…`, `/napsa/…`, `/nir/…`) makes this look derivable from the route; it is not, and `/t/wcf/employers` is the counterexample.

A tenant with no `Endpoints:<Tenant>` client of its own provides nothing — it is consume-only, and it gets no Provider document.

## 4. Produce the OpenAPI document

When the tenant builds and exposes Swashbuckle, generate rather than hand-write. `build_package.py` does all of this; the individual calls, for a one-off:

```bash
dotnet build src/Tenants/<Tenant>/<Tenant>.csproj -c Debug
cd src/Tenants/<Tenant>/bin/Debug/net10.0
ASPNETCORE_ENVIRONMENT=Development dotnet tool run swagger tofile --output swagger.json <Tenant>.dll v1
cd -
python scripts/apply_gateway_route.py \
  src/Tenants/<Tenant>/bin/Debug/net10.0/swagger.json --route <route>
```

The working directory and the environment variable both matter and both fail confusingly — the content root comes from the working directory, and the base `appsettings.json` ships unsubstituted `__Token__` URLs that only the Development layer replaces with something `Uri` can parse. `apply_gateway_route.py` is idempotent and also fills `servers` from `scripts/environments.py`.

For a virtual tenant, or a tenant without Swashbuckle, assemble the document by hand from the route inventory of step 1 and the DTO types each route produces. Same result, same shape: `openapi: 3.0.x`, `info`, `servers`, `paths`, `components.schemas`.

Whichever way it was produced, the document must satisfy all of:

| Field | Requirement |
|---|---|
| `info.title` | `<full descriptive name> (<CODE>)` — `Plant Quarantine and Phytosanitary Service (PQPS)`. **Never a class name.** A published spec ships `"title": "HubController"`, which is what happens when the export is taken unchecked |
| `info.version` | The document version, matching the DOCX cover |
| `servers` | The three environment URLs from `scripts/environments.py` |
| `paths` | Every key prefixed with `/t/<route>` exactly **once**. A published spec ships `/t/pqps/t/pqps/Hub/pesticides` — re-running the prefix step over an already-prefixed document by hand |
| `components.securitySchemes` | HTTP Basic. Every tenant is Basic-authenticated; a spec that omits this tells the consumer nothing about how to authenticate |
| tags | A domain name per logical group — `NAPSA`, `PACRA`, `NIR`, `Employers` — so the Postman step can fold by tag |
| `parameters[].required` | Set on every parameter. Published specs leave it unset throughout, so nothing distinguishes a mandatory query parameter from an optional one |
| `responses` | Exactly the status codes the code declares. Not fewer, not invented ones |

Three published specs ship three different wrong titles — `"HubController"`, `"DAM"`, `"WCF"`. A class name, and two bare codes: none is `<full name> (<CODE>)`.

**Tags default to the C# class name** when no route calls `.WithTags(…)`, which is how a published spec ends up advertising `BusinessEntitiesModule` and `NapsaEmployersModule` to a third party. Detect it:

```bash
grep -rLn "WithTags" src/Tenants/<Tenant>/Modules/     # files listed here have no tags
```

The fix belongs in the module, and this skill does not make it. Report each module file that needs `.WithTags(…)` so the user can change it and re-run; meanwhile the tag stays as the export produced it.

Response codes are worth checking against the code rather than the older document. A published DOCX documents `404` and `400` for an endpoint whose module declares only `.Produces(200)` and `.Produces(500)`, and gives `Person` as the type of a `500` response where the code returns `ProblemDetails`. The code is the contract — document what it declares, and report any mismatch with the older document rather than reconciling it by editing either side.

## 5. Fill every compartment from source

The section order is fixed. Nothing may be left as template text, and nothing may be invented — each compartment has exactly one source.

**The document has exactly these six chapters (Heading 2), in this order, and no others:**

```
1. Executive Summary
2. Glossary
3. Endpoints
     3.1 GET /t/<route>/<path>          one Heading 3 per endpoint
4. Schemas
     4.1 ProblemDetails
     4.2 ProblemDetailsDefinitions
     4.3 …                              remaining DTOs, alphabetically
5. API Environments
     5.1 Development
     5.2 Staging
     5.3 Production
6. Contacts and Signature               no Heading 3 — the sub-titles are bold body text
```

Executive Summary is dropped only when `info.description` is empty; the other five are always present. `openapi_to_docx.py` refuses to render any other Heading 2, and `verify_package.py` fails a document whose chapters differ. There is no Consume or Provide chapter.

| # | Compartment | Source |
|---|---|---|
| | Cover: full name, `(<CODE>)`, role | `info.title` and the role being rendered |
| | Cover: Project, Client, Contract No., Prepared by | Fixed platform constants — copy from any published spec, they do not vary per tenant |
| | Disclaimer | Fixed. Copy verbatim |
| | Document History | One row per real revision: Description, Author, Version, Date. Prior rows are carried forward, never rewritten. **Bump the version with the revision** — a published spec carries four history rows all at `1.0` |
| | Table of Contents | Generated by Word, see step 6 |
| 1 | Executive Summary | `info.description`, **and only its first section**. What this tenant is and which datasets or upstream systems it exposes, derived from the endpoint inventory — `EServicesSharedModule` routes under `/nir/persons` and `/nbr/entities` are what makes DAM's summary read "Persons (NIR), Businesses (NBR)". Do not describe capabilities no route provides |
| 2 | Glossary | A Term / Definition table. Always `API`, `ZamConnect`, `<CODE>`; then every acronym from `GLOSSARY` in `scripts/openapi_to_docx.py` that appears in the document's text. An acronym missing from that table is left out rather than given an invented expansion — add it to `GLOSSARY` |
| 3 | Endpoints | One Heading 3 per endpoint the role carries: `(c)` the Consume endpoints, `(p)` the Provide ones, `(t)` all of them, Consume first (see step 3) |
| | — each endpoint | Heading 3 titled `<METHOD> /t/<route>/<path>`. A prose sentence saying what it returns and from where, then **Input parameters** (Parameter Type, Name, Type, Description) and **Response** (Status Code, Content-Type, Type, Description). Parameter types come from the route signature; response codes and types come from `.Produces<T>(…)` or `ActionResult<T>`, never from a previous document |
| 4 | Schemas | `ProblemDetails` first, its `ProblemDetailsDefinitions` next, then the rest alphabetically. One Heading 3 per DTO reachable from the endpoints **this document contains**. Name, Type, Description; descriptions from `///` XML doc comments. An enum-valued property lists its members inline (`0 – Unknown`, `1 – Phone`, …) rather than saying "integer" |
| | ProblemDetails + ProblemDetailsDefinitions | Every tenant returning problem details documents both: the envelope, and the table of concrete Title/Detail/Status/Registry triples the tenant can actually emit. Read these from the tenant's `CustomResults.Problem` call sites and its `Error` definitions — an invented error code is worse than an omitted one |
| 5 | API Environments | Heading 3 per environment — Development, Staging, Production. The three Base URLs from `scripts/environments.py`, with their prose, plus a worked example concatenating the Base URL with one real route of this tenant. **Never copied from an older spec** — published specs carry stale URLs (`api.dotgov.uk`, `api.stage.gov.zm`) that no longer resolve |
| 6 | Contacts and Signature | `templates/contacts-and-signature.xml`, spliced in verbatim — the block from the published WCF `(t)` specification: bold "Client representatives" and "DotGov representatives" captions, each with an empty First Name / Last Name / Position / E-mail / Phone table, a signature rule and a `[signature of the … Representative]` caption. **Left blank.** It is filled in at signing; filling it here would put named individuals' contact details into a document going to a third party. Change the layout by editing the fragment, never the rendered DOCX |

**Only the Executive Summary comes from `info.description`.** A tenant's Description frequently runs on past the summary into `## Submission model`, `## Record structure`, `## Authentication`, `## Errors` and the like. Every one of those would render as its own numbered top-level section, pushing reference prose ahead of the Endpoints section and restating what the endpoint and schema tables already carry. `openapi_to_docx.py` keeps the first section under the heading Executive Summary, turns any `###` inside it into a bold lead-in, and drops every later Heading 2 — that is deliberate, not a truncation bug. A heading inside a route's `.WithDescription(…)` is likewise rendered as a bold lead-in, so it cannot open a chapter. Content that has to reach the document belongs either in the summary itself or in the route's `.WithDescription(…)`, which renders under its own endpoint.

Two naming traps in the section headings:

- The first API environment is headed **Testing** in one published spec and **Development** in the others, while all of them describe "Development environment (DEV)" in the prose beneath. Heading and prose must agree; use one and hold it.
- Schema headings are suffixed " Schema" in two published specs and not in the third. Pick one per document.

**Scope the Schemas section to the document.** All three of one package's role documents carry the identical full schema set, so the Provider document defines `NapsaMember` and `Person` although its single endpoint returns neither. Either scope each document to what its own endpoints reach, or carry the union in all three — but do the same thing in all three, and say which.

Absent `///` comments and `.WithSummary(…)` on routes, the tables come out with empty Description columns. That is a code fix, and this skill does not make it — render the document with the columns as thin as the source leaves them, and report every DTO property and route that needs a comment, by file and member. Do not invent a description to fill the cell: a description typed straight into the DOCX is both unsourced and lost at the next render.

## 6. Render the Word document, once per role

`build_package.py` does this once per role. The underlying call, for a one-off re-render:

```bash
python scripts/openapi_to_docx.py \
  <swagger.json> "<CODE> (t) API Specification.docx" \
  --tenant <CODE> --role Tenant --version <X.Y> --author "<name>" --route <route> \
  --sections sections.json [--only-section Consume|Provide]
```

Render the Tenant document first — it is the complete one — then the Consumer and Provider documents as projections of it, each dropping the endpoints it does not own:

| File | Role word | Endpoints | Flags |
|---|---|---|---|
| `<CODE> (t) API Specification.docx` | Tenant | Consume **and** Provide | `--role Tenant` |
| `<CODE> (c) API Specification.docx` | Consumer | Consume only | `--role Consumer --only-section Consume` |
| `<CODE> (p) API Specification.docx` | Provider | Provide only | `--role Provider --only-section Provide` |

`--sections` is a JSON file mapping every OpenAPI path to `Consume` or `Provide`. It has to be supplied because the OpenAPI document carries no such marker — the split is read from the client each module injects (step 3), and nothing in the HTTP surface reflects it. The renderer refuses a mapping that leaves any path unclassified, so an endpoint can never be dropped from the Tenant document silently.

`--only-section` also scopes the Schemas section to the DTOs that section's endpoints actually reach, which is what stops a Provider document defining the response types only its Consumer counterpart returns. The `(t)` document carries the union.

`--role` takes `Tenant`, `Consumer` or `Provider` (`Both` is accepted as the older spelling of `Tenant`). Skip a role with no endpoints rather than shipping a document with an empty section — `--only-section` refuses outright when it would leave the document empty. Repaginate through a real Word instance so the Table of Contents and page numbers are exact — the script does this and falls back to estimates with a warning if Word is unavailable. Estimated page numbers are not shippable; re-run where Word is present.

The renderer also scrubs the package on the way out: `dc:creator`, `dc:title`, `dc:subject` and `cp:lastModifiedBy` in `docProps/core.xml` (Word's own save during repagination re-stamps the last of those, so the scrub runs after it), the ~1.1 MB of `divsChild` junk in `word/webSettings.xml`, any `[trash]/*` part, and a `Table Grid` style on every table including the template's own Document History.

File names follow `<CODE> (c|p|t) API Specification.docx`. One published spec uses the plural "Specifications" — that is legacy, do not copy it forward.

Render from `templates/api-specification-template.docx`. Never start from a published tenant's document: it carries that tenant's headers, history rows, bookmarks and metadata, and every one of them has to be found and replaced by hand.

### The format the template encodes

Worth knowing even though the renderer handles it, because this is what to check when a render looks wrong.

| | |
|---|---|
| Page | US Letter, 12240 × 15840 twips. Margins 1440 top/bottom/left, **1080 right**, header and footer 720 |
| Sections | `titlePg` with distinct first-page and even-page header/footer parts. The cover deliberately has none of either |
| Body default | Times New Roman 12pt, set in `docDefaults` |
| Logo | `word/media/image1.png` on the cover. A render that lost it is broken |

Styles carry the whole look; nothing is formatted inline:

| Element | Style | Appearance |
|---|---|---|
| Section title (Executive Summary, Glossary, Endpoints, Schemas, API Environments) | **Heading 2** | Times New Roman 22pt bold, grey `A6A6A6`, outline level 1 |
| Endpoint and schema title | **Heading 3** | Times New Roman 16pt regular, blue `3B3F8B`, outline level 2 |
| Body prose | `paragraph` | Times New Roman 12pt, auto spacing before and after. **Not `Normal`** |
| Disclaimer block | `Disclaimer` | Times New Roman 8pt |
| Bulleted list | `ListParagraph` | |
| Every table | `Table Grid` | |

**Sections are Heading 2, not Heading 1.** `Heading1` is defined (Calibri 16pt, `2F5496`) and used nowhere. Emitting one puts a stray blue Calibri line in a document that is otherwise Times New Roman, and a TOC1 row among TOC2s.

Consistency is not a given in the published set, so follow the template rather than a sample: one published spec styles its disclaimer as `paragraph` instead of `Disclaimer`, and table styling is all over the place — 57 tables with no style at all in one document, a mix of 20 `Table Grid` and 15 unstyled in the other. Use `Table Grid` throughout.

### Headers, footers and fields

These are separate parts of the package. Extracting the body text shows none of them, which is how they go stale.

- **Header (default and even):** `<CODE> (<Role>) API Specification    Version <X>.<Y>`. Role- and version-specific, so it changes on every render and every version bump.
- **Footer (default and even):** `Prepared by: dotGov Solutions LLC <YYYY>.    Last modified: <date>    Page <n> of <N>`.
- **Cover:** first-page header and footer are empty by design.

The footer holds four live Word fields — `DATE \@ "yyyy"`, `DATE \@ "MMMM d, yyyy"`, `PAGE`, `NUMPAGES`. Two consequences:

1. **`DATE` is live, not a stamp.** Open a delivered document in Word and save it, and "Last modified" silently becomes that day's date, on a file that did not otherwise change. Never re-save a shipped document to "check" it.
2. **`NUMPAGES` cannot be trusted from a recalculation.** Both published specs ship a wrong cached count — a 26-page document whose footer says "of 17", and one that says "of 38" on one page and a different total on another. The renderer takes the count once from `ComputeStatistics(2)` after the TOC stabilises and writes it into the cached field text. Do not "fix" this by re-adding a blanket `Fields.Update()` across all `StoryRanges` — that is the exact thing that produced page counts oscillating between 32 and 3 on an unchanged document.

### Table of Contents

The field is `TOC \o "1-3" \h \z \u`: hyperlinked, with a `_Toc…` bookmark and a `PAGEREF` field per entry. Since only Heading 2 and Heading 3 are used, it renders as TOC2 and TOC3 rows.

Three failure modes, all present in the published set:

- **Stale.** One spec has 72 Heading 3s and 71 TOC3 rows — a heading added without the TOC being regenerated.
- **Empty heading.** An empty Heading 3 produces a blank, clickable TOC row that leads nowhere. Never emit a heading with no text.
- **Untrimmed heading text.** Published headings begin with a space (` Executive Summary`, ` Glossary`, ` Endpoints`), which carries straight into the TOC. Trim every heading.

Also watch for **duplicate headings** — one spec emits `Consignment Schema`, `ExchangeDocument Schema` and `UsedTransportMean Schema` twice each. Either the same schema is rendered twice, or two distinct schemas are colliding on one display name; both need the schema inventory fixed, not the heading renamed.

Schema heading naming differs between the two published specs: one suffixes every heading with " Schema", the other does not. Pick one per document and hold it.

### Document metadata and package hygiene

`docProps/core.xml` travels with the file and is visible to whoever receives it.

| Field | Set to |
|---|---|
| `dc:title` | `<full name> (<CODE>) API Specification` |
| `dc:subject` | `API Specification` |
| `dc:creator` | `dotGov Solutions LLC` |
| `cp:lastModifiedBy` | Cleared |

The template inherits a previous author's name in `dc:creator` and a different person's in `cp:lastModifiedBy`, and both propagate into every render unless overwritten. One published spec ships a personal email address as `dc:creator` — inside a document handed to a third party. Treat that as the sensitive-data rule below, not a cosmetic detail.

Two pieces of carried-over junk to strip while you are there: a `[trash]/0000.dat` part in one published document, and a `word/webSettings.xml` of roughly 1.1 MB — leftover `divsChild` data from an HTML paste, present in both published specs and in the template, and larger than the rest of the document combined.

## 7. Build the Postman collection

```powershell
powershell -File scripts/openapi_to_postman.ps1 `
  -Tenant <CODE> -SwaggerJson <swagger.json>
```

It goes in `Tenant/` only, as `<CODE>.postman_collection.json`, and covers the whole surface — both Consume and Provide. Required shape:

- `info.name` is the tenant code alone, matching the collections already in `postman collections/`.
- Requests addressed at `{{zc_base_url}}`, with `/t/<route>/…` as the literal path. Not a per-tenant host variable.
- Collection-level **Basic** auth using `{{username}}` / `{{password}}`. One published collection ships `{{test}}` for both fields; another is `"type": "bearer"` with `{{your_access_token}}` — bearer is not how any tenant authenticates, and a collection that says so will not work for the consumer who receives it.
- Foldered **by tag**, not by URL segment. Segment foldering produces the nesting a published collection shows — `nir` > `persons` > `zampass` > `{zamPassId}` for a single request — which nobody navigates. Partial foldering is no better: one published collection has a single `NAPSA` folder and four requests loose at the root.
- Request names are the operation, `GET /nir/persons/identity-document`, not free text like "Nir person".
- **Every path must carry the tenant route.** A published collection requests `{{zc_base_url}}/t/napsa/employers` where the endpoint is `/t/wcf/napsa/employers` — the tenant segment dropped, so the request 404s as shipped. Diff every URL in the collection against `paths` in the OpenAPI document.

**Example values are the biggest risk in this file.** One published collection carries what read as live identifiers — an NRC, a TPIN, a PACRA registration number, an employer number — baked into request URLs, in a file handed to a third party. Use obviously synthetic values, and never copy a value out of a developer's working collection.

## 8. Gates

Every one of these is a defect found in an already-published package. `verify_package.py` is all
of them in one command, and `build_package.py` ends by running it:

```bash
python scripts/verify_package.py src/Tenants/<Tenant>/Deliverables --route <r> --version <X.Y>
```

It checks the OpenAPI document, opens each DOCX as a package rather than extracting its text
(headers, footers, styles and metadata are separate parts, and are exactly where staleness
hides), diffs the `(c)` and `(t)` bodies against each other, cross-checks every Postman URL
against `paths`, and confirms the five folders exist. `Archive/` is skipped — it holds
superseded versions by design. Exit code is non-zero if anything failed, so it can gate a commit.

| Gate | Fails when |
|---|---|
| Prefix | Any path does not start with `/t/<route>`, or contains it twice |
| Title | `info.title` is a class name, or omits `(<CODE>)` |
| Parameter names | The same operation names a path parameter differently in the DOCX, the OpenAPI and the Postman collection |
| Environments | A Base URL in the document differs from `scripts/environments.py` |
| Placeholders | Any `{{…}}`, `TODO`, `__Token__` or template text survives in the DOCX — **including in the header and footer parts** |
| Empty columns | A Description column is blank for more than a couple of rows — the source lacks XML doc comments |
| Filing | The `(c)`/`(t)` marker in the filename does not match the folder the file sits in, a role folder carries a numeric prefix, or a folder sits between `Deliverables/` and the role folders |
| Role agreement | The filename marker, the cover role word and the running header role word disagree |
| Chapters | The Heading 2 list is not Executive Summary, Glossary, Endpoints, Schemas, API Environments, Contacts and Signature in that order (Executive Summary alone may be absent) |
| Signature block | The Contacts and Signature tables are populated |
| Tenant completeness | An endpoint in the module inventory has no Heading 3 in the `(t)` document |
| Consume/Provide split | An endpoint sits in a role document that contradicts the client its module injects |
| Response codes | A status code in a response table is one the module does not `.Produces`, or an error row's type is not `ProblemDetails` |
| Required flags | An OpenAPI parameter has no `required`, or the DOCX marks optionality inside the Name cell instead of its own column |
| Tags | An OpenAPI tag is a C# class name — no route calls `.WithTags(…)` |
| Environment heading | The first environment's heading and its prose name different environments ("Testing" over "Development environment (DEV)") |
| History | Two history rows share a version |
| Header version | The `Version <X>.<Y>` in the running header differs from the cover and from `info.version` |
| Heading level | Any Heading 1 is used; sections must be Heading 2 |
| Heading text | A heading is empty, has leading or trailing whitespace, or repeats another heading |
| TOC | TOC3 row count differs from the Heading 3 count — the TOC was not regenerated |
| Pagination | The renderer fell back to estimated page numbers, or the footer's cached `NUMPAGES` differs from `docProps/app.xml`'s `Pages` |
| Table style | A table carries no style instead of `Table Grid` |
| Metadata | `dc:creator` is a person rather than `dotGov Solutions LLC`, `cp:lastModifiedBy` is populated, or any email address appears in `docProps/core.xml` |
| Package | A `[trash]/*` part survives, or the logo `word/media/image1.png` is missing |
| Pair equality | The `(c)` and `(t)` documents differ anywhere beyond the role word on the cover and in the header |
| Postman auth | Not collection-level Basic with `{{username}}`/`{{password}}` — `{{test}}` or a bearer token |
| Postman routes | A request URL is absent from the OpenAPI `paths`, or drops the `/t/<route>` segment |
| Postman data | A request carries a real-looking NRC, TPIN, registration or account number as an example value |

One check cannot be automated: **never open a shipped DOCX in Word and save it.** The footer's `DATE` fields are live, so saving rewrites "Last modified" on a document whose content did not change. Inspect by unzipping the package, not by opening it.

## 9. Place the package and report

Write into `src/Tenants/<Tenant>/Deliverables/` itself (unless `--out` overrides it), creating `Consumer`, `Provider`, `Tenant`, `Integration Requests` and `Archive` even where some stay empty — a consumer looks for all five.

**Move, never overwrite.** A superseded version goes to `Archive` before the new one lands. These are delivered artifacts other people already reference; replacing one in place destroys the record of what was sent. `build_package.py` does this for you, into `Archive/<YYYY-MM-DD HHMM>/`, before it writes anything.

`Integration Requests` is never generated. It holds upstream material — the counterpart's own API document, mapping spreadsheets, sample certificates — plus a `readme.md` giving the source URL of each. Carry these across unchanged and leave the readme's links intact.

Report: every file written with its path, which gates passed, whether Word repagination succeeded or fell back, and a **Code findings** list of everything the source could not supply — missing `///` comments, missing `.WithTags(…)`, undeclared response codes, committed credentials — each with the file and member to change. These are handed over, never applied: the only files this run touched are the ones listed under `Deliverables/`.

End with the equivalent command (R7), e.g. `/tenant-deliverables PQPS --route pqps --version 1.0 --roles tenant,provider --provide-paths /t/pqps/hub/pesticides`. In gate mode, the last line is `GATE-RESULT: ran`, or `GATE-RESULT: failed <gate or reason>` when a gate fails on something other than a reported source gap.

## Sensitive data

No credential ever goes into this skill, into anything it generates, or into its report. That means passwords, connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and equally the things that locate them: internal host names, server IP addresses and database endpoints.

- In generated config, a secret is a `__Token__` placeholder. Name the variable group, pipeline variable or secret store that supplies the real value, and leave the value out.
- A credential passed to you as an argument is used in the one command that needs it and nowhere else. Never echo it, never write it to a file, never put it in a commit message or a PR description, and redact it in every line of output.
- Never copy a credential out of a file you read, even when the repository already commits it. Finding one in the repo is a finding to report, not a value to reuse.

This applies with particular force here, because the output is handed to a third party. A generated Postman collection authenticates through `{{username}}` / `{{password}}` environment variables and carries no values; the older hand-maintained collections in `postman collections/` have real credentials committed into them, and those are a finding to report, never a pattern to copy into a deliverable.
