---
archived: 2026-10-04
---
# Implementation Plan: `/dgf-scaffold` — a new DGF application, from an empty folder

Branch: feature/dgf-scaffold (stacked on `feature/dgf-specific-skills` at `616b666`; that branch merges into `develop` first)
Created: 2026-09-29
Refined: 2026-09-30 (`/aif-improve`: one task added, ten improved, two dependencies fixed)

## Original Request
create architecture for /dgf-scaffold command.
in research.md file is research through some live systems build on DGF.
But i'd like /dgf-scaffold  to scaffold different things, from simple page to whole applications with multi-tenantcy and other advanced things.

so in that sense, first of all i think that scaffold command willanalyse user prompt and will understand what it should scaffold. depending on that it will collect context for generating simople things in right place or plan application architecture and database and build app based on that.
In case of abiguity user will be surveyed to get context to solve ambiguites or to understand better user expectations

## Refined Request (2026-09-29)
ok, then /dgf-scaffold mult create an app from scratch, it should be executed in empty folder. it must prepare the application solution structure: api (or many), docker, database, workspaces, documentation. Create required workspaces, configure authentication, and also according to user request: create workspace artefacts.

## Settings
- Testing: yes — unit tests for both scripts, golden-output tests for the generator, a generated-application test that runs the
  post-generation check, contract tests for the skill, and a known-bad case for every new blocking finding and exit-3 path
- Logging: verbose — `report.debug("<module.fn>", "<event>", key=value, …)` traces under `--verbose`, as every script does
- Docs: yes — Task 13 is the mandatory documentation checkpoint

## Roadmap Linkage
Milestone: "DGF-Specific Skills"
Rationale: `/dgf-scaffold` is the milestone's one unbuilt item; this plan builds it and supersedes the two decisions that blocked it.

## What `/dgf-scaffold` does

**It creates a new DGF application from scratch, in an empty folder, and generates everything itself:**
- the solution structure: one or more API hosts, Docker, the database project, the workspaces and the documentation;
- the required workspaces;
- the authentication configuration;
- the workspace artefacts the request describes.

It then hands the new workspaces root to the pipeline: `/dgf` sets it up, and every later change is brownfield work for
`/dgf-plan` and `/dgf-implement`.

```
empty folder + "an inspections app for three directorates: a permit register and an approval service, DGPass sign-in"
  0 empty?     design.py --empty-only                               (script)
  1 design     the model turns the request into docs/application.json
  2 validate   names, references, data model, SQL types; what is open; every default  (design.py)
  3 survey     ask only what is open; back to 2
  4 confirm    the defaults (design.py DEFAULT: lines) and the tree (generate.py --dry-run)
  5 generate   solution + workspaces + artefacts, from shipped templates (generate.py)
  6 check      structure, routes, secrets, and the validators over the generated files  (generate.py --check)
  7 report     how to run it, every value to fill in, next: /dgf <folder>/workspaces
```

It does nothing in a folder that is not empty, and it adds nothing to an existing application.

## Research Context
Source: `.ai-factory/RESEARCH.md` (Active Summary, Updated: 2026-09-29 22:55, SHA256: 5f8ecbe98787ebcc609097bc64bcf93275bf73cbd150e9e16b6d51c4b9f77dff)

Topic: `/dgf-scaffold` for the Zambia estate — what is common and what is specific across ZamOffice (`webasm`), eCouncils, ZILAS, ZMA and ZIMS, and which of it becomes a scaffold option.

The first finding is that this is not "drive an existing template". There is no generator. All four apps are clones of the ZamOffice repo shape, so `/dgf-scaffold` would be the first generator the estate has, and that conflicts with ADR 0004 §2. Everything below comes from the five reports. I spot-checked these numbers myself: 308, 1,015 and 888 files. I also confirmed ZMA's three tenant rows, its `WorkspaceName` per instance, and 8 files with hard-coded tenant GUIDs.

## Three layers, not one

```
 SOLUTION (identical shape in all 4)             WORKSPACE overlay              BASE (webasm)
 Web/ (DGE host, ~empty)                         FM/{_DATA,_WORKFLOW,           supplied at image build:
 EServices.API/ ── runs twice: front + back        _PROFILE,_PROCESS,             COPY --from=zamoffice image
 Components/{External,...}                         _COMPONENTS,Templates}         /workspaces/webasm   (pinned tag)
 Database/ (SSDT + StaticTables seeds)           _application.sitemap           local: bind-mount a ZamOffice
 Compose/  azure-pipelines  helm values          js/forms.shared.js             checkout
                                                 BASE:Name → webasm
```

The `BASE:` resolution is the only extension contract, and it is real. `zamoffice` uses it in 308 files, ZIMS in 450, ZILAS in 817 and eCouncils in 1,015.

## Common core (safe as defaults)

- **Solution:**
  - `Web` host with `BuildDotGovEngine()`.
  - `EServices.API` with `AddZamPay`, `AddDgNotify` and `AddDgNotifyOtp`, plus the job scheduler.
  - `Components/External`, an SSDT `Database/`, Compose and Helm values.
  - The `ZamCloud/pipeline-templates` pipeline.
- **appsettings blocks:** DGPass OIDC, Notify and OTP, ZamPay, DgSign, RegistrationAuthority, NIR/ZamConnect (with a `t/<name>` path), PinCodeSign, the distributed cache and Seq.
- **Workspace:** the FM skeleton, `_application.sitemap` with `BASE:_Portal*` links, `NirUserRegistrationPreRegIntranet`, the Workplace grid set, and the `Standard.Review_*` process family.

## Scaffold options (the axes that actually differ)

| Axis | Values seen |
|---|---|
| **Base supply** | Pinned image (ZIMS, ZILAS, ZMA). eCouncils forked it: 888 drifted files, and the intended `COPY --from` is commented out. A scaffold should offer only the pinned image. |
| **Instances** | Single (ZIMS, ZamOffice). Multi-instance (ZILAS with 4 departments, ZMA with 3 directorates). |
| **Org model** | Flat. Or an `AspNetTeams` council hierarchy (eCouncils). |
| **Designer host** | The `Web` builder is empty in ZIMS, ZILAS and ZMA, and commented out of their pipelines. It should default to off. |
| **Integrations** | ZRA, PowerBI, Gotenberg documents and ArcGIS maps are each optional. |
| **Reports** | SSRS and/or PowerBI. |

Two corrections to the framing:
- **ZMA is not runtime multi-tenancy.** It is multi-instance. ZILAS uses the same mechanism: the `WORKSPACE_NAME` build argument renames `_application-<ws>.sitemap`, and the pipeline builds N images. ZMA adds a shared database keyed by an `ApplicationId` column, with one `aspnet_Applications` row per instance. Isolation is by convention only, since there is no row-level security and by-name role lookups have caused real bugs. So there are two options here, not three: multi-instance, with or without the shared-database partition.
- **eCouncils' 34 `councils/` folders are not runtime config.** They are records for the AI harness in that repo. Per-council variation is done by forking forms, so `BuildingPermit<Council>` exists in about 20 copies.

## What every app gets wrong (never copy)

- **Secrets in git in all five, plus the ZMA `.mcp.json` and `Web/readme.md`.** They include OIDC secrets, SQL passwords, an Azure DevOps token, the PKI private key and the NuGet feed password. Every app's Helm values already use `__Token__` placeholders, so the scaffold should emit placeholders in appsettings too.
- **Environment URLs in base appsettings**, and `IgnoreSSLCertificateValidation=true`.
- **A duplicated, broken `Web/Dockerfile`** (two `final` stages).
- **Near-identical appsettings per instance.** Lands and Deeds differ by about 12 lines.
- **Stray `BASE:` references.** ZILAS has some that resolve to nothing, and one on a locally-defined table. The agent's check was name-based, so some may be false positives. I haven't checked any yet.
- **`webasm` isn't a clean base.** It holds Zambia-domain content (`ZIGS_*`, NIR). The scaffold shouldn't try to fix that.

## Open questions (they change the design)

