# zamconnect

Tenant tooling for the [ZamConnect](https://dev.azure.com/zambiazigs/zambiazigs/_git/ZamConnect)
gateway: scaffolding, integration, drift auditing, tests, and the contractual delivery documents.

Run every skill from the ZamConnect repository root — the directory holding `src/ZamConnect.sln`.

## Install

Run these in a **normal interactive terminal**, not inside a Claude Code session — Git Credential
Manager may need to prompt for Azure DevOps sign-in:

```bash
claude plugin marketplace add https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins
claude plugin install zamconnect@dotgov
```

Restart Claude Code, then confirm with `claude plugin list`.

If the `add` fails with `unable to get password from user`, you are running non-interactively. Do
`git clone <url>` once by hand so GCM caches the credential, then retry. Access is controlled by
the `dotgov` project's repo permissions — no extra PAT is needed if you already clone ZamConnect.

### Provision it for the whole team

Declare the marketplace in the ZamConnect repo itself so teammates get the plugin with no setup:

```bash
claude plugin marketplace add https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins --scope project
```

Then add `zamconnect@dotgov` to `enabledPlugins` in the generated `.claude/settings.json` and
commit it:

```json
{
  "extraKnownMarketplaces": {
    "dotgov": {
      "source": {
        "source": "git",
        "url": "https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins"
      }
    }
  },
  "enabledPlugins": ["zamconnect@dotgov"]
}
```

### Updating

`claude plugin update zamconnect` (restart required).

## Skills

| Skill | What it does |
|---|---|
| `/tenant-init <Tenant>` | Scaffolds `src/Tenants/<Tenant>/` from the standard boilerplate (Carter + Serilog + OpenTelemetry + Prometheus + health checks), wires it into `ZamConnect.sln`, and verifies it builds. Boilerplate only — no modules, models or mappers. Then drives the rest of the chain below interactively, gating each step |
| `/tenant-integration <Tenant>` | Builds the integration surface of an existing tenant: the upstream `RestEndpoint`/`SoapEndpoint` client, models, mappers, and the routes the tenant exposes. Takes a Postman collection, OpenAPI spec, REST base URL, WSDL or prose API docs as the source |
| `/integrate-shared [<Tenant>]` | Exposes shared e-Services (NIR, NBR/PACRA, DOC, SRS, ZDI, NLR, ZDA, NAIR, ZRA, MOH) on a tenant by wiring `EServicesShared` through the gateway, driven by an interactive endpoint menu |
| `/tenant-audit [<Tenant>\|--all]` | Read-only drift audit: registration in solution/pipeline/compose, slug consistency across compose/Helm/gateway, `Endpoints:<Name>` config for every client, leaked credentials, and presence of docs, Postman collection and tests. `--fix` repairs the fixable ones |
| `/tenant-tests <Tenant>` | Scaffolds `src/Tests/<Tenant>.Tests/` with a `WebApplicationFactory`, a recording mock upstream handler, and endpoint tests over HTTP. `--live` adds an `[Explicit]` staging fixture |
| `/tenant-deliverables <Tenant>` | Generates the delivery package — OpenAPI JSON, the (c)/(p)/(t) Word API Specifications and the Postman collection — into `src/Tenants/<Tenant>/Deliverables/`. Documents only; never modifies tenant code |

## Agents

| Agent | Use |
|---|---|
| `tenant-deliverables-builder` | Runs the full `tenant-deliverables` package build for a named tenant in its own context, with every gate passing. Write-restricted to `Deliverables/` |

## Prerequisites

Only `/tenant-deliverables` and `tenant-deliverables-builder` need more than the .NET SDK:

- **.NET 10 SDK** — all skills (`dotnet build`, `dotnet tool run swagger`)
- **Python 3.9+** with `python-docx` — the document renderers under `skills/tenant-deliverables/scripts/`
- **Node.js** — `npx openapi-to-postmanv2`, invoked by `openapi_to_postman.ps1`
- **Windows PowerShell** — the Postman conversion step

```
pip install python-docx
```

## Order of execution for a new tenant

Run the skills in this order. Each step assumes the previous one has completed.

| # | Skill | Why it sits here |
|---|---|---|
| 1 | `/tenant-init <Tenant>` | Nothing else can run until `src/Tenants/<Tenant>/` exists and builds |
| 2 | `/tenant-integration <Tenant>` | Needs the scaffold; produces the upstream client and the exposed routes |
| 3 | `/integrate-shared <Tenant>` | **Optional** — only when the tenant also republishes shared e-Services (NIR, PACRA, ZRA, …) |
| 4 | `/tenant-tests <Tenant>` | Fixtures are generated from the routes that exist after steps 2–3 |
| 5 | `/tenant-audit <Tenant>` | Catches what a green build hides: pipeline/compose registration, slug mismatches, missing `Endpoints:<Name>` config, leaked credentials |
| 6 | `/tenant-deliverables <Tenant>` | **Last.** The deliverables are generated from the final API surface; running it earlier ships a stale specification |

```
/tenant-init PQPS
/tenant-integration PQPS --source <wsdl-or-openapi-url>
/integrate-shared PQPS            # only if shared e-Services are needed
/tenant-tests PQPS
/tenant-audit PQPS
/tenant-deliverables PQPS --route /t/pqps --version 1.0
```

### Interactive mode

`/tenant-init` drives this chain itself. After the scaffold it asks before each remaining
step — **Proceed** (run the skill now), **Skip** (leave it, continue) or **Stop** (end the chain) —
and closes with a summary of what ran plus the commands to resume anything left. Answering a gate
with free text instead of an option passes it to that step (a `--source` URL, a route override).

Step 3 defaults to Skip. Steps 4 and 6 are offered only when step 2 or 3 actually ran — there is
nothing to test or document on a bare scaffold.

- `--no-pipeline` — stop after the scaffold, as before
- `--auto` — run steps 2, 4, 5 and 6 with no gates

Notes:

- Steps 2 and 3 are independent of each other — run either or both, in any order, as long as both precede step 4.
- Re-running an earlier step (a new endpoint, a changed DTO) invalidates steps 4–6; re-run tests, audit and docs after it.

## Contributing

The plugin lives in the [`dotgov-claude-plugins`](https://dev.azure.com/dotgov/Core/_git/dotgov-claude-plugins)
marketplace repository, under `plugins/zamconnect/`.

Bump `version` in `.claude-plugin/plugin.json` with every change (SemVer), then validate **both**
manifests before opening a PR:

```bash
claude plugin validate .
claude plugin validate plugins/zamconnect
```

Test locally as a directory marketplace before pushing:

```bash
claude plugin marketplace add /path/to/dotgov-claude-plugins
claude plugin install zamconnect@dotgov
claude plugin details zamconnect@dotgov      # check always-on token cost
```

Tag the release with `claude plugin tag plugins/zamconnect`.

Two rules that matter more than the rest:

- **The `description` in `SKILL.md` frontmatter is the only thing Claude sees when deciding whether
  to load a skill.** Write it as trigger phrases people actually type. Review descriptions in PRs
  more carefully than implementations — a good skill with a vague description never fires.
- **Never commit tokens, `.pfx`/`.jks`/`.pem` files, tenant credentials or client document
  content.** Skills acquire credentials at runtime and cache them outside the repo.

Keep `SKILL.md` lean and push detail into `references/` files that load only when needed — every
session pays the always-on cost. If you also keep a copy of a skill in `~/.claude/skills/`, delete
it; two registrations of the same name collide.
