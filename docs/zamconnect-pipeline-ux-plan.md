# ZamConnect plugin — guided pipeline UX plan

Status: implemented in `0.3.0` (not yet committed; phases 0 and 7 still open) · Previous version: `0.2.0`

## 1. Problem

`/tenant-init` drives a six-step chain, but every gate is the same three-way choice —
`Proceed` / `Skip` / `Stop`. Choosing an option gives the developer nowhere to say *how* the step
should run. The only way to pass details is to ignore the options and type free text, which few
people discover.

The clearest case is step 2. You pick `Proceed` on `/tenant-integration` and get no choice of
source type, no place to paste a URL or path, and no auth scheme. The skill then asks in plain
text, "in one batch". Its own `SKILL.md` has no structured questions at all.

Other gaps found while reviewing all six skills:

| # | Gap | Where |
|---|---|---|
| G1 | Gates have no parameter questions. A step's inputs can only come from free text or flags | `tenant-init` → Pipeline |
| G2 | `tenant-integration` asks nothing in a structured way: no source, auth, system name, endpoint selection or DTO strategy | `tenant-integration` §1 |
| G3 | Inputs that later steps need are never collected up front: the full descriptive name (`OpenApiInfo.Title`), the Consume/Provide role, the document author | `tenant-init`, `tenant-deliverables` |
| G4 | Step 3 always defaults to Skip, even when the developer already knows the tenant republishes NIR/PACRA/ZRA | `tenant-init` → Pipeline |
| G5 | The `integrate-shared` source menu has 10 systems, but `AskUserQuestion` allows at most 4 options per question. The skill never says how to fit them | `integrate-shared` §3b |
| G6 | The audit ends with a report. You can't choose which fixable findings to repair, and `tenant-audit` doesn't have `AskUserQuestion` in `allowed-tools` | `tenant-audit` |
| G7 | Deliverables can't be fully automated: endpoints `inspect_tenant.py` marks `UNKNOWN` / `Provide?`, the version, the author and the roles all need a person. `tenant-deliverables-builder` runs as a subagent, and subagents can't call `AskUserQuestion` | `tenant-deliverables` §3, agent |
| G8 | No review step before files are written, and no equivalent command is echoed, so a guided run can't be repeated without prompts | all writing skills |
| G9 | No saved state. After `Stop`, resuming means retyping every answer, and re-running step 2 doesn't mark steps 4–6 stale | `tenant-init` → Closing |
| G10 | A tenant with more than one upstream (`MCTI` → ZABS + ZMA, `MLSS` → 4 systems) gets one pass of step 2 and no "add another integration" loop | `tenant-init` → Pipeline |
| G11 | Two skills point to `/api-spec-sync`, which is repo-local, not part of this plugin. The pipeline's final step is `/tenant-deliverables`. There are two routes to the documents | `tenant-integration` §8, `integrate-shared` §7 |
| G12 | Spec readiness (`GenerateDocumentationFile`, `Swagger/`, `OpenApiInfo`) is added late, in `tenant-integration` §8, instead of being scaffolded in `tenant-init` | `tenant-init` §3 |

## 2. Design principles (researched)

