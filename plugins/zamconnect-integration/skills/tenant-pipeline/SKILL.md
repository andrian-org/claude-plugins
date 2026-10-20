---
name: tenant-pipeline
description: Guided end-to-end onboarding of a ZamConnect tenant — scaffold, integration, shared e-Services, tests, audit and delivery documents — as one gated chain with a saved state, so a stopped run can be resumed and a re-run step marks what it invalidated. A virtual tenant (gateway routes onto another cluster, no project) gets a shorter chain: shared e-Services routes, then the audit. A virtual tenant that needs an integration its routes and scope can't carry is promoted: scaffolded as a real tenant, its forwarded operations re-implemented with the same contract, then integrated, tested, audited and documented as usual. Use when the user says "onboard <Tenant>", "extend virtual tenant <CODE> with <System>", "promote <CODE>", "run the whole tenant pipeline", "continue/resume <Tenant>", "what's left for <Tenant>", "re-run tests and docs for <Tenant>", or types /tenant-pipeline.
argument-hint: "<TenantName> [--from init|integration|shared|tests|audit|deliverables] [--resume] [--promote] [--status] [--source <url|path>...] [--shared-source <SYS>...] [--all] [--auto] [--dry-run] [--help]"
allowed-tools: Read Write Glob Grep Bash(ls *) Bash(grep *) Bash(find *) Bash(mkdir *) Bash(git config *) AskUserQuestion Skill
disable-model-invocation: false
---

# ZamConnect Tenant Pipeline

Runs the six tenant skills in order, one gate per step, and keeps the run in a state file so it
can be stopped and resumed. The pipeline owns **order, conditions, state and the closing
summary**. Each step skill owns its own gate and questions.

