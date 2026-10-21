---
archived: 2026-09-22
---
# Implementation Plan: Open Decisions Closed

Branch: feature/open-decisions-closed
Created: 2026-09-21
Refined: 2026-09-21 — questions #5 and #6 evidence gathered and verified (Findings 1 and 2)
Refined: 2026-09-21 — `/aif-improve`: `dgf-harness` removed as a constraint and as an evidence source; see `## Scope Amendment`
Base: `main` at `0e28010` (the dual-schema branch was fast-forward merged into `main` before this branch was cut)

## Original Request

**Open Decisions Closed** — reconcile with `dgf-harness` ADRs 0711/0716; answer blueprint open questions #3, #5, #6, #7

## Scope Amendment (2026-09-21)

The user directed, after this plan was first written:

> Ignore completely `dgf-harness`, it is not something that we must follow, not at all. We will start a
> completely new implementation with architecture that we bring from ai-factory.

This supersedes the reconciliation clause of `## Original Request`. The consequences, all applied below:

- **The delivery-model question is decided, not weighed.** `dgf-factory` is an independent Claude Code
  plugin whose pipeline architecture derives from AI Factory 2.18.1. ADR 0001 records that decision rather
  than reasoning toward it.
- **`dgf-harness` is not an authority, a dependency, an architecture source, or a comparison baseline.**
  No task cites a `src/Tools/dgf-harness/` path, and no interview seeds itself from harness behaviour.
- **The harness ADR series (`07xx`) is not cited as a constraint.** Every fact this plan relies on is
  sourced from first-party DGF — the engine under `src/Core`, the MCP server under `src/Tools/dgf-mcp`, the
  shipped schemas, and `docs/wiki/`.
- **The knowledge base and validators are built, not vendored.** Roadmap milestones 7 and 8 stand as
  written.
- **No ADR from that effort's series is cited or reconciled with**, at the user's explicit direction.

## Settings

- Testing: yes — extend `scripts/check-dual-schema-docs.sh` with decision-record assertions
- Logging: verbose
- Docs: yes — mandatory documentation checkpoint at completion
- Output shape: a numbered ADR set under `docs/adr/`, independent of any other repository's series
- Questions #3 and #7: closed by a structured interview with the user during implementation, not from
  repository evidence
- Scope: decisions and their propagation only. No `knowledge/` scaffold, no validators, no `dgf-*` skills,
  no `plugin.json`. This milestone decides; the later milestones build.

## Roadmap Linkage

Milestone: "Open Decisions Closed"
Rationale: This plan is the whole of roadmap milestone 5 — it records the delivery-model decision and closes
the four remaining blueprint open questions, which every later milestone's scope depends on.

## Task Ledger Note

`TaskCreate` / `TaskUpdate` are unavailable in this session. The checkbox list under `## Tasks` is the
**single** progress ledger for this plan. `/aif-implement` updates the checkboxes here and nowhere else.

---

## Background — Verified Evidence

Read from `~/workspaces/dotgov/_DotGovFramework/DotGovFramework` and this repository on **2026-09-21**.
Every task below cites this section rather than re-deriving it. All evidence is first-party DGF.

### Prior work considered and set aside

A separate DGF agent-tooling effort exists in the DGF repository, with its own accepted ADR series. Its
overlap with this plugin was measured on 2026-09-21 and it is **deliberately not a constraint on this
plugin** — not an authority, not a dependency, not an architecture source. This paragraph exists so a later
reader knows the overlap was assessed rather than overlooked. Do not reintroduce it as a design input; see
`## Scope Amendment`.

### Finding 1 — headless process verification is XSD-only, and the semantic gap is provable from the shipped artifacts

Direct answer to open question #5, verified 2026-09-21:

- **The MCP process/workflow validators are one-line XSD wrappers.**
  `src/Tools/dgf-mcp/Tools/ValidateXmlTool.cs` L36-44 — `ValidateWorkflowXml` and `ValidateProcessXml` each
  call `validator.Validate(xml, "<artifact>.xsd")` and nothing else.
  `src/Tools/dgf-mcp/Services/XsdValidationService.cs` is the whole engine: `XmlReaderSettings` with
  `ValidationType.Schema` plus a cached `XmlSchemaSet`. **No semantic pass of any kind.**
