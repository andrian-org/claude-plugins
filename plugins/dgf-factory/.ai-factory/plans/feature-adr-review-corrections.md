# Implementation Plan: ADR Review Corrections

Branch: feature/adr-review-corrections
Created: 2026-09-23
Refined: 2026-09-23 — `/aif-improve`: CHANGE_STATE cross-reference (E20), JSON dialect constraint (E21), exact
citation sites, per-task index rows; blueprint relinks moved into Task 6 so every commit passes the check
Base: `develop` at `a2d86c5`. `config.yaml` names `main` as `git.base_branch`, but `main` (`0e28010`) is 20
commits behind `develop` and lacks milestones 6–7, which this plan edits. The branch is cut from `develop` and
merges back into it.

## Original Request

Close ADR gaps found in the ADR review: supersede ADR 0002 §1-2 with process semantic rules grounded in runtime evidence (End terminal pseudo-state exemption; unreachable-state is warning unless workflow CHANGE_STATE targets and OnTimeout edges are collected across the workspaces root; XSD lags runtime deserializer — 2/23 samples fail with ftitle/StoredProcedure/StoredProcedureActivity; handler resolution is WORKFLOW: reference resolution; add validationFlow and SubProcess references; fix TransitionType citation L127-133); new ADR for validator runtime and dependencies (Python stdlib has no XSD/JSON Schema validation); new ADR amending ADR 0003 range semantics and version-source rationale (already overridden by knowledge/README.md §1.1 and §3); errata to ADR 0005 (enforcement counts 4 enforceable/3 prompt-only, RULES.md owner /dgf-rules not /aif-rules, rule 7 incomplete vs WorkspaceSettings.cs constants); later ADRs: plan-ledger contention at workspaces-root (before milestone 9), /dgf-implement meaning (blueprint Q4, only substantially answered), schema-family and runtime-parity authority (format-coverage.md, XML-always until Wave 1.5). Update ADR index, blueprint ANSWERED blocks, roadmap milestone 8 wording, and keep scripts/check-dual-schema-docs.sh passing.

## Settings

- Testing: yes. Extend `scripts/check-dual-schema-docs.sh` §5 with supersession-integrity assertions, and prove
  each one fires against a mutated scratch copy. Mutated copies are never committed.
- Logging: verbose. Every new script assertion routes through the script's existing `trace` / `warn` / `error`
  helpers, so `DEBUG=1` gives a per-ADR trace.
- Docs: yes. Mandatory documentation checkpoint at completion, through `/aif-docs`.
- Supersession style: **full supersede**. 0006 replaces 0002 and 0008 replaces 0003, each restating the sections
  that stay valid. The status vocabulary is unchanged (`proposed|accepted|rejected|superseded-by-NNNN`).
- Later ADRs: 0009–0011 are drafted as **`proposed`**. Accepting them needs a separate interview before
  milestone 9, which is out of scope here.
- Scope: decision records and their propagation only. No validators, no `knowledge/` facts, no `dgf-*` skills.
  Milestone 8 builds; this plan corrects its inputs.

## Roadmap Linkage

Milestone: "Deterministic Validators"
Rationale: The milestone's four process checks and its validator runtime rest on ADR 0002 and an undecided
runtime. This plan corrects both before any validator code is written.

## Task Ledger Note

`TaskCreate` / `TaskUpdate` are not available in this session. The checkbox list under `## Tasks` is the
**single** progress ledger. `/aif-implement` updates the checkboxes here and nowhere else.

## Evidence Base

This section was read on 2026-09-23 from the DGF repository at `aa1d5c4c2` (`develop`). Implementers cite from
here, re-read before citing, and must not re-derive anything.

