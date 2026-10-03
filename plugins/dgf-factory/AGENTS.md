# AGENTS.md

> Map of this plugin for AI agents and new contributors. Update when the structure
> changes significantly. Detailed content lives in linked files — this is a navigation
> index, not a duplicate.

## Project Overview

`dgf-factory` is a Claude Code plugin that ports the AI Factory prompt-and-artifact
pipeline into a DGF-specific agent factory: the same deterministic
plan → implement → verify → commit pipeline, but shipping pre-loaded knowledge of the
DotGov Framework (.NET 10 / Angular 19 Component-Hosted Pluggable Monolith) instead of
deriving the stack at setup time.

The pipeline spine exists — `/dgf`, `/dgf-plan`, `/dgf-implement`, `/dgf-verify`,
`/dgf-commit`, beside `/dgf-doctor` — on the knowledge base and the validators, and so does the
learning loop — `/dgf-fix` records a patch for each fix inside a plan's scope, `/dgf-evolve`
distils patches into skill-context overrides that `check_override.py` checks before any skill
reads one. Five DGF-specific skills exist too — `/dgf-component`, `/dgf-process`, `/dgf-model`
write one kind of configuration each, only inside a plan's scope, and `/dgf-audit` reports the
root's health and a file's blast radius from a reference graph resolved per application;
`/dgf-scaffold` creates a new application from an empty folder, generated from shipped templates. See
[.ai-factory/DESCRIPTION.md](.ai-factory/DESCRIPTION.md) for scope and verified framework facts,
[docs/pipeline.md](docs/pipeline.md) for how a change flows, and [docs/adr/](docs/adr/README.md)
for the decisions that shape it.

## Tech Stack

- **Primary medium:** Markdown (skills written prompt-as-program)
- **Scripting:** Node.js (`.mjs`), Python 3.9+ — the validators use `lxml` and `jsonschema`,
  hash-pinned in `scripts/requirements.txt`
- **Packaging:** Claude Code plugin — `.claude-plugin/plugin.json` + marketplace entry
- **Target framework:** DotGov Framework — .NET 10, Angular 19.2, SQL Server + EF Core
- **Build system:** none — there is no compile step
- **Database:** none (this plugin holds no runtime state)

## Project Structure