- **The cross-reference validator excludes process outright.**
  `src/Tools/dgf-mcp/Services/XmlCrossReferenceValidator.cs:94` —
  `"Unsupported artifactType: … Supported: form, settings, workflow."` Its workflow coverage is `BASE:X.Y`
  reference resolution only: no reachability, no handler existence, no state-graph analysis.
- **The grammar cannot express the check the grammar implies.** `Schemas/XSD/process.xsd` declares
  `States/State` (L37-44) and `Transitions/Transition` (L131-138), so a transition referring to a state is
  structurally part of the model — but the file contains **no `xs:key`, `xs:keyref` or `xs:unique`**. XSD
  therefore cannot verify that a `Transition` targets a declared `State`. Combined with the previous point,
  this is a closed proof: **a transition to a nonexistent state is unreported by everything DGF ships.** It
  is dead at run time and silent at authoring time.
- **The deepest validator is in-app, DB-bound, and its process branch is commented out.**
  `src/Core/DGF.Explorer/Services/DiagnosticCheckService.cs` has `ValidateWorkflow` and `ValidateHandler`
  (the missing-handler check), but `ValidateProcessWfAndFrm` (L514) has its process path commented out, and
  its only dispatch site is commented too — L680:
  `/*case "PROCESS": ValidateProcessWfAndFrm(controlName); break;*/`. It requires `IDataAccessLayer`, and
  its only reference anywhere in the repository is its DI registration.
- **Headless validation needs no engine build.** `src/Tools/dgf-mcp/DgfMcpServer.csproj` contains **zero
  `<ProjectReference>`** — its XSDs, JSON schemas and wiki are committed assets — so the MCP server builds
  and runs standalone. Validation goes over its HTTP transport.
- **Execution, as opposed to validation, is not headless.**
  `src/Core/DGF.Domain/Process/StateProcess/ProcessManager.cs` can deserialize a `process.xml` with only
  `WorkspaceSettings` + `IFileSerializationService`, but stepping a process runs through
  `src/Core/DGF.OM/Process/StateProcess/InstanceHandler.cs` `GetProcessMapAsync`, which needs a case record
  and therefore the database. The de-facto "does it run" check is the browser, via the Playwright suite
  under `tests/src/specs/solutions/`.

So question #5's answer is asymmetric in a way the blueprint does not anticipate: **structure is
deterministic and headless today; semantics are not checkable against an existing process file by anything
DGF ships.** That gap is the concrete opportunity for a validator in this plugin, and the dead-transition
check is its proven first target — proven not by precedent, but because the schema demonstrably cannot
express it and no shipped validator covers it.

### Finding 2 — versions break knowledge without breaking schemas, and nothing first-party is version-stamped

Direct answer to open question #6, verified 2026-09-21:

- **There is a breaking change of exactly the class a schema check cannot catch.**
  `docs/wiki/Release-notes/RELEASE-1.1.15.md` §"Breaking Changes" — *"TreeTable: expandAll and paging now do
  what they say"*. Two properties "were accepted in configuration and then ignored". Now
  `"expandAll": false` genuinely collapses a tree where before it did nothing, and **`paging` on an eager
  TreeTable is rejected with a configuration error** — *"those pages will now fail to load until you remove
  it, or move them to `"loadMode": "lazy"`."* The same JSON validates against the same schema in 1.1.14 and
  1.1.15; it is merely fatal in one of them. **This single release note answers #6: version gates are
  necessary, and schema validation cannot substitute for them.**
- **The version source of truth is stamped in one build configuration only.**
  `src/Directory.Build.props` L32-34 sets `<Version>1.1.11</Version>` inside
  `<PropertyGroup Condition="'$(Configuration)' == 'ClientDebug'">`. It is the only such definition in the
  repository and there is no second `Directory.Build.props`. The block's own comment claims *"All
  configurations share the same version so the Docker (Release) image is compatible"* — an intent the
  condition does not implement, since no other configuration sets `Version` at all.