| # | Finding | Source |
|---|---|---|
| E1 | `End` is a terminal state reserved by the runtime and never declared as a `State`. A transition to it completes the instance. | `src/Core/DGF.OM/Process/StateProcess/InstanceHandler.cs:291,367,392,409` |
| E2 | Naive dead-transition: **23/23** sample processes flagged, all on `End` only | the 23 files at `src/samples/workspaces/*/FM/_PROCESS/*/process.xml` |
| E3 | Naive unreachable-state (walk from `OnStart/Transitions`): **17/23** flagged | same corpus |
| E4 | A workflow `CHANGE_STATE` step moves an instance to any named state. `GoToStateAsync` only checks that the state exists, not that a transition declares it. **15** sample workflows use `CHANGE_STATE`. | `src/Core/DGF.DataViewer/Workflow/SequenceWorkflow.cs:552-558`; `src/Core/DGF.DataViewer/Process/StateProcessClient.cs:922`; `InstanceHandler.cs:334-372`; `src/samples/workspaces/*/FM/_WORKFLOW` |
| E5 | `StartWorkflowInstanceAsync(…, initialState, …)` starts at a caller-named state | `InstanceHandler.cs:250-259` |
| E6 | `OnTimeout` names a target state (`currentState.OnTimeout.StateName`) and is absent from `process.xsd`. No sample uses it. | `src/Core/DGF.Domain/Process/StateProcess/State.cs:37`; `InstanceHandler.cs:349-357` |
| E7 | **2/23** samples fail `process.xsd` while using constructs the runtime deserializer binds: `ftitle` (3×), `type="StoredProcedure"`, `<StoredProcedureActivity>` | `PrintDeliver`, `DGF.Demo.EService`; `State.cs:13,16`; `AbstractStateEvent.cs:10` |
| E8 | The runtime model binds attributes the XSD lacks: `State/@fdesc`, `State/@ftitle`, `State/OnTimeout`, `Process/@hideDesc` | `State.cs`, `Process.cs:20` |
| E9 | All 172 `action` values in the samples are `WORKFLOW:` references, some `WORKFLOW:/BASE:…`. There are 45 `BASE:` occurrences in process files. | the sample corpus |
| E10 | `Process/@validationFlow` carries references such as `BASE:EDefaultProcessValidation` | `webasm/FM/_PROCESS/*/process.xml` |
| E11 | `SubProcess` exists only as an XSD enum value. It has no sample and no reference in `DGF.Domain/Process` or `DGF.OM/Process`. | `process.xsd` `StateTypeEnum`; grep 2026-09-23 |
| E12 | `TransitionType` is at `process.xsd` **L127-133**; the file has 135 lines and is unchanged since `b459e52bc` (2026-05-19). ADR 0002 cites L137-143. | `src/Tools/dgf-mcp/Schemas/XSD/process.xsd` |
| E13 | `WorkspaceSettings.cs:12-23` constants: `FM`, `_LOOKUP`, `_PROCESS`, `_DATA`, `_COMPONENTS`, `_DataSources`, `_SiteMaps`, `_EndPoints`, `_PROFILE`, `_WORKFLOW`, `_STORAGE`, `Services`. `Templates` lives in `DGF.Kernel/Settings.cs:11`. `_DATACALLS` exists on disk but is **not** a constant. | `src/Core/DGF.Kernel/WorkspaceSettings.cs`, `Settings.cs` |
| E14 | ADR 0005 tags rules 1 and 7 as script, 2 and 3 as gate, and 4, 5 and 6 as prompt-only, so four are enforceable and three are prompt-only. Its Consequences say "three" and "four". | `docs/adr/0005-default-team-rules.md` |
| E15 | ADR 0005 names `/aif-rules` as the owner of `RULES.md`. The blueprint's Q7 answer (`docs/blueprint.md:382`) names `/dgf-rules`. `aif-*` does not ship (ADR 0001). | both files |
| E16 | `knowledge/README.md` §1.1 replaces ADR 0003's version-source rationale ("lagging stamp") with determinism, and §3 redefines `until: null` as open-ended while fixing `since: null` as "no known lower bound". No ADR records either change. | `knowledge/README.md` |
| E17 | Python's stdlib has no XSD or JSON Schema validation. `xmllint` (libxml2) validates `process.xsd` locally. | used during the review |
| E18 | `format-coverage.md` calls XML-always a **Wave 1** policy, to be replaced in **Wave 1.5** when the capability matrix becomes an MCP tool. The trigger is the page going stale under `/dgf-freshness-audit`. | `docs/wiki/AI-Authoring/format-coverage.md:15,138,143` |
| E19 | The check script's §5 greps any blueprint line containing `ANSWERED`, including "SUBSTANTIALLY ANSWERED", and errors if it cites a `proposed` ADR | `scripts/check-dual-schema-docs.sh` §5 |
| E20 | A workflow names its target as `<StateProcess mode="CHANGE_STATE" process="…" state="…" applyforstates="…">`. There are 21 such steps in the samples, all with literal values, and `process` may be `BASE:`-prefixed. `RecordState899` is both the most common target (6×) and a state the naive walk flags as unreachable (E3). Targeted processes `ZIMS4_*` are **absent** from the samples, so the samples are an incomplete workspaces root. | `src/samples/workspaces/webasm/FM/_WORKFLOW/Incident_Process_OnHoldCancel/_workflow.xml:19`; `src/samples/workspaces/*/FM/_WORKFLOW` |
| E21 | The vendored `json/` set mixes **68 draft-04** schemas (from `SchemaExporter`) with 1 draft-07; `standalone/` is all draft-07. The dialect has to be chosen per file from its `$schema`. | `knowledge/schemas/MANIFEST.md` §2.1 |