1. **ADR 0004 §2 no longer holds for Zambia.** It says the skill "drives a template; does not emit files". There is no template. Options: a new ADR that supersedes §2 for this scope, or a "clone-and-parameterise" design.
2. **Where does Zambia knowledge live?** You said this is feasible for Zambian projects only. Estate specifics such as `ZamCloud/pipeline-templates`, ZamPay and NIR probably don't belong in a general DGF plugin, so consider a separate pack or plugin. It would also need ledgers that cite estate repositories, not DGF ones.
3. **Which base tag is authoritative?** The pinned tags disagree across repos (`alpha.3` and `alpha.4`). The scaffold has to ask, or read a single source of truth.
4. **How much does it generate?** Solution plus a minimal workspace is clearly in scope. The domain is not: no `ZIGS_*` content, no per-app modules.

Two things I haven't verified: how the engine maps `WorkspaceName` to `ApplicationId` (it is inside the NuGet packages), and ZILAS's unresolved `BASE:` references.

## How the research is used

- **The shape, not the content.** The research gives the solution's shape: host, database, Docker, workspaces. It gives the
  options that differ: instances, and how the base is supplied. And it gives the defects never to repeat: literal secrets,
  environment URLs in base settings, forked bases, one appsettings file copied per instance, stray `BASE:` references. The
  content is DGF-generic (the user, 2026-09-29): no ZamPay, NIR, ZamConnect, ZRA, `ZamCloud/pipeline-templates`, `ZIGS_*` or
  Zambian roles.
- **Open question 1** → ADR 0026 and ADR 0027 (Tasks 1–2).
- **Open question 2** → no estate knowledge ships. A Zambian application gets the Zambian base simply by pointing the survey's
  base source at the ZamOffice `webasm` (D6).
- **Open question 3** → the base is never pinned by the plugin; the survey asks for it.
- **Open question 4** → the refined request settles it: the solution, the database and the workspace artefacts the request
  describes are all generated.
- **The unverified `WorkspaceName` → `ApplicationId` mapping** → answered by DGF's database readme: `WorkspaceProvider.InitAsync`
  looks the workspace up by `LoweredApplicationName`, and `Current` throws when no row matches. Task 4 records it from the code.

## User decisions (2026-09-29)

| Question | Answer |
|---|---|
| Planning mode | Full |
| Branch base | Stacked on `feature/dgf-specific-skills` |
| What the command does | Creates an app from scratch in an empty folder: API(s), Docker, database, workspaces, documentation, authentication, and the workspace artefacts the request describes (the refined request) |
| The database | "when scaffold is executed in an epty folder then it must generate everything, including database SSDT SQL" |
| Where estate conventions live | DGF-generic only |
| ~~Front door, hands off to the pipeline~~ | Withdrawn by the refined request: the scaffold generates everything itself |

## DGF facts this plan stands on (read 2026-09-29, DGF `1d5999186`)

Tasks 4–5 record each one, stamped and ledgered, before any template uses it. None is written into a shipped file as a DGF path
(ADR 0012).

| Fact | Source |
|---|---|
| **No bootstrap template or generator exists in DGF** | ADR 0004 and ADR 0023 searches, repeated 2026-09-29; `spec-schema-examples/` holds only `.gitkeep` |
| **The minimum of a new app workspace.** `dgf` is the reference layout. It needs `FM/_COMPONENTS/sitemap.json` with a landing route that is not `"/"`, listed first; `_application.sitemap`, which the base does not supply; `FM/_COMPONENTS/Page/SiteMap/`; and a `_PROFILE/<name>/<roleGroup>/_tree.xml` for each `router` component | `src/samples/workspaces/readme.md` |
| **The shell hard-codes `/login`,** and reads its page's `authenticationMethods`. `dgf` satisfies this with a local `SiteMap/loginPage`; its one `BASE:` route, `/user-profile`, is optional | `routes.guard.ts:53`, `auth.guard.ts:29`, `profile-menu.component.ts:132-140`, `AuthenticationExtensions.cs:122` (`LoginPath="/login"`) |
| **`Members` is the profile group every role falls back to,** anonymous users included | `TreeManager` |
| **The base workspace.** `BaseWorkspaceName` is a compile-time constant, `webasm`, and each consumer ships its own `webasm` | `src/samples/workspaces/readme.md` |
| **The application row.** The API does not start without an `aspnet_Applications` row for the workspace: `WorkspaceProvider` finds it by `LoweredApplicationName`. DGF's own seed inserts it under `IF NOT EXISTS` and leaves `SignType` and `IntranetSignType` to their defaults | `src/samples/Database/readme.md`; `ContinuousDeployment/1.PostDeployment.Workspaces.sql` |
| **The framework database.** It is an SDK-style `Microsoft.Build.Sql/2.2.0` baseline of 145 derived objects, with `TreatTSqlWarningsAsErrors=true` and idempotent `ContinuousDeployment/*.sql` scripts. No baseline script seeds `AspNetRoles`: the built-in roles are seeded in code by `ApplicationDbContextSeed` | `DGF.Database.sqlproj`; `Scripts/Script.PostDeployment.sql` |
| **The framework partitions its own rows by `ApplicationId`**, the current workspace's id | `AuditTrailHandler.cs:102`, `InstanceHandler.cs:271`, the identity migration |
| **Authentication.** Cookie authentication is always on. DGPass OIDC is added when `Authentication:<DgPassOptions.AuthenticationScheme>` exists, Azure AD OIDC when `Authentication:<AzureAdOptions.AuthenticationScheme>` exists | `DGF.Authentication/AuthenticationExtensions.cs:114, :169-175, :238-241` |
| **No back-office concept in DGF.** A front-office and a back-office tier are one host deployed twice, with different settings | grep of `src` for `BackOffice`: no match |
| **The host.** The sample API host is a thin `net10.0` project whose `Program.cs` calls `builder.BuildEServicesApi(…)` from `DGF.API` | `src/samples/BFF.API/` |
| **Several instances over one workspace.** The same directory is mounted under each `WorkspaceName`, with a per-instance `_application-<n>.sitemap` bind-mounted over `_application.sitemap` | `src/samples/DGF.Compose/docker-compose.zma.yml` |
| **The local stack** holds traefik, SQL Server, a `db-init` that publishes the database, Seq, Redis, and stubs for Pay, RA, Sign and Notify. DGF's own API and UI images are built from source, and no consumer image tag is pinned | `src/samples/DGF.Compose/readme.md`, `docker-compose*.yml` |
| **No DGF code turns a `settings.xml` into a `CREATE TABLE`** | grep of `src/Core`, `src/PlatformServices`, `src/DGE.Office` |
| **The SQL type follows a field's `dbtype`, not its `type`.** Across 86 exact-case pairs of `settings.xml` and table script, 1,626 fields match a column: `String` → `VARCHAR(size)` 461 times and `NVARCHAR` 77 times; `DateTime` → `DATETIME`; `Guid` → `UNIQUEIDENTIFIER`; `Int16` → `SMALLINT`; `Int32` → `INT`; `Boolean` → `BIT`. A decimal's precision and scale are never in the settings file (the columns hold `DECIMAL (18, 2)`); 13 columns are computed | the pairs in `src/samples/workspaces/{webasm,dgf}` and `src/samples/Database/dbo/Tables` |
| **What this plugin's validators do with a new workspace.** Every `sitemap.json` warns `NO_SCHEMA`, so its routes are never checked (`json_resolve.py:279-281`). `_application.sitemap`, `_tree.xml` and the profile node files are never collected, and naming one explicitly exits `3` (`cli.py:44-72`). A `BASE:` reference with no base in the root is an ERROR. `validate_process.py --all` with no process exits `3`. The vendored `settings.xsd` lacks `PrimaryKey` and `Checkboxlist` (`XSD_LAGS_RUNTIME`). Without `webasm` the inventory warns `BASE_WORKSPACE_ABSENT` | a run over copies of `dgf` with and without `webasm`, 2026-09-30 |

## Decisions