- **Nothing first-party version-stamps DGF knowledge.** The XSDs under `src/Tools/dgf-mcp/Schemas/XSD/` carry
  no `version` attribute and have no per-version copies. The generated JSON schemas under `Schemas/Json/`
  record no DGF version. No component doc carries a "since 1.1.x" marker. No compatibility matrix or
  supported-version-window document exists anywhere in `docs/`.
- **The hosted MCP endpoint is unversioned.** This plugin's own `.mcp.json` and `DESCRIPTION.md` target
  `https://dgf-mcp.dotgov.uk/mcp` — no version segment. Version-addressable knowledge cannot be obtained
  from it, so a version gate has to be carried by this plugin's own artifacts.
- **Release notes are the only version-aware surface that exists.** They live one file per version at
  `docs/wiki/Release-notes/RELEASE-<version>.md` (`1.0.30`–`1.0.33`, `1.1.0`–`1.1.15`), and the MCP's
  `get_release_notes` accepts `"since:X.Y.Z"`, concatenating every strictly-newer release's markdown. That
  is the natural input to a drift check asking "what changed between the stamped version and mine".

### Local ADR numbering

This plugin's ADRs are numbered from `0001` in its own `docs/adr/` and are independent of any other
repository's ADR series. A bare `0001`–`0005` in this plugin always means a dgf-factory ADR.

---

## Commit Plan

| commit | tasks | message |
|---|---|---|
| 1 | 1–2 | `docs: add local ADR set and record the independent delivery model` |
| 2 | 3–4 | `docs: close open questions 5 and 6 with process-verification and version-gating ADRs` |
| 3 | 5–6 | `docs: close open questions 3 and 7 from the team interview` |
| 4 | 7–9 | `docs: propagate closed decisions to blueprint, description and navigation` |
| 5 | 10–11 | `test: assert decision-record consistency in the docs check` |

---

## Tasks

### Phase 1: ADR infrastructure and the delivery-model decision

- [x] **Task 1: Create `docs/adr/` with a README index**

  Create `plugins/dgf-factory/docs/adr/README.md` as the index and the authoring contract for this
  plugin's ADRs.

  Contents:
  - A status table with columns `#`, `Title`, `Status`, `Date`, `Decides` — one row per ADR, seeded with the
    five rows this plan will fill (0001–0005), each initially `proposed`.
  - The frontmatter contract: `id`, `title`, `status`, `date`, `deciders`, `supersedes`, `tags`. Status
    vocabulary: `proposed` | `accepted` | `rejected` | `superseded-by-NNNN`.
  - The section contract: `## Context` (measured evidence, dated) → `## Decision` (imperative, bolded
    one-liner first) → `## Alternatives considered` → `## Consequences` (positive / negative / follow-ups).
  - The numbering note from `## Background`: local ADRs are `0001+` and independent of any other
    repository's series.

  Logging: none — this task produces Markdown only. The ADR index is the audit trail.