## Commit Plan

- **Commit 1** (after tasks 1-2): `test: assert ADR supersession integrity`
- **Commit 2** (after tasks 3-6): `docs(adr): supersede 0002 and 0003, decide validator runtime`
- **Commit 3** (after tasks 7-8): `docs(adr): record 0005 errata and propagate successors`
- **Commit 4** (after tasks 9-11): `docs(adr): propose ledger, implement and parity decisions`
- **Commit 5** (after task 12): `docs: record the corrected decision set`

## Tasks

### Phase 1: Contract and test

- [x] **Task 1: Extend the ADR contract in `docs/adr/README.md`.**
  Add three things:
  - **Errata:** an ADR may be edited in place **only** to correct a fact that does not change its decision. Each
    correction is listed in a dated `## Errata` section at the end of the ADR (date, what was wrong, what is
    right, source). Anything that changes what the ADR decides needs a superseding ADR.
  - **Full supersession:** a successor restates every still-valid section of the ADR it replaces. Readers
    never need to combine two ADRs. The old ADR changes only `status` and `date`.
  - **Proposed ADRs:** an ADR with status `proposed` may not be cited from a blueprint line containing
    `ANSWERED` (E19). A pending decision is cited from a separate `> **DECISION PENDING**` line.

  Files: `docs/adr/README.md`. Logging: n/a (prose).

- [x] **Task 2: Add supersession-integrity assertions to `scripts/check-dual-schema-docs.sh` §5.** (depends on 1)
  1. `status: superseded-by-NNNN` → `NNNN-*.md` exists **and** its frontmatter `supersedes` lists the old id.
     Parse only the inline YAML list form the existing ADRs use (`supersedes: []`, `supersedes: [0002]`,
     `supersedes: [0002, 0003]`). Any other form is an `error`, not a silent skip.
  2. Every id in a `supersedes` list names an ADR whose status is `superseded-by-<this id>`.
  3. No blueprint line containing `ANSWERED` links a superseded ADR as `adr/NNNN-*.md`. Plain-text mentions
     such as "originally ADR 0002" are allowed.
  4. The Status cell (the third `|`-delimited column of the index table in `docs/adr/README.md`) of the row
     linking `(NNNN-*.md)` equals that ADR's frontmatter status.
  5. If an `## Errata` section is present, every entry starts with a `YYYY-MM-DD` date. Violations are a `warn`.

  Logging: every assertion calls `trace "<rel>: supersedes=<…> successor=<…>"` under `DEBUG=1`. Violations use
  `error` (1–4) or `warn` (5), never bare `echo`. Exit codes stay as defined in `.ai-factory/rules/base.md`.
  Update the header comment (it lists the contracts it guards).

  **Test:** in the scratchpad, copy the plugin, inject one fault per assertion (five copies), and confirm each
  exits `1`, or `2` for assertion 5, with the expected message. Then confirm the unmutated tree exits `0`. Do not
  commit the mutated copies. Files: `scripts/check-dual-schema-docs.sh`.

<!-- Commit checkpoint: tasks 1-2 -->

### Phase 2: Superseding and urgent ADRs

