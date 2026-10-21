# Project Roadmap

> A Claude Code plugin that arrives already knowing the DotGov Framework, then runs the
> plan → implement → verify pipeline against the system built with it — backed by
> deterministic, dual-schema, parity-aware validators rather than prompt heuristics.

## Milestones

- [x] **Design Blueprint** — AI Factory teardown, DGF mapping, build order, `dgf-gate-result` schema
- [x] **Pipeline Bootstrap** — `.ai-factory/` config, DESCRIPTION, ARCHITECTURE, base rules, MCP wiring
- [x] **Verified DGF Fact Base** — dual-schema and runtime-parity model made the canonical contract, guarded by a consistency check
- [x] **Reader-Facing Documentation** — README landing page, six `docs/` pages, `AGENTS.md` navigation index
- [x] **Open Decisions Closed** — record the independent, AI Factory-derived delivery model; answer blueprint open questions #3, #5, #6, #7
- [x] **Plugin Manifest & Walking Skeleton** — `.claude-plugin/plugin.json` plus one loadable skill, so Claude Code can discover the plugin at all
- [x] **DGF Knowledge Base** — `knowledge/` facts tree and the vendored JSON/XSD schema set; every fact stamped `dgf_version` + `read_date` + per-source `sha256`, behavioural facts additionally carrying a `since`/`until` range, with a `MANIFEST.md` recording the DGF commit SHA and a re-vendor process ([ADR 0003](../docs/adr/0003-version-gating.md))
- [x] **Deterministic Validators** — Python validators under `scripts/` on `lxml` + `jsonschema`, pinned in `scripts/requirements.txt`, with a missing dependency reported as exit `3`. They resolve the schema family before parsing, resolve components, and check runtime parity against the shipped parity table in `knowledge/schema-families.md` §6 before reporting success; extend that table to every `format-coverage.md` row first, and script ADR 0010's order-of-means route from it. Also: the NJsonSchema inheritance pre-pass; ADR 0014's process checks (XSD structure with a runtime-divergence allowance, dead transition exempting `End`, unreachable state as a warning, and workflow-reference, validation-flow and change-state target resolution); known-good (DGF samples) and known-bad fixture corpora, which pass the doctor's `DGF_PATH` check or live outside the shipped directories; and the drift check, a maintainer tool in `tools/` that compares the `provenance/` ledgers against a DGF checkout. Accept ADR 0011 and correct `knowledge/naming-conventions.md` before the parity check lands ([ADR 0010](../docs/adr/0010-dgf-implement-scope.md), [ADR 0012](../docs/adr/0012-no-dgf-paths-in-shipped-files.md), [ADR 0013](../docs/adr/0013-version-gating-provenance-ledger.md), [ADR 0014](../docs/adr/0014-process-verification-runtime-resolution.md), [ADR 0015](../docs/adr/0015-validator-runtime-and-json-reader.md), [ADR 0016](../docs/adr/0016-legacy-xsd-lag.md))
- [x] **Pipeline Spine** — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit` with DGF domain content over the AI Factory step structure. The plan header carries ADR 0009's `affects_workspaces` and ADR 0010's per-task `kind: config | code` with a `reason`. `/dgf-implement` composes modern JSON under `FM/_COMPONENTS/` first, legacy XML only where no JSON alternative exists, and a little JS/CSS only for `kind: code` tasks. The plan format, its checks and discovery are scripts; gates block only on findings the branch introduced, against the merge-base; `/dgf` records the estate's declared DGF version ([ADR 0009](../docs/adr/0009-plan-ledger-scope.md), [ADR 0010](../docs/adr/0010-dgf-implement-scope.md), [ADR 0017](../docs/adr/0017-plan-file-format.md), [ADR 0018](../docs/adr/0018-change-relative-gates.md), [ADR 0019](../docs/adr/0019-declared-dgf-version.md))
- [x] **Gate Contract Wired** — `dgf-gate-result` blocks carrying `schema_family`, `checks_run`, affected components and affected processes, last-block-wins; a gate may never read as having passed a check it did not run. `scripts/lib/gate_result.py` builds every block, the doctor's included — until then the doctor's always reported `"blocking": true` and suggested the unbuilt `/dgf-fix`, even on a pass — with `blocking` true exactly when `status` is `fail`. Also: `check_plan.py` checks that a plan's Commit Plan groups agree with its task numbering, which had been left to the model ([ADR 0014](../docs/adr/0014-process-verification-runtime-resolution.md), [ADR 0020](../docs/adr/0020-gate-block-contract.md); plan in `archive/plans/feature-gate-contract-wired.md`)
- [x] **Learning Loop** — `/dgf-fix` and `/dgf-evolve`, turning DGF gotchas into patches and skill-context overrides. `/dgf-fix` works only inside the active plan's scope — it reproduces first, lets `check_change.py --skip-validators` decide the scope before any edit, and confirms the fix with the same check — and writes a patch after every fix; `--record` writes one with no change. An override may only tighten a skill — add rules and checks, never relax a STOP, an exit-code row, the status a gate script computes, a Critical Rule or Artifact Ownership — because anyone who commits to the estate can write one. `check_override.py` checks every override before any of the six readers reads it, and a refused one is never read; `/dgf-evolve` writes within that limit, asks first, and reads no override of its own. `/dgf-fix` joins the `verify` gate's allowlist, and the gate suggests it for a finding the branch introduced once the tasks are done and the scope is clean. The doctor's allowlist stays `null`: a broken install is reinstalled, not fixed in the estate — a departure from this milestone's first wording, "the `verify` and `doctor` allowlists", decided in ADR 0022 §8 ([ADR 0021](../docs/adr/0021-learning-loop.md), [ADR 0022](../docs/adr/0022-gate-block-contract-revised.md); plan in `plans/feature-learning-loop.md`)
- [x] **DGF-Specific Skills** — `/dgf-component`, `/dgf-process`, `/dgf-audit`, `/dgf-model` and `/dgf-scaffold`. `/dgf-component`, `/dgf-process` and `/dgf-model` inspect and validate anywhere and write only inside the active plan's scope, each only the artifacts it owns; `validate_model.py` joins the gate, blocking a model reference only where its loader throws; `/dgf-audit` reports the root's health and blast radius per application from one reference graph — the processes a changed shared workflow reaches, which the verify gate's `affected_processes` leaves out ([ADR 0022](../docs/adr/0022-gate-block-contract-revised.md) §6) — never as a gate, with its limits on every reach; roles are an inventory. Without git, `/dgf-process` and `/dgf-model` settle their write against a baseline `check_change.py` saved before it, never the gate's. `/dgf-scaffold` no longer **drives a bootstrap template**, since first-party DGF has none: it creates a whole application from an empty folder, rendered from its own shipped templates and one design file, `docs/application.json`, checks the result over the generated workspaces only, and hands the root to `/dgf`. Its output builds and checks clean but has not been run against a live DGF; what that leaves unverified is listed in its plan's Results ([ADR 0026](../docs/adr/0026-authoring-entry-point-revised.md), [ADR 0027](../docs/adr/0027-dgf-specific-skills-revised.md), [ADR 0024](../docs/adr/0024-learning-loop-revised.md), [ADR 0025](../docs/adr/0025-saved-baseline-without-git.md); plans in `plans/feature-dgf-specific-skills.md` and `plans/feature-dgf-scaffold.md`)
- [ ] **Quality & Authoring Skills** — `/dgf-review`, `/dgf-rules`, `/dgf-rules-check`, `/dgf-qa`, `/dgf-docs`, `/dgf-explore`, `/dgf-grounded`, `/dgf-archive`
- [ ] **Parallel Execution** — coordinator and worktree-isolated workers
- [ ] **Marketplace Release** — register `dgf-factory` in `.claude-plugin/marketplace.json` and verify a clean install, with `/dgf-doctor` clean, including no DGF paths in shipped files. First decide whether maintainer material (`docs/`, `.ai-factory/`, `tools/`, `provenance/`) must also leave the plugin folder ([ADR 0012](../docs/adr/0012-no-dgf-paths-in-shipped-files.md) follow-up), and whether `/dgf`, `/dgf-plan`, `/dgf-implement` and `/dgf-commit` can stop pre-approving every git command (`Bash(git *)`) — their `git -C "<root>" <subcommand>` form needs a wildcard before the subcommand, which Claude Code warns about

## Follow-ups

Task-sized items from finished milestones that no open milestone owns. Pick one up when its area next changes. The detail is in the archived plans under `archive/plans/`.

- **Gate entry summaries.** The 240-character cap cuts the doctor's `VALIDATOR_DEPS_MISSING` entry inside its install command; the `WARN` line above the block carries it whole. Consider a per-entry `fix` field, or a shorter summary that leaves the command to the prose ([ADR 0022](../docs/adr/0022-gate-block-contract-revised.md) §3; `feature-gate-contract-wired.md`, Task 11)
- **`/dgf-commit` reads the Commit Plan from a script.** `lib/plan.py` now parses the groups (`Plan.commits`) and `check_plan.py` checks them, but `/dgf-commit` still parses the prose itself (`feature-gate-contract-wired.md`)
- **A test for `PLAN-FORMAT.md`'s worked example.** Run it through `check_plan.py`, so `RULES.md` rule 4 stops being kept by hand for `/dgf-plan` (`feature-pipeline-spine.md`)
- **Harvest the patches.** Fold what the estates' patches keep teaching into the shipped `knowledge/`, with provenance, and turn `findings: none` patches — problems no validator catches — into validators. Maintainer work: knowledge changes only by a deliberate edit ([ADR 0024](../docs/adr/0024-learning-loop-revised.md) §8; `feature-learning-loop.md`)
- **`/dgf-transfer`.** Port verified rules between estates, if estates ever share rules across roots; today each has one `.dgf-factory/` and no sibling to port from (ADR 0024 §8)
- **`/dgf-commit` places a patch with its fix.** A patch maps to no Commit Plan group, so `/dgf-commit` asks where it goes; it could put a patch in the group of the files it records (`feature-learning-loop.md`, R5)
- **`/dgf-implement` reads patches through `check_patches.py`**, skipping malformed ones, instead of reading the last ten files by name (`feature-learning-loop.md`)
- **A delete for `/dgf-evolve`.** It pre-approves no git and no Bash beyond the plugin's scripts, so an override emptied of rules, or a new one still refused after three attempts, is left for the user to delete. Every reader refuses such a file meanwhile, which is safe but noisy (`feature-learning-loop.md`, Task 8)
- **Patch timestamps.** `/dgf-fix` names a patch by the current minute, but no tool it pre-approves reads the clock, so the model supplies it; `check_patches.py` holds the name and the `date` field equal, not true. A script could print the next free name (`feature-learning-loop.md`)
- **The baseline's two trees.** The working-tree run validates git-ignored and symlinked files that the materialised base tree never holds, so a finding in one always counts as new — stricter, never looser. Decide whether the head run should skip what `git ls-files --others --ignored --exclude-standard` lists, and symlinks ([ADR 0018](../docs/adr/0018-change-relative-gates.md); `feature-pipeline-spine.md`)
- **`/dgf-plan` records reach.** For a task that touches a shared workflow, run `audit_root.py --reach` and write the reached processes into the plan as regression notes (ADR 0023 follow-ups; `feature-dgf-specific-skills.md`)
- **Promote the unchecked workflow edges.** The `reference-edges` rows whose `Checked by` is `—` and whose loader throws — `sub-workflow`, `invoke-table`, `record-table`, `island-table`, `datasource-step` — are audit warnings today; make them blocking validator checks. This extends ADR 0014's deferred list (`feature-dgf-specific-skills.md`)
- **Trace entry points outside processes.** `_PROFILE` trees, sitemaps, `_form.xml` and view `WORKFLOW:` strings, and JSON `workflow` components start workflows no process names; `profile.xsd` does not compile, so this needs a grammar first (ADR 0023 §8)
- **A role check**, if an estate ever keeps its roles list in the root (ADR 0023 §6)
- **`inventory_root.py` counts entities** per workspace (`feature-dgf-specific-skills.md`)
- **Parse XML as the runtime does, in every validator.** The shared lxml parser (`family.xml_parser`) follows the
  declared encoding, so it reports `XML_MALFORMED` on files .NET loads — UTF-8 declared `UTF-16`, as `StringWriter`
  writes, non-ASCII declared `us-ascii`, UTF-32 with a byte-order mark — and refuses a prefix bound to the XML
  namespace, which .NET allows; it also accepts `version="1.1"`, which .NET refuses (`feature-dgf-specific-skills.md`)
- **XmlSerializer's refusals before `Table.InitFields`.** A child element in `primarykey`, a root that is not
  `entity`, a `required` that is not an xsd:boolean, a `type` no `FieldTypeEnum` member names, a bad `xml:space`,
  `version="1.1"` and BOM-less UTF-16 each make an entity's load throw; `validate_model.py` reports none of them
  (`feature-dgf-specific-skills.md`)
- **`xsi:nil` on an entity.** On `fields`, a `field` or the root it binds nothing, a null field, or a null table —
  each a load that throws or returns nothing — and the entity-load check passes all three
  (`feature-dgf-specific-skills.md`)
- **A `settings.xml` with a DTD.** The runtime reads it; `model.read_entity` refuses it, so its entity-load and
  generated-file checks report `NOT RUN` (`knowledge/data-model.md` §3.6; `feature-dgf-specific-skills.md`)
- **Match `XmlDocument.LoadXml` in `model._parse_error`** where expat cannot: a prefix or default namespace bound to
  the XML namespace, and a surrogate pair as two character references. LoadXml takes both, so today's block on them
  is false (`knowledge/data-model.md` §3.6; `feature-dgf-specific-skills.md`)
- **A reference into an entity that cannot load.** The entity is blocked once (`MODEL_ENTITY_UNLOADABLE`), but a
  reference into it still resolves, so an entity broken at the merge-base lets a new reference pass the gate — and
  the referrer's warning says the runtime generates a default, which it cannot (`feature-dgf-specific-skills.md`)
- **The audit validates XML outside `FM/`.** A malformed `a/tools/_workflow.xml`, which no loader reads, is reported
  as a defect in the root; leave it out, as draft JSON is (`feature-dgf-specific-skills.md`)
- **A reach through a file the graph cannot read reads as complete.** `graph._parse` returns no references on an
  `OSError`; the report should say so, as the validators' catch does (`feature-dgf-specific-skills.md`)
- **`/dgf-implement` without git, for a task that deletes.** Step 3.4 runs the whole-root check with no baseline, so
  it cannot tell whether the removal broke another file; `/dgf-process` and `/dgf-model` pass
  `check_change.py --save-baseline` before the write and `--baseline` after it, and it could do the same
  ([ADR 0025](../docs/adr/0025-saved-baseline-without-git.md); `patches/2026-09-29-09.08.md`)
- **The baseline keys on the message, the gate's and the saved one alike.** A finding whose message quotes something a
  harmless edit changes — `MODEL_REFERENCE_APP_DEPENDENT`'s application list, a view-template reason quoting a
  renamed key — reads as new. Decide whether such a message should carry a stable part for the key to use
  ([ADR 0018](../docs/adr/0018-change-relative-gates.md), [ADR 0025](../docs/adr/0025-saved-baseline-without-git.md))
- **Re-read `composition-specs.md`'s `angular.json` digest.** Its ledger entry for `src/DGF.UI/angular.json` is stamped
  at an older DGF commit than `1d5999186`; the fact holds, the digest is stale. Maintainer work: run
  `tools/check_drift.py` against a DGF checkout and re-stamp (`provenance/knowledge/composition-specs.md`)

## Completed

| Milestone | Date |
|-----------|------|
| Design Blueprint | 2026-09-19 |
| Pipeline Bootstrap | 2026-09-18 |
| Verified DGF Fact Base | 2026-09-19 |
| Reader-Facing Documentation | 2026-09-19 |
| Open Decisions Closed | 2026-09-21 |
| Plugin Manifest & Walking Skeleton | 2026-09-22 |
| DGF Knowledge Base | 2026-09-22 |
| Deterministic Validators | 2026-09-24 |
| Pipeline Spine | 2026-09-25 |
| Gate Contract Wired | 2026-09-25 |
| Learning Loop | 2026-09-26 |
| DGF-Specific Skills | 2026-10-04 |