```
plugins/dgf-factory/
├── README.md                   # Landing page — what this plugin is, status, doc links
├── AGENTS.md                   # This file — navigation index
├── .claude-plugin/             # The plugin manifest — Claude Code reads it nowhere else
│   └── plugin.json             #   name, version, description; component paths use defaults
├── skills/                     # The shipped dgf-* corpus (auto-discovered)
│   ├── dgf-doctor/             #   is the plugin installed correctly?
│   │   ├── SKILL.md            #     the prompt-program
│   │   └── scripts/doctor.py   #     the structural validator it calls
│   ├── dgf/                    #   set up a workspaces root: config.yaml + DESCRIPTION.md templates
│   ├── dgf-plan/               #   fast/full/ultra plans; references/PLAN-FORMAT.md, ULTRA-FORMAT.md
│   ├── dgf-implement/          #   execute a plan task by task; references/IMPLEMENTATION-GUIDE.md
│   ├── dgf-verify/             #   the change gate; references/GATE-RESULT-CONTRACT.md
│   ├── dgf-commit/             #   conventional commits scoped by workspace
│   ├── dgf-fix/                #   fix inside the plan's scope, record a patch; references/PATCH-FORMAT.md
│   ├── dgf-evolve/             #   distil patches into overrides; references/OVERRIDE-FORMAT.md
│   ├── dgf-component/          #   inspect, validate or scaffold a component, both families
│   ├── dgf-process/            #   inspect, validate, author or modify a process or workflow; templates/
│   ├── dgf-model/              #   inspect, validate, add or modify an entity's settings.xml; templates/
│   ├── dgf-audit/              #   read-only: the root's health, and a file's blast radius
│   └── dgf-scaffold/           #   a new application from an empty folder; scripts/ design, generate, check;
│                               #     templates/ solution, workspace, patterns + manifest.json; references/DESIGN-FORMAT.md
├── knowledge/                  # The DGF knowledge base — every fact stamped; no DGF paths (ADR 0012)
│   ├── README.md               #   the stamping convention (the only unstamped file); §7 machine-read tables
│   ├── schema-families.md      #   two families, resolution rules, correspondence, runtime parity (67 rows)
│   ├── component-catalogue.md  #   34 dispatchable components; why 4 other counts differ
│   ├── composition-specs.md    #   workspace layout, applibs*, 5 legacy artifacts, events, XML-always, code places
│   ├── naming-conventions.md   #   directory/file/type names a generator must reproduce exactly
│   ├── json-reader.md          #   how the runtime reads component JSON: options, dispatch, folders, file refs
│   ├── process-model.md        #   process.xsd vs the runtime model; how references resolve
│   ├── data-model.md           #   entities, fields, relations; what each model loader does with a reference
│   ├── reference-graph.md      #   every reference as an edge: its rule, When absent, When empty, Reach, Checked by
│   ├── permissions.md          #   where the root names roles; that nothing in it declares one
│   ├── application-layout.md   #   a new application: workspace minimum, application row, roles, sign-in, host, local stack (§7 tables)
│   └── schemas/                #   vendored set — json/ xsd/ standalone/ + MANIFEST.md (dialects, membership)
├── scripts/                    # SHIPPED validators skills call — exit 0/1/2/3, one output format (docs/skill-authoring.md)
│   ├── validate_config.py      #   family, schema (read the runtime's way) and parity, both families
│   ├── resolve_components.py   #   component types (JSON and forms) and component file references
│   ├── validate_process.py     #   process structure + semantics; workflow CHANGE_STATE targets
│   ├── validate_model.py       #   an entity's and a form's references, an entity's load, a form's cells (ADR 0027 §3)
│   ├── route_means.py          #   ADR 0010's order of means: JSON or legacy XML for a new config
│   ├── locate_plan.py          #   the workspaces root and the active plan (ADR 0017 §6)
│   ├── inventory_root.py       #   each workspace, counted; what is not one
│   ├── check_plan.py           #   a plan's header, tasks, Commit Plan, file classes, routes, bundle, overlaps
│   ├── check_change.py         #   a branch's change against its plan and the merge-base (ADR 0018)
│   ├── verify_gate.py          #   the verify gate: every check, the status computed, one block (ADR 0022)
│   ├── check_patches.py        #   the patches' format, and which are new against the cursor (ADR 0024)
│   ├── check_override.py       #   may a skill read its override: shape, sources, forbidden, limit (ADR 0024)
│   ├── audit_root.py           #   the whole-root audit, or a file's reach per application (ADR 0027 §5)
│   ├── requirements.txt        #   lxml + jsonschema, exact pins with hashes (Python 3.9+)
│   └── lib/                    #   report, deps, knowledge, cli, family, json_*, prepass, xsd, parity, workspace,
│                               #   process_checks, plan, git, runner, baseline, gate_result, patches, overrides,
│                               #   model, edges, graph, roles
├── tests/                      # NOT SHIPPED — unittest suite; fixtures/unit/ and the known-bad corpus
├── provenance/                 # NOT SHIPPED — where each knowledge file's facts were read from
│   └── knowledge/              #   one ledger per knowledge file, same relative path: DGF paths + sha256
├── tools/                      # NOT SHIPPED — repo-maintenance tools contributors run
│   ├── check-dual-schema-docs.sh  # doc, decision-record, manifest and stamp contracts; section 8 runs the tests
│   ├── check_knowledge_stamps.py  # stamps, ledgers and vendored digests; section 7 invokes it
│   ├── vendor_schemas.py          # re-vendors DGF's schema set, rewriting DGF paths on the way in
│   ├── derive_sql_types.py        # the SQL type of each dbtype, tallied from DGF's settings/table pairs (data-model.md §6)
│   ├── run_known_good.py          # every validator over DGF's samples (via scripts/lib/runner.py); each error excused
│   ├── known-good-exceptions.txt  # the evidenced excuses, and the warning baseline
│   ├── check_drift.py             # the provenance ledgers' digests against a DGF checkout
│   └── requirements.in            # the validator dependencies, compiled with uv
├── docs/                       # Detailed documentation, one topic per page
│   ├── adr/                    #   architecture decision records — README.md is the index
│   ├── getting-started.md      #   prerequisites, repo layout, build order
│   ├── architecture.md         #   slice structure and dependency rules
│   ├── skill-authoring.md      #   SKILL.md contract, gates, exit codes
│   ├── dgf-knowledge.md        #   sourcing and version-stamping DGF facts
│   ├── dgf-schemas.md          #   the two schema families: JSON + XSD, parity, vendoring
│   ├── pipeline.md             #   the spine, .dgf-factory/, the plan format, the change gate, the loop, the DGF-specific skills
│   └── blueprint.md            #   the full design: AI Factory teardown + DGF mapping
├── .mcp.json                   # MCP servers — dgf-mcp only; both dev config and shipped
├── .ai-factory.json            # AI Factory 2.18.1 install receipts (managed-skill ownership)
├── skills-lock.json            # skills.sh install lock for externally sourced skills
├── .ai-factory/                # Pipeline artifacts — single-writer ownership per command
│   ├── config.yaml             #   language, paths, workflow, git settings
│   ├── DESCRIPTION.md          #   what this project is; verified DGF facts; risks
│   └── rules/base.md           #   detected project conventions
└── .claude/
    ├── skills/                 # 29 aif skills (the reference pipeline) +
    │                           # plugin-structure (Claude Code plugin layout reference)
    └── agents/                 # 19 subagents — coordinators, workers, loop roles, sidecars
```