- [x] **Task 3: Write ADR 0006, "Process verification: structure with a runtime-divergence allowance, semantics
  by our own validators" (`supersedes: [0002]`).** (depends on 1)
  Restate 0002 §3 (vendored XSDs, in-process validation, no MCP dependency) and §4 (no runtime claim,
  Playwright out of the gate, `checks_run`) unchanged in substance. Replace §1–§2:
  - **Structure:** XSD failures are blocking **except** failures on constructs the runtime deserializer binds
    (E7, E8). Those are reported as `xsd-runtime-divergence` warnings (exit `2`). The divergence list becomes a
    stamped structural fact in `knowledge/` under milestone 8 (not written here), derived from `State.cs`,
    `Process.cs` and `AbstractStateEvent.cs`.
  - **Revised check table:**

    | check | rule | severity |
    |---|---|---|
    | dead transition | every `Transition/@state` (under `OnStart`, `State` and `OnTimeout`) names a declared `State/@name` **or the reserved `End`** (E1) | blocking |
    | unreachable state | entry set = `OnStart` transitions ∪ `CHANGE_STATE` targets for this process across the workspaces root (E4, ADR 0004) ∪ `OnTimeout` edges (E6) | **warning**, because entry via `StartWorkflowInstanceAsync` (E5) cannot be seen statically |
    | workflow-reference resolution | every `WORKFLOW:` action on `OnStart`, `State` and `Transition` resolves under `_WORKFLOW` in the workspace or, for `BASE:`, in `webasm` (E9). This replaces "handler resolution" and absorbs the process `BASE:` row. | blocking |
    | validation-flow resolution | `Process/@validationFlow` resolves the same way (E10) | blocking |
    | change-state target resolution | every workflow `<StateProcess mode="CHANGE_STATE">` has a `process` that resolves (a `BASE:` value resolves into `webasm`), and its `state` and each `;`-separated `applyforstates` entry name a declared state of that process or `End` (E20). This is the dead-transition defect seen from the workflow side. | blocking |

  - `SubProcess` references are **deferred, not committed**, with the reason from E11 recorded.
  - Context: E1–E12, with the corrected `TransitionType` citation (E12), and the empirical result that the naive
    0002 rules fail the shipped corpus (E2, E3, E7).
  - Follow-ups:
    - the 23 samples become milestone 8's **known-good** corpus: zero errors required, warnings allowed and
      listed. The samples are an **incomplete** workspaces root (E20: `ZIMS4_*` processes are targeted but
      absent), so the corpus run must declare the missing processes as expected-external and must not pass
      them silently;
    - the upstream `xs:keyref` proposal carries over;
    - upstream XSD lag (E8) is reported to the DGF team.

  **Present the Decision section to the user and get confirmation before setting `status: accepted`.**
  Files: `docs/adr/0006-process-verification-revised.md`.

- [x] **Task 4: Write ADR 0007, "Validator runtime and dependencies".** (depends on 1)
  Context: E17; `DESCRIPTION.md` allows Node `.mjs` and Python 3; `doctor.py` and `check_knowledge_stamps.py` are
  stdlib-only; the plugin-install model (check the `plugin-structure` skill for whether a plugin can declare or
  install dependencies).
  **Hard criterion (E21):** the runtime must validate both **draft-04** (68 generated schemas) and **draft-07**,
  choosing the dialect per file from its `$schema`. Python `jsonschema` covers both; `ajv` needs a separate
  draft-04 package; a stdlib-only JSON path has no validator. Reject any option that fails this criterion.
  Weigh these options:
  - **(a)** Python + `lxml` + `jsonschema`, pinned;
  - **(b)** Python stdlib plus `xmllint` for XSD, with JSON Schema in stdlib or a vendored validator;
  - **(c)** Node + `ajv` + an XSD binding;
  - **(d)** a .NET tool reusing DGF's `XsdValidationService`.

  For each, record availability on macOS, Linux and CI, the install path for a consumer, dialect coverage, and
  what happens when the dependency is missing. The missing-dependency behaviour must be to report and exit `3`
  (usage), never a silent pass.

  **Decide this by a structured interview with the user**: AskUserQuestion with the options and a
  recommendation. Record their answer as the Decision, status `accepted`. Files:
  `docs/adr/0007-validator-runtime.md`.

