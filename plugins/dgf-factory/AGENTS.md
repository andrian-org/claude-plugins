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
See [.ai-factory/DESCRIPTION.md](.ai-factory/DESCRIPTION.md) for scope, verified
framework facts and accepted risks.

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
├── docs/                       # Detailed documentation, one topic per page
│   ├── getting-started.md      #   prerequisites, repo layout, build order
│   ├── architecture.md         #   slice structure and dependency rules
│   ├── skill-authoring.md      #   SKILL.md contract, gates, exit codes
│   ├── dgf-knowledge.md        #   sourcing and version-stamping DGF facts
│   ├── dgf-schemas.md          #   the two schema families: JSON + XSD, parity, vendoring
│   └── blueprint.md            #   the full design: AI Factory teardown + DGF mapping
├── .mcp.json                   # MCP servers: filesystem + hosted DGF docs MCP
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

Not yet created: `.claude-plugin/plugin.json`, `skills/dgf-*/`, `agents/`, and the
DGF knowledge references and validator scripts that the blueprint calls for first.

## Key Entry Points

| File | Purpose |
|---|---|
| [docs/blueprint.md](docs/blueprint.md) | The design. Read Part 2 §"Build order" before writing any skill. |
| [.ai-factory/DESCRIPTION.md](.ai-factory/DESCRIPTION.md) | Project scope, verified DGF facts, the accepted ADR divergence |
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
| DGF ADRs | `DotGovFramework/docs/adr/0701`–`0720` | The harness design series. **Read 0711 and 0716 before changing delivery model.** |
| Existing harness | `DotGovFramework/src/Tools/dgf-harness/` | A built ai-factory extension with 7 `dgf-*` skills — overlaps this plugin's scope |
| DGF docs MCP | `https://dgf-mcp.dotgov.uk/mcp` | Hosted DGF documentation, wired in `.mcp.json` |
| Sibling plugin | `../doc-coverage-audit/` | Layout conventions for a plugin in this marketplace |
| Marketplace manifest | `../../.claude-plugin/marketplace.json` | Where this plugin must be registered to ship |

## Documentation

| Document | Path | Description |
|---|---|---|
| README | `README.md` | Plugin landing page |
| Getting Started | `docs/getting-started.md` | Prerequisites, repo layout, build order |
| Architecture | `docs/architecture.md` | Slice structure and dependency rules |
| Skill Authoring | `docs/skill-authoring.md` | SKILL.md contract, gates, exit codes |
| DGF Knowledge Sourcing | `docs/dgf-knowledge.md` | Citing and version-stamping DGF facts |
| DGF Schemas | `docs/dgf-schemas.md` | The two schema families (JSON + XSD), runtime parity, vendoring |
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

- **Framework facts must be verified, never assumed.** The blueprint's Part 2 is marked
  `[assume]` throughout because it was written from one sentence of description. Confirm
  against the DGF repository or the DGF docs MCP before writing a fact into a skill, and
  cite where it came from.
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