| Principle | Source | Applied as |
|---|---|---|
| Every prompt has a flag equivalent. Never *require* a prompt. With no TTY or `--no-input`, fail and name the missing flag | [clig.dev — Interactivity](https://clig.dev/#interactivity) | R1, R10 |
| Make the default right for most users | [clig.dev — Arguments and flags](https://clig.dev/#arguments-and-flags) | `(Recommended)` on every question, `--auto` |
| Suggest the next command. Tell the user what changed | [clig.dev — Output](https://clig.dev/#output) | R7, closing summary |
| Offer a dry run, and confirm moderate changes | [clig.dev — Arguments and flags](https://clig.dev/#arguments-and-flags) | R6 review call, `--dry-run` |
| Operations are idempotent and crash-only | [clig.dev — Robustness](https://clig.dev/#robustness-guidelines) | R8 state and resume |
| Wizards suit infrequent setup tasks. Show a progress indicator, enforce order, save state and allow resume, reuse previous answers as defaults | [NN/g — Wizards](https://www.nngroup.com/articles/wizards/) | "Step n of N", R8 |
| Show a summary of choices before the final action. Let the user go back and edit one step instead of restarting | [UX Planet — Wizard pattern](https://uxplanet.org/wizard-design-pattern-8c86e14f2a38), [Eleken](https://www.eleken.co/blog-posts/wizard-ui-pattern-explained) | R6 `Adjust`, `--from <step>` |
| Fewer, focused steps. Catch errors per step, not at the end | [Andrew Coyle — Form wizard](https://www.andrewcoyle.com/blog/how-to-design-a-form-wizard) | Parameter packs; validate per step |
| Scaffolders ask a short question set with defaults, support `--yes`, and have a full-flag form | [create-next-app CLI](https://nextjs.org/docs/app/api-reference/cli/create-next-app) | R7 equivalent command, `--auto` |
| `AskUserQuestion` limits: 1–4 questions per call, 2–4 options each, "Other" free text always present, `multiSelect`, previews. Not available in subagents | [Claude Code — user input](https://code.claude.com/docs/en/agent-sdk/user-input) | R2, R9, G7 |
| Interview the developer with `AskUserQuestion` to settle real decisions before generating | [Claude Code best practices](https://code.claude.com/docs/en/best-practices) | Parameter packs |

## 3. Proposal

### 3.1 Shared interaction contract

Add one reference file, `plugins/zamconnect-integration/references/interaction-contract.md`. Every skill links to
it with `${CLAUDE_PLUGIN_ROOT}/references/interaction-contract.md`, so the rules live in one place.

| Rule | Requirement |
|---|---|
| **R1 Flag parity** | Each question maps to a flag. A flag that is present skips its question. The pipeline passes answers downstream as flags, so no question is ever asked twice |
| **R2 Structured only** | Questions go through `AskUserQuestion`, never plain text. Option order stays fixed and `(Recommended)` moves between options. The header is the step name (≤12 chars) |
| **R3 Details channel** | **Other** is the only text field that can be relied on, and it *replaces* the choice. Use it for the one value that can't be listed (a URL or path), and say so in the question text, not in option descriptions. Option notes (`annotations[q].notes`) are read when present, but are never the only way to supply a value. The VS Code dialog shows no notes field |
| **R12 Every option is a complete answer** | Selecting an option must be enough to act on it. No option may tell the user to pick a different option ("Pick Other and give the path"). If an answer needs a value, either the value *is* the option (a discovered file, a detected header) or a follow-up question asks for it. Never ask the user for something the skill can detect: source type, protocol and SOAP version come from the file itself |
| **R4 Required inputs in the gate** | If an input is required and has no safe default, such as the integration source, ask for it in the same call as the gate. Optional inputs appear only under `Customize…` |
| **R5 Options from the repo** | Build options from what's on disk: source files found in the repo, existing tenants, the agency register, earlier answers. Generic labels are the fallback |
| **R6 Review before write** | After inputs and before the first file is written, make one call that shows the planned files, routes and equivalent command. Options: `Apply (Recommended)` / `Adjust` / `Cancel`. `Adjust` asks one multiSelect listing the earlier questions, then re-asks only the ones picked |
| **R7 Echo the command** | After each step, print the fully-flagged command that reproduces it and save it in state |
| **R8 State & resume** | Save answers, per-step status and commands to state (§3.4). Previous answers become the next run's defaults |
| **R9 More than 4 options** | Group first, then drill down (category → items). For many items, spread them over up to 4 `multiSelect` questions in one call (16 items), plus an `All` option |
| **R10 Headless** | `--auto` takes every `(Recommended)` default. If a required input has no default, stop with `missing --source <url|path>`. Never guess |
| **R11 Echo interpretation** | Parse free text and state how it was read ("Source: WSDL at `https://…?wsdl`, SOAP 1.1"). Re-ask only that one question if it's ambiguous |

### 3.2 The gate, redesigned

Two gate shapes, depending on whether the step needs input that has no default.

**Shape A: step with defaults** (`integrate-shared`, `tenant-tests`, `tenant-deliverables`):

```
Header: Step 4/6
Q: /tenant-tests PQPS — scaffold src/Tests/PQPS.Tests and write endpoint tests. Run it?
  Proceed (Recommended)   — full coverage matrix, all modules, no live fixture
  Customize…              — choose coverage, modules, live staging fixture
  Skip                    — leave undone, continue the chain
  Stop                    — end here; state is saved for /tenant-pipeline PQPS --resume
```

`Proceed` runs with the defaults shown in its description. `Customize…` opens that step's parameter
pack (§3.3). A note on `Proceed` counts as a customization and is applied without another prompt.

**Shape B: step whose required input has no default** (`tenant-integration`): the gate question and
the required-input questions go in one `AskUserQuestion` call, so a single screen asks for both
"run it?" and "with what?". If the gate answer is `Skip` or `Stop`, the other answers are ignored.

#### What `Proceed` and `Customize…` mean, per step

`Skip` and `Stop` mean the same thing at every gate. A note on `Proceed` is applied as a
customization, with no extra prompt. Inputs that have no safe default are asked either way. Steps 1
and 5 have no gate: step 1 is the intake itself, and step 5 is read-only.

| Step | `Proceed` — runs with these defaults | `Customize…` — also asks |
|---|---|---|
| **2 `tenant-integration`** | Uses the source from the gate call. Protocol, SOAP version and auth are detected from it and confirmed in the proposal call. The proposal call opens with all upstream operations selected, the derived system name / client class, `Public DTOs + mapper`, and data role `Provide`. The surface is made spec-ready (§8) | Client class name override · upstream `Timeout` (REST only) · spec-ready now or later (`--no-spec-ready`) · module grouping (one module per system, or per business domain) · SOAP per-operation URLs (`<Tenant>SoapEndpointOptions`) |
| **3 `integrate-shared`** | Opens the group menu, which stays required. All operations in the chosen groups are selected. Mode is `routes`, or `inherit` when everything is selected, or `common` when the tenant already has a `CommonModule`. Tag `EServices`, no base path, shared response models | Swagger tag · module mode (`routes` / `common` / `inherit`) · response model (`Shared model` / `Tenant DTO + mapper`) · base path, only when the tenant already groups its own routes under one |
| **4 `tenant-tests`** | Creates `src/Tests/<Tenant>.Tests` if it doesn't exist. Adds `public partial class Program;` if missing. Full coverage matrix (happy path, upstream 404, upstream 500, forwarded body, route contract) for every module. No live fixture. Registers in the solution and runs `dotnet test` | Coverage (`Full matrix` / `Happy path + errors` / `Smoke only`) · modules (pick from the tenant's modules) · live staging fixture (`[Explicit]`, `[Category("Staging")]`) |
| **6 `tenant-deliverables`** | Route from `GATEWAY-CONFIG.md`. Version `1.0` for a new package, or the current version when the package exists and the contract hasn't changed. Roles from `inspect_tenant.py`. Author from `git config user.name`. Output to `Deliverables/`, with superseded files moved to `Archive/`. Endpoints marked `UNKNOWN` / `Provide?` are still asked | Document version (`1.0` / bump minor / keep) · roles (derived / all three / Tenant only) · author (git user / `dotGov Solutions LLC` / Other) · output directory (`--out`) |

### 3.3 Parameter packs, per step

Each pack is one `AskUserQuestion` call of at most 4 questions. `→ flag` shows the flag each answer
becomes.

#### Step 1 — `tenant-init` intake (new)

Asked once, right after the name is validated. It decides which steps come next and their defaults (G3, G4).

| Q | Options | Details via Other / notes | → flag |
|---|---|---|---|
| Project style | `Carter modules (Recommended)`, `MVC controllers` | — | `--controllers` |
| What will it integrate with? (multi) | `Agency REST API`, `Agency SOAP service`, `Shared e-Services (NIR, PACRA, ZRA…)`, `Not known yet` | — | `--integrates rest,soap,shared` |
| Full descriptive name | Agency-register match, if any · `Decide later (use code)` | **Other**: e.g. "Plant Quarantine and Phytosanitary Service" | `--full-name "<…>"` |
| Pipeline mode | `Guided (Recommended)`, `Auto with defaults`, `Scaffold only` | — | `--auto` / `--no-pipeline` |

Effects:

- `shared` flips step 3 to `Proceed (Recommended)`.
- `rest`/`soap` sets the default for step 2's protocol question.
- The full name goes straight into a spec-ready `AddSwaggerGen` with `OpenApiInfo.Title = "<Full name> (<CODE>)"` (G12). A `Swagger/` folder and `GenerateDocumentationFile` are scaffolded too.

A review call (R6) then shows the files, dev ports, pipeline slug and `core-<slug>`, with `Adjust`
for port or slug overrides.

#### Step 2 — `tenant-integration` (the headline fix)

**Call A, gate plus required inputs (Shape B):**

| Q | Options | Details via Other / notes | → flag |
|---|---|---|---|
| Step 2/6 — build the integration? | `Proceed (Recommended)`, `Customize…`, `Skip`, `Stop` | — | — |
| Integration source (multi) | See below. The options are the sources themselves, never source *types* (R12) | **Other**: a URL or path, one per line | `--source` (repeatable) |

The skill doesn't ask which *type* of source it is. That's read from the file, per `tenant-integration` §1a.
It also doesn't ask for auth or protocol yet: both are detected once the source is parsed, and are
confirmed in Call B.

The source question is built from discovery. Search `src/Tenants/<T>/Deliverables/Integration Requests/`,
`postman collections/`, and the repo root for `*.wsdl`, `*.postman_collection.json`,
`*swagger*.json|yaml`, `*openapi*.json|yaml`, `*.docx`, `*.pdf`. Match on the tenant code first.

*Candidates found:*

```
Integration source for TT — select one or more, or paste a URL or path in Other.
  [ ] postman collections/TT.postman_collection.json    Postman · 12 requests · JSON bodies (REST)
  [ ] Integration Requests/tt-service.wsdl              WSDL · SOAP 1.1 · 5 operations
  [ ] Integration Requests/TT API Guide.docx            API document · converted to Markdown first
  [ ] Other: ______________________________
```

*Nothing found:*

```
No integration source for TT in the repo. Paste a URL or path in Other, or:
  ( ) Search Downloads and Desktop        .wsdl / Postman / OpenAPI / .docx / .pdf changed in the last 30 days
  ( ) Wait while I add files              creates Integration Requests/, then rescans when you answer
  ( ) Skip the integration for now        marks step 2 skipped and continues the chain
  ( ) Other: ______________________________
```

After it's read, the skill echoes its interpretation (R11): "Read as: Postman collection, 12
requests, REST, Basic auth at collection level."

**Call B: proposal review.** It runs after the source is parsed, so its options come from the source (R5):

| Q | Options | → flag |
|---|---|---|
| Endpoints to expose (multi, spread over up to 2 questions by tag or `wsdl:operation`) | One option per upstream group, e.g. `Pesticides — 3 ops`, plus `All operations` | `--expose` |
| Upstream system name / client class | Name derived from `info.title` / `wsdl:service` `(Recommended)`, a short-code alternative | `--system` |
| Upstream auth | The **detected** scheme first, as a complete answer: `Basic (from collection auth)`, `Custom header X-Api-Key (from securitySchemes)`, `Client certificate (WS-Security policy)`. Then the other supported schemes. If `Custom header` is picked with no detected header name, a follow-up asks for the name, offering headers found in the source | `--auth`, `--auth-header` |
| Response shaping | `Public DTOs + mapper (Recommended)`, `Pass-through (shared model exists)` | `--dto public|passthrough` |
| Data role of these routes | `Provide — agency's own system (Recommended)`, `Consume — via gateway` | `--role` (feeds deliverables `--provide-paths`, G7) |

**Call C: review (R6).** Shows the client class, config section, models, mapper, modules and the
routes table (method, `/t/<route>/…`, purpose), plus the equivalent command. Options: `Apply` / `Adjust` / `Cancel`.

**Loop (G10).** After a successful build, ask: `Continue to step 3 (Recommended)` / `Add another integration source`. Choosing the second repeats Call A–C for the next upstream.

#### Step 3 — `integrate-shared`

The source menu fits within 4 options by grouping (G5, R9):

| Q (multi) | Options |
|---|---|
| Which shared e-Services? | `Identity — NIR (6 ops)`, `Business registries — NBR, DOC, SRS (3)`, `Immigration — ZDI (5)`, `Land, tax, health, education — NLR, ZDA, ZRA, MOH, NAIR (6)` |

Then one drill-down call per chosen group, with operations as `multiSelect` options labelled
`GET /nir/persons/nrc/{nrc} — person by NRC`. All operations start selected. Under `Customize…`:
Swagger tag, module mode (`routes` / `common` / `inherit`) and response model (`Shared model (Recommended)` / `Tenant DTO`).
Finish with the existing confirmation table, which becomes an R6 call.

#### Step 4 — `tenant-tests`

`Customize…` pack:

| Q | Options | → flag |
|---|---|---|
| Coverage | `Full matrix (Recommended)` (happy, 404, 500, forwarded body, route contract), `Happy path + errors`, `Smoke only` | `--coverage` (new) |
| Modules (multi) | Up to 4 modules found in the tenant + `All` | `--module` |
| Live staging fixture | `No (Recommended)`, `Yes — [Explicit] [Category("Staging")]` | `--live` |

If tests fail: `Fix the tenant (Recommended)` / `Show failures` / `Stop`. The skill's rule stays: don't
weaken assertions.

#### Step 5 — `tenant-audit`

The audit is read-only, so it runs without a gate (clig: mild actions need no confirmation). The
decision point moves to the findings (G6):

| Q (multi) | Options |
|---|---|
| Apply fixes? | One option per fixable finding (`Missing pipeline file`, `Compose service missing`, …), spread over up to 4 questions, + `Fix all fixable (Recommended)` |

Findings it can't fix, such as a missing `Endpoints:<Name>` or a committed credential, are printed
with the exact block to add and are never offered as options. Add `AskUserQuestion` to `allowed-tools`.

#### Step 6 — `tenant-deliverables`

`Customize…` pack. The route is always read from `GATEWAY-CONFIG.md`.

| Q | Options | → flag |
|---|---|---|
| Document version | `1.0 (Recommended for new)`, `Bump minor`, `Keep current (docs-only re-render)` | `--version` |
| Roles | Derived from `inspect_tenant.py` `(Recommended)`, `All three`, `Tenant only` | `--roles` |
| Author (history row) | `dotGov Solutions LLC (Recommended)`, `git config user.name` | `--author` (new) |

Then one follow-up call per 4 endpoints that `inspect_tenant.py` marks `UNKNOWN` / `Provide?`:
`Consume` / `Provide`, with the injected client named in each description. The answers go into
`--provide-paths`.

After the build, the **Code findings** list (missing `///`, `.WithTags`, undeclared codes) becomes:
`Fix now, then re-render (Recommended)`, which routes back to `tenant-integration` §8; `Hand over the list`; or `Stop`.
The skill itself stays documentation-only.

Because subagents can't ask questions, the pipeline collects every answer above *before* it
dispatches `tenant-deliverables-builder`, and passes them as flags (G7).

### 3.4 Orchestrator and state

**New skill `tenant-pipeline`.** It owns the chain that is now the `## Pipeline` section of `tenant-init`.

- `tenant-init` becomes scaffold-only. Unless `--no-pipeline` is passed, it hands off to
  `/tenant-pipeline <Tenant> --from integration`, so existing behaviour is unchanged.
- It works for existing tenants too: `/tenant-pipeline PQPS --from tests`,
  `/tenant-pipeline PQPS --resume`, `/tenant-pipeline PQPS --status`.
- **Invalidation:** re-running step 2 or 3 marks steps 4–6 `stale`. Resume offers them first.

**State file:** `.claude/zamconnect/<Tenant>.pipeline.json` in the ZamConnect repo, gitignored.
It deliberately sits outside `src/Tenants/<Tenant>/`, because the tenant `Dockerfile` copies that
whole folder into the image.

```json
{
  "tenant": "PQPS",
  "updated": "2026-09-23T10:42:00Z",
  "answers": { "style": "carter", "integrates": ["soap"], "fullName": "Plant Quarantine and Phytosanitary Service",
               "sources": ["Deliverables/Integration Requests/pqps.wsdl"], "auth": "Basic", "role": "provide" },
  "steps": [
    { "n": 1, "skill": "tenant-init", "status": "ran", "command": "/tenant-init PQPS --full-name \"…\" --integrates soap" },
    { "n": 2, "skill": "tenant-integration", "status": "ran", "command": "/tenant-integration PQPS --source … --auth Basic --role provide" },
    { "n": 4, "skill": "tenant-tests", "status": "stale" }
  ]
}
```

State never contains credentials, host names found in source files, or example identifiers. The
sensitive-data rules apply to it.

**Closing summary:** keep the existing one-line-per-step table and add the equivalent commands.
That makes the guided run reproducible with `--auto`.

### 3.5 Flag additions (R1 parity)

| Skill | New flags |
|---|---|
| `tenant-init` | `--full-name`, `--integrates rest,soap,shared`, `--dry-run` |
| `tenant-pipeline` (new) | `<Tenant>`, `--from <step>`, `--resume`, `--status`, `--auto`, `--dry-run` |
| `tenant-integration` | `--auth`, `--system`, `--dto public|passthrough`, `--role provide|consume`, `--no-spec-ready`, `--dry-run` |
| `integrate-shared` | `--dto shared|tenant` |
| `tenant-tests` | `--coverage full|errors|smoke` |
| `tenant-audit` | `--fix <check>` (select fixes by name) |
| `tenant-deliverables` | `--author`, `--provide-paths` (exposes the existing `build_package.py` option) |

## 4. Requirements

**Functional**

1. Every option in the guided flow is a complete answer (R12). The only typed input is "Other", for a value that can't be listed (R3).
2. Picking `Proceed` on `tenant-integration` never leads to a plain-text question. The source is asked in the gate call, with the files found on disk as its options. Protocol and auth are detected from the source.
3. Every question has a flag, and a flag that is present suppresses its question.
4. Every writing step shows an R6 review before its first file write.
5. Every step prints its equivalent command. The final summary lists all of them.
6. State is saved after each step. `--resume` continues from the first step that isn't `ran`, with earlier answers as defaults.
7. Re-running step 2 or 3 marks steps 4–6 stale.
8. `--auto` with a required input missing exits with the name of the missing flag.
9. The deliverables builder agent receives every answer as flags and never needs to ask.

**Non-functional**

- `SKILL.md` files stay lean. The contract and the packs go in `references/` (always-on token cost, per the README).
- No option, note, state or report ever echoes a credential.
- Gate order and labels are identical in every step.
- It works in both the CLI and the VS Code extension. Phase 0 verifies this.

## 5. Implementation steps

| Phase | Work | Files |
|---|---|---|
| **0 — Spike** | Check in the **CLI and in VS Code**: (a) are option notes / `annotations` returned to the skill; (b) "Other" together with `multiSelect`; (c) `AskUserQuestion` from a skill invoked via the `Skill` tool; (d) a 4-question call renders properly. If notes are missing in VS Code, R3 falls back to "Other" plus an explicit `Details` question | scratch only |
| **1 — Contract** | Write the interaction contract (R1–R11) and the gate shapes | `references/interaction-contract.md` (new) |
| **2 — Orchestrator** | Create `tenant-pipeline`. Move the `## Pipeline` section out of `tenant-init` and hand off to it. Add state, resume, invalidation and the closing summary | `skills/tenant-pipeline/SKILL.md` (new), `skills/tenant-init/SKILL.md`, `plugin.json` |
| **3 — tenant-init intake** | Intake pack, agency-register lookup, spec-ready scaffold (G12), R6 review | `skills/tenant-init/SKILL.md` |
| **4 — tenant-integration** | Calls A/B/C, candidate-source discovery, the add-another loop, role capture. Replace the `/api-spec-sync` reference (G11) | `skills/tenant-integration/SKILL.md`, `skills/tenant-integration/references/question-packs.md` (new) |
| **5 — Other steps** | `integrate-shared` grouping/drill-down; `tenant-tests` coverage pack; `tenant-audit` fix selection plus `AskUserQuestion` in `allowed-tools`; `tenant-deliverables` version/roles/author/UNKNOWN classification; the builder agent takes flags only | the four `SKILL.md` files, `agents/tenant-deliverables-builder.md` |
| **6 — Docs & release** | README: new flags, the new "Order of execution" and "Interactive mode" sections, a state-file note. Bump to `0.3.0`, run `claude plugin validate` on both manifests, add the `.gitignore` entry to ZamConnect | `README.md`, `plugin.json`, ZamConnect `.gitignore` |
| **7 — Evals** | Scenario evals (§6) with `claude plugin eval` | `plugins/zamconnect-integration/evals/` (new) |

Phases 3–5 are independent once phase 1 lands and can be split across PRs.

## 6. Test plan

- [ ] New REST tenant from an OpenAPI URL typed into "Other" at the step 2 gate: no plain-text question appears, and the review shows the routes before any write
- [ ] Lint every `SKILL.md`: no option label or description tells the user to pick another option ("Pick Other…"), and no question asks for something the skill can detect
- [ ] New SOAP tenant with a `.wsdl` in `Integration Requests/`: the file is offered as an option, SOAP 1.1 is detected and echoed
- [ ] A collection whose auth block uses the `X-Api-Key` header offers `Custom header X-Api-Key` as the first auth option. Picking it produces a `Custom` config section, and the echoed command shows `--auth Custom --auth-header X-Api-Key`
- [ ] Intake answer `Shared e-Services` makes step 3 `Proceed (Recommended)`. The group menu fits in 4 options
- [ ] Two upstreams through the add-another loop: two clients, two config sections, one routes table
- [ ] `Stop` at step 4, then `/tenant-pipeline <T> --resume`: starts at step 4 with no questions re-asked
- [ ] Re-run step 2 after the chain completes: steps 4–6 show `stale`
- [ ] `--auto` without `--source`: exits with `missing --source`
- [ ] Deliverables with one `UNKNOWN` endpoint: the classification is asked, passed as `--provide-paths`, and the builder agent runs without prompting
- [ ] Audit with a missing compose service: offered as a fix option. A missing `Endpoints:<Name>` is reported, not offered
- [ ] Regression: `/tenant-init X --no-pipeline` asks only the intake questions, scaffolds, and stops without gating anything
- [ ] No credential appears in any option, state file or summary (grep the state file after a run using `Basic` auth)

## 7. Decisions taken in 0.3.0

Revisit any of these at review.

1. **Orchestrator name:** `tenant-pipeline`.
2. **Documents route:** the plugin points to `/tenant-deliverables`. The repo-local `/api-spec-sync` is mentioned only as an optional developer-side regeneration.
3. **State location:** `.claude/zamconnect/<Tenant>.pipeline.json` in the ZamConnect repo. The directory writes its own `.gitignore` (`*`), so the repository's `.gitignore` isn't edited.
4. **Spec-ready scaffold:** always on in `tenant-init`. The title falls back to the bare code until the full name is known.
5. **Gate mode:** the pipeline doesn't build gates. It runs each skill with `--gate n/N`, and the skill returns `GATE-RESULT: …`, so each step's defaults stay in that step's skill.
6. **Document author default:** `dotGov Solutions LLC` (the existing `build_package.py` default), not a person's name, in line with the document-metadata rule.
7. **New `--spec-only` on `tenant-integration`:** it's how the deliverables' code findings get fixed without `tenant-deliverables` ever writing code.
8. **Question packs are inline** in each `SKILL.md`, not in separate `references/` files. They only load when the skill runs, so the always-on cost is unchanged.
