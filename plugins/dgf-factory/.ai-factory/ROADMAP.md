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
- [ ] **Plugin Manifest & Walking Skeleton** — `.claude-plugin/plugin.json` plus one loadable skill, so Claude Code can discover the plugin at all
- [ ] **DGF Knowledge Base** — `knowledge/` facts tree and the vendored JSON/XSD schema set; every fact stamped `dgf_version` + `read_date` + per-source `sha256`, behavioural facts additionally carrying a `since`/`until` range, with a `MANIFEST.md` recording the DGF commit SHA and a re-vendor process ([ADR 0003](../docs/adr/0003-version-gating.md))
- [ ] **Deterministic Validators** — shared `scripts/` that resolve schema family before parsing, resolve components, and check runtime parity before reporting success; plus the four process-semantic checks ADR 0002 commits to — dead transition, unreachable state, handler resolution, process `BASE:` references — a known-bad fixture corpus, and the version drift check ([ADR 0002](../docs/adr/0002-process-verification.md), [ADR 0003](../docs/adr/0003-version-gating.md))
- [ ] **Pipeline Spine** — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`, `/dgf-commit` with DGF domain content over the AI Factory step structure
- [ ] **Gate Contract Wired** — `dgf-gate-result` blocks carrying `schema_family`, `checks_run`, affected components and affected processes, last-block-wins; a gate may never read as having passed a check it did not run ([ADR 0002](../docs/adr/0002-process-verification.md))
- [ ] **Learning Loop** — `/dgf-fix` and `/dgf-evolve`, turning DGF gotchas into patches and skill-context overrides
- [ ] **DGF-Specific Skills** — `/dgf-component`, `/dgf-process`, `/dgf-audit`, then `/dgf-model`; `/dgf-scaffold` stays here (the estate is brownfield-dominant) and **drives the existing bootstrap template** rather than emitting files — blocked until that template is identified, since it is not in first-party DGF ([ADR 0004](../docs/adr/0004-authoring-entry-point.md))
- [ ] **Quality & Authoring Skills** — `/dgf-review`, `/dgf-rules`, `/dgf-rules-check`, `/dgf-qa`, `/dgf-docs`, `/dgf-explore`, `/dgf-grounded`, `/dgf-archive`
- [ ] **Parallel Execution** — coordinator and worktree-isolated workers
- [ ] **Marketplace Release** — register `dgf-factory` in `.claude-plugin/marketplace.json` and verify a clean install

## Completed

| Milestone | Date |
|-----------|------|
| Design Blueprint | 2026-09-19 |
| Pipeline Bootstrap | 2026-09-18 |
| Verified DGF Fact Base | 2026-09-19 |
| Reader-Facing Documentation | 2026-09-19 |
| Open Decisions Closed | 2026-09-21 |