- **D1 — Two ADRs, each superseding one in full, section numbers kept** (`docs/adr/README.md` §"Supersession is always full").
  - **ADR 0026 supersedes ADR 0004.**
    - §1 (brownfield is the default path) is restated: every change after the first is brownfield.
    - §2 is reversed: no bootstrap template exists, so `/dgf-scaffold` generates a new application itself, DGF-generic, from
      shipped templates, and only into an empty folder.
    - §3 (the unit of work is the workspaces root) is restated, with one addition: the scaffold's unit is the empty folder it
      fills.
  - **ADR 0027 supersedes ADR 0023.** Its §1–§6 and §8 are restated, with 0023's two errata folded in, and §7 becomes the
    scaffold's design (D2–D11).
    - §1 gains one rule: in an empty folder there is no root and no plan, so the scaffold writes without either.
    - §2's partition gains a row: every file of a new application, until `/dgf` sets its root up, is the scaffold's.
  - **ADR 0010 and ADR 0017 stand.** `/dgf-plan` and `/dgf-implement` still never plan or write C# or SQL. The scaffold's
    generator is a separate, template-only writer, and it writes only into an empty folder.
  - **This reading of ADR 0010 is flagged.** It treats ADR 0010 as the scope of `/dgf-plan` and `/dgf-implement`. If its
    closing sentence ("That work belongs to a general coding flow outside this plugin") is read as plugin-wide, Task 2 must
    supersede it too. ADR 0027 §7 states the reading so that a reviewer can reject it.
- **D2 — Greenfield only.** `design.py --empty-only` refuses a folder holding anything but `.git/` and `docs/application.json`
  (`SCAFFOLD_DIR_NOT_EMPTY`). Adding to an existing application is the pipeline's job. So the skill:
  - never reads or writes `.dgf-factory/`;
  - runs no override check;
  - reads no patches.
