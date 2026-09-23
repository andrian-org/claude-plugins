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

Setup stage — the design exists, the `dgf-*` skill corpus does not yet.
See [.ai-factory/DESCRIPTION.md](.ai-factory/DESCRIPTION.md) for scope and verified
framework facts, and [docs/adr/](docs/adr/README.md) for the decisions that shape it.

## Tech Stack

- **Primary medium:** Markdown (skills written prompt-as-program)
- **Scripting:** Node.js (`.mjs`), Python 3
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
│   └── dgf-doctor/             #   walking skeleton — is the plugin installed correctly?
│       ├── SKILL.md            #     the prompt-program
│       └── scripts/doctor.py   #     the structural validator it calls
├── knowledge/                  # The DGF knowledge base — every fact stamped; no DGF paths (ADR 0012)
│   ├── README.md               #   the stamping convention (the only unstamped file)
│   ├── schema-families.md      #   two families, resolution rules, correspondence, runtime parity
│   ├── component-catalogue.md  #   34 dispatchable components; why 4 other counts differ
│   ├── composition-specs.md    #   workspace layout, 5 legacy artifacts, events, XML-always policy
│   ├── naming-conventions.md   #   directory/file/type names a generator must reproduce exactly
│   └── schemas/                #   vendored set — json/ xsd/ standalone/ + MANIFEST.md (dialects, membership)
├── provenance/                 # NOT SHIPPED — where each knowledge file's facts were read from
│   └── knowledge/              #   one ledger per knowledge file, same relative path: DGF paths + sha256
├── tools/                      # NOT SHIPPED — repo-maintenance tools contributors run
│   ├── check-dual-schema-docs.sh  # documentation, decision-record, manifest and stamp contracts
│   ├── check_knowledge_stamps.py  # stamps, ledgers and vendored digests; section 7 invokes it
│   └── vendor_schemas.py          # re-vendors DGF's schema set, rewriting DGF paths on the way in
├── docs/                       # Detailed documentation, one topic per page
│   ├── adr/                    #   architecture decision records — README.md is the index
│   ├── getting-started.md      #   prerequisites, repo layout, build order
│   ├── architecture.md         #   slice structure and dependency rules
│   ├── skill-authoring.md      #   SKILL.md contract, gates, exit codes
│   ├── dgf-knowledge.md        #   sourcing and version-stamping DGF facts
│   ├── dgf-schemas.md          #   the two schema families: JSON + XSD, parity, vendoring
│   └── blueprint.md            #   the full design: AI Factory teardown + DGF mapping
├── .mcp.json                   # MCP servers — dgf-mcp only; both dev config and shipped
├── .ai-factory.json            # AI Factory 2.18.1 install receipts (managed-skill ownership)
├── skills-lock.json            # skills.sh install lock for externally sourced skills
├── .ai-factory/                # Pipeline artifacts — single-writer ownership per command
│   ├── config.yaml             #   language, paths, workflow, git settings
│   ├── DESCRIPTION.md          #   what this project is; verified DGF facts; risks
│   └── rules/base.md           #   detected project conventions
└── .claude/
    ├── skills/                 # 30 aif-* skills (the reference pipeline) +
    │                           # plugin-structure (Claude Code plugin layout reference)
    └── agents/                 # 19 subagents — coordinators, workers, loop roles, sidecars
```

Not yet created: the rest of the `skills/dgf-*/` corpus, `agents/`, and the dual-schema
validator scripts and drift check (milestone 8). The manifest and the `/dgf-doctor` walking
skeleton landed with roadmap milestone 6; the `knowledge/` base with milestone 7.

## Key Entry Points

| File | Purpose |
|---|---|
| [.claude-plugin/plugin.json](.claude-plugin/plugin.json) | The manifest. Component paths are left to their defaults — declaring one restates it. |
| [skills/dgf-doctor/SKILL.md](skills/dgf-doctor/SKILL.md) | The first prompt-as-program. The house style the next slices copy. |
| [skills/dgf-doctor/scripts/doctor.py](skills/dgf-doctor/scripts/doctor.py) | Structural validator — manifest, slices, portability (including DGF paths in shipped files), line endings; emits the gate block |
| [knowledge/README.md](knowledge/README.md) | The stamping convention every DGF fact follows — read before writing or citing a fact |
| [knowledge/schemas/MANIFEST.md](knowledge/schemas/MANIFEST.md) | What the vendored schema set holds: directories, dialects, membership |
| [provenance/knowledge/schemas/MANIFEST.md](provenance/knowledge/schemas/MANIFEST.md) | Maintainer-only: the DGF commit, upstream and shipped `sha256` per file, the path rewrite, the re-vendor process |
| [docs/blueprint.md](docs/blueprint.md) | The design. Read Part 2 §"Build order" before writing any skill. |
| [.ai-factory/DESCRIPTION.md](.ai-factory/DESCRIPTION.md) | Project scope, verified DGF facts, the delivery model |
| [docs/adr/README.md](docs/adr/README.md) | Decision records — read before reopening a settled question |
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
| Getting Started | `docs/getting-started.md` | Prerequisites, repo layout, loading it locally, build order |
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
  closed it. Process verification and version gating are decided by
  [ADR 0006](docs/adr/0006-process-verification-revised.md) and
  [ADR 0013](docs/adr/0013-version-gating-provenance-ledger.md); 0002, 0003 and 0008 are
  superseded history.
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
  `ProcessFlow` validate against schemas the runtime ignores. See
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