Not yet created: `agents/`. The manifest and the `/dgf-doctor` walking skeleton landed with roadmap milestone 6,
the `knowledge/` base with milestone 7, the validators, both corpora and the drift check with
milestone 8, the pipeline spine with milestone 9, the wired gate contract — `lib/gate_result.py`,
`verify_gate.py`, the Commit Plan check — with milestone 10, and the learning loop —
`/dgf-fix`, `/dgf-evolve`, `check_patches.py`, `check_override.py` — with milestone 11. Milestone
12 added `/dgf-component`, `/dgf-process`, `/dgf-model` and `/dgf-audit`, `validate_model.py` in the
gate, `audit_root.py`, and the three knowledge files they read; `/dgf-scaffold`, with `knowledge/application-layout.md`
and the field-type tables, closed it.

## Key Entry Points

| File | Purpose |
|---|---|
| [.claude-plugin/plugin.json](.claude-plugin/plugin.json) | The manifest. Component paths are left to their defaults — declaring one restates it. |
| [skills/dgf-doctor/SKILL.md](skills/dgf-doctor/SKILL.md) | The first prompt-as-program. The house style the next slices copy. |
| [skills/dgf-doctor/scripts/doctor.py](skills/dgf-doctor/scripts/doctor.py) | Structural validator — manifest, slices, portability (including DGF paths in shipped files), line endings; emits the gate block |
| [scripts/validate_config.py](scripts/validate_config.py) | The dual-family config validator: family first, the runtime's JSON reader, the parity gate |
| [scripts/validate_process.py](scripts/validate_process.py) | Process verification as ADR 0014 defines it, over a workspaces root |
| [scripts/validate_model.py](scripts/validate_model.py) | The data model's references, resolved each loader's way, blocking only where the loader throws; an entity's own load; a form's cells (ADR 0027 §3) |
| [scripts/audit_root.py](scripts/audit_root.py) | The whole-root audit and blast radius: validators, the graph per application, unresolved references, roles — never a gate (ADR 0027 §5) |
| [scripts/lib/edges.py](scripts/lib/edges.py) | Reads one file's references row by row of the `reference-edges` table; no edge kind is named in code |
| [scripts/lib/graph.py](scripts/lib/graph.py) | The reference graph of one application, and reach over it |
| [scripts/check_plan.py](scripts/check_plan.py) | Every rule a plan must meet (ADR 0017), and the overlap with other branches' plans |
| [scripts/check_change.py](scripts/check_change.py) | The change checks: scope, means, planned files, and new findings against the merge-base (ADR 0018) |
| [scripts/verify_gate.py](scripts/verify_gate.py) | The verify gate `/dgf-verify` relays: the plan and change checks in-process, the task audit, the computed block (ADR 0022) |
| [scripts/check_override.py](scripts/check_override.py) | Whether a skill may read its skill-context override; the ten readers run it first, and a refused override is never read (ADR 0024) |
| [scripts/lib/overrides.py](scripts/lib/overrides.py) | The override template, its sources, the `FORBIDDEN` constructs and the `LIMIT_WORDS` — what the check decides and what it hands to judgement |
| [scripts/check_patches.py](scripts/check_patches.py) | The patch format (`lib/patches.py`), and which patches `/dgf-evolve` has not seen |
| [scripts/lib/gate_result.py](scripts/lib/gate_result.py) | The one builder of every `dgf-gate-result` block — status from the entries, refusals, rendering; stdlib only |
| [scripts/lib/plan.py](scripts/lib/plan.py) | The plan file's flat header, its tasks and Commit Plan, every path's class, and the artifact a path is |
| [skills/dgf-verify/references/GATE-RESULT-CONTRACT.md](skills/dgf-verify/references/GATE-RESULT-CONTRACT.md) | What the verify gate's block holds and how its status is computed |
| [scripts/lib/report.py](scripts/lib/report.py) | Every finding code and the exit code it forces — the single source of severity |
| [tools/run_known_good.py](tools/run_known_good.py) | Maintainer-only: the validators over DGF's samples, held to `tools/known-good-exceptions.txt` |
| [skills/dgf-scaffold/scripts/design.py](skills/dgf-scaffold/scripts/design.py) | The scaffold's design check: the folder is empty, names, references, data model, SQL types, what is open, every default |
| [skills/dgf-scaffold/scripts/generate.py](skills/dgf-scaffold/scripts/generate.py) | Renders a new application from the design and `templates/manifest.json`; `--check` is the post-generation check (`check.py`) |
| [skills/dgf-scaffold/references/DESIGN-FORMAT.md](skills/dgf-scaffold/references/DESIGN-FORMAT.md) | The design file, `docs/application.json`: every key, its rule and its default |
| [knowledge/application-layout.md](knowledge/application-layout.md) | What a new DGF application is made of — the framework facts the scaffold's templates rest on |
| [knowledge/README.md](knowledge/README.md) | The stamping convention every DGF fact follows — read before writing or citing a fact |
| [knowledge/schemas/MANIFEST.md](knowledge/schemas/MANIFEST.md) | What the vendored schema set holds: directories, dialects, membership |
| [provenance/knowledge/schemas/MANIFEST.md](provenance/knowledge/schemas/MANIFEST.md) | Maintainer-only: the DGF commit, upstream and shipped `sha256` per file, the path rewrite, the re-vendor process |
| [docs/pipeline.md](docs/pipeline.md) | How a change flows through the spine, the loop and the DGF-specific skills, and what each script decides |
| [docs/blueprint.md](docs/blueprint.md) | The design. Read Part 2 §"Build order" before writing any skill. |
| [.ai-factory/DESCRIPTION.md](.ai-factory/DESCRIPTION.md) | Project scope, verified DGF facts, the delivery model |
| [docs/adr/README.md](docs/adr/README.md) | Decision records — read before reopening a settled question |
| [docs/adr/0024-learning-loop-revised.md](docs/adr/0024-learning-loop-revised.md) | The learning loop: patches, overrides, the limit an override may not cross, and the script that checks one |
| [docs/adr/0027-dgf-specific-skills-revised.md](docs/adr/0027-dgf-specific-skills-revised.md) | The DGF-specific skills: authoring scope, the artifact partition, the model check, the graph, blast radius, roles |
| [.ai-factory/config.yaml](.ai-factory/config.yaml) | Language, paths, git and workflow settings for the pipeline |
| [.ai-factory/rules/base.md](.ai-factory/rules/base.md) | Naming, error handling, exit-code contract, skill authoring rules |
| [.mcp.json](.mcp.json) | MCP servers available to agents in this project |
| [.claude/skills/aif/SKILL.md](.claude/skills/aif/SKILL.md) | The setup skill this project was configured with |
| [.claude/skills/plugin-structure/SKILL.md](.claude/skills/plugin-structure/SKILL.md) | Canonical Claude Code plugin layout and manifest reference |