- [x] **Task 2: Write ADR 0001 — the delivery model and architectural provenance** (depends on 1)

  Create `docs/adr/0001-independent-plugin-with-ai-factory-derived-architecture.md`.

  This ADR **records a decision the user has already made** (see `## Scope Amendment`, dated 2026-09-21).
  It does not weigh alternatives toward it. Attribute the decision to the user with that date.

  The Decision section has two halves, both explicit:

  1. **`dgf-factory` ships as a Claude Code plugin in the `dotgov` marketplace, independent of any other
     DGF agent-tooling effort.** No dependency, no shared artifacts, no obligation to track another
     repository's ADR series.
  2. **Its pipeline architecture derives from AI Factory 2.18.1.** Name what is carried over, citing
     `docs/blueprint.md` §"What stays: all five core ideas" — single-writer artifact ownership; the
     planner/executor split with `index.md` + phase bundles; machine-readable gate blocks; worktree-isolated
     parallel workers; and the fix → patch → evolve → skill-context learning loop. State that this is a
     **derivation, not a dependency**: the `aif-*` corpus under `.claude/` is installer-managed reference
     material, the plugin ships its own skills, and nothing at runtime requires AI Factory to be installed.

  Consequences must state:
  - The knowledge base and validators are **built**, not vendored from elsewhere. Roadmap milestones 7 and 8
    stand as written.
  - The `.claude-plugin/plugin.json` + marketplace-entry delivery path is confirmed, which unblocks
    milestones 6 and 15.
  - What named trigger would reverse this decision.

  **STOP condition:** this ADR must not reopen the delivery-model question. If the implementer believes the
  decision is wrong, record that as a follow-up in Consequences and report it — do not write an ADR that
  hedges on a decision the user has made.

  Logging: none — Markdown only.

### Phase 2: Close the evidence-answerable questions

- [x] **Task 3: Write ADR 0002 — process verification (closes open question #5)** (depends on 1)

  Blueprint question #5: *"what does verification look like for a process? Is there a way to execute a
  process definition headlessly?"*

  **The evidence is already gathered — see `## Background` Finding 1.** Do not re-run the search. Cite those
  paths and decide. Re-verify a path only if an edit to it would change the conclusion.

  The ADR's Context must state the asymmetry plainly: structure is deterministic and headless today
  (`ValidateXmlTool.cs` → `XsdValidationService`, against an MCP server that builds standalone because
  `DgfMcpServer.csproj` has zero `<ProjectReference>`); semantics are checkable by nothing DGF ships. Give
  the closed proof for the flagship gap — `process.xsd` has no `xs:key`/`xs:keyref`/`xs:unique`, so the
  schema cannot verify a `Transition` targets a declared `State`, and `XmlCrossReferenceValidator.cs:94`
  excludes process from the only reference-resolving validator. Note that the one in-repository validator
  that could have covered it, `DiagnosticCheckService`, has both its process branch (L514) and its dispatch
  site (L680) commented out and requires a live database.

  The Decision section must answer:
  1. What does this plugin treat as "process verified"? Specifically, is XSD-valid sufficient to pass a
     gate, or does a gate require semantic checks that do not exist yet?
  2. Which semantic checks does this plugin commit to implementing over an existing `process.xml`? The
     dead-transition check is the first target, and Finding 1 establishes that nothing else covers it.
  3. Does verification run against vendored XSDs validated in-process, or against a locally booted MCP
     server? Prefer vendored, consistent with ADR 0001's build-not-borrow decision, and state the
     re-vendor/drift obligation that choice creates.
  4. Since a process cannot be *executed* headlessly, what replaces execution in a gate — and does this
     plugin accept a browser-driven check, given that `DESCRIPTION.md` records browser MCP servers as
     excluded on a ~12,000-token budget basis?

  Record Finding 1's negative results in the ADR (no MCP server test project, no process regression corpus,
  no process support in the cross-reference validator) so the next reader does not repeat the search.

  Logging: none — Markdown only.

