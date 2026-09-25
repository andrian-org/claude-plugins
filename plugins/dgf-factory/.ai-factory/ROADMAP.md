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
- [ ] **Gate Contract Wired** — `dgf-gate-result` blocks carrying `schema_family`, `checks_run`, affected components and affected processes, last-block-wins; a gate may never read as having passed a check it did not run. `scripts/lib/gate_result.py` builds every block, the doctor's included — today the doctor's always reports `"blocking": true` and suggests the unbuilt `/dgf-fix`, even on a pass — with `blocking` true exactly when `status` is `fail`. Also: `check_plan.py` checks that a plan's Commit Plan groups agree with its task numbering, which is still left to the model ([ADR 0014](../docs/adr/0014-process-verification-runtime-resolution.md); follow-ups in `plans/feature-pipeline-spine.md`)
- [ ] **Learning Loop** — `/dgf-fix` and `/dgf-evolve`, turning DGF gotchas into patches and skill-context overrides. An override may only tighten a skill — add rules and checks, never relax a STOP, an exit-code row, the gate's status table or a Critical Rule — because anyone who commits to the estate can write one; `/dgf-evolve` writes within that limit
- [ ] **DGF-Specific Skills** — `/dgf-component`, `/dgf-process`, `/dgf-audit`, then `/dgf-model`; `/dgf-scaffold` stays here (the estate is brownfield-dominant) and **drives the existing bootstrap template** rather than emitting files — blocked until that template is identified, since it is not in first-party DGF ([ADR 0004](../docs/adr/0004-authoring-entry-point.md))
- [ ] **Quality & Authoring Skills** — `/dgf-review`, `/dgf-rules`, `/dgf-rules-check`, `/dgf-qa`, `/dgf-docs`, `/dgf-explore`, `/dgf-grounded`, `/dgf-archive`
- [ ] **Parallel Execution** — coordinator and worktree-isolated workers
- [ ] **Marketplace Release** — register `dgf-factory` in `.claude-plugin/marketplace.json` and verify a clean install, with `/dgf-doctor` clean, including no DGF paths in shipped files. First decide whether maintainer material (`docs/`, `.ai-factory/`, `tools/`, `provenance/`) must also leave the plugin folder ([ADR 0012](../docs/adr/0012-no-dgf-paths-in-shipped-files.md) follow-up), and whether `/dgf`, `/dgf-plan`, `/dgf-implement` and `/dgf-commit` can stop pre-approving every git command (`Bash(git *)`) — their `git -C "<root>" <subcommand>` form needs a wildcard before the subcommand, which Claude Code warns about

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