## External References

| Resource | Location | Why it matters |
|---|---|---|
| DotGov Framework | `~/workspaces/dotgov/_DotGovFramework/DotGovFramework` | The domain being encoded. Its `AGENTS.md` maps the framework. |
| DGF JSON schemas | `DotGovFramework/src/Tools/dgf-mcp/Schemas/Json/` | 69 generated component-config schemas — the modern family. MCP: `list_available_json_schemas` |
| DGF XSD schemas | `DotGovFramework/src/Tools/dgf-mcp/Schemas/XSD/` + `Schemas/XmlReference/` | 9 XSDs plus the generated legacy XML grammar reference. MCP: `list_available_xsd_schemas` |
| DGF format coverage | `DotGovFramework/docs/wiki/AI-Authoring/format-coverage.md` | **The runtime-parity authority.** Which components the runtime actually parses JSON for, and the current XML-always generation policy |
| DGF standalone contracts | `DotGovFramework/docs/schemas/` | Only 3 hand-authored JSON contracts (`componentValidator`, `dataFetcherConfiguration`, `eventBase`) — **not** the generated set; only the first is synced into the MCP |
| DGF release notes | `DotGovFramework/docs/wiki/Release-notes/` | The only version-aware surface DGF offers. MCP: `get_release_notes("since:X.Y.Z")` |
| DGF workspace layout | `DotGovFramework/src/Core/DGF.Kernel/WorkspaceSettings.cs` | The `FM/_PROCESS`, `_WORKFLOW`, `_COMPONENTS` constants and the base-workspace inheritance chain |
| DGF docs MCP | `https://dgf-mcp.dotgov.uk/mcp` | Hosted DGF documentation, wired in `.mcp.json` |
| Sibling plugin | `../doc-coverage-audit/` | Layout conventions for a plugin in this marketplace |
| Marketplace manifest | `../../.claude-plugin/marketplace.json` | Where this plugin must be registered to ship |

