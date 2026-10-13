# zamconnect-integration

Claude Code skills that build and check integrations on the
[ZamConnect](https://dev.azure.com/zambiazigs/zambiazigs/_git/ZamConnect) gateway. The skills cover the
whole job: create the tenant project, connect it to the agency's system, add shared e-Services, write tests,
audit the result, and produce the API documents delivered to the client.

This page explains the ideas behind a ZamConnect integration and the steps to create one. For every flag,
check and output of each skill, see [REFERENCE.md](REFERENCE.md).

## Contents

- [How a ZamConnect integration works](#how-a-zamconnect-integration-works)
- [Before you start](#before-you-start)
- [Install the plugin](#install-the-plugin)
- [The skills](#the-skills)
- [Create an integration, step by step](#create-an-integration-step-by-step)
- [When the agency needs only shared e-Services](#when-the-agency-needs-only-shared-e-services)
- [Other tasks](#other-tasks)
- [Troubleshooting](#troubleshooting)
- [Learn more](#learn-more)
- [Contributing](#contributing)

## How a ZamConnect integration works

```
consumer ──► Gateway (YARP) ──/t/<slug>/…──► Tenant service ──► Agency system (REST or SOAP)
   │              │                               │
gateway user   route, cluster, scope        calls back into the gateway
(Basic auth)   (stored in MongoDB)          for shared e-Services (NIR, PACRA, ZRA…)
```

ZamConnect is a set of .NET services behind one API gateway. Each government agency gets its own service,
called a **tenant**. Consumers never call a tenant directly. They call the gateway, which checks who they
are and forwards the request to the right tenant.

### Tenant

A tenant is an ASP.NET Core service in `src/Tenants/<Tenant>/`, one per agency system. It has its own
`Program.cs`, `Dockerfile`, settings and Azure DevOps pipeline, and it is deployed on its own as the
Kubernetes service `core-<slug>`. A tenant does three things:

- It exposes a clean, documented API to consumers.
- It calls the agency's own system (the **upstream**) and translates between the two.
- Where needed, it calls other agencies' data back through the gateway.

Inside a tenant you will find:

| Folder | What it holds |
|---|---|
| `Endpoints/` | The **client** for each upstream system. A REST client derives from `RestEndpoint`, a SOAP client from `SoapEndpoint`. Both come from the shared Core libraries |
| `Models/<System>/` | The request and response shapes of the upstream system |
| `Mapper/` | Code that converts upstream shapes into the public shapes the tenant returns |
| `Modules/` | **Carter modules**: the routes the tenant exposes, such as `GET /employers/{id}`. Some older tenants use MVC controllers instead |

### Names

One agency has several names, and the skills use each in a fixed place:

| Name | Example | Used for |
|---|---|---|
| Tenant name | `PQPS` | Folder, project, namespace. PascalCase as the folder is spelled |
| Slug | `pqps` | The tenant name in lower case with no separators. The gateway path `/t/pqps/…`, the service `core-pqps` and the scope `pqps` |
| Cluster id | `PQPS` | The tenant name in upper case. Names the tenant's service in the gateway |
| Agency code | `CCPC` | A virtual tenant's name (see below), which has no folder under `src/Tenants/` |

The gateway route often differs from the tenant name (for example `mcti/zabs`). The live list of routes is in
`docs/zamconnect-test-routes.md` in the ZamConnect repository. Check it before you pick a name.

### Gateway: route, cluster, scope, gateway user

The gateway is built on YARP, a .NET reverse proxy. It is configured with four kinds of records, all stored
in the gateway's MongoDB:

| Record | What it is | Example |
|---|---|---|
| **Route** | A public path pattern and the cluster it goes to | `t_pqps`: `/t/pqps/{**url}` → `PQPS` |
| **Cluster** | The address of a tenant service | `PQPS` → `http://core-pqps` |
| **Scope** | A permission attached to a route | `pqps` |
| **Gateway user** | A consumer's login (Basic authentication). It holds the scopes it may call | A consumer system that holds `pqps` |

A consumer calls `https://api.test.gsb.gov.zm/t/pqps/hub/pesticides`. The gateway checks that the user holds
the route's scope, then forwards the request to `core-pqps`. The tenant only sees `/hub/pesticides`.

The skills never touch a real gateway. They write the route, cluster and scope into a file,
`GATEWAY-CONFIG.md`, and an administrator imports it into each environment.

### Provide and consume

Each endpoint a tenant exposes is one of two kinds:

- **Provide.** The data comes from the agency's own system. The tenant is the agency's front door.
- **Consume.** The data comes from another system reached back through the gateway, such as a national
  registry. The tenant signs in to the gateway with its own gateway user to fetch it.

The difference matters for the delivery documents, which describe the two kinds separately.

### Shared e-Services

Some national systems are used by many agencies: NIR (persons by NRC), NBR/PACRA (companies), ZRA (tax
clearance), ZDI, DOC and others. Core already has a ready client for them, `EServicesShared`, which calls
them through the gateway. A tenant that needs them doesn't write a new client; `/integrate-shared` wires the
existing one in. `/integrate-shared <Tenant> --list` prints every available operation.

### Virtual tenant

Some agencies have no system of their own and only need shared e-Services that the GOVZM tenant already
serves. Such an agency gets a **virtual tenant**: gateway routes under its own slug that point at GOVZM.
There is no project, no code, no pipeline and no deployment, only a `GATEWAY-CONFIG.md` in
`src/VirtualTenants/<CODE>/`. If the agency later needs its own system or contract, it becomes a real tenant.

### Configuration and secrets

Each tenant has two settings files, and both are committed to git:

- `appsettings.json` is used in DEV, STG and PROD. It holds **placeholders** instead of real values, such as
  `"BaseUrl": "__Endpoints.PqpsApi.BaseUrl__"`. At deploy time the pipeline replaces each placeholder with
  a variable from the environment. A placeholder without a variable fails the deploy.
- `appsettings.Development.json` is used for local runs and tests. Credentials stay placeholders there too.

Each upstream client reads its own section: `Endpoints:<ClientClass>` for REST and
`SoapEndpoints:<ClientClass>` for SOAP. The section name must match the class name. A missing section
doesn't break the build; the tenant crashes when it starts.

Real credentials never go into git or into a skill. The only place for them is `appsettings.local.json`,
which git ignores. You need it only for tests that call the real upstream.

### Handoff files and the administrator

You work only on your machine. Everything that has to happen in DEV, STG and PROD is done by an
administrator, from files the skills write for them:

| File | In git | What the administrator does with it |
|---|---|---|
| `.azure/tenant.azure-pipelines.<slug>.yaml` | Yes | Registers the Azure DevOps pipeline |
| `src/Tenants/<Tenant>/ENVIRONMENT-VARIABLES.json` | No | Creates every listed variable in each environment and fills in its value |
| `src/Tenants/<Tenant>/GATEWAY-CONFIG.md` | No | Imports the route, cluster and scope into each gateway and grants the scope to consumers |

The two files that are not in git are listed in `.gitignore`. Send them to the administrator directly.
ZamPass and RA (Registration Authority) clients are also registered by the administrator, by hand.

### Delivery documents

Each integration is delivered with a document package in `src/Tenants/<Tenant>/Deliverables/`:

| File | For whom |
|---|---|
| `(t)` Tenant API Specification (Word), OpenAPI JSON, Postman collection | The whole API: every endpoint |
| `(p)` Provider API Specification (Word) | The endpoints the tenant provides |
| `(c)` Consumer API Specification (Word) | The endpoints the tenant consumes |

The documents are generated from the tenant's code: route summaries, `///` comments and response types. Good
comments in the code mean good documents.

## Before you start

**Access**

- The ZamConnect repository, cloned on your machine.
- This plugins repository (see [Install](#install-the-plugin)).
- Claude Code (CLI or the VS Code extension).

**Tools**

| Tool | Needed for |
|---|---|
| .NET 10 SDK | Every skill. Run `dotnet tool restore` once in the ZamConnect repository |
| Docker Desktop, running | Image builds and the local gateway test. Without it those checks report `skipped` |
| Git for Windows (Git Bash) | Every skill runs shell commands |
| Python 3.12 or later, on `PATH` as `python` | The document generator. Then `python -m pip install python-docx` |
| Node.js | The Postman collection (downloads `openapi-to-postmanv2` from npm on first use) |
| Microsoft Word for Windows | Exact page numbers in the Word documents. Without it they are estimated and not shippable |
| PowerShell allowed to run local scripts | The document generator. Once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |

The document generator works only on Windows.

**For the integration itself**

- The agency's code and full name (for example `PQPS`, "Plant Quarantine and Phytosanitary Service").
- A description of the agency's system: a Postman collection, an OpenAPI/Swagger file, a SOAP WSDL, a base
  URL, or a Word or PDF document. A Word or PDF source also needs the `convert-documents-to-markdown` skill.
- Which operations the tenant should expose, and whether it needs shared e-Services.

## Install the plugin

The plugin is installed from a local copy of this repository.

1. Clone the repository once, into a folder that will stay where it is:

   ```bash
   git clone https://github.com/andrian-org/claude-plugins.git C:/Workspaces/claude-plugins
   ```

2. Add the folder as a marketplace and install the plugin. Pass the repository root, not the plugin
   folder:

   ```bash
   claude plugin marketplace add C:/Workspaces/claude-plugins
   claude plugin install zamconnect-integration@dotgov
   ```

3. Restart Claude Code (in VS Code, reload the window), then check with `claude plugin list`.

Claude Code reads the plugin straight from that folder. If you move or rename it, add it again.

To get a newer version, run `git pull` in the folder. The change takes effect in the next session, or at
once after `/reload-plugins`.

<details>
<summary>Load the plugin only inside the ZamConnect repository</summary>

From the ZamConnect root, add the marketplace at `local` scope:

```bash
claude plugin marketplace add C:/Workspaces/claude-plugins --scope local
```

This writes `.claude/settings.local.json`, which is not committed. Enable the plugin in the same file:

```json
{
  "extraKnownMarketplaces": {
    "dotgov": {
      "source": { "source": "directory", "path": "C:\\Workspaces\\claude-plugins" }
    }
  },
  "enabledPlugins": { "zamconnect-integration@dotgov": true }
}
```

</details>

<details>
<summary>Replace an install that was added from a URL</summary>

If `claude plugin marketplace list` shows `dotgov` with a Git source, remove it, then add the folder:

```bash
claude plugin marketplace remove dotgov
claude plugin marketplace add C:/Workspaces/claude-plugins
claude plugin install zamconnect-integration@dotgov
```

</details>

## The skills

Run every skill from the ZamConnect repository root, the folder that holds `src/ZamConnect.sln`. Type `/`
in Claude Code to see them. They may also be listed with the plugin prefix, for example
`/zamconnect-integration:tenant-init`.

| Skill | What it does |
|---|---|
| `/tenant-init <Tenant>` | Creates the tenant project and registers it everywhere: solution, Docker Compose, Azure pipeline, gateway package. Then starts the guided flow |
| `/tenant-pipeline <Tenant>` | Runs the whole flow below as one guided chain. You can stop at any step and resume later |
| `/tenant-integration <Tenant>` | Connects the tenant to the agency's system: client, models, mapper, routes and settings |
| `/integrate-shared <Tenant>` | Adds shared e-Services (NIR, PACRA, ZRA…) to a tenant, or creates a virtual tenant |
| `/tenant-tests <Tenant>` | Creates the test project and endpoint tests, then runs them |
| `/tenant-audit <Tenant>` | Checks the tenant for anything missing or wrong, and calls it through a local gateway |
| `/tenant-deliverables <Tenant>` | Generates the Word API specifications, the OpenAPI JSON and the Postman collection |
| `/payment-callback <CODE>` | Forwards ZamPay payment callbacks for an agency through GOVZM. Separate from the tenant flow |

The `tenant-deliverables-builder` agent runs `/tenant-deliverables` in its own context, so its long logs stay
out of your conversation.

Every skill works the same way:

- It asks its questions as a menu. Each question also has a flag, so you can answer up front.
- Before it writes anything, it shows a review: the files it will write, the routes, and the full command
  that repeats the run. You choose `Apply`, `Adjust` or `Cancel`.
- `--help` prints the skill's arguments and examples. `--dry-run` shows the plan and writes nothing.
- It works only on your machine and the local Docker stack. It never commits, pushes or touches a shared
  environment.

## Create an integration, step by step

The recommended way is the **guided flow**: start with `/tenant-init`, choose `Guided`, and the plugin takes
you through steps 1 to 6 below. Before each step it asks whether to run it:

| Option | What it does |
|---|---|
| `Proceed` | Runs the step with the defaults shown in the option |
| `Customize…` | Asks the step's extra questions first |
| `Skip` | Moves on without running the step |
| `Stop` | Ends the flow. Continue later with `/tenant-pipeline <Tenant> --resume` |

`/tenant-pipeline <Tenant> --status` shows what has run and what is left.

### 0. Prepare

1. Start Docker Desktop.
2. In the ZamConnect repository, create a branch, for example `feature/pqps-integration`.
3. Look up the agency in `docs/zamconnect-test-routes.md`. If it already has a route, ask your lead before
   you go on.
4. Put the agency's API description where the skills find it: the repository root or `postman collections/`.
   After step 1, its permanent place is `src/Tenants/<Tenant>/Deliverables/Integration Requests/`. You can
   also give a URL or path when asked.
5. Open Claude Code in the ZamConnect root.

### 1. Create the tenant

```
/tenant-init PQPS
```

Answer the questions: project style (keep Carter), what the tenant integrates with (REST, SOAP, shared
e-Services), its full name, and `Guided`. Check the review, then choose `Apply`.

You get `src/Tenants/PQPS/` with an empty, runnable service, plus its registrations: the solution entry, the
Docker Compose service `core-pqps`, the Azure pipeline file and the two handoff files. The skill confirms that
the project builds, that the Docker image builds, and that the service answers `/health/live`.

### 2. Connect the agency system

The guided flow offers the API descriptions it found. Pick one. The skill works out whether it is REST or
SOAP and how it authenticates, then shows the endpoints it will expose.

You get the upstream client, the models, the mapper, the Carter module with the public routes, the settings
section in both settings files, the new placeholders in `ENVIRONMENT-VARIABLES.json`, and the HTTP methods in
`GATEWAY-CONFIG.md`. The skill also adds the summaries and comments the documents need, then builds.

If the agency has more than one system, the skill offers to add the next one.

### 3. Add shared e-Services (optional)

Choose `Skip` unless the tenant must also return data from national registries. Otherwise pick the groups
(NIR, PACRA, ZRA…). The skill adds a module that calls `EServicesShared`, and a `Gateway` settings section
with the tenant's own gateway user. The report lists the scopes that user needs; give the list to the
administrator.

### 4. Write tests

The skill creates `src/Tests/PQPS.Tests/`. The tests start the tenant in memory and replace the agency system
with a fake, so they run anywhere. They cover the normal answer, upstream errors, and what the tenant sends
upstream. The skill runs them. If one fails, it asks whether to fix the tenant, fix the test, or stop.

### 5. Audit

The audit runs without a question. It checks that nothing is missing: registrations, matching names,
settings sections, no real credentials in committed files, tests and documents. It then loads the tenant's
gateway package into a local gateway in Docker and calls the tenant through it, as the local test user
`testPQPS` with password `test`.

Read the report. A `warn` that the agency system can't be reached is normal: a local container usually can't
reach it. To repair what the audit can fix by itself, run `/tenant-audit PQPS --fix`.

### 6. Generate the documents

The skill builds the OpenAPI JSON, the `(t)`, `(p)` and `(c)` Word specifications and the Postman collection
in `src/Tenants/PQPS/Deliverables/`, then runs its quality checks. If a route has no description or comment,
the report lists it and offers `Fix them now, then re-render`.

Don't open a delivered Word document and save it: Word rewrites its dates. Generate it again instead.

### 7. Finish

The flow ends with a summary of every step and the administrator's task list.

1. Review `git status`, commit the code, and open a pull request. The handoff files are not in git.
2. Send `ENVIRONMENT-VARIABLES.json` and `GATEWAY-CONFIG.md`, plus the scope list from step 3, to the
   administrator. The administrator registers the pipeline, creates the variables, imports the gateway
   package, grants the scopes and registers any ZamPass or RA client.
3. After the deploy, test through the test gateway with the generated Postman collection.

### Running the steps by hand

To run one step on its own, use the skills directly. `--no-pipeline` stops `/tenant-init` from starting the
guided flow:

```
/tenant-init PQPS --integrates soap --no-pipeline
/tenant-integration PQPS --source "src/Tenants/PQPS/Deliverables/Integration Requests/pqps.wsdl"
/integrate-shared PQPS            # only when shared e-Services are needed
/tenant-tests PQPS
/tenant-audit PQPS
/tenant-deliverables PQPS
```

Keep this order. Tests are written from the routes that exist, and the documents from the final code, so
running them earlier gives stale results.

## When the agency needs only shared e-Services

Run `/tenant-init <CODE>` and choose only `Shared e-Services`. The skill offers a virtual tenant. Accept it,
and the guided flow runs three steps:

1. `/integrate-shared` writes the routes from `/t/<slug>/…` to GOVZM into
   `src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md`. Pick all operations or only some.
2. `/tenant-audit` checks the routes against GOVZM and calls each one through the local gateway.
3. `/tenant-deliverables` documents the operations the routes reach.

Send `GATEWAY-CONFIG.md` to the administrator, who imports it and creates the agency's gateway user.

## Other tasks

| Task | What to run |
|---|---|
| Add an endpoint or a system to an existing tenant | `/tenant-integration <Tenant>`, then `/tenant-pipeline <Tenant> --resume` to re-run the tests, audit and documents it made stale |
| Check an existing tenant | `/tenant-audit <Tenant>`, or `/tenant-audit --all` for every tenant |
| Regenerate the documents after a contract change | `/tenant-deliverables <Tenant> --version 1.1`. The previous version moves to `Deliverables/Archive/` |
| See the shared e-Services catalogue | `/integrate-shared <Tenant> --list` |
| Forward ZamPay callbacks to an agency | `/payment-callback <CODE>` |

## Troubleshooting

| Problem | What to do |
|---|---|
| The skills don't appear after `/` | Check `claude plugin list`, then restart Claude Code or run `/reload-plugins`. Delete any copy of the same skill in `~/.claude/skills/`: two skills with one name collide |
| Many permission prompts | Expected: the skills run shell, `dotnet` and `docker` commands. Approve them, or allow them in your settings |
| `missing --source` | `--auto` can't guess the API description. Run the guided flow, or pass `--source <path or URL>` |
| Docker checks report `skipped` | Start Docker Desktop and run `/tenant-audit <Tenant>` again |
| Port 8081 or 10080 in use | The local gateway test needs both. Stop whatever uses them |
| Audit `warn`: upstream unreachable | Normal locally. The tenant answered; only the agency system was out of reach |
| `401` or `403` through the gateway | The gateway user lacks the route's scope. Locally the audit creates the test user; in an environment, ask the administrator |
| `SyntaxError` from a `.py` script | Python is older than 3.12 |
| `running scripts is disabled on this system` | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once |
| Page numbers in the documents are estimated | Word is missing or blocked by a dialog. Open Word once, close any dialog, then generate again |
| The tenant crashes at start with a missing settings section | An `Endpoints:<Name>` or `SoapEndpoints:<Name>` section is missing. `/tenant-audit <Tenant> --only config` shows which one |

## Learn more

- [REFERENCE.md](REFERENCE.md): every flag, every audit check, the local gateway test, the document package
  in detail, pipeline state, and known limitations.
- `/<skill> --help`: one skill's arguments and examples.
- [references/zamconnect-conventions.md](references/zamconnect-conventions.md): ZamConnect rules the skills
  follow: placeholder naming, error-to-HTTP mapping, virtual tenant routes.
- In the ZamConnect repository: `docs/getting-started.md`, `docs/architecture.md`,
  `docs/configuration.md` and `docs/zamconnect-test-routes.md`.

## Contributing

The plugin lives in this repository under `plugins/zamconnect-integration/`.

- Bump `version` in `.claude-plugin/plugin.json` with every change (SemVer), so you can tell which version
  produced a document or a tenant.
- Validate both manifests from the repository root before you open a pull request:

  ```bash
  claude plugin validate .
  claude plugin validate plugins/zamconnect-integration
  ```

- Try a change without installing: `claude --plugin-dir plugins/zamconnect-integration`, then
  `/reload-plugins` after each edit. `claude plugin details zamconnect-integration@dotgov` shows the
  plugin's always-on token cost.
- Tag a release with `claude plugin tag plugins/zamconnect-integration`.
- The `description` in a skill's `SKILL.md` front matter is all Claude sees when it decides to load the
  skill. Write it as the phrases people actually type.
- Keep `SKILL.md` short and put detail in `references/`. Every session pays for what is always loaded.
- Never commit tokens, certificates (`.pfx`, `.jks`, `.pem`), tenant credentials or client documents.