- **D3 — One design file, and it is the generator's only input.**
  - **The file.** `docs/application.json` (`design_format: 1`) holds the whole application. It is written by the model, from
    the request and the survey.
  - **What it holds:**
    - the application's name;
    - `dgf_version` (the `DGF.API` package version to target);
    - `instances[]` and `instance_model`;
    - `apis[]`, each with its `deployments[]`, where a deployment is one API process for one instance, with its authentication;
    - `auth` providers;
    - `roles[]`;
    - `base` (`source`: a local path to a `webasm`, DGF's or an estate's such as ZamOffice's; `supply`: `copy` or `mount`);
    - `modules[]` (D7);
    - `data_model` (D8);
    - `sources`: for every value, whether it came from `prompt`, `asked` or `default`.
  - **What it never holds:** an instance's `ApplicationId`. `generate.py` derives it as a `uuid5` of the application and
    instance names, so a re-generation from the same design reproduces it.
  - **It stays in `docs/`** as the record of what was generated. The generator run from it into a new empty folder reproduces
    the application.
- **D4 — Two scripts decide everything a script can; the model only designs and asks.**
  - **Both are slice-local** (`skills/dgf-scaffold/scripts/`), since no other skill uses them.
  - **They load `scripts/lib/report.py` and `scripts/lib/knowledge.py` by path**, as `doctor.py` does
    (`importlib.util.spec_from_file_location`). Those two modules and `gate_result.py` are the only lib modules with no relative
    import. `cli.py` and `workspace.py` cannot be loaded this way, so each script:
    - has its own argument parser, whose `error()` exits `3`, as `doctor.py`'s does;
    - has its own exact-case helper over `os.scandir`.
  - **Their codes are registered in `report.CODES`**, the single source of severity.
  - **`design.py --folder <dir> [--empty-only]`.** `--empty-only` answers only whether the folder is empty. Without it, the
    script reads the design and checks:
    - the folder is empty;
    - every name against its rule;
    - every cross-reference;
    - the data model (D8);
    - every value against the knowledge tables.

    It prints one `SCAFFOLD_ASK` per open value, with its rule and its candidates, and one `DEFAULT: <key> = <value>` line per
    defaulted value. It exits `0` complete, `1` conflict, `2` questions remain, `3` unreadable.
  - **`generate.py --folder <dir> [--dry-run | --check]`.**
    - It refuses unless `design.py` exits `0`.
    - `--dry-run` prints every target, and writes nothing.
    - Without a flag, it renders into a staging directory inside the folder, and moves the result into place only when
      everything has rendered.
    - `--check` runs the post-generation check (D12).
  - **The template manifest is `skills/dgf-scaffold/templates/manifest.json`**, read by `generate.py` itself. It is not a
    machine-read markdown table: every `knowledge.TABLES` entry is loaded from `knowledge/` by `load_all()` and by the doctor,
    so a slice-local table would be a blocking `KNOWLEDGE_TABLE`.
- **D5 — The solution layout** is the plugin's own, with neutral names. It mirrors the research's common shape, with DGF's
  samples as the evidence:
  ```
  <dir>/
  ├── <App>.slnx                     the API hosts and the database project
  ├── src/<Api>/                     one per API: a thin host on the DGF.API package calling BuildEServicesApi;
  │   ├── appsettings.json           shared settings, the chosen auth sections (D9), every secret a ${VAR}
  │   ├── appsettings.<Deployment>.json   only what differs: WorkspaceName, the auth sections, the ports
  │   └── Dockerfile
  ├── database/<App>.Database/       SDK-style Microsoft.Build.Sql: the app's tables (D8), an aspnet_Applications row per
  │                                  instance and the app's AspNetRoles rows, all idempotent post-deployment scripts
  ├── workspaces/                    the workspaces root: the app workspace(s) (D6, D7); webasm when supply = copy
  ├── docker/                        docker-compose.yml (one API + UI pair per deployment, the stack of DGF's local
  │                                  compose), ui/<Deployment>.json (each UI's settings), .env.example
  └── docs/                          README.md (how to run), architecture.md, data-model.md, configuration.md (every
                                     ${VAR}: where it is used and what it is), application.json
  ```
  - **No Helm and no pipeline.** The request names Docker, and DGF ships no consumer pipeline. Both are follow-ups in
    `docs/README.md`.
  - **What is never literal:** a secret, a host, a feed, a registry or an image tag. Each is a `${VAR}` (`.ai-factory/rules/base.md:163-164`).
  - **`.gitignore`** covers `docker/.env`, `bin/`, `obj/`, `_STORAGE/` and `Temp/`. DGF gitignores the last two.
  - **Rules that hold for shipped templates:**
    - no target at `src/Directory.Build.props` or `src/global.json` (both match doctor's `DGF_PATH`);
    - no `/home/` or `~/` (both `ABSOLUTE_PATH` warnings, which fail `test_doctor`);
    - LF line endings only;
    - in template markdown a variable is written `${NAME}`, never a bare backticked `NAME`: `test_skill_contracts.py`'s code
      token rule scans every `.md` under `skills/`.
- **D6 — The workspaces and multi-tenancy.**
  - **What an instance is.** An instance is a `WorkspaceName` with its own `aspnet_Applications` row. The framework partitions
    its rows by that row's id.
  - **`instance_model`:**
    - `shared-workspace`: one app workspace, mounted under each instance's name, with its `_application-<instance>.sitemap`
      bind-mounted over `_application.sitemap`, as DGF's zma compose sample does;
    - `own-workspace`: one workspace per instance.
  - **What each workspace gets:**
    - `sitemap.json` with the landing route first (never `"/"`) and `/login` with a local login page;
    - `_application.sitemap`;
    - the `Page/SiteMap/` pages;
    - a `_PROFILE` tree per router, in the `Members` group unless a role narrows it.

    It gets no `/user-profile`: that is `dgf`'s one `BASE:` route.
  - **The base.**
    - `supply: copy` copies `base.source` into `workspaces/webasm`, as "each consumer ships its own webasm" says.
    - `supply: mount` mounts it in compose, and the path is a `${VAR}`.

    The folder is always named `webasm` (the constant).
  - **No generated file uses a `BASE:` reference.** Without a base in the root such a reference is an ERROR, and a copied base
    brings its own errors: `webasm` alone holds 36 `SCHEMA_INVALID` and 13 `MODEL_CELL_UNBOUND`. The generated application is
    self-contained, whatever base is supplied.
  - **With more than one instance,** every generated app table gets the `ApplicationId` column exactly as DGF's baseline
    declares it on its own tables. The docs state that isolation is by that column alone.
- **D7 — Workspace artefacts are patterns, rendered from the design.** v1 has three module patterns:

  | Pattern | Files |
  |---|---|
  | `register` | the entity's `settings.xml`; its default form and lookup view; a `DataSource`; a `DataTable`; a list `Page`; its route in `sitemap.json`; a `_PROFILE` node for its roles |
  | `service` | a `register` plus a case process: `process.xml` with draft → submitted → in review → approved or rejected, a `_workflow.xml` per transition, and a task per reviewing role |
  | `page` | a content `Page` and its route |

  - **Every entity gets its own default form and lookup view**, so the runtime never falls back to generating one. Its
    generators throw on a field with no `uimask`, or a table with no non-key `Text` field (`knowledge/data-model.md`).
  - **Every legacy artifact is XML** (`knowledge/composition-specs.md` §4).
  - **What falls outside the patterns** — custom behaviour, integrations, documents — is written into `docs/README.md` as
    work for `/dgf-plan` after `/dgf`, never improvised.
- **D8 — The data model and the SQL.**
  - **What the entities hold.** `data_model.entities[]`: `name`, `key`, and `fields[]`. Each field has `name`, `type` (a
    runtime `FieldTypeEnum` member), `dbtype`, `size`, `required`, `unicode` (strings), `precision` and `scale` (decimals), and
    optionally `extract {entity, view}`.
  - **What `design.py` refuses** (`SCAFFOLD_MODEL_INVALID`):
    - exactly what `knowledge/data-model.md` §2 says makes a table's load throw;
    - a `type` or `dbtype` that is no row of its table;
    - `PrimaryKey` and `Checkboxlist` in v1. The vendored `settings.xsd` lacks both, so every file would warn
      `XSD_LAGS_RUNTIME` (ADR 0016). DGF's samples type a key as `Text`/`Guid` or `Integer`/`Int32`.
  - **Where the column types come from.** Each column's SQL type comes from the `field-sql-types` table, keyed on `dbtype`
    and derived from DGF's 86 pairs (Task 5).
    - A string is `VARCHAR(size)`, or `NVARCHAR(size)` when `unicode` is true. `VARCHAR` is the majority and the default, and
      it is shown at the confirm step.
    - A decimal is `DECIMAL(precision, scale)`, defaulting to the observed `(18, 2)`.
    - A `dbtype` with no evidence is `SCAFFOLD_SQL_TYPE_UNKNOWN`. A column type is never guessed.
  - **One model, two outputs.** The same model renders the entity's `settings.xml` and its table script, so the two agree by
    construction.
- **D9 — Authentication is DGF's own.**
  - **Cookie authentication** is always on.
  - **The survey offers** `dgpass` and `azuread` per deployment. Each chosen provider emits its `Authentication:<scheme>`
    section with the keys DGF's options class reads (Task 4), every value a `${VAR}`. The login page's `authenticationMethods`
    lists the same providers.
  - **`roles[]`** become `AspNetRoles` seed rows per instance, with the columns and `NormalizedName` rule Task 4 records;
    sitemap `roles`; and `_PROFILE` role groups. Names are written exactly: the runtime splits on `,` without trimming
    (`knowledge/permissions.md`).
- **D10 — The survey.**
  - **Before `design.py` runs.** If the request reads as two different applications, the skill asks which one. If
    `docs/application.json` already exists, the skill resumes it rather than starting again.
  - **After it runs.** Every `SCAFFOLD_ASK` becomes an `AskUserQuestion`, at most four per call. The skill loops back to
    `design.py`, for at most five rounds. It then STOPs, keeping the design, and a re-run in the same folder resumes it.
  - **A default is never silent.** The confirm step relays every `DEFAULT:` line and `generate.py --dry-run`'s tree before
    anything is generated. The model computes neither.
- **D11 — Report codes.**

  | Script | Exit | Codes |
  |---|---|---|
  | `design.py` | `1` | `SCAFFOLD_DIR_NOT_EMPTY`, `SCAFFOLD_NAME_INVALID`, `SCAFFOLD_OPTION_INVALID`, `SCAFFOLD_REFERENCE_INVALID`, `SCAFFOLD_MODEL_INVALID`, `SCAFFOLD_SQL_TYPE_UNKNOWN` |
  | `design.py` | `2` | `SCAFFOLD_ASK` |
  | `design.py` | `3` | `SCAFFOLD_DESIGN_UNREADABLE` |
  | `generate.py` | `1` | `SCAFFOLD_TARGET_EXISTS`, `SCAFFOLD_LITERAL_SECRET`, `SCAFFOLD_VAR_UNDECLARED`, `SCAFFOLD_STRUCTURE_INVALID`, `SCAFFOLD_ROUTE_UNRESOLVED`, `SCAFFOLD_VALIDATION_FAILED` |
  | `generate.py` | `3` | `SCAFFOLD_DESIGN_INCOMPLETE`, `SCAFFOLD_TEMPLATE_MISSING`, `SCAFFOLD_WRITE_FAILED`; and the validators' own `DEPENDENCY_MISSING`, relayed |
- **D12 — The post-generation check decides whether the generated application is sound; the skill only relays it.**
  `generate.py --check` runs these checks in order, and any failure exits `1`:
  1. **Secrets.** Every value of a key matching `password|secret|key|token|connectionstring` is `${…}`
     (`SCAFFOLD_LITERAL_SECRET`), and every `${VAR}` used is declared in `docker/.env.example` and `docs/configuration.md`
     (`SCAFFOLD_VAR_UNDECLARED`).
  2. **Structure.** It checks the files no validator reads: `_application.sitemap`, each `_application-<instance>.sitemap`,
     each `_tree.xml` and each profile node file. Each must be well-formed, with the root element and required attributes the
     `workspace-minimum` table records (`SCAFFOLD_STRUCTURE_INVALID`).
  3. **Routes.** Every `sitemap.json` route names a generated page, by exact case. `/login` exists with a login page, and the
     landing route is not `"/"` (`SCAFFOLD_ROUTE_UNRESOLVED`).
  4. **Validators, generated files only.** It runs `validate_config.py`, `resolve_components.py` and `validate_model.py` over
     the generated files, and `validate_process.py` over them only when the design has a process. It never runs `--all` over
     the root: a copied base's own findings are not the generator's.
     - **Allowed:** INFO, and `WARN NO_SCHEMA` on `sitemap.json`, which every site map gets. Also `BASE_WORKSPACE_ABSENT`
       from `inventory_root.py` when `supply: mount`.
     - **Everything else a generated file causes** is `SCAFFOLD_VALIDATION_FAILED`, the validator's own line quoted: any
       ERROR; any other WARN; a validator's exit `3` naming a generated file (`FAMILY_UNRESOLVED`, `SCHEMA_UNSELECTABLE`).
     - **A validator that cannot run** (`DEPENDENCY_MISSING`) exits `3` with that code.

## Commit Plan
- **Commit 1** (after tasks 1–3): `docs(adr): record ADR 0026 and ADR 0027 — the scaffold creates an application from an empty folder`
- **Commit 2** (after tasks 4–5): `docs(knowledge): record the application layout, the field types and their SQL types`
- **Commit 3** (after tasks 6–9): `feat(skills): design check, generator and post-generation check for a new DGF application`
- **Commit 4** (after tasks 10–11): `feat(skills): add /dgf-scaffold`
- **Commit 5** (after tasks 12–13): `docs: document /dgf-scaffold`

## Tasks

### Phase 1: Decisions

- [x] **Task 1: Write ADR 0026, superseding ADR 0004 in full.**
  - Files:
    - `docs/adr/0026-authoring-entry-point-revised.md` (new);
    - `docs/adr/0004-authoring-entry-point.md` (frontmatter `status: superseded-by-0026` only);
    - `docs/adr/README.md` (the index row);
    - `docs/blueprint.md`. Line 384 is an `ANSWERED` line linking `adr/0004-authoring-entry-point.md`, which
      `check-dual-schema-docs.sh` §5b errors on once 0004 is superseded. Its ANSWERED block gains `Revised (2026-09-29)` and
      links 0026; the question text is never edited.
  - Frontmatter as ADR 0025's: `supersedes: [0004]` (inline form), `status: accepted`, `date: 2026-09-29`.
  - The status line records the decider's choices of 2026-09-29, from the table above.
  - Context: the 2026-09-21 interview; the three template searches; the five-application survey; the DGF facts above.
  - Decision: D1's ADR 0026 bullet. Its `## Decision` section must be at least 200 characters.
  - Alternatives: drive a template (none exists); clone an existing app (it copies secrets and forks, per the research's
    "never copy" list); an estate profile (declined); a scaffold that also adds to existing apps (the pipeline's job).
  - Negative consequences:
    - the templates can drift from DGF's samples until the next `tools/check_drift.py` run;
    - the solution files pass no validator, only the post-generation check;
    - the application does not run until its `${VAR}`s are filled.
  - Logging: n/a.
  - Tests: `tools/check-dual-schema-docs.sh` sections 5 and 5b are CLEAN.

- [x] **Task 2: Write ADR 0027, superseding ADR 0023 in full, with its section numbers.** (depends on 1)
  - Files:
    - `docs/adr/0027-dgf-specific-skills-revised.md` (new);
    - `docs/adr/0023-dgf-specific-skills.md` (frontmatter `status: superseded-by-0027` only);
    - `docs/adr/README.md`.
  - §1–§6 and §8 are 0023's text. Both 2026-09-27 errata are folded into the text they correct and listed under Context.
  - §1 and §2 gain D1's two rules.
  - §7 "`/dgf-scaffold`" holds D2–D12, and states D1's reading of ADR 0010.
  - Logging: n/a.
  - Tests: `tools/check-dual-schema-docs.sh` is CLEAN.

- [x] **Task 3: Re-point every live citation of ADR 0004 and ADR 0023.** (depends on 1, 2)
  - Files: every file under `skills/`, `scripts/`, `knowledge/`, `tests/`, `tools/`, `docs/` (not `docs/adr/`), `AGENTS.md`,
    `README.md` and `.ai-factory/DESCRIPTION.md` that cites them — about 60 files and 150 citations.
  - Replace `ADR 0004 §N` with `ADR 0026 §N` and `ADR 0023 §N` with `ADR 0027 §N`, links included.
  - **This changes output that tests assert.**
    - Two messages users see change: `check_change.py:425` and `audit_root.py:97` print "ADR 0004 §3".
    - Nine test files cite one of the two ADRs: `test_verify_gate.py`, `test_skill_contracts.py`, `test_audit_root.py`,
      `test_report.py`, `test_validate_model.py`, `test_runner.py`, `test_workspace.py`, `test_roles.py`, `test_graph.py`.

    Update each assertion in this task, and the comment at `tools/known-good-exceptions.txt:93`.
  - Leave alone:
    - other ADRs' bodies (ADRs are immutable);
    - `.ai-factory/` history;
    - `.ai-factory/ARCHITECTURE.md`, which is `/aif-architecture`'s — Task 13 hands it over.
  - `AGENTS.md` Agent Rules names ADR 0026 and ADR 0027, and lists 0004 and 0023 as superseded history.
  - Logging: n/a.
  - Tests:
    - the grep finds no live citation;
    - the suite and `tools/check-dual-schema-docs.sh` pass;
    - `tools/run_known_good.py`'s output differs from before only in lines whose one change is the ADR number.

### Phase 2: DGF facts

- [x] **Task 4: Record the application layout — `knowledge/application-layout.md`.**
  - Files:
    - `knowledge/application-layout.md` (new);
    - `provenance/knowledge/application-layout.md` (new ledger: `sources:` of DGF-relative `path` + `sha256`, never empty);
    - `knowledge/README.md` (a §7 registry row per table);
    - `scripts/lib/knowledge.py` (a `TABLES` entry per table: its filename, exact headers and allowed values);
    - `tests/test_knowledge.py` (an `EXPECTED_ROWS` entry per table, or `load_all()` raises a KeyError).
  - **The stamp is per file:** frontmatter `dgf_version` (quoted semver) and `read_date`. Read the version from
    `src/Directory.Build.props` at `1d5999186`. If it is not `"1.1.11"`, `check_knowledge_stamps.py` warns of divergence;
    record that in the file.
  - Read at DGF `1d5999186` — the code path, not only a readme (RULES.md rule 1). Record:
    - **the workspace minimum**, from `src/samples/workspaces/dgf/`:
      - `sitemap.json`'s keys and route shape;
      - the local `loginPage` and its `authenticationMethods`;
      - the shell's `/login` requirement (the four code paths above);
      - `_application.sitemap`'s root `map` element, its attributes, and its children (`basedOn`, `dbprefix`, `title`,
        `tabs/mapNode`);
      - `_tree.xml`'s `Tree`/`Folders`/`Folder` shape and the node files' `mapNode`/`set` shape;
      - the `Members` fallback in `TreeManager`;
    - `WorkspaceSettings` (the `webasm` constant, the root and name settings), and `WorkspaceProvider.InitAsync` and `Current`;
    - **the database:**
      - the columns of `aspnet_Applications` and `AspNetRoles`, and which have defaults;
      - how `NormalizedName` is formed, from `ApplicationDbContextSeed` or the Identity code it calls;
      - the baseline's post-deployment idioms (`IF NOT EXISTS`, `MERGE`) and its sqlproj properties;
      - how the local stack publishes the baseline, and what a consumer database project must reference to build against it;
    - **authentication:**
      - the `DgPassOptions` and `AzureAdOptions` scheme names and every property they bind;
      - whether any other scheme is configured from settings;
      - every other `Authentication:*` key the extensions read;
    - **the host:** `BFF.API`'s `Program.cs` and csproj, and the `DGF.API` package's name and the settings it needs;
    - **the local stack:**
      - each service, with its image or build, its environment variables and its mounts;
      - the UI container's settings file and keys;
      - the three custom UI files (`knowledge/composition-specs.md` §5);
      - the zma sample's instance mounts.
  - Machine-read tables:
    - `workspace-minimum` (`File | Root | Required | Rule | Fact`);
    - `auth-schemes` (`Provider | Section | Keys | Fact`);
    - `instance-models` (`Model | Mounts | Sitemap | Applications row | Fact`);
    - `solution-parts` (`Part | Verified values | Placeholders | Fact`). `Verified values` holds only what DGF pins; every
      other value a part needs is a placeholder.
  - The file names no DGF repository path (doctor's `DGF_PATH`). Paths go in the ledger.
  - Logging: n/a.
  - Tests:
    - `tools/check_knowledge_stamps.py` is CLEAN;
    - `tools/check_drift.py <dgf-root>` is CLEAN;
    - `tests/test_knowledge.py` loads the four tables with their expected row counts;
    - `doctor.py` is CLEAN.

- [x] **Task 5: Record the field types and derive their SQL types from DGF's own evidence.**
  - Files:
    - `tools/derive_sql_types.py` (new, maintainer-only);
    - `knowledge/data-model.md` (a new §6 holding three tables);
    - `provenance/knowledge/data-model.md`;
    - `scripts/lib/knowledge.py` (three `TABLES` entries);
    - `knowledge/README.md` §7;
    - `tests/test_knowledge.py` (`EXPECTED_ROWS`);
    - `tests/test_derive_sql_types.py`;
    - `tests/fixtures/unit/sql-types/`.
  - Tables:
    - `field-types` (`Type | In settings.xsd | Fact`) — the 13 runtime `FieldTypeEnum` members, prose only in §2 today
      (`PrimaryKey, Lookup, Picklist, Checkboxlist, Text, Html, Integer, Float, Money, Boolean, DateTime, EditableGrid,
      Image`), each marked by whether the vendored XSD declares it;
    - `db-types` (`Dbtype | Fact`) — the `dbtype` values the samples use;
    - `field-sql-types` (`Dbtype | Size rule | SQL type | Evidence`).
  - The tool:
    - pairs every `FM/_DATA/<T>/settings.xml` in DGF's `webasm` and `dgf` samples with `dbo/Tables/<T>.sql` in the baseline,
      by exact case (86 pairs on 2026-09-30);
    - reads each field's `dbtype`, `size` and `accuracy`, and the column's declared type, with `xml.etree`, so it needs no lxml;
    - skips computed (`AS`) columns;
    - prints, per (`dbtype`, size rule), the majority SQL type, `n/N`, and every alternative.

    Copy its output into the table. `String` keeps `NVARCHAR` as its recorded alternative. A `dbtype` with no pair has no row.
  - Logging: `report.debug("derive_sql_types.pair", "matched", table=…, fields=…, columns=…)`, and each unmatched field or
    computed column at DEBUG.
  - Tests:
    - a fixture tally;
    - a counted alternative;
    - a computed column skipped;
    - a field with no column skipped.

### Phase 3: The design check, the generator and its check

- [x] **Task 6: The design format and `design.py`.** (depends on 4, 5)
  - Files:
    - `skills/dgf-scaffold/references/DESIGN-FORMAT.md` (new): every key, its rule, its default, and one complete example —
      two instances, `shared-workspace`, two APIs, DGPass and Azure AD, a register and a service;
    - `skills/dgf-scaffold/scripts/design.py` (new);
    - `scripts/lib/report.py` (D11's codes);
    - `tests/test_report.py` (a `ScaffoldCodes` class asserting each code's exit);
    - `tests/test_scaffold_design.py`;
    - `tests/fixtures/unit/scaffold/`.
  - **Loading:** `report.py` and `knowledge.py` by path (D4). It has its own argument parser, whose `error()` exits `3`, and
    its own exact-case helper over `os.scandir`.
  - **Reading** (patch 2026-09-26-21.53): the design must be a regular file, bounded in size before it is read. A parse error,
    a `RecursionError` or a non-UTF-8 byte is `SCAFFOLD_DESIGN_UNREADABLE`, never a traceback. Every value's JSON type is
    checked before the value is used as a key or looked up (patch 2026-09-29-10.02).
  - Checks, in order:
    1. the folder is empty (D2). `--empty-only` stops here;
    2. the design parses: `design_format: 1`, no unknown key at any level;
    3. every required value is present, else `SCAFFOLD_ASK`;
    4. names:
       - entity, field, API and deployment names are identifiers (`[A-Za-z][A-Za-z0-9_]*`) and unique ignoring case, since
         APFS and NTFS would collide their files;
       - workspace and instance names are lower-case identifiers, unique;
       - roles contain no `,` and no leading or trailing space;
       - route paths are not `"/"` and are unique;
       - titles are free text;
    5. references: each deployment names an instance and an API; each module names entities and roles that exist; each
       `extract` names an entity;
    6. the data model, `type` against `field-types`, `dbtype` against `db-types`, and each column's SQL type (D8);
    7. options against `auth-schemes`, `instance-models` and D7's pattern list;
    8. `base.source` exists, by exact case, and is a directory named `webasm` with an exact-case `FM/`.
  - Output: a header, then the `SCAFFOLD_ASK` findings and the `DEFAULT:` lines, then the verdict, `route_means.py`-style.
    Every line goes through `report.one_line`.
  - Logging:
    - `report.debug("design.read", "read", path=…, bytes=…, format=…)`;
    - `("design.check", "value", key=…, state=…)`;
    - `("design.check", "done", asks=…, defaults=…, conflicts=…)`.
  - Tests:
    - the example design gives exit 0 and its `DEFAULT:` lines;
    - each open value gives exit 2 with its ask;
    - each exit-1 code is hit once;
    - each exit-3 cause is hit once;
    - every field is offered every JSON type (null, boolean, number, string, list, object) in a refusal test;
    - two names that differ only in case are refused;
    - it runs without lxml and jsonschema (RULES.md rule 5).

- [x] **Task 7: `generate.py` and the solution templates.** (depends on 5, 6)
  - Files:
    - `skills/dgf-scaffold/scripts/generate.py` (new);
    - `skills/dgf-scaffold/templates/manifest.json` (new: `template`, `target`, `repeat`, `when`, `format` per entry);
    - `skills/dgf-scaffold/templates/solution/`:
      - `App.slnx`;
      - `src/Api/{Api.csproj, Program.cs, appsettings.json, appsettings.Deployment.json, Dockerfile}`;
      - `database/{App.Database.sqlproj, dbo/Tables/Entity.sql, Scripts/Script.PostDeployment.sql,
        ContinuousDeployment/1.PostDeployment.Applications.sql, ContinuousDeployment/2.PostDeployment.Roles.sql}`;
      - `docker/{docker-compose.yml, .env.example, ui/Deployment.json}`;
      - `docs/{README.md, architecture.md, data-model.md, configuration.md}`;
      - `.gitignore`, `.gitattributes`;
    - `tests/test_scaffold_generate.py`;
    - `tests/fixtures/golden/scaffold/`.
  - **Before anything is written:**
    - `generate.py` runs `design.py`; anything but exit 0 is `SCAFFOLD_DESIGN_INCOMPLETE`;
    - every target is checked by exact case, and any that exists is `SCAFFOLD_TARGET_EXISTS`, with nothing written;
    - `--dry-run` prints the targets and stops.
  - **Rendering:**
    - placeholders are `{{Name}}`, so `${VAR}` survives;
    - `repeat` covers `api`, `deployment`, `instance`, `entity` and `module`;
    - `when` is a design condition;
    - output is UTF-8 with no BOM and LF line endings;
    - **every pasted value is escaped for its target's `format`** (patch 2026-09-27-21.40): XML text and attribute, JSON
      string, SQL string literal (`'` → `''`) and bracketed identifier, YAML double-quoted, MSBuild XML.
  - **Writing:**
    - everything renders into a staging directory inside the folder;
    - only when the whole application has rendered is each top-level entry moved into place with `os.replace`;
    - any `OSError` is `SCAFFOLD_WRITE_FAILED` (exit 3), and the staging directory is removed, so the folder is left as it
      was;
    - it prints `WROTE: <path>` per file.
  - **Values:**
    - a template may hold only values `solution-parts` records as verified, and only `auth-schemes` keys;
    - `appsettings.<Deployment>.json` holds only what differs;
    - an instance's `ApplicationId` is `uuid5(NAMESPACE_URL, "dgf-scaffold:<app>/<instance>")`;
    - the sqlproj follows the baseline's `Sdk` and properties from Task 4;
    - the post-deployment scripts use `IF NOT EXISTS`: one `aspnet_Applications` row per instance, leaving `SignType` and
      `IntranetSignType` to their defaults, and `AspNetRoles` rows per instance with Task 4's `NormalizedName` rule.
  - D5's shipped-template rules hold.
  - Logging:
    - `report.debug("generate.plan", "file", template=…, target=…)`;
    - `("generate.render", "escaped", format=…, values=…)`;
    - `("generate.write", "moved", path=…)`;
    - `("generate.write", "failed", path=…, error=…)`.
  - Tests:
    - golden output for the example design, and for `own-workspace` with one API;
    - names and titles holding `&`, `<`, `"` and `'` render parseable in every format;
    - an existing target refuses with nothing written;
    - an incomplete design exits 3;
    - a write failure (a read-only staging directory) exits 3 and leaves the folder as it was;
    - two runs give the same `ApplicationId`s;
    - every manifest entry names a template that exists.

- [x] **Task 8: The workspace templates — the minimum and the three patterns.** (depends on 4, 7)
  - Files:
    - `skills/dgf-scaffold/templates/workspace/`: `sitemap.json`, `_application.sitemap`, `_application-instance.sitemap`,
      `Page/SiteMap/Landing.json`, `Page/SiteMap/Login.json`, `_PROFILE/_tree.xml`, `_PROFILE/node.xml`;
    - `skills/dgf-scaffold/templates/patterns/{register,service,page}/`: D7's files;
    - `skills/dgf-scaffold/templates/manifest.json`;
    - `tests/test_scaffold_generate.py`.

    Not `tests/test_skill_templates.py`: its contract (each template contains `"Example"` and validates as is) does not fit
    `{{Name}}` templates.
  - The minimum follows `workspace-minimum` and D6 exactly.
  - Patterns:
    - take every DGF fact from `knowledge/` (`json-reader.md`, `data-model.md`, `process-model.md`, `reference-graph.md`,
      `permissions.md`) or the DGF docs MCP (`get_component_doc`, `get_json_schema_details`), never from memory;
    - use XML for every legacy artifact;
    - use no `BASE:` reference;
    - give every entity its own default form and lookup view, and every field a `uimask`;
    - render the entity's `settings.xml` and its table from one `data_model` entry.
  - Logging: n/a (templates).
  - Tests (skipped without lxml and jsonschema, as the validator tests are):
    - each pattern, and the example design as a whole, generated into a scratch folder, give `generate.py --check` exit 0
      (Task 9);
    - the same with `supply: copy` over a copy of DGF's `webasm`, whose own findings do not count.

- [x] **Task 9: `generate.py --check` — the post-generation check.** (depends on 7, 8)
  - Files:
    - `skills/dgf-scaffold/scripts/generate.py`;
    - `scripts/lib/report.py` (the check's codes, if not already registered by Task 6);
    - `tests/test_scaffold_check.py`.
  - D12, in its order. It runs each validator as a subprocess with the plugin's own interpreter (`sys.executable`) and explicit
    file lists:
    - `validate_config.py <files>` and `resolve_components.py <files>`;
    - `validate_model.py <files> --workspaces-root <folder>/workspaces`;
    - `validate_process.py <files> --workspaces-root …` only when the design has a process.

    It parses their finding lines (`^(ERROR|WARN|INFO) ([A-Z_]+) `), applies the allow-list, and quotes each rejected line
    verbatim.
  - **The structure checks** read XML with `xml.etree` against `workspace-minimum`'s `Root` and `Required` columns. **The route
    check** walks `sitemap.json`'s `routes`, nested routers included.
  - **Exit 3 is mapped by code, not by number** (patch 2026-09-28-14.33):
    - a validator's `DEPENDENCY_MISSING` → exit 3 with that code;
    - `FAMILY_UNRESOLVED` or `SCHEMA_UNSELECTABLE` on a generated file → `SCAFFOLD_VALIDATION_FAILED`;
    - any other exit 3 → `SCAFFOLD_VALIDATION_FAILED` quoting it.
  - Logging:
    - `report.debug("check.secrets", "value", path=…, key=…)`;
    - `("check.structure", "file", path=…, root=…)`;
    - `("check.routes", "route", path=…, page=…)`;
    - `("check.validator", "ran", script=…, exit=…, rejected=…)`.
  - Tests, each fixture with a single deciding branch (patch 2026-09-28-12.39):
    - a planted literal secret;
    - an undeclared `${VAR}`;
    - a malformed `_tree.xml`;
    - a missing `/login`;
    - a route to a missing page;
    - a validator WARN outside the allow-list;
    - `NO_SCHEMA` on `sitemap.json` allowed;
    - `DEPENDENCY_MISSING` relayed as exit 3.

    Run each guard's mutant once to prove its test bites (patch 2026-09-28-08.51).

### Phase 4: The skill

- [x] **Task 10: `skills/dgf-scaffold/SKILL.md`.** (depends on 6–9)
  - Files: `skills/dgf-scaffold/SKILL.md`.
  - Frontmatter:
    - `name: dgf-scaffold`;
    - a `description` with trigger phrases: "new DGF application", "scaffold an app", "from scratch", "empty folder",
      "multi-tenant", "bootstrap";
    - `argument-hint: "<what the application is>"`;
    - `allowed-tools: Read Write Edit Glob Grep Bash(python3 "${CLAUDE_PLUGIN_ROOT}/skills/dgf-scaffold/scripts/*)
      AskUserQuestion mcp__plugin_dgf-factory_dgf-mcp__get_component_doc mcp__plugin_dgf-factory_dgf-mcp__get_json_schema_details`;
    - `disable-model-invocation: false`;
    - `version: 0.1.0`.
  - Steps, each with its exit table, routed by code (following `skills/dgf-process/SKILL.md`'s house pattern):
    - **0 Folder** — the argument's folder or the working directory. `design.py --folder <dir> --empty-only`: 0 → Step 1;
      1 `SCAFFOLD_DIR_NOT_EMPTY` → STOP, "this command only creates a new application; use `/dgf-plan` in an existing one";
      3 → STOP and relay.
    - **1 Design** — if `docs/application.json` exists, resume it. Otherwise write it from the request, each value only from
      the request (source `prompt`), leaving everything else out so `design.py` asks for it.
    - **2 Check** — `design.py`: 0 → Step 4; 1 → show each conflict, ask for a new value, re-run; 2 → Step 3; 3 → STOP.
    - **3 Survey** — D10.
    - **4 Confirm** — relay the `DEFAULT:` lines and `generate.py --dry-run`'s tree; one question: generate, change or cancel.
    - **5 Generate** — `generate.py`: 0 → Step 6; 1 `SCAFFOLD_TARGET_EXISTS` → STOP, "the folder changed since the check";
      3 → STOP and relay each code.
    - **6 Check** — `generate.py --check`: 0 → Step 7; 1 → STOP, "a generator defect", quoting its lines, never hand-patching
      the output; 3 `DEPENDENCY_MISSING` → the install command it prints, then re-run; any other 3 → STOP and relay.
    - **7 Report** — in English (no config exists yet):
      - what was generated;
      - how to run it (from `docs/README.md`);
      - every `${VAR}` to fill;
      - the follow-ups;
      - next: `/dgf <folder>/workspaces`.
  - Execution Rules and Artifact Ownership:
    - Writes: `docs/application.json`, and the application, through `generate.py` only.
    - Never writes: a plan, or anything in a non-empty folder.
  - Critical Rules: never overwrite; no value `design.py` has not accepted; no literal secret; no `BASE:` reference;
    `${CLAUDE_PLUGIN_ROOT}` always.
  - Wording the contract tests hold:
    - every backticked `UPPER_SNAKE` token is a registered code;
    - it never mentions the skill-context directory, which would make it an override reader;
    - no line starts with the word `git` followed by a space, and it quotes no git command, so `NO_GIT` holds.
  - Logging: the scripts' `--verbose`; the skill relays their lines verbatim.

- [x] **Task 11: The doctor, the contract tests and the known-bad corpus.** (depends on 9, 10)
  - Files:
    - `skills/dgf-doctor/scripts/doctor.py` (`EXPECTED_SLICES`);
    - `tests/test_doctor.py` (its own tuple, checked by regex, not by equality);
    - `tests/test_skill_contracts.py` (`NO_GIT` gains `dgf-scaffold`; a test that its body never names `.dgf-factory/` as a
      write target);
    - `tests/helpers.py` and `tests/test_known_bad.py`. `cli` resolves under `scripts/` only today (`test_known_bad.py:43`),
      so accept a plugin-relative path for a slice script;
    - `tests/fixtures/known-bad/scaffold-*/`: one case per exit-1 code and per exit-3 cause of D11, each `expected.json` with
      `cli`, `args`, `exit` and `codes`. A non-empty-folder case passes `--folder` a sub-folder, since the case directory holds
      `expected.json`.
  - Logging: n/a.
  - Tests:
    - the suite passes;
    - the known-bad class, which skips without lxml, passes with the venv;
    - `doctor.py` is CLEAN with `dgf-scaffold` counted.

### Phase 5: Proof and documentation

- [x] **Task 12: Walk the worked example and run every check; record the results.** (depends on 1–11)
  - In the scratchpad (RULES.md rule 4):
    - **The example.** An empty folder and DESIGN-FORMAT.md's example request, walked end to end:
      1. `--empty-only` exits 0;
      2. one survey round (`SCAFFOLD_ASK` for `dgf_version` and `base.source`), then exit 0 with its `DEFAULT:` lines;
      3. `--dry-run`;
      4. `generate.py`;
      5. `--check` exits 0.
    - **Once each with `supply: copy` and `supply: mount`**, over a copy of DGF's `webasm`.
    - **The hand-over.** `/dgf`'s Step 0–1 scripts on `<folder>/workspaces` exit as a first run: `locate_plan.py --root-only`
      exits 1 with `ROOT_NOT_SET_UP`; `inventory_root.py` exits 0, or 2 with `BASE_WORKSPACE_ABSENT` under `mount`.
    - **Refusals and failures:**
      - a non-empty folder is refused by both scripts;
      - a `dbtype` with no evidence gives `SCAFFOLD_SQL_TYPE_UNKNOWN`;
      - **a generation that goes wrong** (patch 2026-09-28-14.33): corrupt one template, generate, and walk Step 6's exit-1 row
        to its STOP.
    - **A real build, when `dotnet` is on `PATH`** (patch 2026-09-27-22.48): `dotnet build` the generated database project
      and one host. Record the result, or that `dotnet` was absent.
    - **Compose, when `docker` is on `PATH`:** `docker compose -f docker/docker-compose.yml config` over a filled `.env`.
  - Run:
    - the venv suite, and the suite under `/usr/bin/python3` without lxml and jsonschema;
    - `doctor.py`;
    - `tools/check-dual-schema-docs.sh` with the venv on `PATH`;
    - `tools/check_knowledge_stamps.py`;
    - `tools/check_drift.py <dgf-root>`;
    - `tools/run_known_good.py <dgf-root>` (differing only as Task 3 allows).
  - Record the commands, the exits and anything surprising under `## Results`.

- [x] **Task 13: Documentation checkpoint.** (depends on 12)
  - Files:
    - `docs/pipeline.md` — a section "Starting an application": the one command, its folder rule, `design.py`'s and
      `generate.py`'s exit tables (as the page has for the spine's, the loop's and the DGF skills' scripts), and the hand-over
      to `/dgf`;
    - `docs/skill-authoring.md` — a slice script loading a stdlib `lib/` module by path, and which modules allow it;
    - `docs/getting-started.md` — the empty-folder flow;
    - `AGENTS.md` — the tree, the entry points, the "Not yet created" line;
    - `README.md` — the status;
    - `.ai-factory/DESCRIPTION.md` — Current State.
  - Handover, not edits:
    - `.ai-factory/ARCHITECTURE.md` (`/aif-architecture`): the slice tree gains `dgf-scaffold/{scripts,templates,references}`,
      plus Task 3's citations;
    - `.ai-factory/ROADMAP.md` (`/aif-roadmap`): milestone 12 closes.
  - Logging: n/a.

## Results

Run 2026-09-30, scratchpad folders, DGF read at the pinned `1d5999186` (extracted with `git archive`; the live checkout was 12 commits ahead and dirty).

**Walked example** (DESIGN-FORMAT.md's design): `--empty-only` 0; one survey round → `design.py` 2 with `SCAFFOLD_ASK` for `dgf_version`, `base.source`, `base.supply` and two `DEFAULT:` lines (`workspace`, `modules[About].route`); complete → 0; `--dry-run` 0 (33 solution + workspace targets); `generate.py` 0 (67 files); `--check` 0 — with `supply: copy` over a copy of DGF's real `webasm` (3570 files, whose own findings are not counted) and with `supply: mount`.
**Hand-over:** `locate_plan.py --root-only` `ROOT_NOT_SET_UP`; `inventory_root.py` 0 under `copy`, 2 `BASE_WORKSPACE_ABSENT` under `mount`.
**Refusals:** a non-empty folder is refused by both scripts (`SCAFFOLD_DIR_NOT_EMPTY`, then `SCAFFOLD_DESIGN_INCOMPLETE`); a corrupted template gives exit 3 `SCAFFOLD_TEMPLATE_MISSING` and the folder is untouched (Step 5's exit-3 row → STOP); `SCAFFOLD_SQL_TYPE_UNKNOWN` by a known-bad case with `--knowledge-dir`.
**Real builds:** `dotnet build` of the generated database project — succeeded, 0 errors, `TreatTSqlWarningsAsErrors` on. `dotnet build` of a generated host — succeeded, from the machine's NuGet cache: package `DGF.API` 1.1.15 (also 1.1.11, 1.1.13) was cached from a private Azure DevOps feed, which confirms the package id and that `Program.cs` compiles against the real package. `docker compose config` over a filled `.env` — 0; inline `configs` content is interpolated.
**Suites:** venv 1078 tests OK; `/usr/bin/python3` (no lxml) 1078 OK, 282 skipped; `doctor.py` pass; `check-dual-schema-docs.sh` CLEAN; `check_knowledge_stamps.py` CLEAN; `run_known_good.py` CLEAN against the pinned tree (against the live checkout it is BLOCKED by `autoComplete` components DGF added since — not this branch); `check_drift.py` against the pinned tree: 4 warnings, three pre-existing (older ledgers) and `TreeManager.cs`, whose recorded digest is the CRLF working-tree one while `git archive` gives LF — an artifact of extracting, not drift. Against the live checkout 12 of this branch's 70 application-layout sources have changed (see the ledger).

**Deviations from the plan, each on evidence**
- Sign-in providers are `basic`, `dgpass`, `azure` (the shell's method names and DGF's `Authentication:DGPassOIDC` / `AzureOIDC` sections), not `dgpass`/`azuread`; `basic` is DGF's own local sign-in.
- `unicode` is not a design key: `dbtype` `StringUnicode` selects `NVARCHAR` in 55 of 55 fields.
- `AspNetRoles` has one unique index on `NormalizedName`, and the code seeds roles only when the table is empty: the SQL writes each role once (built-ins included), under the first instance.
- The application tables' `ApplicationId` column is `NULL`, not `NOT NULL`: nothing in the runtime fills it, so `NOT NULL` would fail every insert.
- The host needs its `Integrations` sections to start, so the generated settings carry the Registration Authority, signing and notification sections as `${VAR}` placeholders (the plan listed integrations out of scope).
- UI settings are inline compose `configs`, not `docker/ui/*.json`: a bind-mounted file is not interpolated.
- The manifest gained repeat scopes `workspace`, `group`, `membership` and a list form of `repeat`; a secret-named key must hold exactly one `${VAR}`, so the SQL and Redis connection strings are variables.
- `design.py` gained `--knowledge-dir` and a `generated` mode; commits 3 and 4 are one, since the doctor requires `SKILL.md`.
- Register lists and service starts use the grid node's `CreateForm` / `OpenForm` (`FORM:default`, `STATEPROCESS:<Module>`), on sample evidence; separate "New"/"Start" folders had none.

**Unverified — no DGF runtime was run:** `FORM:default` and `STATEPROCESS:` behaviour at runtime; that a case created through `CreateForm` is tied to the `<Module>` process instance; that the grid shows its create button; route-level role gating (only `requireAuthorization` exists); newer DGF's per-request application resolution (unread). Unreachable from the command line, covered by unit tests only: `SCAFFOLD_TARGET_EXISTS` (a race), `SCAFFOLD_TEMPLATE_MISSING`, `SCAFFOLD_WRITE_FAILED`.

## Risks

- **ADR 0010's reading (D1).** If it is read as plugin-wide, Task 2 also supersedes ADR 0010.
- **Thin SQL evidence.** A `dbtype` with no DGF pair cannot be used until evidence exists. Task 5's tally shows how many there
  are.
- **v1 refuses `PrimaryKey` and `Checkboxlist`.** The vendored XSD lags on both. Lifting this needs a re-vendored
  `settings.xsd` or an evidenced exception.
- **The application does not run until its `${VAR}`s are filled.** DGF pins no consumer image, feed or registry.
- **The solution files are checked only by the post-generation check and, when `dotnet` exists, one real build.** No
  validator reads C#, SQL, compose or MSBuild.
- **The templates drift from DGF's samples** between maintainer runs of `tools/check_drift.py`.

## Out of scope (follow-ups)

- Adding to an existing application. That is `/dgf-plan` and `/dgf-implement`, after `/dgf`.
- Helm and pipelines. DGF ships no consumer pipeline, and the request names Docker.
- Integrations: DGF's Pay, Sign, Notify and RA, which its local stack stubs.
- `BASE:` references in generated files, which a later version could allow once a base is in the root.
- Estate profiles, Zambian or any other (declined 2026-09-29).
- DGF's service spec v0.9 as the `service` pattern's input. It is provisional; v1's `service` is D7's pattern.