## Documentation

| Document | Path | Description |
|---|---|---|
| README | `README.md` | Plugin landing page |
| Getting Started | `docs/getting-started.md` | Prerequisites, repo layout, loading it locally, trying the spine |
| Pipeline Spine | `docs/pipeline.md` | The five skills, `.dgf-factory/`, plan format, change gate, learning loop, the DGF-specific skills |
| Architecture | `docs/architecture.md` | Slice structure and dependency rules |
| Skill Authoring | `docs/skill-authoring.md` | SKILL.md contract, gates, exit codes |
| DGF Knowledge Sourcing | `docs/dgf-knowledge.md` | Citing and version-stamping DGF facts |
| DGF Schemas | `docs/dgf-schemas.md` | The two schema families (JSON + XSD), runtime parity, vendoring |
| Decision Records | `docs/adr/README.md` | Index of architecture decisions — delivery model, process verification, validator runtime, version gating, scope, default rules |
| Architecture Blueprint | `docs/blueprint.md` | AI Factory teardown and the DGF mapping |
| Repository README | `../../README.md` | The `dotgov` marketplace and how to install its plugins |

## AI Context Files

| File | Purpose |
|---|---|
| `AGENTS.md` | This navigation index — structure, entry points, external references |
| `.ai-factory/DESCRIPTION.md` | Project specification: scope, stack, verified facts, risks |
| `.ai-factory/ARCHITECTURE.md` | Architecture pattern, folder structure and dependency rules |
| `.ai-factory/rules/base.md` | Project coding and authoring conventions |
| `CLAUDE.md` | Not present. Claude Code reads `AGENTS.md` in its place. |

## Agent Rules

