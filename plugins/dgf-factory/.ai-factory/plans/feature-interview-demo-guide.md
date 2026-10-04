# Implementation Plan: Interview Demo Guide — Split Bill on DGF, built live with dgf-factory

Branch: feature/hackathon-demo-guide
Created: 2026-10-04

> Written on the existing branch, which was cut from `develop`, not from the configured base branch `main`:
> `main` is behind `develop` by the whole DGF-specific-skills milestone, `/dgf-scaffold` included, and the demo
> builds the application with it. The merge target is `develop`, as for the last four feature branches.
>
> This plan **replaces** the untracked draft that sat on this branch for the earlier request ("a hackathon,
> 30–60 minutes, e-service edits"). The draft was never committed; a copy is in this session's scratchpad.
> The machine facts it had verified were re-checked today and carried over where they still hold.
>
> `.claude/settings.local.json` sets `HANDOFF_MODE=1`, so this plan took the non-interactive path: no
> preference questions were asked, the defaults are recorded under Settings, and every decision below is
> yours to change before `/aif-implement`.

## Original Request
i will meet tomorrow with best company from eu to hire me, i want to demonstrate everything I done through DGF and dgf-factory projects. DGF as a runtime that i have build from scratch and dgf-factory as a builder for DGF.

I want to demonstrate capabilities by developing an application from scratch on dgf. Application let it be "Split bill web app, with mobile friendly design".

So you must preapare a plan of what and how i will demonstrate that. I have no more that 1-2 hours.

As a result of this plan i expect an guide, step-by-step instructions to do that and what to expect at the end.

## Settings
- Testing: yes — the test of a demo guide is a rehearsal: the 75-minute core is run once end to end on this machine against the clock from a clean state, every placeholder in the guide is replaced with the run's real output, and each extension segment is timed on its own (Task 9). No unit tests: the deliverables are Markdown, one JSON design file, one compose override, two settings files and two SQL files.
- Logging: minimal — not applicable to Markdown. The guide's fallback section names the scripts' `--verbose` flag (or `DEBUG=1`) and `docker compose logs --tail 80 splitbill-api` for a live diagnosis.
- Docs: yes — the deliverable is documentation; `README.md` and `AGENTS.md` link it (Task 10).

## Roadmap Linkage
Milestone: "none"
Rationale: Interview material for 2026-10-05; no roadmap milestone owns it. The guide loads the plugin with `--plugin-dir` (Decision 2), so it claims nothing from the Marketplace Release milestone, and it changes no skill, script or knowledge file.

## What the guide must achieve

- **Audience and time box.** A hiring team — engineers and a technical lead — for one to two hours, with questions interrupting at any point. A **75-minute core**, a **60-minute cut** when the conversation runs long, and **extensions to 120** that slot in without re-planning. The guide is a presenter's script: minute marks, what to type, what to say in one or two sentences, what the audience sees, a fallback for every live step, and a "what to expect at the end" section the presenter can check against.
- **Two subjects, one story.** *DGF* — a runtime built from scratch: one Angular shell, one API, one dispatcher, 34 statically registered component services; an application is a workspace of configuration over a base, read at request time, in two schema families. *dgf-factory* — a builder that arrives already knowing DGF: it generates a whole application from one design file, plans and executes changes as configuration, lets scripts decide everything a script can decide, gates every change against the merge-base, and learns from each fix.
- **Five live moments the room remembers.** (1) DGF's own showcase runs a four-step e-service in the browser, and a saved file is live on the next refresh. (2) An **empty folder becomes a running Split Bill application**: the scaffold's survey, the defaults nobody chose, the tree, the clean check, then the app itself at its own URL. (3) Groups, members and expenses are entered on a **phone-sized viewport** in the generated registers. (4) The pipeline adds the **balances page** ("who owes whom") and a process change to the new app, the gate passes, a deliberate break is caught with the exact finding, and the fix becomes a patch and a rule. (5) The close names what scripts decided and what the model decided — and the numbers behind it.
- **Honest about the seams.** DGF publishes no consumer images, feed or database baseline yet, so the generated application runs tonight on the framework's locally built images and its live database. The guide says so in one sentence at the moment it matters, and never claims the scaffold's own compose stack was booted.

## What is on this machine (verified 2026-10-04)

| Fact | Evidence |
|---|---|
| DGF checkout `~/workspaces/dotgov/_DotGovFramework/DotGovFramework`, branch `develop` at `5310789be` (release notes finalise 1.1.16), working tree clean, no `demo/*` branches, no `.dgf-factory/` under its samples | `git` in the checkout |
| The default compose stack (`src/samples/DGF.Compose/docker-compose.yml`, project `dotgov-framework`): traefik, SQL Server 2022, Redis, Seq, Gotenberg and four WireMock stubs are **up and healthy** on `global-network`; `dgf-api` and `dgf-ui` **exited 2 hours ago**, their images built (`dgf-api` 804 MB, `dgf-ui` 155 MB); `db-init` and `dgf-demo-seed` ran | `docker ps -a`, `docker images`, `docker network inspect global-network` |
| `./up.sh` restarts it: network, `.env`, TLS certificate, RA key, stale names, `docker compose up -d --wait`, then polls `/health/live` for up to 300 s. Showcase `https://dgf.localtest.me/components` (no login), API `dgf-api.localtest.me`, logs `dgf-logs.localtest.me`, traefik `localhost:8080`. `--down` keeps volumes; **never `--clean`** (the DACPAC re-publish on emulated SQL Server is the slow path) | `up.sh`; `readme.md` |
| `dgf-api` runs `WorkspaceName: dgf` with `DGF_WORKSPACES_ROOT_PATH=/workspaces`, **`DGF_CONFIGURATION_CACHING_DISABLED=true`**, bind-mounts `../workspaces/dgf` and `../workspaces/webasm` read-write, and replaces `/app/appsettings.json` with `configs/default/appsettings.json` (hosts and `CorsOrigins` for `dgf*.localtest.me`, basic sign-in on). `dgf-ui` mounts `dgf-ui/appsettings.default.json` (`apiUrl`). **A saved JSON or XML file is live on the next page load.** The base templates `dgf-api-clean-base` / `dgf-ui-clean-base` in `docker-compose.base.yml` exist for a second application to `extends:` — the consumer stacks (`docker-compose.zims.yml`) do exactly that | `docker-compose.yml:45-123`; `docker-compose.base.yml` |
| Database `DGF`, `sa` password and the admin credentials in the compose folder's `.env`; `sqlcmd` is inside `dgf-sqlserver` at `/opt/mssql-tools18/bin/sqlcmd` (the healthcheck uses it; `mssql-tools` has no arm64 image). SQL Server runs **emulated** on this Apple Silicon machine | `.env-example`, `docker-compose.infra.yml` |
| **The API does not start without an `aspnet_Applications` row** for its `WorkspaceName` (`WorkspaceProvider.Current` throws); the row's `ApplicationId` partitions the framework's own rows. `AspNetRoles` has one unique index on `NormalizedName`, so a role name exists once across applications; the code seeds roles only when the table is empty, and the seeded `admin` and its roles belong to the showcase's `ApplicationId` `B6E1A1C4-…` | `1.PostDeployment.Workspaces.sql`; `knowledge/application-layout.md` §2–§3 |
| The `dgf` workspace: 62 catalogue pages, 111 component JSON files, 12 entities, one real e-service `DGF.Demo.EService` (Apply → Pay → Sign → Issue, `allowAnonymouslyProcessing`), the `ComponentsPay`, `ComponentsMonitor` and `ComponentsDataTableHierarchy` pages. Enter through `/components` and the sidebar: **deep links to child routes render blank** | `dgf/readme.md`; the wiki's `The-DGF-Workspace.md` |
| The UI is Angular 19.2 + PrimeNG 19 over the Bootstrap 5 grid, viewport meta set, **mobile threshold 991 px** (`UtilsService.isMobile()` switches pickers to touch UI), the sidebar overlays on small screens, `row`/`cols` stack. No PWA manifest. `*.localtest.me` resolves to 127.0.0.1, so **a phone cannot reach the stack: the phone view is Chrome DevTools' device toolbar** | `src/DGF.UI/src/index.html`, `utils.service.ts`; the wiki's `Row.md`, `Sidebar.md`, `ListBox.md` |
| `/dgf-scaffold` generates: `<App>.slnx`, one thin host per API on the `DGF.API` package, a `Microsoft.Build.Sql` database project with **`dbo/Tables/<Entity>.sql` per entity, `1.PostDeployment.Applications.sql` (the row, `IF NOT EXISTS`) and `2.PostDeployment.Roles.sql`**, a compose stack, `docs/`, and per workspace `sitemap.json`, `home`/`loginPage`, `_application.sitemap`, `_PROFILE/Main/<group>/_tree.xml` with a node per module. A `register` module = `settings.xml` + default `_form.xml` + table and lookup `_view.xml` + `DataSource/<Entity>.json` (`type: table`) + a `dataTable` list page + a `GRID` node with `CreateForm`/`OpenForm` `FORM:default`. A `service` module adds `_PROCESS/<Module>/process.xml` (Draft → Submitted → InReview → Approved/Rejected → End, a `Task` per review role) and five `_workflow.xml`. **The output builds and checks clean; it has never been run against a live DGF** — unverified: `FORM:default`/`STATEPROCESS:` at runtime, the grid's create button, role gating | `tests/fixtures/golden/scaffold/single/`, `example/`; `plans/feature-dgf-scaffold.md` §Results |
| Routes: `DataSource`, `Page`, `DataTable` → JSON; `Form`, `Workflow`, `Process` → XML; `Chart` → `ROUTE_NO_ROW` (knowledge stamped 1.1.11; DGF added `Chart` and `AutoComplete` since). The validators flag those two as `UNKNOWN_COMPONENT` in the showcase, not in anything the scaffold generates | `route_means.py` runs; the earlier draft's audit numbers |
| A `rawsql` data source is `{"type": "rawsql", "singleResult": false, "query": "…"}` (schema properties `Query`, `CountQuery`, `Parameters`, `AllowUnauthorizedAccess`, …); **its key column must be aliased `AS [key]`**; the OM ignores SQL `DEFAULT`s (nullable columns, which the generated tables have); JSON allows comments but no trailing commas; a wrong component `type` renders a blank page with no error | `dgf/FM/_COMPONENTS/DataSource/DemoApplicationStats.json`; `knowledge/schemas/json/RawSqlDataSource.schema.json`; the wiki's `Database.md` §7 |
| Plugin `.venv` (Python 3.9.6) has `lxml` 6.1.3 and `jsonschema` 4.25.1; the system `python3` has neither. **The skills call bare `python3`**, so `claude` must be launched from a shell with the `.venv` activated. `/dgf-doctor` is **warn, not clean**: two `ABSOLUTE_PATH` warnings from the git-ignored IDE build folder `skills/dgf-scaffold/templates/solution/obj/` | `doctor.py` run; `.venv/bin/python -c "import lxml, jsonschema"` |
| Claude Code 2.1.285; the plugin is **not installed** (`claude plugin list`: gitkraken-hooks, zambia-service-directory). It loads with `claude --plugin-dir <plugin>`; a plugin's skills may surface namespaced (`/dgf-factory:dgf-doctor`) — Task 9 records what the terminal shows | `claude --version`, `claude plugin list` |
| `docs/demo/` does not exist; `dotnet` 10, `node`, `docker`, `mkcert` present; `DGF.API` 1.1.15 is in the local NuGet cache; the hosted DGF docs MCP is loaded in this session | `ls`; the earlier draft's checks |
| Measured earlier on the samples root: whole-root `audit_root.py` 8.1 s, `--reach` 0.03 s, unit suite 56 s (1078 tests), `check_drift.py` 0.15 s, `inventory_root.py` 0.2 s | the earlier draft's timed runs |

## Decisions (made for this plan — change any of them before approving)

1. **The scaffolded application runs on the showcase stack: its images, its database, its traefik.** The empty folder is `~/demo/splitbill` (a `git init -b main` repository). `/dgf-scaffold` generates the whole application there. Its `workspaces/splitbill` is served by a second API container and a second UI container added to the **same compose project** with one extra file — `docker compose -f docker-compose.yml -f docker-compose.splitbill.yml up -d splitbill-api splitbill-ui` in the compose folder — so `sqlserver`, `redis`, `.env` and the TLS certificate are shared and `up.sh` is untouched. `splitbill-api` extends `dgf-api-clean-base` with `dgf-api`'s environment block, `WorkspaceName: splitbill`, caching disabled, the mounts `${SPLITBILL_APP}/workspaces/splitbill:/workspaces/splitbill` and `../workspaces/webasm:/workspaces/webasm`, a copy of `configs/default/appsettings.json` with every `dgf-api.localtest.me` → `splitbill-api.localtest.me`, `dgf.localtest.me` → `splitbill.localtest.me` and `WorkspaceName`, and the traefik host `splitbill-api.localtest.me`; `splitbill-ui` extends `dgf-ui-clean-base` with an `appsettings.json` whose `apiUrl` is the new API, host `splitbill.localtest.me`. The **generated SQL is applied to the live `DGF` database** by one script, `apply-sql.sh`: the application row and the role from `ContinuousDeployment/`, then each `dbo/Tables/*.sql` guarded by `IF OBJECT_ID(…) IS NULL`, through `docker cp` and `sqlcmd` inside `dgf-sqlserver`. *Why:* DGF pins no consumer image, feed or baseline — the scaffold's own `README.md` says so — and this is the one way a generated application can run on this machine tonight; it is also exactly how DGF's consumer stacks run. *The spike (Task 3) decides it, with a 75-minute time box.* **Rule:** if by the end of the box the Groups register does not open its create form at `https://splitbill.localtest.me` with the admin signed in, stop debugging and switch to **fallback F**: the Split Bill lives inside the `dgf` workspace as pages, entities and a process the pipeline authors (tables still from the scaffold's generated SQL), and the scaffold is shown for generate + check + tree only. The decision and its evidence go into `prep-checklist.md`.
2. **Load the plugin with `claude --plugin-dir "$PLUGIN"`** from this `develop` checkout, started from a shell with `source "$PLUGIN/.venv/bin/activate"` so the skills' bare `python3` has the validators' dependencies. The marketplace install is one spoken line in the close. *Alternative:* merge `develop → main` tonight and install live — a GitHub round-trip in the room and a merge outside this plan's scope.
3. **The design is pre-written, three values left open.** `docs/demo/splitbill/application.json` holds everything the request states — name, instance, modules, roles, the full data model — and omits `dgf_version`, `base.source` and `base.supply`, so the scaffold's survey asks **one round of three questions** on stage (answers: `1.1.15`, the checkout's `webasm` path, `mount`) and prints its `DEFAULT:` lines; the file is copied to `~/demo/splitbill/docs/application.json` before the demo, so Step 1 is a resume with zero drafting. `1.1.15` because that is the `DGF.API` version the scaffold's host build was confirmed against; the running images are built from the checkout and read configuration, not a version. *Why not a blank folder and the full survey:* five rounds of four questions is ten minutes of typing; one round shows the mechanism.
4. **The data model is final at scaffold time, and `Group` is not a table name.** Nothing after the scaffold writes SQL (`/dgf-plan` and `/dgf-implement` compose configuration; `/dgf-model` names the database work and never writes it), so every entity and field the demo needs is in the design: `BillGroup` (titled "Group" — `GROUP` is a reserved word and the OM's generated SQL is not assumed to bracket it), `Member`, `Expense`, `Settlement`. Equal split only; no editable grid (v1 refuses `EditableGrid`).
5. **Three live changes on the new application, in one fast plan** (`/dgf-plan fast`, no branch — the generated repo has one commit, and a full plan's Explore round costs minutes). **A** — the balances page: `FM/_COMPONENTS/DataSource/Balances.json`, a `rawsql` data source computing, per group and member, paid, equal share and balance (the SQL is below, settlements subtracting when present), and `Page/SiteMap/Balances.json` — the scaffold's content page — gains a `dataTable` bound to it with four columns (Group, Member, Paid, Balance), which fit a phone. Both JSON, both `kind: config`, both routed `json`. **B** — the settle-up process speaks the domain: in `FM/_PROCESS/SettleUp/process.xml` the states' `title`s become Requested / Sent / Confirming / Settled / Disputed, and `Rejected` gains a transition back to `Submitted` titled "Resend"; XML, routed `xml`, checked by `validate_process.py`. **C** — the deliberate break, by hand in the editor: the new transition's target becomes `Submited` → `DEAD_TRANSITION`, blocking, a finding this branch introduced, `suggested_next: /dgf-fix`. Then `/dgf-fix` (the smallest fix, a patch), `/dgf-commit` (the Commit Plan's groups), `/dgf-evolve` (the rule, checked by `check_override.py`). *Optional A′, if Task 4 confirms the JSON shape:* a `listBox` grid of `card` items over the same data source (`gridColumns` sm = 1) as the phone layout, the showcase's `ComponentsListBox` page as the reference.
6. **The mobile story is shown, not claimed.** Chrome DevTools' device toolbar (iPhone 14 Pro, 393 × 852) on the register list, the create form and the overlaying sidebar, and on the balances table — twice, once in Act 2 and once after change A. The one line to say: the shell is responsive by construction — one grid, one mobile threshold, touch pickers below it — and a workspace adds nothing to get it.
7. **Timeline: a 75-minute core**, with an opening about the two projects, three acts, pauses for questions after each act, a 60-minute cut list and 120-minute extensions (an audit with blast radius, a code tour of how DGF is built, the test and provenance story, the Pay and Monitor pages, change A′). Minute marks and quarter-hour checkpoints are in the outline below.
8. **The deliverable lives in `docs/demo/`**: `interview-guide.md`, `prep-checklist.md`, `cheat-sheet.md`, and `splitbill/` holding `application.json`, `docker-compose.splitbill.yml`, `appsettings.splitbill.json`, `ui-appsettings.splitbill.json`, `apply-sql.sh`, `reset.sql` and `balances.sql`. `docs/` is maintainer material, not shipped, so DGF paths are allowed in prose; the docs contract (check 4) still forbids absolute paths in link targets and in fenced code of every `*.md`, so commands use `$DGF`, `$PLUGIN`, `$APP` and `$COMPOSE` set once at the top of the checklist, and the compose override uses `${SPLITBILL_APP}` from the compose folder's `.env`. The override and the two settings files are **copied into the compose folder** by the checklist (`docker-compose.splitbill.yml`, `configs/splitbill/appsettings.json`, `dgf-ui/appsettings.splitbill.json`), where `extends:` and `../workspaces/webasm` resolve exactly as the consumer stacks' files do; the DGF checkout stays clean apart from those untracked copies.
9. **Checkpoints and reset.** After generation, `tar czf ~/demo/splitbill-generated.tgz -C ~/demo splitbill` is the restore point for the folder; commits in the generated repo mark each step (`demo/1-set-up`, `demo/2-planned`, `demo/3-implemented`, `demo/4-fixed`, `demo/5-committed` as lightweight tags). `reset.sql` drops the four tables, the role and the row; `apply-sql.sh` is idempotent, so a rehearsal repeats with one tarball, one SQL file and `docker compose … up -d` (the containers re-read the mounted workspace; `docker restart splitbill-api` if a route "does not take"). `up.sh` is never run with `--clean`.
10. **Knowledge drift is a one-line answer, not a prerequisite.** The knowledge base is stamped 1.1.11 and the checkout is 1.1.15+; the generated application uses neither `Chart` nor `AutoComplete`, so its audit is CLEAN, and the showcase's 24 `UNKNOWN_COMPONENT` findings are the honest answer to "what happens when the framework moves" (the gate still blocks only on what a branch introduces). Re-vendoring is a maintainer milestone, not tonight's work.

## The Split Bill application

**The one-sentence request the presenter types:**

> `/dgf-scaffold a split-bill web app for a group of friends: groups, their members, expenses one member paid and everyone splits equally, a settle-up request that a group organiser confirms, and a balances page — local sign-in, mobile friendly`

**The design** (`docs/demo/splitbill/application.json`; Task 2 validates it and may correct a key against `DESIGN-FORMAT.md` — the shape below follows its worked example):

```json
{
  "design_format": 1,
  "application": {"name": "SplitBill", "title": "Split Bill"},
  "instances": [{"name": "splitbill", "title": "Split Bill"}],
  "apis": [{"name": "Api", "deployments": [{"name": "Splitbill", "instance": "splitbill", "auth": ["basic"]}]}],
  "roles": ["Organiser"],
  "modules": [
    {"name": "Groups",   "pattern": "register", "title": "Groups",   "entity": "BillGroup",  "route": "/groups"},
    {"name": "Members",  "pattern": "register", "title": "Members",  "entity": "Member",     "route": "/members"},
    {"name": "Expenses", "pattern": "register", "title": "Expenses", "entity": "Expense",    "route": "/expenses"},
    {"name": "SettleUp", "pattern": "service",  "title": "Settle up", "entity": "Settlement", "route": "/settleup", "roles": ["Organiser"]},
    {"name": "Balances", "pattern": "page",     "title": "Balances", "route": "/balances"}
  ],
  "data_model": {"entities": [
    {"name": "BillGroup", "title": "Group", "key": "Id", "fields": [
      {"name": "Id", "type": "Integer", "dbtype": "Int32", "required": true},
      {"name": "Name", "type": "Text", "dbtype": "StringUnicode", "size": 100, "required": true},
      {"name": "Currency", "type": "Text", "dbtype": "String", "size": 3, "required": true},
      {"name": "CreatedOn", "type": "DateTime", "dbtype": "DateTime"}
    ]},
    {"name": "Member", "title": "Member", "key": "Id", "fields": [
      {"name": "Id", "type": "Integer", "dbtype": "Int32", "required": true},
      {"name": "GroupId", "title": "Group", "type": "Picklist", "dbtype": "Int32", "required": true, "extract": {"entity": "BillGroup"}},
      {"name": "Name", "type": "Text", "dbtype": "StringUnicode", "size": 100, "required": true},
      {"name": "Email", "type": "Text", "dbtype": "String", "size": 200}
    ]},
    {"name": "Expense", "title": "Expense", "key": "Id", "fields": [
      {"name": "Id", "type": "Integer", "dbtype": "Int32", "required": true},
      {"name": "GroupId", "title": "Group", "type": "Picklist", "dbtype": "Int32", "required": true, "extract": {"entity": "BillGroup"}},
      {"name": "PaidById", "title": "Paid by", "type": "Picklist", "dbtype": "Int32", "required": true, "extract": {"entity": "Member"}},
      {"name": "Title", "type": "Text", "dbtype": "StringUnicode", "size": 200, "required": true},
      {"name": "Amount", "type": "Money", "dbtype": "Decimal", "required": true},
      {"name": "SpentOn", "title": "Spent on", "type": "DateTime", "dbtype": "DateTime", "required": true},
      {"name": "Notes", "type": "Text", "dbtype": "StringUnicode", "size": "MAX"}
    ]},
    {"name": "Settlement", "title": "Settlement", "key": "Id", "fields": [
      {"name": "Id", "type": "Integer", "dbtype": "Int32", "required": true},
      {"name": "GroupId", "title": "Group", "type": "Picklist", "dbtype": "Int32", "required": true, "extract": {"entity": "BillGroup"}},
      {"name": "FromMemberId", "title": "From", "type": "Picklist", "dbtype": "Int32", "required": true, "extract": {"entity": "Member"}},
      {"name": "ToMemberId", "title": "To", "type": "Picklist", "dbtype": "Int32", "required": true, "extract": {"entity": "Member"}},
      {"name": "Amount", "type": "Money", "dbtype": "Decimal", "required": true},
      {"name": "Note", "type": "Text", "dbtype": "StringUnicode", "size": 200},
      {"name": "RequestedOn", "title": "Requested on", "type": "DateTime", "dbtype": "DateTime"}
    ]}
  ]},
  "sources": {"application.name": "prompt", "instances": "prompt", "apis": "prompt", "roles": "prompt", "modules": "prompt", "data_model": "prompt"}
}
```

Verified today with `design.py` over this exact file: exit `2`, exactly three `SCAFFOLD_ASK` lines (`dgf_version`, `base.source`, `base.supply`) and one `DEFAULT:` line, `instance_model = "own-workspace"`; the register and page modules' `roles` default to `Members` silently. After the three answers Task 2 expects exit `0`. The Groups, Members and Expenses nodes land under `_PROFILE/Main/Members/`, which every signed-in user gets; the SettleUp node under `Main/Organiser/`.

**The data the presenter enters** (on the cheat sheet, typed in Act 2): group *Lisbon trip*, `EUR`; members *Ana*, *Ben*, *Chloe*; expenses *Dinner* 90.00 paid by Ana, *Taxi* 30.00 paid by Ben, *Tickets* 60.00 paid by Chloe. Equal share 60.00 each: Ana +30.00, Ben −30.00, Chloe 0.00 — numbers the room can check in its head when the balances page appears.

**Change A's query** (`docs/demo/splitbill/balances.sql`; Task 4 runs it against the live database before it goes into the data source — one line, no comments, inside the JSON):

```sql
WITH cnt AS (SELECT GroupId, COUNT(*) AS Members FROM dbo.Member GROUP BY GroupId),
     paid AS (SELECT GroupId, PaidById AS MemberId, SUM(Amount) AS Paid FROM dbo.Expense GROUP BY GroupId, PaidById),
     share AS (SELECT e.GroupId, SUM(e.Amount) / c.Members AS Share FROM dbo.Expense e JOIN cnt c ON c.GroupId = e.GroupId GROUP BY e.GroupId, c.Members),
     settled AS (SELECT GroupId, FromMemberId AS MemberId, SUM(Amount) AS Paid FROM dbo.Settlement GROUP BY GroupId, FromMemberId),
     received AS (SELECT GroupId, ToMemberId AS MemberId, SUM(Amount) AS Received FROM dbo.Settlement GROUP BY GroupId, ToMemberId)
SELECT m.Id AS [key], g.Name AS [Group], m.Name AS [Member],
       ISNULL(p.Paid, 0) AS [Paid], ISNULL(s.Share, 0) AS [Share],
       ISNULL(p.Paid, 0) - ISNULL(s.Share, 0) + ISNULL(st.Paid, 0) - ISNULL(r.Received, 0) AS [Balance]
FROM dbo.Member m
JOIN dbo.BillGroup g ON g.Id = m.GroupId
LEFT JOIN paid p ON p.GroupId = m.GroupId AND p.MemberId = m.Id
LEFT JOIN share s ON s.GroupId = m.GroupId
LEFT JOIN settled st ON st.GroupId = m.GroupId AND st.MemberId = m.Id
LEFT JOIN received r ON r.GroupId = m.GroupId AND r.MemberId = m.Id
ORDER BY g.Name, [Balance] DESC
```

## The guide — outline

Files under `docs/demo/`:

| File | Purpose |
|---|---|
| `interview-guide.md` | The presenter's script: the story in three sentences, the opening, the acts with minute marks and quarter-hour checkpoints, what to type, what to say, what the audience sees, a pause after each act, every fallback, the 60/75/120 timeline, the close, the Q&A crib, and **What to expect at the end** |
| `prep-checklist.md` | Variables; night-before and T-30 lists; the spike's decision (S1 or F) and its evidence; the reset recipe; the checkpoints; what never goes on screen |
| `cheat-sheet.md` | One page, in order: every command, prompt and survey answer with its minute mark and cut line; the data to enter; the second-screen companion |
| `splitbill/application.json` | The design (above), validated by `design.py` |
| `splitbill/docker-compose.splitbill.yml`, `appsettings.splitbill.json`, `ui-appsettings.splitbill.json` | The hosting override (Decision 1), copied into the compose folder by the checklist |
| `splitbill/apply-sql.sh`, `reset.sql`, `balances.sql` | Apply the generated SQL to the live database; undo it; change A's query |

### Act 0 — Before the room (not live)

Stack up (`./up.sh`), the showcase loaded once, one e-service run completed. `~/demo/splitbill` holds only `.git/` and `docs/application.json` (restored from the tarball if a rehearsal left it generated); the four tables and the row are **absent** (`reset.sql` run) because the SQL is applied live. The override files copied into the compose folder; `SPLITBILL_APP` set in its `.env`. Terminal 1: Claude Code started in `~/demo/splitbill` with `--plugin-dir`, `.venv` active, `/dgf-doctor` already green once, context cleared. Terminal 2: a plain shell in the compose folder with `.venv` active — the fallback that runs the scripts directly, `apply-sql.sh` and `docker compose`. Browser tabs: the catalogue, the e-service page, `https://splitbill.localtest.me` (shows a blank page until the containers start — opened later), Seq. Editor open on `~/demo/splitbill` and on `src/samples/workspaces/dgf/FM`. Font sizes up. `.env`, the admin password and the RA key never on screen; the catalogue needs no login.

### Opening (0:00–0:05)

Who you are in one breath. Then the two sentences the whole demo rests on: *"DGF is a runtime I built from scratch: one Angular shell, one API, one dispatcher, and a government service is a folder of configuration it reads at request time."* *"dgf-factory is a Claude Code plugin that already knows that runtime: it generates an application from one design file, plans and executes changes as configuration, and lets scripts — not the model — decide whether a change is sound."* What we will do: build a split-bill app from an empty folder, run it on a phone-sized screen, change it through the pipeline, break it, and watch the gate catch it. One architecture drawing on the whiteboard or a single slide: shell → dispatcher → component services → workspace (`FM/_COMPONENTS` JSON, `_DATA` `_PROCESS` `_WORKFLOW` XML) over `webasm`.

### Act 1 — DGF running (0:05–0:17, then 2 minutes of questions)

| Min | Do | Say | Audience sees |
|---|---|---|---|
| 0:05 | Open `/components` | "DGF's own showcase: 62 pages, one per component, each a rendered example beside the configuration that produced it. Everything on screen is files." | The catalogue |
| 0:06 | The ProcessFlow page: run the e-service — Apply, Pay, Sign, Decision | "A real state process over a real table: four states, four workflows, legacy XML. Each Next writes the case row and the state instance." | The rail advancing |
| 0:09 | Editor: `dgf/FM/{_PROCESS,_WORKFLOW,_DATA,_COMPONENTS}` and `webasm` beneath | "Two tiers: the application over the base, `BASE:` reaches down, nothing falls back. Components are JSON; forms, views, workflows and processes are XML — two schema families, both live, and a schema existing is not the runtime reading it." | The tree |
| 0:11 | Hand-edit the `Issue` state's `title` in `process.xml`; refresh the rail; `git checkout -- process.xml` | "Read at request time, caching off in this stack. Also: nothing checked that edit. That is the problem the builder solves." | The last step renamed |
| 0:13 | DevTools device toolbar on the catalogue page: a form page, the sidebar | "One grid, one mobile threshold at 991 px, touch pickers below it. A workspace gets this for free." | The phone view |
| 0:15 | (If the room is service-minded: the Pay page — stub portal, Paid, receipt.) Pause | "Questions on the runtime before we build on it?" | — |

### Act 2 — From an empty folder to a running app (0:17–0:42, then 3 minutes of questions)

| Min | Type | Say | Audience sees |
|---|---|---|---|
| 0:17 | `/dgf-doctor` | "Every quality command ends in a machine-readable block. A script computes the status; the model relays it." | `dgf-gate-result`, `pass` |
| 0:18 | `ls -la ~/demo/splitbill ~/demo/splitbill/docs` | "An empty folder, a git repository, and one design file I wrote from the request — the scaffold would have written it from the sentence; I pre-wrote it to save your time." | `.git`, `docs/application.json` |
| 0:19 | The one-sentence `/dgf-scaffold …` prompt | "DGF ships no generator. The skill checks the design with a script, asks only what is open — three things — and prints every default nobody chose." Answer: `1.1.15`, the `webasm` path, `mount` | `SCAFFOLD_ASK` ×3, then `DEFAULT:` lines |
| 0:22 | generate | "The tree first, then it writes: the solution, the database project, the compose stack, the workspace — the four entities with their forms, views and data sources, the five list pages, the settle-up process with one workflow per state." Then the check: "secrets are variables, structure, routes, then the validators over what was generated — CLEAN." | `TARGETS: n`, `WROTE: n files`, `--check` CLEAN, the report |
| 0:26 | Editor: `workspaces/splitbill/FM/_DATA/Expense/settings.xml` beside `database/SplitBill.Database/dbo/Tables/Expense.sql`; `docs/data-model.md` | "One design entry, two files that agree: the entity the runtime reads and the table the database gets." | The two files |
| 0:28 | Terminal 2: `./apply-sql.sh`, then `docker compose -f docker-compose.yml -f docker-compose.splitbill.yml up -d splitbill-api splitbill-ui`; `curl -k https://splitbill-api.localtest.me/health/live` | "DGF publishes no consumer images yet, so tonight this runs on the framework's locally built images and its live database — the same images the generated compose file would pull. The application row, one role, four tables." | `Seeded aspnet_Applications row…`, `CREATE TABLE` ×4, two containers up, `Healthy` |
| 0:31 | `https://splitbill.localtest.me` → Sign in (`admin`) → Menu → Groups: *Lisbon trip* → Members: Ana, Ben, Chloe → Expenses: Dinner 90 / Ana, Taxi 30 / Ben, Tickets 60 / Chloe | "Generated registers: list, create, open. Every field, label and lookup came from the design." | The app, the rows |
| 0:38 | DevTools device toolbar: the Expenses list, the create form, the sidebar | "Same files, phone width." | The phone view |
| 0:40 | Pause | "Questions on the scaffold?" | — |

### Act 3 — The pipeline on the new application (0:43–1:07, then questions in the close)

| Min | Type | Say | Audience sees |
|---|---|---|---|
| 0:43 | `/dgf ~/demo/splitbill/workspaces` (version `1.1.15`); `git add -A`; `/dgf-commit` | "Set-up inventories the root and records the estate's DGF version against the knowledge's stamp. First commit." | The inventory, `config.yaml`, `DESCRIPTION.md`, the commit |
| 0:46 | `/dgf-plan fast "add a Balances page showing, per group and member, what they paid, their equal share and their balance, from a raw SQL data source; and make the settle-up process speak the domain: Requested, Sent, Confirming, Settled, Disputed, with a Resend transition from Disputed back to Sent"` | "Three tasks. The plan declares the workspace it touches and, per task, configuration or code and why; a script routes each new file — JSON for the data source and the page, XML for the process — and checks the plan before anything is written." | `PLAN.md`, `check_plan.py` CLEAN |
| 0:49 | `/dgf-implement` tasks 1–2; refresh `/balances` | "One task at a time, each validated against the last commit before the box is ticked. Ana +30, Ben −30, Chloe 0 — the numbers you can check." | The balances table |
| 0:53 | `/dgf-implement` task 3 | "A legacy artifact: XML, validated against the grammar and the runtime model." | The retitled states, the new transition |
| 0:56 | `/dgf-verify` | "The gate: every task done, every changed file inside the plan, no new finding across the whole root." | The block, `pass` |
| 0:58 | Break C by hand (`Submited`); `/dgf-verify` | "A transition to a state that does not exist. The runtime would have thrown on the organiser's click; the gate names it now and says what to run." | `fail`, `DEAD_TRANSITION`, `suggested_next: /dgf-fix` |
| 1:00 | `/dgf-fix` | "Reproduce, the smallest fix inside the plan's scope, confirm with the same check — and a patch: the estate just learned something." | The fix, the patch file |
| 1:02 | `/dgf-commit` | "Conventional commits following the plan's Commit Plan." | `git log` |
| 1:04 | `/dgf-evolve` *(cut line 1)* | "Patches distil into a rule the skill checks next time; a script checks the rule first — a rule may add a check, never relax a gate." | The override, `check_override.py` accepting it |
| 1:07 | DevTools device toolbar on `/balances` | "And it still fits a phone." | The phone view |

### Close (1:08–1:15)

What scripts decided today — `design.py`, `generate.py --check`, `check_plan.py`, `check_change.py`, the four validators, `verify_gate.py`, `check_override.py` — and what was left to judgement. The numbers: 34 component services behind one dispatcher; 69 JSON schemas and 9 XSDs vendored with digests; 1078 unit tests, a known-bad corpus of one case per blocking finding; 27 decision records; every framework fact stamped with the DGF version and the source digest it was read at. Where to get it: `claude plugin marketplace add andrian-org/claude-plugins`, `claude plugin install dgf-factory@andrian-org`. What is next for each project (your words). Q&A crib, one line each citing an ADR or knowledge file: "Is this BPMN?", "JSON or XML?", "Can it write C#?", "Does the generated app run on its own?" (it builds and checks clean; DGF publishes four artifacts it needs — base, baseline, UI image, feed — which is why it ran on the showcase's images today), "What if the model is wrong?", "How do you keep the knowledge current?", "Why Python for the validators?", "What about roles?" (global by name, partitioned by application id — a wart the research found in every estate).

### Extensions to 120 (+45)

| Insert after | Min | Rows |
|---|---|---|
| Act 3 | 6 | `/dgf-audit` over the new root (`GRAPH:` lines, roles) and `/dgf-audit --reach workspaces/splitbill/FM/_WORKFLOW/SettleUp.InReview/_workflow.xml` — "blast radius before a change, and a `LIMIT:` line saying what a static walk cannot see" |
| Act 1 | 10 | **How DGF is built**: `ComponentsController` (one dispatcher), `ComponentServiceProvider` (the static registry — why a validator is possible), `WorkspaceSettings` (`webasm`, `FmPath`/`FmBasePath`), the parity table in `knowledge/schema-families.md` §6 — `Workflow` and `ProcessFlow` have JSON schemas the runtime ignores |
| Act 3 | 8 | **How it is kept honest**: the unit suite started in Terminal 2 at the top of the act (56 s); `tests/fixtures/known-bad/process-dead-transition/expected.json`; `tools/check_drift.py` against the checkout; the provenance ledgers; the ADR index |
| Act 1 | 5 | The Pay page (stub portal, receipt) and the Monitor page (the diagram from `FM/_PROCESS`) |
| Act 3 | 10 | Change A′: the `listBox` card grid over the balances data source, through plan → implement → verify once more, with the room predicting the gate's verdict |
| Close | 6 | Longer Q&A |

## Timeline, checkpoints and cut lines

| Version | Minutes |
|---|---|
| **75** (core) | opening 5 · Act 1 12 + 2 · Act 2 25 + 3 · Act 3 25 · close 7 (minus 4 of pauses absorbed into questions) |
| **60** | 75 minus: `/dgf-evolve` (3), the Pay row (3), the phone view of the catalogue (1), the data entry trimmed to one group, two members, two expenses (3), the tree walk in Act 2 trimmed to the two files (2), the pauses merged into the close (3) |
| **120** | 75 plus the six inserts above (45) |

Where you should be: **0:17** doctor done · **0:31** the app answers `/health/live` · **0:45** first commit · **1:00** the gate has failed once · **1:08** closing. Cut lines in order: `/dgf-evolve`; the Pay row; the catalogue phone view; A′; the tree walk; the second e-service run.

## Fallbacks

- **Claude slow or a skill misfires** → Terminal 2 runs the same decision directly: `design.py`, `generate.py --check`, `verify_gate.py`, `check_plan.py`, `check_override.py`. The scripts are the product; the skills are the conversation around them.
- **The generated app does not boot in the room** → `docker compose logs --tail 80 splitbill-api`; if it is the row or a table, re-run `apply-sql.sh`; if it is anything else, open the tarball's pre-generated copy in the editor and run Act 3 on it without the browser — the gate, the break and the fix need no runtime.
- **A route renders blank** → re-enter through `/home` and the menu, never a cold deep link; `docker restart splitbill-api` (15 s); check the component `type` and the JSON for a trailing comma.
- **Sign-in fails for `admin` on the new API** (the admin and its roles belong to the showcase's application id) → the checklist carries the one `INSERT` that maps `admin` to `Organiser` under the new id, rehearsed in Task 3; if sign-in itself fails, the routes' `requireAuthorization` is set `false` in the rehearsal and the guide says why.
- **`/dgf-implement` goes sideways** → `git checkout demo/3-implemented` in the generated repo and continue from `/dgf-verify`.
- **The stack is down** → no browser: the known-bad corpus for "the validator catches this", the golden fixture's audit for CLEAN, the scaffold on its own; Act 1 shrinks to the editor walk.
- **Running out of time** → the cut lines above, marked on the cheat sheet.

## What to expect at the end

- **In the browser:** `https://splitbill.localtest.me` signed in as the administrator, with the Groups, Members and Expenses registers holding the entered rows and `/balances` showing Ana +30.00, Ben −30.00, Chloe 0.00 — all of it shown once at phone width. The showcase at `https://dgf.localtest.me/components` unchanged (the title edit reverted).
- **In `~/demo/splitbill`:** the generated solution — the `.slnx`, `src/Api/`, `database/SplitBill.Database/` with four table scripts, `docker/`, `docs/` with the design — and under `workspaces/`: `splitbill/` with the five pages, four entities, the settle-up process and its five workflows, plus `.dgf-factory/` holding `config.yaml`, `DESCRIPTION.md`, `PLAN.md` (three ticked tasks), one patch under `patches/`, and (with evolve) `skill-context/dgf-process/SKILL.md` and `evolutions/`. A git history of four or five commits: set up, the plan, the balances page, the process change with its fix and patch, the override.
- **In the terminal:** the doctor's block (`pass`), the scaffold's `--check` (CLEAN), two verify blocks — one `pass`, one `fail` naming `DEAD_TRANSITION` with `suggested_next: /dgf-fix` — and `check_override.py` accepting the rule.
- **In the database:** one `aspnet_Applications` row (`splitbill`), one role (`Organiser`), four tables with the entered rows. `reset.sql` removes all of it.

## Risks

- **The spike fails or runs over its box.** Then fallback F: a smaller story that still shows every skill, decided tonight, not in the room. The guide is written so Act 2's rows are the only ones that change.
- **Roles and the admin are partitioned by application id** while role names are global; whether `admin` signs in to the new API, and whether the SettleUp node under `Organiser` appears, is unknown until Task 3. The fallbacks above cover both outcomes.
- **Change A depends on a `rawsql` shape and the `dataTable` columns being right.** Task 4 validates both files with `validate_config.py` and renders the page once before the guide quotes them; A′ is optional for the same reason.
- **The scaffold's register and service behaviour at runtime is unverified** (`FORM:default`, `STATEPROCESS:`, the create button). Task 3 is the first time it runs; the guide claims only what Task 9's rehearsal saw.
- **Emulated SQL Server.** Keep the stack up from the morning; `up.sh` without `--clean`; the four `CREATE TABLE`s take seconds, the DACPAC would take minutes.
- **Skill names under `--plugin-dir`** may be namespaced; Task 9 records what the terminal shows and the cheat sheet prints that.
- **Questions mid-flow.** `/dgf-scaffold` asks three; `/dgf` asks the version and the git settings; `/dgf-commit` asks to confirm; `/dgf-evolve` asks before writing. The cheat sheet gives every answer.
- **Secrets.** `.env`, the admin password and the RA key never on screen; the appsettings copies hold no literal secret (the compose environment supplies the connection strings).
- **Time.** An interview is a conversation; the quarter-hour checkpoints and the cut lines keep the core inside the slot.

## Out of scope

- Refreshing `knowledge/` to DGF 1.1.15+ (Chart, AutoComplete); merging `develop → main`; booting the scaffold's own compose stack; building the generated host image; slides beyond one architecture picture; changes to any skill, script or knowledge file; a hands-on segment for the audience.

## Commit Plan
- **Commit 1** (after tasks 1-4): "docs(demo): add the Split Bill design, the hosting override and the spike's results"
- **Commit 2** (after tasks 5-8): "docs(demo): write the interview guide, the prep checklist and the cheat sheet"
- **Commit 3** (after tasks 9-10): "docs(demo): record the rehearsal and link the guide"

## Tasks

### Phase 1: Tonight's spike and the demo assets

- [x] Task 1: Make the install demo-clean and the stack warm. Remove the git-ignored IDE build output under `skills/dgf-scaffold/templates/solution/` (`git clean -fdX skills/dgf-scaffold/templates/solution/` removes only ignored files) and re-run `.venv/bin/python skills/dgf-doctor/scripts/doctor.py` until the block says `pass`. In the compose folder run `./up.sh`, time it, confirm `https://dgf.localtest.me/components` answers and `https://dgf-api.localtest.me/health/live` is `Healthy`, and run the e-service once. **Files:** none in the repo (local state). **Evidence:** the doctor's block with `"status": "pass"`; the start time in seconds; one completed e-service run.
- [x] Task 2: Write and validate the design. Create `docs/demo/splitbill/application.json` from the design above (correct any key against `skills/dgf-scaffold/references/DESIGN-FORMAT.md`; keep `dgf_version`, `base.source` and `base.supply` out). In a scratch folder with only `docs/application.json`: `design.py --empty-only` → 0; `design.py` → 2 with exactly three `SCAFFOLD_ASK` lines; add the three answers to a scratch copy → 0; `generate.py --dry-run` → 0 (record `TARGETS: n`); `generate.py` → 0 (record `WROTE: n files`); `generate.py --check` → 0 CLEAN, run with the `.venv` python. Read the generated `workspaces/splitbill` tree once and note the exact node, page, process and workflow paths the guide will name. **Files:** `docs/demo/splitbill/application.json`. **Evidence:** the six exit codes and the `DEFAULT:` lines, recorded for the guide; the dry-run tree saved to the scratchpad.
- [x] Task 3: The hosting spike — 75 minutes, then decide (Decision 1). Write `docs/demo/splitbill/docker-compose.splitbill.yml` (two services extending `dgf-api-clean-base` and `dgf-ui-clean-base`, `dgf-api`'s environment block with `WorkspaceName: splitbill`, the two mounts, the settings mounts, traefik labels for `splitbill-api.localtest.me` and `splitbill.localtest.me`, `depends_on` the shared services), `appsettings.splitbill.json` (the default file with the host and workspace substitutions), `ui-appsettings.splitbill.json`, `apply-sql.sh` (copies `1.PostDeployment.Applications.sql`, `2.PostDeployment.Roles.sql` and each `dbo/Tables/*.sql` into `dgf-sqlserver`, wraps each table in `IF OBJECT_ID('dbo.<T>') IS NULL`, runs `sqlcmd` with the password read from the compose folder's `.env`, prints each result) and `reset.sql`. Generate into `~/demo/splitbill` (`git init -b main`, the design copied in, the three answers given), tar the result, copy the override files into the compose folder, set `SPLITBILL_APP` in its `.env`, apply the SQL, start the two services, and walk: `/health/live`, `/home`, sign in as `admin`, the menu, create a group, a member, an expense; the SettleUp node (and, if it is missing, the `INSERT` mapping `admin` to `Organiser` under the new application id); the phone view. Fix what is in the override files; **never patch a generated file**. Record the outcome — S1 with what worked and what needed the role insert, or F with the reason — in `docs/demo/prep-checklist.md` (a stub for now; Task 5 completes it). If F: Task 5 gains the fallback's Act 2 (the scaffold shown for generate + check; the Split Bill authored inside `dgf` by `/dgf-plan` + `/dgf-implement`, tables from the generated SQL), and Tasks 4 and 6 target the `dgf` workspace. **Files:** the five files under `docs/demo/splitbill/`, `docs/demo/prep-checklist.md` (stub). **Evidence:** `docker compose … up -d` exit 0 and both containers `Up`; a screenshot or the `curl` of `/health/live`; a row in each of `BillGroup`, `Member`, `Expense` created through the browser; the decision line with the clock time.
- [x] Task 4: Rehearse the three live changes and lock their outputs (depends on 3). Run `balances.sql` against the live database with the demo data through `sqlcmd` and keep the result (Ana 30.00, Ben −30.00, Chloe 0.00). Write the two JSON files for change A (`DataSource/Balances.json` as `rawsql` with the query on one line; the content page with a four-column `dataTable`, `dataSourcePath: "Balances"`, column `displayType`s as the generated list page uses) and change B's process edit, validate them with `validate_config.py`, `resolve_components.py` and `validate_process.py` from the plugin root, render `/balances` once, and run `/dgf-plan fast`, `/dgf-implement`, `/dgf-verify`, break C, `/dgf-verify`, `/dgf-fix`, `/dgf-commit` and `/dgf-evolve` once through the skills in `~/demo/splitbill` with `--plugin-dir`. Capture: the plan header and the three tasks as `/dgf-plan` writes them, the `PRE_EXISTING` counts, both gate blocks, the `DEAD_TRANSITION` line, the patch path, the proposed commit messages, `/dgf-evolve`'s question and the override. If time allows, try A′ (`listBox` + `card`, `gridColumns`) with `get_component_examples` as the reference and keep or drop it. Then restore the folder from the tarball and run `reset.sql`. **Files:** `docs/demo/splitbill/balances.sql`; the captured outputs in the scratchpad. **Evidence:** `/balances` rendered with the expected numbers; two gate blocks, `pass` then `fail` with `DEAD_TRANSITION`; every skill prompt's answer recorded.
  - **Done 2026-10-04, with one deviation:** the pipeline was rehearsed through the scripts each skill calls — `inventory_root.py`, `check_plan.py`, `validate_config.py`, `resolve_components.py`, `validate_process.py`, `verify_gate.py` (pass, then fail with `DEAD_TRANSITION`, then pass), `check_patches.py`, `check_override.py` (accepted, then `OVERRIDE_FORBIDDEN`) — with the plan, patch and override written to their formats by hand, because this session cannot drive an interactive Claude Code session. The skills' own prompts and questions are first exercised in Task 9. A′ was not tried. `/balances` rendered Ana 30.00, Chloe 0.00, Ben −30.00 at 393 × 852 with no restart.

### Phase 2: The guide

- [x] Task 5: Write `docs/demo/prep-checklist.md` (depends on 3). Sections: *Variables* (`DGF`, `PLUGIN`, `APP`, `COMPOSE`, set once); *Decision* (S1 or F, the evidence from Task 3); *Night before* — stack up, the plugin loads (`claude --plugin-dir "$PLUGIN" -p "/dgf-doctor"` from a shell with the `.venv` active), the skill names as the terminal shows them, the override files copied, `SPLITBILL_APP` in `.env`, `reset.sql` run, the folder restored to `.git` + `docs/application.json`, browser tabs, terminal layout, editor windows; *T-30* — `docker ps` healthy, `/health/live`, the catalogue loads, one e-service run, the folder and the database clean, context cleared; *Reset recipe* for repeating a rehearsal (tarball, `reset.sql`, `docker compose … up -d`, `docker restart splitbill-api`); *Never on screen*. **Files:** `docs/demo/prep-checklist.md`. **Evidence:** every command runs on this machine (Task 9 ticks each line); no absolute path in a fenced block.
- [x] Task 6: Write `docs/demo/interview-guide.md` — the frame, the opening, Act 1 and Act 2 (depends on 2, 3). The story in three sentences; how to read the act tables and the quarter-hour checkpoints; Act 0; the opening with the two sentences and the architecture picture; Act 1's six rows with the exact file and `title` attribute edited and its revert; Act 2's eight rows with the exact `/dgf-scaffold` prompt, the three survey answers, the `DEFAULT:` lines to expect, the `TARGETS:` and `WROTE:` counts, the two files to open side by side, the two Terminal 2 commands and their printed lines, the sign-in and the data to enter in order, the phone view steps. Each row carries its fallback. **Files:** `docs/demo/interview-guide.md`. **Evidence:** every quoted output line is copied from Task 2's and Task 3's runs; the minute marks of the opening, Act 1 and Act 2 sum to 42.
- [x] Task 7: Act 3, the close, the extensions, the timeline, the fallbacks, the Q&A crib and "What to expect at the end" (depends on 4, 6). Act 3's eleven rows with the exact `/dgf-plan fast` prompt, the plan header and tasks, what `/dgf-implement` writes for each (the `rawsql` data source, the `dataTable` page, the retitled states and the `Resend` transition — quoted), the verify block's fields to point at, the break C edit (file, line, the misspelt target), the `DEAD_TRANSITION` line, the `/dgf-fix` flow and the patch path, the commit messages, `/dgf-evolve`'s question and the override; the close with the numbers and the install lines; the six extension inserts as rows; the 60/75/120 table, the checkpoints and the cut lines; the fallback section; the Q&A crib with one-line answers citing an ADR or knowledge file each; the "What to expect at the end" section as above with the real counts. **Files:** `docs/demo/interview-guide.md`. **Evidence:** the minute marks sum to 75, and the cuts and inserts to 60 and 120; every fallback names the command to type.
- [x] Task 8: Write `docs/demo/cheat-sheet.md` (depends on 7): one page — every command, prompt, survey answer and data value in order with its minute mark, checkpoint and cut line, the extensions marked as such, nothing else — printable, kept on the second screen. **Files:** `docs/demo/cheat-sheet.md`. **Evidence:** it fits one page at the presenter's font size; its commands are byte-identical to the guide's.

### Phase 3: Rehearsal and links

- [ ] Task 9: Rehearse against the clock (depends on 8). From the reset state, run the 75-minute core once end to end with a stopwatch, following the cheat sheet only; tag the checkpoints in the generated repo as each step completes; replace every remaining placeholder in the guide and the cheat sheet with the run's text; record the skill names as shown under `--plugin-dir`; time each extension insert on its own; write a *Rehearsal log* section at the end of the guide — what failed, what changed, which fallback was chosen, the stopwatch times at each checkpoint. Reset with the recipe. If time remains, run the 60-minute cut once. **Files:** `docs/demo/interview-guide.md`, `docs/demo/cheat-sheet.md`, `docs/demo/prep-checklist.md`. **Evidence:** the run finishes inside 75 minutes with the stopwatch time at each checkpoint written into the log; the five tags exist in the generated repo; each insert has a measured duration.
  - **Partly done 2026-10-04.** Done: Act 2's terminal commands timed from the reset state, the seed script run twice, and the reset recipe run as written, all recorded in the guide's Rehearsal log. **Open:** the stopwatch run of the whole core through the skills in an interactive Claude Code session, the skill names as the terminal shows them, and the timed extensions. This session cannot drive an interactive session; the presenter runs it the night before, following the cheat sheet.
- [x] Task 10: Link and check (depends on 9). Add an *Interview Demo* row to the Documentation table in `README.md`, add `docs/demo/` to the Project Structure tree and the Documentation table in `AGENTS.md`, run `bash tools/check-dual-schema-docs.sh` (sections 1 and 4 sweep `docs/demo/*.md`) and `doctor.py` once more. **Files:** `README.md`, `AGENTS.md`. **Evidence:** the docs check CLEAN; the doctor `pass`.