Read `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md` first. Its gate, gate mode, state
file and rules R1–R14 are assumed below.

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`).

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Tenant folder name. Required. When omitted, asked first from the contract's Missing arguments menu (R13), with tenants that have a state file first and a `New tenant` option that asks for the name in plain text and starts at step 1. `--auto` stops with `missing <TenantName>`. The pipeline always passes it on, so no step asks it again |
| `--from <step>` | Start at this step. Everything before it is left as it is in state |
| `--resume` | Start at the first `stale` step, then the first `pending` / `failed` one. This is the default when a state file exists and neither `--from` nor `--status` is given |
| `--promote` | The tenant is a virtual tenant and now needs an integration its routes can't carry: run the promotion chain (below) |
| `--status` | Print the state table and the resume commands, then stop. Asks nothing, writes nothing |
| `--source <url\|path>` | Integration source for step 2; repeatable. Each one becomes an `answers.integrations` entry `{ "sources": [...] }`. A database source keeps its `db=<path>` form, a GraphQL one `graphql=<…>` |
| `--shared-source <SYS>` | Shared e-Services system for step 3 (`NIR`, `NBR`, `ZRA`, …); repeatable. Becomes `answers.sharedSources`, and step 3 gets one `--source <SYS>` per code |
| `--all` | Every shared operation for step 3. Becomes `answers.sharedAll: true`, and step 3 gets `--all` |
| `--auto` | No gates. Every step runs with its `(Recommended)` defaults and is given `--auto`. Missing sources are checked before any step runs (see Running). Stops on the first required input that has no default (R10) |
| `--dry-run` | Passed to every step. Plans are printed and nothing is written |
| `--help` | Print the arguments and examples, then stop. Asks and writes nothing (R14) |

## The chain

| # | Step key | Skill | Offered when | Arguments passed |
|---|---|---|---|---|
| 1 | `init` | `tenant-init` | `src/Tenants/<T>/` does not exist | The [step 1 arguments](#step-arguments) |
| 2 | `integration` | `tenant-integration` | always. Under `--auto`, `skipped` with the reason "no protocol or source" when state holds neither a `rest` / `graphql` / `soap` / `db` member in `integrates` nor an `integrations` source | `<T> --gate 2/6`, plus `--protocol` with the `rest` / `graphql` / `soap` / `db` members of the intake answer `integrates`, in that order: `--protocol rest`, `--protocol rest,soap`, `--protocol graphql,db`, … With none of them (only `shared` / `unknown`), no `--protocol` |
| 3 | `shared` | `integrate-shared` | always. `--recommend proceed` when `integrates` contains `shared`, otherwise `--recommend skip`. On a controllers tenant without Carter the skill recommends `Skip` itself, and `Proceed` adds Carter | `<T> --gate 3/6`, plus the [shared source flags](#step-arguments) |
| 4 | `tests` | `tenant-tests` | the tenant exposes at least one route (see below) | `<T> --gate 4/6` |
| 5 | `audit` | `tenant-audit` | always. It edits no repo file, so it has **no gate**. It still builds local images and writes the tenant's gateway config and test user to the local Docker `mongo` (Checks 8–9) | `<T> --report-only` (also under `--auto`) |
| 6 | `deliverables` | `tenant-deliverables` | the tenant exposes at least one route | `<T> --gate 6/6 --route <route>` |

### Step arguments

Step 1 gets exactly these arguments:

- always `<T> --no-pipeline`. In `tenant-init`, `--no-pipeline` always wins over `--auto`: it scaffolds and never starts this chain a second time;
- `--auto` and `--dry-run` when the pipeline has them;
- `--source`, `--shared-source` and `--all` as given to the pipeline;
- `--controllers`, `--full-name` and `--integrates` from state, when state holds them;
- never `--gate`. Step 1 has no gate: its intake and review are its questions.

Step 3 gets the shared source answers from state: one `--source <SYS>` per `answers.sharedSources` code, and `--all` when `answers.sharedAll` is `true`. With neither, step 3 asks for the groups in its own gate.

The virtual and promotion chains use the same lists. The promotion chain's step 1 also gets `--no-virtual`, and its own `--integrates` in place of the one in state.

### Virtual chain

A virtual tenant (conventions C11) has no project, so there is nothing to scaffold, integrate or test. The pipeline runs the virtual chain when state holds `answers.virtual: true` (written by `tenant-init` step 1b, or reported by step 1 as `virtual: true`), or when `src/VirtualTenants/<T>/` exists and `src/Tenants/<T>/` holds no project:

| # | Step key | Skill | Arguments passed |
|---|---|---|---|
| 1 | `init` | `tenant-init` | Only when neither folder nor state exists: the [step 1 arguments](#step-arguments). It decides `virtual` in its step 1b |
| 3 | `shared` | `integrate-shared` | `<T> --mode virtual --gate 3/6 --recommend proceed`, plus `--shape`, `--scope`, `--endpoint` and the [shared source flags](#step-arguments) from state |
| 5 | `audit` | `tenant-audit` | `<T> --report-only`. It runs its virtual checks (Check V) |
| 6 | `deliverables` | `tenant-deliverables` | `<T> --gate 6/6 --route <slug>`. Offered when `src/VirtualTenants/<T>/GATEWAY-CONFIG.md` exists |

Record steps 2 and 4 as `skipped` with the reason "virtual tenant". Keep the step numbers of the full chain, so the state table reads the same for every tenant. When step 3 records `ran`, mark steps 5 and 6 `stale` if they were `ran`. `<slug>` is the first segment after `/t/` in the package's routes.

A virtual tenant that later needs a project is a real tenant from then on, through the promotion chain below.

### Promotion chain

A virtual tenant's routes can only forward to a path prefix a host already serves, under one scope. When the agency needs more — its own upstream system, an operation no host serves, token login or per-caller credentials, a combined route, its own contract — no route or scope change can carry it. The agency becomes a real tenant, and every operation its routes forwarded moves into the tenant's code with its contract frozen: same paths, request and response models, status codes, serialization and consumer scope (`tenant-integration` step 1b).

It starts with `--promote`, or from a virtual tenant's run (state `answers.virtual: true`, or `src/VirtualTenants/<T>/` with no project) when the developer asks for an agency integration. Ask header `Promote` first. The question lists the operations the routes forward today and says why the new integration needs a project:

| Option | Meaning |
|---|---|
| `Promote — project, forwarded operations re-implemented, then the integration (Recommended)` | The chain below |
| `Stay virtual` | Ends the run. The integration isn't built |

`--auto` takes `Promote`. A tenant with a project under `src/Tenants/<T>/` while `src/VirtualTenants/<T>/` still exists is a promotion in progress: resume the chain below without asking.

| # | Step key | Skill | Arguments passed |
|---|---|---|---|
| 1 | `init` | `tenant-init` | `<T> --no-virtual --no-pipeline --integrates <members>`, plus the rest of the [step 1 arguments](#step-arguments). `<members>` is the agency upstreams asked for, plus `shared` when the host is GOVZM. It moves the virtual routes into the tenant's `GATEWAY-CONFIG.md` as cross-cluster routes, the fallback until step 2 |
| 2 | `integration` | `tenant-integration` | `<T> --gate 2/6 --promote` plus `--protocol` as in the full chain. The promotion pass runs first, then the new upstream passes |
| 3 | `shared` | `integrate-shared` | `<T> --gate 3/6 --recommend skip`, plus the [shared source flags](#step-arguments): step 2 already exposes the forwarded shared operations. `Proceed` adds other shared operations only |
| 4 | `tests` | `tenant-tests` | `<T> --gate 4/6`. The promoted routes are on disk, so they are covered |
| 5 | `audit` | `tenant-audit` | `<T> --report-only`. The tenant has a project, so Checks 1–9 run, not Check V |
| 6 | `deliverables` | `tenant-deliverables` | `<T> --gate 6/6 --route <slug> --version <next>`. The route stays the virtual slug. `<next>` is one minor above `info.version` of `src/VirtualTenants/<T>/Deliverables/Tenant/<T> (t) API Swagger.json`, so consumers get a successor of the document they hold, not a new API. With no virtual package, no `--version` |

State. On entry, replace the virtual chain's records: step 1 is `pending` again, and steps 2 and 4 drop `skipped — virtual tenant`. Set `answers.virtual: false` and `answers.promotedFrom: "virtual"`, and keep the virtual answers (`shape`, `scope`, `endpoints`) under `answers.promotion` — step 2 reads the scope from there. Step 2 records its promotion entry (`tenant-integration` Report) beside the integration entries.

Parity is a hard stop. When step 2 ends with `GATE-RESULT: failed parity <METHOD> <path>`, record `failed` and stop the chain. Tests and documents built over a changed contract would ship that change to every consumer of the virtual tenant. A re-run of step 2 re-checks parity, and marks steps 4–6 `stale` as usual.

### Route check

"Exposes at least one route" is checked on disk, not taken from state, so it also holds for an existing tenant run with `--from`:

```bash
grep -rlE "Map(Get|Post|Put|Patch|Delete)\(|\[Http(Get|Post|Put|Patch|Delete)|:[[:space:]]*[A-Za-z]*SharedModule\(" src/Tenants/<T>/Modules src/Tenants/<T>/Controllers 2>/dev/null
grep -lF '{**catch-all}' src/Tenants/<T>/Program.cs 2>/dev/null
```

The `SharedModule(` alternative catches an `integrate-shared` `inherit` module, whose routes come from its base class and contain no `Map*` call.

The second grep finds a catch-all proxy (`tenant-integration --proxy`). It counts for step 4: the proxy is
tested. It doesn't count for step 6, because proxied operations aren't in the tenant's Swagger: a tenant
whose only route is the catch-all records step 6 as `skipped` with the reason "proxy only — no documented
operations".

When neither check finds anything, record the step as `skipped` with the reason "no routes" and don't
gate it. There is nothing to test or document.

`<route>` for step 6 is the gateway path without `/t/`, resolved in this order:

1. `src/Tenants/<T>/GATEWAY-CONFIG.md` — `routes[].configJson.match.path` of the import package
   (`/t/<route>/{**url}`); a hand-written file may hold the bare route object instead, same `match.path`
2. `docs/zamconnect-test-routes.md` — the live route whose `clusterId` is `<T>` uppercased. Routes
   often differ from the tenant name, so never guess from the folder name while this doc has a match

Never make the developer retype it. With neither source, leave `--route` off and let
`tenant-deliverables` apply its own default.

Pass every answer already in state as a flag (R1): `--source`, `--auth`, `--system`, `--role` for
step 2, `--version` / `--author` for step 6, and so on. The step then asks only what's still open.

Step 2 answers map to flags one-to-one, per entry of `answers.integrations`:

| State key | Flag |
|---|---|
| `protocol`, `sources` | `--protocol`, `--source` (a database entry keeps its `db=<path>` form, a GraphQL one `graphql=<…>`) |
| `auth`, `loginPath` | `--auth`, `--login-path` |
| `credentials`, `callers` | `--credentials`, `--callers` |
| `proxy: true` | `--proxy` |
| `dbAccess`, `dbWrites: true` | `--db-access`, `--db-writes` |
| `aggregate`, `shape`, `cache` (an aggregate entry) | `--aggregate`, `--aggregate-shape`, `--cache` |

## Running

1. **Load state.** Read `.claude/zamconnect/<T>.pipeline.json` if it exists. With `--status`, print
   the table (see Closing) and stop. The source flags join the loaded answers: each `--source` an
   `integrations` entry `{ "sources": [...] }`, `--shared-source` the `sharedSources` list, `--all`
   `sharedAll: true`. A source already in state isn't added twice. When step 1 runs, it records them
   itself (it gets them as given); otherwise they are written with the first step's state.
2. **Pick the start step.** From `--from`, from `--resume`, or from step 1 when there's no state and
   no tenant folder. If there's no state but the tenant exists, start at step 2 and create the state
   file with step 1 recorded as `ran`, command unknown. If there's no state but
   `src/VirtualTenants/<T>/` exists, use the virtual chain from step 3 and record step 1 the same way —
   unless `src/Tenants/<T>/` holds a project too: that is a promotion in progress, so use the promotion
   chain from step 2. When step 1 reports `virtual: true`, continue with the virtual chain. With
   `--promote`, or a `Promote` answer, use the promotion chain from step 1.
3. **For each step from the start:**
   - If its condition fails, record `skipped` with the reason and move on.
   - Invoke the skill through the `Skill` tool with the arguments above. Don't reimplement a step
     inline, and don't paste its instructions into the conversation.
   - Read the skill's final `GATE-RESULT:` line. Step 1 (`tenant-init --no-pipeline`) prints one
     too, and so does step 5 under `--report-only`: `GATE-RESULT: failed <reason>` only for a
     finding that blocks the chain (tenant-audit Report, "Gate result"). Its other `fail`, `warn`
     and `skipped` rows don't stop the chain: keep them for the closing summary. No line from
     step 5 means the audit didn't finish: record `failed`. Record `ran` /
     `skipped` / `failed`, the equivalent command the step printed, and the answers it reported
     for state. Write the state file after **every** step, not at the end. With `--dry-run`,
     write nothing, the state file included.
   - On `stopped`, stop the chain. On `failed`, stop and report the failure. Never carry on silently
     past a failed step.
4. **Invalidate.** When step 2 or 3 records `ran`, set every step from 4 to 6 that is currently
   `ran` to `stale`. Their output was built from the surface that just changed. When step 6
   reports `spec-only: ran` (its Findings fix ran `tenant-integration --spec-only`), set steps 4
   and 5 to `stale` the same way: the code changed after they ran.
5. **Close** (below).

With `--auto`, invoke each step with `--auto` instead of `--gate`, except step 5: the audit always
gets `--report-only`, because its `--auto` writes repo repairs (a missing pipeline file, compose
service or solution entry). Its fixable findings go in the closing summary as
`/tenant-audit <T> --fix`. `--no-pipeline` on step 1 only stops `tenant-init` from starting this
chain, and wins over the `--auto` passed with it; the Azure pipeline file is still created.

Under `--auto`, check the sources right after state is loaded, before any step runs, step 1
included (R10). Use state plus the source flags. When state holds no `integrates` yet, derive it
from the source flags as `tenant-init` step 1a does. Check only the steps that will run:

- Step 2: every `rest` / `graphql` / `soap` / `db` member of `integrates` needs a source of its
  own, and a `db` member a `db=<path>` source. Otherwise stop with
  `missing --source <url|path> for <protocol>`.
- Step 3: when `integrates` holds `shared`, `sharedSources` or `sharedAll` is needed. Otherwise
  stop with `missing --shared-source <SYS> or --all`. Step 3 runs only when the intake included
  `shared`.

The stop writes nothing, the state file included, so the same command with the flag added starts
cleanly. With neither a protocol nor a source there is nothing to check: step 2 is `skipped` (see
the chain). Everything else follows the same conditions.

## Closing

The chain as it actually ran, one line per step, then the exact commands to resume anything left over:

```
PQPS pipeline
  1 init           ran       /tenant-init PQPS --full-name "Plant Quarantine and Phytosanitary Service" --integrates soap
  2 integration    ran       /tenant-integration PQPS --source "…/pqps.wsdl" --auth Basic --role provide
  3 shared         skipped
  4 tests          ran       /tenant-tests PQPS --coverage full
  5 audit          stopped here
  6 deliverables   pending

Resume:  /tenant-pipeline PQPS --resume
Or run:  /tenant-audit PQPS
         /tenant-deliverables PQPS --route pqps
```

Steps marked `stale` are listed with the reason, e.g. "stale — integration re-ran on 2026-09-23".

When step 5 recorded `ran`, list its non-blocking rows under the chain, one line per row: check, status, finding. Lead with the `fail` rows, then `warn`, then `skipped`. They didn't stop the chain, but each one is still open:

```
Audit findings (not blocking)
  check 4  fail     2 tokens missing from ENVIRONMENT-VARIABLES.json
  check 9  warn     GET /t/pqps/hub/pesticides: upstream not reachable from the local stack
  check 7  warn     no Postman collection
```

A virtual tenant's summary shows steps 2 and 4 as `skipped — virtual tenant`, and its administrator list is shorter: import `src/VirtualTenants/<T>/GATEWAY-CONFIG.md` into each gateway and create the agency's gateway user with the route scope. There is no pipeline, variable or image.

A promoted tenant's summary heads the chain with `promoted from virtual tenant on <host>` and the parity result. Its administrator list is the full tenant's, plus the cutover from the tenant's `GATEWAY-CONFIG.md`, in its order: deploy, grant the tenant's gateway user the upstream scopes, import the package, then delete the old virtual routes (named by id) in each gateway. Consumers' users and scopes don't change. Rollback is re-importing `src/VirtualTenants/<T>/GATEWAY-CONFIG.md`, so the summary says to keep that folder until every gateway has been cut over, and to delete it only then.

## Sensitive data

Every step is local only (conventions C10): the chain writes files in the repo and the local Docker stack, and never creates a pipeline, variable, gateway record or ZamPass / RA client in any environment. The closing summary ends with the administrator's manual list: register the pipeline, add the `ENVIRONMENT-VARIABLES.json` entries to each environment, import `GATEWAY-CONFIG.md` into each gateway and grant the consumer scopes, register any ZamPass / RA client. Step 2 may add to it: create every gateway user named in a `per-caller` credential map with the tenant's scope, and open a network path from the cluster to a database upstream. It says that `ENVIRONMENT-VARIABLES.json` and `GATEWAY-CONFIG.md` are not in git (C10, "Not committed"), so the engineer sends them to the administrator directly.

No credential ever goes into this skill, the state file, or the summary. That means passwords,
connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and
equally the things that locate them: internal host names, server IP addresses and database
endpoints. If a step's answer contained one (a URL with embedded credentials, a token in a
header), record the flag name with the value redacted, and tell the developer to pass it again at
run time.
