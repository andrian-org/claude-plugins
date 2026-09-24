---
name: tenant-pipeline
description: Guided end-to-end onboarding of a ZamConnect tenant — scaffold, integration, shared e-Services, tests, audit and delivery documents — as one gated chain with a saved state, so a stopped run can be resumed and a re-run step marks what it invalidated. Use when the user says "onboard <Tenant>", "run the whole tenant pipeline", "continue/resume <Tenant>", "what's left for <Tenant>", "re-run tests and docs for <Tenant>", or types /tenant-pipeline.
argument-hint: "<TenantName> [--from init|integration|shared|tests|audit|deliverables] [--resume] [--status] [--auto] [--dry-run]"
allowed-tools: Read Write Glob Grep Bash(ls *) Bash(grep *) Bash(find *) Bash(mkdir *) Bash(git config *) AskUserQuestion Skill
disable-model-invocation: false
---

# ZamConnect Tenant Pipeline

Runs the six tenant skills in order, one gate per step, and keeps the run in a state file so it
can be stopped and resumed. The pipeline owns **order, conditions, state and the closing
summary**. Each step skill owns its own gate and questions.

Read `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md` first. Its gate, gate mode, state
file and rules R1–R12 are assumed below.

All paths are relative to the ZamConnect repository root (the directory holding `src/ZamConnect.sln`).

## Arguments

| Argument | Meaning |
|---|---|
| `<TenantName>` | Tenant folder name. Asked for if it's missing, with existing tenants that have a state file offered first |
| `--from <step>` | Start at this step. Everything before it is left as it is in state |
| `--resume` | Start at the first `stale` step, then the first `pending` / `failed` one. This is the default when a state file exists and neither `--from` nor `--status` is given |
| `--status` | Print the state table and the resume commands, then stop. Asks nothing, writes nothing |
| `--auto` | No gates. Every step runs with its `(Recommended)` defaults and is given `--auto`. Stops on the first required input that has no default (R10) |
| `--dry-run` | Passed to every step. Plans are printed and nothing is written |

## The chain

| # | Step key | Skill | Offered when | Arguments passed |
|---|---|---|---|---|
| 1 | `init` | `tenant-init` | `src/Tenants/<T>/` does not exist | `<T> --no-pipeline` + intake answers from state |
| 2 | `integration` | `tenant-integration` | always | `<T> --gate 2/6`, plus `--protocol rest` or `--protocol soap` only when the intake answer `integrates` names exactly one of them |
| 3 | `shared` | `integrate-shared` | always. `--recommend proceed` when `integrates` contains `shared`, otherwise `--recommend skip` | `<T> --gate 3/6` |
| 4 | `tests` | `tenant-tests` | the tenant exposes at least one route (see below) | `<T> --gate 4/6` |
| 5 | `audit` | `tenant-audit` | always. Run read-only, so it has **no gate** | `<T> --report-only` (also under `--auto`) |
| 6 | `deliverables` | `tenant-deliverables` | the tenant exposes at least one route | `<T> --gate 6/6 --route <route>` |

"Exposes at least one route" is checked on disk, not taken from state, so it also holds for an existing tenant run with `--from`:

```bash
grep -rlE "Map(Get|Post|Put|Patch|Delete)\(|\[Http(Get|Post|Put|Patch|Delete)" src/Tenants/<T>/Modules src/Tenants/<T>/Controllers 2>/dev/null
```

When the check finds nothing, record the step as `skipped` with the reason "no routes" and don't
gate it. There is nothing to test or document.

`<route>` for step 6 is the gateway path without `/t/`, resolved in this order:

1. `src/Tenants/<T>/GATEWAY-CONFIG.md` — `routes[].configJson.match.path` of the import package
   (`/t/<route>/{**url}`); a pre-0.4 file has the bare route object instead, same `match.path`
2. `docs/zamconnect-test-routes.md` — the live route whose `clusterId` is `<T>` uppercased. Routes
   often differ from the tenant name, so never guess from the folder name while this doc has a match

Never make the developer retype it. With neither source, leave `--route` off and let
`tenant-deliverables` apply its own default.

Pass every answer already in state as a flag (R1): `--source`, `--auth`, `--system`, `--role` for
step 2, `--version` / `--author` for step 6, and so on. The step then asks only what's still open.

## Running

1. **Load state.** Read `.claude/zamconnect/<T>.pipeline.json` if it exists. With `--status`, print
   the table (see Closing) and stop.
2. **Pick the start step.** From `--from`, from `--resume`, or from step 1 when there's no state and
   no tenant folder. If there's no state but the tenant exists, start at step 2 and create the state
   file with step 1 recorded as `ran`, command unknown.
3. **For each step from the start:**
   - If its condition fails, record `skipped` with the reason and move on.
   - Invoke the skill through the `Skill` tool with the arguments above. Don't reimplement a step
     inline, and don't paste its instructions into the conversation.
   - Read the skill's final `GATE-RESULT:` line (step 5, with no gate, counts as `ran` unless it
     reported a failure). Record `ran` / `skipped` / `failed`, the equivalent command the step
     printed, and any answers it reported. Write the state file after **every** step, not at the end.
   - On `stopped`, stop the chain. On `failed`, stop and report the failure. Never carry on silently
     past a failed step.
4. **Invalidate.** When step 2 or 3 records `ran`, set every step from 4 to 6 that is currently
   `ran` to `stale`. Their output was built from the surface that just changed.
5. **Close** (below).

With `--auto`, invoke each step with `--auto` instead of `--gate`, except step 5: the audit always
gets `--report-only`, because its `--auto` writes repairs (e.g. a pipeline file step 1 deliberately
skipped). Its fixable findings go in the closing summary as `/tenant-audit <T> --fix`. Step 3 runs
only when the intake included `shared`. Everything else follows the same conditions.

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

## Sensitive data

No credential ever goes into this skill, the state file, or the summary. That means passwords,
connection strings, API keys, bearer tokens, client secrets, certificates and private keys, and
equally the things that locate them: internal host names, server IP addresses and database
endpoints. If a step's answer contained one (a URL with embedded credentials, a token in a
header), record the flag name with the value redacted, and tell the developer to pass it again at
run time.