- **Decisions live in `docs/adr/`.** [docs/adr/README.md](docs/adr/README.md) is the index.
  Before reopening a settled question — delivery model, what "process verified" means, version
  gating, the validator runtime, the unit of work, the default rule set — read the ADR that
  closed it. Process verification, the validator runtime and version gating are decided by
  [ADR 0014](docs/adr/0014-process-verification-runtime-resolution.md),
  [ADR 0015](docs/adr/0015-validator-runtime-and-json-reader.md) and
  [ADR 0013](docs/adr/0013-version-gating-provenance-ledger.md); the plan format, change-relative
  gates and the declared DGF version by [ADR 0017](docs/adr/0017-plan-file-format.md),
  [ADR 0018](docs/adr/0018-change-relative-gates.md) and
  [ADR 0019](docs/adr/0019-declared-dgf-version.md); the gate block — who builds it, how its
  status is computed, what it may claim, which command it suggests — by
  [ADR 0022](docs/adr/0022-gate-block-contract-revised.md); the learning loop — patches, overrides,
  the limit an override may not cross, and the script that checks one — by
  [ADR 0024](docs/adr/0024-learning-loop-revised.md); the DGF-specific skills — authoring scope, the
  artifact partition, the model check, the reference graph and blast radius — by
  [ADR 0027](docs/adr/0027-dgf-specific-skills-revised.md), whose §7 also designs `/dgf-scaffold`, and
  the scaffold's reversal of "drive a template" together with the whole-root unit by
  [ADR 0026](docs/adr/0026-authoring-entry-point-revised.md); a writing skill's baseline without git — saved
  before the write, never the gate's — by [ADR 0025](docs/adr/0025-saved-baseline-without-git.md);
  0002, 0003, 0004, 0006, 0007, 0008, 0020, 0021 and 0023 are superseded history.
  Reverse a decision with a new ADR that supersedes the old one in full; never by editing it. The
  only in-place edit is a dated erratum that corrects a fact without changing the decision.
  A `proposed` ADR decides nothing until it is accepted.
- **This plugin's architecture derives from AI Factory and depends on nothing else.** It takes
  no dependency on any other DGF agent-tooling effort and is not obliged to track another
  repository's ADR series ([ADR 0001](docs/adr/0001-independent-plugin-with-ai-factory-derived-architecture.md)).
- **Framework facts must be verified, never assumed.** The blueprint's Part 2 is marked
  `[assume]` throughout because it was written from one sentence of description. Confirm
  against the DGF repository or the DGF docs MCP before writing a fact into a skill, and
  cite where it came from.
- **No DGF repository paths in shipped files** ([ADR 0012](docs/adr/0012-no-dgf-paths-in-shipped-files.md)).
  Files a developer installs never contain a path into the DGF repository: no `src/…`, no
  `docs/wiki/…`, no local checkout path. Shipped files
  are everything under the directories `doctor.py` lists in `SHIPPED_DIRS` (`skills/`,
  `agents/`, `commands/`, `scripts/`, `knowledge/`, `.claude-plugin/`). A developer's install
  has no DGF checkout, so shipped content cites the shipped `knowledge/` base or a DGF docs MCP
  tool instead. Workspace layout paths such as `FM/_COMPONENTS/` are allowed: they describe the
  developer's own workspaces, not the DGF repository. Maintainer material (`docs/`, ADRs,
  `.ai-factory/`, `provenance/`, `tools/`) still cites DGF paths as evidence. A fact's DGF
  sources go in its `provenance/` ledger, never in the knowledge file. `doctor.py` blocks on a
  violation.
- **Determinism before prompting.** If a JSON Schema, an XSD, or a script can decide the
  question, write the script. Do not encode a statically checkable rule as a prompt
  instruction.
- **Both schema families, always — and check parity.** DGF supports modern JSON component
  config *and* legacy XML. Any task touching component schemas — validating, generating,
  inspecting — resolves the family first and handles both; never default to JSON. And
  never treat a passing JSON validation as proof the runtime reads JSON: `Workflow` and
  `ProcessFlow` validate against schemas the runtime ignores
  ([ADR 0011](docs/adr/0011-schema-parity-authority.md)). `scripts/validate_config.py`
  implements the rule; use it, not a hand-rolled check. See
  [docs/dgf-schemas.md](docs/dgf-schemas.md).
- **Single-writer artifacts.** Each `.ai-factory/` artifact has exactly one owning
  command; everything else treats it as read-only input.
- **Do not fork `aif-*` skills.** They are managed by the AI Factory installer and tracked
  in `.ai-factory.json`; hand-edits are detected and overwritten on update.
- **LF line endings only.** Enforced by `.gitattributes` — CRLF breaks shebangs and
  heredocs in plugin scripts.
- **Decompose shell commands** — run one operation per call rather than chaining
  with `&&`, so a failure is attributable and a denied step does not hide the rest.
  - Incorrect: `git checkout main && git pull`
  - Correct: first `git checkout main`, then `git pull origin main`