- [x] **Task 4: Write ADR 0003 — version gating (closes open question #6)** (depends on 1)

  Blueprint question #6: *"do DGF versions differ enough that references need version gates?"*

  **The evidence is already gathered — see `## Background` Finding 2.** Do not re-run the search. The
  question is answered: **yes.** `RELEASE-1.1.15.md` §"Breaking Changes" is a same-schema/different-verdict
  break — `paging` on an eager TreeTable moved from silently dropped to a hard configuration error, so
  identical JSON validates in both versions and only fails to load in one. A schema check cannot catch that
  class of change, which is precisely what a version gate is for.

  The ADR's job is to decide the mechanism:
  1. **Stamp fields.** Which fields must this plugin's knowledge carry? Decide the set — at minimum the DGF
     version a fact was read from, the date, and a per-file digest of the vendored source so drift is
     detectable. Read the version from `src/Directory.Build.props`, not from a git tag: a stamp that lags
     the thing it stamps is worse than no stamp.
  2. **Stamp versus gate.** Decide per fact class. A component property that changed verdict between
     releases needs a *range*; a stable structural fact needs only a *stamp* recording what it was read
     from. Do not gate everything — an over-gated fact base goes stale as fast as an unstamped one.
  3. **Out-of-range behaviour.** What does a consumer do when its DGF version falls outside a stamped
     range: refuse, warn, or proceed? Tie this to the exit-code contract in `.ai-factory/rules/base.md`.
  4. **What cannot be depended on.** The hosted MCP endpoint is unversioned
     (`https://dgf-mcp.dotgov.uk/mcp`), so version-addressable knowledge cannot be fetched from it. Record
     that the gate is carried by this plugin's own vendored artifacts, and say how.
  5. **One upstream defect to note, not fix.** The canonical `<Version>1.1.11</Version>` is set only under
     `Condition="'$(Configuration)' == 'ClientDebug'"`, despite a comment asserting all configurations share
     it. Record it in Consequences as a follow-up owned upstream, and state which version this plugin
     stamps against in the meantime.

  Also record `get_release_notes("since:X.Y.Z")` as the only version-aware query surface that exists today
  — it is the natural input to a drift check that asks "what changed between the stamped version and mine".

  Logging: none — Markdown only.

### Phase 3: Close the team-only questions

- [x] **Task 5: Interview the user, then write ADR 0004 — authoring entry point (closes open question #3)** (depends on 1)

  Blueprint question #3: *"is 'build a system from scratch' the dominant case? If yes, `/dgf-scaffold` moves
  to phase 1."* This is not in the repository. Ask the user, using `AskUserQuestion`:

  1. Across real dotGov delivery work, what share is greenfield (new system from nothing) versus brownfield
     (extending a running system)?
  2. When a new system does start, who starts it — is it scaffolded by hand today, or from a template?
  3. What is the unit of work a skill should target: a whole system, or one application inside a larger
     workspace?

  Then write `docs/adr/0004-authoring-entry-point.md` recording the user's answer, attributed to them with
  the date, and state the consequence for roadmap ordering — specifically whether a scaffold skill moves
  earlier than milestone 12.

  **Requires the user to be present.** If `/aif-implement` runs unattended, stop at this task rather than
  inventing an answer, and report it as blocked.

  Logging: none — Markdown only.

- [x] **Task 6: Interview the user, then write ADR 0005 — default team rules (closes open question #7)** (depends on 1, 5)

  Blueprint question #7: *"which dotGov-specific rules should ship as defaults in `RULES.md` rather than
  being discovered per project?"*

  Ask the user which conventions are true of every dotGov DGF system rather than discovered per project.
  Seed the conversation with concrete candidates drawn from first-party evidence, so the question is
  answerable rather than open-ended:
  - the XML-always Wave-1 generation policy for the five legacy artifact types, from
    `docs/wiki/AI-Authoring/format-coverage.md`;
  - auth conventions — JWT Bearer plus OIDC via Azure AD and DGPass;
  - the test stack — xUnit / FluentAssertions / Moq, Jest, Playwright;
  - declarative-behaviour conventions: configuration composed through DataFetcher and `EventBase` verbs
    rather than hand-written JavaScript in workspace artifacts;
  - scope discipline: DGF-seam guidance only, not general C#, SQL or Angular advice.

  Write `docs/adr/0005-default-team-rules.md` with the decided default set, each rule tagged with how it
  would be enforced (script, gate, or prompt-only), and an explicit note of which candidates were
  **rejected** as project-specific. Do not create `RULES.md` itself — `paths.rules_file` is owned by
  `/aif-rules`, and writing it here would breach single-writer ownership.

  Logging: none — Markdown only.

### Phase 4: Propagate the closed decisions

- [x] **Task 7: Flip the blueprint's open questions** (depends on 2, 3, 4, 5, 6)

  Edit `docs/blueprint.md` §"Open questions to resolve before writing skills". For questions #3, #5, #6 and
  #7, append a `> **ANSWERED (2026-09-21).**` block in the exact style already used for #1, #2 and #4, each
  linking the ADR that decided it. Keep the question text itself unchanged — it is the historical record.

  Also in `docs/blueprint.md`:
  - update §"Proposed skill set" if ADR 0004 moved a scaffold skill's phase;
  - reconcile §"What changes: delivery layer" with ADR 0001 — the table's `extensions/injections → defer`
    row and anything implying a shared delivery mechanism are now settled as out of scope;
  - confirm §"Build order" steps 1 and 2 still read correctly given that knowledge and validators are built
    rather than borrowed.

  Logging: none — Markdown only.

- [x] **Task 8: Update `DESCRIPTION.md`** (depends on 2, 3, 4, 5, 6)

  Rewrite `.ai-factory/DESCRIPTION.md` §"Known Risk — Accepted". The section currently instructs a future
  reader to "read ADRs 0711 and 0716 first and either reconcile with `dgf-harness` or record why the
  divergence is intentional." ADR 0001 settles that, so the section becomes short: the plugin is
  independent, its architecture derives from AI Factory 2.18.1, and the decision is recorded in ADR 0001.
  Remove the reconciliation instruction and the ADR-reading prerequisite rather than restating them.

  Also:
  - update §"Target Framework Facts" with the version facts from Finding 2 — the `1.1.11` source of truth
    and its `ClientDebug`-only condition;
  - update the blueprint open-questions summary line so it no longer lists #3, #5, #6 and #7 as open;
  - add the process-verification asymmetry from Finding 1 as a verified fact row, since it directly shapes
    what `/dgf-verify` can claim.

  Logging: none — Markdown only.

- [x] **Task 9: Update `AGENTS.md` and `README.md`** (depends on 7, 8)

  `AGENTS.md`:
  - add `docs/adr/` to §"Project Structure" and §"Documentation";
  - in §"External References", remove the rows that present another DGF agent-tooling effort and its ADR
    series as required reading — ADR 0001 makes them non-constraints. Keep the rows for first-party DGF
    material this plugin genuinely depends on: the framework itself, the JSON and XSD schema directories,
    `format-coverage.md`, and the hosted MCP;
  - add a §"Agent Rules" entry pointing at `docs/adr/README.md` as the decision record, and one stating that
    this plugin's architecture derives from AI Factory and takes no dependency on other DGF tooling.

  `README.md`: add `docs/adr/` to the documentation table. Keep the landing page lean — link, do not
  summarise.

  Logging: none — Markdown only.

### Phase 5: Verification

- [x] **Task 10: Extend the documentation check with decision-record assertions** (depends on 1–9)

  Extend `scripts/check-dual-schema-docs.sh` rather than adding a second script. Its structure supports this
  directly: numbered check sections, an `error` / `warn` pair accumulating into `ERRORS` / `WARNINGS`, and a
  `main()` that calls each check in sequence under a fixed exit-code contract.

  Changes:
  - generalise the file header comment and the printed title (currently `Dual-schema documentation check`) so
    the script's stated purpose covers both contracts. **Keep the filename** — `.ai-factory/rules/base.md`,
    `AGENTS.md` and the dual-schema plan all reference it by name, and renaming churns all three for no gain.
    Record this as a deliberate mismatch between name and scope in the header.
  - add `check_decision_records()` as section 5 and register it in `main()` after `check_absolute_paths`.

  Assertions:
  | # | assertion | severity |
  |---|---|---|
  | 1 | `docs/adr/README.md` exists | error |
  | 2 | every `docs/adr/NNNN-*.md` has an index row, and every index row has a file | error |
  | 3 | every ADR's frontmatter has `id`, `title`, `status`, `date`, and `id` matches its filename prefix | error |
  | 4 | every `status` is in the allowed vocabulary | error |
  | 5 | no blueprint open question is ANSWERED without linking an existing ADR file | error |
  | 6 | no ADR remains `proposed` while its blueprint question is marked ANSWERED | error |
  | 7 | no owned markdown cites a `src/Tools/dgf-harness/` path or presents another DGF agent-tooling effort as a constraint | error — ADR 0001 settled this; a reintroduction is a regression |
  | 8 | an ADR with no `## Decision` section, or a `## Decision` under 200 characters | warn |

  Note that `owned_markdown()` already walks all `*.md` outside `.claude/`, `.git/`, `node_modules/` and
  `plans/`, so new ADR files are picked up by the existing checks 2 and 4 with no change. `REQUIRED_DOCS`
  stays as it is — ADRs are discovered, not enumerated. Assertion 7 must exempt this plan's
  `## Scope Amendment` and `## Original Request`, which quote the superseded scope deliberately; scope the
  scan to `owned_markdown()`, which already prunes `plans/`.

  Logging: follow the script's existing contract exactly. Use `error` and `warn` for findings, `trace` for
  per-file detail behind `DEBUG=1` / `LOG_LEVEL=debug`, and `section` for the heading. Emit one `trace` line
  per ADR scanned, and one summarising the count. Exit codes stay `0` clean / `1` blocked / `2` warnings /
  `3` usage error.

  Run it and confirm it exits `0` before marking this task done. A check that has never failed has not been
  tested: temporarily break one assertion, confirm exit `1`, then restore.

- [x] **Task 11: Roadmap update and documentation checkpoint** (depends on 10)

  - Run `bash scripts/check-dual-schema-docs.sh` and confirm exit `0`.
  - Mark roadmap milestone **"Open Decisions Closed"** `[x]` in `.ai-factory/ROADMAP.md` and add its row to
    the Completed table with the real completion date. This is the one roadmap edit `/aif-implement` is
    permitted to make, and only because the evidence is unambiguous.
  - Milestones 7 and 8 need no revision — ADR 0001 confirms the knowledge base and validators are built
    rather than borrowed, which is what they already describe. If ADR 0004 moved a scaffold skill earlier,
    report that milestone 12 needs reordering and let the user run `/aif-roadmap`; do not edit roadmap
    structure here.
  - Mandatory docs checkpoint: run `/aif-docs` for the `docs/adr/` addition.

  Logging: report the check script's exit code verbatim.

---

## Out of Scope (deliberate)

- **Reconciling with any other DGF agent-tooling effort.** Settled by `## Scope Amendment` and recorded in
  ADR 0001. Reintroducing it is a regression caught by Task 10 assertion 7.
- **`RULES.md` itself** — owned by `/aif-rules`. ADR 0005 decides its default content; it does not write it.
- **Roadmap restructuring** — owned by `/aif-roadmap`. Task 11 may tick milestone 5 and nothing else.
- **`.claude-plugin/plugin.json`, `knowledge/`, validators, `dgf-*` skills** — milestones 6–9.
- **Pushing `main`.** The dual-schema merge is local; `main` is 4 commits ahead of `origin/main`. Pushing is
  the user's call.

## Risks

| risk | mitigation |
|---|---|
| ADR 0001 reopens a decision the user already made | Task 2 carries an explicit STOP condition: record disagreement as a follow-up in Consequences and report it, rather than writing a hedged ADR. |
| Tasks 5 and 6 need the user present | Both are marked as blocking on user input. Unattended execution must stop, not invent answers attributed to the team. |
| ADR 0003 over-gates the fact base | Task 4 decides stamp-versus-gate per fact class explicitly, and records that an over-gated fact base goes stale as fast as an unstamped one. |
| Generalising the check script blurs its name | Accepted deliberately: the filename is referenced from three places. The header records the mismatch. |
| Finding 1's semantic-gap proof is load-bearing for ADR 0002 | It rests on three first-party artifacts that were read directly: the absent `xs:key`/`xs:keyref` in `process.xsd`, the artifact-type rejection at `XmlCrossReferenceValidator.cs:94`, and the commented-out process branch in `DiagnosticCheckService`. Re-verify these three if ADR 0002's conclusion is challenged. |
