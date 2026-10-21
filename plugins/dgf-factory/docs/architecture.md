[← Pipeline Spine](pipeline.md) · [Back to README](../README.md) · [Skill Authoring →](skill-authoring.md)

# Architecture

A reader-facing summary. The canonical, enforceable version lives in
[`.ai-factory/ARCHITECTURE.md`](../.ai-factory/ARCHITECTURE.md) — when the two disagree,
that file wins.

**Pattern: Structured Modules (Vertical Slices).** One skill is one self-contained slice.
Shared DGF facts live in `knowledge/`, shared validators in `scripts/`.

## Why this pattern

Every skill is auto-discovered and fires on its own `description`. Nothing calls a skill
as a function, so feature independence is very high and slices that own their material
end-to-end match that reality. A technical-layer split would scatter one skill's prompt,
facts and validator across three trees for no benefit.

Explicit Architecture was considered and rejected: its value is enforcing domain purity
across a dependency-inverted runtime, and there is no runtime here to invert.

## Layout

```text
plugins/dgf-factory/
├── .claude-plugin/plugin.json   # manifest — must live here
├── skills/<name>/               # SLICES — SKILL.md + references/ + scripts/ + templates/
│   ├── dgf-doctor/              #   the install check, with its own scripts/doctor.py
│   ├── dgf, dgf-plan, dgf-implement, dgf-verify, dgf-commit/   # the pipeline spine
│   ├── dgf-fix, dgf-evolve/     #   the learning loop — patches, and overrides that only tighten
│   └── dgf-component, dgf-process, dgf-model, dgf-audit/   # the DGF-specific skills; two ship templates/
├── agents/*.md                  # subagents (not yet built)
├── knowledge/                   # SHARED DOMAIN — versioned DGF facts + vendored schemas
│   └── schemas/{json,xsd,standalone}/   # both families, kept in separate directories
├── scripts/                     # SHARED INFRASTRUCTURE — cross-slice validators
│   ├── validate_config.py       #   family, schema and parity, both families
│   ├── resolve_components.py    #   component types and component file references
│   ├── validate_process.py      #   process structure and semantics, change-state targets
│   ├── validate_model.py        #   the references an entity and a form make, an entity's load, a form's cells
│   ├── route_means.py           #   JSON or legacy XML for a new configuration
│   ├── locate_plan.py           #   the workspaces root and the active plan
│   ├── inventory_root.py        #   each workspace, counted; what is not one
│   ├── check_plan.py            #   a plan's header, tasks, Commit Plan, file classes, routes, overlaps
│   ├── check_change.py          #   a branch's change against its plan and the merge-base
│   ├── verify_gate.py           #   the verify gate: every check, the computed status, one block
│   ├── check_patches.py         #   the patch format; which patches the cursor has not seen
│   ├── check_override.py        #   may a skill read its override: shape, sources, forbidden, limit
│   ├── audit_root.py            #   the whole-root audit, and a file's reach per application
│   ├── requirements.txt         #   lxml + jsonschema, exact pins with hashes
│   └── lib/                     #   what the scripts share (below)
├── .mcp.json                    # MCP servers
├── tests/                       # NOT SHIPPED — unittest suite, fixtures, the known-bad corpus
├── tools/                       # NOT SHIPPED — repo-maintenance checks, vendoring, known-good run, drift check
└── provenance/                  # NOT SHIPPED — the DGF sources of each knowledge file
```

`scripts/lib/` is one module per concern, so a validator stays a short composition:

| Module | Concern |
|---|---|
| `report.py` | Findings, reports, the finding codes and their exit codes, the rendered verdict, the `DEBUG` trace |
| `deps.py` | The import guard: missing `lxml` or `jsonschema` is exit `3` with the install command |
| `knowledge.py` | The loader for the machine-read tables in `knowledge/` (stdlib only; `doctor.py` loads it too) |
| `cli.py` | Argument parsing that exits `3`, and the directory walk |
| `family.py` | Family detection from bytes |
| `json_reader.py`, `prepass.py` | The runtime-faithful JSON reader, and the NJsonSchema inheritance merge |
| `json_resolve.py`, `json_validate.py` | Which schema a JSON file is read against, and validation with the runtime's reader semantics |
| `xsd.py` | Grammar selection, the two-pass `process.xml` check, legacy-grammar lag |
| `parity.py` | The runtime-parity gate |
| `workspace.py` | The workspaces-root model and the engine's reference resolution, exact-case |
| `process_checks.py` | Dead transitions, unreachable states, workflow and change-state references |
| `plan.py` | The plan file's flat header, tasks and Commit Plan; each path's class — config, code, excluded, other — and the artifact it is |
| `git.py` | The read-only git calls — changed files, refs, and a commit's tree written blob by blob |
| `runner.py` | Every validator over a root or some of its files; `tools/run_known_good.py` uses the same runner |
| `baseline.py` | Which findings a branch introduced: the merge-base comparison of [ADR 0018](adr/0018-change-relative-gates.md) |
| `patches.py` | The patch file — name, fields, sections — and the patch cursor ([ADR 0024](adr/0024-learning-loop-revised.md) §1) |
| `overrides.py` | The override template, its sources, the `FORBIDDEN` constructs and the `LIMIT_WORDS` it hands to judgement (ADR 0024 §5) |
| `model.py` | Each model loader's own resolution rule — table, form, lookup view, dialog, grid — an entity's own load, and a form's bound cells ([ADR 0027](adr/0027-dgf-specific-skills-revised.md) §3) |
| `edges.py` | One file's references, read row by row of the `reference-edges` table: elements, condition, values, rule; no edge kind is named in code |
| `graph.py` | The reference graph of one application, reach over it, referrers, unreached shared workflows (ADR 0027 §4) |
| `roles.py` | Every role name the root uses, read from the `role-sources` table, split as the runtime splits it (ADR 0027 §6) |
| `gate_result.py` | Builds, validates and renders every `dgf-gate-result` block, its status computed from its entries ([ADR 0022](adr/0022-gate-block-contract-revised.md)); stdlib only, and imports nothing from its package, so `doctor.py` loads it by path |

`verify_gate.py` is the verify gate: it runs `check_plan.py`'s and `check_change.py`'s checks
in-process and builds the one block `/dgf-verify` relays. No prompt assembles a gate block.

Folder names are Claude Code plugin names rather than the reference pattern's
`src/[Module]/Slices/` names. Auto-discovery only loads components from the plugin's
mandated paths; a tree that ignores them is a tree Claude Code never loads. The pattern's
boundary and dependency rules are kept in full — only the vocabulary is translated.

`knowledge/` and `scripts/` are deliberately **not** auto-discovered. They are plain
files, reached as `${CLAUDE_PLUGIN_ROOT}/knowledge/…` and `${CLAUDE_PLUGIN_ROOT}/scripts/…`.

### Two kinds of script

They live apart, because one kind ships and the other does not
([ADR 0012](adr/0012-no-dgf-paths-in-shipped-files.md)):

| Kind | Who runs it | Where | Example |
|---|---|---|---|
| Runtime validator | A skill calls it mid-run | plugin-root `scripts/` — shipped | `validate_config.py`, `resolve_components.py`, `validate_process.py`, `validate_model.py`, `route_means.py`, `locate_plan.py`, `inventory_root.py`, `check_plan.py`, `check_change.py`, `verify_gate.py`, `check_patches.py`, `check_override.py`, `audit_root.py` |
| Repo-maintenance tool | A contributor runs it by hand | `tools/` — not shipped | `check-dual-schema-docs.sh`, `check_knowledge_stamps.py`, `vendor_schemas.py`, `run_known_good.py`, `check_drift.py` |

A tool may import `scripts/lib/` directly: `run_known_good.py` runs the validators over DGF's
samples through `scripts/lib/runner.py`, the runner the change gate uses. The reverse never happens. A shipped script imports nothing from
`tools/` or `tests/`.

A shipped file names no path into the DGF repository. A maintenance tool may, because it
runs against a DGF checkout that only a maintainer has.

A validator used by exactly one slice lives in that slice's own `scripts/`, not here —
`skills/dgf-doctor/scripts/doctor.py` is the current example. **Promote on the second
use, not in anticipation of it:** a helper moves up to plugin-root `scripts/` when a
second slice actually needs it, not when one might.

## Dependency direction

One way only:

```text
SKILL.md → own references/ + scripts/ → shared knowledge/ + scripts/ → nothing
```