- [x] **Task 5: Write ADR 0008, "Stamp every fact, gate only behavioural ones (revised)"
  (`supersedes: [0003]`).** (depends on 1)
  Restate 0003 §2–§4 (fact classes, out-of-range behaviour, gate carried by this plugin) in substance. Replace:
  - the version-source rationale with **determinism**, per `knowledge/README.md` §1.1 (E16). Keep the
    `ClientDebug` defect and the lag against tags 1.1.12–1.1.15 as negatives.
  - the range semantics: `until: null` is open-ended; `since: null` means "no known lower bound, never a floor
    value". Worked example: `since: "1.1.15"` with `dgf_version: "1.1.11"` is coherent.

  Mark 0003's follow-up on `applies.since` as discharged by `knowledge/README.md` §3. Status `accepted` (this
  records a convention already in force). Files: `docs/adr/0008-version-gating-revised.md`.

- [x] **Task 6: Flip the superseded ADRs, update the index, and relink the blueprint answers.** (depends on 3, 4, 5)
  - Set 0002 to `status: superseded-by-0006` and 0003 to `status: superseded-by-0008`, with `date: 2026-09-23`
    on both. Change no other text in either.
  - In `docs/adr/README.md`, add rows for 0006, 0007 and 0008, and update the 0002 and 0003 status cells.
  - In `docs/blueprint.md`, update the Q5 and Q6 `ANSWERED` blocks: add a `Revised (2026-09-23)` sentence and
    relink them to 0006 and 0008. Mention 0002 and 0003 as plain text only (E19, assertion 3). Question text
    is never edited.
  - Run `bash scripts/check-dual-schema-docs.sh`. It must exit `0`: the flip and the relink land together so
    commit 2 is green.

  Files: `docs/adr/0002-*.md`, `docs/adr/0003-*.md`, `docs/adr/README.md`, `docs/blueprint.md`.

<!-- Commit checkpoint: tasks 3-6 -->

### Phase 3: Errata and propagation

- [ ] **Task 7: Add a dated `## Errata` section to ADR 0005.** (depends on 1)
  Correct four things:
  - the enforceable/prompt-only counts (E14), fixing the Positive and Negative bullets in place;
  - the `RULES.md` owner, which becomes `/dgf-rules` (E15; `/aif-rules` does not ship);
  - rule 7's directory list, aligned with E13. List every `WorkspaceSettings.cs` constant, note `Templates`'
    separate source, and record that `_DATACALLS` is on disk but not a constant, so the script must not require
    it.
  - Cite `knowledge/naming-conventions.md:27-29`, which already lists every constant, as corroboration. The
    stamped fact is correct and is not edited.

  Also add `docs/adr/0002` L137→L127 as an erratum **in 0006's Context** (0002 itself is frozen once
  superseded). Files: `docs/adr/0005-default-team-rules.md`.