| | Rule |
|---|---|
| ✅ | A skill reads its own `references/` and `templates/`, calls its own `scripts/` |
| ✅ | A skill reads `${CLAUDE_PLUGIN_ROOT}/knowledge/` and calls `${CLAUDE_PLUGIN_ROOT}/scripts/` |
| ✅ | A shared script reads `knowledge/schemas/json/`, `.../xsd/` and `.../standalone/` |
| ❌ | A validator or skill that handles only one schema family |
| ❌ | A slice reads another slice's `references/`, `scripts/` or `templates/` |
| ❌ | Anything in `knowledge/` names a skill, a step number or a pipeline stage |
| ✅ | `/dgf-evolve` reads each target's shipped `SKILL.md`, read-only — the one file of another slice it reads — and writes only overrides under `.dgf-factory/` |
| ❌ | A shared script imports from a slice, branches on who called it, or lists its callers — `check_override.py` takes `--skill`; the contract test holds which skills read an override |
| ❌ | Circular invocation — A invokes B, B invokes A |
| ❌ | Absolute paths, `~/`, or working-directory-relative paths |

**Promote on the second use.** Facts and validators stay local to a slice until a second
slice needs them, then move up to `knowledge/` or `scripts/`. Not in anticipation.

## Two schema families

DGF configurations come in two formats — modern JSON component config and legacy XML —
because the framework still runs systems written against the older one. Both have
committed schemas, and the DGF MCP serves them through separate tool families.

Two rules follow, and both are enforceable architecture rather than advice. Any consumer
of a component schema **resolves the family before parsing** and never defaults to JSON.
And because a JSON schema existing does not mean the runtime reads it — `Workflow` and
`ProcessFlow` are validated by JSON schemas the runtime ignores in favour of
`_workflow.xml` and `process.xml` — a passing validation in an unsupported family is a
warning, not a success.

Full inventories, the correspondence map, the detection contract and the vendoring rules
are in [DGF Schemas](dgf-schemas.md).

## How slices communicate

Skills never call each other as functions. Three mechanisms only:

- **Artifacts.** Each `.dgf-factory/` artifact has exactly one owning slice; every other
  slice treats it as read-only. `/dgf-plan` writes the plan, `/dgf-implement` updates only
  the checkbox ledger, `/dgf-verify` reads both.
- **Gate blocks.** A quality slice ends its report with one fenced `dgf-gate-result` JSON
  block. Callers parse the **last** such block and nothing else — never the prose above it.
- **Command invocation.** A slice may invoke another as a command, but never reaches into
  its files.

## Single-writer ownership

Two slices writing the same file silently destroy each other's work across sessions. The
ownership table is the thing that makes multi-session, multi-agent work non-chaotic.

| Artifact | Owner | Others |
|---|---|---|
| `config.yaml`, `DESCRIPTION.md` | `/dgf` | read-only |
| `PLAN.md`, `plans/<stem>.md` | `/dgf-plan` | `/dgf-implement` updates only the checkboxes |
| `ARCHITECTURE.md` | `/dgf-architecture` | structure notes only |
| `plans/<stem>/` (ultra) | `/dgf-plan` | `/dgf-implement` updates only the ledger in `index.md` |
| `patches/` | `/dgf-fix` — append-only | the latest ten read by `/dgf-implement`, `/dgf-fix`, `/dgf-component`, `/dgf-process` and `/dgf-model` as cautions; consumed by `/dgf-evolve` |
| `skill-context/<skill>/SKILL.md` | `/dgf-evolve` | checked by `check_override.py`, then read by its skill — one of ten readers — never when the check refuses it |
| `evolutions/` — logs and `patch-cursor.json` | `/dgf-evolve` | read-only |
| `knowledge/` | deliberate human edit with a cited source | read-only to every slice |

## See Also

- [Pipeline Spine](pipeline.md) — the spine's five slices, the learning loop's two and the four DGF-specific ones, and how a change flows through them
- [Skill Authoring](skill-authoring.md) — the contract a slice's `SKILL.md` must follow
- [DGF Knowledge Sourcing](dgf-knowledge.md) — the rules governing `knowledge/`
- [DGF Schemas](dgf-schemas.md) — the two schema families and the rules for consuming them
- [Architecture Blueprint](blueprint.md) — why these five ideas were carried over from AI Factory