- [ ] **Task 8: Point the remaining live documents at the successors.** (depends on 6)
  The blueprint relinks already happened in Task 6. The header note moves to Task 10.
  - `knowledge/README.md`:
    - repoint ADR 0003 citations to 0008;
    - replace the §3 "superseded by this section" blockquote with a one-line pointer to 0008;
    - change "where this file and the ADR disagree, this file wins" to state that they now agree;
    - leave the stamp frontmatter untouched, because README is exempt.
  - `docs/dgf-knowledge.md`: L16 and L138 0003 → 0008; L137 0002 → 0006.
  - `.ai-factory/ROADMAP.md`: reword milestone 8 to name the checks from 0006 plus the runtime from 0007, and
    repoint "Gate Contract Wired" to 0006. **This file is owned by `/aif-roadmap`, so route the edit through
    it.**
  - `.ai-factory/DESCRIPTION.md`: L76, L97 and L171 0002 → 0006 (L171's "§4" becomes 0006 §4, restated);
    L98 0003 → 0008. The file is owned by `/aif`, so route through the owner, or record it as a follow-up if the
    owner cannot run in this session. Until then the old links still resolve, because superseded ADRs are
    kept.

  Leave historical ADRs (0004's links to 0002) and archived plans unchanged. Logging: n/a. Run the check script;
  it must exit `0`. Files: the ones listed above.

<!-- Commit checkpoint: tasks 7-8 -->

### Phase 4: Proposed ADRs (status `proposed`)

Each proposed ADR has Context (cited), **Options** with trade-offs, a **Recommended** option, and a stated
**Decision trigger**: the milestone it must be accepted before. `## Decision` holds the recommendation, marked
as not yet accepted, and must be at least 200 characters (the script warns otherwise). **Each task adds its own
`proposed` index row in `docs/adr/README.md`**, because the script errors on any ADR without a row, and runs the
check script to exit `0` before finishing.

- [ ] **Task 9: ADR 0009, "Plan ledger at workspaces-root scope".** (depends on 1)
  - Context: ADR 0004's contention follow-up; `workflow.plan_id_format` values in `config.yaml`; single-writer
    ownership.
  - Options: per-application `plan_id` prefix; a plan-level `affects_workspaces` field plus a lock check; a
    per-workspace ledger under one root.
  - Trigger: before milestone 9.

  Files: `docs/adr/0009-plan-ledger-scope.md`, `docs/adr/README.md`.

- [ ] **Task 10: ADR 0010, "What `/dgf-implement` implements".** (depends on 1, 6. Task 6 also edits
  `docs/blueprint.md`.)
  - Context: blueprint Q4 ("SUBSTANTIALLY ANSWERED"), `format-coverage.md`, and ADR 0005 rule 2.
  - Options: configuration-composer with code as an exception; symmetric code and config; config-only with code
    handed off.
  - Trigger: before milestone 9.
  - Add a `> **DECISION PENDING** — [ADR 0010](adr/0010-…)` line under blueprint Q4, on a line without the word
    `ANSWERED` (E19).
  - Fix the blueprint section-header note "All seven are now closed", which becomes six closed with #4 pending
    ADR 0010. That note must not contain the word `ANSWERED` together with the 0010 link.

  Files: `docs/adr/0010-dgf-implement-scope.md`, `docs/blueprint.md`, `docs/adr/README.md`.

- [ ] **Task 11: ADR 0011, "Schema-family resolution and the runtime-parity authority".** (depends on 1)
  - Context: `AGENTS.md` "Both schema families" rule, `docs/dgf-schemas.md`, and E18. It also records Workflow
    and ProcessFlow as validated but ignored by the runtime.
  - Decision to propose: `format-coverage.md` is the sole parity authority; XML-always holds until DGF Wave 1.5;
    the review trigger is `knowledge/composition-specs.md`'s `review_date` plus re-vendor.
  - Options: static page as authority; wait for the MCP matrix; derive parity from runtime deserializers.
  - Trigger: before milestone 8's parity check is written.
  - Add the ADR to `docs/dgf-schemas.md` See Also.

  Files: `docs/adr/0011-schema-parity-authority.md`, `docs/dgf-schemas.md`, `docs/adr/README.md`.

<!-- Commit checkpoint: tasks 9-11 -->

### Phase 5: Verification and docs

- [ ] **Task 12: Run the gates and the documentation checkpoint.** (depends on 2-11)
  - Run `bash scripts/check-dual-schema-docs.sh`: exit `0`.
  - Run `python3 scripts/check_knowledge_stamps.py`: exit `0`.
  - Run `python3 skills/dgf-doctor/scripts/doctor.py`: no new findings.
  - Run `git diff --check` and confirm LF endings only.
  - Run the `/aif-docs` checkpoint:
    - `AGENTS.md` Agent Rules: the decision list adds validator runtime, and 0006/0008 replace 0002/0003;
    - `AGENTS.md` Documentation table: the ADR row description;
    - `README.md` if it cites decisions.

  Record any owner-routed edit that could not run (Task 8) as an explicit follow-up in this plan.
  Files: as reported by `/aif-docs`.

<!-- Commit checkpoint: task 12 -->

## Risks

- **ADR 0006's divergence allowance can hide real XSD errors** if the list is built loosely. It must be derived
  only from `[XmlElement]`/`[XmlAttribute]` bindings in the three runtime model files, never from "what the
  samples happen to use".
- **Task 4 blocks on the user's answer.** If the interview cannot happen, write 0007 as `proposed` and flag
  milestone 8 as blocked. Do not guess the runtime.
- **Single-writer edits (Task 8)** may need owner commands that assume an interactive session. Deferring with a
  recorded follow-up is acceptable; hand-editing `ROADMAP.md` or `DESCRIPTION.md` is not.
